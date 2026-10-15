"""Garden planting for the path tracer, grown leaf by leaf (the palms are in scripts/palms.py).

In export mode three.js only records where the planting goes (src/plants.js, src/site.js ->
nahiku-meta.json 'plants' and 'lawn'); here every plant is built from real geometry:

  - lawn: a manicured turf of individual grass blades (instanced 0.5 m tiles, edge tiles of 12.5 cm)
    on every bit of open ground of our lot and the nearest neighbours; beds get bark mulch
  - shrubs (bougainvillea, gardenia, hedge, groundcover): twigs carrying hundreds of leaves, with
    bracts and flowers; ti plants on bare canes; monstera with split leaves on long petioles
  - plumeria trees (candelabra branches, leaf rosettes, white and yellow flowers)
  - the background canopy trees (branching trunks, leaves)

Each kind is built as a handful of variants and instanced with geometry nodes, so a neighbourhood
of planting costs little memory. Leaves carry procedural vein textures, per-leaf colour variation,
gloss and translucency.

    import plants_bpy; plants_bpy.build(meta, b)        # b: three.js world (metres) -> Blender
"""
import math, time
import numpy as np
import bpy
from mathutils import Vector, Matrix

UP = np.array([0.0, 0.0, 1.0])
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


def mulch_material():
    """Shredded bark mulch: dark brown chips (voronoi cells) with lighter dry tops and soil between."""
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
    'bougainvillea': dict(R=0.62, H=1.0, twigs=420, leaves=(7, 12), leaf_len=0.055, twig_len=0.2, leaf_angle=58, droop=0.35, up=0.15,
                          shape='ovate', stems=6, stem_r=0.016, bloom=0.62, phyllo='alt', lump=0.22),
    'gardenia': dict(R=0.48, H=0.95, twigs=300, leaves=(6, 10), leaf_len=0.085, twig_len=0.14, leaf_angle=50, droop=0.15, up=0.45,
                     shape='elliptic', stems=5, stem_r=0.014, bloom=0.16, phyllo='opp', lump=0.14),
    'hedge': dict(R=0.5, H=1.25, twigs=420, leaves=(8, 12), leaf_len=0.045, twig_len=0.12, leaf_angle=55, droop=0.1, up=0.3,
                  shape='small', stems=6, stem_r=0.014, bloom=0.04, phyllo='alt', lump=0.1),
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
    tpls = [leaf_tpl(_prof(S['shape']), fold=fo, arch=ar, twist=tw, stations=(0, 0.1, 0.3, 0.55, 0.8, 1.0))
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
    tpb = [leaf_tpl(_prof('bract'), fold=0.05, cup=0.25, arch=-0.05, stations=(0, 0.15, 0.4, 0.7, 1.0), cols=2),
           leaf_tpl(_prof('bract'), fold=0.1, cup=0.4, arch=0.05, twist=0.3, stations=(0, 0.15, 0.4, 0.7, 1.0), cols=2)]
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
    tp_in = leaf_tpl(_prof('obovate'), fold=0.05, cup=0.35, arch=-0.12, stations=(0, 0.2, 0.5, 0.8, 1.0), cols=2)
    tp_out = leaf_tpl(_prof('obovate'), fold=0.04, cup=0.2, arch=0.08, twist=0.25, stations=(0, 0.2, 0.5, 0.8, 1.0), cols=2)
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
        place(pe, tp, np.repeat(tip[i][None] + ax * 0.01, 5, 0), _norm(rad + ax * 0.25), np.repeat(ax, 5, 0), np.full(5, 0.009), np.full(5, 1.2))


# ---------------------------------------------------------------- ti plant (Cordyline fruticosa)
def ti_plant(seed):
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'cane': Buf(), 'dry': Buf()}
    nc = rng.choice([2, 3, 3, 4, 5])
    tpls = [leaf_tpl(_prof('lance'), fold=0.06, arch=a, twist=tw, cols=2, stations=(0, 0.08, 0.16, 0.3, 0.45, 0.6, 0.75, 0.88, 1.0))
            for a, tw in ((0.1, 0.1), (0.3, -0.25), (0.55, 0.3), (0.8, -0.15))]
    for c in range(nc):
        h = rng.uniform(0.15, 0.75) * (1.0 if c == 0 else rng.uniform(0.25, 0.9))
        lean = rng.uniform(0, 6.28); lv = np.array([math.cos(lean), math.sin(lean), 0]) * rng.uniform(0.03, 0.12)
        base = np.array([rng.normal(0, 0.1), rng.normal(0, 0.1), 0])
        t = np.linspace(0, 1, 7)[:, None]
        path = base + t * np.array([0, 0, h]) + (t ** 2) * lv * h
        r = rng.uniform(0.011, 0.017)
        tubes(out['cane'], path[None], np.linspace(r * 1.15, r * 0.9, 7)[None], sides=7)
        top = path[-1]; ax = _norm(path[-1] - path[-2])
        n = rng.integers(20, 32)
        i = np.arange(n); age = i / (n - 1)                     # 0 = youngest (top centre) .. 1 = oldest
        ph = rng.uniform(0, 6.28) + i * GOLDEN
        el = np.radians(82 - 100 * age ** 0.85 + rng.normal(0, 7, n))
        hd = np.stack([np.cos(ph), np.sin(ph), np.zeros(n)], 1)
        D = _norm(np.cos(el)[:, None] * hd + np.sin(el)[:, None] * UP)
        Nn = _norm(UP - D * (D @ UP)[:, None] + hd * 0.15 + rng.normal(0, 0.2, (n, 3)))
        P = top - ax * (age * 0.09)[:, None] + hd * 0.008
        L = rng.uniform(0.42, 0.62) * rng.uniform(0.85, 1.15, n) * (0.6 + 0.4 * np.clip(age * 3, 0, 1))
        pk = np.clip((age * 3.99).astype(int) + rng.integers(-1, 1, n), 0, 3)
        for j, tp in enumerate(tpls):
            s = pk == j; place(out['leaf'], tp, P[s], D[s], Nn[s], L[s], rng.uniform(0.85, 1.2, s.sum()))
        # a dead leaf or two hanging against the cane
        nd = rng.integers(0, 3)
        if nd and h > 0.35:
            ph = rng.uniform(0, 6.28, nd); hd = np.stack([np.cos(ph), np.sin(ph), np.zeros(nd)], 1)
            D = _norm(hd * 0.35 - UP); place(out['dry'], tpls[0], np.repeat(top[None], nd, 0) - ax * 0.12 + hd * 0.01, D, hd, rng.uniform(0.25, 0.4, nd), np.full(nd, 0.7))
    return out


# ---------------------------------------------------------------- monstera
def monstera_blade(rng, splits=7, holes=True):
    """Unit monstera leaf (length 1 from the petiole junction to the tip, +Y), split from the margin
    toward the midrib along the lateral veins, with a row of holes near the midrib."""
    Vs, Fs, UVs = [], [], []
    for side in (-1, 1):
        sk = np.sort(np.linspace(0.2, 0.9, splits) + rng.normal(0, 0.02, splits))
        g = 0.008 + rng.random(splits) * 0.006
        rs = rng.uniform(0.38, 0.62, splits)
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
        for a, gg, r_ in zip(sk, g, rs):
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
        dn = math.radians(rng.uniform(-45, -10))
        D = _norm(hd * math.cos(dn) + UP * math.sin(dn) + np.cross(UP, hd) * rng.normal(0, 0.2))
        Nn = _norm(UP + hd * 0.4 + rng.normal(0, 0.15, 3))
        bl = blades[0 if size > 0.6 else 1 if size > 0.48 else 2 + rng.integers(0, 2)]
        place(out['leaf'], bl, tip[None] - D[None] * 0.01, D[None], Nn[None], np.array([size]))
    return out


# ---------------------------------------------------------------- plumeria tree
def plumeria_tree(seed, scale=1.0):
    rng = np.random.default_rng(seed)
    out = {'leaf': Buf(), 'bark': Buf(), 'petal': Buf()}
    segs = []                                # (path (k,3), r0, r1)
    tips = []
    def grow(p, d, L, r, depth, first=False):
        end = p + d * L
        side = _norm(np.cross(d, UP) + 1e-6)
        mid = (p + end) / 2 + side * rng.normal(0, 0.06) * L + UP * 0.08 * L
        t = np.linspace(0, 1, 6)[:, None]
        path = (1 - t) ** 2 * p + 2 * (1 - t) * t * mid + t * t * end
        segs.append((path, r, r * 0.88))
        if depth == 0:
            tips.append((end, _norm(path[-1] - path[-2]))); return
        k = rng.integers(3, 5) if first else (2 if rng.random() < 0.5 else 3)
        az0 = rng.uniform(0, 6.28)
        hd0 = _norm(d * np.array([1, 1, 0]) + 1e-6)
        for j in range(k):
            az = az0 + j * 2 * math.pi / k + rng.normal(0, 0.35)
            hd = np.array([math.cos(az), math.sin(az), 0])
            spread = math.radians(rng.uniform(45, 62) if first else rng.uniform(22, 42))
            nd = _norm(d * math.cos(spread) + _norm(hd - d * (hd @ d) + 1e-6) * math.sin(spread) + UP * 0.12)
            grow(end, nd, L * rng.uniform(0.78, 0.95), r * 0.86, depth - 1)
    h0 = rng.uniform(0.7, 1.0)
    grow(np.zeros(3), _norm(UP + rng.normal(0, 0.1, 3) * np.array([1, 1, 0])), h0, 0.14, 4, first=True)
    k = 6
    for path, r0, r1 in segs:
        tubes(out['bark'], path[None], np.linspace(r0, r1, len(path))[None], sides=9)
    tpl = [leaf_tpl(_prof('plumeria'), fold=0.14, arch=a, twist=tw, cols=2, stations=(0, 0.1, 0.25, 0.42, 0.6, 0.78, 0.92, 1.0)) for a, tw in ((0.05, 0.1), (0.15, -0.2), (0.28, 0.25))]
    petal = leaf_tpl(_prof('obovate'), fold=0.05, cup=0.15, arch=-0.05, twist=0.5, stations=(0, 0.2, 0.45, 0.7, 0.9, 1.0), cols=2)
    for pos, d in tips:
        n = rng.integers(18, 28)
        i = np.arange(n); age = i / (n - 1)
        ph = rng.uniform(0, 6.28) + i * GOLDEN
        hd = np.stack([np.cos(ph), np.sin(ph), np.zeros(n)], 1)
        el = np.radians(72 - 85 * age + rng.normal(0, 8, n))
        D = _norm(np.cos(el)[:, None] * hd + np.sin(el)[:, None] * UP + d * 0.2)
        Nn = _norm(UP - D * (D @ UP)[:, None] + rng.normal(0, 0.15, (n, 3)))
        L = rng.uniform(0.26, 0.38, n) * (0.55 + 0.45 * np.clip(age * 2.5, 0, 1))
        P = pos - d * (age * 0.05)[:, None]
        pk = np.clip((age * 2.99).astype(int), 0, 2)
        for j, tp in enumerate(tpl):
            s = pk == j; place(out['leaf'], tp, P[s], D[s], Nn[s], L[s], rng.uniform(0.85, 1.15, s.sum()))
        if rng.random() < 0.9:                  # an inflorescence of white, yellow-eyed flowers
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
def canopy_tree(seed):
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
def grass_tile(seed, size=0.5, density=22000):
    """A square of mown turf: blades 4-8 cm, cut tips, leaning every way; tiles seamlessly at `size`."""
    rng = np.random.default_rng(seed)
    n = int(size * size * density)
    base = np.concatenate([(rng.random((n, 2)) - 0.5) * size, np.zeros((n, 1))], 1)
    h = np.clip(rng.normal(0.058, 0.012, n), 0.025, 0.1)
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


def grass_material():
    m = bpy.data.materials.new('plant lawn'); nt, N, L = _nodes(m)
    out = N.new('ShaderNodeOutputMaterial')
    geo = N.new('ShaderNodeNewGeometry'); uvn = N.new('ShaderNodeUVMap'); sep = N.new('ShaderNodeSeparateXYZ')
    L.new(uvn.outputs['UV'], sep.inputs[0])
    ramp = N.new('ShaderNodeValToRGB'); e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = _lin('#3e6224'); e[1].position = 1.0; e[1].color = _lin('#8a9440')
    e.new(0.3).color = _lin('#4d7428'); e.new(0.62).color = _lin('#5c8230'); e.new(0.88).color = _lin('#6e8a36')
    e.new(0.975).color = _lin('#86804a')
    L.new(geo.outputs['Random Per Island'], ramp.inputs['Fac'])
    # lawn-scale mottling (soil, water, wear): world-position noise, so neighbouring tiles agree
    no = N.new('ShaderNodeTexNoise'); no.inputs['Scale'].default_value = 0.35; no.inputs['Detail'].default_value = 4
    L.new(geo.outputs['Position'], no.inputs['Vector'])
    nm = N.new('ShaderNodeMapRange'); nm.inputs['From Min'].default_value = 0.3; nm.inputs['From Max'].default_value = 0.7
    nm.inputs['To Min'].default_value = 0.78; nm.inputs['To Max'].default_value = 1.15
    L.new(no.outputs['Fac'], nm.inputs['Value'])
    hsv = N.new('ShaderNodeHueSaturation'); L.new(ramp.outputs['Color'], hsv.inputs['Color']); L.new(nm.outputs['Result'], hsv.inputs['Value'])
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
    ms = N.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = 0.3
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
    leaf('groundcover', 4, '#6f8a68', '#9aae90', n_veins=5, angle=50, vein=0.2, rough=0.55, transl=0.2, sheen=0.6, val_var=0.12, sat_var=0.15)
    leaf('monstera', 5, '#1d4a17', '#3f6a28', n_veins=14, angle=89, vein=0.35, vein_w=0.006, aspect=0.5, rough=0.32, spec=0.5, transl=0.2, bump=0.3, val_var=0.12, back=(1.1, 1.12, 1.0))
    leaf('plumeria', 6, '#3d6b24', '#9ab055', n_veins=22, angle=75, vein=0.6, vein_w=0.007, rough=0.38, transl=0.3, bump=0.45, val_var=0.15, dry=(1.6, 1.1, 0.25, 1), dry_share=0.05)
    leaf('ti-red', 7, '#7a1224', '#93283a', n_veins=40, angle=12, vein=0.15, vein_w=0.004, aspect=0.12, rough=0.26, spec=0.6, transl=0.35, trans_tint=(1.6, 0.6, 0.7),
         variegate=(_lin('#b3203f'), 0.3), val_var=0.2, hue_var=0.015, back=(1.0, 1.0, 1.0))
    leaf('ti-burgundy', 8, '#43101a', '#5a1a28', n_veins=40, angle=12, vein=0.15, vein_w=0.004, aspect=0.12, rough=0.24, spec=0.6, transl=0.3, trans_tint=(1.8, 0.7, 0.8),
         edge=_lin('#9a1c34'), val_var=0.2, hue_var=0.015, back=(1.0, 1.0, 1.0))
    leaf('ti-green', 9, '#3e4a1c', '#5a6a2a', n_veins=40, angle=12, vein=0.15, vein_w=0.004, aspect=0.12, rough=0.28, spec=0.55, transl=0.32,
         variegate=(_lin('#6e1a30'), 0.35), val_var=0.2, hue_var=0.03, back=(1.0, 1.0, 1.0))
    leaf('tree', 10, '#2f5a22', '#5f8a3a', n_veins=8, angle=55, vein=0.25, rough=0.4, transl=0.3, val_var=0.22, hue_var=0.04, dry=(1.5, 1.2, 0.3, 1), dry_share=0.04)
    leaf('tree-dark', 11, '#22451a', '#4a6e2c', n_veins=10, angle=60, vein=0.25, rough=0.3, spec=0.6, transl=0.25, val_var=0.2, hue_var=0.03)
    leaf('tree-light', 12, '#4a7a2c', '#7a9a45', n_veins=7, angle=50, vein=0.25, rough=0.45, transl=0.32, val_var=0.22, hue_var=0.05)
    bimg, bh = leaf_image('bract', 13, _lin('#c41f7c'), _lin('#e05aa0'), n_veins=7, angle=40, vein=0.35, vein_w=0.012, margin=0.1, mott=0.08, sunken=False)
    M['bract'] = petal_material('plant bract', _lin('#c41f7c'), vein_img=bimg, transl=0.5, rough=0.5, sheen=0.2)
    M['floret'] = petal_material('plant floret', _lin('#f2ead2'), transl=0.4)
    M['petal'] = petal_material('plant petal', _lin('#f6f2e4'), transl=0.42, rough=0.5, sheen=0.35)
    M['plumeria-petal'] = petal_material('plant plumeria petal', _lin('#f7f4ea'), _lin('#f2b818'), center_len=0.42, transl=0.42, rough=0.45, sheen=0.35)
    M['bud'] = plain_material('plant bud', _lin('#d9dcc0'), 0.5, 0.3)
    M['dry'] = leaf_material('plant dry leaf', *leaf_image('leaf-dry', 14, _lin('#6e5530'), _lin('#8a7040'), n_veins=30, angle=12, aspect=0.12), rough=0.7, transl=0.2)
    M['stem'] = bark_material('plant stem', _lin('#5c4a38'), _lin('#33281e'), scale=30, bump=0.2)
    M['green-stem'] = plain_material('plant petiole', _lin('#3a5a22'), 0.4, 0.15)
    M['cane'] = bark_material('plant ti cane', _lin('#7a6c5a'), _lin('#4a3e32'), scale=40, rings=0.018, ring_col=_lin('#3a3028'), bump=0.5)
    M['plumeria-bark'] = bark_material('plant plumeria bark', _lin('#5e5e54'), _lin('#3a3a32'), scale=14, lichen=_lin('#a8a690'), bump=0.3, stretch=2.0)
    M['tree-bark'] = bark_material('plant tree bark', _lin('#5a5048'), _lin('#2e2822'), scale=9, lichen=_lin('#7a786a'), bump=0.6, stretch=5.0)
    M['lawn'] = grass_material()
    M['mulch'] = mulch_material()
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
    def __init__(self, box=None):
        self.bvh = _world_tris(_terrain_objects(), box=box)

    def z(self, x, y, default=0.0):
        if self.bvh is None: return default
        loc, nrm, _, _ = self.bvh.ray_cast(Vector((x, y, 500.0)), Vector((0, 0, -1)), 2000.0)
        return loc.z if loc is not None else None

    def zn(self, x, y):
        if self.bvh is None: return None, None
        loc, nrm, _, _ = self.bvh.ray_cast(Vector((x, y, 500.0)), Vector((0, 0, -1)), 2000.0)
        return (loc.z, nrm) if loc is not None else (None, None)


def lawn_cells(ground, cover, box, beds, cell=0.5, sub=4):
    """Open lawn in box (Blender xy): ground present, nothing within 35 cm above it, not inside a
    solid, not in a bed. Returns full cells and edge sub-cells: lists of (x, y, z, normal)."""
    x0, y0, x1, y1 = box
    full, part = [], []
    sc = cell / sub
    offs = (np.arange(sub) + 0.5) * sc - cell / 2
    down, up = Vector((0, 0, -1)), Vector((0, 0, 1))
    def ok(x, y):
        if any(bx0 < x < bx1 and by0 < y < by1 for bx0, by0, bx1, by1 in beds): return None
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


def mulch(ground, rect, mat, col, name, rng):
    """A bed of bark mulch over rect (Blender xy), following the ground, edges slightly ragged."""
    x0, y0, x1, y1 = rect
    nx = max(2, int((x1 - x0) / 0.25) + 1); ny = max(2, int((y1 - y0) / 0.25) + 1)
    xs = np.linspace(x0 - 0.12, x1 + 0.12, nx); ys = np.linspace(y0 - 0.12, y1 + 0.12, ny)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    edge = np.minimum(np.minimum(X - xs[0], xs[-1] - X), np.minimum(Y - ys[0], ys[-1] - Y))
    X = X + (edge < 0.01) * rng.normal(0, 0.04, X.shape); Y = Y + (edge < 0.01) * rng.normal(0, 0.04, Y.shape)
    Z = np.zeros_like(X)
    for i in range(nx):
        for j in range(ny):
            z = ground.z(X[i, j], Y[i, j]); Z[i, j] = (z if z is not None else 0.0) + 0.012 + (0.02 if edge[i, j] > 0.2 else 0.0)
    a = (np.arange(nx - 1)[:, None] * ny + np.arange(ny - 1)[None, :]).ravel()
    F = np.stack([a, a + ny, a + ny + 1, a + 1], -1)
    buf = Buf(); buf.add(np.stack([X, Y, Z], -1).reshape(-1, 3), F, np.stack([X, Y], -1).reshape(-1, 2))
    ob = bpy.data.objects.new(name, buf.mesh(name, [mat])); col.objects.link(ob)
    return ob


# ---------------------------------------------------------------- the planting plan
BEDS = {   # spacing (m) of plants in a bed, number of variants built
    'bougainvillea': dict(spacing=0.95, variants=5),
    'gardenia': dict(spacing=0.8, variants=4),
    'hedge': dict(spacing=0.62, variants=4),
    'groundcover': dict(spacing=0.5, variants=4),
    'monstera': dict(spacing=1.3, variants=4),
    'ti': dict(spacing=0.48, variants=6),
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
    ground = Ground()
    def brect(r):
        x0, z0, x1, z1 = r
        return (min(x0, x1), min(-z0, -z1), max(x0, x1), max(-z0, -z1))
    beds = [p for p in plants if p['type'] == 'bed']
    bed_rects = [brect(p['rect']) for p in beds]

    # ---- shrubs, ti and monstera in the beds
    flowers = {'bougainvillea': _bougainvillea_flowers, 'gardenia': _gardenia_flowers, 'groundcover': _small_white_flowers, 'hedge': _small_white_flowers}
    leafkey = {'bougainvillea': 'bougainvillea', 'gardenia': 'gardenia', 'hedge': 'hedge', 'groundcover': 'groundcover'}
    protos = {}
    for kind, cfg in BEDS.items():
        if not any(p.get('kind') == kind for p in beds): continue
        nv = cfg['variants']
        if kind in SHRUBS:
            fn = lambda i, kind=kind: shrub(1000 + 37 * i + len(kind), SHRUBS[kind], flowers.get(kind))
            km = {'leaf': leafkey[kind], 'stem': 'stem', 'bract': 'bract', 'floret': 'floret', 'petal': 'petal', 'bud': 'bud'}
        elif kind == 'ti':
            fn = lambda i: ti_plant(2000 + i)
            km = {'leaf': lambda i: ('ti-red', 'ti-burgundy', 'ti-red', 'ti-green', 'ti-red', 'ti-burgundy')[i % 6], 'cane': 'cane', 'dry': 'dry'}
        elif kind == 'monstera':
            fn = lambda i: monstera(3000 + i)
            km = {'leaf': 'monstera', 'stem': 'green-stem'}
        protos[kind] = _variants('v-' + kind, nv, fn, mats, km)
    log(f'plants: bed variants built {time.time() - t0:.1f}s')
    for kind, pc in protos.items():
        P, R, S, I = [], [], [], []
        nv = BEDS[kind]['variants']
        for p, rect in zip(beds, bed_rects):
            if p['kind'] != kind: continue
            r = np.random.default_rng(p['seed'] & 0xffffffff)
            pts = _bed_points(r, rect, BEDS[kind]['spacing'], p.get('density', 1.1))
            for x, y in pts:
                z = ground.z(x, y)
                if z is None: z = b([0, p['ground'], 0]).z
                P.append((x, y, z - 0.015)); R.append((r.normal(0, 0.04), r.normal(0, 0.04), r.uniform(0, 6.283)))
                S.append(r.uniform(0.82, 1.18)); I.append(r.integers(0, nv))
        instancer('plants-' + kind, pc, np.array(P), np.array(R), np.array(S), np.array(I), col)
        log(f'plants: {kind} x{len(P)}')
    # mulch under every bed
    for i, rect in enumerate(bed_rects):
        mulch(ground, rect, mats['mulch'], col, f'mulch{i}', rng)

    # ---- plumeria trees
    plu = [p for p in plants if p['type'] == 'plumeria']
    if plu:
        pc = _variants('v-plumeria', 5, lambda i: plumeria_tree(4000 + i), mats, {'leaf': 'plumeria', 'bark': 'plumeria-bark', 'petal': 'plumeria-petal'})
        P, R, S, I = [], [], [], []
        for p in plu:
            r = np.random.default_rng(p['seed'] & 0xffffffff)
            v = b(p['pos']); z = ground.z(v.x, v.y); z = v.z if z is None else z
            P.append((v.x, v.y, z - 0.03)); R.append((0, 0, r.uniform(0, 6.283))); S.append(p.get('scale', 1) * r.uniform(1.05, 1.25)); I.append(r.integers(0, 5))
        instancer('plants-plumeria', pc, np.array(P), np.array(R), np.array(S), np.array(I), col)
        log(f'plants: plumeria x{len(P)} {time.time() - t0:.1f}s')

    # ---- background canopy trees
    tr = [p for p in plants if p['type'] == 'tree']
    if tr and trees:
        tk = lambda i: ('tree', 'tree-dark', 'tree-light')[i % 3]
        pc = _variants('v-tree', 6, lambda i: canopy_tree(5000 + i), mats, {'leaf': tk, 'bark': 'tree-bark'})
        P, R, S, I = [], [], [], []
        for p in tr:
            r = np.random.default_rng(p['seed'])
            v = b(p['pos']); s = p['size'] / 4.0
            P.append((v.x, v.y, v.z - 0.25)); R.append((r.normal(0, 0.03), r.normal(0, 0.03), r.uniform(0, 6.283)))
            S.append((s, s, s * p.get('sy', 1.0))); I.append(r.integers(0, 6))
        instancer('plants-trees', pc, np.array(P), np.array(R), np.array(S), np.array(I), col)
        log(f'plants: trees x{len(P)} {time.time() - t0:.1f}s')

    # ---- lawn: grass blades on the open ground of our lot and the nearest neighbours
    lw = meta.get('lawn')
    if lawn and lw and lw.get('lot'):
        lx0, lz0, lx1, lz1 = lw['lot']
        boxes = []
        for dx, dy, dz in lw.get('houses', [[0, 0, 0]]):
            if abs(dz) > near: continue
            boxes.append(brect([lx0 + dx - 14.0, lz0 + dz, lx1 + dx + 6.0, lz1 + dz]))
        X0 = min(bx[0] for bx in boxes); Y0 = min(bx[1] for bx in boxes); X1 = max(bx[2] for bx in boxes); Y1 = max(bx[3] for bx in boxes)
        skip = {c.name for c in (col, bpy.data.collections.get('palms')) if c}
        others = [o for o in bpy.data.objects if o.type == 'MESH' and not any(c.name in skip for c in o.users_collection)
                  and not any(m and m.name.startswith('terrain') for m in o.data.materials) and o.data.polygons]
        cover = _world_tris(others, box=(X0 - 1, Y0 - 1, X1 + 1, Y1 + 1), zmax=2.0)
        log(f'plants: lawn cover bvh {time.time() - t0:.1f}s')
        full, part = [], []
        seen = set()
        for bx in boxes:
            f_, p_ = lawn_cells(ground, cover, bx, bed_rects)
            for c in f_:
                k = (round(c[0], 2), round(c[1], 2))
                if k not in seen: seen.add(k); full.append(c)
            for c in p_:
                k = (round(c[0], 3), round(c[1], 3))
                if k not in seen: seen.add(k); part.append(c)
        log(f'plants: lawn cells {len(full)} full, {len(part)} edge {time.time() - t0:.1f}s')
        nv = 6
        big = proto_collection('v-turf', [bpy.data.objects.new(f't{i}', grass_tile(6000 + i, 0.5).mesh(f'turf{i}', [mats['lawn']])) for i in range(nv)])
        small = proto_collection('v-turf-s', [bpy.data.objects.new(f's{i}', grass_tile(6100 + i, 0.125).mesh(f'turfs{i}', [mats['lawn']])) for i in range(nv)])
        for name, cells, pc in (('lawn', full, big), ('lawn-edge', part, small)):
            if not cells: continue
            P = np.array([(c[0], c[1], c[2] - 0.004) for c in cells])
            rz = rng.integers(0, 4, len(cells)) * (math.pi / 2)
            R = _tilt_euler([tuple(c[3]) for c in cells], rz)
            S = np.ones((len(cells), 3)); S[:, 0] = rng.choice([-1.0, 1.0], len(cells))
            instancer('plants-' + name, pc, P, R, S, rng.integers(0, nv, len(cells)), col)
    log(f'plants: done {time.time() - t0:.1f}s')
    return col
