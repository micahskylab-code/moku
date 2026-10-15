"""Palms (and the palm-like cycad) for the path tracer, grown leaf by leaf.

The three.js scene draws palms as a few textured cards, which is what makes them read as CG up
close. For Cycles every palm is rebuilt here from its position and size (nahiku-meta.json 'palms':
kind, seed, base, height). Kinds, as planted at Kukui'ula and in the brochure renderings:

  - 'queen'      Syagrus romanzoffiana, the big palms of both renderings: a 12-14 in grey trunk with
                 leaf-scar rings and lichen (the real palm-bark scan), the 'boots' of cut leaf bases
                 under the crown, 14-19 long arching fronds whose leaflets leave the rachis in clusters
                 in several planes and hang limp (the plumose, weeping look), yellowing older fronds,
                 brown tips, 2-4 dead fronds hanging against the trunk, pendulous orange/green fruit
                 panicles with their woody spathes
  - 'foxtail'    Wodyetia bifurcata: smooth grey trunk, bright green crownshaft, 8-11 bottle-brush
                 fronds (leaflets all round the rachis), red-orange fruit
  - 'christmas'  Adonidia merrillii (Manila palm): slender ringed grey trunk, pale green crownshaft,
                 strongly recurved fronds with leaflets in a V, red fruit clusters
  - 'lipstick'   Cyrtostachys renda: clustering slender ringed stems, scarlet crownshafts and petioles,
                 stiff ascending fronds
  - 'areca'      Dypsis lutescens: yellow-green ringed canes in dense clumps, golden petioles,
                 arching fronds with a V of leaflets
  - 'roebelenii' Phoenix roebelenii (pygmy date): a rough, knobby 3-8 ft trunk, a dense ball of fine
                 dark fronds
  - 'cycad'      Cycas revoluta (sago): a short shaggy trunk, a rosette of stiff glossy fronds
  - 'coconut'    distant skyline palms: curved trunk, long hanging leaflets, nuts

Leaflets are built vectorised (thousands per frond), crowns as a handful of variants per kind,
instanced per palm with geometry nodes, so a whole neighbourhood of palms costs little memory.

    import palms; palms.build(meta['palms'], b)      # b: three.js world (metres) -> Blender world
"""
import math, os, random
import numpy as np
import bpy
from mathutils import Vector, Matrix, Quaternion

UP = np.array([0.0, 0.0, 1.0])
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'textures')
GOLDEN = math.radians(137.508)


def _norm(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def _lin(hexstr):
    h = hexstr.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple([x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0])


class MeshBuf:
    """Collects polygons (all of one arity per add) with per-vertex attributes, UVs and a material
    slot per add; several bufs join into one multi-material mesh (fewer, bigger meshes keep the
    path tracer's memory down)."""
    def __init__(self):
        self.parts = []          # (verts, faces (local), uv, attrs, mat)
        self.n = 0

    def add(self, verts, faces, uv=None, mat=0, **attrs):
        verts = np.asarray(verts, dtype=np.float32).reshape(-1, 3)
        if not len(verts): return
        uv = np.zeros((len(verts), 2), np.float32) if uv is None else np.asarray(uv, np.float32).reshape(-1, 2)
        at = {k: np.broadcast_to(np.asarray(a, dtype=np.float32), (len(verts),)).copy() for k, a in attrs.items()}
        self.parts.append((verts, np.asarray(faces, dtype=np.int64), uv, at, mat))
        self.n += len(verts)

    def extend(self, other, R=None, off=None, mat=None):
        for v, f, uv, at, m in other.parts:
            if R is not None: v = v @ np.asarray(R, np.float32).T
            if off is not None: v = v + np.asarray(off, np.float32)
            self.parts.append((v, f, uv, at, m if mat is None else mat)); self.n += len(v)

    def mesh(self, name, materials):
        materials = materials if isinstance(materials, (list, tuple)) else [materials]
        V = np.concatenate([p[0] for p in self.parts])
        polys, base = {}, 0
        for v, f, uv, at, m in self.parts:
            polys.setdefault(f.shape[1], []).append((f + base, np.full(len(f), m, np.int32))); base += len(v)
        loops, starts, totals, mats, off = [], [], [], [], 0
        for k in sorted(polys):
            F = np.concatenate([f for f, _ in polys[k]]); loops.append(F.ravel()); mats.append(np.concatenate([m for _, m in polys[k]]))
            starts.append(off + np.arange(len(F)) * k); totals.append(np.full(len(F), k)); off += F.size
        loops = np.concatenate(loops).astype(np.int32)
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(V)); me.vertices.foreach_set('co', V.ravel())
        me.loops.add(len(loops)); me.loops.foreach_set('vertex_index', loops)
        me.polygons.add(sum(len(s) for s in starts))
        me.polygons.foreach_set('loop_start', np.concatenate(starts).astype(np.int32))
        me.polygons.foreach_set('loop_total', np.concatenate(totals).astype(np.int32))
        me.polygons.foreach_set('material_index', np.concatenate(mats))
        for m in materials: me.materials.append(m)
        names = sorted({k for p in self.parts for k in p[3]})
        for k in names:
            vals = np.concatenate([p[3].get(k, np.zeros(len(p[0]), np.float32)) for p in self.parts])
            a = me.attributes.new(k, 'FLOAT', 'POINT'); a.data.foreach_set('value', vals)
        UV = np.concatenate([p[2] for p in self.parts])
        lay = me.uv_layers.new(name='UVMap'); lay.data.foreach_set('uv', UV[loops].ravel())
        me.update(calc_edges=True)
        me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
        return me


# ---------------------------------------------------------------- materials
def _img(path, colorspace):
    if not os.path.exists(path): return None
    im = bpy.data.images.load(path, check_existing=True)
    try: im.colorspace_settings.name = colorspace
    except Exception: pass
    return im


def _leaf_material(name, greens, tip_burn, age_col=(0.2, 0.17, 0.05, 1), transl=0.35, burn_col=(0.33, 0.2, 0.07, 1),
                   burn_from=0.78, rough=0.46, spec=0.34, under=(1.25, 1.25, 1.15), age_from=0.55, age_amt=0.75, gloss=0.0,
                   grade=(0.035, 0.75)):
    """Leaflets: per-leaflet colour from a ramp of greens (attribute-free: Random Per Island), older fronds
    (attribute 'age') yellowing, dry tips on a share of the leaflets (attribute 'tip' = 0 base .. 1 tip),
    a paler waxy underside, translucency (thin leaves glow yellow-green against the sun)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    for n in list(N): N.remove(n)
    out = N.new('ShaderNodeOutputMaterial')
    geo = N.new('ShaderNodeNewGeometry')
    ramp = N.new('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position = 0.0; els[0].color = greens[0]
    els[1].position = 1.0; els[1].color = greens[-1]
    for t, c in zip(np.linspace(0, 1, len(greens))[1:-1], greens[1:-1]):
        e = els.new(float(t)); e.color = c
    L.new(geo.outputs['Random Per Island'], ramp.inputs['Fac'])
    col = ramp.outputs['Color']
    # older (lower) fronds turn olive-yellow
    age = N.new('ShaderNodeAttribute'); age.attribute_name = 'age'
    agem = N.new('ShaderNodeMapRange'); agem.inputs['From Min'].default_value = age_from; agem.inputs['From Max'].default_value = 1.0
    agem.inputs['To Max'].default_value = age_amt
    L.new(age.outputs['Fac'], agem.inputs['Value'])
    am = N.new('ShaderNodeMix'); am.data_type = 'RGBA'; am.inputs[7].default_value = age_col
    L.new(agem.outputs['Result'], am.inputs['Factor']); L.new(col, am.inputs[6]); col = am.outputs[2]
    # dry, yellow-brown tips on a share of the leaflets (how far down the leaflet varies per leaflet)
    tip = N.new('ShaderNodeAttribute'); tip.attribute_name = 'tip'
    jit = N.new('ShaderNodeMath'); jit.operation = 'MULTIPLY_ADD'; jit.inputs[1].default_value = 0.25; jit.inputs[2].default_value = -0.12
    sc2 = N.new('ShaderNodeMath'); sc2.operation = 'MULTIPLY'; sc2.inputs[1].default_value = 3.71
    fr2 = N.new('ShaderNodeMath'); fr2.operation = 'FRACT'
    L.new(geo.outputs['Random Per Island'], sc2.inputs[0]); L.new(sc2.outputs[0], fr2.inputs[0]); L.new(fr2.outputs[0], jit.inputs[0])
    tp = N.new('ShaderNodeMath'); tp.operation = 'ADD'; L.new(tip.outputs['Fac'], tp.inputs[0]); L.new(jit.outputs[0], tp.inputs[1])
    burn = N.new('ShaderNodeMapRange'); burn.inputs['From Min'].default_value = burn_from; burn.inputs['From Max'].default_value = min(1.0, burn_from + 0.14)
    L.new(tp.outputs[0], burn.inputs['Value'])
    some = N.new('ShaderNodeMath'); some.operation = 'LESS_THAN'; some.inputs[1].default_value = tip_burn
    pick = N.new('ShaderNodeMath'); pick.operation = 'FRACT'
    scale = N.new('ShaderNodeMath'); scale.operation = 'MULTIPLY'; scale.inputs[1].default_value = 7.31
    L.new(geo.outputs['Random Per Island'], scale.inputs[0]); L.new(scale.outputs[0], pick.inputs[0]); L.new(pick.outputs[0], some.inputs[0])
    fac = N.new('ShaderNodeMath'); fac.operation = 'MULTIPLY'
    L.new(burn.outputs['Result'], fac.inputs[0]); L.new(some.outputs[0], fac.inputs[1])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs[7].default_value = burn_col
    L.new(fac.outputs[0], mix.inputs['Factor']); L.new(col, mix.inputs[6]); col = mix.outputs[2]
    # the underside is paler and greyer (waxy)
    bk = N.new('ShaderNodeMix'); bk.data_type = 'RGBA'; bk.blend_type = 'MULTIPLY'; bk.inputs[7].default_value = (*under, 1)
    L.new(geo.outputs['Backfacing'], bk.inputs['Factor']); L.new(col, bk.inputs[6]); col = bk.outputs[2]
    if grade:
        # living fronds read grey-green in the renderings, not chartreuse: hue toward ~100 deg, saturation -25%
        gr = N.new('ShaderNodeHueSaturation'); gr.inputs['Hue'].default_value = 0.5 + grade[0]; gr.inputs['Saturation'].default_value = grade[1]
        L.new(col, gr.inputs['Color']); col = gr.outputs['Color']
    p = N.new('ShaderNodeBsdfPrincipled')
    p.inputs['Roughness'].default_value = rough
    p.inputs['Specular IOR Level'].default_value = spec
    if gloss: p.inputs['Coat Weight'].default_value = gloss; p.inputs['Coat Roughness'].default_value = 0.15
    L.new(col, p.inputs['Base Color'])
    tr = N.new('ShaderNodeBsdfTranslucent')
    bright = N.new('ShaderNodeHueSaturation'); bright.inputs['Value'].default_value = 1.3; bright.inputs['Saturation'].default_value = 0.9
    bright.inputs['Hue'].default_value = 0.51       # transmitted light: green, not yellow
    L.new(col, bright.inputs['Color']); L.new(bright.outputs['Color'], tr.inputs['Color'])
    ms = N.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = transl
    L.new(p.outputs['BSDF'], ms.inputs[1]); L.new(tr.outputs['BSDF'], ms.inputs[2])
    L.new(ms.outputs['Shader'], out.inputs['Surface'])
    return m


def _plain(name, color, rough, bump_scale=0.0, noise_scale=40.0, var=0.0, stretch=None, coat=0.0, ramp_to=None):
    """A plain finish; var: per-island value jitter; ramp_to: a second colour along UV v (0..1)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N.get('Principled BSDF')
    p.inputs['Base Color'].default_value = color; p.inputs['Roughness'].default_value = rough
    if coat: p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = 0.2
    src = None
    if ramp_to is not None:
        uvn = N.new('ShaderNodeUVMap'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(uvn.outputs['UV'], sep.inputs[0])
        cl = N.new('ShaderNodeMath'); cl.operation = 'MINIMUM'; cl.inputs[1].default_value = 1.0; L.new(sep.outputs['Y'], cl.inputs[0])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[6].default_value = color; mx.inputs[7].default_value = ramp_to
        L.new(cl.outputs[0], mx.inputs['Factor']); src = mx.outputs[2]
    if var:
        geo = N.new('ShaderNodeNewGeometry')
        mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 1 - var; mr.inputs['To Max'].default_value = 1 + var
        L.new(geo.outputs['Random Per Island'], mr.inputs['Value'])
        hs = N.new('ShaderNodeHueSaturation'); hs.inputs['Color'].default_value = color
        if src is not None: L.new(src, hs.inputs['Color'])
        L.new(mr.outputs['Result'], hs.inputs['Value']); src = hs.outputs['Color']
    if src is not None: L.new(src, p.inputs['Base Color'])
    if bump_scale:
        tc = N.new('ShaderNodeTexCoord'); no = N.new('ShaderNodeTexNoise'); no.inputs['Scale'].default_value = noise_scale
        no.inputs['Detail'].default_value = 6
        s = tc.outputs['Object']
        if stretch:
            mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = stretch; L.new(s, mp.inputs['Vector']); s = mp.outputs['Vector']
        bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = bump_scale; bu.inputs['Distance'].default_value = 0.004
        L.new(s, no.inputs['Vector']); L.new(no.outputs['Fac'], bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    return m


def _trunk_material(name, bark, ring, lichen, spacing, photo=None, tint=(1, 1, 1), tile=(0.4, 0.8), ring_bump=0.55,
                    lichen_amt=(0.58, 0.7), knobs=0.0, rough=0.88, coat=0.0):
    """Palm bark. With `photo` (a folder holding color/normal/roughness of a real palm-trunk scan):
    the photo, wrapped round the trunk (UV u around, v = metres up), tinted, with large-scale
    weathering blotches and leaf-scar rings. Without: procedural bark with leaf-scar rings every
    `spacing` metres, lichen patches, and (knobs) the rough leaf-base stubs of a pygmy date."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N.get('Principled BSDF'); p.inputs['Roughness'].default_value = rough
    if coat: p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = 0.3
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['UV'], sep.inputs[0])
    oi = N.new('ShaderNodeObjectInfo')
    # leaf-scar rings: v (metres up) with a little wobble
    wob = N.new('ShaderNodeTexNoise'); wob.inputs['Scale'].default_value = 1.6; wob.inputs['Detail'].default_value = 3.0
    L.new(tc.outputs['Object'], wob.inputs['Vector'])
    wobm = N.new('ShaderNodeMath'); wobm.operation = 'MULTIPLY_ADD'; wobm.inputs[1].default_value = spacing * 4.0   # irregular spacing
    L.new(wob.outputs['Fac'], wobm.inputs[0]); L.new(sep.outputs['Y'], wobm.inputs[2])
    div = N.new('ShaderNodeMath'); div.operation = 'DIVIDE'; div.inputs[1].default_value = spacing
    L.new(wobm.outputs[0], div.inputs[0])
    fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(div.outputs[0], fr.inputs[0])
    ringv = N.new('ShaderNodeMapRange'); ringv.interpolation_type = 'SMOOTHSTEP'
    ringv.inputs['From Min'].default_value = 0.0; ringv.inputs['From Max'].default_value = 0.14
    L.new(fr.outputs[0], ringv.inputs['Value'])
    col_img = _img(os.path.join(photo, 'color.jpg'), 'sRGB') if photo else None
    if col_img is not None:
        mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (round(0.8 / tile[0]) or 1, 1.0 / tile[1], 1)
        off = N.new('ShaderNodeVectorMath'); off.operation = 'MULTIPLY'; off.inputs[1].default_value = (0.37, 3.1, 0)
        L.new(oi.outputs['Random'], off.inputs[0])
        add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'; L.new(tc.outputs['UV'], add.inputs[0]); L.new(off.outputs[0], add.inputs[1])
        # warp the photo up the trunk with the ring noise so its 0.9 m repeat never reads as tiled bands
        wv = N.new('ShaderNodeCombineXYZ'); wsc = N.new('ShaderNodeMath'); wsc.operation = 'MULTIPLY'; wsc.inputs[1].default_value = 0.45
        L.new(wob.outputs['Fac'], wsc.inputs[0]); L.new(wsc.outputs[0], wv.inputs['Y'])
        add2 = N.new('ShaderNodeVectorMath'); add2.operation = 'ADD'; L.new(add.outputs[0], add2.inputs[0]); L.new(wv.outputs[0], add2.inputs[1])
        L.new(add2.outputs[0], mp.inputs['Vector'])
        tx = N.new('ShaderNodeTexImage'); tx.image = col_img; L.new(mp.outputs['Vector'], tx.inputs['Vector'])
        c = tx.outputs['Color']
        tn = N.new('ShaderNodeMix'); tn.data_type = 'RGBA'; tn.blend_type = 'MULTIPLY'; tn.inputs['Factor'].default_value = 1.0
        tn.inputs[7].default_value = (*tint, 1); L.new(c, tn.inputs[6]); c = tn.outputs[2]
        # darker scar bands
        rb = N.new('ShaderNodeMix'); rb.data_type = 'RGBA'; rb.blend_type = 'MULTIPLY'; rb.inputs[6].default_value = (1, 1, 1, 1)
        inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; L.new(ringv.outputs['Result'], inv.inputs[1])
        rbm = N.new('ShaderNodeMath'); rbm.operation = 'MULTIPLY'; rbm.inputs[1].default_value = 0.35; L.new(inv.outputs[0], rbm.inputs[0])
        L.new(rbm.outputs[0], rb.inputs['Factor']); rb.inputs[7].default_value = (0.55, 0.53, 0.5, 1)
        L.new(c, rb.inputs[6]); c = rb.outputs[2]
        blot = N.new('ShaderNodeTexNoise'); blot.inputs['Scale'].default_value = 2.2; blot.inputs['Detail'].default_value = 8; blot.inputs['Roughness'].default_value = 0.62
        mpb = N.new('ShaderNodeMapping'); mpb.inputs['Scale'].default_value = (3.0, 3.0, 0.7)
        L.new(tc.outputs['Object'], mpb.inputs['Vector']); L.new(mpb.outputs['Vector'], blot.inputs['Vector'])
        bm = N.new('ShaderNodeMapRange'); bm.inputs['From Min'].default_value = 0.42; bm.inputs['From Max'].default_value = 0.68
        bm.inputs['To Min'].default_value = 0.6; bm.inputs['To Max'].default_value = 1.1
        L.new(blot.outputs['Fac'], bm.inputs['Value'])
        dk = N.new('ShaderNodeMix'); dk.data_type = 'RGBA'; dk.blend_type = 'MULTIPLY'; dk.inputs['Factor'].default_value = 1.0
        cb = N.new('ShaderNodeCombineColor'); [L.new(bm.outputs['Result'], cb.inputs[i]) for i in range(3)]
        L.new(c, dk.inputs[6]); L.new(cb.outputs[0], dk.inputs[7]); c = dk.outputs[2]
        nimg = _img(os.path.join(photo, 'normal.jpg'), 'Non-Color')
        if nimg is not None:
            tn2 = N.new('ShaderNodeTexImage'); tn2.image = nimg; L.new(mp.outputs['Vector'], tn2.inputs['Vector'])
            nm = N.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 1.3; L.new(tn2.outputs['Color'], nm.inputs['Color'])
            bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = ring_bump * 0.6; bu.inputs['Distance'].default_value = 0.01
            L.new(ringv.outputs['Result'], bu.inputs['Height']); L.new(nm.outputs['Normal'], bu.inputs['Normal'])
            L.new(bu.outputs['Normal'], p.inputs['Normal'])
        rimg = _img(os.path.join(photo, 'roughness.jpg'), 'Non-Color')
        if rimg is not None:
            tr = N.new('ShaderNodeTexImage'); tr.image = rimg; L.new(mp.outputs['Vector'], tr.inputs['Vector'])
            L.new(tr.outputs['Color'], p.inputs['Roughness'])
    else:
        grain = N.new('ShaderNodeTexNoise'); grain.inputs['Scale'].default_value = 60.0; grain.inputs['Detail'].default_value = 6
        stretch = N.new('ShaderNodeMapping'); stretch.inputs['Scale'].default_value = (6.0, 6.0, 0.6)
        L.new(tc.outputs['Object'], stretch.inputs['Vector']); L.new(stretch.outputs['Vector'], grain.inputs['Vector'])
        blot = N.new('ShaderNodeTexNoise'); blot.inputs['Scale'].default_value = 5.0; blot.inputs['Detail'].default_value = 8; blot.inputs['Roughness'].default_value = 0.7
        L.new(tc.outputs['Object'], blot.inputs['Vector'])
        lich = N.new('ShaderNodeMapRange'); lich.inputs['From Min'].default_value = lichen_amt[0]; lich.inputs['From Max'].default_value = lichen_amt[1]
        L.new(blot.outputs['Fac'], lich.inputs['Value'])
        c1 = N.new('ShaderNodeMix'); c1.data_type = 'RGBA'; c1.inputs[6].default_value = ring; c1.inputs[7].default_value = bark
        L.new(ringv.outputs['Result'], c1.inputs['Factor'])
        c2 = N.new('ShaderNodeMix'); c2.data_type = 'RGBA'; c2.inputs[7].default_value = lichen
        L.new(lich.outputs['Result'], c2.inputs['Factor']); L.new(c1.outputs[2], c2.inputs[6])
        gm = N.new('ShaderNodeMix'); gm.data_type = 'RGBA'; gm.blend_type = 'MULTIPLY'; gm.inputs['Factor'].default_value = 0.35
        L.new(c2.outputs[2], gm.inputs[6]); L.new(grain.outputs['Color'], gm.inputs[7])
        c = gm.outputs[2]
        hb = N.new('ShaderNodeMath'); hb.operation = 'MULTIPLY_ADD'; hb.inputs[1].default_value = 0.25
        L.new(grain.outputs['Fac'], hb.inputs[0]); L.new(ringv.outputs['Result'], hb.inputs[2])
        h = hb.outputs[0]
        if knobs:
            vo = N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 1.0
            mk = N.new('ShaderNodeMapping'); mk.inputs['Scale'].default_value = (9.0, 1.0 / (spacing * 1.6), 1)
            L.new(tc.outputs['UV'], mk.inputs['Vector']); L.new(mk.outputs['Vector'], vo.inputs['Vector'])
            kn = N.new('ShaderNodeMath'); kn.operation = 'MULTIPLY_ADD'; kn.inputs[1].default_value = -knobs
            L.new(vo.outputs['Distance'], kn.inputs[0]); L.new(h, kn.inputs[2]); h = kn.outputs[0]
            dkn = N.new('ShaderNodeMix'); dkn.data_type = 'RGBA'; dkn.blend_type = 'MULTIPLY'; dkn.inputs[7].default_value = (0.5, 0.45, 0.4, 1)
            L.new(vo.outputs['Distance'], dkn.inputs['Factor']); L.new(c, dkn.inputs[6]); c = dkn.outputs[2]
        bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = ring_bump; bu.inputs['Distance'].default_value = 0.012
        L.new(h, bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    # darker, earthier at the foot (soil splash, irrigation)
    foot = N.new('ShaderNodeMapRange'); foot.inputs['From Min'].default_value = 0.5; foot.inputs['From Max'].default_value = 0.0
    L.new(sep.outputs['Y'], foot.inputs['Value'])
    c3 = N.new('ShaderNodeMix'); c3.data_type = 'RGBA'; c3.blend_type = 'MULTIPLY'; c3.inputs[7].default_value = (0.6, 0.5, 0.4, 1)
    L.new(foot.outputs['Result'], c3.inputs['Factor']); L.new(c, c3.inputs[6])
    L.new(c3.outputs[2], p.inputs['Base Color'])
    return m


def _boot_material(name):
    """Cut leaf bases: grey-brown fibrous wood, greener on the youngest (attribute 'age' 0 = young)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N.get('Principled BSDF'); p.inputs['Roughness'].default_value = 0.85
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (90, 90, 6)
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    fib = N.new('ShaderNodeTexNoise'); fib.inputs['Scale'].default_value = 1.0; fib.inputs['Detail'].default_value = 4
    L.new(mp.outputs['Vector'], fib.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); e = ramp.color_ramp.elements
    e[0].position = 0.3; e[0].color = (0.045, 0.038, 0.028, 1); e[1].position = 0.75; e[1].color = (0.2, 0.17, 0.13, 1)
    L.new(fib.outputs['Fac'], ramp.inputs['Fac'])
    geo = N.new('ShaderNodeNewGeometry')
    vr = N.new('ShaderNodeMapRange'); vr.inputs['To Min'].default_value = 0.7; vr.inputs['To Max'].default_value = 1.3
    L.new(geo.outputs['Random Per Island'], vr.inputs['Value'])
    hs = N.new('ShaderNodeHueSaturation'); L.new(ramp.outputs['Color'], hs.inputs['Color']); L.new(vr.outputs['Result'], hs.inputs['Value'])
    age = N.new('ShaderNodeAttribute'); age.attribute_name = 'age'
    am = N.new('ShaderNodeMapRange'); am.inputs['From Min'].default_value = 0.35; am.inputs['From Max'].default_value = 0.0
    L.new(age.outputs['Fac'], am.inputs['Value'])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[7].default_value = (0.09, 0.12, 0.035, 1)
    L.new(am.outputs['Result'], mx.inputs['Factor']); L.new(hs.outputs['Color'], mx.inputs[6])
    L.new(mx.outputs[2], p.inputs['Base Color'])
    bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = 0.6; bu.inputs['Distance'].default_value = 0.003
    L.new(fib.outputs['Fac'], bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    return m


def _fruit_material(name, cols):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N.get('Principled BSDF'); p.inputs['Roughness'].default_value = 0.38
    geo = N.new('ShaderNodeNewGeometry')
    ramp = N.new('ShaderNodeValToRGB'); e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = cols[0]; e[1].position = 1.0; e[1].color = cols[-1]
    for t, c in zip(np.linspace(0, 1, len(cols))[1:-1], cols[1:-1]): e.new(float(t)).color = c
    L.new(geo.outputs['Random Per Island'], ramp.inputs['Fac']); L.new(ramp.outputs['Color'], p.inputs['Base Color'])
    return m


# ---------------------------------------------------------------- geometry
LEAFLET_ST = np.array([0.0, 0.1, 0.24, 0.42, 0.62, 0.82, 1.0])


def leaflets(buf, P, T, side, beta, sweep, length, width, droop, fold, age=0.0, limp=1.4, twist=None):
    """Many leaflets at once. P (n,3) points on the rachis, T (n,3) rachis tangents, side (n,) -1/+1,
    beta (n,) angle out of the frond plane, sweep (n,) lean toward the frond tip, length, width,
    droop (n,) gravity bend (how far the blade turns toward straight down), fold: V of the blade.
    Each leaflet: a narrow V-folded blade arcing away from the rachis and hanging limp toward its point."""
    n = len(P)
    if n == 0: return
    Y = _norm(np.cross(UP[None], T)); bad = np.linalg.norm(np.cross(UP[None], T), axis=1) < 1e-3
    Y[bad] = np.array([0, 1.0, 0])
    Nn = _norm(np.cross(T, Y))
    sw, cb = sweep[:, None], beta[:, None]
    d0 = _norm(np.cos(sw) * (side[:, None] * Y * np.cos(cb) + Nn * np.sin(cb)) + np.sin(sw) * T)
    st = LEAFLET_ST; k = len(st)
    pts = np.zeros((n, k, 3)); dirs = np.zeros((n, k, 3))
    p = P.copy(); pts[:, 0] = p
    for i in range(1, k):
        t = (st[i - 1] + st[i]) / 2
        d = _norm(d0 - UP[None] * (droop * t ** limp)[:, None])
        p = p + d * (length * (st[i] - st[i - 1]))[:, None]
        pts[:, i] = p; dirs[:, i] = d
    dirs[:, 0] = dirs[:, 1]
    nb = _norm(np.cross(T[:, None, :], dirs))
    nb = np.where(nb[..., 2:3] < 0, -nb, nb)
    if twist is not None:            # twist the blade about its own axis toward the tip
        a = (twist[:, None] * st[None, :])[..., None]
        wv = _norm(np.cross(nb, dirs))
        nb = _norm(nb * np.cos(a) + wv * np.sin(a))
    w = _norm(np.cross(nb, dirs))
    hw = width[:, None] * 0.5 * (0.35 + 0.65 * np.sin(np.pi * np.minimum(1.0, 0.18 + st * 0.95)) ** 0.7) * (1 - st ** 3)
    fo = fold[:, None] if np.ndim(fold) else fold
    V = np.stack([pts - w * hw[..., None], pts + nb * (hw * fo)[..., None], pts + w * hw[..., None]], 2)   # (n,k,3,3)
    a = np.arange(k - 1)[:, None] * 3
    f = np.concatenate([np.stack([a, a + 3, a + 4, a + 1], -1), np.stack([a + 1, a + 4, a + 5, a + 2], -1)], 0).reshape(-1, 4)
    F = (f[None] + (np.arange(n) * k * 3)[:, None, None]).reshape(-1, 4)
    tips = np.broadcast_to(st[None, :, None], (n, k, 3)).ravel()
    ages = np.broadcast_to(np.asarray(age, np.float32).reshape(-1, 1, 1) if np.ndim(age) else np.float32(age), (n, k, 3)).ravel()
    uv = np.stack([np.broadcast_to(np.array([0, 0.5, 1.0])[None, None], (n, k, 3)), np.broadcast_to(st[None, :, None], (n, k, 3))], -1)
    buf.add(V.reshape(-1, 3), F, uv.reshape(-1, 2), tip=tips, age=ages)


def _tube(buf, pts, radii, sides=8, v0=0.0, flat=1.0, u0=0.0, ref=None, **attrs):
    """A tube along pts (UV u around, v = metres along); flat < 1 squashes it (petioles)."""
    pts = np.asarray(pts, float)
    T = _norm(np.gradient(pts, axis=0))
    if ref is None: ref = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    verts, uvs, faces = [], [], []
    s = 0.0
    for i, (p, t, r) in enumerate(zip(pts, T, radii)):
        if i: s += np.linalg.norm(pts[i] - pts[i - 1])
        a = _norm(np.cross(t, ref)); b = np.cross(t, a)
        for j in range(sides + 1):
            th = 2 * math.pi * j / sides
            verts.append(p + r * (math.cos(th) * a + flat * math.sin(th) * b)); uvs.append((u0 + j / sides, v0 + s))
    for i in range(len(pts) - 1):
        for j in range(sides):
            a = i * (sides + 1) + j
            faces.append([a, a + 1, a + sides + 2, a + sides + 1])
    buf.add(verts, faces, uvs, **attrs)


def _frond_axis(L, elev, droop, n=24, twist=0.0, rng=None, power=1.6):
    """Rachis: rises at `elev`, bends down progressively (more on long, old fronds), a slight sideways sweep."""
    pts, p = [np.zeros(3)], np.zeros(3)
    side = rng.uniform(-0.12, 0.12) if rng else 0.0
    for i in range(n):
        s = (i + 0.5) / n
        a = elev - droop * s ** power
        p = p + (L / n) * np.array([math.cos(a), side * math.sin(math.pi * s) + math.sin(twist * s) * 0.1, math.sin(a)])
        pts.append(p.copy())
    return np.array(pts)


# Species. Lengths in metres for a palm of height `href` (crowns are scaled (h / href) ** spow).
#   fronds: live fronds per crown; L: frond length; pet: bare petiole (fraction of L); ns: leaflet positions per side;
#   ll: longest leaflet; lw: leaflet width; arr: 'plumose' (clusters in several planes) | 'brush' (all round) | 'v';
#   vb: V angle (rad) for 'v'; ld: leaflet droop (base, + along frond); limp: where the droop sets in (low = near base);
#   elev: rachis angle of the newest / oldest frond (deg); rd: rachis droop; rpow: how late the rachis bends;
#   r0: frond attachment radius; drop: oldest frond attaches this far down; shaft: crownshaft length (m) or 0;
#   dead: hanging dead fronds (choices); fruit: panicles (choices); rad: trunk radius (m); ring: scar spacing (m)
KIND = {
    'queen': dict(fronds=(18, 24), L=(3.9, 4.9), pet=0.14, ns=150, ll=0.84, lw=0.02, arr='plumose', ld=(3.0, 5.2), limp=0.7,
                  elev=(60, -50), epow=0.8, rd=(1.25, 0.9), rpow=2.0, r0=0.1, drop=0.55, shaft=0, dead=(2, 2, 3, 3, 4), fruit=(1, 2, 2, 3),
                  rad=0.16, ring=0.09, href=7.0, spow=0.3, rachis=0.03, broken=0.11),
    'foxtail': dict(fronds=(8, 11), L=(2.5, 3.1), pet=0.1, ns=95, ll=0.48, lw=0.028, arr='brush', ld=(0.6, 1.6), limp=1.4,
                    elev=(72, -12), epow=1.0, rd=(0.8, 0.9), rpow=1.8, r0=0.06, drop=0.2, shaft=1.0, dead=(0, 0, 1), fruit=(0, 0, 1),
                    rad=0.15, ring=0.07, href=7.0, spow=0.3, rachis=0.026, broken=0.02),
    'christmas': dict(fronds=(9, 12), L=(1.45, 1.85), pet=0.16, ns=58, ll=0.56, lw=0.034, arr='v', vb=0.5, ld=(0.4, 1.0), limp=1.6,
                      elev=(72, 8), epow=1.0, rd=(1.9, 0.6), rpow=1.35, r0=0.03, drop=0.1, shaft=0.75, dead=(0,), fruit=(0, 1, 1, 2),
                      rad=0.085, ring=0.09, href=4.5, spow=0.35, rachis=0.018, broken=0.02),
    'lipstick': dict(fronds=(6, 8), L=(1.35, 1.75), pet=0.26, ns=44, ll=0.5, lw=0.036, arr='v', vb=0.28, ld=(0.25, 0.6), limp=1.8,
                     elev=(82, 30), epow=1.0, rd=(0.75, 0.4), rpow=1.6, r0=0.02, drop=0.06, shaft=0.85, dead=(0,), fruit=(0,),
                     rad=0.04, ring=0.11, href=4.0, spow=0.35, rachis=0.014, broken=0.02),
    'areca': dict(fronds=(7, 10), L=(1.6, 2.2), pet=0.12, ns=55, ll=0.55, lw=0.028, arr='v', vb=0.32, ld=(0.8, 0.6), limp=1.4,
                  elev=(78, 16), epow=1.0, rd=(0.9, 0.55), rpow=1.6, r0=0.02, drop=0.15, shaft=0.35, dead=(0,), fruit=(0,),
                  rad=0.04, ring=0.1, href=3.0, spow=0.35, rachis=0.016, broken=0.02),
    'roebelenii': dict(fronds=(32, 44), L=(0.95, 1.3), pet=0.22, ns=42, ll=0.3, lw=0.013, arr='v2', vb=0.42, ld=(0.6, 1.1), limp=1.2,
                       elev=(80, -28), epow=0.9, rd=(0.85, 0.7), rpow=1.6, r0=0.05, drop=0.25, shaft=0, dead=(0, 1, 2), fruit=(0,),
                       rad=0.075, ring=0.05, href=1.8, spow=0.35, rachis=0.011, broken=0.03),
    'cycad': dict(fronds=(24, 36), L=(0.75, 1.1), pet=0.18, ns=72, ll=0.16, lw=0.0065, arr='v', vb=0.18, ld=(0.05, 0.1), limp=2.0,
                  elev=(62, 2), epow=1.0, rd=(0.35, 0.3), rpow=1.4, r0=0.08, drop=0.06, shaft=0, dead=(0, 1), fruit=(0,),
                  rad=0.11, ring=0.035, href=0.5, spow=0.25, rachis=0.008, broken=0.0),
    'coconut': dict(fronds=(20, 26), L=(3.8, 4.8), pet=0.12, ns=85, ll=1.0, lw=0.045, arr='v', vb=-0.55, ld=(0.9, 1.0), limp=1.4,
                    elev=(70, -40), epow=1.0, rd=(0.66, 0.66), rpow=1.6, r0=0.12, drop=0.3, shaft=0, dead=(0, 1, 1, 2), fruit=(1,),
                    rad=0.16, ring=0.09, href=10.0, spow=0.25, rachis=0.045, broken=0.03),
}
KIND['foxtail_legacy'] = KIND['queen']
ALIASES = {'foxtail_legacy': 'queen'}


def _frond(leaf, stem, rng, kind, L, elev, droop, age):
    K = KIND[kind]
    axis = _frond_axis(L, elev, droop, twist=rng.uniform(-1, 1), rng=rng, power=K['rpow'])
    pet = K['pet'] * rng.uniform(0.85, 1.15)
    u_ = np.linspace(0, 1, len(axis))
    _tube(stem, axis, K['rachis'] * (0.18 + 0.82 * (1 - u_) ** 1.3 + 0.9 * np.exp(-u_ * 25)), sides=6, flat=0.7, age=age)
    T = _norm(np.gradient(axis, axis=0))
    nr = np.random.default_rng(rng.randrange(1 << 30))
    m = len(axis) - 1
    def at(s):
        idx = s * m; i0 = np.minimum(idx.astype(int), m - 1); f = (idx - i0)[:, None]
        return axis[i0] * (1 - f) + axis[i0 + 1] * f, _norm(T[i0] * (1 - f) + T[i0 + 1] * f)
    ns = K['ns']; arr = K['arr']
    if arr == 'plumose':
        # leaflets in clusters of 2-5, leaving the rachis in several planes, limp, hanging
        S, SIDE, BETA = [], [], []
        for side in (-1, 1):
            s = pet; cnt = 0
            while cnt < ns and s < 0.995:
                c = int(nr.integers(2, 6))
                for j in range(c):
                    S.append(s + nr.uniform(0, 0.006)); SIDE.append(side)
                    BETA.append(-0.75 + 1.85 * (j + nr.uniform(0, 0.8)) / c)
                cnt += c
                s += (1 - pet) * c / ns * nr.uniform(0.85, 1.25)
        s = np.array(S); side = np.array(SIDE, float); beta = np.array(BETA)
    elif arr == 'brush':
        # leaflets all round the rachis (bottle-brush), several at each node
        S, SIDE, BETA = [], [], []
        for i in range(ns):
            s0 = pet + (1 - pet) * (i + nr.uniform(0, 0.7)) / ns
            for j in range(4):
                S.append(s0 + nr.uniform(0, 0.004)); SIDE.append(1.0 if j % 2 else -1.0)
                BETA.append(-1.25 + 2.6 * (j // 2 + nr.uniform(0, 1)) / 2)
        s = np.array(S); side = np.array(SIDE); beta = np.array(BETA)
    else:
        n = ns * 2
        s = np.sort(pet + (1 - pet) * (np.arange(n) // 2 + nr.uniform(0, 0.8, n)) / (n // 2))
        side = np.where(np.arange(n) % 2, 1.0, -1.0)
        vb = K.get('vb', 0.3)
        if arr == 'v2':                       # Phoenix: leaflets in two planes, alternating up and down
            beta = vb * np.where(nr.random(n) < 0.5, 1.0, -0.5) + nr.uniform(-0.15, 0.15, n)
        else:
            beta = vb + nr.uniform(-0.12, 0.12, n)
    n = len(s)
    P, Tt = at(s)
    u = (s - pet) / (1 - pet)
    if arr == 'plumose':
        prof = np.sin(np.pi * (0.08 + 0.86 * u)) ** 0.6 * (1 - 0.3 * u)
    elif arr == 'brush':
        prof = np.sin(np.pi * (0.1 + 0.85 * u)) ** 0.5 * (1 - 0.35 * u)
    else:
        prof = np.sin(np.pi * (0.1 + 0.85 * u)) ** 0.8 * (1 - 0.3 * u)
    ln = K['ll'] * prof * nr.uniform(0.8, 1.1, n)
    broken = nr.random(n) < K['broken']; ln[broken] *= nr.uniform(0.25, 0.6, broken.sum())
    d0, d1 = K['ld']
    dr = (d0 + d1 * u ** 0.8) * (0.85 + 0.45 * age) * nr.uniform(0.7, 1.3, n)
    sweep = nr.uniform(0.25, 0.55, n) if arr in ('plumose', 'brush') else nr.uniform(0.45, 0.65, n)
    tw = nr.uniform(-0.6, 0.6, n) if arr in ('plumose', 'brush') else None
    leaflets(leaf, P, Tt, side, beta, sweep, ln, np.full(n, K['lw']) * nr.uniform(0.85, 1.15, n),
             dr, np.full(n, 0.3 if arr != 'brush' else 0.15), age=np.full(n, age), limp=K['limp'], twist=tw)


def _drupes(buf, centres, r, elong=1.2):
    """Small round fruit (octahedra, smooth shaded) at centres (n,3)."""
    n = len(centres)
    if not n: return
    d = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, elong), (0, 0, -elong)], float)
    V = centres[:, None, :] + r[:, None, None] * d[None]
    f = np.array([[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]])
    F = (f[None] + (np.arange(n) * 6)[:, None, None]).reshape(-1, 3)
    buf.add(V.reshape(-1, 3), F)


def _panicle(stem, fruit, spathe, rng, nr, origin, hd, reach, hang, n_rach, n_fruit, fr_r, spathe_len=0.0):
    """A fruiting panicle: an arching peduncle from `origin` heading `hd`, rachillae hanging off its end,
    fruit along each; optionally the woody boat-shaped spathe that enclosed it."""
    stalk = [origin + hd * reach * t + np.array([0, 0, -hang * t * t]) for t in np.linspace(0, 1, 6)]
    _tube(stem, stalk, np.linspace(0.028, 0.014, 6), sides=5, age=0.3)
    top = stalk[-1]
    C = []
    for _ in range(n_rach):
        b0 = top + np.array([rng.gauss(0, 0.09), rng.gauss(0, 0.09), rng.uniform(-0.12, 0.06)])
        bd = _norm(np.array([rng.gauss(0, 0.45), rng.gauss(0, 0.45), -1.0]) + hd * 0.25)
        ln = rng.uniform(0.35, 0.85)
        mid = b0 + bd * ln * 0.5 + np.array([0, 0, -0.04])
        _tube(stem, [b0, mid, b0 + bd * ln], [0.005, 0.004, 0.003], sides=3, age=0.5)
        for t in np.linspace(0.08, 1.0, rng.randint(*n_fruit)):
            C.append(b0 + bd * ln * t + np.array([rng.gauss(0, 0.016), rng.gauss(0, 0.016), rng.gauss(0, 0.008)]))
    if C:
        C = np.array(C); _drupes(fruit, C, nr.uniform(*fr_r, len(C)), 1.2)
    if spathe_len:
        # the woody spathe: a long narrow boat, open side down, hanging beside the panicle
        sp0 = origin + hd * 0.08
        sd = _norm(hd * 0.55 + np.array([0, 0, 0.6 if rng.random() < 0.5 else -0.9]))
        pts = [sp0 + sd * spathe_len * t for t in np.linspace(0, 1, 7)]
        rr = [0.02, 0.055, 0.075, 0.075, 0.06, 0.035, 0.004]
        _tube(spathe, pts, rr, sides=8, flat=0.55, age=0.5)


def crown_mesh(kind, seed, mats):
    """Fronds, spear, crownshaft, leaf bases, dead fronds and fruit; origin at the top of the trunk, Z up."""
    rng = random.Random(seed)
    K = KIND[kind]
    leaf, stem, dead, fruit, base, shaft, deadleaf, spathe = (MeshBuf() for _ in range(8))
    n = rng.randint(*K['fronds'])
    az0 = rng.uniform(0, 2 * math.pi)
    e0, e1 = K['elev']
    for k in range(n):
        age = k / max(1, n - 1)                            # 0 = newest (upright) .. 1 = oldest (hanging)
        elev = math.radians(e0 + (e1 - e0) * age ** K['epow'] + rng.uniform(-8, 8))
        droop = (K['rd'][0] + K['rd'][1] * age) * rng.uniform(0.85, 1.2)
        drop = -K['drop'] * age
        L = rng.uniform(*K['L']) * (0.82 if age < 0.12 else 1.0) * (rng.uniform(0.75, 1.0) if rng.random() < 0.2 else 1.0)
        lb, sb = MeshBuf(), MeshBuf()
        _frond(lb, sb, rng, kind, L, elev, droop, age)
        az = az0 + k * GOLDEN + rng.uniform(-0.35, 0.35)
        R = np.array(Matrix.Rotation(az, 3, 'Z'))
        off = R @ np.array([K['r0'], 0, drop])
        _move(lb, leaf, R, off); _move(sb, stem, R, off)
        if kind in ('queen', 'coconut', 'roebelenii'):    # the fibrous sheath of the leaf base, wrapping the trunk
            hd = R @ np.array([1.0, 0, 0])
            p0 = np.array([0, 0, drop - 0.45]) + hd * 0.09
            p1 = off + hd * 0.06 + np.array([0, 0, 0.05])
            pts = [p0 + (p1 - p0) * t + hd * 0.07 * math.sin(math.pi * t) for t in np.linspace(0, 1, 5)]
            w = {'queen': 1.0, 'coconut': 1.1, 'roebelenii': 0.55}[kind]
            _tube(base, pts, [0.07 * w, 0.09 * w, 0.085 * w, 0.065 * w, 0.04 * w], sides=6, flat=0.5, age=age)
    # unopened spear leaf
    sp = 1.3 if kind in ('queen', 'coconut') else 0.6 if kind in ('foxtail', 'christmas', 'areca', 'lipstick') else 0.3
    _tube(stem, [[0, 0, 0], [0.01, 0, sp * 0.45], [0.02, 0.01, sp]], [0.035 * (sp / 1.3 + 0.3), 0.025, 0.004], sides=6, age=0.0)
    # crownshaft: the smooth sheath of the leaf bases at the top of the trunk
    if K['shaft']:
        L_ = K['shaft']; r_ = K['rad'] * {'foxtail': 1.05, 'christmas': 1.15, 'lipstick': 1.25, 'areca': 1.15}.get(kind, 1.1)
        zz = np.linspace(-L_, 0.06, 8)
        rr = [r_ * (1.0 + 0.12 * math.sin(math.pi * min(1, (z + L_) / L_ * 1.1)) - 0.35 * max(0, (z + 0.12) / 0.18)) for z in zz]
        _tube(shaft, [[0, 0, z] for z in zz], rr, sides=14, age=0.0)
    # dry fronds hanging against the trunk (queen palms keep a few until they fall)
    for _ in range(rng.choice(K['dead'])):
        lb, sb = MeshBuf(), MeshBuf()
        La = rng.uniform(*K['L']) * rng.uniform(0.7, 0.95)
        _frond(lb, sb, rng, kind, La, math.radians(rng.uniform(-86, -70)), 0.15, 1.0)
        R = np.array(Matrix.Rotation(rng.uniform(0, 6.28), 3, 'Z'))
        o = R @ np.array([K['r0'] + 0.04, 0, -K['drop'] - rng.uniform(0.05, 0.4)])
        _move(lb, deadleaf, R, o); _move(sb, dead, R, o)
    nr = np.random.default_rng(seed)
    if kind == 'coconut':
        c = []
        for _ in range(rng.randint(6, 16)):
            a = rng.uniform(0, 6.28); c.append([math.cos(a) * 0.25, math.sin(a) * 0.25, rng.uniform(-0.55, -0.2)])
        _drupes(fruit, np.array(c), nr.uniform(0.1, 0.13, len(c)), 1.1)
    elif kind == 'queen':
        # one to three panicles of orange/green drupes hanging below the crown on arching stalks, with spathes
        for _ in range(rng.choice(K['fruit'])):
            a = rng.uniform(0, 6.28); hd = np.array([math.cos(a), math.sin(a), 0.0])
            _panicle(stem, fruit, spathe, rng, nr, hd * 0.16 + np.array([0, 0, -0.42]), hd, 0.38, 0.4, rng.randint(26, 40), (9, 15), (0.011, 0.015),
                     spathe_len=rng.uniform(0.7, 1.0))
    elif kind in ('foxtail', 'christmas'):
        for _ in range(rng.choice(K['fruit'])):
            a = rng.uniform(0, 6.28); hd = np.array([math.cos(a), math.sin(a), 0.0])
            sz = (0.018, 0.024) if kind == 'foxtail' else (0.012, 0.016)
            _panicle(stem, fruit, spathe, rng, nr, hd * K['rad'] + np.array([0, 0, -K['shaft'] - 0.05]), hd, 0.22, 0.25,
                     rng.randint(10, 18), (5, 9), sz)
    J = MeshBuf(); ml = []
    fk = {'coconut': 'coconut', 'foxtail': 'fruit_red', 'christmas': 'fruit_red'}.get(kind, 'fruit')
    for buf, m in ((leaf, mats['leaf_' + kind]), (stem, mats.get('rachis_' + kind, mats['rachis'])), (dead, mats['dead']),
                   (deadleaf, mats['deadleaf']), (fruit, mats[fk]), (base, mats['boot']), (spathe, mats['spathe']),
                   (shaft, mats.get('shaft_' + kind, mats['rachis']))):
        if buf.parts: J.extend(buf, mat=len(ml)); ml.append(m)
    return [J.mesh(f'{kind}{seed}-crown', ml)]


def _move(src, dst, R, off):
    dst.extend(src, R, off)


def trunk_mesh(height, r0, lean_dir, bend, kind, seed):
    """Trunk (and, for queen palms, the boots below the crown) as MeshBufs at the origin."""
    rng = random.Random(seed)
    K = KIND[kind]
    height = height - K['shaft']                       # the crownshaft (part of the crown) tops the trunk
    n = max(8, int(height / (0.2 if kind in ('queen', 'foxtail', 'coconut') else 0.15)))
    pts, radii = [], []
    for i in range(n + 1):
        t = i / n
        off = bend * height * (0.6 * t + 0.4 * t * t) if kind == 'queen' else bend * height * t * t   # queen: a straight lean
        pts.append([math.cos(lean_dir) * off, math.sin(lean_dir) * off, height * t])
        if kind == 'queen':          # flared foot, a gentle swelling a third of the way up
            r = r0 * (1.0 + 0.4 * math.exp(-t * 22) + 0.08 * math.exp(-((t - 0.35) / 0.25) ** 2) - 0.2 * t)
        elif kind == 'foxtail':      # Wodyetia: swollen a little above the middle, narrowing under the crownshaft
            r = r0 * (1.0 + 0.3 * math.exp(-t * 20) + 0.12 * math.exp(-((t - 0.5) / 0.25) ** 2) - 0.2 * t)
        elif kind == 'christmas':    # a swollen foot, then slender
            r = r0 * (1.0 + 0.55 * math.exp(-t * 9) - 0.1 * t)
        elif kind == 'coconut':
            r = r0 * (1.0 + 0.6 * math.exp(-t * 14) - 0.22 * t)
        elif kind in ('roebelenii', 'cycad'):
            r = r0 * (1.0 + 0.25 * math.exp(-t * 6) + 0.06 * math.sin(t * 40 + seed))
        else:
            r = r0 * (1.0 + 0.2 * math.exp(-t * 20) - 0.15 * t)
        radii.append(r)
    buf = MeshBuf()
    _tube(buf, pts, radii, sides={'queen': 16, 'foxtail': 14, 'coconut': 10, 'christmas': 10}.get(kind, 8), u0=rng.random())
    top = np.array(pts[-1]); tdir = _norm(np.array(pts[-1]) - np.array(pts[-2]))
    sh = None
    if kind == 'queen':
        # the cut leaf bases ('boots') of old fronds in a spiral below the crown: a fibrous collar and flat,
        # wedge-shaped stubs standing up and out from the trunk, the older ones lower down and greyer
        sb = MeshBuf()
        rt = radii[-1]
        _tube(sb, [top + tdir * (h - 1.5) for h in np.linspace(0, 1.5, 7)], [rt * f for f in (0.98, 1.08, 1.18, 1.26, 1.3, 1.25, 1.0)], sides=16, age=0.6)
        nb = rng.randint(18, 26); a0 = rng.uniform(0, 6.28)
        for k in range(nb):
            u = k / (nb - 1)
            a = a0 + k * GOLDEN + rng.uniform(-0.2, 0.2); hd = np.array([math.cos(a), math.sin(a), 0.0])
            h0 = -0.5 - 1.25 * u + rng.uniform(-0.08, 0.08)
            if top[2] + h0 < 1.5: continue
            p0 = top + tdir * h0 + hd * rt * 0.95
            d = _norm(hd * rng.uniform(0.45, 1.0) + np.array([0, 0, 1.0]))
            ln = rng.uniform(0.3, 0.6) * (1 - 0.35 * u)
            w = rng.uniform(0.06, 0.09)
            _tube(sb, [p0 + d * ln * t + hd * 0.05 * t * t for t in np.linspace(0, 1, 4)], [w, w * 0.9, w * 0.75, w * 0.4], sides=6, flat=0.35, age=0.4 + 0.6 * u)
        sh = sb
    elif kind == 'cycad':
        # a shaggy collar of old leaf bases at the top of the stem
        sb = MeshBuf(); rt = radii[-1]
        for k in range(rng.randint(14, 22)):
            a = rng.uniform(0, 6.28); hd = np.array([math.cos(a), math.sin(a), 0.0])
            p0 = top + np.array([0, 0, -rng.uniform(0.0, 0.25)]) + hd * rt * 0.8
            d = _norm(hd * 0.8 + np.array([0, 0, 0.6])); ln = rng.uniform(0.06, 0.12)
            _tube(sb, [p0, p0 + d * ln], [0.03, 0.01], sides=5, flat=0.5, age=0.9)
        sh = sb
    return buf, sh, Vector(top.tolist()), Vector(tdir.tolist())


def materials():
    lin = lambda r, g, b: (r, g, b, 1)
    photo = os.path.join(ASSETS, 'bark', 'palm_trunk')
    photo = photo if os.path.exists(os.path.join(photo, 'color.jpg')) else None
    return {
        # queen: grey-green to yellow-green leaflets, a good share with brown dry ends, the oldest fronds olive-yellow
        'leaf_queen': _leaf_material('palm leaf queen', [_lin('#2e4628'), _lin('#3a562c'), _lin('#486632'), _lin('#587438'), _lin('#6a7e40')], 0.1,
                                     age_col=_lin('#74763a'), burn_col=_lin('#8a7440'), burn_from=0.86, transl=0.3, under=(1.25, 1.28, 1.22), age_amt=0.5),
        'leaf_foxtail': _leaf_material('palm leaf foxtail', [_lin('#33521f'), _lin('#44672a'), _lin('#55782f'), _lin('#6a8836')], 0.15,
                                       age_col=_lin('#8a8034'), burn_from=0.85, transl=0.36),
        'leaf_christmas': _leaf_material('palm leaf christmas', [_lin('#3a5e22'), _lin('#4c7228'), _lin('#5f8430'), _lin('#76963a')], 0.12,
                                         age_col=_lin('#9a8a3a'), burn_from=0.88, transl=0.38, rough=0.38, spec=0.45),
        'leaf_lipstick': _leaf_material('palm leaf lipstick', [_lin('#2e5020'), _lin('#3c6226'), _lin('#4c722c'), _lin('#5e8232')], 0.1,
                                        age_col=_lin('#8a8034'), burn_from=0.9, transl=0.34, rough=0.35, spec=0.5),
        'leaf_areca': _leaf_material('areca leaf', [_lin('#3c5c26'), _lin('#4a6c2c'), _lin('#587a34'), _lin('#68863e')], 0.12,
                                     age_col=_lin('#8a8a44'), burn_from=0.86, transl=0.3),
        'leaf_roebelenii': _leaf_material('palm leaf roebelenii', [_lin('#1f3a18'), _lin('#2a4a1e'), _lin('#365a24'), _lin('#446a2a')], 0.08,
                                          age_col=_lin('#7a7030'), burn_from=0.9, transl=0.3, rough=0.32, spec=0.5),
        'leaf_cycad': _leaf_material('palm leaf cycad', [_lin('#1c3416'), _lin('#24421b'), _lin('#2e5020')], 0.05,
                                     age_col=_lin('#6a6a2a'), burn_from=0.92, transl=0.2, rough=0.25, spec=0.6, gloss=0.3),
        'leaf_coconut': _leaf_material('coconut leaf', [lin(0.05, 0.09, 0.02), lin(0.08, 0.13, 0.03), lin(0.11, 0.15, 0.04), lin(0.15, 0.16, 0.05)], 0.25),
        'rachis': _plain('palm rachis', _lin('#5a6030'), 0.5, var=0.15, ramp_to=_lin('#7a8a3a')),
        'rachis_queen': _plain('palm rachis queen', _lin('#4a5a2a'), 0.5, var=0.15, ramp_to=_lin('#6a7a36')),
        'rachis_areca': _plain('areca petiole', _lin('#7e8248'), 0.45, var=0.15, ramp_to=_lin('#66763c')),
        'rachis_lipstick': _plain('palm petiole lipstick', _lin('#a8241a'), 0.35, var=0.12, coat=0.3, ramp_to=_lin('#6a5a24')),
        'rachis_roebelenii': _plain('palm rachis roebelenii', _lin('#4a5228'), 0.5, var=0.12),
        'rachis_cycad': _plain('palm rachis cycad', _lin('#3a4a22'), 0.45, var=0.1),
        'dead': _plain('palm dead frond', _lin('#6a5032'), 0.85, var=0.25),
        'deadleaf': _leaf_material('palm dead leaflets', [_lin('#5a4024'), _lin('#7a5a32'), _lin('#9a7a48'), _lin('#b09a68')], 0.0, transl=0.25, rough=0.8, spec=0.2,
                                   age_from=2.0, grade=None),
        'fruit': _fruit_material('palm fruit', [_lin('#5a6a1a'), _lin('#8a7a20'), _lin('#c47a1c'), _lin('#d8661a')]),
        'fruit_red': _fruit_material('palm fruit red', [_lin('#7a8a20'), _lin('#c8501a'), _lin('#b8281a'), _lin('#a01c16')]),
        'spathe': _plain('palm spathe', _lin('#6a5038'), 0.75, var=0.2, bump_scale=0.4, noise_scale=80, stretch=(1, 1, 8)),
        'boot': _boot_material('palm leaf base'),
        'shaft_foxtail': _plain('palm crownshaft foxtail', _lin('#5c7a2e'), 0.4, var=0.08, coat=0.2, ramp_to=_lin('#7a9038')),
        'shaft_christmas': _plain('palm crownshaft christmas', _lin('#7a9a48'), 0.4, var=0.08, coat=0.2, ramp_to=_lin('#8aa65a')),
        'shaft_lipstick': _plain('palm crownshaft lipstick', _lin('#b0352a'), 0.3, var=0.12, coat=0.35, ramp_to=_lin('#c8402c')),
        'shaft_areca': _plain('palm crownshaft areca', _lin('#848c64'), 0.5, var=0.1, ramp_to=_lin('#9a9c7c')),
        'trunk_queen': _trunk_material('palm trunk', (0.05, 0.048, 0.044, 1), (0.022, 0.021, 0.019, 1), (0.11, 0.11, 0.1, 1), 0.09,
                                       photo=photo, tint=(0.3, 0.295, 0.285), tile=(0.45, 0.9)),
        'trunk_foxtail': _trunk_material('palm trunk foxtail', (0.05, 0.048, 0.044, 1), (0.022, 0.021, 0.019, 1), (0.11, 0.11, 0.1, 1), 0.07,
                                         photo=photo, tint=(0.62, 0.62, 0.6), tile=(0.5, 1.2), ring_bump=0.3),
        'trunk_christmas': _trunk_material('palm trunk christmas', _lin('#8a8478'), _lin('#4a463e'), _lin('#a8a698'), 0.09, ring_bump=0.8),
        'trunk_lipstick': _trunk_material('palm stem lipstick', _lin('#7a6a3a'), _lin('#3a3018'), _lin('#8a7a40'), 0.11, ring_bump=0.9, rough=0.5, coat=0.2),
        'trunk_areca': _trunk_material('areca stem', _lin('#7a7c5e'), _lin('#64644c'), _lin('#8e8e76'), 0.1, ring_bump=0.3, rough=0.6),   # olive-grey, faint rings
        'trunk_roebelenii': _trunk_material('palm trunk roebelenii', _lin('#4a4034'), _lin('#2a241c'), _lin('#6a6252'), 0.05, ring_bump=1.0, knobs=0.8, rough=0.95),
        'trunk_cycad': _trunk_material('palm trunk cycad', _lin('#4a3e30'), _lin('#2a221a'), _lin('#5a5040'), 0.035, ring_bump=1.0, knobs=1.0, rough=0.95),
        'trunk_coconut': _trunk_material('coconut trunk', (0.075, 0.066, 0.055, 1), (0.035, 0.03, 0.025, 1), (0.13, 0.125, 0.11, 1), 0.09,
                                         photo=photo, tint=(0.72, 0.7, 0.68), tile=(0.65, 1.3)),
        'coconut': _plain('coconut fruit', (0.12, 0.13, 0.03, 1), 0.45, var=0.2),
    }


def _instancer(name, proto_col, P, rot, scale, idx, parent_col):
    """One object whose geometry nodes put proto_col's children at P (n,3) with euler rot (n,3),
    uniform scale (n,) and variant idx (n,): instances cost the path tracer next to nothing."""
    n = len(P)
    me = bpy.data.meshes.new(name + '-pts')
    me.vertices.add(n); me.vertices.foreach_set('co', np.asarray(P, np.float32).ravel())
    sc3 = np.repeat(np.asarray(scale, np.float32)[:, None], 3, 1)
    for an, typ, data in (('rot', 'FLOAT_VECTOR', np.asarray(rot, np.float32)), ('scl', 'FLOAT_VECTOR', sc3), ('idx', 'INT', np.asarray(idx, np.int32))):
        a = me.attributes.new(an, typ, 'POINT'); a.data.foreach_set('vector' if typ == 'FLOAT_VECTOR' else 'value', data.ravel())
    ob = bpy.data.objects.new(name, me); parent_col.objects.link(ob)
    ng = bpy.data.node_groups.new(name + '-gn', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    ci = N.new('GeometryNodeCollectionInfo'); ci.inputs['Collection'].default_value = proto_col
    ci.inputs['Separate Children'].default_value = True; ci.inputs['Reset Children'].default_value = True
    io = N.new('GeometryNodeInstanceOnPoints'); io.inputs['Pick Instance'].default_value = True
    na = {}
    for an, dt in (('rot', 'FLOAT_VECTOR'), ('scl', 'FLOAT_VECTOR'), ('idx', 'INT')):
        a = N.new('GeometryNodeInputNamedAttribute'); a.data_type = dt; a.inputs['Name'].default_value = an; na[an] = a
    e2r = N.new('FunctionNodeEulerToRotation'); L.new(na['rot'].outputs['Attribute'], e2r.inputs['Euler'])
    L.new(gi.outputs[0], io.inputs['Points']); L.new(ci.outputs['Instances'], io.inputs['Instance'])
    L.new(na['idx'].outputs['Attribute'], io.inputs['Instance Index']); L.new(e2r.outputs['Rotation'], io.inputs['Rotation'])
    L.new(na['scl'].outputs['Attribute'], io.inputs['Scale']); L.new(io.outputs['Instances'], go.inputs[0])
    ob.modifiers.new('instances', 'NODES').node_group = ng
    return ob


VARIANTS = {'queen': 7, 'foxtail': 5, 'christmas': 5, 'lipstick': 5, 'areca': 5, 'roebelenii': 4, 'cycad': 3, 'coconut': 4}
CLUMPING = ('areca', 'lipstick')        # young suckers at the foot of every cane


def _kind(p):
    k = p.get('kind', 'queen')
    return 'queen' if k in ('foxtail_legacy',) else k if k in KIND else 'queen'


def build(palms, b, variants=None, collection_name='palms'):
    """palms: [{kind, seed, base (three.js metres), height, trunkR, lean}]; b: three.js -> Blender.
    Trunks of a kind are merged into one mesh; crowns are a few variants per kind, instanced."""
    col = bpy.data.collections.new(collection_name); bpy.context.scene.collection.children.link(col)
    mats = materials()
    nvar = {k: (variants or v) for k, v in VARIANTS.items()}
    protos = {}
    kinds = sorted({_kind(p) for p in palms})
    for kind in kinds:
        pc = bpy.data.collections.new('v-' + kind + '-crowns')
        for i in range(nvar[kind]):
            pc.objects.link(bpy.data.objects.new(f'{kind}-crown-{i:02d}', crown_mesh(kind, 100 + i * 7 + len(kind), mats)[0]))
        protos[kind] = pc
    trunks, boots = {}, {}
    inst = {k: ([], [], [], []) for k in protos}
    used = {k: [] for k in protos}
    for p in palms:
        rng = random.Random(p['seed'])
        kind = _kind(p); K = KIND[kind]
        base = b(p['base'])
        h = max(p['height'], K['shaft'] + 0.2)
        r0 = K['rad'] * rng.uniform(0.9, 1.1) * (min(1.25, max(0.8, (h / K['href']) ** 0.3)))
        bend = (0.03 + rng.random() * 0.05) * min(p.get('lean', 1), 2.5) * {'queen': 0.5, 'coconut': 1.6, 'foxtail': 0.35, 'christmas': 0.8}.get(kind, 1.0)
        ldir = rng.uniform(0, 6.283)
        if kind == 'queen':
            # queen palms lean 3-5 deg; a pair grows apart (each leans away from its neighbour, toward the light)
            bend = math.tan(math.radians(rng.uniform(3.0, 5.0)))
            nb = [q for q in palms if q is not p and _kind(q) == 'queen' and q.get('house', 0) == p.get('house', 0)]
            nb = [(b(q['base']) - base) for q in nb]
            nb = [v for v in nb if 0.1 < v.length < 6.0]
            if nb:
                v = min(nb, key=lambda v: v.length); ldir = math.atan2(-v.y, -v.x) + rng.uniform(-0.3, 0.3)
        tb, sh, top, tdir = trunk_mesh(h, r0, ldir, bend, kind, p['seed'])
        trunks.setdefault(kind, MeshBuf()).extend(tb, off=np.array(base[:]))      # all trunks of a kind: one mesh
        if sh: boots.setdefault(kind, MeshBuf()).extend(sh, off=np.array(base[:]))
        q = Vector((0, 0, 1)).rotation_difference(tdir)
        q = q @ Quaternion((0, 0, 1), rng.uniform(0, 6.283))
        s = min(1.4, max(0.6, (h / K['href']) ** K['spow']))
        P, R, S, I = inst[kind]
        # never the same crown twice in a row among neighbours: pick the variant least used so far nearby
        near = [i for (pp, i) in used[kind] if (pp - base).length < 12]
        cand = [i for i in range(nvar[kind]) if i not in near] or list(range(nvar[kind]))
        vi = cand[rng.randrange(len(cand))]
        used[kind].append((base.copy(), vi))
        P.append(tuple(base + top)); R.append(tuple(q.to_euler('XYZ'))); S.append(s); I.append(vi)
        if kind in CLUMPING:
            # a young sucker or two at the foot of every cane: these palms grow as dense clumps
            for _ in range(rng.choice([1, 1, 2])):
                a_ = rng.uniform(0, 6.283); d_ = rng.uniform(0.15, 0.4)
                sb = base + Vector((math.cos(a_) * d_, math.sin(a_) * d_, -0.02)); hs = rng.uniform(0.3, 0.6)
                qs = Quaternion((0, 0, 1), rng.uniform(0, 6.283)); qs = Quaternion(Vector((math.cos(a_ + 1.57), math.sin(a_ + 1.57), 0)), rng.uniform(0.1, 0.35)) @ qs
                P.append(tuple(sb + Vector((0, 0, K['shaft'] * hs * 0.5)))); R.append(tuple(qs.to_euler('XYZ'))); S.append(hs); I.append(rng.randrange(nvar[kind]))
    for kind, (P, R, S, I) in inst.items():
        if P: _instancer('palms-' + kind, protos[kind], P, R, S, I, col)
    for kind, tb in trunks.items():
        col.objects.link(bpy.data.objects.new('trunks-' + kind, tb.mesh('trunks-' + kind, mats['trunk_' + kind])))
    for kind, bb in boots.items():
        col.objects.link(bpy.data.objects.new('boots-' + kind, bb.mesh('boots-' + kind, mats['boot'])))
    return col
