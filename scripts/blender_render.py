"""Path-traced renders of the exported Na Hiku scene with Blender Cycles.

    python3 scripts/blender_render.py blender/nahiku.glb blender/nahiku-meta.json out_dir \
        --views front back kitchen --samples 256 --res 1920x1080
    python3 scripts/blender_render.py ... --night --frames 0-383 --res 1920x1080

The scene comes from scripts/export.mjs (three.js -> glTF, metres). Here it gets what a real
renderer needs to look like a photograph: physical sky and sun, global illumination, glass and
water that refract, leaves that transmit light, filmic tone mapping.
"""
import argparse, json, math, os, sys
import bpy
from mathutils import Vector, Quaternion

ap = argparse.ArgumentParser()
ap.add_argument('glb'); ap.add_argument('meta'); ap.add_argument('out')
ap.add_argument('--views', nargs='*', default=[])
ap.add_argument('--night', action='store_true')
ap.add_argument('--frames', default='')
ap.add_argument('--step', type=int, default=1)
ap.add_argument('--samples', type=int, default=256)
ap.add_argument('--res', default='1920x1080')
ap.add_argument('--exposure', type=float, default=0.0)
ap.add_argument('--threads', type=int, default=0)
ap.add_argument('--plate', default='')          # timeline.json: render the 360 night plate for the film
ap.add_argument('--panos', default='')          # tour/panos.json: path-traced 360 panoramas for the tour
# sky and light (scripts/materials_bpy.py): a photographed HDRI sky + Sun lamp, or the procedural Nishita sky
ap.add_argument('--sky', default='hdri', choices=['hdri', 'procedural'])
ap.add_argument('--hdri', default='autumn_field_puresky')                   # any day sky in assets/manifest.json (clear, faint cirrus)
ap.add_argument('--clouds', default='kloofendal_48d_partly_cloudy_puresky')   # its cumulus laid low on the horizon over --hdri ('' = none)
ap.add_argument('--cloud-top', type=float, default=11.0)                    # clouds kept below this elevation (deg)
ap.add_argument('--cloud-yaw', type=float, default=0.0)                     # turn the cloud layer (deg) to place the cumulus
ap.add_argument('--cumulus-top', type=float, default=35.0)                  # trade-wind cumulus band up to this elevation (deg; <= cloud-top: off)
ap.add_argument('--cirrus', type=float, default=0.3)                        # light cirrus above ~15 deg (peak opacity, 0 = none)
ap.add_argument('--toe', type=float, default=0.007)                         # shadow toe lift: scene-linear value true black is raised to (0 = off)
ap.add_argument('--sky-strength', type=float, default=1.0)                  # x the HDRI's measured sky + sun
ap.add_argument('--sky-yaw', type=float, default=0.0)                       # turn the clouds (deg) away from the sun-matched angle
ap.add_argument('--hdri-res', type=int, default=0)                          # cap the HDRI width (e.g. 4096 for tests; 0 = full 8K)
ap.add_argument('--polarizer', type=float, default=0.12)                    # lens polariser on the visible sky, 0..1 (light: brochure sky is mid blue)
ap.add_argument('--interior-ev', type=float, default=2.3)                   # interiors exposed +EV over the exteriors
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
meta = json.load(open(args.meta))
os.makedirs(args.out, exist_ok=True)
W, H = map(int, args.res.split('x'))

# three.js world (y up) -> Blender world (z up), as the glTF importer converts it
def b(v): return Vector((v[0], -v[2], v[1]))
Q_UP = Quaternion((1, 0, 0), math.radians(90))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=args.glb)
scene = bpy.context.scene
# palms are exported as positions and sizes only; grow them leaf by leaf here (scripts/palms.py)
import palms
palms.build([p for p in meta.get('palms', []) if 'kind' in p], lambda v: Vector((v[0], -v[2], v[1])))
# beds, plumeria, background trees and the lawn: recorded as proxies too, grown leaf and blade here (scripts/plants_bpy.py)
try:
    import plants_bpy
    plants_bpy.build(meta, lambda v: Vector((v[0], -v[2], v[1])), log=lambda s: print(s, flush=True))
except Exception:
    import traceback; traceback.print_exc()

# ---------------------------------------------------------------- materials
# every finish rebuilt from the photo-scanned library in assets/ at real-world scale: siding, standing-seam
# roofs, coral stone, travertine, cedar, teak, white oak, linen, ...; glass and water refract, leaves
# transmit light, the ocean is a wind-roughened sea (scripts/materials_bpy.py)
import materials_bpy
materials_bpy.apply(meta=meta, night=args.night, log=lambda s: print(s, flush=True))
import water_bpy; water_bpy.apply(meta=meta, night=args.night, log=lambda s: print(s, flush=True))   # pool, spa, falls (scripts/water_bpy.py)

# ---------------------------------------------------------------- world and light
# day: a photographed sky (assets/hdri, its sun painted out) lights the scene and is the background, turned
# so its sun sits where each view's Sun lamp is; the lamp carries the measured direct irradiance with the
# colour of sunlight at that elevation. Night / plate build on the procedural sky (its strength is set to 0).
S = materials_bpy.World(scene, mode='procedural' if (args.night or args.plate) else args.sky, hdri=args.hdri,
                        strength=args.sky_strength, yaw=args.sky_yaw, max_res=args.hdri_res,
                        polarizer=args.polarizer, log=lambda s: print(s, flush=True),
                        clouds=args.clouds, cloud_top=args.cloud_top, cloud_yaw=args.cloud_yaw,
                        cumulus_top=args.cumulus_top, cirrus=args.cirrus)
nt, bg, camsky, sky, sun, sun_data = S.nt, S.bg, S.camsky, S.sky, S.sun, S.sun_data
set_sun = S.set_sun
if not args.night: S.auto_exposure(meta, args.exposure, args.interior_ev, only=args.views)   # interiors metered +EV, white-balanced

# ---------------------------------------------------------------- render settings
r = scene.render
r.engine = 'CYCLES'; r.resolution_x = W; r.resolution_y = H; r.resolution_percentage = 100
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGBA' if args.night else 'RGB'
if args.threads: r.threads_mode = 'FIXED'; r.threads = args.threads
c = scene.cycles
c.device = 'CPU'; c.samples = args.samples; c.use_adaptive_sampling = True; c.adaptive_threshold = 0.015
c.use_denoising = True
try: c.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
# diffuse 7 / transmission 10: light reaches the shade under dense planting through leaves and bounces
# (critique-preview2-front #6: 2% of the frame was pure black there)
c.max_bounces = 12; c.diffuse_bounces = 7; c.glossy_bounces = 5; c.transmission_bounces = 10; c.transparent_max_bounces = 24
c.caustics_reflective = False; c.caustics_refractive = False
c.sample_clamp_indirect = 8.0
c.blur_glossy = 1.0
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = args.exposure
if args.toe > 0 and not args.night:
    # a slight toe lift, as a photo's shadows keep detail (critique-preview2-front #6): Blender applies the view
    # curve in scene-linear after exposure, before AgX, so a curve that adds `toe` at black and fades out by 0.12
    # lifts true black to ~13 sRGB (0.003 -> ~17) and leaves mid-tones and highlights exactly as they were
    try:
        vs = scene.view_settings; vs.use_curve_mapping = True
        cm = vs.curve_mapping; cm.extend = 'EXTRAPOLATED'
        cv = cm.curves[3]
        while len(cv.points) > 2: cv.points.remove(cv.points[1])
        cv.points[0].location = (0.0, args.toe); cv.points[-1].location = (1.0, 1.0)
        for x, y in ((0.012, 0.012 + args.toe * 0.55), (0.04, 0.04 + args.toe * 0.12), (0.12, 0.12)): cv.points.new(x, y)
        for pt in cv.points: pt.handle_type = 'AUTO_CLAMPED'
        cm.update()
    except Exception as e: print('toe lift failed', e, flush=True)

cam_data = bpy.data.cameras.new('cam'); cam_data.sensor_fit = 'VERTICAL'; cam_data.clip_start = 0.05; cam_data.clip_end = 20000
cam = bpy.data.objects.new('cam', cam_data); scene.collection.objects.link(cam); scene.camera = cam
cam.rotation_mode = 'QUATERNION'

def aim(pos, target, fov, shift_y=0.0):
    cam.location = b(pos)
    cam.rotation_quaternion = (b(target) - b(pos)).to_track_quat('-Z', 'Y')
    cam_data.angle_y = math.radians(fov)
    cam_data.shift_y = shift_y          # lens shift: a level camera framed lower, verticals stay plumb (architectural view)

# ---------------------------------------------------------------- 360 panoramas for the tour
if args.panos:
    bg.inputs['Strength'].default_value = 0.28; camsky.inputs['Strength'].default_value = 0.28
    spec = json.load(open(args.panos))
    set_sun(spec['sunDir'])
    cam_data.type = 'PANO'
    try: cam_data.panorama_type = 'EQUIRECTANGULAR'
    except Exception: cam_data.cycles.panorama_type = 'EQUIRECTANGULAR'
    cam.rotation_mode = 'XYZ'; cam.rotation_euler = (math.radians(90), 0, 0)   # centre = three.js -Z, right = +X
    for p in spec['panos']:
        if args.views and p['id'] not in args.views: continue
        cam.location = b([v * 0.3048 for v in p['pos']])
        c.samples = args.samples if p.get('interior', True) else max(96, args.samples // 2)
        r.filepath = os.path.join(args.out, f"{p['id']}.jpg"); r.image_settings.file_format = 'JPEG'; r.image_settings.quality = 92
        bpy.ops.render.render(write_still=True)
        print('rendered pano', p['id'], flush=True)
    sys.exit(0)

# ---------------------------------------------------------------- day stills
if not args.night:
    sky_strength = 0.28
    bg.inputs['Strength'].default_value = sky_strength
    camsky.inputs['Strength'].default_value = sky_strength
    for vid in args.views or list(meta['views'].keys()):
        v = meta['views'][vid]
        set_sun(v['sunDir'])
        if not v.get('interior') and hasattr(S, 'aim_clouds'): S.aim_clouds(v['pos'], v['target'], v['fov'], W / H)
        aim(v['pos'], v['target'], v['fov'], v.get('shiftY', 0.0))
        # interiors need more paths; exteriors converge fast
        c.samples = args.samples if v.get('interior') else max(64, args.samples // 2)
        r.filepath = os.path.join(args.out, f'{vid}.png')
        bpy.ops.render.render(write_still=True)
        print('rendered', vid, flush=True)
    sys.exit(0)

# ---------------------------------------------------------------- night
r.film_transparent = True                       # stars are composited behind (scripts/composite_night.py)
bg.inputs['Strength'].default_value = 0.0
sun_data.energy = 0.0
moon = bpy.data.lights.new('moon', 'SUN'); moon.energy = 0.02; moon.color = (0.62, 0.72, 0.95); moon.angle = math.radians(0.5)
mo = bpy.data.objects.new('moon', moon); scene.collection.objects.link(mo); mo.rotation_euler = (math.radians(55), 0, math.radians(150))
amb = nt.nodes.new('ShaderNodeBackground'); amb.inputs['Color'].default_value = (0.012, 0.018, 0.035, 1); amb.inputs['Strength'].default_value = 1.0
nt.links.new(amb.outputs['Background'], next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD').inputs['Surface'])

def point(pos, watts, color, radius=0.08, kind='POINT'):
    L = bpy.data.lights.new('l', kind); L.energy = watts; L.color = color
    if kind == 'POINT': L.shadow_soft_size = radius
    o = bpy.data.objects.new('l', L); scene.collection.objects.link(o); o.location = b(pos); return o

for l in meta['lamps']: point(l['pos'], 60, (1.0, 0.72, 0.45), 0.12)
for rm in meta['rooms']:
    x0, y0, x1, y1 = rm['rect']; area = (x1 - x0) * (y1 - y0)
    if area < 4: continue
    L = bpy.data.lights.new('room', 'AREA'); L.shape = 'RECTANGLE'; L.size = (x1 - x0) * 0.5; L.size_y = (y1 - y0) * 0.5
    L.energy = min(900, area * 22) * (0.5 if rm['outdoor'] else 1.0); L.color = (1.0, 0.76, 0.5)
    o = bpy.data.objects.new('room', L); scene.collection.objects.link(o)
    o.location = b([(x0 + x1) / 2, rm['ceiling'] - 0.15, (y0 + y1) / 2])          # facing down by default
if meta.get('pool'):
    x0, y0, x1, y1 = [v * 0.3048 for v in meta['pool']['rect']]
    for t in (0.25, 0.75):
        L = bpy.data.lights.new('pool', 'AREA'); L.size = 0.4; L.energy = 120; L.color = (0.35, 0.85, 1.0)
        o = bpy.data.objects.new('pool', L); scene.collection.objects.link(o)
        o.location = b([(x0 + x1) / 2, -0.6 * 0.3048 - 1.0, y0 + (y1 - y0) * t]); o.rotation_euler = (math.radians(180), 0, 0)
        o.rotation_euler = (0, 0, 0)      # area lights face -Z; flip to face up
        o.rotation_euler = (math.pi, 0, 0)
for pm in [p for p in meta.get('palms', []) if p.get('house', 0) == 0 and p.get('kind', 'foxtail') == 'foxtail'][:8]:
    L = bpy.data.lights.new('up', 'SPOT'); L.energy = 400; L.color = (1.0, 0.8, 0.55); L.spot_size = math.radians(30); L.spot_blend = 0.6
    o = bpy.data.objects.new('up', L); scene.collection.objects.link(o)
    bx, by, bz = pm['base']; o.location = b([bx + 0.45, by + 0.1, bz + 0.45]); o.rotation_euler = (0, 0, 0)   # spot points down -Z; aim up:
    o.rotation_euler = (math.pi, 0, 0)

if args.plate:
    # equirectangular camera, world-aligned: image centre = Blender +Y (three.js -Z), right = +X, up = +Z
    tl = json.load(open(args.plate))
    cam_data.type = 'PANO'
    try: cam_data.panorama_type = 'EQUIRECTANGULAR'
    except Exception: cam_data.cycles.panorama_type = 'EQUIRECTANGULAR'
    cam.rotation_mode = 'XYZ'; cam.rotation_euler = (math.radians(90), 0, 0)
    cam.location = b(tl['pos'])
    r.resolution_x, r.resolution_y = W, H
    lon0, lon1 = [v + math.pi / 2 for v in tl['yawRange']]          # three.js yaw -> equirect longitude
    lat0, lat1 = tl['pitchRange']
    r.use_border = True; r.use_crop_to_border = True
    r.border_min_x = 0.5 + lon0 / (2 * math.pi); r.border_max_x = 0.5 + lon1 / (2 * math.pi)
    r.border_min_y = 0.5 + lat0 / math.pi; r.border_max_y = 0.5 + lat1 / math.pi
    r.filepath = os.path.join(args.out, 'plate.png')
    json.dump(dict(W=W, H=H, x0=int(round(r.border_min_x * W)), y0=int(round((1 - r.border_max_y) * H)), lon0=lon0, lon1=lon1, lat0=lat0, lat1=lat1),
              open(os.path.join(args.out, 'plate.json'), 'w'))
    bpy.ops.render.render(write_still=True)
    print('rendered plate', flush=True)
    sys.exit(0)

frames = meta['night']['frames']
a, z = (map(int, args.frames.split('-')) if args.frames else (0, len(frames) - 1))
cam_data.angle_y = math.radians(meta['night']['fov'])
for i in range(a, z + 1, args.step):
    f = frames[i]
    cam.location = b(f['pos'])
    qx, qy, qz, qw = f['quat']
    cam.rotation_quaternion = Q_UP @ Quaternion((qw, qx, qy, qz))
    r.filepath = os.path.join(args.out, f'n{i:05d}.png')
    bpy.ops.render.render(write_still=True)
    print('rendered frame', i, flush=True)
