"""Palms for the path tracer, grown leaf by leaf.

The three.js scene draws palms as a few textured cards, which is what makes them read as CG up
close. For Cycles every palm is rebuilt here from its position and size (nahiku-meta.json): a
ringed, slightly bottle-shaped trunk, a smooth crownshaft, fronds with hundreds of individual
leaflets (foxtail: leaflets in every plane round the rachis; areca: a V of arching leaflets), an
unopened spear, a hanging dead frond and fruit on some. Crowns are built as a handful of variants
and instanced, so a whole neighbourhood of palms costs little memory.

    import palms; palms.build(meta['palms'], b)      # b: three.js world -> Blender world
"""
import math, random
import numpy as np
import bpy
from mathutils import Vector, Matrix, Quaternion

UP = np.array([0.0, 0.0, 1.0])


def _norm(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


class MeshBuf:
    """Collects quads (and per-vertex attributes) and turns them into one Blender mesh."""
    def __init__(self):
        self.v, self.f, self.attr = [], [], {}
        self.n = 0

    def add(self, verts, faces, **attrs):
        verts = np.asarray(verts, dtype=np.float32).reshape(-1, 3)
        self.v.append(verts); self.f.append(np.asarray(faces, dtype=np.int64) + self.n)
        for k, a in attrs.items():
            self.attr.setdefault(k, []).append(np.broadcast_to(np.asarray(a, dtype=np.float32), (len(verts),)).copy())
        self.n += len(verts)

    def mesh(self, name, material, uv=None):
        V = np.concatenate(self.v); F = np.concatenate(self.f)
        me = bpy.data.meshes.new(name)
        me.from_pydata(V.tolist(), [], F.tolist())
        me.materials.append(material)
        me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
        for k, parts in self.attr.items():
            a = me.attributes.new(k, 'FLOAT', 'POINT'); a.data.foreach_set('value', np.concatenate(parts))
        if uv is not None:
            lay = me.uv_layers.new(name='UVMap')
            loops = np.zeros(len(me.loops), dtype=np.int64); me.loops.foreach_get('vertex_index', loops)
            lay.data.foreach_set('uv', np.asarray(uv, dtype=np.float32)[loops].ravel())
        me.update()
        return me


# ---------------------------------------------------------------- materials
def _leaf_material(name, greens, tip_burn):
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
    # dry, yellowed tips on a share of the leaflets
    tip = N.new('ShaderNodeAttribute'); tip.attribute_name = 'tip'
    burn = N.new('ShaderNodeMapRange'); burn.inputs['From Min'].default_value = 0.86; burn.inputs['From Max'].default_value = 1.0
    L.new(tip.outputs['Fac'], burn.inputs['Value'])
    some = N.new('ShaderNodeMath'); some.operation = 'LESS_THAN'; some.inputs[1].default_value = tip_burn
    pick = N.new('ShaderNodeMath'); pick.operation = 'FRACT'
    scale = N.new('ShaderNodeMath'); scale.operation = 'MULTIPLY'; scale.inputs[1].default_value = 7.31
    L.new(geo.outputs['Random Per Island'], scale.inputs[0]); L.new(scale.outputs[0], pick.inputs[0]); L.new(pick.outputs[0], some.inputs[0])
    fac = N.new('ShaderNodeMath'); fac.operation = 'MULTIPLY'
    L.new(burn.outputs['Result'], fac.inputs[0]); L.new(some.outputs[0], fac.inputs[1])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs[7].default_value = (0.21, 0.15, 0.06, 1)
    L.new(fac.outputs[0], mix.inputs['Factor']); L.new(ramp.outputs['Color'], mix.inputs[6])
    p = N.new('ShaderNodeBsdfPrincipled')
    p.inputs['Roughness'].default_value = 0.36
    p.inputs['Specular IOR Level'].default_value = 0.55
    L.new(mix.outputs[2], p.inputs['Base Color'])
    tr = N.new('ShaderNodeBsdfTranslucent')
    bright = N.new('ShaderNodeHueSaturation'); bright.inputs['Value'].default_value = 1.5; bright.inputs['Saturation'].default_value = 1.15
    L.new(mix.outputs[2], bright.inputs['Color']); L.new(bright.outputs['Color'], tr.inputs['Color'])
    ms = N.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = 0.3
    L.new(p.outputs['BSDF'], ms.inputs[1]); L.new(tr.outputs['BSDF'], ms.inputs[2])
    L.new(ms.outputs['Shader'], out.inputs['Surface'])
    return m


def _plain(name, color, rough, bump_scale=0.0, noise_scale=40.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = color; p.inputs['Roughness'].default_value = rough
    if bump_scale:
        nt = m.node_tree
        tc = nt.nodes.new('ShaderNodeTexCoord'); no = nt.nodes.new('ShaderNodeTexNoise'); no.inputs['Scale'].default_value = noise_scale
        bu = nt.nodes.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = bump_scale; bu.inputs['Distance'].default_value = 0.004
        nt.links.new(tc.outputs['Object'], no.inputs['Vector']); nt.links.new(no.outputs['Fac'], bu.inputs['Height']); nt.links.new(bu.outputs['Normal'], p.inputs['Normal'])
    return m


def _trunk_material(name, bark, ring, lichen, spacing):
    """Grey bark with leaf-scar rings (UV v = metres up the trunk), lichen blotches, soil splash at the foot."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N.get('Principled BSDF'); p.inputs['Roughness'].default_value = 0.88
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['UV'], sep.inputs[0])
    # slightly wavy rings
    wob = N.new('ShaderNodeTexNoise'); wob.inputs['Scale'].default_value = 3.0
    L.new(tc.outputs['Object'], wob.inputs['Vector'])
    wobm = N.new('ShaderNodeMath'); wobm.operation = 'MULTIPLY_ADD'; wobm.inputs[1].default_value = spacing * 0.5
    L.new(wob.outputs['Fac'], wobm.inputs[0]); L.new(sep.outputs['Y'], wobm.inputs[2])
    div = N.new('ShaderNodeMath'); div.operation = 'DIVIDE'; div.inputs[1].default_value = spacing
    L.new(wobm.outputs[0], div.inputs[0])
    fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(div.outputs[0], fr.inputs[0])
    ringv = N.new('ShaderNodeMapRange'); ringv.interpolation_type = 'SMOOTHSTEP'
    ringv.inputs['From Min'].default_value = 0.0; ringv.inputs['From Max'].default_value = 0.12
    L.new(fr.outputs[0], ringv.inputs['Value'])          # 0 at the scar, 1 on the smooth band
    # fine vertical fibres and blotches
    grain = N.new('ShaderNodeTexNoise'); grain.inputs['Scale'].default_value = 60.0; grain.inputs['Detail'].default_value = 6
    stretch = N.new('ShaderNodeMapping'); stretch.inputs['Scale'].default_value = (6.0, 6.0, 0.6)
    L.new(tc.outputs['Object'], stretch.inputs['Vector']); L.new(stretch.outputs['Vector'], grain.inputs['Vector'])
    blot = N.new('ShaderNodeTexNoise'); blot.inputs['Scale'].default_value = 5.0; blot.inputs['Detail'].default_value = 8; blot.inputs['Roughness'].default_value = 0.7
    L.new(tc.outputs['Object'], blot.inputs['Vector'])
    lich = N.new('ShaderNodeMapRange'); lich.inputs['From Min'].default_value = 0.58; lich.inputs['From Max'].default_value = 0.7
    L.new(blot.outputs['Fac'], lich.inputs['Value'])
    c1 = N.new('ShaderNodeMix'); c1.data_type = 'RGBA'; c1.inputs[6].default_value = ring; c1.inputs[7].default_value = bark
    L.new(ringv.outputs['Result'], c1.inputs['Factor'])
    c2 = N.new('ShaderNodeMix'); c2.data_type = 'RGBA'; c2.inputs[7].default_value = lichen
    L.new(lich.outputs['Result'], c2.inputs['Factor']); L.new(c1.outputs[2], c2.inputs[6])
    gm = N.new('ShaderNodeMix'); gm.data_type = 'RGBA'; gm.blend_type = 'MULTIPLY'; gm.inputs['Factor'].default_value = 0.35
    L.new(c2.outputs[2], gm.inputs[6]); L.new(grain.outputs['Color'], gm.inputs[7])
    # darker, earthier at the foot
    foot = N.new('ShaderNodeMapRange'); foot.inputs['From Min'].default_value = 0.6; foot.inputs['From Max'].default_value = 0.0
    L.new(sep.outputs['Y'], foot.inputs['Value'])
    c3 = N.new('ShaderNodeMix'); c3.data_type = 'RGBA'; c3.blend_type = 'MULTIPLY'; c3.inputs[7].default_value = (0.55, 0.45, 0.35, 1)
    L.new(foot.outputs['Result'], c3.inputs['Factor']); L.new(gm.outputs[2], c3.inputs[6])
    L.new(c3.outputs[2], p.inputs['Base Color'])
    hb = N.new('ShaderNodeMath'); hb.operation = 'MULTIPLY_ADD'; hb.inputs[1].default_value = 0.25
    L.new(grain.outputs['Fac'], hb.inputs[0]); L.new(ringv.outputs['Result'], hb.inputs[2])
    bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = 0.55; bu.inputs['Distance'].default_value = 0.012
    L.new(hb.outputs[0], bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    return m


# ---------------------------------------------------------------- geometry
def _leaflet(buf, rng, P, T, side, beta, sweep, length, width, droop, fold, stations=(0.0, 0.12, 0.35, 0.62, 0.85, 1.0)):
    """One leaflet from rachis point P: a narrow, V-folded blade that arcs and droops to a point."""
    Y = _norm(np.cross(UP, T)) if abs(T[2]) < 0.97 else np.array([0, 1.0, 0])
    Nn = _norm(np.cross(T, Y))
    d0 = _norm(math.cos(sweep) * (side * Y * math.cos(beta) + Nn * math.sin(beta)) + math.sin(sweep) * T)
    pts, dirs = [P.copy()], []
    seg = np.diff(stations) * length
    p = P.copy()
    for k, ds in enumerate(seg):
        t = stations[k + 1]
        d = _norm(d0 - UP * droop * t ** 1.4)
        p = p + d * ds; pts.append(p.copy()); dirs.append(d)
    dirs = [dirs[0]] + dirs
    verts, tips = [], []
    for k, (q, d) in enumerate(zip(pts, dirs)):
        t = stations[k]
        nb = _norm(np.cross(T, d)); nb = nb if nb[2] >= 0 else -nb
        w = _norm(np.cross(nb, d))
        hw = width * 0.5 * (0.35 + 0.65 * math.sin(math.pi * min(1.0, 0.18 + t * 0.95)) ** 0.7) * (1 - t ** 3)
        verts += [q - w * hw, q + nb * hw * fold, q + w * hw]
        tips += [t, t, t]
    faces = []
    for k in range(len(pts) - 1):
        a = k * 3
        faces += [[a, a + 3, a + 4, a + 1], [a + 1, a + 4, a + 5, a + 2]]
    buf.add(verts, faces, tip=tips)


def _tube(buf, pts, radii, sides=8, uv=None, v0=0.0):
    """A tube along pts; returns per-vertex uv (u around, v = metres along) if uv is a list."""
    pts = np.asarray(pts, float)
    T = _norm(np.gradient(pts, axis=0))
    ref = np.array([1.0, 0, 0]) if abs(T[0][0]) < 0.9 else np.array([0, 1.0, 0])
    verts, faces = [], []
    s = 0.0
    for i, (p, t, r) in enumerate(zip(pts, T, radii)):
        if i: s += np.linalg.norm(pts[i] - pts[i - 1])
        a = _norm(np.cross(t, ref)); b = np.cross(t, a)
        for j in range(sides + 1):
            th = 2 * math.pi * j / sides
            verts.append(p + r * (math.cos(th) * a + math.sin(th) * b))
            if uv is not None: uv.append((j / sides, v0 + s))
    for i in range(len(pts) - 1):
        for j in range(sides):
            a = i * (sides + 1) + j
            faces.append([a, a + 1, a + sides + 2, a + sides + 1])
    buf.add(verts, faces)


def _move(src, dst, R, off, attrs=True):
    """Appends everything in src to dst, rotated by R and shifted by off."""
    if not src.v: return
    V = np.concatenate(src.v) @ R.T + off
    F = np.concatenate(src.f)
    extra = {k: np.concatenate(a) for k, a in src.attr.items()} if attrs else {}
    dst.add(V, F, **extra)


def _frond_axis(L, elev, droop, n=20, twist=0.0):
    pts, p = [np.zeros(3)], np.zeros(3)
    for i in range(n):
        s = (i + 0.5) / n
        a = elev - droop * s ** 1.5
        p = p + (L / n) * np.array([math.cos(a), math.sin(twist * s) * 0.15, math.sin(a)])
        pts.append(p.copy())
    return np.array(pts)


def _frond(leaf, stem, rng, kind, L, elev, droop):
    axis = _frond_axis(L, elev, droop, twist=rng.uniform(-1, 1))
    _tube(stem, axis, np.linspace({'foxtail': 0.028, 'coconut': 0.04}.get(kind, 0.018), 0.006, len(axis)), sides=5)
    T = _norm(np.gradient(axis, axis=0))
    n_side = {'foxtail': 190, 'coconut': 100}.get(kind, 62)
    for side in (-1, 1):
        for i in range(n_side):
            s = 0.07 + 0.92 * (i + rng.uniform(0, 0.8)) / n_side
            idx = s * (len(axis) - 1); i0 = int(idx); f = idx - i0
            P = axis[i0] * (1 - f) + axis[min(i0 + 1, len(axis) - 1)] * f
            Tt = _norm(T[i0] * (1 - f) + T[min(i0 + 1, len(axis) - 1)] * f)
            prof = math.sin(math.pi * (0.1 + 0.85 * s)) ** 0.8 * (1 - 0.3 * s)
            if kind == 'foxtail':
                beta = rng.uniform(-0.8, 1.5)              # leaflets radiate all round the rachis
                _leaflet(leaf, rng, P, Tt, side, beta, rng.uniform(0.3, 0.6), 0.9 * prof * rng.uniform(0.8, 1.1),
                         0.034, 1.6 + 1.8 * s, 0.25)
            elif kind == 'coconut':
                beta = -0.55 + rng.uniform(-0.2, 0.2)      # long leaflets hanging in a V under the rachis
                _leaflet(leaf, rng, P, Tt, side, beta, rng.uniform(0.35, 0.55), 0.95 * prof * rng.uniform(0.85, 1.08),
                         0.038, 1.1 + 0.9 * s, 0.2)
            else:
                beta = 0.32 + rng.uniform(-0.12, 0.12)    # a V of arching leaflets
                _leaflet(leaf, rng, P, Tt, side, beta, rng.uniform(0.5, 0.7), 0.52 * prof * rng.uniform(0.9, 1.05),
                         0.03, 0.9 + 0.5 * s, 0.3)


def crown_mesh(kind, seed, mats):
    """Fronds, spear, crownshaft cap, dead frond and fruit, origin at the top of the trunk, Z up."""
    rng = random.Random(seed)
    leaf, stem, dead, fruit, shaft = MeshBuf(), MeshBuf(), MeshBuf(), MeshBuf(), MeshBuf()
    if kind == 'foxtail':
        n, Lr = rng.randint(18, 22), (3.7, 4.7)
    elif kind == 'coconut':
        n, Lr = rng.randint(20, 26), (3.6, 4.6)
    else:
        n, Lr = rng.randint(6, 8), (1.6, 2.1)
    golden = math.radians(137.5)
    az0 = rng.uniform(0, 2 * math.pi)
    for k in range(n):
        age = k / (n - 1)                                  # 0 = newest (upright) .. 1 = oldest (hanging)
        elev = math.radians({'foxtail': 62 - 118 * age, 'coconut': 70 - 110 * age}.get(kind, 75 - 70 * age) + rng.uniform(-8, 8))
        droop = {'foxtail': 1.9, 'coconut': 1.1}.get(kind, 1.5) * ({'foxtail': 0.55 + 0.6 * age}.get(kind, 0.6 + 0.6 * age)) * rng.uniform(0.85, 1.15)
        L = rng.uniform(*Lr)
        lb, sb = MeshBuf(), MeshBuf()
        _frond(lb, sb, rng, kind, L, elev, droop)
        rot = Matrix.Rotation(az0 + k * golden + rng.uniform(-0.2, 0.2), 3, 'Z')
        R = np.array(rot)
        _move(lb, leaf, R, R @ np.array([0.06, 0, 0]))
        _move(sb, stem, R, R @ np.array([0.06, 0, 0]))
    # unopened spear leaf
    _tube(stem, [[0, 0, 0], [0.02, 0, 0.5], [0.03, 0.01, 1.1]], [0.035, 0.03, 0.004], sides=6)
    # dry fronds hanging against the trunk
    for _ in range(rng.choice([0, 1, 1, 2]) if kind in ('foxtail', 'coconut') else 0):
        lb, sb = MeshBuf(), MeshBuf()
        _frond(lb, sb, rng, kind, rng.uniform(2.0, 2.8), math.radians(rng.uniform(-80, -62)), 0.3)
        R = np.array(Matrix.Rotation(rng.uniform(0, 6.28), 3, 'Z'))
        _move(lb, dead, R, np.array([0, 0, -0.2]), attrs=False)
        _move(sb, dead, R, np.array([0, 0, -0.2]), attrs=False)
    # coconuts in a cluster under the crown
    if kind == 'coconut':
        for _ in range(rng.randint(6, 16)):
            a = rng.uniform(0, 6.28); q = np.array([math.cos(a) * 0.25, math.sin(a) * 0.25, rng.uniform(-0.55, -0.2)])
            r = rng.uniform(0.1, 0.13)
            oct_v = [q + r * np.array(d) for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1.1), (0, 0, -1.1))]
            fruit.add(oct_v, [[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]])
    # fruit for foxtails: one to three panicles of drupes hanging below the crown on arching stalks
    if kind == 'foxtail':
        for _ in range(rng.choice([0, 1, 1, 2, 3])):
            a = rng.uniform(0, 6.28); hd = np.array([math.cos(a), math.sin(a), 0.0])
            c0 = hd * 0.18 + np.array([0, 0, -0.5])
            stalk = [c0 + hd * 0.25 * t + np.array([0, 0, -0.5 * t * t]) for t in np.linspace(0, 1, 5)]
            _tube(stem, stalk, np.linspace(0.02, 0.012, 5), sides=5)
            top = stalk[-1]
            for _ in range(rng.randint(14, 22)):            # rachillae hanging off the stalk, fruit along each
                b0 = top + np.array([rng.gauss(0, 0.06), rng.gauss(0, 0.06), rng.uniform(-0.05, 0.05)])
                bd = _norm(np.array([rng.gauss(0, 0.5), rng.gauss(0, 0.5), -1.0]))
                ln = rng.uniform(0.35, 0.7)
                for t in np.linspace(0.1, 1.0, rng.randint(8, 14)):
                    q = b0 + bd * ln * t + np.array([rng.gauss(0, 0.012), rng.gauss(0, 0.012), 0])
                    r = rng.uniform(0.011, 0.015)
                    oct_v = [q + r * np.array(d) for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1.25), (0, 0, -1.25))]
                    fruit.add(oct_v, [[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]])
    objs = []
    for buf, m, nm in ((leaf, mats['leaf_' + kind], 'leaves'), (stem, mats['rachis'], 'rachis'), (dead, mats['dead'], 'dead'), (fruit, mats['coconut' if kind == 'coconut' else 'fruit'], 'fruit')):
        if buf.v: objs.append(buf.mesh(f'{kind}{seed}-{nm}', m))
    return objs


def trunk_mesh(height, r0, lean_dir, bend, kind, seed, mats):
    rng = random.Random(seed)
    n = max(8, int(height / 0.25))
    pts, radii = [], []
    for i in range(n + 1):
        t = i / n
        off = bend * height * t * t
        pts.append([math.cos(lean_dir) * off, math.sin(lean_dir) * off, height * t])
        if kind == 'foxtail':
            r = r0 * (1.0 + 0.35 * math.exp(-t * 18) + 0.12 * math.exp(-((t - 0.3) / 0.25) ** 2) - 0.18 * t)
        elif kind == 'coconut':
            r = r0 * (1.0 + 0.6 * math.exp(-t * 14) - 0.22 * t)
        else:
            r = r0 * (1.0 + 0.2 * math.exp(-t * 20) - 0.15 * t)
        radii.append(r)
    buf, uv = MeshBuf(), []
    _tube(buf, pts, radii, sides={'foxtail': 14, 'coconut': 10}.get(kind, 7), uv=uv)
    me = buf.mesh(f'trunk{seed}', mats['trunk_' + kind], uv=uv)
    top = np.array(pts[-1]); tdir = _norm(np.array(pts[-1]) - np.array(pts[-2]))
    sh = None
    if kind == 'foxtail':      # fibrous crown base with the boots of cut old leaf bases (queen palm)
        sb = MeshBuf()
        L = 1.3
        _tube(sb, [top + tdir * (L * s - L) for s in np.linspace(0, 1, 6)], [radii[-1] * f for f in (1.0, 1.12, 1.2, 1.18, 1.0, 0.6)], sides=14)
        for k in range(rng.randint(7, 12)):
            a = rng.uniform(0, 6.28); hd = np.array([math.cos(a), math.sin(a), 0.0])
            h0 = rng.uniform(-1.6, -0.35)
            p0 = top + tdir * h0 + hd * radii[-1] * 0.8
            d = _norm(hd * rng.uniform(0.5, 1.0) + np.array([0, 0, rng.uniform(0.6, 1.4)]))
            ln = rng.uniform(0.2, 0.45)
            _tube(sb, [p0 + d * ln * t for t in np.linspace(0, 1, 4)], [0.05, 0.045, 0.035, 0.01], sides=5)
        sh = sb.mesh(f'shaft{seed}', mats['shaft'])
    return me, sh, Vector(top.tolist()), Vector(tdir.tolist())


def materials():
    lin = lambda r, g, b: (r, g, b, 1)
    return {
        'leaf_foxtail': _leaf_material('palm leaf', [lin(0.05, 0.09, 0.025), lin(0.075, 0.12, 0.035), lin(0.1, 0.145, 0.045), lin(0.14, 0.165, 0.06)], 0.25),
        'leaf_areca': _leaf_material('areca leaf', [lin(0.05, 0.11, 0.02), lin(0.085, 0.15, 0.03), lin(0.13, 0.19, 0.04)], 0.12),
        'rachis': _plain('palm rachis', (0.16, 0.18, 0.06, 1), 0.5),
        'dead': _plain('palm dead frond', (0.2, 0.14, 0.07, 1), 0.8),
        'fruit': _plain('palm fruit', (0.42, 0.2, 0.03, 1), 0.4),
        'shaft': _plain('palm crownshaft', (0.085, 0.07, 0.045, 1), 0.85, bump_scale=0.4, noise_scale=120),
        'trunk_foxtail': _trunk_material('palm trunk', (0.05, 0.048, 0.044, 1), (0.022, 0.021, 0.019, 1), (0.11, 0.11, 0.1, 1), 0.06),
        'trunk_areca': _trunk_material('areca stem', (0.2, 0.22, 0.09, 1), (0.08, 0.08, 0.04, 1), (0.25, 0.25, 0.12, 1), 0.12),
        'leaf_coconut': _leaf_material('coconut leaf', [lin(0.05, 0.09, 0.02), lin(0.08, 0.13, 0.03), lin(0.11, 0.15, 0.04), lin(0.15, 0.16, 0.05)], 0.25),
        'trunk_coconut': _trunk_material('coconut trunk', (0.075, 0.066, 0.055, 1), (0.035, 0.03, 0.025, 1), (0.13, 0.125, 0.11, 1), 0.09),
        'coconut': _plain('coconut fruit', (0.12, 0.13, 0.03, 1), 0.45),
    }


def build(palms, b, variants=6, collection_name='palms'):
    """palms: [{kind, seed, base (three.js metres), height, trunkR, lean}]; b: three.js -> Blender."""
    col = bpy.data.collections.new(collection_name); bpy.context.scene.collection.children.link(col)
    mats = materials()
    crowns = {}
    for kind in ('foxtail', 'areca', 'coconut'):
        if any(p.get('kind', 'foxtail') == kind for p in palms):
            crowns[kind] = [crown_mesh(kind, 100 + i, mats) for i in range(variants)]
    for p in palms:
        rng = random.Random(p['seed'])
        kind = p.get('kind', 'foxtail')
        base = b(p['base'])
        h = p['height'] * (0.92 if kind == 'areca' else 1.0)
        r0 = max(p.get('trunkR', 0.17), 0.04) * {'foxtail': 0.75, 'coconut': 0.85}.get(kind, 0.9)
        bend = (0.03 + rng.random() * 0.05) * min(p.get('lean', 1), 2.5) * {'foxtail': 0.5, 'coconut': 1.6}.get(kind, 1.0)
        me, sh, top, tdir = trunk_mesh(h, r0, rng.uniform(0, 6.283), bend, kind, p['seed'], mats)
        o = bpy.data.objects.new('trunk', me); o.location = base; col.objects.link(o)
        if sh: so = bpy.data.objects.new('shaft', sh); so.location = base; col.objects.link(so)
        q = Vector((0, 0, 1)).rotation_difference(tdir)
        q = q @ Quaternion((0, 0, 1), rng.uniform(0, 6.283))
        s = (h / 10.0) ** 0.25 if kind in ('foxtail', 'coconut') else (h / 3.0) ** 0.35
        for cm in crowns[kind][rng.randrange(variants)]:
            co = bpy.data.objects.new('crown', cm); col.objects.link(co)
            co.location = base + top; co.rotation_mode = 'QUATERNION'; co.rotation_quaternion = q; co.scale = (s, s, s)
    return col
