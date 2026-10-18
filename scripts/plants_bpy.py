"""Garden planting for the path tracer, grown leaf by leaf (the palms are in scripts/palms.py).

In export mode three.js only records where the planting goes (src/plants.js, src/site.js ->
nahiku-meta.json 'plants' and 'lawn'); here every plant is built from real geometry:

  - lawn: a manicured turf of individual grass blades (instanced 0.5 m tiles, edge tiles of 12.5 cm)
    on every bit of open ground of our lot and the nearest neighbours; beds get bark mulch (the real
    photo scan in assets/textures/ground/bark_mulch), draped on the ground but never up a wall
  - shrubs (bougainvillea, gardenia, hedge, groundcover): twigs carrying hundreds of leaves, with
    bracts and flowers (bougainvillea also throws long arching canes); ti plants on bare canes;
    monstera with split, fenestrated leaves on long petioles
  - plumeria trees (a short trunk forking low into thick candelabra limbs, leaf rosettes, white and
    yellow flowers)
  - the background trees: dome (mango, kamani), umbrella (monkeypod) and tall (java plum) forms,
    grown inside lumpy crown envelopes (trunk, scaffold limbs, branches, twigs, leaf clumps), set in
    groves of two to four

Each kind is built as a handful of variants and instanced with geometry nodes, so a neighbourhood
of planting costs little memory. Leaves carry procedural vein textures, per-leaf colour variation,
gloss and translucency.

    import plants_bpy; plants_bpy.build(meta, b)        # b: three.js world (metres) -> Blender
"""
import math, os, time
import numpy as np
import bpy
from mathutils import Vector, Matrix

UP = np.array([0.0, 0.0, 1.0])
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'textures')
GOLDEN = math.radians(137.508)


def _norm(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def _lin(hexstr):
    h = hexstr.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple([x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0])


def _rand_dirs(rng, n):
    v = rng.normal(size=(n, 3)); return _norm(v)


def _frame(T):
    """Two unit vectors perpendicular to each row of T."""
    ref = np.where(np.abs(T[:, 2:3]) < 0.9, UP, np.array([1.0, 0, 0]))
    e1 = _norm(np.cross(T, ref)); e2 = np.cross(T, e1)
    return e1, e2


# ---------------------------------------------------------------- mesh buffers
class Buf:
    """Polygons (any mix of triangles and quads), per-vertex UVs, a material slot per polygon."""
    def __init__(self):
        self.v, self.uv, self.polys = [], [], {}
        self.n = 0

    def add(self, verts, faces, uv=None, mat=0):
        verts = np.asarray(verts, np.float32).reshape(-1, 3)
        faces = np.asarray(faces, np.int64)
        if not len(verts) or not len(faces): return
        self.v.append(verts)
        self.uv.append(np.zeros((len(verts), 2), np.float32) if uv is None else np.asarray(uv, np.float32).reshape(-1, 2))
        k = faces.shape[1]
        self.polys.setdefault(k, []).append((faces + self.n, np.full(len(faces), mat, np.int32)))
        self.n += len(verts)

    def extend(self, other, mat_map=None):
        if not other.v: return
        for k, parts in other.polys.items():
            for f, m in parts:
                self.polys.setdefault(k, []).append((f + self.n, m if mat_map is None else np.asarray(mat_map)[m]))
        self.v += other.v; self.uv += other.uv; self.n += other.n

    def transformed(self, R, t):
        o = Buf(); o.v = [v @ np.asarray(R, np.float32).T + np.asarray(t, np.float32) for v in self.v]; o.uv = list(self.uv)
        o.polys = {k: list(p) for k, p in self.polys.items()}; o.n = self.n
        return o

    def mesh(self, name, materials):
        V = np.concatenate(self.v) if self.v else np.zeros((0, 3), np.float32)
        UV = np.concatenate(self.uv) if self.uv else np.zeros((0, 2), np.float32)
        loops, starts, totals, mats = [], [], [], []
        off = 0
        for k in sorted(self.polys):
            F = np.concatenate([f for f, _ in self.polys[k]]); M = np.concatenate([m for _, m in self.polys[k]])
            loops.append(F.ravel()); totals.append(np.full(len(F), k, np.int32)); starts.append(off + np.arange(len(F), dtype=np.int32) * k); mats.append(M)
            off += F.size
        loops = np.concatenate(loops).astype(np.int32); starts = np.concatenate(starts); totals = np.concatenate(totals); mats = np.concatenate(mats)
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(V)); me.vertices.foreach_set('co', V.ravel())
        me.loops.add(len(loops)); me.loops.foreach_set('vertex_index', loops)
        me.polygons.add(len(starts)); me.polygons.foreach_set('loop_start', starts); me.polygons.foreach_set('loop_total', totals)
        me.polygons.foreach_set('material_index', mats)
        lay = me.uv_layers.new(name='UVMap'); lay.data.foreach_set('uv', UV[loops].ravel())
        for m in materials: me.materials.append(m)
        me.update(calc_edges=True)
        try: me.shade_smooth()
        except Exception: me.polygons.foreach_set('use_smooth', np.ones(len(starts), bool))
        return me


# ---------------------------------------------------------------- leaf templates
class Tpl:
    """A unit leaf (or petal, bract, blade): base at the origin, length 1 along +Y, upper side +Z."""
    def __init__(self, v, f, uv):
        self.v = np.asarray(v, np.float32); self.f = np.asarray(f, np.int64); self.uv = np.asarray(uv, np.float32)


def leaf_tpl(profile, stations=(0, 0.08, 0.22, 0.4, 0.6, 0.78, 0.92, 1.0), cols=2, fold=0.1, arch=0.12, cup=0.0, twist=0.0, tip_curl=0.0):
    """profile(t) -> half width (in lengths). fold: V of the two halves; arch: droop of the tip (in lengths);
    cup: the margins curl up; twist: radians of twist toward the tip."""
    S = np.linspace(-1, 1, 2 * cols + 1)
    V, UV = [], []
    for t in stations:
        hw = profile(t)
        ang = twist * t
        for s in S:
            x = s * hw
            z = fold * abs(x) + cup * (s * s) * hw - arch * t * t - tip_curl * max(0.0, t - 0.8) ** 2 * 10
            xr, zr = x * math.cos(ang) - z * math.sin(ang), x * math.sin(ang) + z * math.cos(ang)
            V.append((xr, t, zr)); UV.append(((s + 1) / 2, t))
    nc = len(S); F = []
    for i in range(len(stations) - 1):
        for j in range(nc - 1):
            a = i * nc + j
            F.append((a, a + 1, a + nc + 1, a + nc))
    return Tpl(V, F, UV)


def P_ELLIPTIC(r=0.25, base=0.5, tip=1.0):
    return lambda t: r * max(0.0, math.sin(math.pi * min(1.0, t)) ** 0.75) * (1 - 0.15 * t) if t > 0 else r * 0.06


def place(buf, tpl, P, D, N, L, A=None, mat=0, uv_jitter=None):
    """Instances tpl at P (n,3) pointing along D, upper side toward N, length L (n,), width scale A (n,)."""
    n = len(P)
    if n == 0: return
    y = _norm(D); x = _norm(np.cross(y, N)); z = np.cross(x, y)
    A = np.ones(n) if A is None else A
    tv = tpl.v
    W = (L * A)[:, None, None]; Ln = L[:, None, None]
    out = P[:, None, :] + tv[None, :, 0:1] * W * x[:, None, :] + tv[None, :, 1:2] * Ln * y[:, None, :] + tv[None, :, 2:3] * Ln * z[:, None, :]
    m = len(tv)
    F = (tpl.f[None, :, :] + (np.arange(n) * m)[:, None, None]).reshape(-1, tpl.f.shape[1])
    uv = np.broadcast_to(tpl.uv, (n, m, 2)).reshape(-1, 2)
    buf.add(out.reshape(-1, 3), F, uv, mat)


def tubes(buf, paths, radii, sides=6, mat=0, v_scale=1.0):
    """Many tubes at once: paths (n,k,3), radii (n,k). UV v = metres along (for bark), u around."""
    paths = np.asarray(paths, float); radii = np.asarray(radii, float)
    n, k, _ = paths.shape
    if n == 0: return
    T = _norm(np.gradient(paths, axis=1)) if k > 1 else np.tile(UP, (n, 1, 1))
    ref = np.where(np.abs(T[..., 2:3]) < 0.95, UP, np.array([1.0, 0, 0]))
    e1 = _norm(np.cross(T, ref)); e2 = np.cross(T, e1)
    th = np.linspace(0, 2 * math.pi, sides + 1)
    ring = np.cos(th)[None, None, :, None] * e1[:, :, None, :] + np.sin(th)[None, None, :, None] * e2[:, :, None, :]
    V = paths[:, :, None, :] + radii[:, :, None, None] * ring                      # (n,k,s+1,3)
    seg = np.linalg.norm(np.diff(paths, axis=1), axis=-1)
    vv = np.concatenate([np.zeros((n, 1)), np.cumsum(seg, axis=1)], axis=1) * v_scale
    UV = np.stack([np.broadcast_to(th[None, None, :] / (2 * math.pi), (n, k, sides + 1)), np.broadcast_to(vv[:, :, None], (n, k, sides + 1))], -1)
    m = k * (sides + 1)
    i, j = np.meshgrid(np.arange(k - 1), np.arange(sides), indexing='ij')
    a = (i * (sides + 1) + j).ravel()
    f = np.stack([a, a + 1, a + sides + 2, a + sides + 1], -1)
    F = (f[None] + (np.arange(n) * m)[:, None, None]).reshape(-1, 4)
    buf.add(V.reshape(-1, 3), F, UV.reshape(-1, 2), mat)


def curve(p0, p1, sag, k=5, bow=None):
    """(n,k,3) quadratic curves from p0 to p1 sagging/bowing by `sag` (n,3) at the middle."""
    t = np.linspace(0, 1, k)[None, :, None]
    mid = (p0 + p1) / 2 + sag
    return (1 - t) ** 2 * p0[:, None, :] + 2 * (1 - t) * t * mid[:, None, :] + t * t * p1[:, None, :]


# ---------------------------------------------------------------- procedural leaf images
def _noise(rng, H, W, scale, octaves=3):
    from scipy.ndimage import zoom
    out = np.zeros((H, W))
    for o in range(octaves):
        s = max(2, int(scale * 2 ** o))
        g = rng.random((s + 3, s + 3))
        z = zoom(g, ((H + 2 * H / s) / (s + 3), (W + 2 * W / s) / (s + 3)), order=3)[:H, :W]
        out += (z - 0.5) / 2 ** o
    return out


def _image(name, rgb, colorspace='Linear Rec.709'):
    H, W = rgb.shape[:2]
    img = bpy.data.images.new(name, W, H, alpha=True, float_buffer=True)
    px = np.ones((H, W, 4), np.float32); px[..., :rgb.shape[2]] = rgb
    if rgb.shape[2] == 1: px[..., 1] = px[..., 2] = rgb[..., 0]
    img.pixels.foreach_set(px.ravel())
    try: img.colorspace_settings.name = colorspace
    except Exception: pass
    img.pixels.foreach_set(px.ravel())
    img.update()
    return img


def leaf_image(name, seed, base, mid, *, W=256, H=512, n_veins=9, angle=55, vein=0.35, vein_w=0.010, margin=0.25,
               mott=0.12, aspect=0.3, sunken=True, reticulate=0.15, edge=None, variegate=None, base_tint=None):
    """Albedo (linear RGB) + height for a pinnate leaf in UV space (u across 0..1, v base->tip)."""
    rng = np.random.default_rng(seed)
    u = (np.arange(W) + 0.5)[None, :] / W; v = (np.arange(H) + 0.5)[:, None] / H
    x = (u - 0.5) * 2; ax = np.abs(x)
    mw = 0.03 * (1.1 - 0.8 * v)
    midrib = np.exp(-(ax / mw) ** 2)
    k = aspect / math.tan(math.radians(angle))
    ph = (v - ax * k * (1 + 0.6 * ax) + 0.02 * _noise(rng, H, W, 6, 2)) * n_veins
    fr = ph - np.floor(ph); d = np.minimum(fr, 1 - fr) / n_veins
    lat = np.exp(-(d / (vein_w * (1.2 - 0.6 * ax))) ** 2) * np.clip((ax - mw) * 30, 0, 1) * (1 - ax ** 3 * 0.85) * (v < 0.97)
    ret = np.abs(_noise(rng, H, W, 40, 2)); ret = np.exp(-(ret / 0.03) ** 2) * reticulate
    veins = np.clip(np.maximum(midrib, lat * vein) + ret * 0.5, 0, 1)
    base = np.array(base[:3]); mid = np.array(mid[:3])
    n1 = _noise(rng, H, W, 5, 3)
    col = base[None, None, :] * (1 + mott * n1[..., None])
    col *= (1 - margin * ax ** 3)[..., None]
    col *= (0.92 + 0.12 * v)[..., None] if base_tint is None else 1
    if base_tint is not None:
        bt = np.clip(1 - v / 0.35, 0, 1)[..., None]
        col = col * (1 - bt) + np.array(base_tint[:3]) * bt
    if variegate is not None:                                    # pink / cream margins and streaks (ti)
        vc, w = variegate
        st = np.clip((ax - (1 - w)) / max(w, 1e-3) + 0.15 * _noise(rng, H, W, 8, 2), 0, 1)
        col = col * (1 - st[..., None]) + np.array(vc[:3]) * st[..., None]
    col = col * (1 - veins[..., None]) + mid[None, None, :] * veins[..., None]
    if edge is not None:
        e = np.clip((ax - 0.94) / 0.06, 0, 1)[..., None]
        col = col * (1 - e) + np.array(edge[:3]) * e
    height = (-veins if sunken else veins) * 0.6 + 0.08 * n1
    return _image(name, np.clip(col, 0, 1).astype(np.float32)), _image(name + '-h', height[..., None].astype(np.float32) * 0.5 + 0.5, 'Non-Color')


# ---------------------------------------------------------------- materials
def _nodes(m):
    m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    return nt, nt.nodes, nt.links


def leaf_material(name, img, himg, *, rough=0.4, spec=0.5, transl=0.3, bump=0.25, hue_var=0.03, val_var=0.18, sat_var=0.1,
                  trans_tint=(1.25, 1.35, 0.6), back=(1.15, 1.2, 1.1), dry=None, dry_share=0.0, coat=0.0, sheen=0.0):
    """Leaf: image albedo x per-leaf (island) and per-plant variation, two-sided with a paler underside,
    thin-leaf translucency, vein bump; `dry` blends some leaves toward a yellow/brown."""
    m = bpy.data.materials.new(name)
    nt, N, L = _nodes(m)
    out = N.new('ShaderNodeOutputMaterial')
    uvn = N.new('ShaderNodeUVMap'); uvn.uv_map = 'UVMap'
    tex = N.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Linear'; tex.extension = 'EXTEND'
    L.new(uvn.outputs['UV'], tex.inputs['Vector'])
    geo = N.new('ShaderNodeNewGeometry'); oi = N.new('ShaderNodeObjectInfo')
    # per-leaf hue/value/saturation shifts
    def rnd_shift(seed_mul, amp, src):
        mm = N.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; mm.inputs[1].default_value = seed_mul
        L.new(src, mm.inputs[0])
        fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(mm.outputs[0], fr.inputs[0])
        ma = N.new('ShaderNodeMapRange'); ma.inputs['To Min'].default_value = 1 - amp; ma.inputs['To Max'].default_value = 1 + amp
        L.new(fr.outputs[0], ma.inputs['Value'])
        return ma.outputs['Result']
    isl = geo.outputs['Random Per Island']
    add = N.new('ShaderNodeMath'); add.operation = 'ADD'
    L.new(isl, add.inputs[0]); mo = N.new('ShaderNodeMath'); mo.operation = 'MULTIPLY'; mo.inputs[1].default_value = 0.37
    L.new(oi.outputs['Random'], mo.inputs[0]); L.new(mo.outputs[0], add.inputs[1])
    hsv = N.new('ShaderNodeHueSaturation')
    hu = N.new('ShaderNodeMapRange'); hu.inputs['To Min'].default_value = 0.5 - hue_var; hu.inputs['To Max'].default_value = 0.5 + hue_var
    hm = N.new('ShaderNodeMath'); hm.operation = 'FRACT'; hm2 = N.new('ShaderNodeMath'); hm2.operation = 'MULTIPLY'; hm2.inputs[1].default_value = 3.17
    L.new(add.outputs[0], hm2.inputs[0]); L.new(hm2.outputs[0], hm.inputs[0]); L.new(hm.outputs[0], hu.inputs['Value'])
    L.new(hu.outputs['Result'], hsv.inputs['Hue'])
    L.new(rnd_shift(7.13, sat_var, add.outputs[0]), hsv.inputs['Saturation'])
    L.new(rnd_shift(1.0, val_var, add.outputs[0]), hsv.inputs['Value'])
    L.new(tex.outputs['Color'], hsv.inputs['Color'])
    col = hsv.outputs['Color']
    if dry is not None and dry_share > 0:
        pick = N.new('ShaderNodeMath'); pick.operation = 'FRACT'; pm = N.new('ShaderNodeMath'); pm.operation = 'MULTIPLY'; pm.inputs[1].default_value = 13.7
        L.new(isl, pm.inputs[0]); L.new(pm.outputs[0], pick.inputs[0])
        lt = N.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; lt.inputs[1].default_value = dry_share; L.new(pick.outputs[0], lt.inputs[0])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[7].default_value = dry
        L.new(lt.outputs[0], mx.inputs['Factor']); L.new(col, mx.inputs[6]); col = mx.outputs[2]
    # paler, greyer underside
    bk = N.new('ShaderNodeMix'); bk.data_type = 'RGBA'; bk.blend_type = 'MULTIPLY'; bk.inputs[7].default_value = (*back, 1)
    L.new(geo.outputs['Backfacing'], bk.inputs['Factor']); L.new(col, bk.inputs[6]); col = bk.outputs[2]
    p = N.new('ShaderNodeBsdfPrincipled')
    p.inputs['Roughness'].default_value = rough
    p.inputs['Specular IOR Level'].default_value = spec
    if coat:
        p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = 0.12
    if sheen:
        p.inputs['Sheen Weight'].default_value = sheen; p.inputs['Sheen Roughness'].default_value = 0.4
    L.new(col, p.inputs['Base Color'])
    if bump:
        ht = N.new('ShaderNodeTexImage'); ht.image = himg; ht.extension = 'EXTEND'; L.new(uvn.outputs['UV'], ht.inputs['Vector'])
        bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = bump; bu.inputs['Distance'].default_value = 0.0015
        L.new(ht.outputs['Color'], bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    tr = N.new('ShaderNodeBsdfTranslucent')
    tt = N.new('ShaderNodeMix'); tt.data_type = 'RGBA'; tt.blend_type = 'MULTIPLY'; tt.inputs['Factor'].default_value = 1.0
    tt.inputs[7].default_value = (*trans_tint, 1); L.new(col, tt.inputs[6]); L.new(tt.outputs[2], tr.inputs['Color'])
    ms = N.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = transl
    L.new(p.outputs['BSDF'], ms.inputs[1]); L.new(tr.outputs['BSDF'], ms.inputs[2])
    L.new(ms.outputs['Shader'], out.inputs['Surface'])
    return m


def bark_material(name, base, dark, *, rough=0.85, scale=6.0, rings=0.0, ring_col=None, lichen=None, bump=0.4, stretch=4.0):
    m = bpy.data.materials.new(name)
    nt, N, L = _nodes(m)
    out = N.new('ShaderNodeOutputMaterial'); p = N.new('ShaderNodeBsdfPrincipled'); p.inputs['Roughness'].default_value = rough
    L.new(p.outputs['BSDF'], out.inputs['Surface'])
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (stretch, stretch, 1.0)
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    no = N.new('ShaderNodeTexNoise'); no.inputs['Scale'].default_value = scale; no.inputs['Detail'].default_value = 8; no.inputs['Roughness'].default_value = 0.65
    L.new(mp.outputs['Vector'], no.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); e = ramp.color_ramp.elements
    e[0].position = 0.35; e[0].color = dark; e[1].position = 0.7; e[1].color = base
    L.new(no.outputs['Fac'], ramp.inputs['Fac'])
    col = ramp.outputs['Color']
    if lichen is not None:
        bl = N.new('ShaderNodeTexNoise'); bl.inputs['Scale'].default_value = 3.0; bl.inputs['Detail'].default_value = 6
        L.new(tc.outputs['Object'], bl.inputs['Vector'])
        lm = N.new('ShaderNodeMapRange'); lm.inputs['From Min'].default_value = 0.6; lm.inputs['From Max'].default_value = 0.72
        L.new(bl.outputs['Fac'], lm.inputs['Value'])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[7].default_value = lichen
        L.new(lm.outputs['Result'], mx.inputs['Factor']); L.new(col, mx.inputs[6]); col = mx.outputs[2]
    hgt = no.outputs['Fac']
    if rings:
        uvn = N.new('ShaderNodeUVMap'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(uvn.outputs['UV'], sep.inputs[0])
        d = N.new('ShaderNodeMath'); d.operation = 'MULTIPLY'; d.inputs[1].default_value = 1.0 / rings; L.new(sep.outputs['Y'], d.inputs[0])
        fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(d.outputs[0], fr.inputs[0])
        rv = N.new('ShaderNodeMapRange'); rv.interpolation_type = 'SMOOTHSTEP'; rv.inputs['From Min'].default_value = 0.0; rv.inputs['From Max'].default_value = 0.18
        L.new(fr.outputs[0], rv.inputs['Value'])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[6].default_value = ring_col or dark
        L.new(rv.outputs['Result'], mx.inputs['Factor']); L.new(col, mx.inputs[7]); col = mx.outputs[2]
        ad = N.new('ShaderNodeMath'); ad.operation = 'MULTIPLY_ADD'; ad.inputs[1].default_value = 0.3
        L.new(no.outputs['Fac'], ad.inputs[0]); L.new(rv.outputs['Result'], ad.inputs[2]); hgt = ad.outputs[0]
    L.new(col, p.inputs['Base Color'])
    bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = bump; bu.inputs['Distance'].default_value = 0.004
    L.new(hgt, bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    return m


def petal_material(name, base, center=None, *, center_len=0.35, transl=0.45, rough=0.45, sheen=0.3, vein_img=None):
    """White / magenta petals and bracts: translucent, soft sheen; `center` colours the petal base (plumeria yellow)."""
    m = bpy.data.materials.new(name)
    nt, N, L = _nodes(m)
    out = N.new('ShaderNodeOutputMaterial'); p = N.new('ShaderNodeBsdfPrincipled')
    p.inputs['Roughness'].default_value = rough; p.inputs['Sheen Weight'].default_value = sheen; p.inputs['Specular IOR Level'].default_value = 0.4
    geo = N.new('ShaderNodeNewGeometry')
    col_src = None
    if vein_img is not None:
        uvn = N.new('ShaderNodeUVMap'); tex = N.new('ShaderNodeTexImage'); tex.image = vein_img; tex.extension = 'EXTEND'
        L.new(uvn.outputs['UV'], tex.inputs['Vector']); col_src = tex.outputs['Color']
    if center is not None:
        uvn = N.new('ShaderNodeUVMap'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(uvn.outputs['UV'], sep.inputs[0])
        mr = N.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'; mr.inputs['From Min'].default_value = center_len; mr.inputs['From Max'].default_value = center_len * 0.25
        L.new(sep.outputs['Y'], mr.inputs['Value'])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[6].default_value = base; mx.inputs[7].default_value = center
        if col_src is not None: L.new(col_src, mx.inputs[6])
        L.new(mr.outputs['Result'], mx.inputs['Factor']); col_src = mx.outputs[2]
    hsv = N.new('ShaderNodeHueSaturation'); hsv.inputs['Color'].default_value = base
    if col_src is not None: L.new(col_src, hsv.inputs['Color'])
    vr = N.new('ShaderNodeMapRange'); vr.inputs['To Min'].default_value = 0.88; vr.inputs['To Max'].default_value = 1.08
    L.new(geo.outputs['Random Per Island'], vr.inputs['Value']); L.new(vr.outputs['Result'], hsv.inputs['Value'])
    L.new(hsv.outputs['Color'], p.inputs['Base Color'])
    tr = N.new('ShaderNodeBsdfTranslucent'); L.new(hsv.outputs['Color'], tr.inputs['Color'])
    ms = N.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = transl
    L.new(p.outputs['BSDF'], ms.inputs[1]); L.new(tr.outputs['BSDF'], ms.inputs[2]); L.new(ms.outputs['Shader'], out.inputs['Surface'])
    return m


def plain_material(name, color, rough=0.6, transl=0.0):
    m = bpy.data.materials.new(name); nt, N, L = _nodes(m)
    out = N.new('ShaderNodeOutputMaterial'); p = N.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = color; p.inputs['Roughness'].default_value = rough
    if transl:
        tr = N.new('ShaderNodeBsdfTranslucent'); tr.inputs['Color'].default_value = color
        ms = N.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = transl
        L.new(p.outputs['BSDF'], ms.inputs[1]); L.new(tr.outputs['BSDF'], ms.inputs[2]); L.new(ms.outputs['Shader'], out.inputs['Surface'])
    else:
        L.new(p.outputs['BSDF'], out.inputs['Surface'])
    return m


def _asset(*parts):
    p = os.path.join(ASSETS, *parts)
    return p if os.path.exists(p) else None


def _load(path, colorspace):
    im = bpy.data.images.load(path, check_existing=True)
    try: im.colorspace_settings.name = colorspace
    except Exception: pass
    return im


def photo_ground_material(name, folder, tile_m, *, tint=(1, 1, 1), rot=0.0, bump=1.0, var=0.12):
    """A real photo-scanned ground texture (assets/textures/<folder>/color, normal, roughness) laid in
    world space (tile_m metres a tile), two scales mixed to hide the repeat, slight value variation."""
    m = bpy.data.materials.new(name); nt, N, L = _nodes(m)
    out = N.new('ShaderNodeOutputMaterial'); p = N.new('ShaderNodeBsdfPrincipled')
    L.new(p.outputs['BSDF'], out.inputs['Surface'])
    geo = N.new('ShaderNodeNewGeometry')
    def mapped(scale, angle):
        mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1 / scale, 1 / scale, 1); mp.inputs['Rotation'].default_value = (0, 0, angle)
        L.new(geo.outputs['Position'], mp.inputs['Vector']); return mp.outputs['Vector']
    v1, v2 = mapped(tile_m, rot), mapped(tile_m * 1.37, rot + 0.9)
    blend = N.new('ShaderNodeTexNoise'); blend.inputs['Scale'].default_value = 0.6; blend.inputs['Detail'].default_value = 2
    L.new(geo.outputs['Position'], blend.inputs['Vector'])
    bm = N.new('ShaderNodeMapRange'); bm.inputs['From Min'].default_value = 0.42; bm.inputs['From Max'].default_value = 0.58
    L.new(blend.outputs['Fac'], bm.inputs['Value'])
    def tex(fname, cs):
        a = N.new('ShaderNodeTexImage'); a.image = _load(os.path.join(folder, fname), cs); L.new(v1, a.inputs['Vector'])
        b_ = N.new('ShaderNodeTexImage'); b_.image = a.image; L.new(v2, b_.inputs['Vector'])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; L.new(bm.outputs['Result'], mx.inputs['Factor'])
        L.new(a.outputs['Color'], mx.inputs[6]); L.new(b_.outputs['Color'], mx.inputs[7])
        return mx.outputs[2]
    col = tex('color.jpg', 'sRGB')
    vn = N.new('ShaderNodeTexNoise'); vn.inputs['Scale'].default_value = 0.25; L.new(geo.outputs['Position'], vn.inputs['Vector'])
    vm = N.new('ShaderNodeMapRange'); vm.inputs['To Min'].default_value = 1 - var; vm.inputs['To Max'].default_value = 1 + var
    vm.inputs['From Min'].default_value = 0.3; vm.inputs['From Max'].default_value = 0.7
    L.new(vn.outputs['Fac'], vm.inputs['Value'])
    hs = N.new('ShaderNodeHueSaturation'); L.new(col, hs.inputs['Color']); L.new(vm.outputs['Result'], hs.inputs['Value'])
    tn = N.new('ShaderNodeMix'); tn.data_type = 'RGBA'; tn.blend_type = 'MULTIPLY'; tn.inputs['Factor'].default_value = 1.0; tn.inputs[7].default_value = (*tint, 1)
    L.new(hs.outputs['Color'], tn.inputs[6]); L.new(tn.outputs[2], p.inputs['Base Color'])
    if os.path.exists(os.path.join(folder, 'roughness.jpg')):
        L.new(tex('roughness.jpg', 'Non-Color'), p.inputs['Roughness'])
    else:
        p.inputs['Roughness'].default_value = 0.9
    if os.path.exists(os.path.join(folder, 'normal.jpg')):
        nm = N.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = bump
        L.new(tex('normal.jpg', 'Non-Color'), nm.inputs['Color']); L.new(nm.outputs['Normal'], p.inputs['Normal'])
    return m


def mulch_material():
    """Shredded bark mulch: the real photo scan (assets/textures/ground/bark_mulch) when present,
    else dark brown chips (voronoi cells) with lighter dry tops and soil between."""
    f = _asset('ground', 'bark_mulch')
    if f and os.path.exists(os.path.join(f, 'color.jpg')):
        return photo_ground_material('plant mulch', f, 1.5, tint=(0.66, 0.56, 0.48), bump=1.2)    # one dark-brown bark mulch
    m = bpy.data.materials.new('plant mulch'); nt, N, L = _nodes(m)
    out = N.new('ShaderNodeOutputMaterial'); p = N.new('ShaderNodeBsdfPrincipled'); p.inputs['Roughness'].default_value = 0.92
    L.new(p.outputs['BSDF'], out.inputs['Surface'])
    tc = N.new('ShaderNodeTexCoord'); geo = N.new('ShaderNodeNewGeometry')
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 2.6, 1.0); mp.inputs['Rotation'].default_value = (0, 0, 0.7)
    L.new(geo.outputs['Position'], mp.inputs['Vector'])
    vo = N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 32.0; vo.feature = 'F1'
    L.new(mp.outputs['Vector'], vo.inputs['Vector'])
    ve = N.new('ShaderNodeTexVoronoi'); ve.inputs['Scale'].default_value = 32.0; ve.feature = 'DISTANCE_TO_EDGE'
    L.new(mp.outputs['Vector'], ve.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = _lin('#2a1a10'); e[1].position = 1.0; e[1].color = _lin('#7a5a3e')
    el = e.new(0.5); el.color = _lin('#4a3020')
    L.new(vo.outputs['Color'], ramp.inputs['Fac'])
    gap = N.new('ShaderNodeMapRange'); gap.inputs['From Min'].default_value = 0.0; gap.inputs['From Max'].default_value = 0.06
    L.new(ve.outputs['Distance'], gap.inputs['Value'])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[6].default_value = _lin('#1a120c')
    L.new(gap.outputs['Result'], mx.inputs['Factor']); L.new(ramp.outputs['Color'], mx.inputs[7])
    L.new(mx.outputs[2], p.inputs['Base Color'])
    bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = 0.8; bu.inputs['Distance'].default_value = 0.01
    L.new(gap.outputs['Result'], bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    return m


# ---------------------------------------------------------------- instancing
def proto_collection(name, objs):
    col = bpy.data.collections.new(name)
    for i, o in enumerate(objs):
        o.name = f'{name}-{i:03d}'
        col.objects.link(o)
    return col


def instancer(name, proto_col, P, rot, scale, idx, parent_col):
    """One object whose geometry nodes put proto_col's children at P (n,3) with euler rot (n,3),
    scale (n,) or (n,3) and variant idx (n,)."""
    n = len(P)
    if n == 0: return None
    me = bpy.data.meshes.new(name + '-pts')
    me.vertices.add(n); me.vertices.foreach_set('co', np.asarray(P, np.float32).ravel())
    scale = np.asarray(scale, np.float32)
    if scale.ndim == 1: scale = np.repeat(scale[:, None], 3, 1)
    for an, typ, data in (('rot', 'FLOAT_VECTOR', np.asarray(rot, np.float32)), ('scl', 'FLOAT_VECTOR', scale), ('idx', 'INT', np.asarray(idx, np.int32))):
        a = me.attributes.new(an, typ, 'POINT')
        a.data.foreach_set('vector' if typ == 'FLOAT_VECTOR' else 'value', data.ravel())
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
    mod = ob.modifiers.new('instances', 'NODES'); mod.node_group = ng
    return ob


def join(name, parts, mats):
    """parts: [(Buf, material_index_in_mats)] -> one object with all materials."""
    B = Buf()
    for b, mi in parts:
        B.extend(b, mat_map=np.full(64, mi, np.int32))
    me = B.mesh(name, mats)
    return bpy.data.objects.new(name, me)


# ---------------------------------------------------------------- leaf shapes
def _prof(kind):
    s = math.sin; pi = math.pi
    if kind == 'ovate':          # broadest below the middle (bougainvillea, gardenia)
        return lambda t: 0.30 * (max(0.0, s(pi * min(1, t ** 0.8))) ** 0.7) * (1 - 0.25 * t) + 0.012
    if kind == 'elliptic':
        return lambda t: 0.26 * max(0.0, s(pi * t)) ** 0.75 + 0.01
    if kind == 'small':
        return lambda t: 0.30 * max(0.0, s(pi * t)) ** 0.65 + 0.01
    if kind == 'obovate':        # broadest above the middle (petals, plumeria)
        return lambda t: 0.30 * max(0.0, s(pi * min(1, t ** 1.6))) ** 0.6 + 0.012
    if kind == 'lance':          # ti: channelled petiole, long lanceolate blade
        return lambda t: 0.014 if t < 0.14 else 0.014 + 0.125 * max(0.0, s(pi * min(1, (t - 0.14) / 0.86) ** 0.8)) ** 0.75
    if kind == 'plumeria':       # oblanceolate with a short petiole
        return lambda t: 0.01 if t < 0.1 else 0.01 + 0.2 * max(0.0, s(pi * min(1, ((t - 0.1) / 0.9) ** 1.25))) ** 0.7
    if kind == 'bract':          # broad, heart-based papery bract
        return lambda t: 0.36 * max(0.0, s(pi * min(1, t ** 0.72))) ** 0.75 + 0.015
    if kind == 'tree':
        return lambda t: 0.24 * max(0.0, s(pi * min(1, t ** 0.9))) ** 0.7 + 0.01
    raise KeyError(kind)


# ---------------------------------------------------------------- shrubs
SHRUBS = {
    # R, H: radius and height (m); twigs per plant; leaves per twig; leaf length (m)
    # r5 (critique-preview4-back #11): an arching, cane-like habit - long canes reach out and bow down over the planter
    # copings (cane_drop), not a compact rounded dome
    'bougainvillea': dict(R=0.58, H=0.9, twigs=320, leaves=(7, 12), leaf_len=0.055, twig_len=0.2, leaf_angle=58, droop=0.35, up=0.1,
                          shape='ovate', stems=6, stem_r=0.016, bloom=0.36, phyllo='alt', lump=0.4, canes=(7, 12), cane_len=1.25, cane_drop=0.55),
    'gardenia': dict(R=0.58, H=1.15, twigs=420, leaves=(6, 10), leaf_len=0.09, twig_len=0.15, leaf_angle=50, droop=0.15, up=0.45,
                     shape='elliptic', stems=6, stem_r=0.015, bloom=0.26, phyllo='opp', lump=0.16),
    'hedge': dict(R=0.5, H=1.25, twigs=420, leaves=(8, 12), leaf_len=0.045, twig_len=0.12, leaf_angle=55, droop=0.1, up=0.3,
                  shape='small', stems=6, stem_r=0.014, bloom=0.04, phyllo='alt', lump=0.1),
    # a clipped screen hedge on the side lot line (critic r2 back #11), >= 2.5 m (8.5-9 ft) so the neighbour's pool
    # deck and chaises stay out of the back view (critic preview3 back #5): dense small leaves, a narrow column
    'screen': dict(R=0.58, H=2.8, twigs=980, leaves=(8, 12), leaf_len=0.05, twig_len=0.13, leaf_angle=55, droop=0.08, up=0.3,
                   shape='small', stems=7, stem_r=0.016, bloom=0.0, phyllo='alt', lump=0.07),
    # r5 (critique-preview4-back #12): a few soft cream flowers, a little larger (flower_len), not a glitter of white dots
    'jasmine': dict(R=0.6, H=0.28, twigs=300, leaves=(6, 10), leaf_len=0.035, twig_len=0.12, leaf_angle=62, droop=0.05, up=0.5,
                    shape='elliptic', stems=5, stem_r=0.005, bloom=0.035, phyllo='opp', lump=0.12, flat=True, flower_len=0.013),
    'dichondra': dict(R=0.4, H=0.12, twigs=200, leaves=(5, 8), leaf_len=0.022, twig_len=0.08, leaf_angle=70, droop=0.05, up=0.7,
                      shape='small', stems=4, stem_r=0.003, bloom=0.0, phyllo='alt', lump=0.08, flat=True),
    'hibiscus': dict(R=0.7, H=1.6, twigs=380, leaves=(6, 9), leaf_len=0.09, twig_len=0.16, leaf_angle=52, droop=0.15, up=0.35,
                     shape='ovate', stems=5, stem_r=0.016, bloom=0.12, phyllo='alt', lump=0.25),
    'groundcover': dict(R=0.42, H=0.3, twigs=150, leaves=(6, 9), leaf_len=0.04, twig_len=0.1, leaf_angle=60, droop=0.05, up=0.6,
                        shape='small', stems=4, stem_r=0.006, bloom=0.1, phyllo='opp', lump=0.12, flat=True),
}


def shrub(seed, S, flower_fn=None):
    """A shrub as twigs on a lumpy dome, each twig carrying leaves (and flowers). Returns
    {material_key: Buf}; keys: leaf, stem, + whatever flower_fn adds."""
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'stem': Buf()}
    R = S['R'] * rng.uniform(0.85, 1.15); H = S['H'] * rng.uniform(0.85, 1.15)
    flat = S.get('flat', False)
    zc, rz = (0.0, H) if flat else (H * 0.42, H * 0.58)
    C = _rand_dirs(rng, 9); amp = rng.uniform(0.3, 1.0, 9) * S.get('lump', 0.15)
    env = lambda d: 1 + (amp * np.exp((d @ C.T - 1) / 0.2)).sum(-1) - amp.sum() * 0.12
    # twig tips in the outer shell of the dome
    n = S['twigs']
    d = _rand_dirs(rng, n * 2); d = d[d[:, 2] > (0.05 if flat else -0.45)][:n]; n = len(d)
    f = 1 - 0.5 * rng.random(n) ** 1.3
    tip = d * env(d)[:, None] * f[:, None] * np.array([R, R, rz]) + np.array([0, 0, zc])
    tip[:, 2] = np.maximum(tip[:, 2], 0.03 + 0.04 * rng.random(n))
    out_dir = _norm(tip - np.array([0, 0, zc * 0.6]))
    tdir = _norm(out_dir + rng.normal(0, 0.35, (n, 3)) + np.array([0, 0, S['up']]))
    tl = S['twig_len'] * rng.uniform(0.6, 1.35, n)
    tbase = tip - tdir * tl[:, None]
    tbase[:, 2] = np.maximum(tbase[:, 2], 0.01)
    # main stems from the crown of the roots, and a branchlet from the nearest to every twig
    m = S['stems'] + rng.integers(-1, 2)
    sd = _norm(rng.normal(0, 1, (m, 3)) * np.array([1, 1, 0.3]) + np.array([0, 0, 1.4 if not flat else 0.2]))
    s0 = np.concatenate([rng.normal(0, 0.05 * R, (m, 2)), np.zeros((m, 1))], 1)
    s1 = s0 + sd * np.array([R, R, rz + zc]) * rng.uniform(0.35, 0.6, (m, 1))
    tubes(out['stem'], curve(s0, s1, rng.normal(0, 0.04, (m, 3)), 6), np.linspace(S['stem_r'], S['stem_r'] * 0.55, 6)[None].repeat(m, 0), sides=6)
    near = np.argmin(((tbase[:, None, :] - s1[None, :, :]) ** 2).sum(-1) + 0.0 * rng.random((n, m)), axis=1)
    src = s1[near] + rng.normal(0, 0.02, (n, 3))
    tubes(out['stem'], curve(src, tbase, rng.normal(0, 0.03, (n, 3)) + np.array([0, 0, 0.03]), 4),
          np.linspace(S['stem_r'] * 0.4, S['stem_r'] * 0.22, 4)[None].repeat(n, 0), sides=4)
    tubes(out['stem'], curve(tbase, tip, rng.normal(0, 0.01, (n, 3)), 3), np.linspace(S['stem_r'] * 0.22, S['stem_r'] * 0.12, 3)[None].repeat(n, 0), sides=4)
    # long arching canes breaking out of the dome (bougainvillea): twigs all along them
    nc = rng.integers(*S['canes']) if S.get('canes') else 0
    if nc:
        az = rng.uniform(0, 6.28, nc); hd = np.stack([np.cos(az), np.sin(az), np.zeros(nc)], 1)
        c0 = hd * R * rng.uniform(0.3, 0.6, (nc, 1)) + np.array([0, 0, 1.0]) * (zc + rz * rng.uniform(0.2, 0.6, (nc, 1)))
        cl = S['cane_len'] * rng.uniform(0.6, 1.2, nc)
        cd = S.get('cane_drop', 0.0)                            # arching canes end lower than they start
        c1 = c0 + hd * (cl * 0.85)[:, None] + UP * (rng.uniform(-0.25 - cd, 0.25 - cd * 0.6, nc) * cl)[:, None]
        cp = curve(c0, c1, (UP * (0.35 + 0.25 * cd) * cl[:, None]) + rng.normal(0, 0.05, (nc, 3)), 7)
        tubes(out['stem'], cp, np.linspace(S['stem_r'] * 0.5, S['stem_r'] * 0.18, 7)[None].repeat(nc, 0), sides=4)
        k = 9
        ct = cp[:, 2:, :].reshape(-1, 3)                        # points along the outer part of every cane
        idx = rng.integers(0, len(ct), nc * k)
        tb2 = ct[idx] + rng.normal(0, 0.03, (nc * k, 3))
        dirs = _norm(hd[idx // 5] * 0.6 + rng.normal(0, 0.45, (nc * k, 3)) + UP * 0.3)
        tl2 = S['twig_len'] * rng.uniform(0.6, 1.2, nc * k)
        tp2 = tb2 + dirs * tl2[:, None]
        tubes(out['stem'], curve(tb2, tp2, rng.normal(0, 0.01, (nc * k, 3)), 3), np.linspace(S['stem_r'] * 0.18, S['stem_r'] * 0.1, 3)[None].repeat(nc * k, 0), sides=4)
        tip = np.concatenate([tip, tp2]); tdir = np.concatenate([tdir, dirs]); tl = np.concatenate([tl, tl2]); tbase = np.concatenate([tbase, tb2])
        d = np.concatenate([d, _norm(tp2 - np.array([0, 0, zc]))]); n = len(tip)
    # leaves along every twig
    lo, hi = S['leaves']
    k = rng.integers(lo, hi + 1, n)
    ti = np.repeat(np.arange(n), k)
    kk = np.concatenate([np.arange(c) for c in k])
    sk = (kk + rng.random(len(kk)) * 0.6 + 0.2) / k[ti]
    P = tbase[ti] + tdir[ti] * (tl[ti] * sk)[:, None]
    e1, e2 = _frame(tdir)
    phi = rng.uniform(0, 6.28, n)[ti] + (kk * GOLDEN if S['phyllo'] == 'alt' else (kk // 2) * (math.pi / 2) + (kk % 2) * math.pi)
    beta = np.radians(S['leaf_angle'] + rng.normal(0, 12, len(ti)))
    rad = np.cos(phi)[:, None] * e1[ti] + np.sin(phi)[:, None] * e2[ti]
    D = np.cos(beta)[:, None] * tdir[ti] + np.sin(beta)[:, None] * rad
    D = _norm(D - UP * (S['droop'] * rng.uniform(0.4, 1.6, len(ti)))[:, None])
    o = _norm(P - np.array([0, 0, zc * 0.5]))
    Nn = _norm(UP * 1.0 + o * 0.6 + rng.normal(0, 0.35, (len(ti), 3)))
    young = np.clip((1 - sk) * 3.5, 0, 1)
    Lf = S['leaf_len'] * rng.uniform(0.75, 1.2, len(ti)) * (0.45 + 0.55 * young)
    tpls = [leaf_tpl(_prof(S['shape']), fold=fo, arch=ar, twist=tw, cols=1, stations=(0, 0.2, 0.45, 0.72, 1.0))
            for fo, ar, tw in ((0.12, 0.08, 0.0), (0.22, 0.18, 0.25), (0.06, 0.03, -0.2))]
    pick = rng.integers(0, len(tpls), len(ti))
    for j, tp in enumerate(tpls):
        sel = pick == j
        place(out['leaf'], tp, P[sel] + D[sel] * 0.004, D[sel], Nn[sel], Lf[sel], rng.uniform(0.85, 1.15, sel.sum()))
    if flower_fn is not None:
        flower_fn(rng, out, tip, tdir, d, S)
    return out


def _bougainvillea_flowers(rng, out, tip, tdir, d, S):
    """Panicles of magenta bracts, three to a flower, with the small cream true flowers inside."""
    br, fl = out.setdefault('bract', Buf()), out.setdefault('floret', Buf())
    sun = np.clip(0.45 + 0.6 * d[:, 2], 0.1, 1)
    pick = rng.random(len(tip)) < S['bloom'] * sun
    tpb = [leaf_tpl(_prof('bract'), fold=0.05, cup=0.25, arch=-0.05, stations=(0, 0.15, 0.4, 0.7, 1.0), cols=1),
           leaf_tpl(_prof('bract'), fold=0.1, cup=0.4, arch=0.05, twist=0.3, stations=(0, 0.15, 0.4, 0.7, 1.0), cols=1)]
    Ps, Ds, Ns, Ls = [], [], [], []
    for i in np.nonzero(pick)[0]:
        nf = rng.integers(7, 20)
        c = tip[i] + tdir[i] * 0.03
        fp = c + rng.normal(0, 1, (nf, 3)) * np.array([0.05, 0.05, 0.035]) + tdir[i] * rng.uniform(-0.04, 0.06, (nf, 1))
        ax = _norm(tdir[i] * 0.6 + d[i] * 0.6 + UP * 0.5 + rng.normal(0, 0.45, (nf, 3)))
        e1, e2 = _frame(ax)
        for j in range(3):
            ph = rng.uniform(0, 6.28, nf) + j * 2.094
            rad = np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2
            Ps.append(fp); Ds.append(_norm(ax * 0.82 + rad * 0.57)); Ns.append(_norm(-rad * 0.8 + ax * 0.3)); Ls.append(rng.uniform(0.022, 0.036, nf))
        # cream tubular florets in about half the flowers
        sel = rng.random(nf) < 0.45
        if sel.any():
            place(fl, leaf_tpl(_prof('obovate'), stations=(0, 0.5, 1.0), cols=1), fp[sel] + ax[sel] * 0.012, ax[sel], _norm(e1[sel]), rng.uniform(0.008, 0.012, sel.sum()), np.full(sel.sum(), 0.9))
    if Ps:
        P, D, Nn, L = map(np.concatenate, (Ps, Ds, Ns, Ls))
        pk = rng.integers(0, 2, len(P))
        for j, tp in enumerate(tpb):
            s = pk == j; place(br, tp, P[s], D[s], Nn[s], L[s], rng.uniform(0.85, 1.1, s.sum()))


def _gardenia_flowers(rng, out, tip, tdir, d, S):
    pe = out.setdefault('petal', Buf()); bud = out.setdefault('bud', Buf())
    pick = rng.random(len(tip)) < S['bloom']
    tp_in = leaf_tpl(_prof('obovate'), fold=0.05, cup=0.35, arch=-0.12, stations=(0, 0.2, 0.5, 0.8, 1.0), cols=1)
    tp_out = leaf_tpl(_prof('obovate'), fold=0.04, cup=0.2, arch=0.08, twist=0.25, stations=(0, 0.2, 0.5, 0.8, 1.0), cols=1)
    for i in np.nonzero(pick)[0]:
        c = tip[i] + tdir[i] * 0.015
        ax = _norm(tdir[i] * 0.5 + UP + rng.normal(0, 0.3, 3))[None]
        e1, e2 = _frame(ax)
        for whorl, (n_p, beta, L, tp) in enumerate(((6, 38, 0.024, tp_in), (7, 78, 0.034, tp_out))):
            ph = rng.uniform(0, 6.28) + np.arange(n_p) * 2 * math.pi / n_p + rng.normal(0, 0.08, n_p)
            rad = np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2
            b = np.radians(beta + rng.normal(0, 6, n_p))[:, None]
            Dd = _norm(np.cos(b) * ax + np.sin(b) * rad + np.cross(ax, rad) * 0.15)
            place(pe, tp, np.repeat(c[None], n_p, 0) + ax * 0.004 * whorl, Dd, _norm(ax - Dd * 0.3), np.full(n_p, L) * rng.uniform(0.9, 1.1, n_p), np.full(n_p, 1.25))
    # a few green-white buds
    pick = (rng.random(len(tip)) < S['bloom'] * 0.8) & ~pick
    idx = np.nonzero(pick)[0]
    if len(idx):
        p0 = tip[idx]; ax = _norm(tdir[idx] + UP * 0.5)
        tubes(bud, p0[:, None, :] + ax[:, None, :] * np.linspace(0, 0.035, 5)[None, :, None], np.array([0.003, 0.008, 0.009, 0.006, 0.001])[None].repeat(len(idx), 0), sides=6)


def _small_white_flowers(rng, out, tip, tdir, d, S):
    pe = out.setdefault('petal', Buf())
    pick = rng.random(len(tip)) < S['bloom']
    tp = leaf_tpl(_prof('obovate'), fold=0.0, cup=0.2, stations=(0, 0.4, 1.0), cols=1)
    for i in np.nonzero(pick)[0]:
        ax = _norm(UP + rng.normal(0, 0.25, 3))[None]; e1, e2 = _frame(ax)
        ph = rng.uniform(0, 6.28) + np.arange(5) * 1.2566
        rad = np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2
        place(pe, tp, np.repeat(tip[i][None] + ax * 0.01, 5, 0), _norm(rad + ax * 0.25), np.repeat(ax, 5, 0), np.full(5, S.get('flower_len', 0.009)), np.full(5, 1.2))


# ---------------------------------------------------------------- ti plant (Cordyline fruticosa)
def ti_plant(seed):
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'cane': Buf(), 'dry': Buf()}
    nc = rng.choice([2, 3, 3, 4, 5])
    tpls = [leaf_tpl(_prof('lance'), fold=0.035, cup=0.04, arch=a, twist=tw, cols=2, stations=(0, 0.08, 0.16, 0.3, 0.45, 0.6, 0.75, 0.88, 1.0))
            for a, tw in ((0.14, 0.12), (0.34, -0.22), (0.6, 0.28), (0.9, -0.15))]
    for c in range(nc):
        h = rng.uniform(0.15, 0.75) * (1.0 if c == 0 else rng.uniform(0.25, 0.9))
        lean = rng.uniform(0, 6.28); lv = np.array([math.cos(lean), math.sin(lean), 0]) * rng.uniform(0.03, 0.12)
        base = np.array([rng.normal(0, 0.1), rng.normal(0, 0.1), 0])
        t = np.linspace(0, 1, 7)[:, None]
        path = base + t * np.array([0, 0, h]) + (t ** 2) * lv * h
        r = rng.uniform(0.011, 0.017)
        tubes(out['cane'], path[None], np.linspace(r * 1.15, r * 0.9, 7)[None], sides=7)
        top = path[-1]; ax = _norm(path[-1] - path[-2])
        n = rng.integers(16, 27)
        i = np.arange(n); age = i / (n - 1)                     # 0 = youngest (top centre) .. 1 = oldest
        ph = rng.uniform(0, 6.28) + i * GOLDEN
        el = np.radians(80 - 78 * age ** 0.9 + rng.normal(0, 8, n))   # a vase of leaves, the oldest near level
        hd = np.stack([np.cos(ph), np.sin(ph), np.zeros(n)], 1)
        D = _norm(np.cos(el)[:, None] * hd + np.sin(el)[:, None] * UP)
        Nn = _norm(UP - D * (D @ UP)[:, None] + hd * 0.15 + rng.normal(0, 0.2, (n, 3)))
        P = top - ax * (age * 0.09)[:, None] + hd * 0.008
        L = rng.uniform(0.4, 0.58) * rng.uniform(0.85, 1.15, n) * (0.6 + 0.4 * np.clip(age * 3, 0, 1))
        pk = np.clip((age * 3.99).astype(int) + rng.integers(-1, 1, n), 0, 3)
        for j, tp in enumerate(tpls):
            s = pk == j; place(out['leaf'], tp, P[s], D[s], Nn[s], L[s], rng.uniform(1.0, 1.35, s.sum()))
        # a dead leaf or two hanging against the cane
        nd = rng.integers(0, 3)
        if nd and h > 0.35:
            ph = rng.uniform(0, 6.28, nd); hd = np.stack([np.cos(ph), np.sin(ph), np.zeros(nd)], 1)
            D = _norm(hd * 0.35 - UP); place(out['dry'], tpls[0], np.repeat(top[None], nd, 0) - ax * 0.12 + hd * 0.01, D, hd, rng.uniform(0.25, 0.4, nd), np.full(nd, 0.7))
    return out


# ---------------------------------------------------------------- strap-leaf groundcovers
def strap_tufts(seed, tufts=(5, 8), leaves=(28, 46), L=(0.16, 0.3), width=0.6, spread=0.28, el=(70, 15), arch=0.5, key='leaf'):
    """Mondo grass / liriope / tradescantia: a patch of tufts, each a fountain of narrow arching straps.
    width: blade width scale (lance template is ~0.14 L wide)."""
    rng = np.random.default_rng(seed)
    out = {key: Buf()}
    tpls = [leaf_tpl(_prof('lance'), fold=0.06, arch=a, twist=tw, cols=1, stations=(0, 0.15, 0.35, 0.55, 0.75, 0.9, 1.0))
            for a, tw in ((arch * 0.4, 0.3), (arch, -0.4), (arch * 1.6, 0.5))]
    for k in range(rng.integers(*tufts)):
        c = np.array([rng.normal(0, spread), rng.normal(0, spread), 0.0])
        n = rng.integers(*leaves)
        ph = rng.uniform(0, 6.28, n)
        e = np.radians(rng.uniform(el[1], el[0], n))
        hd = np.stack([np.cos(ph), np.sin(ph), np.zeros(n)], 1)
        D = _norm(np.cos(e)[:, None] * hd + np.sin(e)[:, None] * UP)
        Nn = _norm(UP - D * (D @ UP)[:, None] + rng.normal(0, 0.25, (n, 3)))
        P = c + hd * rng.uniform(0, 0.02, (n, 1))
        Ln = rng.uniform(*L, n) * (0.5 + 0.5 * np.sin(e))
        pk = rng.integers(0, 3, n)
        for j, tp in enumerate(tpls):
            sl = pk == j; place(out[key], tp, P[sl], D[sl], Nn[sl], Ln[sl], width * rng.uniform(0.8, 1.2, sl.sum()))
    return out


def alocasia(seed):
    """Elephant ear (Alocasia / Colocasia): a few huge glossy arrow-shaped blades on long upright petioles."""
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'stem': Buf()}
    blades = [monstera_blade(rng, splits=0, holes=False) for _ in range(2)]
    n = rng.integers(5, 9)
    for i in range(n):
        az = rng.uniform(0, 6.28); hd = np.array([math.cos(az), math.sin(az), 0])
        el = math.radians(rng.uniform(52, 80)); pl = rng.uniform(0.7, 1.35)
        b0 = np.array([rng.normal(0, 0.06), rng.normal(0, 0.06), 0.0])
        tip = b0 + (hd * math.cos(el) + UP * math.sin(el)) * pl
        tubes(out['stem'], curve(b0[None], tip[None], (hd * 0.04)[None], 8), np.linspace(0.028, 0.012, 8)[None], sides=7)
        size = rng.uniform(0.55, 0.95)
        dn = math.radians(rng.uniform(-75, -40))
        D = _norm(hd * math.cos(dn) + UP * math.sin(dn) + np.cross(UP, hd) * rng.normal(0, 0.2))
        Nn = _norm(UP * 0.5 + hd * 0.9 + rng.normal(0, 0.15, 3))
        place(out['leaf'], blades[i % 2], tip[None] - D[None] * 0.06 * size, D[None], Nn[None], np.array([size]), np.array([0.85]))
    return out


def _hibiscus_flowers(rng, out, tip, tdir, d, S):
    """Hibiscus: big five-petalled red flowers facing out of the shrub, with a pale staminal column."""
    pe = out.setdefault('petal', Buf()); bud = out.setdefault('bud', Buf())
    pick = rng.random(len(tip)) < S['bloom'] * np.clip(0.4 + 0.6 * d[:, 2] + 0.3, 0.2, 1)
    tp = leaf_tpl(_prof('obovate'), fold=0.03, cup=0.18, arch=0.06, twist=0.3, stations=(0, 0.2, 0.5, 0.8, 1.0), cols=1)
    for i in np.nonzero(pick)[0]:
        c = tip[i] + tdir[i] * 0.02
        ax = _norm(d[i] * 0.8 + tdir[i] * 0.4 + UP * 0.3 + rng.normal(0, 0.25, 3))[None]
        e1, e2 = _frame(ax)
        ph = rng.uniform(0, 6.28) + np.arange(5) * 2 * math.pi / 5
        rad = np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2
        Dd = _norm(ax * 0.45 + rad)
        place(pe, tp, np.repeat(c[None], 5, 0), Dd, _norm(ax - Dd * 0.2), np.full(5, rng.uniform(0.055, 0.07)), np.full(5, 1.5))
        tubes(bud, (c + ax * np.linspace(0, 0.07, 4)[:, None])[None], np.array([[0.003, 0.0025, 0.002, 0.004]]), sides=5)


def heliconia(seed):
    """Heliconia (lobster claw / parrot's beak): banana-like paddle leaves on upright pseudostems, red
    boat-shaped bracts in a zigzag spike with yellow-green tips."""
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'stem': Buf(), 'bract': Buf()}
    tpl = [leaf_tpl(lambda t: 0.012 if t < 0.12 else 0.012 + 0.2 * max(0.0, math.sin(math.pi * min(1, (t - 0.12) / 0.88))) ** 0.6,
                    fold=0.08, arch=a, twist=tw, cols=2, stations=(0, 0.12, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0)) for a, tw in ((0.12, 0.15), (0.3, -0.25))]
    bt = leaf_tpl(lambda t: 0.16 * max(0.0, math.sin(math.pi * min(1, t ** 0.7))) ** 0.6 + 0.01, fold=0.6, cup=0.3, arch=-0.15,
                  cols=1, stations=(0, 0.2, 0.45, 0.7, 0.9, 1.0))
    for k in range(rng.integers(4, 8)):
        b0 = np.array([rng.normal(0, 0.18), rng.normal(0, 0.18), 0.0])
        h = rng.uniform(0.8, 1.6)
        lean = np.array([rng.normal(0, 0.08), rng.normal(0, 0.08), 1.0]); top = b0 + _norm(lean) * h
        tubes(out['stem'], np.linspace(b0, top, 6)[None], np.linspace(0.03, 0.018, 6)[None], sides=7)
        n = rng.integers(3, 6); az0 = rng.uniform(0, 6.28)
        for j in range(n):            # distichous: the leaves fan out in one plane, alternating
            az = az0 + (j % 2) * math.pi + rng.normal(0, 0.25); hd = np.array([math.cos(az), math.sin(az), 0])
            p0 = b0 + (top - b0) * (0.45 + 0.55 * j / max(1, n - 1))
            el = math.radians(rng.uniform(45, 75)); D = _norm(hd * math.cos(el) + UP * math.sin(el))
            place(out['leaf'], tpl[j % 2], p0[None], D[None], _norm(UP - D * D[2] + hd * 0.2)[None], np.array([rng.uniform(0.7, 1.1)]))
        if rng.random() < 0.6:        # an inflorescence: zigzag rachis with 5-9 bracts
            nb = rng.integers(5, 10); ax = _norm(lean * np.array([1, 1, 0]) * 2 + UP)
            pts = top + ax[None] * np.linspace(0.02, 0.38, nb)[:, None]
            side = np.where(np.arange(nb) % 2, 1.0, -1.0); sd = _norm(np.cross(ax, np.array([1.0, 0.3, 0])))
            D = _norm(sd[None] * side[:, None] * 1.0 + ax[None] * 0.55)
            place(out['bract'], bt, pts, D, np.repeat(ax[None], nb, 0), rng.uniform(0.09, 0.13, nb) * np.linspace(1.0, 0.6, nb))
            tubes(out['stem'], pts[None], np.full((1, nb), 0.008), sides=5)
    return out


# ---------------------------------------------------------------- monstera
def monstera_blade(rng, splits=7, holes=True):
    """Unit monstera leaf (length 1 from the petiole junction to the tip, +Y), split from the margin
    toward the midrib along the lateral veins, with a row of holes near the midrib."""
    Vs, Fs, UVs = [], [], []
    for side in (-1, 1):
        sk = np.sort(np.linspace(0.2, 0.9, splits) + rng.normal(0, 0.02, splits))
        g = 0.012 + rng.random(splits) * 0.008
        rs = rng.uniform(0.2, 0.4, splits)
        cuts_s = list(np.concatenate([sk - g, sk + g])); cuts_r = list(rs)
        hole_s = []
        if holes:
            mids = (sk[:-1] + sk[1:]) / 2
            for m_ in mids:
                if rng.random() < 0.8:
                    hw = (sk[1] - sk[0]) * rng.uniform(0.12, 0.22); r0, r1 = rng.uniform(0.12, 0.2), rng.uniform(0.26, 0.36)
                    hole_s.append((m_ - hw, m_ + hw, r0, r1)); cuts_s += [m_ - hw, m_ + hw]; cuts_r += [r0, r1]
        S_ = np.unique(np.concatenate([np.linspace(0, 1, 46), np.clip(cuts_s, 0, 1)]))
        R_ = np.unique(np.concatenate([np.linspace(0, 1, 12) ** 0.9, np.clip(cuts_r, 0, 1)]))
        th = np.radians(-80 + S_ * 170)
        ex = 0.48 * np.cos(th) * (1 - 0.4 * np.maximum(0, np.sin(th)) ** 6); ey = 0.42 + 0.58 * np.sin(th)
        my = np.clip((S_ - 0.12) / 0.88, 0, 1) * 0.97
        X = (R_[None, :] * ex[:, None]) * side
        Y = my[:, None] + R_[None, :] * (ey - my)[:, None] + R_[None, :] * (1 - R_[None, :]) * 0.08
        Z = -0.09 * R_[None, :] ** 2 + 0.02 * np.sin(R_[None, :] * math.pi) - 0.06 * (Y ** 2)
        ns, nr = len(S_), len(R_)
        V = np.stack([X, Y, Z], -1).reshape(-1, 3)
        UV = np.stack([np.broadcast_to(0.5 + side * 0.5 * R_[None, :], (ns, nr)), np.broadcast_to(S_[:, None], (ns, nr))], -1).reshape(-1, 2)
        sc = (S_[:-1] + S_[1:]) / 2; rc = (R_[:-1] + R_[1:]) / 2
        keep = np.ones((ns - 1, nr - 1), bool)
        for a, gg, r_ in zip(sk, g, rs):          # radial splits: an angular gap, so they widen toward the margin
            keep &= ~((np.abs(sc - a) < gg)[:, None] & (rc > r_)[None, :])
        for s0, s1, r0, r1 in hole_s:
            keep &= ~(((sc > s0) & (sc < s1))[:, None] & ((rc > r0) & (rc < r1))[None, :])
        ii, jj = np.nonzero(keep)
        a = ii * nr + jj
        F = np.stack([a, a + nr, a + nr + 1, a + 1], -1) if side > 0 else np.stack([a, a + 1, a + nr + 1, a + nr], -1)
        off = sum(len(v) for v in Vs)
        Vs.append(V); Fs.append(F + off); UVs.append(UV)
    return Tpl(np.concatenate(Vs), np.concatenate(Fs), np.concatenate(UVs))


def monstera(seed):
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'stem': Buf()}
    n = rng.integers(9, 16)
    blades = [monstera_blade(rng, splits=s, holes=h) for s, h in ((7, True), (8, True), (6, False), (5, False))]
    for i in range(n):
        az = rng.uniform(0, 6.28) if i else rng.uniform(0, 6.28)
        hd = np.array([math.cos(az), math.sin(az), 0])
        el = math.radians(rng.uniform(42, 78))
        pl = rng.uniform(0.5, 1.1)
        b0 = np.array([rng.normal(0, 0.08), rng.normal(0, 0.08), 0.02])
        tip = b0 + (hd * math.cos(el) + UP * math.sin(el)) * pl
        sag = -UP * 0.06 + hd * 0.05
        path = curve(b0[None], tip[None], sag[None], 8)
        tubes(out['stem'], path, np.linspace(0.016, 0.009, 8)[None], sides=7)
        size = rng.uniform(0.4, 0.75) * (0.7 + 0.3 * pl / 1.1)
        dn = math.radians(rng.uniform(-68, -30))           # blades hang from the petiole tip, facing out and up
        D = _norm(hd * math.cos(dn) + UP * math.sin(dn) + np.cross(UP, hd) * rng.normal(0, 0.25))
        Nn = _norm(UP * 0.7 + hd * 0.75 + rng.normal(0, 0.2, 3))
        bl = blades[0 if size > 0.6 else 1 if size > 0.48 else 2 + rng.integers(0, 2)]
        place(out['leaf'], bl, tip[None] - D[None] * 0.01, D[None], Nn[None], np.array([size]))
    return out


# ---------------------------------------------------------------- plumeria tree
def plumeria_tree(seed, scale=1.0, young=False):
    """young (r6, critique-preview5-front #10): the small street plumerias as real-size young trees, not a scaled-down
    mature crown (which forked at ~25 cm and read as a round gardenia bush): a bare grey trunk to 0.85-1.1 m (3-3.6 ft),
    two to four candelabra limbs, one or two more forks, a rosette only at each blunt branch tip, so the branching
    shows under and between the leaves."""
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'bark': Buf(), 'petal': Buf()}
    segs = []                                # (path (k,3), r0, r1)
    tips = []
    if young:
        def grow_y(p, d, L, r, depth, first=False):
            end = p + d * L
            side = _norm(np.cross(d, UP) + 1e-6)
            mid = p + d * L * 0.45 + side * rng.normal(0, 0.06) * L - UP * 0.05 * L * (1 - d[2])
            t = np.linspace(0, 1, 6)[:, None]
            path = (1 - t) ** 2 * p + 2 * (1 - t) * t * mid + t * t * end
            segs.append((path, r, r * 0.88))
            if depth == 0 or (not first and rng.random() < 0.3):
                tips.append((end, _norm(path[-1] - path[-2]))); return
            k = rng.integers(2, 5) if first else (2 if rng.random() < 0.7 else 3)
            az0 = rng.uniform(0, 6.28)
            for j in range(k):
                az = az0 + j * 2 * math.pi / k + rng.normal(0, 0.4)
                hd = np.array([math.cos(az), math.sin(az), 0])
                spread = math.radians(rng.uniform(32, 50) if first else rng.uniform(16, 30))
                nd = _norm(d * math.cos(spread) + _norm(hd - d * (hd @ d) + 1e-6) * math.sin(spread) + UP * 0.3)
                grow_y(end, nd, rng.uniform(0.4, 0.58) if first else L * rng.uniform(0.7, 0.9), r * 0.8, depth - 1)
        h0 = rng.uniform(0.85, 1.1)
        lean = rng.normal(0, 0.12, 3) * np.array([1, 1, 0])
        # the bare trunk: a slight S, then the first fork
        grow_y(np.zeros(3), _norm(UP + lean), h0, 0.075, 3, first=True)
        for path, r0, r1 in segs:
            tubes(out['bark'], path[None], np.linspace(r0, r1, len(path))[None], sides=9)
        tpl = [leaf_tpl(_prof('plumeria'), fold=0.14, arch=a, twist=tw, cols=1, stations=(0, 0.1, 0.3, 0.55, 0.8, 1.0)) for a, tw in ((0.05, 0.1), (0.18, -0.2), (0.34, 0.25))]
        petal = leaf_tpl(_prof('obovate'), fold=0.05, cup=0.15, arch=-0.05, twist=0.5, stations=(0, 0.25, 0.55, 0.8, 1.0), cols=1)
        for pos, d in tips:
            rs = rng.uniform(0.8, 1.15); d = _norm(d + rng.normal(0, 0.2, 3))
            n = rng.integers(int(13 * rs), int(20 * rs) + 1)            # thin rosettes: the limbs show below them
            i = np.arange(n); age = i / (n - 1)
            ph = rng.uniform(0, 6.28) + i * GOLDEN
            hd = np.stack([np.cos(ph), np.sin(ph), np.zeros(n)], 1)
            el = np.radians(72 - 70 * age ** 0.9 + rng.normal(0, 8, n))   # held up and out, none hanging below the tip
            D = _norm(np.cos(el)[:, None] * hd + np.sin(el)[:, None] * UP + d * 0.25)
            Nn = _norm(UP - D * (D @ UP)[:, None] + rng.normal(0, 0.15, (n, 3)))
            L = rng.uniform(0.2, 0.32, n) * (0.55 + 0.45 * np.clip(age * 2.5, 0, 1)) * rs
            P = pos - d * (age * 0.03)[:, None]
            pk = np.clip((age * 2.99).astype(int), 0, 2)
            for j, tp in enumerate(tpl):
                s = pk == j; place(out['leaf'], tp, P[s], D[s], Nn[s], L[s], rng.uniform(0.85, 1.15, s.sum()))
            if rng.random() < 0.55:
                nf = rng.integers(8, 18)
                stalk = rng.uniform(0.1, 0.2)
                fc = pos + UP * stalk + d * 0.04 + rng.normal(0, 1, (nf, 3)) * np.array([0.06, 0.06, 0.03])
                tubes(out['bark'], curve(np.repeat(pos[None] + UP * 0.02, nf, 0), fc, rng.normal(0, 0.01, (nf, 3)), 3), np.full((nf, 3), 0.003), sides=4)
                ax = _norm(UP * 1.2 + (fc - pos) * 6 + rng.normal(0, 0.3, (nf, 3)))
                e1, e2 = _frame(ax)
                ph0 = rng.uniform(0, 6.28)
                for j in range(5):
                    phj = np.full(nf, j * 1.2566 + ph0)
                    rad = np.cos(phj)[:, None] * e1 + np.sin(phj)[:, None] * e2
                    tang = np.cross(ax, rad)
                    place(out['petal'], petal, fc + ax * 0.004, _norm(rad * 0.85 + ax * 0.25 + tang * 0.25), _norm(ax - rad * 0.2), rng.uniform(0.032, 0.042, nf), np.full(nf, 1.15))
        return out
    def grow(p, d, L, r, depth, first=False):
        end = p + d * L
        side = _norm(np.cross(d, UP) + 1e-6)
        # plumeria limbs leave the fork outward, then turn up (the candelabra)
        mid = p + d * L * 0.45 + side * rng.normal(0, 0.05) * L - UP * 0.06 * L * (1 - d[2])
        t = np.linspace(0, 1, 6)[:, None]
        path = (1 - t) ** 2 * p + 2 * (1 - t) * t * mid + t * t * end
        segs.append((path, r, r * 0.9))
        if depth == 0 or (depth == 1 and rng.random() < 0.4):     # an open crown: some limbs stop a fork early
            tips.append((end, _norm(path[-1] - path[-2]))); return
        k = rng.integers(3, 6) if first else (2 if rng.random() < 0.55 else 3)
        az0 = rng.uniform(0, 6.28)
        for j in range(k):
            az = az0 + j * 2 * math.pi / k + rng.normal(0, 0.35)
            hd = np.array([math.cos(az), math.sin(az), 0])
            spread = math.radians(rng.uniform(38, 55) if first else rng.uniform(20, 38))
            nd = _norm(d * math.cos(spread) + _norm(hd - d * (hd @ d) + 1e-6) * math.sin(spread) + UP * 0.22)
            grow(end, nd, rng.uniform(0.62, 0.8) if first else L * rng.uniform(0.8, 0.95), r * 0.84, depth - 1)
    h0 = rng.uniform(0.35, 0.6)                 # a short trunk forking low into a broad, rounded crown
    grow(np.zeros(3), _norm(UP + rng.normal(0, 0.1, 3) * np.array([1, 1, 0])), h0, 0.13, 4, first=True)
    k = 6
    for path, r0, r1 in segs:
        tubes(out['bark'], path[None], np.linspace(r0, r1, len(path))[None], sides=9)
    tpl = [leaf_tpl(_prof('plumeria'), fold=0.14, arch=a, twist=tw, cols=1, stations=(0, 0.1, 0.3, 0.55, 0.8, 1.0)) for a, tw in ((0.05, 0.1), (0.18, -0.2), (0.34, 0.25))]
    petal = leaf_tpl(_prof('obovate'), fold=0.05, cup=0.15, arch=-0.05, twist=0.5, stations=(0, 0.25, 0.55, 0.8, 1.0), cols=1)
    for pos, d in tips:
        # r5 (critique-preview4-front #2): every rosette its own size (+-20 %) and tilt, so no two read as clones
        rs = rng.uniform(0.8, 1.2); d = _norm(d + rng.normal(0, 0.22, 3))
        n = rng.integers(int(22 * rs), int(34 * rs) + 1)
        i = np.arange(n); age = i / (n - 1)
        ph = rng.uniform(0, 6.28) + i * GOLDEN
        hd = np.stack([np.cos(ph), np.sin(ph), np.zeros(n)], 1)
        el = np.radians(70 - 95 * age ** 0.9 + rng.normal(0, 8, n))
        D = _norm(np.cos(el)[:, None] * hd + np.sin(el)[:, None] * UP + d * 0.2)
        Nn = _norm(UP - D * (D @ UP)[:, None] + rng.normal(0, 0.15, (n, 3)))
        L = rng.uniform(0.28, 0.42, n) * (0.55 + 0.45 * np.clip(age * 2.5, 0, 1)) * rs
        P = pos - d * (age * 0.05)[:, None]
        pk = np.clip((age * 2.99).astype(int), 0, 2)
        for j, tp in enumerate(tpl):
            s = pk == j; place(out['leaf'], tp, P[s], D[s], Nn[s], L[s], rng.uniform(0.85, 1.15, s.sum()))
        if rng.random() < 0.42:                 # an inflorescence of white, yellow-eyed flowers (on some tips only)
            nf = rng.integers(14, 30)
            stalk = rng.uniform(0.14, 0.26)
            fc = pos + UP * stalk + d * 0.05 + rng.normal(0, 1, (nf, 3)) * np.array([0.08, 0.08, 0.035])
            tubes(out['bark'], curve(np.repeat(pos[None] + UP * 0.02, nf, 0), fc, rng.normal(0, 0.01, (nf, 3)), 3), np.full((nf, 3), 0.0035), sides=4)
            ax = _norm(UP * 1.2 + (fc - pos) * 6 + rng.normal(0, 0.3, (nf, 3)))
            e1, e2 = _frame(ax)
            for j in range(5):
                phj = rng.uniform(0, 6.28, nf) * 0 + j * 1.2566 + rng.uniform(0, 6.28, nf)[0]
                rad = np.cos(phj)[:, None] * e1 + np.sin(phj)[:, None] * e2
                tang = np.cross(ax, rad)
                place(out['petal'], petal, fc + ax * 0.004, _norm(rad * 0.85 + ax * 0.25 + tang * 0.25), _norm(ax - rad * 0.2), rng.uniform(0.034, 0.044, nf), np.full(nf, 1.15))
    return out


# ---------------------------------------------------------------- background canopy trees
TREE_FORMS = {
    # trunk height, crown centre height, crown radii (x, z), envelope lumpiness, leaf clumps, leaves per clump, leaf length
    'dome': dict(trunk=(1.3, 2.0), cz=4.4, R=(3.7, 3.0), lump=0.32, clumps=230, leaves=(55, 80), leaf=(0.16, 0.25), girth=0.26),       # mango, kamani
    'umbrella': dict(trunk=(1.8, 2.6), cz=5.3, R=(5.2, 2.4), lump=0.28, clumps=300, leaves=(55, 75), leaf=(0.15, 0.24), girth=0.3),    # monkeypod
    'tall': dict(trunk=(1.6, 2.4), cz=5.6, R=(2.9, 4.0), lump=0.36, clumps=240, leaves=(55, 80), leaf=(0.18, 0.27), girth=0.22),      # java plum, be-still
}


def canopy_tree(seed, form='dome', bloom=0.0):
    """A tropical shade tree grown inside a lumpy crown envelope: a buttressed trunk forking into
    scaffold limbs, limbs into branches, branches into twigs ending in clumps of leaves that fill
    the outer shell of the crown (so it reads as a dense, rounded, cumulus-like canopy with gaps,
    the way kamani, mango and monkeypod trees look across a golf course).

    r5 (critique-preview4-back #5 / front #3): the background trees read as 'lollipops' - one ball of leaves on a
    stick trunk. The spreading forms below ('monkeypod', 'kiawe', 'kamani') are grown instead from one to four
    leaning stems, each carrying its own sub-crowns: a crown of 3-8 flattened lobes offset around the tree, so the
    silhouette is broad, flat-topped and ragged, with sky through the gaps, and the shadow is no longer a disc.
    Sized so a scale of 1 is a ~4 m crown radius (the canopy-height data's crown radius), ~5.5-7.5 m tall."""
    SPREAD = {
        # stems (n), stem length (m), stem lean (deg), lobes (n), lobe offset (m), lobe radius / half-height (m),
        # lobe centre height (m), leaf clumps, leaves per clump, leaf length (m), stem girth (m)
        'monkeypod': dict(stems=(1, 3), sl=(1.8, 2.8), lean=(10, 28), lobes=(5, 8), off=(1.2, 2.6), lr=(1.9, 2.8), lz=(0.9, 1.4), cz=(4.8, 5.8), clumps=340, leaves=(40, 60), leaf=(0.12, 0.2), girth=0.28),
        'kiawe': dict(stems=(2, 4), sl=(1.2, 2.2), lean=(22, 42), lobes=(5, 8), off=(1.0, 2.4), lr=(1.4, 2.3), lz=(0.7, 1.2), cz=(3.6, 4.6), clumps=280, leaves=(55, 85), leaf=(0.07, 0.12), girth=0.15),
        'kamani': dict(stems=(1, 2), sl=(1.5, 2.3), lean=(5, 18), lobes=(3, 6), off=(0.8, 1.8), lr=(2.2, 3.0), lz=(1.4, 2.1), cz=(4.3, 5.3), clumps=300, leaves=(45, 70), leaf=(0.16, 0.24), girth=0.26),
    }
    if form in SPREAD:
        rng = np.random.default_rng(seed)
        F = SPREAD[form]
        out = {'leaf': Buf(), 'bark': Buf()}
        U = lambda ab, n=None: rng.uniform(ab[0], ab[1], n)
        # stems: from a common foot, leaning out on spread azimuths
        ns = int(rng.integers(F['stems'][0], F['stems'][1] + 1))
        az0 = rng.uniform(0, 6.28)
        saz = az0 + np.arange(ns) * 2 * math.pi / ns + rng.normal(0, 0.35, ns)
        sel = np.radians(90 - (U(F['lean'], ns) if ns > 1 else U(F['lean'], ns) * 0.4))
        sd = np.stack([np.cos(saz) * np.cos(sel), np.sin(saz) * np.cos(sel), np.sin(sel)], 1)
        sb = np.stack([np.cos(saz), np.sin(saz), np.zeros(ns)], 1) * 0.12
        st = sb + sd * U(F['sl'], ns)[:, None]
        r0 = F['girth'] * rng.uniform(0.85, 1.15) / math.sqrt(ns) * 1.25
        tubes(out['bark'], curve(sb, st, rng.normal(0, 0.12, (ns, 3)) * np.array([1, 1, 0]), 6),
              (r0 * (1 + 0.5 * np.exp(-np.linspace(0, 1, 6) * 7)) * np.linspace(1, 0.72, 6))[None].repeat(ns, 0), sides=8)
        for a in rng.uniform(0, 6.28, rng.integers(3, 5)):            # root flares
            h = np.array([math.cos(a), math.sin(a), 0])
            p0 = h * r0 * 0.6 + np.array([0, 0, 0.35]); p1 = h * r0 * 2.6 + np.array([0, 0, -0.05])
            tubes(out['bark'], curve(p0[None], p1[None], (h * 0.06 + np.array([0, 0, -0.06]))[None], 4), np.array([[r0 * 0.4, r0 * 0.3, r0 * 0.2, r0 * 0.08]]), sides=6)
        # lobes (sub-crowns) round the tree: flattened, offset, at varied heights; the first sits over the middle
        nl = int(rng.integers(F['lobes'][0], F['lobes'][1] + 1))
        laz = az0 + np.arange(nl) * 2 * math.pi / nl + rng.normal(0, 0.45, nl)
        lo = U(F['off'], nl); lo[0] *= 0.25
        LC = np.stack([np.cos(laz) * lo, np.sin(laz) * lo, U(F['cz'], nl) + rng.normal(0, 0.25, nl)], 1)
        LC[1:, 2] -= (lo[1:] / F['off'][1]) * rng.uniform(0.0, 0.8, nl - 1)        # outer lobes droop a little
        LR = U(F['lr'], nl); LZ = U(F['lz'], nl)
        # each lobe hangs off the stem nearest its azimuth: a limb from the stem top into the lobe
        own = np.array([int(np.argmin(np.abs(np.angle(np.exp(1j * (saz - a)))))) for a in laz])
        L0 = st[own] + rng.normal(0, 0.06, (nl, 3))
        L1 = LC - np.array([0, 0, 1.0]) * LZ[:, None] * 0.4
        L1[:, 2] = np.maximum(L1[:, 2], L0[:, 2] + 0.4)
        tubes(out['bark'], curve(L0, L1, rng.normal(0, 0.2, (nl, 3)) + np.array([0, 0, 0.2]), 6), np.linspace(r0 * 0.75, r0 * 0.35, 6)[None].repeat(nl, 0), sides=7)
        B0, B1, BL = [], [], []
        for i in range(nl):
            k = int(rng.integers(3, 6))
            dd = _norm(rng.normal(0, 1, (k, 3)) * np.array([1, 1, 0.5]) + np.array([0, 0, 0.35]))
            B0.append(np.repeat(L1[i][None], k, 0) + rng.normal(0, 0.05, (k, 3)))
            B1.append(LC[i] + dd * np.array([LR[i], LR[i], LZ[i]]) * rng.uniform(0.55, 0.8, (k, 1)))
            BL += [i] * k
        B0, B1 = np.concatenate(B0), np.concatenate(B1); nb = len(B0); BL = np.array(BL)
        tubes(out['bark'], curve(B0, B1, rng.normal(0, 0.12, (nb, 3)) + np.array([0, 0, 0.1]), 5), np.linspace(r0 * 0.32, r0 * 0.1, 5)[None].repeat(nb, 0), sides=5)
        # leaf clumps on the lobes' outer shells (share by lobe area), none buried inside a neighbouring lobe
        share = LR ** 2 / (LR ** 2).sum()
        cps, ccs = [], []
        for i in range(nl):
            m_ = max(8, int(F['clumps'] * share[i] * 1.6))
            d = _rand_dirs(rng, m_); d = d[d[:, 2] > -0.45]
            lump = 1 + 0.18 * np.sin(d @ rng.normal(0, 3.0, 3) + rng.uniform(0, 6.28))
            p_ = LC[i] + d * np.array([LR[i], LR[i], LZ[i]]) * (lump * (0.8 + 0.25 * rng.random(len(d)) ** 0.6))[:, None]
            inside = np.zeros(len(p_), bool)
            for j in range(nl):
                if j == i: continue
                q = (p_ - LC[j]) / np.array([LR[j], LR[j], LZ[j]])
                inside |= (q ** 2).sum(1) < 0.75
            p_ = p_[~inside][:max(4, int(F['clumps'] * share[i]))]
            cps.append(p_); ccs.append(np.repeat(LC[i][None], len(p_), 0))
        cp, cc = np.concatenate(cps), np.concatenate(ccs); n = len(cp)
        cp[:, 2] = np.maximum(cp[:, 2], st[:, 2].max() + 0.3)
        near = np.argmin(((cp[:, None, :] - B1[None, :, :]) ** 2).sum(-1), axis=1)
        tw = cp - _norm(cp - cc) * 0.22
        tubes(out['bark'], curve(B1[near], tw, rng.normal(0, 0.08, (n, 3)) + np.array([0, 0, 0.08]), 4), np.linspace(r0 * 0.09, r0 * 0.03, 4)[None].repeat(n, 0), sides=4)
        lo_, hi_ = F['leaves']
        k = rng.integers(lo_, hi_ + 1, n)
        ci = np.repeat(np.arange(n), k)
        o = _norm(cp - cc)[ci]
        e1, e2 = _frame(o)
        rr = 0.5 * np.sqrt(rng.random(len(ci))); ph = rng.uniform(0, 6.28, len(ci))
        P = cp[ci] + (np.cos(ph) * rr)[:, None] * e1 + (np.sin(ph) * rr)[:, None] * e2 + o * rng.normal(0, 0.12, (len(ci), 1))
        D = _norm(o * 0.5 + (np.cos(ph))[:, None] * e1 + (np.sin(ph))[:, None] * e2 + rng.normal(0, 0.35, (len(ci), 3)) - UP * 0.15)
        Nn = _norm(UP * 1.0 + o * 0.6 + rng.normal(0, 0.4, (len(ci), 3)))
        Lf = rng.uniform(*F['leaf'], len(ci))
        tpls = [leaf_tpl(_prof('tree'), fold=0.15, arch=a, cols=1, stations=(0, 0.3, 0.65, 1.0)) for a in (0.05, 0.18)]
        pk = rng.integers(0, 2, len(ci))
        aw = 0.7 if form == 'kiawe' else 1.0                                       # kiawe: fine pinnate leaflets
        for j, tp in enumerate(tpls):
            s = pk == j; place(out['leaf'], tp, P[s], D[s], Nn[s], Lf[s], rng.uniform(0.8, 1.2, s.sum()) * aw)
        return out
    rng = np.random.default_rng(seed)
    F = TREE_FORMS[form]
    out = {'leaf': Buf(), 'bark': Buf()}
    if bloom: out['bloom'] = Buf()
    Rx, Rz = F['R'][0] * rng.uniform(0.85, 1.15), F['R'][1] * rng.uniform(0.85, 1.15)
    th = rng.uniform(*F['trunk']); cz = F['cz'] * rng.uniform(0.92, 1.08)
    lean = np.array([rng.normal(0, 0.12), rng.normal(0, 0.12), 0])
    C = np.array([0, 0, cz]) + lean * cz
    # crown envelope with lumps (sub-crowns)
    nl = 11; Ld = _rand_dirs(rng, nl); Ld[:, 2] = np.abs(Ld[:, 2]) * 0.8 + 0.1; Ld = _norm(Ld)
    amp = rng.uniform(0.4, 1.0, nl) * F['lump']
    env = lambda d: 1 + (amp * np.exp((d @ Ld.T - 1) / 0.15)).sum(-1) - amp.sum() * 0.08
    rad = lambda d: env(d)[:, None] * np.array([Rx, Rx, Rz])
    # trunk with a flared, buttressed foot
    r0 = F['girth'] * rng.uniform(0.85, 1.15)
    t = np.linspace(0, 1, 7)[:, None]
    top = lean * th + np.array([0, 0, th])
    trunk = t * top + np.array([0, 0, 0]) * (1 - t) + (t * (1 - t)) * rng.normal(0, 0.15, 3) * np.array([1, 1, 0])
    tubes(out['bark'], trunk[None], (r0 * (1 + 0.45 * np.exp(-t[:, 0] * 9)) * (1 - 0.18 * t[:, 0]))[None], sides=10, v_scale=1.0)
    for a in rng.uniform(0, 6.28, rng.integers(3, 6)):            # root flares
        h = np.array([math.cos(a), math.sin(a), 0])
        p0 = h * r0 * 0.6 + np.array([0, 0, 0.45]); p1 = h * r0 * 2.3 + np.array([0, 0, -0.05])
        tubes(out['bark'], curve(p0[None], p1[None], (h * 0.08 + np.array([0, 0, -0.08]))[None], 4), np.array([[r0 * 0.4, r0 * 0.3, r0 * 0.2, r0 * 0.08]]), sides=6)
    # scaffold limbs from the top of the trunk toward the inner crown
    m = rng.integers(3, 6)
    az = rng.uniform(0, 6.28) + np.arange(m) * 2 * math.pi / m + rng.normal(0, 0.3, m)
    el = np.radians(rng.uniform(25, 60, m) if form != 'tall' else rng.uniform(45, 75, m))
    dl = np.stack([np.cos(az) * np.cos(el), np.sin(az) * np.cos(el), np.sin(el)], 1)
    L0 = top + rng.normal(0, 0.1, (m, 3)) * np.array([1, 1, 0]) - np.array([0, 0, 1]) * rng.uniform(0, 0.4, (m, 1))
    L1 = C + dl * rad(dl) * rng.uniform(0.35, 0.55, (m, 1))
    L1[:, 2] = np.maximum(L1[:, 2], top[2] + 0.6)
    tubes(out['bark'], curve(L0, L1, rng.normal(0, 0.25, (m, 3)) + np.array([0, 0, 0.25]), 6), np.linspace(r0 * 0.65, r0 * 0.38, 6)[None].repeat(m, 0), sides=8)
    # branches from every limb end toward the crown shell
    B0, B1 = [], []
    for i in range(m):
        k = rng.integers(3, 6)
        dd = _norm(dl[i] * 0.9 + rng.normal(0, 0.55, (k, 3)) + np.array([0, 0, 0.25]))
        B0.append(np.repeat(L1[i][None], k, 0) + rng.normal(0, 0.05, (k, 3)))
        B1.append(C + dd * rad(dd) * rng.uniform(0.6, 0.8, (k, 1)))
    B0, B1 = np.concatenate(B0), np.concatenate(B1); nb = len(B0)
    tubes(out['bark'], curve(B0, B1, rng.normal(0, 0.15, (nb, 3)) + np.array([0, 0, 0.12]), 5), np.linspace(r0 * 0.34, r0 * 0.12, 5)[None].repeat(nb, 0), sides=6)
    # leaf clumps in the outer shell, each on a twig from the nearest branch end
    n = F['clumps']
    d = _rand_dirs(rng, n * 3); d = d[d[:, 2] > -0.55][:n]; n = len(d)
    f = 0.74 + 0.3 * rng.random(n) ** 0.6
    cp = C + d * rad(d) * f[:, None]
    cp[:, 2] = np.maximum(cp[:, 2], top[2] + 0.4)
    near = np.argmin(((cp[:, None, :] - B1[None, :, :]) ** 2).sum(-1), axis=1)
    src = B1[near]
    tw = cp - _norm(cp - C) * 0.25
    tubes(out['bark'], curve(src, tw, rng.normal(0, 0.1, (n, 3)) + np.array([0, 0, 0.1]), 4), np.linspace(r0 * 0.1, r0 * 0.035, 4)[None].repeat(n, 0), sides=4)
    if bloom:      # pink shower tree (Cassia javanica): pendant clusters of pink-to-white flowers out on the crown
        ptp = leaf_tpl(_prof('obovate'), fold=0.05, cup=0.2, arch=0.05, stations=(0, 0.3, 0.7, 1.0), cols=1)
        for i in np.nonzero(rng.random(n) < bloom)[0]:
            o_ = _norm(cp[i] - C); nf = rng.integers(40, 80)
            fc = cp[i] + o_ * 0.18 - UP * rng.uniform(0.0, 0.25) + rng.normal(0, 1, (nf, 3)) * np.array([0.16, 0.16, 0.12])
            Df = _norm(rng.normal(0, 1, (nf, 3)) + o_ * 0.6)
            place(out['bloom'], ptp, fc, Df, _norm(np.cross(Df, rng.normal(0, 1, (nf, 3)))), rng.uniform(0.018, 0.028, nf), np.full(nf, 1.2))
    lo, hi = F['leaves']
    k = rng.integers(lo, hi + 1, n)
    ci = np.repeat(np.arange(n), k)
    o = _norm(cp - C)[ci]                                   # outward at the clump
    e1, e2 = _frame(o)
    rr = 0.48 * np.sqrt(rng.random(len(ci))); ph = rng.uniform(0, 6.28, len(ci))
    P = cp[ci] + (np.cos(ph) * rr)[:, None] * e1 + (np.sin(ph) * rr)[:, None] * e2 + o * rng.normal(0, 0.12, (len(ci), 1))
    D = _norm(o * 0.55 + (np.cos(ph))[:, None] * e1 + (np.sin(ph))[:, None] * e2 + rng.normal(0, 0.35, (len(ci), 3)) - UP * 0.2)
    Nn = _norm(UP * 1.0 + o * 0.7 + rng.normal(0, 0.4, (len(ci), 3)))
    Lf = rng.uniform(*F['leaf'], len(ci))
    tpls = [leaf_tpl(_prof('tree'), fold=0.15, arch=a, cols=1, stations=(0, 0.3, 0.65, 1.0)) for a in (0.05, 0.18)]
    pk = rng.integers(0, 2, len(ci))
    for j, tp in enumerate(tpls):
        s = pk == j; place(out['leaf'], tp, P[s], D[s], Nn[s], Lf[s], rng.uniform(0.8, 1.2, s.sum()))
    return out


def canopy_tree_old(seed):
    """A broad tropical shade tree (kamani / mango / monkeypod-like) about 8 m tall and wide."""
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'bark': Buf()}
    segs, tips = [], []
    def grow(p, d, L, r, depth):
        end = p + d * L
        t = np.linspace(0, 1, 5)[:, None]
        mid = (p + end) / 2 + rng.normal(0, 0.08, 3) * L
        segs.append(((1 - t) ** 2 * p + 2 * (1 - t) * t * mid + t * t * end, r, r * 0.75))
        if depth == 0 or r < 0.012:
            tips.append((end, d)); return
        k = rng.choice([2, 3, 3]) if depth < 5 else rng.choice([3, 4, 5])
        az0 = rng.uniform(0, 6.28)
        for j in range(k):
            az = az0 + j * 2 * math.pi / k + rng.normal(0, 0.4)
            hd = np.array([math.cos(az), math.sin(az), 0])
            up = rng.uniform(0.35, 0.8) if depth == 5 else rng.uniform(0.1, 0.5)
            nd = _norm(d * (0.2 if depth == 5 else 0.6) + hd * rng.uniform(0.6, 1.0) + UP * up)
            grow(end, nd, L * rng.uniform(0.6, 0.78) * (1.5 if depth == 5 else 1.0), r * 0.68, depth - 1)
    trunk_h = rng.uniform(1.4, 2.4)
    grow(np.zeros(3), _norm(UP + rng.normal(0, 0.08, 3) * np.array([1, 1, 0])), trunk_h, 0.24, 5)
    for path, r0, r1 in segs:
        tubes(out['bark'], path[None], np.linspace(r0, r1, len(path))[None], sides=7 if r0 > 0.05 else 4)
    tpls = [leaf_tpl(_prof('tree'), fold=0.15, arch=a, cols=1, stations=(0, 0.3, 0.65, 1.0)) for a in (0.05, 0.18)]
    Ps, Ds, Ns, Ls = [], [], [], []
    for pos, d in tips:
        # a clump of leafy twigs round the end of every branchlet
        nt = rng.integers(9, 15)
        tdir = _norm(d * 0.5 + rng.normal(0, 0.6, (nt, 3)) + UP * 0.35)
        tl = rng.uniform(0.3, 0.65, nt)
        base = pos + rng.normal(0, 0.25, (nt, 3))
        for j in range(nt):
            nl = rng.integers(10, 16)
            s = (np.arange(nl) + 0.5) / nl
            P = base[j] + tdir[j] * (tl[j] * s)[:, None]
            e1, e2 = _frame(tdir[j][None])
            ph = rng.uniform(0, 6.28) + np.arange(nl) * GOLDEN
            rad = np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2
            D = _norm(tdir[j] * 0.45 + rad - UP * 0.25)
            Ps.append(P); Ds.append(D); Ns.append(_norm(UP + rad * 0.3 + rng.normal(0, 0.3, (nl, 3)))); Ls.append(rng.uniform(0.11, 0.18, nl))
    P, D, Nn, L = map(np.concatenate, (Ps, Ds, Ns, Ls))
    pk = rng.integers(0, 2, len(P))
    for j, tp in enumerate(tpls):
        s = pk == j; place(out['leaf'], tp, P[s], D[s], Nn[s], L[s], rng.uniform(0.8, 1.2, s.sum()))
    return out


# ---------------------------------------------------------------- lawn
def grass_tile(seed, size=0.5, density=22000, wh=None, keep=None, hscale=1.0):
    """A square of mown turf: blades 4-8 cm, cut tips, leaning every way; tiles seamlessly at `size`.
    wh: a (w, h) rectangle from the origin instead; keep: mask on the blade roots; hscale: mown shorter."""
    rng = np.random.default_rng(seed)
    if wh is None:
        n = int(size * size * density)
        base = np.concatenate([(rng.random((n, 2)) - 0.5) * size, np.zeros((n, 1))], 1)
    else:
        n = int(wh[0] * wh[1] * density)
        base = np.concatenate([rng.random((n, 2)) * np.asarray(wh), np.zeros((n, 1))], 1)
    if keep is not None:
        base = base[keep(base[:, :2])]; n = len(base)
    h = np.clip(rng.normal(0.058, 0.012, n), 0.025, 0.1) * hscale
    young = rng.random(n) < 0.25                       # new, uncut blades are pointed and a little taller
    h[young] *= 1.15
    az = rng.uniform(0, 6.28, n); tilt = np.radians(rng.uniform(4, 38, n)); curl = np.radians(rng.uniform(5, 45, n))
    lean = np.stack([np.cos(az), np.sin(az), np.zeros(n)], 1)
    side = np.stack([-np.sin(az), np.cos(az), np.zeros(n)], 1)
    tw = rng.normal(0, 0.5, n)
    side = _norm(side + lean * tw[:, None] * 0.3)
    w0 = rng.uniform(0.0022, 0.0038, n)
    ts = np.array([0.0, 0.38, 0.72, 1.0])
    pts, p = [base], base.copy()
    for i in range(1, 4):
        a = tilt + curl * (ts[i - 1] + ts[i]) / 2
        d = lean * np.sin(a)[:, None] + UP * np.cos(a)[:, None]
        p = p + d * (h * (ts[i] - ts[i - 1]))[:, None]; pts.append(p)
    widths = [w0, w0 * 0.95, w0 * 0.8, np.where(young, w0 * 0.05, w0 * 0.55)]
    V = np.stack([np.stack([q - side * (w / 2)[:, None], q + side * (w / 2)[:, None]], 1) for q, w in zip(pts, widths)], 1)   # (n,4,2,3)
    UV = np.broadcast_to(np.stack(np.meshgrid([0.0, 1.0], ts), -1)[None], (n, 4, 2, 2))
    a = np.array([[0, 1, 3, 2], [2, 3, 5, 4], [4, 5, 7, 6]])
    F = (a[None] + (np.arange(n) * 8)[:, None, None]).reshape(-1, 4)
    buf = Buf(); buf.add(V.reshape(-1, 3), F, UV.reshape(-1, 2))
    return buf


PAVER_PITCH = 0.24          # m, flat to flat (r3: ~30% smaller cells than the slab material's 0.34 m lattice, which the
                            # opaque turf base of every tile now hides - critic r2 front #11)
R3 = math.sqrt(3.0)


def _hex_edge(xy, s=PAVER_PITCH):
    """Metres from the nearest rib centre line for points xy (tile coords, lattice origin at 0,0)."""
    q = xy / s
    C = np.array([[0, 0], [1, 0], [0, R3], [1, R3], [0.5, R3 / 2]])
    d = q[:, None, :] - C[None]
    k = np.argmin((d ** 2).sum(-1), 1)
    o = np.abs(d[np.arange(len(q)), k])
    hexd = np.maximum(o[:, 0], 0.5 * o[:, 0] + R3 / 2 * o[:, 1])
    return (0.5 - hexd) * s


def paver_tile(seed, s=PAVER_PITCH, margin=0.022, rib_w=0.024, rib_h=0.012, hscale=0.3, over=0.1):
    """One period (s x s*sqrt3) of the grass-paver drive: turf inside the hex cells (a share of the blades
    leaning over the ribs), raised grey concrete ribs, and an opaque thatch base under the blades so the slab
    material never shows through (front rendering p4)."""
    kr = np.random.default_rng(seed + 17)
    keep = lambda xy: (_hex_edge(xy, s) > margin) | (kr.random(len(xy)) < over)
    buf = grass_tile(seed, wh=(s, s * R3), density=30000, keep=keep, hscale=hscale)
    base = Buf(); base.add([(0, 0, 0.004), (s, 0, 0.004), (s, s * R3, 0.004), (0, s * R3, 0.004)], [[0, 1, 2, 3]], [(0, 0), (1, 0), (1, 1), (0, 1)], mat=2)
    buf.extend(base)
    rib = Buf()
    hw = rib_w / 2
    for c in ((0.0, 0.0), (0.5, R3 / 2)):
        cx, cy = c
        Vh = [(0.5, -0.5 / R3), (0.5, 0.5 / R3), (0.0, 1 / R3), (-0.5, 0.5 / R3)]
        for a, b_ in zip(Vh[:-1], Vh[1:]):
            p0 = np.array([cx + a[0], cy + a[1]]) * s; p1 = np.array([cx + b_[0], cy + b_[1]]) * s
            t = (p1 - p0) / np.linalg.norm(p1 - p0); nrm = np.array([-t[1], t[0]])
            p0 = p0 - t * hw; p1 = p1 + t * hw
            q = [p0 - nrm * hw, p1 - nrm * hw, p1 + nrm * hw, p0 + nrm * hw]
            V = [(x, y, rib_h) for x, y in q] + [(x, y, -0.01) for x, y in q]
            F = [[0, 1, 2, 3], [4, 5, 1, 0], [5, 6, 2, 1], [6, 7, 3, 2], [7, 4, 0, 3]]
            rib.add(V, F, [(x * 4, y * 4) for x, y, _ in V], mat=1)
    buf.extend(rib)
    return buf


def grass_material(per_instance=False, wear=0.0):
    """wear: share of straw yellowing (the thinner, drier turf along wall bases and bed edges)."""
    m = bpy.data.materials.new('plant paver turf' if per_instance else 'plant lawn edge' if wear else 'plant lawn'); nt, N, L = _nodes(m)
    out = N.new('ShaderNodeOutputMaterial')
    geo = N.new('ShaderNodeNewGeometry'); uvn = N.new('ShaderNodeUVMap'); sep = N.new('ShaderNodeSeparateXYZ')
    L.new(uvn.outputs['UV'], sep.inputs[0])
    ramp = N.new('ShaderNodeValToRGB'); e = ramp.color_ramp.elements
    # manicured Bermuda / zoysia: warm yellow-green (sunlit lawn in the renderings ~#a8b340), not blue-green
    e[0].position = 0.0; e[0].color = _lin('#46661f'); e[1].position = 1.0; e[1].color = _lin('#94a040')
    e.new(0.3).color = _lin('#557624'); e.new(0.62).color = _lin('#64862a'); e.new(0.88).color = _lin('#789234')
    e.new(0.975).color = _lin('#988e4a')
    L.new(geo.outputs['Random Per Island'], ramp.inputs['Fac'])
    # lawn-scale mottling (soil, water, wear): world-position noise, so neighbouring tiles agree
    no = N.new('ShaderNodeTexNoise'); no.inputs['Scale'].default_value = 0.35; no.inputs['Detail'].default_value = 4
    L.new(geo.outputs['Position'], no.inputs['Vector'])
    nm = N.new('ShaderNodeMapRange'); nm.inputs['From Min'].default_value = 0.3; nm.inputs['From Max'].default_value = 0.7
    nm.inputs['To Min'].default_value = 0.78; nm.inputs['To Max'].default_value = 1.15
    L.new(no.outputs['Fac'], nm.inputs['Value'])
    hsv = N.new('ShaderNodeHueSaturation'); L.new(ramp.outputs['Color'], hsv.inputs['Color']); L.new(nm.outputs['Result'], hsv.inputs['Value'])
    if not per_instance:
        # r4 (critic preview3 back #3): the lawn read saturated chartreuse (hue ~72, sat ~0.65); a sunlit Hawaiian
        # Bermuda / zoysia lawn is a soft olive-straw green (~hue 56-60, sat ~0.4): shift the hue, cut saturation
        # ~35%, lift value ~15%; broad patches (irrigation, soil) shift hue and value over ~10-20 m; faint mowing
        # stripes ~1.2 m wide along the lot (light / dark as the blades lie toward / away from the sun)
        lf = N.new('ShaderNodeTexNoise'); lf.inputs['Scale'].default_value = 0.07; lf.inputs['Detail'].default_value = 2
        L.new(geo.outputs['Position'], lf.inputs['Vector'])
        lh = N.new('ShaderNodeMapRange'); lh.inputs['From Min'].default_value = 0.35; lh.inputs['From Max'].default_value = 0.65
        lh.inputs['To Min'].default_value = 0.448; lh.inputs['To Max'].default_value = 0.472; L.new(lf.outputs['Fac'], lh.inputs['Value'])
        lv = N.new('ShaderNodeMapRange'); lv.inputs['From Min'].default_value = 0.35; lv.inputs['From Max'].default_value = 0.65
        lv.inputs['To Min'].default_value = 1.14; lv.inputs['To Max'].default_value = 1.3; L.new(lf.outputs['Fac'], lv.inputs['Value'])
        sx = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Position'], sx.inputs[0])
        sw = N.new('ShaderNodeMath'); sw.operation = 'SINE'
        sm = N.new('ShaderNodeMath'); sm.operation = 'MULTIPLY'; sm.inputs[1].default_value = math.pi / 1.2
        L.new(sx.outputs['X'], sm.inputs[0]); L.new(sm.outputs[0], sw.inputs[0])
        sq = N.new('ShaderNodeMapRange'); sq.inputs['From Min'].default_value = -0.35; sq.inputs['From Max'].default_value = 0.35
        sq.inputs['To Min'].default_value = 0.955; sq.inputs['To Max'].default_value = 1.045; L.new(sw.outputs[0], sq.inputs['Value'])
        vv = N.new('ShaderNodeMath'); vv.operation = 'MULTIPLY'; L.new(lv.outputs['Result'], vv.inputs[0]); L.new(sq.outputs['Result'], vv.inputs[1])
        g2 = N.new('ShaderNodeHueSaturation'); g2.inputs['Saturation'].default_value = 0.62
        L.new(hsv.outputs['Color'], g2.inputs['Color']); L.new(lh.outputs['Result'], g2.inputs['Hue']); L.new(vv.outputs[0], g2.inputs['Value'])
        hsv = g2
        if wear:
            wn = N.new('ShaderNodeTexNoise'); wn.inputs['Scale'].default_value = 2.5; L.new(geo.outputs['Position'], wn.inputs['Vector'])
            wm = N.new('ShaderNodeMapRange'); wm.inputs['To Min'].default_value = wear * 0.4; wm.inputs['To Max'].default_value = wear * 1.6
            L.new(wn.outputs['Fac'], wm.inputs['Value'])
            wy = N.new('ShaderNodeMix'); wy.data_type = 'RGBA'; wy.inputs[7].default_value = _lin('#9a9058')
            L.new(wm.outputs['Result'], wy.inputs['Factor']); L.new(hsv.outputs['Color'], wy.inputs[6])
            hp = N.new('ShaderNodeHueSaturation'); L.new(wy.outputs[2], hp.inputs['Color']); hsv = hp     # (keeps a 'Color' output)
    if per_instance:
        # grass pavers: every cell grows a little differently (hue, vigour), greener than lime (critic r2 front #11)
        oi = N.new('ShaderNodeObjectInfo')
        hu = N.new('ShaderNodeMapRange'); hu.inputs['To Min'].default_value = 0.505; hu.inputs['To Max'].default_value = 0.54
        va = N.new('ShaderNodeMapRange'); va.inputs['To Min'].default_value = 0.72; va.inputs['To Max'].default_value = 1.08
        sa = N.new('ShaderNodeMapRange'); sa.inputs['To Min'].default_value = 0.78; sa.inputs['To Max'].default_value = 0.98
        fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; mu = N.new('ShaderNodeMath'); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = 7.13
        L.new(oi.outputs['Random'], mu.inputs[0]); L.new(mu.outputs[0], fr.inputs[0])
        L.new(oi.outputs['Random'], hu.inputs['Value']); L.new(fr.outputs[0], va.inputs['Value']); L.new(oi.outputs['Random'], sa.inputs['Value'])
        h2 = N.new('ShaderNodeHueSaturation'); L.new(hsv.outputs['Color'], h2.inputs['Color'])
        L.new(hu.outputs['Result'], h2.inputs['Hue']); L.new(va.outputs['Result'], h2.inputs['Value']); L.new(sa.outputs['Result'], h2.inputs['Saturation'])
        hsv = h2
    # darker, yellower at the base (thatch), straw on cut tips
    base = N.new('ShaderNodeMapRange'); base.inputs['From Min'].default_value = 0.0; base.inputs['From Max'].default_value = 0.45
    base.inputs['To Min'].default_value = 0.35; base.inputs['To Max'].default_value = 1.0
    L.new(sep.outputs['Y'], base.inputs['Value'])
    mb = N.new('ShaderNodeMix'); mb.data_type = 'RGBA'; mb.blend_type = 'MULTIPLY'; mb.inputs['Factor'].default_value = 1.0
    cb = N.new('ShaderNodeCombineXYZ'); L.new(base.outputs['Result'], cb.inputs['X']); L.new(base.outputs['Result'], cb.inputs['Y'])
    bz = N.new('ShaderNodeMath'); bz.operation = 'MULTIPLY'; bz.inputs[1].default_value = 0.8; L.new(base.outputs['Result'], bz.inputs[0]); L.new(bz.outputs[0], cb.inputs['Z'])
    L.new(hsv.outputs['Color'], mb.inputs[6]); L.new(cb.outputs['Vector'], mb.inputs[7])
    tipm = N.new('ShaderNodeMapRange'); tipm.inputs['From Min'].default_value = 0.9; tipm.inputs['From Max'].default_value = 1.0
    L.new(sep.outputs['Y'], tipm.inputs['Value'])
    tf = N.new('ShaderNodeMath'); tf.operation = 'MULTIPLY'; tf.inputs[1].default_value = 0.45; L.new(tipm.outputs['Result'], tf.inputs[0])
    mt = N.new('ShaderNodeMix'); mt.data_type = 'RGBA'; mt.inputs[7].default_value = _lin('#a39a5a')
    L.new(tf.outputs[0], mt.inputs['Factor']); L.new(mb.outputs[2], mt.inputs[6])
    col = mt.outputs[2]
    p = N.new('ShaderNodeBsdfPrincipled'); p.inputs['Roughness'].default_value = 0.42; p.inputs['Specular IOR Level'].default_value = 0.45
    L.new(col, p.inputs['Base Color'])
    tr = N.new('ShaderNodeBsdfTranslucent')
    tt = N.new('ShaderNodeMix'); tt.data_type = 'RGBA'; tt.blend_type = 'MULTIPLY'; tt.inputs['Factor'].default_value = 1.0; tt.inputs[7].default_value = (1.3, 1.4, 0.55, 1)
    L.new(col, tt.inputs[6]); L.new(tt.outputs[2], tr.inputs['Color'])
    # r5 (critique-preview4-front #7): albedo +12 % and a larger translucent share, so lawn in shade keeps its blades
    # (sky light through the blades) instead of crushing to near-black
    br_ = N.new('ShaderNodeMix'); br_.data_type = 'RGBA'; br_.blend_type = 'MULTIPLY'; br_.inputs['Factor'].default_value = 1.0
    br_.inputs[7].default_value = (1.12, 1.12, 1.08, 1.0); L.new(col, br_.inputs[6]); L.new(br_.outputs[2], p.inputs['Base Color'])
    ms = N.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = 0.4
    L.new(p.outputs['BSDF'], ms.inputs[1]); L.new(tr.outputs['BSDF'], ms.inputs[2]); L.new(ms.outputs['Shader'], out.inputs['Surface'])
    return m


# ---------------------------------------------------------------- materials for every kind
def materials():
    M = {}
    def leaf(key, seed, base, mid, **kw):
        lk = {k: kw.pop(k) for k in list(kw) if k in ('n_veins', 'angle', 'vein', 'vein_w', 'margin', 'mott', 'aspect', 'sunken', 'reticulate', 'edge', 'variegate', 'base_tint')}
        img, him = leaf_image('leaf-' + key, seed, _lin(base), _lin(mid), **lk)
        M[key] = leaf_material('plant ' + key, img, him, **kw)
    leaf('bougainvillea', 1, '#3d6a24', '#7a9a44', n_veins=6, angle=50, vein=0.3, rough=0.48, transl=0.32, val_var=0.2)
    leaf('gardenia', 2, '#1f4317', '#4f7a2e', n_veins=9, angle=58, vein=0.45, rough=0.22, spec=0.65, transl=0.2, bump=0.5, coat=0.25, val_var=0.15)
    leaf('hedge', 3, '#2b5520', '#5a8236', n_veins=7, angle=55, vein=0.25, rough=0.3, spec=0.6, transl=0.25, val_var=0.18)
    # r6 (critique-preview5-back #2): the side-lot screen read as a near-black wall behind the right bougainvillea bed: its
    # own leaf at ~1.5x the hedge's linear albedo, a larger share of light through the leaves and a paler back face
    leaf('screen', 21, '#36672a', '#6e9c44', n_veins=7, angle=55, vein=0.25, rough=0.34, spec=0.55, transl=0.45, val_var=0.2, hue_var=0.04,
         trans_tint=(1.35, 1.45, 0.65), back=(1.3, 1.35, 1.15))
    leaf('groundcover', 4, '#6f8a68', '#9aae90', n_veins=5, angle=50, vein=0.2, rough=0.55, transl=0.2, sheen=0.6, val_var=0.12, sat_var=0.15)
    leaf('monstera', 5, '#25501a', '#3f6a28', n_veins=14, angle=89, vein=0.35, vein_w=0.006, aspect=0.5, rough=0.42, spec=0.36, transl=0.2, bump=0.3, val_var=0.12, back=(1.1, 1.12, 1.0))
    leaf('plumeria', 6, '#335d1e', '#86a04a', n_veins=22, angle=75, vein=0.42, vein_w=0.007, rough=0.36, transl=0.3, bump=0.45, val_var=0.15, dry=(1.6, 1.1, 0.25, 1), dry_share=0.05)
    # r5 (critique-preview4-back #11): ti toward p5's dark burgundy - value and saturation ~30 % lower than r4's crimson
    leaf('ti-red', 7, '#4d292e', '#61363f', n_veins=40, angle=12, vein=0.15, vein_w=0.004, aspect=0.12, rough=0.38, spec=0.4, transl=0.36, trans_tint=(1.3, 0.75, 0.8),
         variegate=(_lin('#7b484f'), 0.3), edge=_lin('#804f58'), val_var=0.2, hue_var=0.015, back=(1.0, 1.0, 1.0))
    leaf('ti-burgundy', 8, '#3e1a21', '#52232f', n_veins=40, angle=12, vein=0.15, vein_w=0.004, aspect=0.12, rough=0.36, spec=0.4, transl=0.32, trans_tint=(1.4, 0.75, 0.85),
         edge=_lin('#7b484f'), val_var=0.2, hue_var=0.015, back=(1.0, 1.0, 1.0))
    leaf('ti-green', 9, '#3e4a1c', '#5a6a2a', n_veins=40, angle=12, vein=0.15, vein_w=0.004, aspect=0.12, rough=0.38, spec=0.4, transl=0.32,
         variegate=(_lin('#6e1a30'), 0.35), val_var=0.2, hue_var=0.03, back=(1.0, 1.0, 1.0))
    leaf('tree', 10, '#2f5a22', '#5f8a3a', n_veins=8, angle=55, vein=0.25, rough=0.4, transl=0.3, val_var=0.22, hue_var=0.04, dry=(1.5, 1.2, 0.3, 1), dry_share=0.04)
    leaf('tree-dark', 11, '#22451a', '#4a6e2c', n_veins=10, angle=60, vein=0.25, rough=0.3, spec=0.6, transl=0.25, val_var=0.2, hue_var=0.03)
    leaf('tree-light', 12, '#4a7a2c', '#7a9a45', n_veins=7, angle=50, vein=0.25, rough=0.45, transl=0.32, val_var=0.22, hue_var=0.05)
    # r5 (critique-preview4-back #11): magenta bracts (hue ~320), not blue-violet heliotrope
    bimg, bh = leaf_image('bract', 13, _lin('#b02883'), _lin('#d65aa8'), n_veins=7, angle=40, vein=0.35, vein_w=0.012, margin=0.1, mott=0.08, sunken=False)
    M['bract'] = petal_material('plant bract', _lin('#b02883'), vein_img=bimg, transl=0.45, rough=0.5, sheen=0.15)
    M['jasmine-petal'] = petal_material('plant jasmine petal', _lin('#eee4c4'), transl=0.4, rough=0.6, sheen=0.15)
    M['floret'] = petal_material('plant floret', _lin('#f2ead2'), transl=0.4)
    M['petal'] = petal_material('plant petal', _lin('#f6f2e4'), transl=0.42, rough=0.5, sheen=0.35)
    M['plumeria-petal'] = petal_material('plant plumeria petal', _lin('#f7f4ea'), _lin('#f2b818'), center_len=0.42, transl=0.42, rough=0.45, sheen=0.35)
    M['heliconia-bract'] = petal_material('plant heliconia bract', _lin('#c42a1c'), _lin('#d8c040'), center_len=0.25, transl=0.3, rough=0.35, sheen=0.1)
    M['hibiscus-petal'] = petal_material('plant hibiscus petal', _lin('#c8202a'), _lin('#7a0a14'), center_len=0.2, transl=0.5, rough=0.45, sheen=0.3)
    M['shower-petal'] = petal_material('plant shower petal', _lin('#e9a2bd'), _lin('#f6e2ea'), center_len=0.5, transl=0.45, rough=0.5, sheen=0.3)
    M['bud'] = plain_material('plant bud', _lin('#d9dcc0'), 0.5, 0.3)
    M['dry'] = leaf_material('plant dry leaf', *leaf_image('leaf-dry', 14, _lin('#6e5530'), _lin('#8a7040'), n_veins=30, angle=12, aspect=0.12), rough=0.7, transl=0.2)
    M['stem'] = bark_material('plant stem', _lin('#5c4a38'), _lin('#33281e'), scale=30, bump=0.2)
    M['green-stem'] = plain_material('plant petiole', _lin('#3a5a22'), 0.4, 0.15)
    M['cane'] = bark_material('plant ti cane', _lin('#7a6c5a'), _lin('#4a3e32'), scale=40, rings=0.018, ring_col=_lin('#3a3028'), bump=0.5)
    M['plumeria-bark'] = bark_material('plant plumeria bark', _lin('#5e5e54'), _lin('#3a3a32'), scale=14, lichen=_lin('#a8a690'), bump=0.3, stretch=2.0)
    M['tree-bark'] = bark_material('plant tree bark', _lin('#5a5048'), _lin('#2e2822'), scale=9, lichen=_lin('#7a786a'), bump=0.6, stretch=5.0)
    leaf('mondo', 15, '#3c5832', '#6e8e58', n_veins=12, angle=8, vein=0.12, vein_w=0.004, aspect=0.06, rough=0.4, spec=0.4, transl=0.42, val_var=0.15)
    leaf('tradescantia', 16, '#4a2050', '#6b3a7a', n_veins=14, angle=10, vein=0.15, aspect=0.2, rough=0.4, spec=0.45, transl=0.25, sheen=0.4, val_var=0.15,
         trans_tint=(1.2, 0.6, 1.3))
    # r5 (critique-preview4-back #12): less mirror-glossy (the r4 glints read as white glitter), more leaf-to-leaf value
    leaf('jasmine', 17, '#1f3a18', '#3f6a2e', n_veins=7, angle=50, vein=0.4, vein_w=0.008, rough=0.42, spec=0.42, transl=0.22, bump=0.4, coat=0.06, val_var=0.3, hue_var=0.03)
    leaf('dichondra', 18, '#8a967a', '#b4bea0', n_veins=6, angle=55, vein=0.15, rough=0.6, transl=0.25, sheen=0.7, val_var=0.1, sat_var=0.1)
    leaf('heliconia', 20, '#2a5a1e', '#4f7f30', n_veins=40, angle=70, vein=0.15, vein_w=0.004, aspect=0.35, rough=0.4, spec=0.45, transl=0.35, val_var=0.15,
         dry=(1.5, 1.1, 0.3, 1), dry_share=0.08)
    leaf('alocasia', 19, '#2a5222', '#4a7634', n_veins=9, angle=62, vein=0.5, vein_w=0.01, aspect=0.75, rough=0.45, spec=0.4, transl=0.4, bump=0.6, val_var=0.12)
    M['lawn'] = grass_material()
    M['lawn-edge'] = grass_material(wear=0.3)
    # turf thatch under the blades, matched to their shaded base, so a gap reads as shade, not as green paint (back #3)
    M['thatch'] = plain_material('plant lawn thatch', _lin('#45531f'), 0.95)
    M['mulch'] = mulch_material()
    M['edging'] = plain_material('plant bed edging', _lin('#3c3a35'), 0.55)
    M['paver-rib'] = plain_material('plant paver rib', _lin('#85837b'), 0.9)          # concrete grey (~150-160 sRGB lit), not white
    M['paver-base'] = plain_material('plant paver turf base', _lin('#3e4c22'), 0.95)   # turf thatch filling each cell
    M['paver-lawn'] = grass_material(per_instance=True)
    M['stone-edging'] = plain_material('plant bed stone edging', _lin('#a69b86'), 0.85)   # tan coral stone edging (p4)
    return M


# ---------------------------------------------------------------- variants
def _variants(name, n, fn, mats, keymap):
    """Builds n variants with fn(i) -> {key: Buf}; keymap: key -> material key."""
    objs = []
    for i in range(n):
        parts = fn(i)
        keys = [k for k in parts if parts[k].v]
        mlist = [mats[keymap[k] if isinstance(keymap[k], str) else keymap[k](i)] for k in keys]
        objs.append(join(f'{name}{i}', [(parts[k], j) for j, k in enumerate(keys)], mlist))
    return proto_collection(name, objs)


# ---------------------------------------------------------------- ground and coverage
def _terrain_objects():
    return [o for o in bpy.data.objects if o.type == 'MESH' and any(m and m.name.startswith('terrain') for m in o.data.materials)]


def _world_tris(objs, box=None, zmax=None):
    from mathutils.bvhtree import BVHTree
    Vs, Ts, off = [], [], 0
    for o in objs:
        me = o.data
        if not len(me.polygons): continue
        me.calc_loop_triangles()
        v = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', v); v = v.reshape(-1, 3)
        M = np.array(o.matrix_world); v = v @ M[:3, :3].T + M[:3, 3]
        t = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', t); t = t.reshape(-1, 3)
        tv = v[t]
        keep = np.ones(len(t), bool)
        if box is not None:
            x0, y0, x1, y1 = box
            keep &= (tv[..., 0].max(1) > x0) & (tv[..., 0].min(1) < x1) & (tv[..., 1].max(1) > y0) & (tv[..., 1].min(1) < y1)
        if zmax is not None: keep &= tv[..., 2].min(1) < zmax
        if not keep.any(): continue
        t = t[keep]; used = np.unique(t); remap = np.full(len(v), -1, np.int64); remap[used] = np.arange(len(used))
        Vs.append(v[used]); Ts.append(remap[t] + off); off += len(used)
    if not Vs: return None
    V = np.concatenate(Vs); T = np.concatenate(Ts)
    return BVHTree.FromPolygons(V.tolist(), T.tolist(), all_triangles=True)


class Ground:
    def __init__(self, box=None, context_box=None):
        # context_box: also the DEM surround ('realsite near') inside that box, where it rises through the lot's terrain
        # (r5, critique-preview4-back #3: a strip of bare DEM where it crossed the pad read as balding astroturf);
        # the top-most surface wins, since that is the one that shows
        self.bvh = _world_tris(_terrain_objects(), box=box)
        self.ctx = None
        if context_box is not None:
            objs = [o for o in bpy.data.objects if o.type == 'MESH' and any(m and m.name.startswith('realsite near') for m in o.data.materials)]
            self.ctx = _world_tris(objs, box=context_box) if objs else None

    def _hit(self, x, y):
        best = None
        for t in (self.bvh, self.ctx):
            if t is None: continue
            loc, nrm, _, _ = t.ray_cast(Vector((x, y, 500.0)), Vector((0, 0, -1)), 2000.0)
            if loc is not None and (best is None or loc.z > best[0].z + 1e-4): best = (loc, nrm)
        return best

    def z(self, x, y, default=0.0):
        if self.bvh is None: return default
        h = self._hit(x, y)
        return h[0].z if h is not None else None

    def zn(self, x, y):
        if self.bvh is None: return None, None
        h = self._hit(x, y)
        return (h[0].z, h[1]) if h is not None else (None, None)


def lawn_cells(ground, cover, box, beds, cell=0.5, sub=4):
    """Open lawn in box (Blender xy): ground present, nothing within 35 cm above it, not inside a
    solid, not in a bed. Returns full cells and edge sub-cells: lists of (x, y, z, normal)."""
    x0, y0, x1, y1 = box
    full, part = [], []
    sc = cell / sub
    offs = (np.arange(sub) + 0.5) * sc - cell / 2
    down, up = Vector((0, 0, -1)), Vector((0, 0, 1))
    def ok(x, y):
        # beds: (rect, outline or None); a curved bed keeps the lawn out only inside its outline
        if any(bx0 < x < bx1 and by0 < y < by1 and (pl is None or _inside(pl, ((x, y),))[0]) for (bx0, by0, bx1, by1), pl in beds): return None
        z, n = ground.zn(x, y)
        if z is None or n.z < 0.5: return None
        if cover is not None:
            h = cover.ray_cast(Vector((x, y, z + 0.35)), down, 0.38)
            if h[0] is not None and h[0].z > z - 0.03: return None
            h = cover.ray_cast(Vector((x, y, z + 0.02)), up, 1.2)
            if h[0] is not None and h[1].z > 0.2: return None              # inside a solid (wall, step)
        return z, n
    for cx in np.arange(x0 + cell / 2, x1, cell):
        for cy in np.arange(y0 + cell / 2, y1, cell):
            res = [[ok(cx + dx, cy + dy) for dy in offs] for dx in offs]
            good = [r for row in res for r in row if r is not None]
            if len(good) == sub * sub:
                z = float(np.mean([g[0] for g in good])); full.append((cx, cy, z, res[sub // 2][sub // 2][1]))
            elif good:
                for i, dx in enumerate(offs):
                    for j, dy in enumerate(offs):
                        if res[i][j] is not None: part.append((cx + dx, cy + dy, res[i][j][0], res[i][j][1]))
    return full, part


def _tilt_euler(normals, rz):
    out = np.zeros((len(rz), 3))
    for i, (n, a) in enumerate(zip(normals, rz)):
        q = Vector((0, 0, 1)).rotation_difference(Vector(n)) if n is not None else None
        m = Matrix.Rotation(a, 3, 'Z')
        if q is not None: m = q.to_matrix() @ m
        out[i] = m.to_euler('XYZ')[:]
    return out


def mulch(ground, rect, mat, col, name, rng, zref=None, tol=1e9, edge_mat=None, slope=False):
    """A bed of bark mulch over rect (Blender xy), following the ground, edges slightly ragged.
    Robust to steps: grid points whose ground is missing, steep, or more than `tol` from the bed's
    level (zref, else the median) are dropped, and so is every quad spanning a height jump, so the
    mulch never climbs a retaining wall or hangs over a drop."""
    x0, y0, x1, y1 = rect
    nx = max(2, int((x1 - x0) / 0.25) + 1); ny = max(2, int((y1 - y0) / 0.25) + 1)
    xs = np.linspace(x0 - 0.12, x1 + 0.12, nx); ys = np.linspace(y0 - 0.12, y1 + 0.12, ny)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    edge = np.minimum(np.minimum(X - xs[0], xs[-1] - X), np.minimum(Y - ys[0], ys[-1] - Y))
    if edge_mat is None:
        X = X + (edge < 0.01) * rng.normal(0, 0.04, X.shape); Y = Y + (edge < 0.01) * rng.normal(0, 0.04, Y.shape)
    Z = np.full_like(X, np.nan)
    for i in range(nx):
        for j in range(ny):
            z, n = ground.zn(X[i, j], Y[i, j])
            if z is not None and n.z > (0.12 if slope else 0.55): Z[i, j] = z
    ok = ~np.isnan(Z)
    if not ok.any(): return None
    ref = zref if zref is not None else float(np.median(Z[ok]))
    ok &= np.abs(np.where(ok, Z, ref) - ref) < tol
    Z = np.where(ok, Z, ref) + 0.012 + np.where(edge > 0.2, 0.02, 0.0)
    q = ok[:-1, :-1] & ok[1:, :-1] & ok[1:, 1:] & ok[:-1, 1:]
    Zq = np.stack([Z[:-1, :-1], Z[1:, :-1], Z[1:, 1:], Z[:-1, 1:]], -1)
    q &= (Zq.max(-1) - Zq.min(-1)) < (0.9 if slope else 0.14)
    ii, jj = np.nonzero(q)
    if not len(ii): return None
    a = ii * ny + jj
    F = np.stack([a, a + ny, a + ny + 1, a + 1], -1)
    buf = Buf(); buf.add(np.stack([X, Y, Z], -1).reshape(-1, 3), F, np.stack([X, Y], -1).reshape(-1, 2))
    if edge_mat is not None:
        # a defined bed: a dark steel edging strip standing 3 cm proud round the mulch, where the ground allows
        Zg = Z - 0.012 - np.where(edge > 0.2, 0.02, 0.0)
        ring = [(i, 0) for i in range(nx)] + [(nx - 1, j) for j in range(1, ny)] + [(i, ny - 1) for i in range(nx - 2, -1, -1)] + [(0, j) for j in range(ny - 2, 0, -1)] + [(0, 0)]
        for (i0, j0), (i1, j1) in zip(ring[:-1], ring[1:]):
            if not (ok[i0, j0] and ok[i1, j1]) or abs(Zg[i0, j0] - Zg[i1, j1]) > 0.14: continue
            a_, b_ = (X[i0, j0], Y[i0, j0], Zg[i0, j0]), (X[i1, j1], Y[i1, j1], Zg[i1, j1])
            buf.add([(a_[0], a_[1], a_[2] - 0.03), (b_[0], b_[1], b_[2] - 0.03), (b_[0], b_[1], b_[2] + 0.045), (a_[0], a_[1], a_[2] + 0.045)],
                    [[0, 1, 2, 3]], [(0, 0), (1, 0), (1, 1), (0, 1)], mat=1)
    me = buf.mesh(name, [mat] + ([edge_mat] if edge_mat is not None else []))
    # drop the unused grid points
    try:
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS'); bm.to_mesh(me); bm.free()
    except Exception: pass
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    return ob


# ---------------------------------------------------------------- curved beds (critic r2 back #12, front #13)
def bed_spec(kind):
    """A bed's kind as exported by src/plants.js: 'mondo', 'mondo@y0' (curved plan sides), 'ti@!' (no edging)."""
    if '@' not in kind: return kind, '', True
    k, spec = kind.split('@', 1)
    return k, spec.replace('!', ''), '!' not in spec


def _smooth(t):
    t = np.clip(t, 0.0, 1.0); return t * t * (3 - 2 * t)


def bed_outline(rect, sides, seed, step=0.1):
    """Counter-clockwise outline (n,2) of a bed in Blender xy whose curved sides sweep inward in soft waves
    (rounded corners between two curved sides, straight sides stay on the rect). sides: plan sides
    'x0 x1 y0 y1' (plan y0 is Blender's top edge: three z -> Blender -y)."""
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    c = {'b': 'y1' in sides, 'r': 'x1' in sides, 't': 'y0' in sides, 'l': 'x0' in sides}
    rng = np.random.default_rng(seed & 0xffffffff)
    opp = (c['b'] and c['t']) or (c['l'] and c['r'])
    amp = min(0.9, (0.22 if opp else 0.42) * min(w, h))
    Rc = min(0.48 * min(w, h), max(1.6 * amp, 0.6))
    rad = {k: (Rc if c[a] and c[b] else 0.0) for k, (a, b) in {'br': ('b', 'r'), 'tr': ('t', 'r'), 'tl': ('t', 'l'), 'bl': ('b', 'l')}.items()}
    # sides in traversal order: (name, start, direction, length, corner at start, corner at end, side before, side after)
    S = [('b', (x0 + rad['bl'], y0), (1, 0), w - rad['bl'] - rad['br'], 'l', 'r'),
         ('r', (x1, y0 + rad['br']), (0, 1), h - rad['br'] - rad['tr'], 'b', 't'),
         ('t', (x1 - rad['tr'], y1), (-1, 0), w - rad['tr'] - rad['tl'], 'r', 'l'),
         ('l', (x0, y1 - rad['tl']), (0, -1), h - rad['tl'] - rad['bl'], 't', 'b')]
    arcs = {'b': ('br', (x1 - rad['br'], y0 + rad['br']), -math.pi / 2), 'r': ('tr', (x1 - rad['tr'], y1 - rad['tr']), 0.0),
            't': ('tl', (x0 + rad['tl'], y1 - rad['tl']), math.pi / 2), 'l': ('bl', (x0 + rad['bl'], y0 + rad['bl']), math.pi)}
    wave = {}
    for name, _, _, L, _, _ in S:
        nw = max(1, int(round(L / 9.0))) if L > 3.0 else 0; ph = rng.uniform(0, 6.283); a2 = rng.uniform(0.0, 0.15)   # long, slow sweeps
        wave[name] = (nw, ph, a2)
    def inset(name, t, L, before, after):
        if not c[name]: return np.zeros_like(t)
        nw, ph, a2 = wave[name]
        u = t / max(L, 1e-6)
        wv = 0.5 + 0.5 * np.sin(2 * math.pi * nw * u + ph) * (1 - a2) + a2 * 0.5 * np.sin(2 * math.pi * (2 * nw + 1) * u + ph * 1.7) if nw else 0.5 + 0 * u
        d = amp * (0.3 + 0.7 * np.clip(wv, 0, 1))
        tl = min(2.2, L / 3)
        if not c[before]: d = d * _smooth(t / tl)
        if not c[after]: d = d * _smooth((L - t) / tl)
        return d
    pts, prev_end = [], {}
    for name, (sx, sy), (dx, dy), L, before, after in S:
        L = max(L, 0.0)
        n = max(2, int(L / step) + 1)
        t = np.linspace(0, L, n)
        d = inset(name, t, L, before, after)
        nx, ny = -dy, dx                                   # inward (left of a counter-clockwise walk)
        pts += [(sx + dx * ti + nx * di, sy + dy * ti + ny * di) for ti, di in zip(t[:-1], d[:-1])]
        prev_end[name] = d[-1]
        corner, (cx, cy), a0 = arcs[name]
        if rad[corner] > 0:
            nxt = {'b': 'r', 'r': 't', 't': 'l', 'l': 'b'}[name]
            nn = {'b': 'r', 'r': 't', 't': 'l', 'l': 'b'}[nxt]
            Ln = [q for q in S if q[0] == nxt][0][3]
            d1 = float(inset(nxt, np.array([0.0]), Ln, name, nn)[0])
            for k in range(9):
                f = k / 9; a = a0 + f * math.pi / 2
                r = rad[corner] - (d[-1] * (1 - f) + d1 * f)
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        else:
            pts.append((sx + dx * L + nx * d[-1], sy + dy * L + ny * d[-1]))
    P = np.array(pts)
    keep = np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-4]
    return P[keep]


def _inside(poly, P):
    """Even-odd point-in-polygon for points P (n,2)."""
    P = np.asarray(P, float).reshape(-1, 2)
    xi, yi = poly[:, 0][None], poly[:, 1][None]
    xj, yj = np.roll(poly[:, 0], 1)[None], np.roll(poly[:, 1], 1)[None]
    out = np.zeros(len(P), bool)
    for k in range(0, len(P), 4000):
        x, y = P[k:k + 4000, 0:1], P[k:k + 4000, 1:2]
        cr = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / np.where(yj == yi, 1e-12, yj - yi) + xi)
        out[k:k + 4000] = cr.sum(1) % 2 == 1
    return out


def _poly_dist(poly, P):
    """Distance from points P (n,2) to the outline."""
    A = poly; B = np.roll(poly, -1, 0); AB = B - A; l2 = np.maximum((AB ** 2).sum(1), 1e-12)
    out = np.empty(len(P))
    for k in range(0, len(P), 2000):
        Q = P[k:k + 2000][:, None, :]
        t = np.clip(((Q - A[None]) * AB[None]).sum(-1) / l2[None], 0, 1)
        out[k:k + 2000] = np.sqrt((((A[None] + t[..., None] * AB[None]) - Q) ** 2).sum(-1)).min(1)
    return out


def mulch_curved(ground, rect, poly, mat, col, name, edge_mat=None, slope=False):
    """Bark mulch inside a curved outline: a ground-following grid well inside it, plus a skirt strip whose
    outer edge is the smooth outline, and (edge_mat) a low tan stone edging band along the outline."""
    nzmin, jump = (0.12, 0.9) if slope else (0.55, 0.14)
    x0, y0, x1, y1 = rect
    nx = max(2, int((x1 - x0) / 0.25) + 1); ny = max(2, int((y1 - y0) / 0.25) + 1)
    xs = np.linspace(x0, x1, nx); ys = np.linspace(y0, y1, ny)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    XY = np.stack([X.ravel(), Y.ravel()], 1)
    ins = _inside(poly, XY); dist = np.zeros(len(XY)); dist[ins] = _poly_dist(poly, XY[ins])
    sw = min(0.35, 0.3 * min(x1 - x0, y1 - y0))
    Z = np.full(len(XY), np.nan)
    for i in np.nonzero(ins & (dist > sw * 0.45))[0]:
        z, n = ground.zn(XY[i, 0], XY[i, 1])
        if z is not None and n.z > nzmin: Z[i] = z
    ok = ~np.isnan(Z)
    Z = np.where(ok, Z, 0.0) + 0.018 + np.where(dist > 0.35, 0.008, 0.0)
    ok = ok.reshape(nx, ny); Zg = Z.reshape(nx, ny)
    q = ok[:-1, :-1] & ok[1:, :-1] & ok[1:, 1:] & ok[:-1, 1:]
    Zq = np.stack([Zg[:-1, :-1], Zg[1:, :-1], Zg[1:, 1:], Zg[:-1, 1:]], -1)
    q &= (Zq.max(-1) - Zq.min(-1)) < jump
    buf = Buf()
    ii, jj = np.nonzero(q)
    if len(ii):
        a = ii * ny + jj
        buf.add(np.stack([X, Y, Zg], -1).reshape(-1, 3), np.stack([a, a + ny, a + ny + 1, a + 1], -1), XY)
    # skirt: outline -> inward by sw (inward normals of the counter-clockwise outline)
    T = np.roll(poly, -1, 0) - np.roll(poly, 1, 0); T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    Nn = np.stack([-T[:, 1], T[:, 0]], 1)
    inner = poly + Nn * sw
    zo = [ground.zn(*p) for p in poly]; zi = [ground.zn(*p) for p in inner]
    good = lambda r: r[0] is not None and r[1].z > nzmin
    m = len(poly)
    V, F, UV = [], [], []
    for k in range(m):
        k2 = (k + 1) % m
        if not (good(zo[k]) and good(zo[k2]) and good(zi[k]) and good(zi[k2])): continue
        zz = [zo[k][0], zo[k2][0], zi[k2][0], zi[k][0]]
        if max(zz) - min(zz) > jump: continue
        b = len(V)
        for p, z in zip((poly[k], poly[k2], inner[k2], inner[k]), zz): V.append((p[0], p[1], z + 0.012)); UV.append((p[0], p[1]))
        F.append([b, b + 1, b + 2, b + 3])
    if F: buf.add(V, F, UV)
    if edge_mat is not None:
        o = poly - Nn * 0.03; e = poly + Nn * 0.09
        V, F, UV = [], [], []
        for k in range(m):
            k2 = (k + 1) % m
            if zo[k][0] is None or zo[k2][0] is None or abs(zo[k][0] - zo[k2][0]) > jump: continue
            g0, g1 = zo[k][0], zo[k2][0]
            b = len(V)
            V += [(o[k][0], o[k][1], g0 - 0.03), (o[k2][0], o[k2][1], g1 - 0.03), (o[k2][0], o[k2][1], g1 + 0.035), (o[k][0], o[k][1], g0 + 0.035),
                  (e[k][0], e[k][1], g0 + 0.035), (e[k2][0], e[k2][1], g1 + 0.035), (e[k2][0], e[k2][1], g1 - 0.03), (e[k][0], e[k][1], g0 - 0.03)]
            UV += [(0, 0), (1, 0), (1, 1), (0, 1), (0, 1), (1, 1), (1, 0), (0, 0)]
            F += [[b, b + 1, b + 2, b + 3], [b + 3, b + 2, b + 5, b + 4], [b + 4, b + 5, b + 6, b + 7]]
        if F: buf.add(V, F, UV, mat=1)
    if not buf.v: return None
    me = buf.mesh(name, [mat] + ([edge_mat] if edge_mat is not None else []))
    try:
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS'); bm.to_mesh(me); bm.free()
    except Exception: pass
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    return ob


# ---------------------------------------------------------------- the planting plan
BEDS = {   # spacing (m) of plants in a bed, number of variants built
    'bougainvillea': dict(spacing=0.95, variants=5),
    'gardenia': dict(spacing=0.8, variants=4),
    'hedge': dict(spacing=0.62, variants=4),
    'screen': dict(spacing=0.6, variants=3),
    'groundcover': dict(spacing=0.5, variants=4),
    'monstera': dict(spacing=1.3, variants=4),
    'ti': dict(spacing=0.48, variants=6),
    'mondo': dict(spacing=0.48, variants=4),          # fine strap tufts under everything (leaf shapes read)
    'tradescantia': dict(spacing=0.4, variants=3),
    'jasmine': dict(spacing=0.55, variants=4),        # glossy Asiatic jasmine on the bank below the pool wall
    'dichondra': dict(spacing=0.45, variants=3),      # silver ribbon along bed edges
    'alocasia': dict(spacing=1.1, variants=4),
    'heliconia': dict(spacing=1.0, variants=4),
    'hibiscus': dict(spacing=1.3, variants=3),
}


def _bed_points(rng, rect, spacing, density):
    x0, y0, x1, y1 = rect
    sp = spacing / math.sqrt(max(density, 0.2) / 1.1)
    w, h = x1 - x0, y1 - y0
    nx, ny = max(1, int(round(w / sp))), max(1, int(round(h / sp)))
    gx = (np.arange(nx) + 0.5) / nx; gy = (np.arange(ny) + 0.5) / ny
    X, Y = np.meshgrid(gx, gy, indexing='ij')
    X = X + rng.uniform(-0.32, 0.32, X.shape) / nx; Y = Y + rng.uniform(-0.32, 0.32, Y.shape) / ny
    return np.stack([x0 + np.clip(X, 0.03, 0.97).ravel() * w, y0 + np.clip(Y, 0.03, 0.97).ravel() * h], 1)


def build(meta, b, near=60.0, lawn=True, trees=True, log=print):
    """meta: nahiku-meta.json (needs 'plants' / 'lawn' from src/export.js); b: three.js metres -> Blender."""
    t0 = time.time()
    plants = meta.get('plants') or []
    scene = bpy.context.scene
    col = bpy.data.collections.new('planting'); scene.collection.children.link(col)
    if not plants and not meta.get('lawn'):
        return col
    mats = materials()
    rng = np.random.default_rng(7)
    lw_ = meta.get('lawn') or {}
    gbox = None
    if lw_.get('lot'):
        lx0, lz0, lx1, lz1 = lw_['lot']; ga, gb_ = b([lx0 - 30, 0, lz0 - 40]), b([lx1 + 30, 0, lz1 + 40])
        gbox = (min(ga.x, gb_.x), min(ga.y, gb_.y), max(ga.x, gb_.x), max(ga.y, gb_.y))
    ground = Ground(context_box=gbox)
    def brect(r):
        x0, z0, x1, z1 = r
        return (min(x0, x1), min(-z0, -z1), max(x0, x1), max(-z0, -z1))
    beds = [p for p in plants if p['type'] == 'bed']
    for p in beds:
        p['kind'], p['curve'], p['edge'] = bed_spec(p['kind'])
    bed_rects = [brect(p['rect']) for p in beds]
    # curved outlines; a bed planted inside another (edge False) takes the outer bed's outline and its mulch
    polys = [bed_outline(r, p['curve'], p['seed']) if p['curve'] else None for p, r in zip(beds, bed_rects)]
    outer = [None] * len(beds)
    for i, (p, r) in enumerate(zip(beds, bed_rects)):
        if p['edge']: continue
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        for j, (q, r2) in enumerate(zip(beds, bed_rects)):
            if j != i and q['edge'] and q.get('house') == p.get('house') and r2[0] <= cx <= r2[2] and r2[1] <= cy <= r2[3]:
                outer[i] = j; polys[i] = polys[j] if polys[i] is None else polys[i]; break
    # r5 (critique-preview4-back #12): the jasmine bank feathers into the lower lawn - the lawn (and the mulch) stop
    # 0.45 m inside the bed's lawn-side outline and the jasmine thins out over that strip with noise
    FEATHER = 0.45
    lawn_polys = list(polys)
    for i, (p, r) in enumerate(zip(beds, bed_rects)):
        if p['kind'] == 'jasmine' and 'x0' in p['curve']:
            lawn_polys[i] = bed_outline((r[0] + FEATHER, r[1], r[2], r[3]), p['curve'], p['seed'])
    lawn_beds = [((r[0] + FEATHER, r[1], r[2], r[3]) if lp is not pl else r, lp) for r, pl, lp in zip(bed_rects, polys, lawn_polys)]

    # ---- shrubs, ti and monstera in the beds
    flowers = {'bougainvillea': _bougainvillea_flowers, 'gardenia': _gardenia_flowers, 'groundcover': _small_white_flowers, 'hedge': _small_white_flowers,
               'hibiscus': _hibiscus_flowers, 'jasmine': _small_white_flowers}
    leafkey = {'bougainvillea': 'bougainvillea', 'gardenia': 'gardenia', 'hedge': 'hedge', 'screen': 'screen', 'groundcover': 'groundcover', 'jasmine': 'jasmine', 'dichondra': 'dichondra', 'hibiscus': 'gardenia'}
    protos = {}
    for kind, cfg in BEDS.items():
        if not any(p.get('kind') == kind for p in beds): continue
        nv = cfg['variants']
        if kind in SHRUBS:
            fn = lambda i, kind=kind: shrub(1000 + 37 * i + len(kind), SHRUBS[kind], flowers.get(kind))
            km = {'leaf': leafkey[kind], 'stem': 'stem', 'bract': 'bract', 'floret': 'floret', 'petal': {'hibiscus': 'hibiscus-petal', 'jasmine': 'jasmine-petal'}.get(kind, 'petal'), 'bud': 'bud'}
        elif kind == 'ti':
            fn = lambda i: ti_plant(2000 + i)
            km = {'leaf': lambda i: ('ti-burgundy', 'ti-red', 'ti-burgundy', 'ti-green', 'ti-burgundy', 'ti-red')[i % 6], 'cane': 'cane', 'dry': 'dry'}
        elif kind == 'monstera':
            fn = lambda i: monstera(3000 + i)
            km = {'leaf': 'monstera', 'stem': 'green-stem'}
        elif kind == 'mondo':
            fn = lambda i: strap_tufts(3100 + i, tufts=(5, 7), leaves=(22, 34), L=(0.16, 0.26), width=0.3, spread=0.22, el=(72, 25))
            km = {'leaf': 'mondo'}
        elif kind == 'tradescantia':
            fn = lambda i: strap_tufts(3200 + i, tufts=(4, 7), leaves=(14, 22), L=(0.1, 0.18), width=1.3, spread=0.18, el=(55, 5), arch=0.25)
            km = {'leaf': 'tradescantia'}
        elif kind == 'heliconia':
            fn = lambda i: heliconia(3400 + i)
            km = {'leaf': 'heliconia', 'stem': 'green-stem', 'bract': 'heliconia-bract'}
        elif kind == 'alocasia':
            fn = lambda i: alocasia(3300 + i)
            km = {'leaf': 'alocasia', 'stem': 'green-stem'}
        protos[kind] = _variants('v-' + kind, nv, fn, mats, km)
    log(f'plants: bed variants built {time.time() - t0:.1f}s')
    for kind, pc in protos.items():
        P, R, S, I = [], [], [], []
        nv = BEDS[kind]['variants']
        for bi, (p, rect) in enumerate(zip(beds, bed_rects)):
            if p['kind'] != kind: continue
            r = np.random.default_rng(p['seed'] & 0xffffffff)
            pts = _bed_points(r, rect, BEDS[kind]['spacing'], p.get('density', 1.1))
            pl = polys[bi]
            if pl is not None and len(pts): pts = pts[_inside(pl, pts)]
            if kind == 'jasmine' and lawn_polys[bi] is not pl and len(pts):
                # feathered lawn edge: keep a plant with a probability rising over the strip, broken up by noise
                inner = _inside(lawn_polys[bi], pts)
                dd = np.where(inner, FEATHER + _poly_dist(lawn_polys[bi], pts), FEATHER - _poly_dist(lawn_polys[bi], pts))
                nz = np.sin(pts[:, 0] * 4.3 + pts[:, 1] * 1.7) * np.sin(pts[:, 1] * 3.1 - pts[:, 0] * 2.3)
                pts = pts[r.random(len(pts)) < np.clip(dd / FEATHER + 0.45 * nz - 0.1, 0.0, 1.0)]
            zref = b([0, p['ground'], 0]).z
            for x, y in pts:
                z = ground.z(x, y)
                if z is None: z = zref
                nb = [ground.z(x + dx, y + dy) for dx, dy in ((0.12, 0), (-0.12, 0), (0, 0.12), (0, -0.12))]
                tol = 0.32 if kind in ('mondo', 'alocasia', 'dichondra', 'tradescantia') else 1.6 if kind == 'jasmine' else 0.15   # groundcovers climb banks (jasmine: all of it, no bare soil)
                if any(q is not None and abs(q - z) > tol for q in nb): continue    # right on a wall's step or a drop: skip
                P.append((x, y, z - 0.015)); R.append((r.normal(0, 0.04), r.normal(0, 0.04), r.uniform(0, 6.283)))
                S.append((r.uniform(0.65, 1.35) if kind == 'jasmine' else r.uniform(0.82, 1.18)) * p.get('scale', 1)); I.append(r.integers(0, nv))
        instancer('plants-' + kind, pc, np.array(P), np.array(R), np.array(S), np.array(I), col)
        log(f'plants: {kind} x{len(P)}')
    # mulch under every bed
    for i, (p, rect) in enumerate(zip(beds, bed_rects)):
        if outer[i] is not None: continue                      # the outer bed's mulch covers it
        slope = p['kind'] == 'jasmine'                         # groundcover on the bank: mulch follows the slope
        if lawn_polys[i] is not polys[i]:                       # feathered into the lawn: mulch only inside the strip, no edging
            mulch_curved(ground, lawn_beds[i][0], lawn_polys[i], mats['mulch'], col, f'mulch{i}', edge_mat=None, slope=slope)
        elif polys[i] is not None:
            mulch_curved(ground, rect, polys[i], mats['mulch'], col, f'mulch{i}', edge_mat=mats['stone-edging'] if p['edge'] else None, slope=slope)
        else:
            mulch(ground, rect, mats['mulch'], col, f'mulch{i}', rng, edge_mat=mats['edging'] if p['edge'] else None, slope=slope)

    # ---- plumeria trees
    plu = [p for p in plants if p['type'] == 'plumeria']
    if plu:
        km = {'leaf': 'plumeria', 'bark': 'plumeria-bark', 'petal': 'plumeria-petal'}
        pc = _variants('v-plumeria', 5, lambda i: plumeria_tree(4000 + i), mats, km)
        # r6 (critique-preview5-front #10): the small ones (scale < 0.7, the street pair) are young trees grown at real size
        # (scale 0.5 -> 1.0), each pair member its own variant and size, a quarter turn apart
        yc = _variants('v-plumeria-young', 3, lambda i: plumeria_tree(4100 + 13 * i, young=True), mats, km)
        P, R, S, I = [], [], [], []
        YP, YR, YS, YI = [], [], [], []
        for p in plu:
            r = np.random.default_rng(p['seed'] & 0xffffffff)
            v = b(p['pos']); z = ground.z(v.x, v.y); z = v.z if z is None else z
            sc = p.get('scale', 1)
            if sc < 0.7:
                # pair members differ (seed = x * 17 + y * 3 + 11 in src/plants.js; the pair's are 2200 / 2250): other
                # variant, a quarter turn apart
                k = (int(p['seed']) // 50) % 2
                YP.append((v.x, v.y, z - 0.03)); YR.append((r.normal(0, 0.02), r.normal(0, 0.02), (1.1 if k else 2.67) + r.uniform(-0.3, 0.3)))
                YS.append(sc / 0.5 * r.uniform(0.95, 1.05)); YI.append(k if r.random() < 0.85 else 2)
                continue
            P.append((v.x, v.y, z - 0.03)); R.append((0, 0, r.uniform(0, 6.283))); S.append(sc * r.uniform(1.05, 1.25)); I.append(r.integers(0, 5))
        if P: instancer('plants-plumeria', pc, np.array(P), np.array(R), np.array(S), np.array(I), col)
        if YP: instancer('plants-plumeria-young', yc, np.array(YP), np.array(YR), np.array(YS), np.array(YI), col)
        log(f'plants: plumeria x{len(P)}, young x{len(YP)} {time.time() - t0:.1f}s')

    # ---- specimen trees: pink shower tree (Cassia javanica)
    sh = [p for p in plants if p['type'] == 'shower']
    if sh:
        pc = _variants('v-shower', 2, lambda i: canopy_tree(5200 + i, 'dome', bloom=0.45), mats, {'leaf': 'tree-light', 'bark': 'plumeria-bark', 'bloom': 'shower-petal'})
        P, R, S, I = [], [], [], []
        for p in sh:
            r = np.random.default_rng(p['seed'] & 0xffffffff)
            v = b(p['pos']); z = ground.z(v.x, v.y); z = v.z if z is None else z
            sc_ = p.get('scale', 1) * r.uniform(0.92, 1.05)
            P.append((v.x, v.y, z - 0.1)); R.append((0, 0, r.uniform(0, 6.283))); S.append((sc_, sc_, sc_ * 0.95)); I.append(r.integers(0, 2))
        instancer('plants-shower', pc, np.array(P), np.array(R), np.array(S), np.array(I), col)
        log(f'plants: shower tree x{len(P)}')

    # ---- background canopy trees
    tr = [p for p in plants if p['type'] == 'tree']
    # the neighbours' back queen palms that scripts/palms.py turned into broadleaf trees (critic preview3 front #5)
    for q in meta.get('palms', []):
        if q.get('_tree'):
            tr.append({'type': 'tree', 'pos': q['base'], 'size': 4.0 * (0.85 + 0.25 * ((q['seed'] * 0.618) % 1)), 'sy': 0.95, 'seed': q['seed'] & 0xffffff, 'near': True})
    if tr and trees:
        # r5 (critique-preview4-back #5, front #3): spreading, multi-stem, lobed crowns - monkeypod, kiawe, kamani - in
        # place of the dome / umbrella / tall balls that read as lollipops on the hills
        forms = ('monkeypod', 'kiawe', 'kamani', 'monkeypod', 'kiawe', 'kamani', 'monkeypod', 'kiawe')
        tk = lambda i: ('tree', 'tree-light', 'tree-dark', 'tree-dark', 'tree-light', 'tree', 'tree', 'tree-dark')[i]
        nv = len(forms)
        # the background trees stand 50 m - 1.5 km off: the same aerial perspective as the real-site land they stand on
        # (scripts/materials_bpy.py r_realsite), on copies of the leaf / bark materials so the garden keeps its own
        import materials_bpy as _mb
        fm = dict(mats)
        for key in ('tree', 'tree-dark', 'tree-light', 'tree-bark'):
            m2 = mats[key].copy(); m2.name = mats[key].name + ' far'
            # r6 (critique-preview5-front #2 / #3): exactly the land's haze (materials_bpy.LAND_HAZE), so no crown or
            # building belt goes paler than the hillside it stands on
            _mb.aerial(_mb.G(m2.node_tree), **_mb.LAND_HAZE)
            if key != 'tree-bark':
                # and matte at distance: the leaves' sky sheen (spec 0.5, rough 0.4) turned crowns 100-200 m off
                # blue-grey, faded cut-outs against the land (critique-preview5-front #3, the ghost tree)
                for n_ in m2.node_tree.nodes:
                    if n_.type == 'BSDF_PRINCIPLED':
                        n_.inputs['Specular IOR Level'].default_value = min(n_.inputs['Specular IOR Level'].default_value, 0.3)
                        n_.inputs['Roughness'].default_value = max(n_.inputs['Roughness'].default_value, 0.55)
            fm[key] = m2
        pc = _variants('v-tree', nv, lambda i: canopy_tree(5000 + i, forms[i]), fm, {'leaf': tk, 'bark': 'tree-bark'})
        P, R, S, I = [], [], [], []
        lot_c = None
        if meta.get('lawn', {}).get('lot'):
            lx0, lz0, lx1, lz1 = meta['lawn']['lot']; lot_c = b([(lx0 + lx1) / 2, 0, (lz0 + lz1) / 2])
        # r4 (critic preview3 front #8): no lone 'lollipop' trees standing on the fairways - a tree with no other within
        # 22 m is either dropped or becomes a grove of 3-5 with mixed forms and sizes; crowns are squashed or stretched
        # a little so no two read as the same ball
        bp = np.array([[b(p['pos']).x, b(p['pos']).y] for p in tr]) if tr else np.zeros((0, 2))
        # the grove companions of trees out on the real terrain stand on it too (Ground only knows the modelled
        # ground, so before r5 every far tree lost its companions and stood alone)
        rs = [o for o in bpy.data.objects if o.type == 'MESH' and any(m and m.name.startswith('realsite near') for m in o.data.materials)]
        rs_bvh = _world_tris(rs, box=(bp[:, 0].min() - 60, bp[:, 1].min() - 60, bp[:, 0].max() + 60, bp[:, 1].max() + 60)) if rs and len(bp) else None
        def gz(x, y):
            z = ground.z(x, y)
            if z is None and rs_bvh is not None:
                loc = rs_bvh.ray_cast(Vector((x, y, 800.0)), Vector((0, 0, -1)), 3000.0)[0]
                z = None if loc is None else loc.z
            return z
        # r6 (critique-preview5-front #2): src/realsite.js plants the building belts with their crowns under the eave, so the
        # two-storey footprint blocks 300-450 m off stood bare across the only ocean view (crowns 2-6 m tall in front of
        # walls 3-8 m high). Each belt tree now grows from its own ground to 38-52% of the way up the roof of the building
        # it fronts (eave and ridge read off the exported massing), 5-13 m tall (~10-12 m in front of those blocks), and
        # gets one or two more crowns just outside it: a two-deep, opaque band of canopy over which only the upper roof
        # shows, as Kukui'ula / Po'ipu houses show over their trees (register I-16)
        TH = {'monkeypod': 7.0, 'kiawe': 5.5, 'kamani': 7.0}                  # crown top (m) at scale 1, canopy_tree SPREAD
        ekd = rkd = None
        if any(p['seed'] >= 700000 for p in tr):
            from mathutils import kdtree
            def wtris(key):
                out = []
                for o in bpy.data.objects:
                    if o.type != 'MESH' or not any(m and m.name.startswith(key) for m in o.data.materials): continue
                    me = o.data; me.calc_loop_triangles()
                    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co)
                    M = np.array(o.matrix_world); co = co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
                    ti = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', ti)
                    out.append(co[ti.reshape(-1, 3)])
                return np.concatenate(out) if out else None
            WT, RT = wtris('realsite walls'), wtris('realsite roofs')
            if WT is not None and RT is not None and len(WT) and len(RT):
                wz = WT[:, :, 2]; wtop = np.abs(wz - wz.max(1)[:, None]) < 0.02          # each wall quad's eave edge
                two = np.where(wtop.sum(1) == 2)[0]
                o2 = np.argsort(~wtop[two], axis=1, kind='stable')[:, :2]
                EA, EB = WT[two, o2[:, 0]], WT[two, o2[:, 1]]
                en = np.ceil(np.hypot(*(EB - EA)[:, :2].T) / 3.0).astype(int) + 1     # a sample every ~3 m
                sid = np.repeat(np.arange(len(en)), en); first = np.cumsum(en) - en
                et = (np.arange(en.sum()) - first[sid]) / np.maximum(en[sid] - 1, 1)
                EV = EA[sid] + (EB - EA)[sid] * et[:, None]
                ekd = kdtree.KDTree(len(EV))
                for i, q in enumerate(EV): ekd.insert((q[0], q[1], 0.0), i)
                ekd.balance()
                RV = np.unique(np.round(RT.reshape(-1, 3), 1), axis=0)
                rkd = kdtree.KDTree(len(RV))
                for i, q in enumerate(RV): rkd.insert((q[0], q[1], 0.0), i)
                rkd.balance()
        nbelt = [0, 0]
        for k, p in enumerate(tr):
            r = np.random.default_rng(p['seed'])
            v = b(p['pos']); s = p['size'] / 4.0
            belt = p['seed'] >= 700000                     # src/realsite.js: planting along a background building's foot
            d2 = ((bp - bp[k]) ** 2).sum(1); d2[k] = 1e12
            lone = not p.get('near') and not belt and d2.min() > 22.0 ** 2
            if lone and r.random() < 0.25: continue
            if not belt and not p.get('near'): s *= r.uniform(0.8, 1.2)
            ax = r.uniform(0.85, 1.15)
            rot = (r.normal(0, 0.03), r.normal(0, 0.03), r.uniform(0, 6.283))
            jit = r.uniform(0.85, 1.05); vi = int(r.integers(0, nv))       # (same draw order as before r6)
            syy = p.get('sy', 1.0)
            comp = []
            if belt and ekd is not None:
                ec, ei, ed_ = ekd.find((v.x, v.y, 0.0))
                if ed_ < 12.0:
                    rb = np.random.default_rng(p['seed'] + 7919)
                    eave = EV[ei][2]
                    ridge = max([RV[j][2] for _, j, _ in rkd.find_range((v.x, v.y, 0.0), 30.0)], default=eave)
                    ridge = min(max(ridge, eave), eave + 12.0)
                    bH = min(max(eave + (ridge - eave) * rb.uniform(0.38, 0.52) - v.z, 5.0), 13.0)
                    kk = bH / (TH[forms[vi]] * s * syy * jit)
                    if kk > 1.0:                                              # never shrink; widen a little, mostly taller
                        sh = kk ** 0.4; s *= sh; syy *= kk / sh
                    nbelt[0] += 1
                    ox, oy = v.x - ec.x, v.y - ec.y; dn = math.hypot(ox, oy)
                    if dn < 0.3:
                        a = rb.uniform(0, 6.283); ox, oy = math.cos(a), math.sin(a)
                    else: ox, oy = ox / dn, oy / dn
                    for _ in range(1 if rb.random() < 0.6 else 2):
                        out_, along = 4.0 * s * rb.uniform(0.7, 1.1), 4.0 * s * rb.uniform(-0.7, 0.7)
                        x, y = v.x + ox * out_ - oy * along, v.y + oy * out_ + ox * along
                        z = gz(x, y)
                        if z is None or abs(z - v.z) > 4.0: continue
                        v2 = int(rb.integers(0, nv)); s2 = s * rb.uniform(0.75, 1.0)
                        H2 = min(max(v.z + bH * rb.uniform(0.75, 0.95) - z, 4.0), 14.0)
                        comp.append(((x, y, z - 0.25), (rb.normal(0, 0.03), rb.normal(0, 0.03), rb.uniform(0, 6.283)),
                                     (s2, s2, H2 / TH[forms[v2]]), v2))
                    nbelt[1] += len(comp)
            P.append((v.x, v.y, v.z - 0.25)); R.append(rot)
            S.append((s * ax, s / ax, s * syy * jit)); I.append(vi)
            for c_ in comp:
                P.append(c_[0]); R.append(c_[1]); S.append(c_[2]); I.append(c_[3])
            # trees grow in groves: companions crowding in beside the far ones, crowns interlocking, mixed kinds and sizes
            # (not near our lot, where the plan is exact; not the building belts, already a row)
            far = not p.get('near') and not belt and (lot_c is None or math.hypot(v.x - lot_c.x, v.y - lot_c.y) > 140)
            for _ in range(r.integers(3, 6) if lone else r.integers(1, 4) if far else 0):
                a = r.uniform(0, 6.283); dd = s * r.uniform(2.6, 4.8)
                x, y = v.x + math.cos(a) * dd, v.y + math.sin(a) * dd
                z = gz(x, y)
                if z is None or abs(z - v.z) > 3: continue
                s2 = s * r.uniform(0.55, 1.05)
                P.append((x, y, z - 0.25)); R.append((r.normal(0, 0.03), r.normal(0, 0.03), r.uniform(0, 6.283)))
                S.append((s2, s2, s2 * r.uniform(0.8, 1.15))); I.append(r.integers(0, nv))
        instancer('plants-trees', pc, np.array(P), np.array(R), np.array(S), np.array(I), col)
        log(f'plants: trees x{len(P)} (belt raised x{nbelt[0]}, +{nbelt[1]} belt crowns) {time.time() - t0:.1f}s')

    # ---- lawn: grass blades on the open ground of our lot and the nearest neighbours
    lw = meta.get('lawn')
    if lawn and lw and lw.get('lot'):
        lx0, lz0, lx1, lz1 = lw['lot']
        boxes = []
        for dx, dy, dz in lw.get('houses', [[0, 0, 0]]):
            if abs(dz) > near: continue
            bx_ = brect([lx0 + dx - 14.0, lz0 + dz - 1.4, lx1 + dx + 6.0, lz1 + dz + 1.4])
            boxes.append((math.floor(bx_[0] * 2) / 2, math.floor(bx_[1] * 2) / 2, math.ceil(bx_[2] * 2) / 2, math.ceil(bx_[3] * 2) / 2))
        X0 = min(bx[0] for bx in boxes); Y0 = min(bx[1] for bx in boxes); X1 = max(bx[2] for bx in boxes); Y1 = max(bx[3] for bx in boxes)
        skip = {c.name for c in (col, bpy.data.collections.get('palms')) if c}
        # r6 (critique-preview5-back #3, the 'divots'): only objects in the scene. The instancing prototypes (palm crowns,
        # shrubs, plumerias, canopy trees) live in collections never linked to the scene, all built at the world origin,
        # which is plan (0, 0) in front of the lanai: their leaves counted as cover and punched frond-shaped holes in
        # the turf there, the smooth terrain showing between the surviving tiles
        others = [o for o in scene.objects if o.type == 'MESH' and not any(c.name in skip for c in o.users_collection)
                  and not any(m and (m.name.startswith('terrain') or m.name.startswith('realsite near')) for m in o.data.materials) and o.data.polygons]
        # grass pavers: the honeycomb cells are full of turf (only the 1 in ribs show), so the lawn grows through them
        pav = [o for o in others if any(m and m.name.lower().startswith('grasspavers') for m in o.data.materials)]
        pav_bvh = _world_tris(pav, box=(X0 - 1, Y0 - 1, X1 + 1, Y1 + 1)) if pav else None
        cover = _world_tris(others, box=(X0 - 1, Y0 - 1, X1 + 1, Y1 + 1), zmax=2.0)
        log(f'plants: lawn cover bvh {time.time() - t0:.1f}s')
        full, part = [], []
        seen = set()
        for bx in boxes:
            f_, p_ = lawn_cells(ground, cover, bx, lawn_beds)
            for c in f_:
                k = (round(c[0], 2), round(c[1], 2))
                if k not in seen: seen.add(k); full.append(c)
            for c in p_:
                k = (round(c[0], 3), round(c[1], 3))
                if k not in seen: seen.add(k); part.append(c)
        log(f'plants: lawn cells {len(full)} full, {len(part)} edge {time.time() - t0:.1f}s')
        paver = []
        if pav_bvh is not None:
            # grass pavers: one hex period per tile on the material's world lattice, short turf in the cells and
            # light concrete ribs proud of it, so the honeycomb reads (front rendering p4)
            def _slab(x, y):
                loc = pav_bvh.ray_cast(Vector((x, y, 500.0)), Vector((0, 0, -1)), 2000.0)[0]
                return None if loc is None else loc.z
            tw, th = PAVER_PITCH, PAVER_PITCH * R3
            for bx in boxes:
                for i in range(int(math.floor(bx[0] / tw)), int(math.ceil(bx[2] / tw))):
                    for j in range(int(math.floor(bx[1] / th)), int(math.ceil(bx[3] / th))):
                        x, y = i * tw, j * th
                        if ('pv', i, j) in seen: continue
                        zs = [_slab(x + dx, y + dy) for dx, dy in ((0.01, 0.01), (tw - 0.01, 0.01), (0.01, th - 0.01), (tw - 0.01, th - 0.01), (tw / 2, th / 2))]
                        if any(z is None for z in zs) or max(zs) - min(zs) > 0.03: continue
                        if any(bx0 < x + tw / 2 < bx1 and by0 < y + th / 2 < by1 for bx0, by0, bx1, by1 in bed_rects): continue
                        seen.add(('pv', i, j)); paver.append((x, y, max(zs)))
            log(f'plants: grass-paver tiles {len(paver)}')
        if paver:
            hs = (0.26, 0.42, 0.3, 0.5, 0.34, 0.24, 0.46, 0.38)          # cell-to-cell vigour (mown height)
            pv = proto_collection('v-paver', [bpy.data.objects.new(f'p{i}', paver_tile(6200 + i, hscale=hs[i], over=0.06 + 0.02 * (i % 4)).mesh(
                f'paver{i}', [mats['paver-lawn'], mats['paver-rib'], mats['paver-base']])) for i in range(len(hs))])
            P = np.array([(x, y, z - 0.002) for x, y, z in paver])
            instancer('plants-lawn-pavers', pv, P, np.zeros((len(P), 3)), np.ones((len(P), 3)), rng.integers(0, len(hs), len(P)), col)
        nv = 6
        def _turf(seed, size, **kw):
            # blades plus a thatch quad just above the ground (critique-preview4-back #3: gaps read as shade, not paint)
            t_ = grass_tile(seed, size, **kw); hs_ = size / 2 + 0.004
            t_.add([(-hs_, -hs_, 0.006), (hs_, -hs_, 0.006), (hs_, hs_, 0.006), (-hs_, hs_, 0.006)], [[0, 1, 2, 3]], [(0, 0), (1, 0), (1, 1), (0, 1)], mat=1)
            return t_
        big = proto_collection('v-turf', [bpy.data.objects.new(f't{i}', _turf(6000 + i, 0.5).mesh(f'turf{i}', [mats['lawn'], mats['thatch']])) for i in range(nv)])
        # edge sub-cells (along walls, steps, bed edges): a little thinner and yellower (critic preview3 back #3)
        # r5 (critique-preview4-back #3): edge sub-cells at full lawn density and colour, a little oversized so they
        # close up against slabs, coping and trunk bases (r4: thinner, yellower edge tiles read as balding turf)
        small = proto_collection('v-turf-s', [bpy.data.objects.new(f's{i}', _turf(6100 + i, 0.14, density=23000).mesh(f'turfs{i}', [mats['lawn'], mats['thatch']])) for i in range(nv)])
        for name, cells, pc in (('lawn', full, big), ('lawn-edge', part, small)):
            if not cells: continue
            P = np.array([(c[0], c[1], c[2] - 0.004) for c in cells])
            rz = rng.integers(0, 4, len(cells)) * (math.pi / 2)
            R = _tilt_euler([tuple(c[3]) for c in cells], rz)
            S = np.ones((len(cells), 3)); S[:, 0] = rng.choice([-1.0, 1.0], len(cells))
            instancer('plants-' + name, pc, P, R, S, rng.integers(0, nv, len(cells)), col)
    log(f'plants: done {time.time() - t0:.1f}s')
    return col
