"""Photo-real materials and real-sky light for the Cycles renders (called by scripts/blender_render.py).

    import materials_bpy as MB
    MB.apply(meta=meta, night=False)           # every glTF material (named in src/materials.js) -> photo PBR
    sky = MB.World(scene, mode='hdri')         # photographed sky (assets/hdri) + Sun lamp; mode='procedural'
    sky.set_sun(view['sunDir'])                #   falls back to the Nishita sky with painted clouds

Every surface is rebuilt from the photo-scanned textures in assets/ (manifest.json): colour, roughness
and height maps projected in WORLD metres at their real tile size (the exporter's UVs are in feet, or
0..1 per box face, so they are not used except to read the layouts the three.js textures paint, e.g. the
stepping stones and hex pavers). Colours are re-balanced to the references (ref/front.png, back.png,
board-7.png): the photo keeps its structure, its mean is moved to the target colour. On top: per-board /
per-slab / per-panel colour scatter, large-scale mottling so tiles never repeat visibly, dirt in corners
and at wall bases (ambient-occlusion grime), weathering streaks on the roofs.
"""
import base64, json, math, os, tempfile
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')
FT = 0.3048
DEFAULT_HDRI = 'kloofendal_48d_partly_cloudy_puresky'
PROC_STRENGTH = 0.28            # blender_render.py sets the world strength to this (Nishita-sky calibration)

_manifest = None
def manifest():
    global _manifest
    if _manifest is None:
        try: _manifest = {e['name']: e for e in json.load(open(os.path.join(ASSETS, 'manifest.json')))}
        except Exception: _manifest = {}
    return _manifest

def srgb2lin(c):
    c = max(0.0, c)
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def lin(hexstr_or_tuple):
    """'#rrggbb' or sRGB (0..1) tuple -> linear RGBA tuple."""
    if isinstance(hexstr_or_tuple, str):
        h = hexstr_or_tuple.lstrip('#'); t = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    else: t = list(hexstr_or_tuple)
    return (srgb2lin(t[0]), srgb2lin(t[1]), srgb2lin(t[2]), 1.0)

def lin2hex(c):
    f = lambda v: max(0, min(255, round(255 * (v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055))))
    return '#%02x%02x%02x' % (f(c[0]), f(c[1]), f(c[2]))

# ------------------------------------------------------------------------------------------ images
_img_cache = {}
def image(asset, key='color'):
    """Load assets/textures/<cat>/<asset>/<key>.* (cached). Colour maps sRGB, data maps Non-Color."""
    e = manifest().get(asset)
    if not e: return None
    rel = e['files'].get(key)
    if not rel: return None
    path = os.path.join(ASSETS, rel)
    if path in _img_cache: return _img_cache[path]
    if not os.path.exists(path): return None
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'sRGB' if key.startswith('color') else 'Non-Color'
    _img_cache[path] = img
    return img

def mean_albedo(asset, key='color'):
    """Mean linear albedo of a texture (manifest value for the stock colour map, measured otherwise)."""
    e = manifest().get(asset, {})
    if key == 'color' and e.get('mean_albedo_srgb'):
        return lin(tuple(e['mean_albedo_srgb']))[:3]
    img = image(asset, key)
    if img is None: return (0.5, 0.5, 0.5)
    try:
        import numpy as np
        px = np.empty(len(img.pixels), dtype=np.float32); img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)[::97, :3]
        if not img.is_float:                                  # byte images: pixels are the sRGB code values
            px = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
        return tuple(float(v) for v in px.mean(0))
    except Exception:
        return (0.5, 0.5, 0.5)


# ------------------------------------------------------------------------------------------ node graph helper
class G:
    """Minimal builder over a node tree; every method returns an output socket (or node)."""
    def __init__(self, tree):
        self.t = tree; self.N = tree.nodes; self.L = tree.links
        self._geo = self._tc = None

    def node(self, kind, **props):
        n = self.N.new(kind)
        for k, v in props.items(): setattr(n, k, v)
        return n

    def put(self, sock, v):
        if v is None: return
        if isinstance(v, bpy.types.NodeSocket): self.L.new(v, sock)
        elif isinstance(v, bpy.types.Node): self.L.new(v.outputs[0], sock)
        else:
            dv = sock.default_value
            if hasattr(dv, '__len__') and not hasattr(v, '__len__'): v = [v] * len(dv)
            if hasattr(dv, '__len__') and len(dv) == 4 and len(v) == 3: v = (*v, 1.0)
            sock.default_value = v

    # --- inputs
    def geo(self):
        if self._geo is None: self._geo = self.node('ShaderNodeNewGeometry')
        return self._geo
    def P(self): return self.geo().outputs['Position']
    def Nrm(self): return self.geo().outputs['True Normal']
    def Nsh(self): return self.geo().outputs['Normal']
    def texco(self):
        if self._tc is None: self._tc = self.node('ShaderNodeTexCoord')
        return self._tc
    def obj_attr(self, name):
        a = self.node('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name=name)
        return a.outputs['Fac']
    def attr(self, name, out='Color'):
        a = self.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name)
        return a.outputs[out]
    def obj_random(self):
        return self.node('ShaderNodeObjectInfo').outputs['Random']

    # --- maths
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.put(n.inputs[0], a)
        if b is not None: self.put(n.inputs[1], b)
        if c is not None: self.put(n.inputs[2], c)
        return n.outputs[0]
    def add(self, a, b): return self.math('ADD', a, b)
    def sub(self, a, b): return self.math('SUBTRACT', a, b)
    def mul(self, a, b): return self.math('MULTIPLY', a, b)
    def vmath(self, op, a, b=None, scale=None, out=0):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.put(n.inputs[0], a)
        if b is not None: self.put(n.inputs[1], b)
        if scale is not None: self.put(n.inputs[3], scale)
        return n.outputs[out]
    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ'); self.put(n.inputs[0], v)
        return n.outputs['X'], n.outputs['Y'], n.outputs['Z']
    def comb(self, x=0.0, y=0.0, z=0.0):
        n = self.node('ShaderNodeCombineXYZ')
        self.put(n.inputs['X'], x); self.put(n.inputs['Y'], y); self.put(n.inputs['Z'], z)
        return n.outputs[0]
    def maprange(self, v, a, b, c=0.0, d=1.0, smooth=False, clamp=True):
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP' if smooth else 'LINEAR', clamp=clamp)
        self.put(n.inputs['Value'], v); self.put(n.inputs[1], a); self.put(n.inputs[2], b); self.put(n.inputs[3], c); self.put(n.inputs[4], d)
        return n.outputs['Result']
    def mix(self, fac, a, b, blend='MIX', clamp=False):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_result=clamp)
        self.put(n.inputs[0], fac); self.put(n.inputs[6], a); self.put(n.inputs[7], b)
        return n.outputs[2]
    def mixf(self, fac, a, b):
        n = self.node('ShaderNodeMix', data_type='FLOAT')
        self.put(n.inputs[0], fac); self.put(n.inputs[2], a); self.put(n.inputs[3], b)
        return n.outputs[0]
    def hsv(self, col, h=0.5, s=1.0, v=1.0):
        n = self.node('ShaderNodeHueSaturation')
        self.put(n.inputs['Hue'], h); self.put(n.inputs['Saturation'], s); self.put(n.inputs['Value'], v); self.put(n.inputs['Color'], col)
        return n.outputs[0]
    def gamma(self, col, g):
        n = self.node('ShaderNodeGamma'); self.put(n.inputs[0], col); self.put(n.inputs[1], g)
        return n.outputs[0]
    def bw(self, col):
        n = self.node('ShaderNodeRGBToBW'); self.put(n.inputs[0], col)
        return n.outputs[0]
    def noise(self, vec, scale=1.0, detail=2.0, rough=0.5, dims='3D', out='Fac', distortion=0.0):
        n = self.node('ShaderNodeTexNoise', noise_dimensions=dims)
        self.put(n.inputs['Vector'], vec); self.put(n.inputs['Scale'], scale); self.put(n.inputs['Detail'], detail)
        self.put(n.inputs['Roughness'], rough); self.put(n.inputs['Distortion'], distortion)
        return n.outputs[out]
    def white(self, vec, out='Value'):
        n = self.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D'); self.put(n.inputs['Vector'], vec)
        return n.outputs[out]
    def voronoi(self, vec, scale=1.0, out='Distance', feature='F1', randomness=1.0):
        n = self.node('ShaderNodeTexVoronoi', feature=feature)
        self.put(n.inputs['Vector'], vec); self.put(n.inputs['Scale'], scale); self.put(n.inputs['Randomness'], randomness)
        return n.outputs[out]
    def tex(self, img, vec, interp='Linear', ext='REPEAT'):
        n = self.node('ShaderNodeTexImage', interpolation=interp, extension=ext)
        n.image = img; self.put(n.inputs['Vector'], vec)
        return n
    def ao(self, distance=0.4, samples=4, only_local=False):
        n = self.node('ShaderNodeAmbientOcclusion', samples=samples, only_local=only_local)
        self.put(n.inputs['Distance'], distance)
        return n.outputs['AO']
    def bump(self, height, strength=1.0, distance=1.0, normal=None):
        n = self.node('ShaderNodeBump')
        self.put(n.inputs['Height'], height); self.put(n.inputs['Strength'], strength); self.put(n.inputs['Distance'], distance)
        if normal is not None: self.put(n.inputs['Normal'], normal)
        return n.outputs[0]
    def smoothstep(self, e0, e1, x): return self.maprange(x, e0, e1, 0.0, 1.0, smooth=True)


# ------------------------------------------------------------------------------------------ projections
def axis_masks(g):
    """1/0 masks for the dominant axis of the world normal (hard box projection, one texture lookup)."""
    nx, ny, nz = g.sep(g.vmath('ABSOLUTE', g.Nrm()))
    mx = g.mul(g.math('GREATER_THAN', nx, ny), g.math('GREATER_THAN', nx, nz))
    my = g.mul(g.math('GREATER_THAN', ny, nx), g.math('GREATER_THAN', ny, nz))
    mz = g.sub(g.sub(1.0, mx), my)
    return mx, my, mz

def box_uv(g, su, sv, rot=0.0, off=(0.0, 0.0), P=None, masks=None):
    """Planar-per-face projection in world metres: walls get u = along the wall, v = height; floors and
    roofs get (x, y) rotated by rot (radians). One tile = su x sv metres."""
    P = P or g.P()
    px, py, pz = g.sep(P)
    mx, my, mz = masks or axis_masks(g)
    c, s = math.cos(rot), math.sin(rot)
    tu = g.add(g.mul(px, c), g.mul(py, -s)); tv = g.add(g.mul(px, s), g.mul(py, c))
    u = g.add(g.add(g.mul(mx, py), g.mul(my, px)), g.mul(mz, tu))
    v = g.add(g.mul(g.add(mx, my), pz), g.mul(mz, tv))
    return g.comb(g.add(g.math('DIVIDE', u, su), off[0]), g.add(g.math('DIVIDE', v, sv), off[1]), 0.0)

def grain_uv(g, su, sv, axis_attr='nh_axis', grain='V', off=(0.0, 0.0)):
    """Wood: the image's grain runs along the member's long axis (object property nh_axis: 0=x 1=y 2=z,
    set by apply()); end grain faces fall back to plain box projection."""
    ax = g.obj_attr(axis_attr)
    a = g.comb(g.math('COMPARE', ax, 0.0, 0.1), g.math('COMPARE', ax, 1.0, 0.1), g.math('COMPARE', ax, 2.0, 0.1))
    n = g.Nrm(); P = g.P()
    along = g.vmath('DOT_PRODUCT', P, a, out=1)
    across_dir = g.vmath('NORMALIZE', g.vmath('CROSS_PRODUCT', n, a))
    across = g.vmath('DOT_PRODUCT', P, across_dir, out=1)
    side = g.math('LESS_THAN', g.math('ABSOLUTE', g.vmath('DOT_PRODUCT', n, a, out=1)), 0.7)
    gu, gv = (across, along) if grain == 'V' else (along, across)
    gs_u, gs_v = (su, sv) if grain == 'V' else (su, sv)
    side_uv = g.comb(g.add(g.math('DIVIDE', gu, gs_u), off[0]), g.add(g.math('DIVIDE', gv, gs_v), off[1]), 0.0)
    end_uv = box_uv(g, su, sv, off=off)
    n2 = g.node('ShaderNodeMix', data_type='VECTOR'); g.put(n2.inputs[0], side); g.put(n2.inputs[4], end_uv); g.put(n2.inputs[5], side_uv)
    return n2.outputs[1]

def slope_frame(g, fallback=(1.0, 0.0)):
    """For roofs / ceilings: t = metres along the eave (across the fall line), s = metres down the slope."""
    nx, ny, nz = g.sep(g.Nrm())
    hl = g.math('SQRT', g.add(g.mul(nx, nx), g.mul(ny, ny)))
    flat = g.math('LESS_THAN', hl, 0.08)
    inv = g.math('DIVIDE', 1.0, g.math('MAXIMUM', hl, 1e-4))
    dx = g.mixf(flat, g.mul(nx, inv), fallback[0]); dy = g.mixf(flat, g.mul(ny, inv), fallback[1])
    px, py, pz = g.sep(g.P())
    t = g.add(g.mul(px, g.math('MULTIPLY', dy, -1.0)), g.mul(py, dx))
    s = g.add(g.mul(px, dx), g.mul(py, dy))
    return t, s


# ------------------------------------------------------------------------------------------ material shell
def fresh(m):
    """Clear a material to Principled + Output; returns (G, principled, output)."""
    nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    g = G(nt)
    out = g.node('ShaderNodeOutputMaterial'); p = g.node('ShaderNodeBsdfPrincipled')
    g.L.new(p.outputs[0], out.inputs['Surface'])
    try: m.blend_method = 'OPAQUE'
    except Exception: pass
    return g, p, out

def principled(m):
    if not m.node_tree: return None
    return next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)

def photo(g, asset, uv, target=None, sat=1.0, contrast=1.0, color_key='color', bump=1.0, bump_dist=0.004,
          rough=(None, None), normal=None):
    """Sample a photo set at uv. Colour: the photo's structure with its mean moved to `target` (sRGB hex)
    and contrast/saturation scaled. Returns dict(color, rough, height, normal, ao)."""
    out = {}
    img = image(asset, color_key)
    c = g.tex(img, uv).outputs['Color']
    if sat != 1.0: c = g.hsv(c, s=sat)
    if contrast != 1.0: c = g.gamma(c, contrast)     # gamma around the mean: <1 flatter, >1 punchier
    if target is not None:
        m = mean_albedo(asset, color_key)
        if sat != 1.0:                                 # desaturating moves the mean toward its luminance
            lum = 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]; m = [lum + (x - lum) * sat for x in m]
        if contrast != 1.0: m = [x ** contrast for x in m]
        t = lin(target)
        c = g.mix(1.0, c, (t[0] / max(m[0], 1e-3), t[1] / max(m[1], 1e-3), t[2] / max(m[2], 1e-3)), 'MULTIPLY')
    out['color'] = c
    ri = image(asset, 'roughness')
    if ri is not None:
        r = g.tex(ri, uv).outputs['Color']
        r = g.bw(r)
        if rough[0] is not None: r = g.maprange(r, 0.0, 1.0, rough[0], rough[1])
        out['rough'] = r
    hi = image(asset, 'disp')
    if hi is not None and bump:
        h = g.bw(g.tex(hi, uv).outputs['Color'])
        out['height'] = h
        out['normal'] = g.bump(h, strength=bump, distance=bump_dist, normal=normal)
    elif bump:
        out['height'] = g.bw(c)
        out['normal'] = g.bump(out['height'], strength=bump * 0.5, distance=bump_dist, normal=normal)
    ai = image(asset, 'ao')
    if ai is not None: out['ao'] = g.bw(g.tex(ai, uv).outputs['Color'])
    return out

def mottle(g, col, scale_m=6.0, amount=0.08, hue=0.0, P=None, seed=0.0):
    """Large-scale value (and hue) variation so repeats never line up: real surfaces are never uniform."""
    P = P or g.P()
    v = g.vmath('ADD', g.vmath('SCALE', P, scale=1.0 / scale_m), (seed, seed * 0.7, seed * 1.3))
    n = g.noise(v, 1.0, 3.0, 0.55)
    val = g.maprange(n, 0.3, 0.7, 1.0 - amount, 1.0 + amount)
    col = g.mix(1.0, col, g.comb(val, val, val), 'MULTIPLY')
    if hue:
        n2 = g.noise(g.vmath('ADD', v, (13.1, 7.7, 3.3)), 1.0, 2.0, 0.5)
        col = g.hsv(col, h=g.maprange(n2, 0.3, 0.7, 0.5 - hue, 0.5 + hue))
    return col

def grime(g, col, ao_dist=0.35, amount=0.25, dirt='#6e6252', samples=4):
    """Dirt where surfaces meet (wall bases, inside corners, under trim): ambient-occlusion masked tint,
    broken up by noise so it reads as soiling, not as a shadow."""
    ao = g.ao(ao_dist, samples)
    br = g.noise(g.vmath('SCALE', g.P(), scale=2.5), 1.0, 4.0, 0.6)
    k = g.mul(g.maprange(ao, 0.35, 1.0, amount, 0.0), g.maprange(br, 0.35, 0.65, 0.4, 1.3))
    return g.mix(g.math('MINIMUM', k, 1.0), col, g.mix(0.5, col, lin(dirt), 'MULTIPLY'))

HAZE = []          # aerial-perspective nodes in far materials; World points them at its sky

def aerial(g, beta=6e-5, lift=0.035):
    """Aerial perspective on far surfaces, for camera rays only: L = L_surface * T + L_air * (1 - T),
    T = exp(-beta * distance) (beta 0.06/km ~ 60 km visibility, clean trade-wind air). The airlight is the
    photographed horizon sky in that azimuth (World fills in the HDRI and its rotation), so the sea pales
    toward the horizon and the far coast softens, as in any real photo across distance."""
    out = next(n for n in g.N if n.type == 'OUTPUT_MATERIAL')
    if not out.inputs['Surface'].links: return
    surf = out.inputs['Surface'].links[0].from_socket
    lp = g.node('ShaderNodeLightPath')
    T = g.math('EXPONENT', g.mul(lp.outputs['Ray Length'], -beta))
    fac = g.mul(g.sub(1.0, T), lp.outputs['Is Camera Ray'])
    vx, vy, _ = g.sep(g.vmath('SCALE', g.geo().outputs['Incoming'], scale=-1.0))
    d = g.vmath('NORMALIZE', g.comb(vx, vy, lift))
    mp = g.node('ShaderNodeMapping', vector_type='POINT'); g.put(mp.inputs['Vector'], d)
    env = g.node('ShaderNodeTexEnvironment', interpolation='Linear'); g.put(env.inputs['Vector'], mp.outputs[0])
    em = g.node('ShaderNodeEmission'); g.put(em.inputs['Color'], (0.33, 0.36, 0.43)); g.put(em.inputs['Strength'], 1.0)
    mix = g.node('ShaderNodeMixShader'); g.put(mix.inputs[0], fac)
    g.L.new(surf, mix.inputs[1]); g.L.new(em.outputs[0], mix.inputs[2]); g.L.new(mix.outputs[0], out.inputs['Surface'])
    HAZE.append((env, mp, em, g))

def finish(g, p, color=None, rough=None, normal=None, metallic=None, spec=None, coat=None, coat_rough=None,
           sheen=None, sheen_tint=None, aniso=None, ior=None):
    for k, v in (('Base Color', color), ('Roughness', rough), ('Normal', normal), ('Metallic', metallic),
                 ('Specular IOR Level', spec), ('Coat Weight', coat), ('Coat Roughness', coat_rough),
                 ('Sheen Weight', sheen), ('Sheen Tint', sheen_tint), ('Anisotropic', aniso), ('IOR', ior)):
        if v is not None: g.put(p.inputs[k], v)


# ------------------------------------------------------------------------------------------ recipes: exterior
def r_siding(m, ctx):
    """White painted lap siding (6 1/2" exposure): real scanned boards, crisp new white paint over the
    grain, satin sheen, grime at the base / in corners / under the eaves."""
    g, p, _ = fresh(m)
    H = 8 * 0.165; uv = box_uv(g, 2 * H, H)
    ph = photo(g, 'painted_lap_siding', uv, target='#e9e8e3', sat=0.0, contrast=0.55, color_key='color_white',
               bump=1.0, bump_dist=0.012, rough=(0.38, 0.62))
    c = g.mix(0.55, ph['color'], lin('#ecebe6'))                 # new paint fills the old weathering
    c = mottle(g, c, 4.0, 0.03)
    c = grime(g, c, 0.45, 0.28, '#8a7f70')
    finish(g, p, color=c, rough=ph.get('rough', 0.5), normal=ph['normal'], spec=0.5)

def r_trim(m, ctx):
    g, p, _ = fresh(m)
    c = mottle(g, lin('#eeede8'), 3.0, 0.02)
    c = grime(g, c, 0.3, 0.18, '#8a7f70')
    n = g.bump(g.noise(g.vmath('SCALE', g.P(), scale=60.0), 1.0, 2.0, 0.5), 0.05, 0.001)   # brushed paint
    finish(g, p, color=c, rough=0.36, normal=n, spec=0.5)

def r_paint(m, ctx, color='#efeee9', rough=0.78):
    """Interior flat white paint (walls / ceilings); faint roller texture."""
    g, p, _ = fresh(m)
    c = mottle(g, lin(color), 2.5, 0.015)
    c = grime(g, c, 0.25, 0.1, '#9a9080')
    n = g.bump(g.noise(g.vmath('SCALE', g.P(), scale=90.0), 1.0, 3.0, 0.6), 0.06, 0.0008)
    finish(g, p, color=c, rough=rough, normal=n, spec=0.45)

def r_batten(m, ctx):
    """Board-and-batten: 1x3 battens 16" on centre over flat boards, painted white (eggshell)."""
    g, p, _ = fresh(m)
    n3 = g.Nrm(); nx, ny, nz = g.sep(n3)
    # u = metres along the wall (horizontal, in the wall plane)
    along = g.vmath('NORMALIZE', g.vmath('CROSS_PRODUCT', n3, (0.0, 0.0, 1.0)))
    u = g.vmath('DOT_PRODUCT', g.P(), along, out=1)
    pitch, half = 0.4064, 0.032
    f = g.math('FRACT', g.math('DIVIDE', u, pitch))
    e = g.mul(g.math('ABSOLUTE', g.sub(f, 0.5)), pitch)                       # metres from the batten centre line
    rib = g.maprange(e, half + 0.002, half - 0.002, 0.0, 0.019)                 # 3/4" proud, eased edges
    wall = g.math('LESS_THAN', g.math('ABSOLUTE', nz), 0.5)
    h = g.mul(rib, wall)
    nrm = g.bump(h, 1.0, 1.0)
    nrm = g.bump(g.noise(g.vmath('SCALE', g.P(), scale=80.0), 1.0, 3.0, 0.6), 0.05, 0.0008, normal=nrm)
    c = mottle(g, lin('#eeede7'), 2.5, 0.015)
    c = grime(g, c, 0.25, 0.12, '#9a9080')
    finish(g, p, color=c, rough=0.62, normal=nrm, spec=0.45)

def r_tongue_groove(m, ctx, exterior=False):
    """White painted tongue-and-groove ceiling / soffit boards (5 1/4" exposure, V-groove), boards running
    up the slope as on the design board; flat ceilings run along the house (x)."""
    g, p, _ = fresh(m)
    t, s = slope_frame(g, fallback=(0.0, 1.0))
    pitch = 0.1334
    f = g.math('FRACT', g.math('DIVIDE', t, pitch))
    e = g.mul(g.math('ABSOLUTE', g.sub(f, 0.5)), pitch)
    groove = g.maprange(e, pitch / 2 - 0.004, pitch / 2, 0.0, -0.003)
    board = g.math('FLOOR', g.math('DIVIDE', t, pitch))
    rnd = g.white(g.comb(board, 3.3, 0.0))
    nrm = g.bump(groove, 1.0, 1.0)
    nrm = g.bump(g.noise(g.vmath('SCALE', g.P(), scale=70.0), 1.0, 3.0, 0.6), 0.05, 0.0008, normal=nrm)
    base = lin('#efeee8')
    c = g.mix(1.0, base, g.comb(*(g.maprange(rnd, 0.0, 1.0, 0.975, 1.02),) * 3), 'MULTIPLY')
    if exterior: c = grime(g, c, 0.4, 0.22, '#8f8575')
    else: c = grime(g, c, 0.3, 0.1, '#9a9080')
    finish(g, p, color=c, rough=0.55, normal=nrm, spec=0.45)

def r_standing_seam(m, ctx, color='#8d9196', metallic=0.0, rough=0.42):
    """Standing-seam metal roof: 16" panels, 1" ribs running down the slope, painted (Kynar) neutral grey
    over galvalume; the scanned galvanized sheet gives the spangle / patina in sheen, slight oil-canning
    inside each panel, panel-to-panel tone scatter, faint wash streaks down the fall line."""
    g, p, _ = fresh(m)
    t, s = slope_frame(g)
    W = 0.4064
    f = g.math('FRACT', g.math('DIVIDE', t, W))
    e = g.mul(g.math('ABSOLUTE', g.sub(f, 0.5)), W)                                  # 0 at panel centre
    d = g.sub(W / 2, e)                                                              # metres to the seam
    rib = g.maprange(d, 0.022, 0.006, 0.0, 0.032, smooth=True)                       # 1 1/4" rib, 1/2" cap
    panel = g.math('FLOOR', g.math('DIVIDE', t, W))
    prnd = g.white(g.comb(panel, g.math('FLOOR', g.math('DIVIDE', s, 7.0)), 1.7))
    # oil canning: slow waves across each flat pan, stronger mid-pan
    oc = g.noise(g.comb(g.math('DIVIDE', t, 0.35), g.math('DIVIDE', s, 2.2), g.mul(prnd, 9.0)), 1.0, 1.0, 0.4)
    oc = g.mul(g.sub(oc, 0.5), g.mul(g.maprange(e, 0.0, W / 2 - 0.02, 0.003, 0.0), 1.0))
    pencil = g.maprange(g.math('ABSOLUTE', g.sub(e, W * 0.17)), 0.004, 0.0, 0.0, 0.0012)   # two pencil ribs
    h = g.add(g.add(rib, oc), pencil)
    nrm = g.bump(h, 1.0, 1.0)
    # galvanized sheet scan: spangle, rolling marks (sheen + tone)
    uv = g.comb(g.math('DIVIDE', t, 1.12), g.math('DIVIDE', s, 1.12), 0.0)
    gal = g.tex(image('galvanized_steel', 'color'), uv).outputs['Color']
    galr = g.bw(g.tex(image('galvanized_steel', 'roughness'), uv).outputs['Color'])
    base = lin(color)
    lum = g.bw(gal)
    tone = g.maprange(lum, 0.25, 0.65, 0.93, 1.05)
    tone = g.mul(tone, g.maprange(prnd, 0.0, 1.0, 0.965, 1.035))
    streak = g.noise(g.comb(g.math('DIVIDE', t, 0.06), g.math('DIVIDE', s, 3.0), 0.0), 1.0, 3.0, 0.6)
    tone = g.mul(tone, g.maprange(streak, 0.35, 0.75, 1.025, 0.96))
    seam_dirt = g.maprange(d, 0.03, 0.012, 1.0, 0.86)                               # dust lodges along the seams
    tone = g.mul(tone, seam_dirt)
    c = g.mix(1.0, base, g.comb(tone, tone, tone), 'MULTIPLY')
    c = mottle(g, c, 12.0, 0.03)
    c = grime(g, c, 0.5, 0.18, '#6f6a62')
    r = g.add(rough, g.mul(g.sub(galr, 0.5), 0.25))
    r = g.add(r, g.maprange(prnd, 0.0, 1.0, -0.04, 0.04))
    finish(g, p, color=c, rough=r, normal=nrm, metallic=metallic, spec=0.5)

def r_fascia(m, ctx):
    """Painted metal fascia, gutters and hip / ridge caps: the roof's grey (as in the references), a shade
    darker from the folded edge."""
    g, p, _ = fresh(m)
    c = mottle(g, lin('#74787d'), 3.0, 0.04)
    c = grime(g, c, 0.25, 0.15, '#5a554e')
    finish(g, p, color=c, rough=0.38, metallic=0.1, spec=0.5)

def r_black_frame(m, ctx, rough=0.32):
    """Black powder-coated aluminium window frames / fixtures."""
    g, p, _ = fresh(m)
    c = lin('#141414')
    c = grime(g, c, 0.15, 0.25, '#7c7468')
    r = g.add(rough, g.mul(g.sub(g.noise(g.vmath('SCALE', g.P(), scale=4.0), 1.0, 3.0, 0.5), 0.5), 0.12))
    finish(g, p, color=c, rough=r, metallic=0.15, spec=0.5)

def r_wood(m, ctx, asset, tile, target, sat=1.0, contrast=1.0, rough=(0.45, 0.7), grain='V', weather=0.0,
           grime_amt=0.12, coat=None, bump=0.6, aspect=1.0, box=False):
    g, p, _ = fresh(m)
    rnd = g.obj_random()
    off = (g.mul(rnd, 7.31), g.mul(rnd, 3.17))
    uv = box_uv(g, tile, tile / aspect, off=off) if box else grain_uv(g, tile, tile / aspect, grain=grain, off=off)
    ph = photo(g, asset, uv, target=target, sat=sat, contrast=contrast, bump=bump, bump_dist=0.0015, rough=rough)
    c = g.mix(1.0, ph['color'], g.comb(*(g.maprange(rnd, 0.0, 1.0, 0.92, 1.07),) * 3), 'MULTIPLY')   # board-to-board
    if weather:
        silver = photo(g, 'weathered_teak_silver', uv, target='#9c968c', sat=0.6, bump=0)['color']
        k = g.mul(g.noise(g.vmath('SCALE', g.P(), scale=1.5), 1.0, 4.0, 0.6), weather * 1.6)
        c = g.mix(g.math('MINIMUM', k, 1.0), c, silver)
    c = mottle(g, c, 2.0, 0.04)
    if grime_amt: c = grime(g, c, 0.3, grime_amt, '#4e4236')
    finish(g, p, color=c, rough=ph.get('rough', 0.55), normal=ph.get('normal'), spec=0.5,
           coat=coat, coat_rough=0.25 if coat else None)
    return g, p

def r_cedar_door(m, ctx):
    """Stained cedar carriage garage door: vertical 5 1/2" boards, oiled reddish-brown (front rendering)."""
    r_wood(m, ctx, 'cedar_door_planks', 1.4, '#a8693f', sat=0.95, contrast=0.68, rough=(0.42, 0.62), grain='V',
           aspect=2.0, grime_amt=0.15, box=True)

def r_cedar_batten(m, ctx):
    r_wood(m, ctx, 'cedar_door_planks', 1.4, '#8a5432', sat=0.95, contrast=0.7, rough=(0.45, 0.65), grain='V',
           aspect=2.0, grime_amt=0.15)

def r_beam(m, ctx):
    """Lanai posts and beams: rough-sawn cedar, oiled, a little sun-greyed (back rendering)."""
    r_wood(m, ctx, 'cedar_beam', 1.2, '#a07a58', sat=0.72, contrast=0.9, rough=(0.55, 0.8), grain='V',
           weather=0.18, grime_amt=0.18, bump=0.9)

def r_teak(m, ctx):
    """Outdoor teak furniture: honey teak, oiled, slightly greyed (design board / back rendering)."""
    r_wood(m, ctx, 'teak', 1.0, '#b38d63', sat=0.8, contrast=0.9, rough=(0.45, 0.65), grain='V', weather=0.12,
           grime_amt=0.06)

def r_oak_millwork(m, ctx):
    """Rift-sawn white oak cabinetry / furniture (design board sample)."""
    r_wood(m, ctx, 'rift_white_oak', 1.0, '#c9a77c', sat=0.85, contrast=0.95, rough=(0.38, 0.55), grain='V',
           grime_amt=0.05)

def r_oak_floor(m, ctx):
    """White oak plank floor, 7 1/2" planks running along the house, matte oil finish."""
    g, p, _ = fresh(m)
    rnd = g.obj_random()
    uv = box_uv(g, 2.0, 2.0, off=(g.mul(rnd, 5.1), g.mul(rnd, 2.3)))
    ph = photo(g, 'white_oak_floor', uv, target='#c3a47f', sat=0.82, contrast=0.9, bump=0.8, bump_dist=0.0012, rough=(0.38, 0.6))
    c = mottle(g, ph['color'], 2.5, 0.03)
    c = grime(g, c, 0.25, 0.08, '#6a5a48')
    finish(g, p, color=c, rough=ph.get('rough', 0.5), normal=ph.get('normal'), spec=0.5)

def r_slab_paving(m, ctx, asset='travertine_honed', tile=1.2, target='#d9ccb6', slab=(0.6096, 0.6096), joint=0.004,
                  rough=(0.5, 0.75), contrast=0.8, sat=0.85, grime_amt=0.2):
    """Honed stone slabs laid in a grid (24" x 24"), each cut from a different part of the scan, tight
    sanded joints; vertical faces get the same stone."""
    g, p, _ = fresh(m)
    px, py, pz = g.sep(g.P())
    ix = g.math('FLOOR', g.math('DIVIDE', px, slab[0])); iy = g.math('FLOOR', g.math('DIVIDE', py, slab[1]))
    cell = g.white(g.comb(ix, iy, 0.5), 'Color')
    cx, cy, cz = g.sep(cell)
    uv = box_uv(g, tile, tile, off=(g.mul(cx, 11.0), g.mul(cy, 11.0)))
    ph = photo(g, asset, uv, target=target, sat=sat, contrast=contrast, bump=0.6, bump_dist=0.0015, rough=rough)
    fx = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.math('DIVIDE', px, slab[0])), 0.5)), slab[0])
    fy = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.math('DIVIDE', py, slab[1])), 0.5)), slab[1])
    jx = g.maprange(fx, slab[0] / 2 - joint, slab[0] / 2, 0.0, 1.0); jy = g.maprange(fy, slab[1] / 2 - joint, slab[1] / 2, 0.0, 1.0)
    _, _, nz = g.sep(g.vmath('ABSOLUTE', g.Nrm()))
    top = g.math('GREATER_THAN', nz, 0.7)
    j = g.mul(g.math('MAXIMUM', jx, jy), top)
    c = g.mix(1.0, ph['color'], g.comb(*(g.maprange(cz, 0.0, 1.0, 0.93, 1.06),) * 3), 'MULTIPLY')
    c = g.mix(j, c, g.mix(1.0, c, lin('#a69a86'), 'MULTIPLY'))
    c = mottle(g, c, 5.0, 0.05)
    if grime_amt: c = grime(g, c, 0.3, grime_amt, '#7d6f5c')
    nrm = g.bump(g.mul(j, -0.002), 1.0, 1.0, normal=ph.get('normal'))
    r = g.mixf(j, ph.get('rough', 0.6), 0.9)
    finish(g, p, color=c, rough=r, normal=nrm, spec=0.5)

def r_coral_wall(m, ctx, target='#cfb894', contrast=0.7, sat=0.85, tile=3.0, grime_amt=0.3):
    """Coral-stone retaining / garden walls: the 4K coral-rubble scan, recoloured to the warm pale
    coral stone of the back rendering; dirt in the joints and along the base."""
    g, p, _ = fresh(m)
    uv = box_uv(g, tile, tile)
    ph = photo(g, 'coral_stone_wall', uv, target=target, sat=sat, contrast=contrast, bump=1.0, bump_dist=0.02, rough=(0.7, 0.95))
    c = ph['color']
    if 'ao' in ph: c = g.mix(1.0, c, g.comb(*(g.maprange(ph['ao'], 0.0, 1.0, 0.75, 1.0),) * 3), 'MULTIPLY')
    c = mottle(g, c, 3.0, 0.06, hue=0.01)
    c = grime(g, c, 0.5, grime_amt, '#6b5f4c')
    finish(g, p, color=c, rough=ph.get('rough', 0.85), normal=ph['normal'], spec=0.4)

def r_pool_shell(m, ctx):
    """Pool / spa shell in hand-set glass mosaic (the back rendering shows tile throughout): light aqua on
    the floor and walls, a 6" band of deeper turquoise at the waterline (top of each wall piece)."""
    g, p, _ = fresh(m)
    uv_t = box_uv(g, 0.6, 0.6)
    tile = photo(g, 'glass_mosaic', uv_t, target='#2a8fa6', sat=1.0, contrast=1.0, color_key='color_aqua', bump=1.0, bump_dist=0.002, rough=(0.08, 0.3))
    pl = photo(g, 'glass_mosaic', uv_t, target='#80c4d2', sat=0.8, contrast=0.8, color_key='color_aqua', bump=1.0, bump_dist=0.002, rough=(0.08, 0.3))
    band = g.attr('nh_wl', 'Fac')                       # metres below the top of the piece (apply())
    k = g.maprange(band, 0.16, 0.145, 0.0, 1.0)
    c = g.mix(k, pl['color'], tile['color'])
    r = g.mixf(k, pl.get('rough', 0.6), tile.get('rough', 0.15))
    n = g.node('ShaderNodeMix', data_type='VECTOR'); g.put(n.inputs[0], k); g.put(n.inputs[4], pl['normal']); g.put(n.inputs[5], tile['normal'])
    finish(g, p, color=c, rough=r, normal=n.outputs[1], spec=0.5)

def r_stepping(m, ctx):
    """Entry walk: large honed travertine stepping slabs set in turf. The layout is the three.js texture
    (UV); the slabs get the travertine scan, the joints a real turf photo."""
    _paver_mask_material(m, ctx, stone=('travertine_honed', 1.2, '#d6cab3'), stone_sat=0.8)

def r_grass_pavers(m, ctx):
    """Driveway: hexagonal concrete grass pavers (the layout from the three.js texture), concrete scan + turf."""
    _paver_mask_material(m, ctx, stone=('concrete_light', 2.0, '#bdb7aa'), stone_sat=0.6, grass_first=True)

def _paver_mask_material(m, ctx, stone, stone_sat=0.8, grass_first=False):
    nt = m.node_tree
    old = next((n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links
                and any(l.to_socket.name in ('Base Color', 'A') for l in n.outputs['Color'].links)), None)
    layout_img = old.image if old else None
    layout_vec = old.inputs['Vector'].links[0].from_node if (old and old.inputs['Vector'].links) else None
    mp = None
    if layout_vec is not None and layout_vec.type == 'MAPPING':
        mp = (tuple(layout_vec.inputs['Location'].default_value), tuple(layout_vec.inputs['Rotation'].default_value), tuple(layout_vec.inputs['Scale'].default_value))
    uvname = None
    if layout_vec is not None and layout_vec.inputs['Vector'].links:
        src = layout_vec.inputs['Vector'].links[0].from_node
        if src.type == 'UVMAP': uvname = src.uv_map
    g, p, _ = fresh(m)
    if layout_img is not None:
        uvn = g.node('ShaderNodeUVMap');
        if uvname: uvn.uv_map = uvname
        v = uvn.outputs[0]
        if mp:
            mn = g.node('ShaderNodeMapping'); g.put(mn.inputs['Vector'], v)
            mn.inputs['Location'].default_value = mp[0]; mn.inputs['Rotation'].default_value = mp[1]; mn.inputs['Scale'].default_value = mp[2]
            v = mn.outputs[0]
        lay = g.tex(layout_img, v, interp='Cubic').outputs['Color']
        r_, g_, b_ = g.sep(lay)
        greenness = g.sub(g_, g.math('MAXIMUM', r_, b_))
        grass = g.maprange(greenness, 0.03, 0.1, 0.0, 1.0)
    else:
        grass = 0.0
    an, tile, target = stone
    uv = box_uv(g, tile, tile, off=(g.mul(g.obj_random(), 9.1), 0.0))
    st = photo(g, an, uv, target=target, sat=stone_sat, contrast=0.85, bump=0.6, bump_dist=0.0015, rough=(0.55, 0.8))
    uvg = box_uv(g, 1.6, 1.6)
    gr = photo(g, 'grass004', uvg, target='#6f8a3c', sat=1.0, contrast=1.0, bump=1.0, bump_dist=0.01, rough=(0.6, 0.85))
    gcol = mottle(g, gr['color'], 3.0, 0.12, hue=0.015)
    scol = mottle(g, st['color'], 4.0, 0.05)
    scol = grime(g, scol, 0.25, 0.25, '#6d6150')
    c = g.mix(grass, scol, gcol)
    r = g.mixf(grass, st.get('rough', 0.65), gr.get('rough', 0.8))
    n = g.node('ShaderNodeMix', data_type='VECTOR'); g.put(n.inputs[0], grass); g.put(n.inputs[4], st['normal']); g.put(n.inputs[5], gr['normal'])
    finish(g, p, color=c, rough=r, normal=n.outputs[1], spec=0.45)

def r_asphalt(m, ctx):
    g, p, _ = fresh(m)
    uv = box_uv(g, 4.0, 4.0)
    ph = photo(g, 'asphalt', uv, target='#4a4947', sat=0.6, contrast=1.0, bump=0.8, bump_dist=0.004, rough=(0.75, 0.95))
    c = mottle(g, ph['color'], 15.0, 0.08)
    finish(g, p, color=c, rough=ph.get('rough', 0.85), normal=ph['normal'], spec=0.4)

def r_concrete(m, ctx):
    g, p, _ = fresh(m)
    ph = photo(g, 'broom_concrete', box_uv(g, 2.5, 2.5), target='#b5aea2', sat=0.7, bump=0.6, bump_dist=0.002, rough=(0.65, 0.9))
    finish(g, p, color=mottle(g, ph['color'], 4.0, 0.05), rough=ph.get('rough', 0.8), normal=ph['normal'])

def r_terrain(m, ctx):
    """The land itself (under and beyond the grown lawn): real mown-turf photo, two scales mixed so it never
    tiles, mottled at 5-40 m; rough grass / soil on the banks; the land-cover map (fairways, greens,
    bunkers, red-dirt fields, mowing stripes) when the export provides it (meta['land']); otherwise the
    terrain's vertex colours (lawn -> wild) steer lawn vs rough."""
    g, p, _ = fresh(m)
    P = g.P()
    uv1 = box_uv(g, 1.6, 1.6, P=P)
    uv2 = box_uv(g, 2.3, 2.3, rot=0.61, off=(0.37, 0.71), P=P)
    a = photo(g, 'grass004', uv1, target='#6c8a37', bump=1.0, bump_dist=0.012, rough=(0.65, 0.9))
    b = photo(g, 'grass004', uv2, target='#6c8a37', bump=0, rough=(0.65, 0.9))
    k = g.maprange(g.noise(g.vmath('SCALE', P, scale=0.35), 1.0, 2.0, 0.5), 0.4, 0.6)
    lawn = g.mix(k, a['color'], b['color'])
    dark = photo(g, 'grass001', uv2, target='#4e6d2c', bump=0, rough=(0.7, 0.9))['color']
    lawn = g.mix(g.maprange(g.noise(g.vmath('SCALE', P, scale=1 / 9.0), 1.0, 3.0, 0.6), 0.45, 0.7, 0.0, 0.45), lawn, dark)
    lawn = mottle(g, lawn, 25.0, 0.1, hue=0.02, P=P)
    lawn = mottle(g, lawn, 5.0, 0.05, P=P, seed=3.0)
    # golf rough / unmown grass: Kauai stays green; a little thatch shows through in patches
    thatch = photo(g, 'lawn_soil_thatch', box_uv(g, 2.0, 2.0, P=P), target='#6f7445', sat=0.8, bump=0)['color']
    rough_grass = g.mix(g.maprange(g.noise(g.vmath('SCALE', P, scale=1 / 14.0), 1.0, 3.0, 0.6), 0.45, 0.75, 0.1, 0.45), dark, thatch)
    rough_grass = mottle(g, rough_grass, 18.0, 0.12, hue=0.02, P=P)
    soil = photo(g, 'red_soil', box_uv(g, 2.0, 2.0, P=P), target='#7a5a40', sat=0.9, bump=0.8, bump_dist=0.01, rough=(0.8, 1.0))
    # vertex colours: ~white on the lots, greens beyond (src/site.js terrainMesh)
    vc = g.attr(ctx.get('terrain_color_attr', 'Color'), 'Color')
    vl = g.bw(vc)
    wild = g.maprange(vl, 0.55, 0.3, 0.0, 1.0)
    lots = ctx.get('lots')
    if lots is not None:                                  # every Na Hiku lot is kept lawn, not just ours
        px, py, _ = g.sep(P)
        x0, y0, w, h = lots['box']
        lm = g.tex(lots['img'], g.comb(g.math('DIVIDE', g.sub(px, x0), w), g.math('DIVIDE', g.sub(py, y0), h), 0.0), ext='CLIP')
        wild = g.mul(wild, g.sub(1.0, g.bw(lm.outputs['Color'])))
    col = g.mix(wild, lawn, rough_grass)
    rough_val = g.mixf(wild, a.get('rough', 0.8), 0.9)
    land = ctx.get('land')
    if land is not None:
        col = _land_cover(g, P, land, col, lawn, rough_grass, soil['color'])
    # steep banks: earth through thin grass
    _, _, nz = g.sep(g.Nrm())
    steep = g.mul(g.maprange(nz, 0.88, 0.6, 0.0, 1.0), g.maprange(g.noise(g.vmath('SCALE', P, scale=0.8), 1.0, 3.0, 0.6), 0.3, 0.6, 0.5, 1.0))
    col = g.mix(steep, col, soil['color'])
    nrm = g.node('ShaderNodeMix', data_type='VECTOR'); g.put(nrm.inputs[0], steep); g.put(nrm.inputs[4], a['normal']); g.put(nrm.inputs[5], soil['normal'])
    finish(g, p, color=col, rough=rough_val, normal=nrm.outputs[1], spec=0.35)
    if not ctx.get('night'): aerial(g)

def _land_cover(g, P, land, col, lawn, rough_grass, soil):
    """meta['land'] = {'box': [x0, y0, w, h] (plan feet), 'image': path} - the three.js land map."""
    img = land['img']
    x0, y0, w, h = land['box']
    px, py, _ = g.sep(P)
    u = g.math('DIVIDE', g.sub(g.math('DIVIDE', px, FT), x0), w)
    v = g.math('DIVIDE', g.sub(g.math('DIVIDE', g.mul(py, -1.0), FT), y0), h)
    t = g.tex(img, g.comb(u, v, 0.0), interp='Cubic', ext='CLIP')
    L, A = t.outputs['Color'], t.outputs['Alpha']
    r, gg, bb = g.sep(L)
    # the canvas colours (linear): fairway (.26,.55,.09) stripe (.35,.66,.12) green (.39,.73,.14)
    # bunker (.87,.76,.51) field (.40,.26,.12)
    sandy = g.mul(g.maprange(bb, 0.25, 0.45), g.maprange(r, 0.6, 0.8))
    field = g.mul(g.maprange(g.sub(r, gg), 0.05, 0.12), g.math('LESS_THAN', bb, 0.3))
    golf = g.math('MAXIMUM', g.sub(g.sub(1.0, sandy), field), 0.0)
    stripes = g.maprange(gg, 0.55, 0.65, 0.94, 1.06)
    fair = g.mix(1.0, g.hsv(lawn, s=1.12, v=1.08), g.comb(stripes, stripes, stripes), 'MULTIPLY')
    sand = lin('#d9cdb0')
    c = g.mix(g.mul(A, golf), col, fair)
    c = g.mix(g.mul(A, field), c, soil)
    c = g.mix(g.mul(A, sandy), c, sand)
    return c

def r_ocean(m, ctx):
    """Open Pacific: deep navy water body, wind chop + trade swell as bump, roughness of a real wind-blown
    sea so each facet mirrors sky well above the hazy horizon (Fresnel at grazing incidence + wave slopes:
    why a real ocean reads deep blue to the horizon instead of a pale mirror of the haze)."""
    g, p, _ = fresh(m)
    P = g.P()
    px, py, pz = g.sep(P)
    sw = g.noise(g.comb(g.mul(g.add(g.mul(px, 0.8), g.mul(py, 0.6)), 1 / 40.0), g.mul(g.add(g.mul(px, -0.6), g.mul(py, 0.8)), 1 / 160.0), 0.0), 1.0, 2.0, 0.5)
    ch = g.noise(g.vmath('SCALE', P, scale=1 / 3.0), 1.0, 6.0, 0.6, distortion=0.3)
    h = g.add(g.mul(sw, 0.9), g.mul(ch, 0.25))
    nrm = g.bump(h, 1.0, 1.0)
    deep = lin('#0a2a52')
    c = mottle(g, deep, 900.0, 0.12, P=P)
    finish(g, p, color=c, rough=ctx.get('ocean_rough', 0.3), normal=nrm, spec=0.5, ior=1.333)
    m['nh_kind'] = 'ocean'
    if not ctx.get('night'): aerial(g)

def r_pool_water(m, ctx):
    """Pool water: clear, refracting; tint = absorption over the ~3 m light path (red lost first)."""
    p = principled(m)
    if not p: return
    p.inputs['Transmission Weight'].default_value = 1.0
    p.inputs['Roughness'].default_value = 0.015
    p.inputs['IOR'].default_value = 1.333
    p.inputs['Alpha'].default_value = 1.0
    for l in list(p.inputs['Alpha'].links): m.node_tree.links.remove(l)
    for l in list(p.inputs['Base Color'].links): m.node_tree.links.remove(l)
    p.inputs['Base Color'].default_value = (0.24, 0.74, 0.9, 1)
    # the ripple normal map from three.js stays; soften it a touch (glassy pool on a calm afternoon)
    for n in m.node_tree.nodes:
        if n.type == 'NORMAL_MAP': n.inputs['Strength'].default_value = 0.6

def r_falls(m, ctx):
    """Sheet of water over the vanishing edge: refracting, aerated (a little white)."""
    g, p, out = fresh(m)
    px, py, pz = g.sep(g.P())
    streak = g.noise(g.comb(g.mul(g.add(px, py), 25.0), g.mul(pz, 1.2), 0.0), 1.0, 4.0, 0.6)
    nrm = g.bump(streak, 0.6, 0.004)
    finish(g, p, color=(0.8, 0.95, 0.97), rough=0.06, normal=nrm, ior=1.333)
    p.inputs['Transmission Weight'].default_value = 0.85
    foam = g.node('ShaderNodeBsdfDiffuse'); g.put(foam.inputs['Color'], (0.9, 0.95, 0.95))
    mx = g.node('ShaderNodeMixShader'); g.put(mx.inputs[0], g.maprange(streak, 0.5, 0.8, 0.05, 0.3))
    g.L.new(p.outputs[0], mx.inputs[1]); g.L.new(foam.outputs[0], mx.inputs[2]); g.L.new(mx.outputs[0], out.inputs['Surface'])

def r_glass(m, ctx):
    p = principled(m)
    if not p: return
    p.inputs['Transmission Weight'].default_value = 1.0
    p.inputs['Roughness'].default_value = 0.0
    p.inputs['IOR'].default_value = 1.52
    p.inputs['Alpha'].default_value = 1.0
    for l in list(p.inputs['Alpha'].links): m.node_tree.links.remove(l)
    p.inputs['Thin Wall'].default_value = True
    p.inputs['Base Color'].default_value = (0.9, 0.95, 0.94, 1)     # faint green of float glass

def r_dark_glass(m, ctx):
    """Massing homes' windows: interior reads dark behind reflective glass."""
    g, p, _ = fresh(m)
    finish(g, p, color=lin('#1c2124'), rough=0.04, spec=0.6, ior=1.52)

def r_gloss_water(m, ctx, color='#13525c', rough=0.04):
    """Water seen from afar (massing-home pools, ponds): glossy dielectric over a dark body."""
    g, p, _ = fresh(m)
    finish(g, p, color=lin(color), rough=rough, ior=1.333, spec=0.5)
    if not ctx.get('night'): aerial(g)


# ------------------------------------------------------------------------------------------ recipes: interior
def r_fabric(m, ctx, target, asset='linen_oatmeal', tile=0.15, sat=1.0, sheen=0.5, rough=(0.75, 0.95), contrast=0.9):
    g, p, _ = fresh(m)
    uv = box_uv(g, tile, tile, off=(g.mul(g.obj_random(), 3.3), 0.0))
    ph = photo(g, asset, uv, target=target, sat=sat, contrast=contrast, bump=0.5, bump_dist=0.0006, rough=rough)
    c = mottle(g, ph['color'], 0.6, 0.03)
    c = grime(g, c, 0.12, 0.1, '#7a6e60')
    finish(g, p, color=c, rough=ph.get('rough', 0.85), normal=ph.get('normal'), sheen=sheen, sheen_tint=(1, 1, 1), spec=0.4)

def r_quartz(m, ctx):
    g, p, _ = fresh(m)
    ph = photo(g, 'white_quartz', box_uv(g, 1.5, 1.5), target='#ecebe7', sat=0.6, contrast=1.0, bump=0.1, bump_dist=0.0003, rough=(0.08, 0.2))
    finish(g, p, color=ph['color'], rough=ph.get('rough', 0.12), normal=ph.get('normal'), spec=0.5, coat=0.3, coat_rough=0.05)

def r_coral_panel(m, ctx):
    """Interior coral-stone feature wall: pale porous coral stone (design board)."""
    r_coral_wall(m, ctx, target='#e4dccc', contrast=0.6, sat=0.35, tile=2.0, grime_amt=0.12)

def r_rattan(m, ctx):
    r_fabric(m, ctx, '#b48a58', asset='rattan_weave', tile=0.3, sat=0.85, sheen=0.1, rough=(0.5, 0.75))

def r_jute(m, ctx):
    r_fabric(m, ctx, '#a68e6c', asset='jute_burlap', tile=1.0, sat=0.8, sheen=0.3, rough=(0.8, 1.0))

def r_simple(m, ctx, color=None, rough=None, metallic=None, coat=None, spec=None, aniso=None):
    p = principled(m)
    if not p: return
    if color is not None:
        for l in list(p.inputs['Base Color'].links): m.node_tree.links.remove(l)
        p.inputs['Base Color'].default_value = lin(color) if isinstance(color, str) else color
    for k, v in (('Roughness', rough), ('Metallic', metallic), ('Coat Weight', coat), ('Specular IOR Level', spec), ('Anisotropic', aniso)):
        if v is not None:
            for l in list(p.inputs[k].links): m.node_tree.links.remove(l)
            p.inputs[k].default_value = v

def r_keep_tex(m, ctx, tint=None, rough=None, sheen=None):
    """three.js pattern textures that are UV-correct (louvres, slats, cane): keep, retune the finish."""
    p = principled(m)
    if not p: return
    nt = m.node_tree
    if tint is not None:
        src = p.inputs['Base Color'].links[0].from_socket if p.inputs['Base Color'].links else None
        if src is not None:
            mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
            mul.inputs[7].default_value = (*tint[:3], 1)
            nt.links.new(src, mul.inputs[6]); nt.links.new(mul.outputs[2], p.inputs['Base Color'])
    if rough is not None:
        for l in list(p.inputs['Roughness'].links): nt.links.remove(l)
        p.inputs['Roughness'].default_value = rough
    if sheen is not None: p.inputs['Sheen Weight'].default_value = sheen

def r_foliage(m, ctx):
    """Leaves: thin-leaf translucency (light through the blade), alpha cut-out kept."""
    p = principled(m)
    if not p: return
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
    l = p.inputs['Base Color'].links
    if l: nt.links.new(l[0].from_socket, tr.inputs['Color'])
    else: tr.inputs['Color'].default_value = p.inputs['Base Color'].default_value
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs['Fac'].default_value = 0.32
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

def r_trunk(m, ctx):
    p = principled(m)
    if not p: return
    src = p.inputs['Base Color'].links[0].from_socket if p.inputs['Base Color'].links else None
    if src:
        nt = m.node_tree
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1.0
        mul.inputs[7].default_value = (0.55, 0.53, 0.5, 1)
        nt.links.new(src, mul.inputs[6]); nt.links.new(mul.outputs[2], p.inputs['Base Color'])

def r_glow(m, ctx):
    p = principled(m)
    if not p: return
    p.inputs['Emission Color'].default_value = (1.0, 0.78, 0.52, 1)
    p.inputs['Emission Strength'].default_value = 25.0 if ctx.get('night') else 0.0


# ------------------------------------------------------------------------------------------ dispatch
RECIPES = {
    'terrain': r_terrain, 'ocean': r_ocean, 'water': r_pool_water, 'glass': r_glass,
    'mirror': lambda m, c: r_simple(m, c, rough=0.0, metallic=1.0),
    'roof': lambda m, c: r_standing_seam(m, c, '#7f8388'),
    'roof bronze': lambda m, c: r_standing_seam(m, c, '#5b5049', rough=0.45),
    'roof slate': lambda m, c: r_standing_seam(m, c, '#5c6267', rough=0.45),
    'fascia': r_fascia, 'soffit': lambda m, c: r_tongue_groove(m, c, exterior=True), 'planks': r_tongue_groove,
    'siding': r_siding, 'trim': r_trim, 'paint': r_paint, 'batten': r_batten,
    'black': r_black_frame, 'blackMatte': lambda m, c: r_black_frame(m, c, rough=0.6),
    'cedar': r_cedar_door, 'cedarBatten': r_cedar_batten, 'solid #6b4a2e': r_cedar_batten,
    'doorPanel': r_trim, 'solid #efeee9': r_trim,                                 # painted door / shutter panels
    'canLight': lambda m, c: r_simple(m, c, color='#f1efea', rough=0.4), 'solid #f2efe9': lambda m, c: r_simple(m, c, color='#f1efea', rough=0.4),
    'woodBeam': r_beam, 'teak': r_teak, 'woodOak': r_oak_millwork, 'oak': r_oak_floor,
    'coral': r_slab_paving, 'pavers': lambda m, c: r_slab_paving(m, c, 'limestone_pavers', 2.4, '#cfc3ad', slab=(0.6, 0.6)),
    'concrete': r_concrete, 'asphalt': r_asphalt,
    'ashlar': r_coral_wall, 'coralWall': r_coral_panel,
    'stepping': r_stepping, 'grassPavers': r_grass_pavers, 'poolTile': r_pool_shell,
    'linen': lambda m, c: r_fabric(m, c, '#e9e2d4'), 'linenWhite': lambda m, c: r_fabric(m, c, '#f0ece3', asset='canvas_white'),
    'linenSand': lambda m, c: r_fabric(m, c, '#d3c4aa'), 'linenSea': lambda m, c: r_fabric(m, c, '#9db1ae'),
    'jute': r_jute, 'rattan': r_rattan, 'quartz': r_quartz,
    'cane': lambda m, c: r_keep_tex(m, c, tint=(0.95, 0.88, 0.78), rough=0.6),
    'slats': lambda m, c: r_keep_tex(m, c, rough=0.6),
    'louver': lambda m, c: r_keep_tex(m, c, tint=(0.82, 0.74, 0.66), rough=0.6),
    'louverWhite': lambda m, c: r_keep_tex(m, c, rough=0.45),
    'louverGrey': lambda m, c: r_keep_tex(m, c, tint=(0.9, 0.9, 0.9), rough=0.45),
    'porcelain': lambda m, c: r_simple(m, c, color='#f4f3ef', rough=0.06, coat=0.6),
    'steel': lambda m, c: r_simple(m, c, color='#c4c7c9', rough=0.3, metallic=1.0, aniso=0.4),
    'brass': lambda m, c: r_simple(m, c, rough=0.3, metallic=1.0),
    'screen': lambda m, c: r_simple(m, c, color='#060708', rough=0.08, spec=0.6),
    'glow': r_glow, 'trunk': r_trunk, 'leaf': r_foliage,
    'waterfall': r_falls, 'massing window': r_dark_glass,
    'massing pool': lambda m, c: r_gloss_water(m, c, '#11606e', 0.05), 'pond': lambda m, c: r_gloss_water(m, c, '#16302c', 0.06),
}
# unnamed three.js materials, recognised by colour (src/neighborhood.js, src/site.js) - see needed changes
SIGNATURES = {'#6f8796': 'massing window', '#2aa0bf': 'massing pool', '#3d7f86': 'pond', '#8fd3df': 'waterfall'}
FOLIAGE_SOLIDS = ('solid #3d5f2c', 'solid #2f5a2a', 'solid #3d6a2c', 'solid #2c5527')
VEG_PREFIXES = ('plant ', 'palm ', 'areca ', 'coconut ', 'v-')          # palms.py / plants_bpy.py own these

def base_name(name):
    head, dot, tail = name.rpartition('.')
    return head if dot and tail.isdigit() else name

def recipe_for(m):
    name = base_name(m.name)
    if name in RECIPES: return name, RECIPES[name]
    if name.startswith('foliage') or name in FOLIAGE_SOLIDS: return name, r_foliage
    if name.startswith('glass'): return 'glass', r_glass
    if name.startswith('water'): return 'water', r_pool_water
    if name.startswith(VEG_PREFIXES): return name, None
    if name.startswith('Material_'):
        p = principled(m)
        if p and not p.inputs['Base Color'].links:
            hx = lin2hex(p.inputs['Base Color'].default_value)
            for sig, key in SIGNATURES.items():
                if max(abs(int(hx[i:i + 2], 16) - int(sig[i:i + 2], 16)) for i in (1, 3, 5)) <= 3:
                    return key, RECIPES[key]
    if name.startswith('solid #'):
        return name, r_solid
    return name, None

def r_solid(m, ctx):
    """Plain coloured furniture parts / accessories: give them a real finish by brightness."""
    p = principled(m)
    if not p or p.inputs['Base Color'].links: return
    c = p.inputs['Base Color'].default_value
    lum = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    sat = max(c[:3]) - min(c[:3])
    woody = c[0] > c[1] > c[2] and c[0] > 1.6 * c[2] and lum < 0.35
    if woody:                                            # slats, legs, frames: teak / oak by tone
        r_wood(m, ctx, 'teak', 1.0, lin2hex(c), sat=0.85, contrast=0.9, grime_amt=0.05)
    elif lum > 0.25 or (sat > 0.08 and lum > 0.1):      # cushions, throws, towels: woven textile
        r_fabric(m, ctx, lin2hex(c), tile=0.15, sheen=0.4)
    else:
        p.inputs['Roughness'].default_value = min(0.7, p.inputs['Roughness'].default_value)


def _set_object_props(log):
    """Per-object data the shaders read: wood grain axis (nh_axis) and, on pool shells, the depth below the
    piece's top edge (nh_wl, metres) for the waterline tile band; also scale the ocean to the horizon."""
    wood = {'woodBeam', 'teak', 'woodOak', 'cedar', 'cedarBatten', 'solid #6b4a2e'}
    done_mesh = set()
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.data.materials: continue
        names = {base_name(m.name) for m in o.data.materials if m}
        if names & wood or any(n.startswith('solid #') for n in names):
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            ext = [max(v[i] for v in bb) - min(v[i] for v in bb) for i in range(3)]
            o['nh_axis'] = float(max(range(3), key=lambda i: ext[i]))
        if 'poolTile' in names and o.data.name not in done_mesh:
            done_mesh.add(o.data.name)
            me = o.data
            sc = o.matrix_world.to_scale()
            # local up = the axis that maps to world Z
            R = o.matrix_world.to_3x3().normalized()
            up = R.inverted() @ Vector((0, 0, 1))
            hs = [v.co.dot(up) for v in me.vertices]
            top = max(hs); k = abs(sc[0])
            tall = (top - min(hs)) * k > 0.3                  # walls get the band; floor / bench slabs don't
            at = me.attributes.get('nh_wl') or me.attributes.new('nh_wl', 'FLOAT', 'POINT')
            at.data.foreach_set('value', [(top - h) * k if tall else 10.0 for h in hs])
        if 'ocean' in names:
            o.scale = (o.scale[0] * 25.0, o.scale[1] * 25.0, o.scale[2] * 25.0) if o.dimensions[1] > 1 else (o.scale[0] * 25.0, o.scale[1], o.scale[2] * 25.0)
            log(f'materials: ocean plane scaled to {o.dimensions[0] / 1000:.0f} km')


def _land_from_meta(meta, log):
    land = (meta or {}).get('land')
    if not land: return None
    try:
        if land.get('png', '').startswith('data:'):
            data = base64.b64decode(land['png'].split(',', 1)[1])
            path = os.path.join(tempfile.gettempdir(), f'nahiku_land_{os.getpid()}.png')
            open(path, 'wb').write(data)
        else:
            path = land['file'] if os.path.isabs(land['file']) else os.path.join(os.path.dirname(meta.get('_path', '.')), land['file'])
        img = bpy.data.images.load(path, check_existing=True); img.colorspace_settings.name = 'sRGB'
        img.alpha_mode = 'STRAIGHT'
        return {'img': img, 'box': land['box']}
    except Exception as e:
        log(f'materials: land map unusable ({e})')
        return None


def _lot_mask(meta, log):
    """Soft mask (1 = on a Na Hiku lot) in Blender world xy, from meta['lawn'] (lot rect + house offsets)."""
    lw = (meta or {}).get('lawn') or {}
    lot, houses = lw.get('lot'), lw.get('houses') or [[0, 0, 0]]
    if not lot or len(lot) != 4: return None
    try:
        import numpy as np
        from scipy.ndimage import gaussian_filter
        rects = []
        for dx, dy, dz in houses:
            x0, y0, x1, y1 = lot[0] + dx, lot[1] + dz, lot[2] + dx, lot[3] + dz      # three.js x / z (m)
            rects.append((x0, -y1, x1, -y0))                                          # Blender x / y
        bx0 = min(r[0] for r in rects) - 30; by0 = min(r[1] for r in rects) - 30
        bx1 = max(r[2] for r in rects) + 30; by1 = max(r[3] for r in rects) + 30
        res = 0.5; W = int((bx1 - bx0) / res); H = int((by1 - by0) / res)
        a = np.zeros((H, W), np.float32)
        for x0, y0, x1, y1 in rects:
            a[int((y0 - by0) / res):int((y1 - by0) / res), int((x0 - bx0) / res):int((x1 - bx0) / res)] = 1.0
        a = np.clip(gaussian_filter(a, 4.0 / res) * 1.6, 0, 1)
        img = bpy.data.images.new('nh_lots', W, H, alpha=False, float_buffer=True)
        img.colorspace_settings.name = 'Non-Color'
        px = np.repeat(a.reshape(-1, 1), 4, 1); px[:, 3] = 1.0
        img.pixels.foreach_set(px.ravel()); img.pack()
        return {'img': img, 'box': (bx0, by0, bx1 - bx0, by1 - by0)}
    except Exception as e:
        log(f'materials: lot mask failed ({e})')
        return None


def apply(meta=None, night=False, log=print, only=None, ocean_rough=0.3):
    """Rebuild every material of the imported scene by name. Materials made by palms.py / plants_bpy.py
    (vegetation) are left alone. Returns {recipe: [material names]}."""
    _set_object_props(log)
    terrain_attr = 'Color'
    for o in bpy.data.objects:
        if o.type == 'MESH' and any(m and m.name == 'terrain' for m in o.data.materials):
            ca = o.data.color_attributes
            if len(ca): terrain_attr = ca[0].name
            break
    ctx = {'night': night, 'meta': meta, 'land': _land_from_meta(meta, log), 'terrain_color_attr': terrain_attr,
           'ocean_rough': ocean_rough, 'lots': _lot_mask(meta, log)}
    used = {}
    for m in list(bpy.data.materials):
        if not m.node_tree or m.get('nh_done'): continue
        key, fn = recipe_for(m)
        if fn is None: continue
        if only and key not in only: continue
        try:
            fn(m, ctx)
            m['nh_done'] = 1
            used.setdefault(key, []).append(m.name)
        except Exception as e:
            import traceback; traceback.print_exc()
            log(f'materials: {m.name} failed: {e}')
    # glass and water don't block the sun (no caustics in the renders): the floor under them is lit
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.data.materials: continue
        names = [m.name.lower() for m in o.data.materials if m]
        if names and all(n.startswith(('glass', 'water')) or base_name(n) == 'waterfall' for n in names):
            o.visible_shadow = False
        if any(m and m.get('nh_kind') == 'ocean' for m in o.data.materials):
            o.visible_shadow = False
    log('materials: ' + ', '.join(f'{k}x{len(v)}' for k, v in sorted(used.items())))
    return used


# ------------------------------------------------------------------------------------------ sky and sun
def _hdri_file(name, nosun=True, max_res=0, log=print):
    e = manifest().get(name, {})
    rel = e.get('files', {}).get('hdr_nosun' if nosun else 'hdr') or e.get('files', {}).get('hdr')
    path = os.path.join(ASSETS, rel) if rel else os.path.join(ASSETS, 'hdri', name + ('_nosun' if nosun else '') + '.hdr')
    if not max_res: return path
    w = int(e.get('resolution', '0x0').split('x')[0] or 0)
    if w and w <= max_res: return path
    cache = os.path.join(tempfile.gettempdir(), 'nahiku_hdri')
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, f'{os.path.splitext(os.path.basename(path))[0]}_{max_res}.hdr')
    if not os.path.exists(out):
        img = bpy.data.images.load(path)
        img.scale(max_res, max_res // 2)
        img.filepath_raw = out; img.file_format = 'HDR'; img.save()
        bpy.data.images.remove(img)
        log(f'sky: cached {max_res}px copy of {name}')
    return out


def blackbody_rgb(T):
    """Linear Rec.709 colour of a blackbody at T kelvin (CIE 1931 2-deg CMFs, Wyman-Sloan-Shirley 2013 fit),
    normalised to luminance 1."""
    def g(x, mu, s1, s2): return math.exp(-0.5 * ((x - mu) / (s1 if x < mu else s2)) ** 2)
    X = Y = Z = 0.0
    for nm in range(380, 781, 5):
        l = nm * 1e-9
        B = 1.0 / (l ** 5 * (math.exp(1.4388e-2 / (l * T)) - 1.0))
        X += B * (1.056 * g(nm, 599.8, 37.9, 31.0) + 0.362 * g(nm, 442.0, 16.0, 26.7) - 0.065 * g(nm, 501.1, 20.4, 26.2))
        Y += B * (0.821 * g(nm, 568.8, 46.9, 40.5) + 0.286 * g(nm, 530.9, 16.3, 31.1))
        Z += B * (1.217 * g(nm, 437.0, 11.8, 36.0) + 0.681 * g(nm, 459.0, 26.0, 13.8))
    r = 3.2406 * X - 1.5372 * Y - 0.4986 * Z; gg = -0.9689 * X + 1.8758 * Y + 0.0415 * Z; b = 0.0557 * X - 0.2040 * Y + 1.0570 * Z
    r, gg, b = max(r, 0), max(gg, 0), max(b, 0)
    lum = 0.2126 * r + 0.7152 * gg + 0.0722 * b
    return (r / lum, gg / lum, b / lum)

def sun_color(elev_deg):
    """Direct sunlight through the air mass at this elevation: ~5800 K high in the sky (white-warm),
    falling to ~3600 K near the horizon. (The HDRI-measured sun colour carries the photographer's
    white balance - greenish for kloofendal - and is not used.)"""
    t = max(0.0, min(1.0, (elev_deg - 3.0) / 37.0)); t = t * t * (3 - 2 * t)
    return blackbody_rgb(3600.0 + 2200.0 * t)


def hdri_sun_azimuth(e):
    """Azimuth (radians, atan2(y, x) in Blender world XY) of the HDRI's sun, from the measured sun pixel.
    Cycles maps a direction to u = 0.5 - atan2(y, x) / 2pi (image centre = +X). The manifest's
    sun_azimuth_blender_deg / sun_dir_blender_unrotated use the opposite convention (180 deg off: verified
    in a render - the painted-out sun's glow came up in front of a camera that had the lamp behind it)."""
    rc, res = e.get('sun_pixel_row_col'), e.get('resolution')
    if rc and res:
        w = int(res.split('x')[0])
        return (0.5 - (rc[1] + 0.5) / w) * 2 * math.pi
    return math.radians(e.get('sun_azimuth_blender_deg', 0.0) + 180.0)


class World:
    """World shader + Sun lamp. mode='hdri': a photographed sky (assets/hdri, sun painted out) lights the
    scene and is the visible background; a Sun lamp at the view's sun direction carries the direct light
    with the HDRI's measured irradiance and colour; the sky is turned about the zenith so its own (removed)
    sun sits where the lamp is (aureole and cloud lighting agree with the shadows). mode='procedural':
    the Nishita multiple-scattering sky with painted clouds for camera rays (previous look).

    Exposes the names blender_render.py uses: nt, bg, camsky (Background nodes whose Strength the render
    modes set to 0.28 - the HDRI path is normalised so that 0.28 means `strength`), sky (Nishita node or
    None), sun, sun_data, set_sun(three.js dir)."""

    def __init__(self, scene, mode='hdri', hdri=DEFAULT_HDRI, strength=1.0, yaw=0.0, max_res=0,
                 cam_saturation=1.0, cam_value=1.0, polarizer=0.5, log=print):
        self.polarizer = polarizer; self.sun_vec = None
        self.scene, self.mode, self.yaw, self.log = scene, mode, math.radians(yaw), log
        world = bpy.data.worlds.new('sky'); scene.world = world
        if world.node_tree is None:
            try: world.use_nodes = True
            except Exception: pass
        nt = self.nt = world.node_tree
        for n in list(nt.nodes):
            if n.type != 'OUTPUT_WORLD': nt.nodes.remove(n)
        self.out = next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
        g = self.g = G(nt)
        self.sky = None; self.mapping = None
        self.sun_data = bpy.data.lights.new('sun', 'SUN')
        self.sun = bpy.data.objects.new('sun', self.sun_data); scene.collection.objects.link(self.sun)
        self.meta = manifest().get(hdri, {})
        if mode == 'hdri' and self.meta:
            self._hdri(hdri, strength, max_res, cam_saturation, cam_value)
        else:
            self.mode = 'procedural'
            self._procedural()
        try: world.cycles.sampling_method = 'MANUAL'; world.cycles.sample_map_resolution = 2048
        except Exception: pass

    # --- photographed sky
    def _hdri(self, name, strength, max_res, cam_sat, cam_val):
        g = self.g
        path = _hdri_file(name, True, max_res, self.log)
        img = bpy.data.images.load(path, check_existing=True)
        tc = g.texco()
        mp = self.mapping = g.node('ShaderNodeMapping', vector_type='POINT')
        g.put(mp.inputs['Vector'], tc.outputs['Generated'])
        env = g.node('ShaderNodeTexEnvironment', interpolation='Cubic'); env.image = img
        g.put(env.inputs['Vector'], mp.outputs[0])
        k = strength / PROC_STRENGTH
        lit = g.mix(1.0, env.outputs['Color'], (k, k, k), 'MULTIPLY')
        self.bg = g.node('ShaderNodeBackground'); g.put(self.bg.inputs['Color'], lit)
        cam = g.hsv(env.outputs['Color'], s=cam_sat, v=cam_val) if (cam_sat != 1.0 or cam_val != 1.0) else env.outputs['Color']
        if self.polarizer: cam = self._polarizer(cam, tc.outputs['Generated'])
        cam = g.mix(1.0, cam, (k, k, k), 'MULTIPLY')
        self.camsky = g.node('ShaderNodeBackground'); g.put(self.camsky.inputs['Color'], cam)
        lp = g.node('ShaderNodeLightPath')
        mix = g.node('ShaderNodeMixShader'); g.put(mix.inputs['Fac'], lp.outputs['Is Camera Ray'])
        g.L.new(self.bg.outputs[0], mix.inputs[1]); g.L.new(self.camsky.outputs[0], mix.inputs[2])
        g.L.new(mix.outputs[0], self.out.inputs['Surface'])
        # irradiance from the HDRI's measurement (luminance); colour from the sun's elevation (set_sun)
        self.sun_lum = self.meta.get('sun_irradiance_lum', self.meta.get('sun_strength_blender', 4.4)) * strength
        self._sun_rgb(50.0)
        self.sun_data.angle = math.radians(0.53)
        self.hdri_sun_az = hdri_sun_azimuth(self.meta)
        for env, mp, em, mg in HAZE:                        # aerial perspective = this sky at the horizon
            env.image = img
            mg.L.new(env.outputs['Color'], em.inputs['Color']); em.inputs['Strength'].default_value = strength
        self.log(f"sky: HDRI {name} ({os.path.basename(path)}), strength {strength}, sun {self.sun_data.energy:.2f} W/m2")

    def _polarizer(self, col, view):
        """Circular polariser on the lens, as real-estate photographers use in Hawaii: skylight is linearly
        polarised up to ~75% at 90 deg from the sun (Rayleigh: P = sin^2 t / (1 + cos^2 t)), much less in
        the horizon haze, and clouds hardly at all; the filter removes that share, so clear sky deepens
        and clouds stand out. Camera rays only (it is a filter, not a change of the light)."""
        g = self.g
        self.sun_vec = g.node('ShaderNodeCombineXYZ')
        d = g.vmath('NORMALIZE', view)
        c = g.vmath('DOT_PRODUCT', d, self.sun_vec.outputs[0], out=1)
        c2 = g.mul(c, c)
        P = g.math('DIVIDE', g.sub(1.0, c2), g.add(1.0, c2))
        _, _, z = g.sep(d)
        P = g.mul(P, g.maprange(z, 0.0, 0.3, 0.3, 0.75, smooth=True))
        r, gg, b = g.sep(col)
        mx = g.math('MAXIMUM', g.math('MAXIMUM', r, gg), b); mn = g.math('MINIMUM', g.math('MINIMUM', r, gg), b)
        clear = g.maprange(g.math('DIVIDE', g.sub(mx, mn), g.math('MAXIMUM', mx, 1e-4)), 0.12, 0.45)   # blue sky, not cloud
        k = g.mul(g.mul(P, clear), self.polarizer)
        col = g.hsv(col, s=g.add(1.0, g.mul(k, 0.9)), v=g.sub(1.0, g.mul(k, 0.85)))
        return col

    def _arch_bvh(self, centre, radius=90.0):
        """BVH of the built scene (no vegetation) within `radius` m of the camera, for metering."""
        from mathutils.bvhtree import BVHTree
        verts, polys = [], []
        for o in self.scene.objects:
            if o.type != 'MESH' or not o.data.materials or not o.visible_get(): continue
            if any(m and m.name.startswith(VEG_PREFIXES) for m in o.data.materials): continue
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            lo = Vector([min(q[i] for q in bb) for i in range(3)]); hi = Vector([max(q[i] for q in bb) for i in range(3)])
            near = Vector([min(max(centre[i], lo[i]), hi[i]) for i in range(3)])
            if (near - centre).length > radius: continue
            mw = o.matrix_world; me = o.data; k = len(verts)
            verts.extend(mw @ vv.co for vv in me.vertices)
            polys.extend([k + i for i in p.vertices] for p in me.polygons)
        return BVHTree.FromPolygons(verts, polys)

    def meter(self, v, compensation=0.82, nx=20, ny=12, nhemi=12, max_ev=4.6):
        """Average metering of an interior view, like a camera: rays through the frame; at each hit the
        share of sky it sees (cosine-weighted) and whether the sun reaches it, against the architecture
        (vegetation left out). An open sunlit exterior meters ~1. Returns the EV that lifts the view
        `compensation` of the way (in stops) to exterior brightness."""
        import random
        rng = random.Random(7)
        b = lambda q: Vector((q[0], -q[2], q[1]))
        pos, tgt = b(v['pos']), b(v['target'])
        bvh = self._arch_bvh(pos)
        cast = lambda o, d, dist: bvh.ray_cast(o, d, dist)
        fwd = (tgt - pos).normalized(); right = fwd.cross(Vector((0, 0, 1))).normalized(); up = right.cross(fwd)
        th = math.tan(math.radians(v.get('fov', 60)) / 2); tw = th * 1.6
        sun = b(v['sunDir']).normalized()
        tot = 0.0; n = 0
        for j in range(ny):
            for i in range(nx):
                d = (fwd + right * tw * ((i + 0.5) / nx * 2 - 1) + up * th * ((j + 0.5) / ny * 2 - 1)).normalized()
                P, N, _, _ = cast(pos, d, 2000.0)
                n += 1
                if P is None: tot += 1.0; continue
                if N.dot(d) > 0: N = -N
                o = P + N * 0.01
                t = N.orthogonal().normalized(); bv = N.cross(t)
                sky = 0
                for _ in range(nhemi):
                    u1, u2 = rng.random(), rng.random(); r_ = math.sqrt(u1); a = 2 * math.pi * u2
                    hd = (t * (r_ * math.cos(a)) + bv * (r_ * math.sin(a)) + N * math.sqrt(max(0.0, 1 - u1))).normalized()
                    if cast(o, hd, 300.0)[0] is None: sky += 1
                lit = 0.0
                if N.dot(sun) > 0 and cast(o, sun, 300.0)[0] is None: lit = N.dot(sun)
                tot += 0.3 * sky / nhemi + 0.7 * lit
        L = max(tot / n, 1e-3)
        return max(0.0, min(max_ev, -math.log2(L) * compensation))

    def auto_exposure(self, meta, base_ev=0.0, interior_ev=2.3, interior_wb=(4600.0, 18.0), meter=True, only=None,
                      lamps_w=15.0):
        """Interiors shot the way a real-estate photographer would: metered exposure (about +2 to +4.6 EV
        over the exterior; windows roll off in AgX), white balance on the walls (the light indoors is
        mostly sunlit-lawn and oak-floor bounce, yellow-green, which the camera neutralises), and the
        lamps switched on (warm 2700 K pendants / lamps from meta['lamps'], shades glowing). A
        render_pre handler matches the camera to the meta view it stands at."""
        lamp_objs = []
        if lamps_w and (meta or {}).get('lamps'):
            col = blackbody_rgb(2700.0); k = max(col); col = [c / k for c in col]
            for l in meta['lamps']:
                L = bpy.data.lights.new('day lamp', 'POINT'); L.energy = lamps_w; L.color = col; L.shadow_soft_size = 0.06
                o = bpy.data.objects.new('day lamp', L); self.scene.collection.objects.link(o)
                o.location = Vector((l['pos'][0], -l['pos'][2], l['pos'][1])); o.hide_render = True
                lamp_objs.append(o)
        glows = [m for m in bpy.data.materials if base_name(m.name) == 'glow' and principled(m)]
        views = []
        for vid, v in (meta or {}).get('views', {}).items():
            ev = 0.0
            if v.get('interior'):
                ev = interior_ev
                if interior_ev and meter and (not only or vid in only):
                    try: ev = self.meter(v, compensation=interior_ev / 2.8)
                    except Exception as e: self.log(f'sky: metering {vid} failed ({e})')
                if not only or vid in only: self.log(f'sky: {vid} exposed +{ev:.2f} EV')
            views.append((Vector((v['pos'][0], -v['pos'][2], v['pos'][1])), bool(v.get('interior')), ev))
        def pre(sc, *_):
            cam = sc.camera
            if cam is None or cam.data.type != 'PERSP': return
            hit = min(views, key=lambda pv: (pv[0] - cam.location).length, default=None)
            inside = hit is not None and (hit[0] - cam.location).length < 0.05 and hit[1]
            vs = sc.view_settings
            vs.exposure = base_ev + (hit[2] if inside else 0.0)
            try:
                vs.use_white_balance = bool(inside and interior_wb)
                if inside and interior_wb: vs.white_balance_temperature, vs.white_balance_tint = interior_wb
            except Exception: pass
            for o in lamp_objs: o.hide_render = not inside
            for m in glows:
                p = principled(m); p.inputs['Emission Color'].default_value = (1.0, 0.78, 0.52, 1)
                p.inputs['Emission Strength'].default_value = 4.0 if inside else 0.0
        for h in [h for h in bpy.app.handlers.render_pre if getattr(h, '__name__', '') == 'nh_exposure']:
            bpy.app.handlers.render_pre.remove(h)
        pre.__name__ = 'nh_exposure'
        bpy.app.handlers.render_pre.append(pre)

    # --- Nishita sky + painted clouds (the previous look; also what --night builds on)
    def _procedural(self):
        nt, g = self.nt, self.g
        self.bg = g.node('ShaderNodeBackground')
        nt.links.new(self.bg.outputs['Background'], self.out.inputs['Surface'])
        sky = self.sky = nt.nodes.new('ShaderNodeTexSky')
        sky.sky_type = 'MULTIPLE_SCATTERING'
        sky.sun_disc = False
        sky.altitude = 60.0
        sky.air_density = 1.0; sky.aerosol_density = 0.35; sky.ozone_density = 1.2
        nt.links.new(sky.outputs['Color'], self.bg.inputs['Color'])
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
        self.camsky = nt.nodes.new('ShaderNodeBackground'); nt.links.new(white.outputs[2], self.camsky.inputs['Color'])
        lp = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(self.bg.outputs['Background'], mix.inputs[1]); nt.links.new(self.camsky.outputs['Background'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], self.out.inputs['Surface'])
        self.sun_data.energy = 4.2; self.sun_data.angle = math.radians(0.6); self.sun_data.color = (1.0, 0.93, 0.84)
        self.log('sky: procedural (Nishita + painted clouds)')

    def _sun_rgb(self, elev):
        c = sun_color(elev); k = max(c)
        self.sun_data.color = [v / k for v in c]
        self.sun_data.energy = getattr(self, 'sun_lum', 4.4) * k        # luminance irradiance unchanged

    def set_sun(self, d3):
        """d3: three.js direction toward the sun (y up)."""
        d = Vector((d3[0], -d3[2], d3[1])).normalized()
        self.sun.rotation_mode = 'QUATERNION'
        self.sun.rotation_quaternion = (-d).to_track_quat('-Z', 'Y')
        if self.sky is not None:
            self.sky.sun_elevation = math.asin(max(-1, min(1, d.z)))
            self.sky.sun_rotation = math.atan2(d.x, -d.y)
        if self.sun_vec is not None:
            for i, v in enumerate(d): self.sun_vec.inputs[i].default_value = v
        if self.mode == 'hdri':
            self._sun_rgb(math.degrees(math.asin(max(-1, min(1, d.z)))))
        if self.mapping is not None:
            az = math.atan2(d.y, d.x)
            rot = (0.0, 0.0, self.hdri_sun_az - az + self.yaw)
            self.mapping.inputs['Rotation'].default_value = rot
            for env, mp, em, mg in HAZE: mp.inputs['Rotation'].default_value = rot
