#!/usr/bin/env python3
"""
fetch_assets.py - build assets/: a local library of REAL photo-scanned PBR textures
and real (photographed) sky HDRIs for the Na Hiku Blender/Cycles renders.

Everything comes from the two big CC0 libraries, ambientCG (Lennart Demes) and
Poly Haven, fetched from hosts that are reachable from the build container
(ambientcg.com / polyhaven.com themselves are blocked there):

  * mat-vis  (github.com/MorePET/mat-vis, release v2026.04.0) re-packs the
    ambientCG and Poly Haven 2K PBR sets as PNG maps inside parquet files on a
    GitHub release; we HTTP-range-read single maps out of them (rowmap offsets).
  * raw.githubusercontent.com / media.githubusercontent.com (Git LFS) - public
    game/web projects that vendor the unmodified Poly Haven / ambientCG files
    (the exact mirror for each asset is recorded in assets/manifest.json).

Usage
  python3 scripts/fetch_assets.py                 # fetch what is missing, rebuild manifest + contact sheet
  python3 scripts/fetch_assets.py --only grass004,kloofendal_48d_partly_cloudy_puresky
  python3 scripts/fetch_assets.py --force         # re-download everything
  python3 scripts/fetch_assets.py --sheet-only    # only rebuild manifest.json + contact_sheet.jpg
  python3 scripts/fetch_assets.py --no-hdri | --no-tex

Output (all paths relative to the project root)
  assets/textures/<category>/<name>/color.jpg     sRGB albedo
                                   normal.jpg    tangent-space normal, ALWAYS OpenGL (+Y/green up)
                                   roughness.jpg linear
                                   ao.jpg        linear (when available)
                                   disp.png      linear height, 0.5 = mid (8- or 16-bit)
                                   metalness.jpg (metals only)
                                   opacity.png   (leaf / blade atlases only)
                                   info.json     per-material stats written by this script
  assets/hdri/<name>.hdr            Radiance HDR, equirectangular, linear Rec.709
  assets/hdri/<name>_nosun.hdr      day skies with the sun disc painted out (use with a Sun lamp)
  assets/hdri/previews/<name>.jpg   tonemapped preview
  assets/manifest.json              [{category,name,files,tile_m,source_url,licence,...}]
  assets/contact_sheet.jpg          labelled thumbnails of everything

Requires: python3, numpy, Pillow, opencv-python (Radiance .hdr I/O), OpenEXR (pip) for .exr sources.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFile, ImageFont

Image.MAX_IMAGE_PIXELS = None
ImageFile.MAXBLOCK = 1 << 26  # optimized JPEG encoding of 4K maps needs a big buffer

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'assets'
TEX = ASSETS / 'textures'
HDRI = ASSETS / 'hdri'
CACHE = ASSETS / '.cache'

MATVIS_TAG = 'v2026.04.0'
MATVIS_BASE = f'https://github.com/MorePET/mat-vis/releases/download/{MATVIS_TAG}/'
RAW = 'https://raw.githubusercontent.com/'
LFS = 'https://media.githubusercontent.com/media/'
UA = 'nahiku-walkthrough-fetch_assets/1.0'

CC0 = 'CC0-1.0 (public domain dedication)'
ATTR_ACG = 'ambientCG.com (Lennart Demes) - CC0, attribution not required'
ATTR_PH = 'Poly Haven (polyhaven.com) - CC0, attribution not required'


def acg_page(i):
    return f'https://ambientcg.com/view?id={i}'


def ph_page(i):
    return f'https://polyhaven.com/a/{i}'


def mv(src, ident):
    """A material taken from the mat-vis 2K tier (ambientCG or Poly Haven)."""
    return {'kind': 'matvis', 'src': src, 'id': ident}


def urls(**maps):
    """A material assembled from direct file URLs (raw GitHub / Git LFS mirrors)."""
    return {'kind': 'url', 'maps': maps}


# --------------------------------------------------------------------------------------------
# THE LIBRARY.  tile_m = real-world width of one texture tile in metres (Poly Haven's published
# dimensions where known, otherwise estimated from features in the photo - see 'tile_note').
# --------------------------------------------------------------------------------------------
TEXTURES = [
    # 1 lawn ---------------------------------------------------------------------------------
    dict(cat='lawn', name='grass004', src=mv('ambientcg', 'Grass004'), tile_m=1.6,
         page=acg_page('Grass004'), attribution=ATTR_ACG,
         tile_note='estimated from blade width (~3 mm) - short mown lawn',
         notes='PRIMARY lawn. Real photo of short, dense, fine-bladed mown turf (yellow-green); '
               'closest available match to Bermuda/zoysia. Use with a little hue/value variation '
               'map at 20-40 m scale to break repetition.'),
    dict(cat='lawn', name='grass001', src=mv('ambientcg', 'Grass001'), tile_m=1.6,
         page=acg_page('Grass001'), attribution=ATTR_ACG,
         tile_note='estimated from blade width',
         notes='Alternate lawn: darker blue-green turf (shade areas / mixing layer).'),
    dict(cat='lawn', name='lawn_soil_thatch', src=mv('ambientcg', 'Ground037'), tile_m=2.0,
         page=acg_page('Ground037'), attribution=ATTR_ACG, tile_note='estimated (twigs, leaf litter)',
         notes='Thin grass over soil + thatch; for worn edges, under trees, path margins.'),
    # 2 coral / limestone ------------------------------------------------------------------------
    dict(cat='stone', name='coral_stone_wall', page=ph_page('coral_stone_wall'), attribution=ATTR_PH,
         src=urls(color=RAW + 'milesroxas/landscape/HEAD/static/models/new-landscape/coral-stone/textures/coral_stone_wall_diff_4k.jpg',
                  normal=RAW + 'milesroxas/landscape/HEAD/static/models/new-landscape/coral-stone/textures/coral_stone_wall_nor_gl_4k.jpg',
                  roughness=RAW + 'milesroxas/landscape/HEAD/static/models/new-landscape/coral-stone/textures/coral_stone_wall_rough_4k.jpg',
                  ao=RAW + 'milesroxas/landscape/HEAD/static/models/new-landscape/coral-stone/textures/coral_stone_wall_ao_4k.jpg',
                  disp=RAW + 'milesroxas/landscape/HEAD/static/models/new-landscape/coral-stone/textures/coral_stone_wall_disp_4k.jpg'),
         normal_src='gl', tile_m=3.0, tile_note='estimated: ~10 coral rocks (25-40 cm) across the tile',
         notes='4K Poly Haven scan of a real coral-stone (fossil coral rubble) wall with mortar joints. '
               'Use for garden/retaining walls built of coral rock.'),
    dict(cat='stone', name='limestone_block_wall', src=mv('polyhaven', 'white_sandstone_blocks_02'),
         page=ph_page('white_sandstone_blocks_02'), attribution=ATTR_PH, tile_m=2.5,
         tile_note='estimated: ~10 courses of ~25 cm blocks',
         notes='Cream ashlar blocks of a porous sedimentary stone - the closest real scan to the cut '
               'coral-stone/limestone block cladding on the pool retaining wall in the back rendering.'),
    # 3 cedar / teak ----------------------------------------------------------------------------
    dict(cat='wood', name='cedar_door_planks', page=ph_page('wood_cabinet_worn_long'), attribution=ATTR_PH,
         src=urls(color=RAW + 'IcterusGames/Garage42/HEAD/assets/textures/wood_cabinet_worn_long_diff_2k.jpg',
                  normal=RAW + 'IcterusGames/Garage42/HEAD/assets/textures/wood_cabinet_worn_long_nor_gl_2k.png',
                  roughness=RAW + 'IcterusGames/Garage42/HEAD/assets/textures/wood_cabinet_worn_long_rough_2k.png'),
         normal_src='gl', tile_m=2.0, tile_note='2:1 tile (2.0 x 1.0 m); ~10 vertical boards of ~10 cm',
         notes='Poly Haven "wood_cabinet_worn_long": real photo of warm, oiled reddish-brown vertical '
               'tongue-and-groove planks - matches the stained cedar carriage garage door in the front '
               'rendering. Tile is 2048x1024 (boards run along V).'),
    dict(cat='wood', name='teak', src=mv('ambientcg', 'Wood003'), page=acg_page('Wood003'), attribution=ATTR_ACG,
         tile_m=1.0, tile_note='estimated (plain-sawn board figure)',
         notes='Golden-brown straight grain with dark streaks - teak outdoor furniture / lanai trim.'),
    dict(cat='wood', name='cedar_beam', src=mv('ambientcg', 'Wood092'), page=acg_page('Wood092'), attribution=ATTR_ACG,
         tile_m=1.2, tile_note='estimated (knots ~2 cm)',
         notes='Orange-brown softwood with small knots (cedar / Douglas fir look) - lanai beams, posts.'),
    dict(cat='wood', name='weathered_teak_silver', src=mv('ambientcg', 'Wood033'), page=acg_page('Wood033'),
         attribution=ATTR_ACG, tile_m=1.0, tile_note='estimated',
         notes='Silver-grey sun-weathered timber with checks - aged teak furniture, fence boards.'),
    # 4 white oak --------------------------------------------------------------------------------
    dict(cat='wood', name='white_oak_floor', page=ph_page('laminate_floor_02'), attribution=ATTR_PH,
         src=urls(color=RAW + 'Cekator3/carwrack/HEAD/assets/textures/wood063/laminate_floor_02_diff_2k.jpg',
                  normal=RAW + 'Cekator3/carwrack/HEAD/assets/textures/wood063/laminate_floor_02_nor_gl_2k.jpg',
                  roughness=RAW + 'Cekator3/carwrack/HEAD/assets/textures/wood063/laminate_floor_02_rough_2k.jpg',
                  disp=RAW + 'Cekator3/carwrack/HEAD/assets/textures/wood063/laminate_floor_02_disp_2k.png'),
         normal_src='gl', tile_m=2.0, tile_note='estimated: planks ~19 cm wide, ~10 rows per tile',
         notes='Poly Haven "laminate_floor_02": photographed light natural oak plank floor (wide planks, '
               'matt). Use for the white-oak floors.'),
    dict(cat='wood', name='white_oak_veneer', src=mv('polyhaven', 'oak_veneer_01'), page=ph_page('oak_veneer_01'),
         attribution=ATTR_PH, tile_m=1.0, tile_note='estimated (veneer leaf width)',
         notes='Real plain-sliced oak veneer - cabinetry, vanity, doors.'),
    dict(cat='wood', name='rift_white_oak', src=mv('ambientcg', 'Wood001'), page=acg_page('Wood001'),
         attribution=ATTR_ACG, tile_m=1.0, tile_note='estimated (board figure)',
         notes='Pale, straight, tight-grained light wood photo - closest real match to the rift-sawn '
               'white-oak sample on the design board (cabinet doors, built-ins). Grain runs along V. '
               '(ambientCG Wood087, the obvious "rift" candidate, is procedural-looking and was rejected.)'),
    # 5 pavers / concrete ------------------------------------------------------------------------
    dict(cat='paving', name='limestone_pavers', src=mv('ambientcg', 'PavingStones132'), page=acg_page('PavingStones132'),
         attribution=ATTR_ACG, tile_m=2.4, tile_note='estimated: 4 x 4 slabs of ~60 cm',
         notes='Cream square limestone/sandstone slabs with joints - pool deck / terrace.'),
    dict(cat='paving', name='travertine_honed', src=mv('ambientcg', 'Travertine009'), page=acg_page('Travertine009'),
         attribution=ATTR_ACG, tile_m=1.2, tile_note='estimated (vein-cut slab)',
         notes='Honed cream vein-cut travertine slab surface - entry stepping stones, coping, '
               'pool-deck slab faces (cut each paver from a random offset of the tile).'),
    dict(cat='paving', name='broom_concrete', page=ph_page('brushed_concrete'), attribution=ATTR_PH + '; authors Dimitrios Savva (photo), Dario Barresi (processing)',
         src=urls(color=RAW + 'The64thGamer/Give-LIFE/HEAD/Mods/Real%20FNaF/Custom%20Assets/Textures/brushed_concrete_diff_2k.jpg',
                  normal=RAW + 'The64thGamer/Give-LIFE/HEAD/Mods/Real%20FNaF/Custom%20Assets/Textures/brushed_concrete_nor_gl_2k.jpg',
                  arm=RAW + 'The64thGamer/Give-LIFE/HEAD/Mods/Real%20FNaF/Custom%20Assets/Textures/brushed_concrete_arm_2k.jpg'),
         normal_src='gl', tile_m=2.5, tile_note='Poly Haven published dimensions 2.5 x 2.5 m',
         notes='Real broom-finished (brushed) exterior concrete - driveway, garage apron, service paths.'),
    dict(cat='paving', name='concrete_light', src=mv('ambientcg', 'Concrete048'), page=acg_page('Concrete048'),
         attribution=ATTR_ACG, tile_m=2.0, tile_note='estimated',
         notes='Light, slightly streaked concrete - curbs, footings, smooth slab.'),
    # 6 pool ---------------------------------------------------------------------------------------
    dict(cat='pool', name='glass_mosaic', src=mv('ambientcg', 'Tiles019'), page=acg_page('Tiles019'),
         attribution=ATTR_ACG, tile_m=0.6, tile_note='estimated: ~24 irregular chips of ~2.5 cm across',
         derive_hue={'name': 'color_aqua', 'from_deg': 220, 'to_deg': 188, 'sat': 1.05},
         notes='Real photo of hand-set iridescent blue glass mosaic (irregular chips, sanded grout) - pool '
               'waterline band, spa, step edges. color_aqua.jpg is derived by this script (hue rotated '
               'blue -> aqua, everything else untouched) to match the turquoise waterline tile in the back '
               'rendering. (ambientCG Tiles035/Tiles020 were rejected as procedural-looking.)'),
    dict(cat='pool', name='pool_plaster_white', src=mv('ambientcg', 'Plaster002'), page=acg_page('Plaster002'),
         attribution=ATTR_ACG, tile_m=2.0, tile_note='estimated',
         notes='White troweled plaster - pool shell interior (under water it reads light aqua).'),
    # 7 mulch / soil / gravel ----------------------------------------------------------------------
    dict(cat='ground', name='bark_mulch', src=mv('ambientcg', 'Ground048'), page=acg_page('Ground048'),
         attribution=ATTR_ACG, tile_m=1.5, tile_note='estimated (shreds 2-6 cm)',
         notes='Dark brown shredded-bark mulch - planting beds.'),
    dict(cat='ground', name='red_soil', src=mv('ambientcg', 'Ground053'), page=acg_page('Ground053'),
         attribution=ATTR_ACG, tile_m=2.0, tile_note='estimated',
         notes='Red-brown iron-rich soil (Kauai red dirt look) - bare beds, construction lots.'),
    dict(cat='ground', name='gravel_fine_grey', src=mv('polyhaven', 'bicolour_gravel'), page=ph_page('bicolour_gravel'),
         attribution=ATTR_PH, tile_m=1.0, tile_note='estimated (5-10 mm aggregate)',
         notes='Fine grey gravel - side yards, drip edges.'),
    dict(cat='ground', name='river_pebbles', src=mv('polyhaven', 'clean_pebbles'), page=ph_page('clean_pebbles'),
         attribution=ATTR_PH, tile_m=1.5, tile_note='estimated (pebbles 2-6 cm)',
         notes='Real scan of loose grey-brown pebbles - dry stream beds, drip strips, accents.'),
    dict(cat='ground', name='beach_sand', src=mv('polyhaven', 'aerial_beach_01'), page=ph_page('aerial_beach_01'),
         attribution=ATTR_PH, tile_m=10.0, tile_note='aerial scan; estimated ~10 m',
         notes='Aerial scan of a real sand beach - coastline / shore strip in distant views.'),
    # 8 bark ---------------------------------------------------------------------------------------
    dict(cat='bark', name='palm_trunk', page=ph_page('palm_tree_bark'),
         attribution=ATTR_PH + '; authors Dimitrios Savva (photo), Rico Cilliers (processing)',
         src=urls(color=RAW + 'dimitricritsinelis/clawd-strike/HEAD/apps/client/public/assets/textures/environment/bazaar/foliage/palms/palm_tree_bark/palm_tree_bark_diff_2k.jpg',
                  normal=RAW + 'dimitricritsinelis/clawd-strike/HEAD/apps/client/public/assets/textures/environment/bazaar/foliage/palms/palm_tree_bark/palm_tree_bark_nor_gl_2k.jpg',
                  arm=RAW + 'dimitricritsinelis/clawd-strike/HEAD/apps/client/public/assets/textures/environment/bazaar/foliage/palms/palm_tree_bark/palm_tree_bark_arm_2k.jpg'),
         normal_src='gl', tile_m=0.65, tile_note='1:2 tile (0.65 x 1.3 m, Poly Haven scan ~1.3 m tall); wrap U around the trunk',
         notes='Real coconut-palm trunk: grey, ringed with leaf scars. U wraps the circumference '
               '(one tile ~ 0.65 m), V runs up the trunk.'),
    dict(cat='bark', name='tree_bark', src=mv('polyhaven', 'bark_brown_02'), page=ph_page('bark_brown_02'),
         attribution=ATTR_PH, tile_m=1.0, tile_note='estimated',
         notes='Generic broadleaf tree bark (monkeypod, plumeria trunks, distant trees).'),
    # 9 leaves / blades (alpha) ----------------------------------------------------------------------
    dict(cat='foliage', name='leaf_blades', page=acg_page('Foliage008'), attribution=ATTR_ACG,
         src=urls(color=LFS + 'avsomers25/428ADAA/HEAD/Assets/Park%20Assets/Grass/Foliage008_2K-PNG/Foliage008_2K-PNG_Color.png',
                  opacity=LFS + 'avsomers25/428ADAA/HEAD/Assets/Park%20Assets/Grass/Foliage008_2K-PNG/Foliage008_2K-PNG_Opacity.png',
                  normal=LFS + 'avsomers25/428ADAA/HEAD/Assets/Park%20Assets/Grass/Foliage008_2K-PNG/Foliage008_2K-PNG_NormalGL.png',
                  roughness=LFS + 'avsomers25/428ADAA/HEAD/Assets/Park%20Assets/Grass/Foliage008_2K-PNG/Foliage008_2K-PNG_Roughness.png'),
         normal_src='gl', tile_m=0.35, tile_note='atlas (not tiling): 7 scanned blades, each ~30 cm long',
         notes='ATLAS with alpha: 7 scanned long narrow green blades. Use as palm leaflets '
               '(pinnae) along a frond rachis, and for lily/grass clumps. Not tileable by design.'),
    dict(cat='foliage', name='broad_leaf', src=mv('ambientcg', 'Leaf001'), page=acg_page('Leaf001'), attribution=ATTR_ACG,
         extra_maps={'opacity': RAW + 'GuillaumeCa/stargaze-retreat/HEAD/assets/textures/tree/Leaf001_4K_Opacity.jpg'},
         tile_m=0.25, tile_note='atlas (not tiling): two scanned leaves (front + back), ~10 cm each',
         notes='ATLAS with alpha: scanned serrated broadleaf, upper and lower face. For shrub / tree '
               'leaf cards (recolour darker/glossier for tropical shrubs).'),
    dict(cat='foliage', name='tropical_leaf_palmate', page=ph_page('pachira_aquatica_01'),
         attribution=ATTR_PH + ' (Pachira aquatica 01 plant model; leaf texture atlas)',
         src=urls(color=RAW + 'IsaacPjones/TerraSphere/HEAD/assets/pachira_aquatica_01_4k.gltf/textures/pachira_aquatica_01_leaves_diff_4k.jpg',
                  normal=RAW + 'IsaacPjones/TerraSphere/HEAD/assets/pachira_aquatica_01_4k.gltf/textures/pachira_aquatica_01_leaves_nor_gl_4k.jpg',
                  arm=RAW + 'IsaacPjones/TerraSphere/HEAD/assets/pachira_aquatica_01_4k.gltf/textures/pachira_aquatica_01_leaves_arm_4k.jpg'),
         uv_alpha=dict(gltf=RAW + 'IsaacPjones/TerraSphere/HEAD/assets/pachira_aquatica_01_4k.gltf/pachira_aquatica_01_4k.gltf', bin=RAW + 'IsaacPjones/TerraSphere/HEAD/assets/pachira_aquatica_01_4k.gltf/pachira_aquatica_01.bin',
                       material='pachira_aquatica_01_leaves'),
         normal_src='gl', tile_m=0.6, tile_note='atlas (not tiling): 4 palmate leaves, leaflets 12-25 cm',
         notes='ATLAS with alpha: photo-scanned glossy dark-green tropical palmate leaves (money tree, 4 '
               'whole leaves of 5-7 leaflets + a petiole strip). opacity.png is rasterised by this script '
               'from the leaf-mesh UVs of the Poly Haven glTF (exact leaf outlines, 2x supersampled). '
               'Use for tropical shrubs/trees and, leaflet by leaflet, for ti / croton / heliconia-style '
               'leaves (recolour red-purple for ti).'),
    dict(cat='foliage', name='fern_frond', page=ph_page('fern_02'),
         attribution=ATTR_PH + '; Fern 02 modelled by Rico Cilliers, scanned by Rob Tuytel',
         src=urls(color=RAW + 'jackhumphries/neon-paws/HEAD/assets/props/fern_02/textures/fern_02_diff_1k.jpg', normal=RAW + 'jackhumphries/neon-paws/HEAD/assets/props/fern_02/textures/fern_02_nor_gl_1k.jpg',
                  arm=RAW + 'jackhumphries/neon-paws/HEAD/assets/props/fern_02/textures/fern_02_arm_1k.jpg', opacity=RAW + 'jackhumphries/neon-paws/HEAD/assets/props/fern_02/textures/fern_02_alpha_1k.png'),
         normal_src='gl', tile_m=0.5, tile_note='atlas (not tiling): scanned fern fronds ~40 cm',
         notes='ATLAS with alpha: scanned fern fronds (Poly Haven fern_02). Only the 1K version was '
               'reachable - fine for ferns more than ~3 m from camera.'),
    # 11 painted siding ---------------------------------------------------------------------------
    dict(cat='siding', name='painted_lap_siding', src=mv('ambientcg', 'WoodSiding009'), page=acg_page('WoodSiding009'),
         attribution=ATTR_ACG, tile_m=1.6, tile_note='estimated: 8 boards of ~20 cm exposure',
         derive_white=True,
         notes='Real photo of painted horizontal wood lap siding (pale yellow paint). color_white.jpg is '
               'derived by this script (chroma removed, lifted to a warm white, grain/shadow structure '
               'kept) for the white board-and-batten / lap siding of the house. The paint is a little '
               'weathered; for crisp new paint mix color_white 50-70% towards flat white (0.85 linear) '
               'and keep the normal map for the board shadows.'),
    # 12 metal --------------------------------------------------------------------------------------
    dict(cat='metal', name='galvanized_steel', page=ph_page('corrugated_iron'),
         attribution=ATTR_PH + '; authors Dimitrios Savva (photo), Jenelle van Heerden (processing)',
         src=urls(color=RAW + 'raisimTech/raisim2Lib/HEAD/rsc/warehouse/textures/corrugated_iron/corrugated_iron_diff_2k.jpg',
                  normal=RAW + 'raisimTech/raisim2Lib/HEAD/rsc/warehouse/textures/corrugated_iron/corrugated_iron_nor_gl_2k.jpg',
                  arm=RAW + 'raisimTech/raisim2Lib/HEAD/rsc/warehouse/textures/corrugated_iron/corrugated_iron_arm_2k.jpg'),
         normal_src='gl', tile_m=1.12, tile_note='Poly Haven published dimensions 1.12 x 1.12 m',
         notes='Real photo-scan of galvanized (spangled zinc) steel sheet, Poly Haven "corrugated_iron". '
               'colour/roughness/metalness = the real spangle and patina for galvalume roofing, flashing, '
               'gutters. The NORMAL map holds the corrugation profile: for standing-seam panels use '
               'colour + roughness + metalness only (seams as geometry or a procedural ridge mask). '
               '(ambientCG SheetMetal002 was rejected: procedural Voronoi spangle.)'),
    # 13 rattan / cane --------------------------------------------------------------------------------
    dict(cat='weave', name='rattan_weave', src=mv('ambientcg', 'Wicker011A'), page=acg_page('Wicker011A'),
         attribution=ATTR_ACG, tile_m=0.3, tile_note='estimated', real_photo=False,
         notes='NOT A PHOTO (procedural ambientCG weave - no real tileable rattan/cane scan was reachable). '
               'Stop-gap for woven furniture seen from >2 m only. For the cane-webbing panels use an '
               'octagonal cane alpha pattern over wood/teak colour instead.'),
    dict(cat='weave', name='bamboo_blind', src=mv('ambientcg', 'Wicker013'), page=acg_page('Wicker013'),
         attribution=ATTR_ACG, tile_m=0.5, tile_note='estimated: slats ~1 cm, ~45 per tile',
         notes='Photo of a natural bamboo/reed slat roll-blind with cord stitching - lanai roll-down '
               'shades, woven ceiling panels, placemats. (For seagrass/jute rugs use fabric/jute_burlap '
               'scaled up.)'),
    # 14 linen / fabric -------------------------------------------------------------------------------
    dict(cat='fabric', name='linen_oatmeal', src=mv('ambientcg', 'Fabric062'), page=acg_page('Fabric062'),
         attribution=ATTR_ACG, tile_m=0.15, tile_note='estimated (weave ~1 mm)',
         notes='Oatmeal woven upholstery fabric - sofas, throw pillows.'),
    dict(cat='fabric', name='canvas_white', src=mv('ambientcg', 'Fabric032'), page=acg_page('Fabric032'),
         attribution=ATTR_ACG, tile_m=0.15, tile_note='estimated',
         notes='Off-white fine canvas weave - outdoor cushions (Sunbrella-like), curtains, bedding.'),
    dict(cat='fabric', name='jute_burlap', src=mv('polyhaven', 'hessian_230'), page=ph_page('hessian_230'),
         attribution=ATTR_PH, tile_m=0.3, tile_note='estimated (open jute weave ~2 mm)',
         notes='Jute hessian - jute rugs (scale the tile 3-5x larger for chunky rug yarn), baskets.'),
    # 15 asphalt ------------------------------------------------------------------------------------------
    dict(cat='road', name='asphalt', src=mv('polyhaven', 'asphalt_02'), page=ph_page('asphalt_02'),
         attribution=ATTR_PH, tile_m=4.0, tile_note='estimated',
         notes='Grey road asphalt with sealed cracks - neighbourhood streets.'),
    dict(cat='road', name='asphalt_dark', src=mv('ambientcg', 'Asphalt025C'), page=acg_page('Asphalt025C'),
         attribution=ATTR_ACG, tile_m=3.0, tile_note='estimated',
         notes='Dark, newer fine asphalt - private drives / blend layer.'),
    # 16 countertop ---------------------------------------------------------------------------------------
    dict(cat='stone', name='white_quartz', src=mv('ambientcg', 'Marble021'), page=acg_page('Marble021'),
         attribution=ATTR_ACG, tile_m=1.5, tile_note='estimated',
         notes='White stone with faint fine veining - quartz / honed marble countertops.'),
    dict(cat='stone', name='white_marble_veined', src=mv('ambientcg', 'Marble001'), page=acg_page('Marble001'),
         attribution=ATTR_ACG, tile_m=1.5, tile_note='estimated',
         notes='Warm white marble with soft grey veins - vanity tops, shower walls.'),
]

# Day skies get a *_nosun variant + measured sun direction/strength (see analyse_hdri).
HDRIS = [
    dict(name='kloofendal_48d_partly_cloudy_puresky', kind='day', res='8k', make_nosun=True,
         url=RAW + 'yql5213576/Sci-Fi-FPS-game-for-godot-4/HEAD/sci-fi-fps/assets/polyhaven_assets/kloofendal_48d_partly_cloudy_puresky_8k.hdr',
         page=ph_page('kloofendal_48d_partly_cloudy_puresky'),
         notes='PRIMARY day sky. Deep blue sky with scattered fair-weather cumulus - the typical '
               'trade-wind sky over Poipu. Sun ~48 deg up in the photo. Pure sky (no ground).'),
    dict(name='qwantani_puresky', kind='day', res='4k', make_nosun=True,
         url=RAW + 'Rwanee/GameJam_2025/HEAD/assets/qwantani_puresky_4k.exr',
         page=ph_page('qwantani_puresky'),
         notes='Alternate day sky: blue sky with scattered cumulus, mid-high sun. Pure sky.'),
    dict(name='autumn_field_puresky', kind='day', res='8k', make_nosun=True,
         url=RAW + 'yql5213576/Sci-Fi-FPS-game-for-godot-4/HEAD/sci-fi-fps/assets/polyhaven_assets/autumn_field_puresky_8k.hdr',
         page=ph_page('autumn_field_puresky'),
         notes='Clear day sky (8K): deep blue, light haze at the horizon, a few wisps of cirrus, sun ~29 deg - '
               'matches the clear sky of the brochure renderings. Pure sky.'),
    dict(name='kloppenheim_06_puresky', kind='golden_hour', res='4k', make_nosun=False,
         url=RAW + 'yql5213576/Sci-Fi-FPS-game-for-godot-4/HEAD/sci-fi-fps/assets/scenes/office/kloppenheim_06_puresky_4k.hdr',
         page=ph_page('kloppenheim_06_puresky'),
         notes='Late-afternoon / golden-hour sky: low sun (~5 deg) at the horizon, blue sky with small '
               'scattered cumulus and cirrus. Good for warm late-day exteriors.'),
    dict(name='qwantani_dusk_2_puresky', kind='twilight', res='4k', make_nosun=False,
         url=RAW + 'd3cxty/7_of_hearts/HEAD/addins/qwantani_dusk_2_puresky_4k.hdr',
         page=ph_page('qwantani_dusk_2_puresky'),
         notes='Sunset / dusk sky with warm horizon glow and clouds - golden-hour and twilight shots.'),
    dict(name='qwantani_night_puresky', kind='night', res='4k', make_nosun=False,
         url=RAW + 'shush2u/copasetique/HEAD/textures/hdri/qwantani_night_puresky_4k.exr',
         page=ph_page('qwantani_night_puresky'),
         notes='Real night sky photo (stars, faint airglow) - ambient fill for night renders; the '
               'project draws its own astronomically placed stars, use this at low strength or for '
               'reflections only.'),
]


# --------------------------------------------------------------------------------------------
# networking
# --------------------------------------------------------------------------------------------
def http_get(url, rng=None, tries=4, timeout=180):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            if rng:
                req.add_header('Range', f'bytes={rng[0]}-{rng[1]}')
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if rng and len(data) != rng[1] - rng[0] + 1:
                raise IOError(f'short range read {len(data)} != {rng[1] - rng[0] + 1}')
            if data.startswith(b'version https://git-lfs'):
                raise IOError('got a Git LFS pointer instead of the file - use the media.githubusercontent.com URL')
            return data
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + 3 * i)
    raise IOError(f'GET {url} failed: {last}')


def http_download(url, dest: Path, tries=4):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=300) as r, open(tmp, 'wb') as f:
                want = int(r.headers.get('Content-Length') or -1)
                shutil.copyfileobj(r, f, 1 << 20)
            got = tmp.stat().st_size
            if want >= 0 and got != want:
                raise IOError(f'truncated download {got} of {want} bytes')
            with open(tmp, 'rb') as f:
                head = f.read(64)
            if head.startswith(b'version https://git-lfs'):
                raise IOError('Git LFS pointer')
            tmp.replace(dest)
            return dest
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + 3 * i)
    raise IOError(f'download {url} failed: {last}')


_MV_INDEX = None


def matvis_index():
    """{(source, id): (parquet_file, {channel: {offset, length}})} for the 2k tier."""
    global _MV_INDEX
    if _MV_INDEX is not None:
        return _MV_INDEX
    cdir = CACHE / 'matvis' / MATVIS_TAG
    cdir.mkdir(parents=True, exist_ok=True)
    mpath = cdir / 'release-manifest.json'
    if not mpath.exists():
        mpath.write_bytes(http_get(MATVIS_BASE + 'release-manifest.json'))
    man = json.loads(mpath.read_text())
    tier = man['tiers']['2k']
    idx = {}
    for src in ('ambientcg', 'polyhaven'):
        for rmf in tier['sources'][src]['rowmap_files']:
            p = cdir / rmf
            if not p.exists():
                p.write_bytes(http_get(tier['base_url'] + rmf))
            try:
                rm = json.loads(p.read_text())
            except json.JSONDecodeError:  # GitHub sometimes serves an HTML error page
                p.write_bytes(http_get(tier['base_url'] + rmf))
                rm = json.loads(p.read_text())
            for mid, chans in rm['materials'].items():
                idx[(src, mid)] = (rm['parquet_file'], chans)
    _MV_INDEX = idx
    return idx


PNG_END = b'IEND\xaeB`\x82'


def matvis_maps(src, ident):
    pq, chans = matvis_index()[(src, ident)]
    starts = sorted(r['offset'] for r in chans.values())
    out = {}
    for ch, rng in chans.items():
        o, n = rng['offset'], rng['length']
        data = http_get(MATVIS_BASE + pq, (o, o + n - 1))
        if data.startswith(b'\x89PNG') and not data.endswith(PNG_END):
            # a few rowmap entries carry a wrong length: read up to the next map and cut at IEND
            nxt = [s for s in starts if s > o]
            end = (nxt[0] if nxt else o + 4 * n) - 1
            big = http_get(MATVIS_BASE + pq, (o, end))
            k = big.find(PNG_END)
            if k < 0:
                raise IOError(f'mat-vis {ident}/{ch}: could not find the end of the PNG')
            data, n = big[:k + len(PNG_END)], k + len(PNG_END)
        out[ch] = (data, MATVIS_BASE + pq + f'#bytes={o}-{o + n - 1}')
    return out


# --------------------------------------------------------------------------------------------
# image helpers
# --------------------------------------------------------------------------------------------
def to_float(im: Image.Image):
    """PIL image -> float32 array in 0..1 (keeps 16-bit precision)."""
    if im.mode in ('I;16', 'I;16B', 'I;16L', 'I'):
        a = np.asarray(im, dtype=np.float64)
        return (a / (65535.0 if a.max() > 255 else 255.0)).astype(np.float32)
    if im.mode == 'F':
        return np.asarray(im, dtype=np.float32)
    a = np.asarray(im)
    scale = 65535.0 if a.dtype == np.uint16 else 255.0
    return (a.astype(np.float32) / scale)


def gray(a):
    return a if a.ndim == 2 else a[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def box_down(a, f):
    if f <= 1:
        return a
    h, w = a.shape[:2]
    h2, w2 = h // f * f, w // f * f
    a = a[:h2, :w2]
    return a.reshape(h2 // f, f, w2 // f, f, *a.shape[2:]).mean(axis=(1, 3))


def seam_ratio(a):
    """Tileability check: |edge-to-opposite-edge step| / mean neighbouring-pixel step (1.0 = seamless)."""
    g = gray(a).astype(np.float64)
    dx = np.abs(np.diff(g, axis=1)).mean()
    dy = np.abs(np.diff(g, axis=0)).mean()
    sx = np.abs(g[:, 0] - g[:, -1]).mean()
    sy = np.abs(g[0, :] - g[-1, :]).mean()
    return round(float(sx / max(dx, 1e-9)), 2), round(float(sy / max(dy, 1e-9)), 2)


def detect_normal_convention(nrm, disp):
    """Compare the normal map with the gradient of the height map.
    OpenGL (+Y up): green ~ +dh/d(row down);  DirectX: green ~ -dh/d(row down).
    Returns ('gl'|'dx'|'?', corr_x, corr_y)."""
    f = max(1, nrm.shape[0] // 512)
    n = box_down(nrm[..., :3], f)
    h = box_down(gray(disp) if disp.ndim == 3 else disp, max(1, disp.shape[0] // n.shape[0]))
    hh, ww = min(n.shape[0], h.shape[0]), min(n.shape[1], h.shape[1])
    n, h = n[:hh, :ww], h[:hh, :ww]
    gy, gx = np.gradient(h.astype(np.float64))
    nx, ny = n[..., 0] * 2 - 1, n[..., 1] * 2 - 1

    def corr(a, b):
        a = a - a.mean()
        b = b - b.mean()
        return float((a * b).sum() / math.sqrt((a * a).sum() * (b * b).sum() + 1e-12))

    cx, cy = corr(nx, -gx), corr(ny, gy)
    conv = '?' if abs(cy) < 0.05 else ('gl' if cy > 0 else 'dx')
    return conv, round(cx, 3), round(cy, 3)


def save_jpg(arr_or_img, path, q=93):
    im = arr_or_img if isinstance(arr_or_img, Image.Image) else Image.fromarray(arr_or_img)
    im.save(path, quality=q, subsampling=0, optimize=True)


def u8(a):
    return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)


def open_img(data):
    im = Image.open(io.BytesIO(data))
    im.load()
    return im


# --------------------------------------------------------------------------------------------
# texture processing
# --------------------------------------------------------------------------------------------
def uv_alpha_mask(spec, W, H, ss=2):
    """Opacity from a glTF: rasterise the UV triangles of every primitive that uses `material`."""
    from PIL import ImageDraw
    g = json.loads(http_get(spec['gltf']))
    b = http_get(spec['bin'])
    mats = [i for i, m in enumerate(g['materials']) if m.get('name') == spec['material']]
    comp = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}

    def acc(i):
        a = g['accessors'][i]
        bv = g['bufferViews'][a['bufferView']]
        n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a['type']]
        arr = np.frombuffer(b, comp[a['componentType']], count=a['count'] * n,
                            offset=bv.get('byteOffset', 0) + a.get('byteOffset', 0))
        return arr.reshape(a['count'], n) if n > 1 else arr

    m = Image.new('L', (W * ss, H * ss), 0)
    dr = ImageDraw.Draw(m)
    tris = 0
    for mesh in g['meshes']:
        for prim in mesh['primitives']:
            if prim.get('material') not in mats:
                continue
            uv = acc(prim['attributes']['TEXCOORD_0']).astype(np.float64)
            idx = acc(prim['indices']).reshape(-1, 3)
            px = np.stack([uv[:, 0] * W * ss, uv[:, 1] * H * ss], 1)  # glTF UV origin = image top-left
            for tri in idx:
                dr.polygon([tuple(px[k]) for k in tri], fill=255)
            tris += len(idx)
    if not tris:
        raise ValueError(f'no primitives use material {spec["material"]}')
    return m.resize((W, H), Image.LANCZOS)


def fetch_texture(t, force=False):
    out = TEX / t['cat'] / t['name']
    info_p = out / 'info.json'
    if info_p.exists() and not force:
        return json.loads(info_p.read_text())
    print(f'  fetching texture {t["cat"]}/{t["name"]} ...', flush=True)
    if out.exists():
        shutil.rmtree(out)  # no stale maps from an earlier source
    out.mkdir(parents=True, exist_ok=True)
    raw = {}  # channel -> (bytes, url)
    if t['src']['kind'] == 'matvis':
        raw.update(matvis_maps(t['src']['src'], t['src']['id']))
    else:
        for ch, u in t['src']['maps'].items():
            raw[ch] = (http_get(u), u)
    for ch, u in (t.get('extra_maps') or {}).items():
        raw[ch] = (http_get(u), u)

    files, mirrors, notes = {}, {}, []
    imgs = {ch: open_img(b) for ch, (b, _u) in raw.items()}
    # Poly Haven ARM = AO (R), roughness (G), metalness (B)
    if 'arm' in imgs:
        arm = imgs.pop('arm').convert('RGB')
        r, g, b = arm.split()
        imgs.setdefault('ao', r)
        imgs.setdefault('roughness', g)
        if np.asarray(b).mean() > 8:
            imgs.setdefault('metalness', b)
        mirrors['arm'] = raw['arm'][1]

    color = imgs['color']
    W, H = color.size
    # colour ------------------------------------------------------------------------------------
    cdata, curl = raw['color']
    if color.format == 'JPEG' and color.mode == 'RGB':
        (out / 'color.jpg').write_bytes(cdata)  # keep the original JPEG bits
    else:
        save_jpg(color.convert('RGB'), out / 'color.jpg', 94)
    files['color'] = 'color.jpg'
    mirrors['color'] = curl
    carr = to_float(color.convert('RGB'))
    if t.get('derive_white'):
        g = gray(carr)
        lift = 0.93 / max(np.percentile(g, 75), 1e-3)  # bring the paint to ~0.93 (sRGB) white
        g2 = np.clip(g * lift, 0, 1)
        warm = np.stack([g2, g2 * 0.992, g2 * 0.972], -1)
        save_jpg(u8(warm), out / 'color_white.jpg', 94)
        files['color_white'] = 'color_white.jpg'
    if t.get('derive_hue'):
        dh = t['derive_hue']
        hsv = np.asarray(color.convert('RGB').convert('HSV'), np.float32)
        h = hsv[..., 0] * (360 / 255)
        shift = dh['to_deg'] - dh['from_deg']
        wgt = np.clip(1 - np.abs(((h - dh['from_deg'] + 180) % 360) - 180) / 60, 0, 1)  # only blue-ish hues
        hsv[..., 0] = ((h + shift * wgt) % 360) * (255 / 360)
        hsv[..., 1] = np.clip(hsv[..., 1] * (1 + (dh.get('sat', 1) - 1) * wgt), 0, 255)
        im2 = Image.fromarray(hsv.astype(np.uint8), 'HSV').convert('RGB')
        save_jpg(im2, out / f'{dh["name"]}.jpg', 94)
        files[dh['name']] = f'{dh["name"]}.jpg'

    disp_arr = None
    if 'displacement' in imgs or 'disp' in imgs:
        dimg = imgs.get('displacement') or imgs.get('disp')
        ddata, durl = raw.get('displacement') or raw.get('disp')
        darr = to_float(dimg)
        if darr.ndim == 3:
            darr = darr[..., 0]
        disp_arr = darr
        if dimg.mode in ('I;16', 'I;16B', 'I;16L', 'I') or np.asarray(dimg).dtype == np.uint16:
            Image.fromarray((np.clip(darr, 0, 1) * 65535 + 0.5).astype(np.uint16)).save(out / 'disp.png')
        else:
            Image.fromarray(u8(darr)).save(out / 'disp.png', optimize=True)
        files['disp'] = 'disp.png'
        mirrors['disp'] = durl

    conv_info = None
    if 'normal' in imgs:
        nimg = imgs['normal'].convert('RGB') if imgs['normal'].mode not in ('I;16', 'I') else imgs['normal']
        narr = to_float(imgs['normal'])
        if narr.ndim == 2:
            raise ValueError('normal map is single channel?')
        narr = narr[..., :3]
        declared = t.get('normal_src')
        if declared is None and t['src']['kind'] == 'matvis':
            # mat-vis keeps the DirectX normal of both libraries (measured on 37 of 38 sets with a
            # height map); used when a set's height map is too flat to measure.
            declared = 'dx'
        conv = declared
        if disp_arr is not None:
            det, cx, cy = detect_normal_convention(narr, disp_arr)
            conv_info = {'detected': det, 'corr_x': cx, 'corr_y': cy, 'declared': declared}
            if det != '?':
                conv = det
            if declared and det not in ('?', declared):
                notes.append(f'normal convention declared {declared} but measured {det}; using measured')
        if conv is None:
            conv = 'gl'
            notes.append('normal convention could not be measured (no height map); assumed OpenGL')
        if conv == 'dx':
            narr = narr.copy()
            narr[..., 1] = 1.0 - narr[..., 1]
            notes.append('normal map converted DirectX -> OpenGL (green flipped)')
        ndata, nurl = raw['normal']
        if conv == 'gl' and imgs['normal'].format == 'JPEG':
            (out / 'normal.jpg').write_bytes(ndata)
        else:
            save_jpg(u8(narr), out / 'normal.jpg', 95)
        files['normal'] = 'normal.jpg'
        mirrors['normal'] = nurl
        del nimg

    for ch in ('roughness', 'ao', 'metalness'):
        if ch in imgs:
            a = to_float(imgs[ch])
            a = a[..., 0] if a.ndim == 3 else a
            if ch == 'metalness' and (t['cat'] != 'metal' or a.max() < 0.05):
                continue  # dielectrics: mat-vis 'metalness' there is empty or a mislabelled mask
            save_jpg(u8(a), out / f'{ch}.jpg', 93)
            files[ch] = f'{ch}.jpg'
            if ch in raw:
                mirrors[ch] = raw[ch][1]

    if t.get('uv_alpha'):
        imgs['opacity'] = uv_alpha_mask(t['uv_alpha'], W, H)
        raw['opacity'] = (b'', t['uv_alpha']['gltf'] + ' (UV triangles of material '
                          + t['uv_alpha']['material'] + ', rasterised)')
    if 'opacity' in imgs:
        oa = to_float(imgs['opacity'])
        oa = oa[..., 0] if oa.ndim == 3 else oa
        if oa.shape != (H, W):
            oa = np.asarray(Image.fromarray(u8(oa)).resize((W, H), Image.LANCZOS), np.float32) / 255
        # sanity: opacity must line up with the coloured pixels of the atlas
        lum = gray(carr)
        inside = lum[oa > 0.5].mean() if (oa > 0.5).any() else 0
        outside = lum[oa < 0.05].mean() if (oa < 0.05).any() else 0
        notes.append(f'opacity check: mean luminance inside {inside:.3f} vs outside {outside:.3f}')
        Image.fromarray(u8(oa)).save(out / 'opacity.png', optimize=True)
        files['opacity'] = 'opacity.png'
        mirrors['opacity'] = raw['opacity'][1]

    sx, sy = seam_ratio(carr)
    res = f'{W}x{H}'
    info = {
        'category': t['cat'], 'name': t['name'],
        'files': {k: f'textures/{t["cat"]}/{t["name"]}/{v}' for k, v in files.items()},
        'resolution': res, 'tile_m': t['tile_m'],
        'tile_aspect': round(W / H, 3),
        'tile_note': t.get('tile_note', ''),
        'normal_convention': 'OpenGL (+Y up, green = up); Blender-native' if 'normal' in files else None,
        'normal_check': conv_info,
        'seam_ratio_x_y': [sx, sy],
        'tileable': bool(sx < 2.0 and sy < 2.0),
        'mean_albedo_srgb': [round(float(v), 3) for v in carr.reshape(-1, 3).mean(0)],
        'source_url': t['page'],
        'mirror_urls': mirrors,
        'licence': CC0,
        'attribution': t['attribution'],
        'library': 'ambientCG' if 'ambientcg' in t['page'] else 'Poly Haven',
        'real_photo': t.get('real_photo', True),
        'notes': t.get('notes', '') + ((' | ' + '; '.join(notes)) if notes else ''),
    }
    if t['src']['kind'] == 'matvis':
        info['fetched_via'] = f'mat-vis {MATVIS_TAG} (github.com/MorePET/mat-vis) 2K tier, HTTP range read'
    info_p.write_text(json.dumps(info, indent=2))
    return info


# --------------------------------------------------------------------------------------------
# HDRI processing
# --------------------------------------------------------------------------------------------
def read_hdr_any(path: Path):
    """-> float32 HxWx3 RGB (linear)."""
    if path.suffix.lower() == '.hdr':
        import cv2
        a = cv2.imread(str(path), cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
        if a is None:
            raise IOError(f'cv2 could not read {path}')
        return a[..., ::-1].astype(np.float32, copy=False)
    try:
        import OpenEXR  # pip install OpenEXR
        with OpenEXR.File(str(path)) as f:
            ch = f.channels()
            if 'RGB' in ch:
                a = ch['RGB'].pixels
            elif 'RGBA' in ch:
                a = ch['RGBA'].pixels[..., :3]
            else:
                a = np.stack([ch[c].pixels for c in ('R', 'G', 'B')], -1)
        return np.ascontiguousarray(a, dtype=np.float32)
    except ImportError:
        import bpy  # Blender's python module, as used by scripts/blender_render.py
        img = bpy.data.images.load(str(path))
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        return px.reshape(h, w, 4)[::-1, :, :3].copy()


def write_hdr(path: Path, rgb):
    import cv2
    ok = cv2.imwrite(str(path), np.ascontiguousarray(rgb[..., ::-1], dtype=np.float32))
    if not ok:
        raise IOError(f'could not write {path}')


def lum709(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def solid_angle_rows(H, W):
    lat = (0.5 - (np.arange(H) + 0.5) / H) * math.pi
    return (2 * math.pi / W) * (math.pi / H) * np.cos(lat), lat


def pix_to_dir(row, col, H, W):
    """Blender equirectangular convention (Environment Texture, no rotation):
    u = atan2(d.y, -d.x)/(2pi) + 0.5,  v = atan2(d.z, hypot(d.x, d.y))/pi + 0.5 (v=1 at image top)."""
    u = (col + 0.5) / W
    elev = (0.5 - (row + 0.5) / H) * math.pi
    phi = (u - 0.5) * 2 * math.pi
    d = (-math.cos(phi) * math.cos(elev), math.sin(phi) * math.cos(elev), math.sin(elev))
    return d, math.degrees(elev), math.degrees(math.atan2(d[1], d[0]))


def tonemap_preview(rgb, out_path, w=1024):
    import cv2
    h = w // 2
    small = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA)
    L = lum709(small)
    upper = L[: h // 2]
    key = float(np.exp(np.log(np.clip(upper, 1e-4, None)).mean()))
    x = small * (0.18 / max(key, 1e-6)) * 1.6
    # ACES-like filmic curve (Narkowicz), then sRGB
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    y = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)
    srgb = np.where(y <= 0.0031308, 12.92 * y, 1.055 * np.power(y, 1 / 2.4) - 0.055)
    Image.fromarray(u8(srgb)).save(out_path, quality=90)


def membrane_fill(img, m, iters=1500):
    """Replace img inside mask m by the smooth membrane (Laplace solution) spanning the mask
    boundary - no streaks, no dark ring, interior stays between the boundary values.
    Starts from the TELEA result; red-black-free Jacobi on the bounding box only."""
    ys, xs = np.where(m)
    if len(ys) == 0:
        return img
    y0, y1 = max(ys.min() - 2, 0), min(ys.max() + 3, img.shape[0])
    x0, x1 = max(xs.min() - 2, 0), min(xs.max() + 3, img.shape[1])
    u = img[y0:y1, x0:x1].astype(np.float64).copy()
    mm = m[y0:y1, x0:x1]
    for _ in range(iters):
        avg = 0.25 * (np.roll(u, 1, 0) + np.roll(u, -1, 0) + np.roll(u, 1, 1) + np.roll(u, -1, 1))
        u[mm] = avg[mm]
    out = img.copy()
    out[y0:y1, x0:x1] = u.astype(img.dtype)
    return out


def remove_sun(rgb):
    """Paint the sun disc + its immediate corona out of a day sky.
    Returns (rgb_nosun, sun_info) where sun_info holds the energy that was removed."""
    import cv2
    H, W = rgb.shape[:2]
    L = lum709(rgb)
    r0, c0 = np.unravel_index(int(np.argmax(L)), L.shape)
    peak = float(L[r0, c0])
    # window around the sun (wraps in longitude)
    half = max(64, W // 32)
    rows = np.arange(max(0, r0 - half), min(H, r0 + half))
    cols = np.arange(c0 - half, c0 + half) % W
    win = rgb[np.ix_(rows, cols)].astype(np.float32)
    Lw = lum709(win)
    ring = np.ones_like(Lw, bool)
    yy, xx = np.mgrid[0:Lw.shape[0], 0:Lw.shape[1]]
    rr = np.hypot(yy - (r0 - rows[0]), xx - half)
    ring = (rr > half * 0.6) & (rr < half * 0.95)
    sky_ref = float(np.median(Lw[ring]))
    thr = max(sky_ref * 3.0, 1.5 * sky_ref + 0.5)
    mask = (Lw > thr).astype(np.uint8)
    # keep only the connected blob that contains the peak
    n, lab = cv2.connectedComponents(mask)
    keep = lab == lab[r0 - rows[0], half]
    mask = keep.astype(np.uint8)
    rad = int(max(3, W / 2048 * 4))
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rad + 1, 2 * rad + 1)))
    out = win.copy()
    for k in range(3):
        lg = np.log(np.clip(win[..., k], 1e-5, None)).astype(np.float32)
        inp = cv2.inpaint(lg, mask, max(3, rad * 2), cv2.INPAINT_TELEA)
        out[..., k] = np.exp(membrane_fill(inp, mask > 0))
    # soften the transition with a feathered blend
    feather = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), rad)
    feather = np.clip(feather * 1.5, 0, 1)[..., None]
    out = out * feather + win * (1 - feather)
    res = rgb.copy()
    res[np.ix_(rows, cols)] = out
    # energy removed -> irradiance of a Sun lamp (W/m^2 in Blender units, world strength 1)
    dom, _lat = solid_angle_rows(H, W)
    removed = (win - out) * dom[rows][:, None, None]
    E = removed.reshape(-1, 3).sum(0)
    d, elev, az = pix_to_dir(r0, int(c0), H, W)
    return res, {
        'sun_pixel_row_col': [int(r0), int(c0)],
        'sun_peak_radiance': round(peak, 1),
        'sun_elevation_deg': round(elev, 2),
        'sun_azimuth_blender_deg': round(az, 2),
        'sun_dir_blender_unrotated': [round(v, 4) for v in d],
        'sun_irradiance_rgb': [round(float(v), 3) for v in E],
        'sun_irradiance_lum': round(float(E @ np.array([0.2126, 0.7152, 0.0722])), 3),
        'sun_color_rgb_norm': [round(float(v / max(E.max(), 1e-9)), 4) for v in E],
        'sun_strength_blender': round(float(E.max()), 3),
        'sun_mask_pixels': int(mask.sum()),
    }


def sky_irradiance_horizontal(rgb):
    H, W = rgb.shape[:2]
    f = max(1, W // 2048)
    small = box_down(rgb, f)
    h, w = small.shape[:2]
    dom, lat = solid_angle_rows(h, w)
    wgt = (dom * np.clip(np.sin(lat), 0, None))[:, None]
    return round(float((lum709(small) * wgt).sum()), 3)


def fetch_hdri(h, force=False):
    HDRI.mkdir(parents=True, exist_ok=True)
    (HDRI / 'previews').mkdir(exist_ok=True)
    info_p = HDRI / f'{h["name"]}.json'
    if info_p.exists() and not force:
        return json.loads(info_p.read_text())
    print(f'  fetching HDRI {h["name"]} ...', flush=True)
    dst = HDRI / f'{h["name"]}.hdr'
    src_ext = Path(h['url'].split('?')[0]).suffix.lower()
    with tempfile.TemporaryDirectory(dir=str(ASSETS)) as td:
        tmp = Path(td) / ('src' + src_ext)
        http_download(h['url'], tmp)
        rgb = read_hdr_any(tmp)
        if src_ext == '.hdr':
            shutil.move(str(tmp), dst)
        else:
            write_hdr(dst, rgb)
    Hh, Ww = rgb.shape[:2]
    info = {
        'category': 'hdri', 'name': h['name'], 'kind': h['kind'],
        'files': {'hdr': f'hdri/{h["name"]}.hdr', 'preview': f'hdri/previews/{h["name"]}.jpg'},
        'resolution': f'{Ww}x{Hh}',
        'source_url': h['page'], 'mirror_urls': {'hdr': h['url']},
        'licence': CC0, 'attribution': ATTR_PH, 'library': 'Poly Haven', 'real_photo': True,
        'max_radiance': round(float(lum709(rgb).max()), 1),
        'sky_horizontal_irradiance_lum': sky_irradiance_horizontal(rgb),
        'notes': h['notes'] + (' Converted from OpenEXR to Radiance HDR (lossless enough for skies).' if src_ext == '.exr' else ''),
        'blender_usage': ('Environment Texture (equirectangular) <- Mapping(Vector, rotation Z = radians('
                          'sun_azimuth_blender_deg - target_sun_azimuth_deg)) <- Texture Coordinate.Generated. '
                          'Azimuths are atan2(y, x) in Blender world XY (counter-clockwise from +X). '
                          'With the *_nosun file, add a Sun lamp (angle 0.53 deg) at the astronomically correct '
                          'direction with strength = sun_strength_blender x world strength and colour = '
                          'sun_color_rgb_norm (strength x colour reproduces the measured sun irradiance per '
                          'channel, sun_irradiance_rgb).'),
    }
    tonemap_preview(rgb, HDRI / 'previews' / f'{h["name"]}.jpg')
    if h.get('make_nosun'):
        nos, sun = remove_sun(rgb)
        info.update(sun)
        write_hdr(HDRI / f'{h["name"]}_nosun.hdr', nos)
        info['files']['hdr_nosun'] = f'hdri/{h["name"]}_nosun.hdr'
        info['sky_horizontal_irradiance_lum_nosun'] = sky_irradiance_horizontal(nos)
        tonemap_preview(nos, HDRI / 'previews' / f'{h["name"]}_nosun.jpg')
        info['files']['preview_nosun'] = f'hdri/previews/{h["name"]}_nosun.jpg'
        del nos
    del rgb
    info_p.write_text(json.dumps(info, indent=2))
    return info


# --------------------------------------------------------------------------------------------
# manifest + contact sheet
# --------------------------------------------------------------------------------------------
def font(sz):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    try:
        return ImageFont.load_default(size=sz)
    except TypeError:
        return ImageFont.load_default()


def build_manifest_and_sheet(tex_infos, hdri_infos):
    manifest = []
    for i in tex_infos + hdri_infos:
        manifest.append(i)
    (ASSETS / 'manifest.json').write_text(json.dumps(manifest, indent=2))

    T = 280
    cols = 6
    f1, f2 = font(15), font(12)
    rows_t = (len(tex_infos) + cols - 1) // cols
    hw, hh = 560, 280
    hcols = 3
    hd_items = []
    for h in hdri_infos:
        hd_items.append((h, 'preview'))
        if 'preview_nosun' in h['files']:
            hd_items.append((h, 'preview_nosun'))
    rows_h = (len(hd_items) + hcols - 1) // hcols
    Wd = cols * T
    Ht = 60 + rows_t * (T + 44) + 40 + rows_h * (hh + 30)
    sheet = Image.new('RGB', (Wd, Ht), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    d.text((10, 12), 'Na Hiku photo-texture + HDRI library (CC0: ambientCG, Poly Haven) - assets/manifest.json',
           fill=(240, 240, 240), font=font(20))
    y0 = 60
    for k, i in enumerate(tex_infos):
        x, y = (k % cols) * T, y0 + (k // cols) * (T + 44)
        im = Image.open(ASSETS / i['files']['color']).convert('RGB')
        if 'opacity' in i['files']:
            a = Image.open(ASSETS / i['files']['opacity']).convert('L').resize(im.size)
            bg = Image.new('RGB', im.size, (128, 128, 128))
            bg.paste(im, (0, 0), a)
            im = bg
        im.thumbnail((T - 6, T - 6), Image.LANCZOS)
        sheet.paste(im, (x + 3 + (T - 6 - im.width) // 2, y + 3 + (T - 6 - im.height) // 2))
        d.text((x + 4, y + T + 2), f'{i["category"]}/{i["name"]}', fill=(255, 255, 255), font=f1)
        ab = {'normal': 'N', 'roughness': 'R', 'ao': 'AO', 'disp': 'D', 'metalness': 'M', 'opacity': 'A', 'color_white': 'W'}
        maps = ' '.join(ab.get(k2, k2) for k2 in i['files'] if k2 != 'color')
        d.text((x + 4, y + T + 22), f'{i["resolution"]}  {i["tile_m"]} m/tile  {maps}', fill=(170, 170, 170), font=f2)
    y1 = y0 + rows_t * (T + 44) + 10
    d.text((10, y1), 'Sky HDRIs (tonemapped previews; *_nosun = sun disc removed for use with a Sun lamp)',
           fill=(240, 240, 240), font=f1)
    y1 += 30
    for k, (h, key) in enumerate(hd_items):
        x, y = (k % hcols) * hw, y1 + (k // hcols) * (hh + 30)
        im = Image.open(ASSETS / h['files'][key]).convert('RGB').resize((hw - 8, hh - 8), Image.LANCZOS)
        sheet.paste(im, (x + 4, y + 4))
        sun = f'  sun el {h["sun_elevation_deg"]} deg' if 'sun_elevation_deg' in h else ''
        lab = f'{h["name"]}{"_nosun" if key == "preview_nosun" else ""}  {h["resolution"]}{sun}'
        d.text((x + 6, y + hh), lab, fill=(255, 255, 255), font=f2)
    sheet.save(ASSETS / 'contact_sheet.jpg', quality=88)


def write_readme():
    txt = """# Na Hiku asset library (generated - do not edit by hand)

Built by `python3 scripts/fetch_assets.py`. Real photo-scanned PBR textures and real sky HDRIs,
all CC0 (ambientCG, Poly Haven). See `manifest.json` for every file, its real-world tile size,
the canonical source page, the exact mirror it was fetched from, and per-asset notes.

* `textures/<category>/<name>/` : color.jpg (sRGB), normal.jpg (OpenGL, +Y up), roughness.jpg,
  ao.jpg, disp.png (0.5 = mid), metalness.jpg, opacity.png (atlases).  Mapping: one tile =
  `tile_m` metres (world units are feet in three.js; metres in the exported GLB).
* `hdri/<name>.hdr` : equirectangular Radiance HDR.  Day skies also have `<name>_nosun.hdr`
  (sun disc painted out) plus the measured sun direction / irradiance / colour in manifest.json,
  so a Blender Sun lamp can be placed at the astronomically correct position for any date/time
  while the photographed sky + clouds still light the scene.
* `contact_sheet.jpg` : thumbnails of everything.
"""
    (ASSETS / 'README.md').write_text(txt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', default='', help='comma-separated asset names to (re)fetch')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--sheet-only', action='store_true')
    ap.add_argument('--no-hdri', action='store_true')
    ap.add_argument('--no-tex', action='store_true')
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(',') if s.strip()}
    ASSETS.mkdir(exist_ok=True)

    tex_infos, hdri_infos, failed = [], [], []
    for t in TEXTURES:
        sel = (not only) or t['name'] in only
        try:
            if args.sheet_only or args.no_tex or not sel:
                p = TEX / t['cat'] / t['name'] / 'info.json'
                if p.exists():
                    tex_infos.append(json.loads(p.read_text()))
                continue
            tex_infos.append(fetch_texture(t, force=args.force or bool(only)))
        except Exception as e:  # noqa: BLE001
            print(f'  !! {t["name"]}: {e}', file=sys.stderr)
            failed.append(t['name'])
    for h in HDRIS:
        sel = (not only) or h['name'] in only
        try:
            if args.sheet_only or args.no_hdri or not sel:
                p = HDRI / f'{h["name"]}.json'
                if p.exists():
                    hdri_infos.append(json.loads(p.read_text()))
                continue
            hdri_infos.append(fetch_hdri(h, force=args.force or bool(only)))
        except Exception as e:  # noqa: BLE001
            print(f'  !! {h["name"]}: {e}', file=sys.stderr)
            failed.append(h['name'])
    build_manifest_and_sheet(tex_infos, hdri_infos)
    write_readme()
    total = sum(f.stat().st_size for f in ASSETS.rglob('*') if f.is_file() and '.cache' not in f.parts)
    print(f'done: {len(tex_infos)} textures, {len(hdri_infos)} HDRIs, library size {total / 1e6:.0f} MB'
          + (f'; FAILED: {", ".join(failed)}' if failed else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
