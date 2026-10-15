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

# ---------------------------------------------------------------- materials
def principled(m):
    if not m.node_tree: return None
    return next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)

def base_link(m, p):
    l = p.inputs['Base Color'].links
    return l[0].from_socket if l else None

for m in bpy.data.materials:
    p = principled(m)
    if not p: continue
    name = m.name.lower()
    if name.startswith('glass'):
        p.inputs['Transmission Weight'].default_value = 1.0
        p.inputs['Roughness'].default_value = 0.0
        p.inputs['IOR'].default_value = 1.5
        p.inputs['Alpha'].default_value = 1.0
        for l in list(p.inputs['Alpha'].links): m.node_tree.links.remove(l)
        p.inputs['Thin Wall'].default_value = True
        p.inputs['Base Color'].default_value = (0.92, 0.96, 0.96, 1)
    elif name.startswith('water'):
        p.inputs['Transmission Weight'].default_value = 1.0
        p.inputs['Roughness'].default_value = 0.02
        p.inputs['IOR'].default_value = 1.33
        p.inputs['Alpha'].default_value = 1.0
        for l in list(p.inputs['Alpha'].links): m.node_tree.links.remove(l)
        p.inputs['Base Color'].default_value = (0.62, 0.9, 0.93, 1)
    elif name.startswith('mirror'):
        p.inputs['Metallic'].default_value = 1.0; p.inputs['Roughness'].default_value = 0.0
    elif name.startswith('roof') or name.startswith('fascia'):
        src = base_link(m, p)
        if src:   # darken the standing-seam grey toward the renderings' charcoal
            mul = m.node_tree.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1.0
            mul.inputs[7].default_value = (0.62, 0.64, 0.66, 1)
            m.node_tree.links.new(src, mul.inputs[6]); m.node_tree.links.new(mul.outputs[2], p.inputs['Base Color'])
        else:
            col = p.inputs['Base Color'].default_value; p.inputs['Base Color'].default_value = (col[0] * 0.62, col[1] * 0.64, col[2] * 0.66, 1)
        p.inputs['Metallic'].default_value = 0.12; p.inputs['Roughness'].default_value = 0.5
    elif name.startswith('trunk'):
        src = base_link(m, p)
        if src:
            mul = m.node_tree.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1.0
            mul.inputs[7].default_value = (0.55, 0.53, 0.5, 1)
            m.node_tree.links.new(src, mul.inputs[6]); m.node_tree.links.new(mul.outputs[2], p.inputs['Base Color'])
    elif name.startswith('ocean'):
        # deep Pacific blue; wind chop tilts the facets so they mirror the bluer sky above the haze
        nt_ = m.node_tree
        for l in list(p.inputs['Base Color'].links): nt_.links.remove(l)
        p.inputs['Base Color'].default_value = (0.006, 0.035, 0.09, 1)
        p.inputs['Roughness'].default_value = 0.14; p.inputs['Metallic'].default_value = 0.0
        geo_ = nt_.nodes.new('ShaderNodeNewGeometry')
        chop = nt_.nodes.new('ShaderNodeTexNoise'); chop.inputs['Scale'].default_value = 0.35; chop.inputs['Detail'].default_value = 6
        nt_.links.new(geo_.outputs['Position'], chop.inputs['Vector'])
        bump_ = nt_.nodes.new('ShaderNodeBump'); bump_.inputs['Strength'].default_value = 0.35; bump_.inputs['Distance'].default_value = 0.4
        nt_.links.new(chop.outputs['Fac'], bump_.inputs['Height']); nt_.links.new(bump_.outputs['Normal'], p.inputs['Normal'])
    elif name.startswith('glow'):
        p.inputs['Emission Color'].default_value = (1.0, 0.78, 0.52, 1)
        p.inputs['Emission Strength'].default_value = 25.0 if args.night else 0.0
    # leaves and fronds: let light through (thin-leaf translucency), as real foliage does
    if name.startswith('foliage') or name in ('solid #3d5f2c', 'solid #2f5a2a', 'solid #3d6a2c', 'solid #2c5527'):
        nt = m.node_tree
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
        src = base_link(m, p)
        if src: nt.links.new(src, tr.inputs['Color'])
        else: tr.inputs['Color'].default_value = p.inputs['Base Color'].default_value
        mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs['Fac'].default_value = 0.32
        # keep the alpha cut-out: the importer drives Principled alpha; wrap translucency with it
        nt.links.new(p.outputs['BSDF'], mix.inputs[1]); nt.links.new(tr.outputs['BSDF'], mix.inputs[2])
        alpha_src = p.inputs['Alpha'].links[0].from_socket if p.inputs['Alpha'].links else None
        if alpha_src:
            tp = nt.nodes.new('ShaderNodeBsdfTransparent'); mix2 = nt.nodes.new('ShaderNodeMixShader')
            nt.links.new(alpha_src, mix2.inputs['Fac']); nt.links.new(tp.outputs['BSDF'], mix2.inputs[1]); nt.links.new(mix.outputs['Shader'], mix2.inputs[2])
            nt.links.new(mix2.outputs['Shader'], out.inputs['Surface'])
        else:
            nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
        p.inputs['Roughness'].default_value = 0.55
        p.inputs['Specular IOR Level'].default_value = 0.35

for o in bpy.data.objects:
    if o.type != 'MESH' or not o.data.materials: continue
    names = [m.name.lower() for m in o.data.materials if m]
    if names and all(n.startswith(('glass', 'water')) for n in names):
        o.visible_shadow = False

# ---------------------------------------------------------------- world and light
world = bpy.data.worlds.new('sky'); scene.world = world
nt = world.node_tree if world.node_tree else None
if nt is None:
    world.use_nodes = True; nt = world.node_tree
for n in list(nt.nodes):
    if n.type not in ('OUTPUT_WORLD',): nt.nodes.remove(n)
bg = nt.nodes.new('ShaderNodeBackground')
nt.links.new(bg.outputs['Background'], next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD').inputs['Surface'])
sky = nt.nodes.new('ShaderNodeTexSky')
sky.sky_type = 'MULTIPLE_SCATTERING'
sky.sun_disc = False
sky.altitude = 60.0
sky.air_density = 1.0; sky.aerosol_density = 0.35; sky.ozone_density = 1.2
nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
def camera_sky():
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    zc = nt.nodes.new('ShaderNodeMath'); zc.operation = 'MAXIMUM'; zc.inputs[1].default_value = 0.02; nt.links.new(sep.outputs['Z'], zc.inputs[0])
    den = nt.nodes.new('ShaderNodeMath'); den.operation = 'ADD'; den.inputs[1].default_value = 0.12; nt.links.new(zc.outputs[0], den.inputs[0])
    px = nt.nodes.new('ShaderNodeMath'); px.operation = 'DIVIDE'; nt.links.new(sep.outputs['X'], px.inputs[0]); nt.links.new(den.outputs[0], px.inputs[1])
    py = nt.nodes.new('ShaderNodeMath'); py.operation = 'DIVIDE'; nt.links.new(sep.outputs['Y'], py.inputs[0]); nt.links.new(den.outputs[0], py.inputs[1])
    comb = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(px.outputs[0], comb.inputs['X']); nt.links.new(py.outputs[0], comb.inputs['Y'])
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 1.1; noise.inputs['Detail'].default_value = 10; noise.inputs['Roughness'].default_value = 0.62
    nt.links.new(comb.outputs[0], noise.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.56; ramp.color_ramp.elements[1].position = 0.74
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    band = nt.nodes.new('ShaderNodeMapRange'); band.inputs['From Min'].default_value = 0.42; band.inputs['From Max'].default_value = 0.08
    nt.links.new(sep.outputs['Z'], band.inputs['Value'])
    lowcut = nt.nodes.new('ShaderNodeMapRange'); lowcut.inputs['From Min'].default_value = 0.0; lowcut.inputs['From Max'].default_value = 0.035
    nt.links.new(sep.outputs['Z'], lowcut.inputs['Value'])
    m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; nt.links.new(ramp.outputs['Color'], m1.inputs[0]); nt.links.new(band.outputs['Result'], m1.inputs[1])
    m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; nt.links.new(m1.outputs[0], m2.inputs[0]); nt.links.new(lowcut.outputs['Result'], m2.inputs[1])
    hs = nt.nodes.new('ShaderNodeHueSaturation'); hs.inputs['Saturation'].default_value = 1.55; hs.inputs['Value'].default_value = 0.92
    nt.links.new(sky.outputs['Color'], hs.inputs['Color'])
    white = nt.nodes.new('ShaderNodeMix'); white.data_type = 'RGBA'; white.inputs[7].default_value = (2.4, 2.45, 2.5, 1)
    nt.links.new(m2.outputs[0], white.inputs['Factor']); nt.links.new(hs.outputs['Color'], white.inputs[6])
    camsky = nt.nodes.new('ShaderNodeBackground'); nt.links.new(white.outputs[2], camsky.inputs['Color'])
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(bg.outputs['Background'], mix.inputs[1]); nt.links.new(camsky.outputs['Background'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD').inputs['Surface'])
    return camsky
camsky = camera_sky()

sun_data = bpy.data.lights.new('sun', 'SUN'); sun_data.energy = 4.2; sun_data.angle = math.radians(0.6)
sun_data.color = (1.0, 0.93, 0.84)
sun = bpy.data.objects.new('sun', sun_data); scene.collection.objects.link(sun)

def set_sun(d3):
    d = b(d3).normalized()
    sun.rotation_mode = 'QUATERNION'
    sun.rotation_quaternion = (-d).to_track_quat('-Z', 'Y')
    sky.sun_elevation = math.asin(max(-1, min(1, d.z)))
    sky.sun_rotation = math.atan2(d.x, -d.y)

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
c.max_bounces = 10; c.diffuse_bounces = 5; c.glossy_bounces = 5; c.transmission_bounces = 10; c.transparent_max_bounces = 24
c.caustics_reflective = False; c.caustics_refractive = False
c.sample_clamp_indirect = 8.0
c.blur_glossy = 1.0
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = args.exposure

cam_data = bpy.data.cameras.new('cam'); cam_data.sensor_fit = 'VERTICAL'; cam_data.clip_start = 0.05; cam_data.clip_end = 20000
cam = bpy.data.objects.new('cam', cam_data); scene.collection.objects.link(cam); scene.camera = cam
cam.rotation_mode = 'QUATERNION'

def aim(pos, target, fov):
    cam.location = b(pos)
    cam.rotation_quaternion = (b(target) - b(pos)).to_track_quat('-Z', 'Y')
    cam_data.angle_y = math.radians(fov)

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
        aim(v['pos'], v['target'], v['fov'])
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
