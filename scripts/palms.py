"""Palms for the path tracer, grown leaf by leaf.

The three.js scene draws palms as a few textured cards, which is what makes them read as CG up
close. For Cycles every palm is rebuilt here from its position and size (nahiku-meta.json):

  - 'foxtail' (the tall feather palms of the renderings; built as queen palms, Syagrus): a grey,
    ringed trunk wearing the real palm-bark photo (assets/textures/bark/palm_trunk), the cut leaf
    boots and fibrous leaf bases under the crown, 18-24 long arching fronds whose leaflets leave the
    rachis in clusters in several planes and hang limp toward the tip (the 'weeping' look),
    yellowing older fronds, a dead frond, a hanging fruit panicle
  - 'areca' (Dypsis lutescens clumps): yellow-green ringed canes, arching fronds with a V of
    leaflets
  - 'coconut' (distant skyline palms): curved trunk, long hanging leaflets, nuts

Leaflets are built vectorised (thousands per frond), crowns as a handful of variants instanced
per palm, so a whole neighbourhood of palms costs little memory.

    import palms; palms.build(meta['palms'], b)      # b: three.js world -> Blender world
"""
import math, os, random
import numpy as np
import bpy
from mathutils import Vector, Matrix, Quaternion

UP = np.array([0.0, 0.0, 1.0])
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'textures')


def _norm(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


class MeshBuf:
    """Collects polygons (all of one arity per add) with per-vertex attributes, UVs and a material
    slot per add; several bufs join into one multi-material mesh (fewer, bigger meshes keep the
    path tracer's memory down)."""
    def __init__(self):
        self.parts = []          # (verts, faces (local), uv, attrs, mat)
        self.n = 0

    @property
    def v(self): return [p[0] for p in self.parts]

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


def _leaf_material(name, greens, tip_burn, age_col=(0.2, 0.17, 0.05, 1), transl=0.32):
    """Leaflets: per-leaflet colour from a ramp of greens, older fronds (attribute 'age') yellowing,
    dry tips on a share of the leaflets (attribute 'tip'), a paler waxy underside, translucency."""
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
    agem = N.new('ShaderNodeMapRange'); agem.inputs['From Min'].default_value = 0.55; agem.inputs['From Max'].default_value = 1.0
    agem.inputs['To Max'].default_value = 0.75
    L.new(age.outputs['Fac'], agem.inputs['Value'])
    am = N.new('ShaderNodeMix'); am.data_type = 'RGBA'; am.inputs[7].default_value = age_col
    L.new(agem.outputs['Result'], am.inputs['Factor']); L.new(col, am.inputs[6]); col = am.outputs[2]
    # dry, yellow-brown tips on a share of the leaflets
    tip = N.new('ShaderNodeAttribute'); tip.attribute_name = 'tip'
    burn = N.new('ShaderNodeMapRange'); burn.inputs['From Min'].default_value = 0.8; burn.inputs['From Max'].default_value = 1.0
    L.new(tip.outputs['Fac'], burn.inputs['Value'])
    some = N.new('ShaderNodeMath'); some.operation = 'LESS_THAN'; some.inputs[1].default_value = tip_burn
    pick = N.new('ShaderNodeMath'); pick.operation = 'FRACT'
    scale = N.new('ShaderNodeMath'); scale.operation = 'MULTIPLY'; scale.inputs[1].default_value = 7.31
    L.new(geo.outputs['Random Per Island'], scale.inputs[0]); L.new(scale.outputs[0], pick.inputs[0]); L.new(pick.outputs[0], some.inputs[0])
    fac = N.new('ShaderNodeMath'); fac.operation = 'MULTIPLY'
    L.new(burn.outputs['Result'], fac.inputs[0]); L.new(some.outputs[0], fac.inputs[1])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs[7].default_value = (0.3, 0.2, 0.08, 1)
    L.new(fac.outputs[0], mix.inputs['Factor']); L.new(col, mix.inputs[6]); col = mix.outputs[2]
    # the underside is paler and greyer (waxy)
    bk = N.new('ShaderNodeMix'); bk.data_type = 'RGBA'; bk.blend_type = 'MULTIPLY'; bk.inputs[7].default_value = (1.25, 1.25, 1.15, 1)
    L.new(geo.outputs['Backfacing'], bk.inputs['Factor']); L.new(col, bk.inputs[6]); col = bk.outputs[2]
    p = N.new('ShaderNodeBsdfPrincipled')
    p.inputs['Roughness'].default_value = 0.46
    p.inputs['Specular IOR Level'].default_value = 0.34
    L.new(col, p.inputs['Base Color'])
    tr = N.new('ShaderNodeBsdfTranslucent')
    bright = N.new('ShaderNodeHueSaturation'); bright.inputs['Value'].default_value = 1.5; bright.inputs['Saturation'].default_value = 1.2
    L.new(col, bright.inputs['Color']); L.new(bright.outputs['Color'], tr.inputs['Color'])
    ms = N.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = transl
    L.new(p.outputs['BSDF'], ms.inputs[1]); L.new(tr.outputs['BSDF'], ms.inputs[2])
    L.new(ms.outputs['Shader'], out.inputs['Surface'])
    return m


def _plain(name, color, rough, bump_scale=0.0, noise_scale=40.0, var=0.0, stretch=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N.get('Principled BSDF')
    p.inputs['Base Color'].default_value = color; p.inputs['Roughness'].default_value = rough
    if var:
        geo = N.new('ShaderNodeNewGeometry')
        mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 1 - var; mr.inputs['To Max'].default_value = 1 + var
        L.new(geo.outputs['Random Per Island'], mr.inputs['Value'])
        hs = N.new('ShaderNodeHueSaturation'); hs.inputs['Color'].default_value = color
        L.new(mr.outputs['Result'], hs.inputs['Value']); L.new(hs.outputs['Color'], p.inputs['Base Color'])
    if bump_scale:
        tc = N.new('ShaderNodeTexCoord'); no = N.new('ShaderNodeTexNoise'); no.inputs['Scale'].default_value = noise_scale
        no.inputs['Detail'].default_value = 6
        src = tc.outputs['Object']
        if stretch:
            mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = stretch; L.new(src, mp.inputs['Vector']); src = mp.outputs['Vector']
        bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = bump_scale; bu.inputs['Distance'].default_value = 0.004
        L.new(src, no.inputs['Vector']); L.new(no.outputs['Fac'], bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    return m


def _trunk_material(name, bark, ring, lichen, spacing, photo=None, tint=(1, 1, 1), tile=(0.4, 0.8)):
    """Palm bark. With `photo` (a folder holding color/normal/roughness of a real palm-trunk scan):
    the photo, wrapped round the trunk (UV u around, v = metres up), tinted, with large-scale
    weathering blotches. Without: procedural grey bark with leaf-scar rings."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N.get('Principled BSDF'); p.inputs['Roughness'].default_value = 0.88
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['UV'], sep.inputs[0])
    oi = N.new('ShaderNodeObjectInfo')
    col_img = _img(os.path.join(photo, 'color.jpg'), 'sRGB') if photo else None
    if col_img is not None:
        # u: whole tiles round the trunk; v: metres / tile height; a random offset per palm
        mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (round(0.8 / tile[0]) or 1, 1.0 / tile[1], 1)
        off = N.new('ShaderNodeVectorMath'); off.operation = 'MULTIPLY'; off.inputs[1].default_value = (0.37, 3.1, 0)
        L.new(oi.outputs['Random'], off.inputs[0])
        add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'; L.new(tc.outputs['UV'], add.inputs[0]); L.new(off.outputs[0], add.inputs[1])
        L.new(add.outputs[0], mp.inputs['Vector'])
        tx = N.new('ShaderNodeTexImage'); tx.image = col_img; L.new(mp.outputs['Vector'], tx.inputs['Vector'])
        c = tx.outputs['Color']
        # tint toward the darker, cooler grey of a queen-palm trunk, and dark weathering streaks
        tn = N.new('ShaderNodeMix'); tn.data_type = 'RGBA'; tn.blend_type = 'MULTIPLY'; tn.inputs['Factor'].default_value = 1.0
        tn.inputs[7].default_value = (*tint, 1); L.new(c, tn.inputs[6]); c = tn.outputs[2]
        blot = N.new('ShaderNodeTexNoise'); blot.inputs['Scale'].default_value = 2.2; blot.inputs['Detail'].default_value = 8; blot.inputs['Roughness'].default_value = 0.62
        mpb = N.new('ShaderNodeMapping'); mpb.inputs['Scale'].default_value = (3.0, 3.0, 0.7)
        L.new(tc.outputs['Object'], mpb.inputs['Vector']); L.new(mpb.outputs['Vector'], blot.inputs['Vector'])
        bm = N.new('ShaderNodeMapRange'); bm.inputs['From Min'].default_value = 0.42; bm.inputs['From Max'].default_value = 0.68
        bm.inputs['To Min'].default_value = 0.55; bm.inputs['To Max'].default_value = 1.12
        L.new(blot.outputs['Fac'], bm.inputs['Value'])
        dk = N.new('ShaderNodeMix'); dk.data_type = 'RGBA'; dk.blend_type = 'MULTIPLY'; dk.inputs['Factor'].default_value = 1.0
        cb = N.new('ShaderNodeCombineColor'); [L.new(bm.outputs['Result'], cb.inputs[i]) for i in range(3)]
        L.new(c, dk.inputs[6]); L.new(cb.outputs[0], dk.inputs[7]); c = dk.outputs[2]
        nimg = _img(os.path.join(photo, 'normal.jpg'), 'Non-Color')
        if nimg is not None:
            tn2 = N.new('ShaderNodeTexImage'); tn2.image = nimg; L.new(mp.outputs['Vector'], tn2.inputs['Vector'])
            nm = N.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 1.3; L.new(tn2.outputs['Color'], nm.inputs['Color'])
            L.new(nm.outputs['Normal'], p.inputs['Normal'])
        rimg = _img(os.path.join(photo, 'roughness.jpg'), 'Non-Color')
        if rimg is not None:
            tr = N.new('ShaderNodeTexImage'); tr.image = rimg; L.new(mp.outputs['Vector'], tr.inputs['Vector'])
            L.new(tr.outputs['Color'], p.inputs['Roughness'])
    else:
        wob = N.new('ShaderNodeTexNoise'); wob.inputs['Scale'].default_value = 3.0
        L.new(tc.outputs['Object'], wob.inputs['Vector'])
        wobm = N.new('ShaderNodeMath'); wobm.operation = 'MULTIPLY_ADD'; wobm.inputs[1].default_value = spacing * 0.5
        L.new(wob.outputs['Fac'], wobm.inputs[0]); L.new(sep.outputs['Y'], wobm.inputs[2])
        div = N.new('ShaderNodeMath'); div.operation = 'DIVIDE'; div.inputs[1].default_value = spacing
        L.new(wobm.outputs[0], div.inputs[0])
        fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(div.outputs[0], fr.inputs[0])
        ringv = N.new('ShaderNodeMapRange'); ringv.interpolation_type = 'SMOOTHSTEP'
        ringv.inputs['From Min'].default_value = 0.0; ringv.inputs['From Max'].default_value = 0.12
        L.new(fr.outputs[0], ringv.inputs['Value'])
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
        c = gm.outputs[2]
        hb = N.new('ShaderNodeMath'); hb.operation = 'MULTIPLY_ADD'; hb.inputs[1].default_value = 0.25
        L.new(grain.outputs['Fac'], hb.inputs[0]); L.new(ringv.outputs['Result'], hb.inputs[2])
        bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = 0.55; bu.inputs['Distance'].default_value = 0.012
        L.new(hb.outputs[0], bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
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
    e[0].position = 0.3; e[0].color = (0.035, 0.03, 0.022, 1); e[1].position = 0.75; e[1].color = (0.16, 0.14, 0.11, 1)
    L.new(fib.outputs['Fac'], ramp.inputs['Fac'])
    age = N.new('ShaderNodeAttribute'); age.attribute_name = 'age'
    am = N.new('ShaderNodeMapRange'); am.inputs['From Min'].default_value = 0.35; am.inputs['From Max'].default_value = 0.0
    L.new(age.outputs['Fac'], am.inputs['Value'])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[7].default_value = (0.09, 0.12, 0.035, 1)
    L.new(am.outputs['Result'], mx.inputs['Factor']); L.new(ramp.outputs['Color'], mx.inputs[6])
    L.new(mx.outputs[2], p.inputs['Base Color'])
    bu = N.new('ShaderNodeBump'); bu.inputs['Strength'].default_value = 0.6; bu.inputs['Distance'].default_value = 0.003
    L.new(fib.outputs['Fac'], bu.inputs['Height']); L.new(bu.outputs['Normal'], p.inputs['Normal'])
    return m


def _fruit_material(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N.get('Principled BSDF'); p.inputs['Roughness'].default_value = 0.4
    geo = N.new('ShaderNodeNewGeometry')
    ramp = N.new('ShaderNodeValToRGB'); e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.12, 0.16, 0.03, 1); e[1].position = 1.0; e[1].color = (0.55, 0.25, 0.03, 1)
    e.new(0.55).color = (0.3, 0.28, 0.04, 1)
    L.new(geo.outputs['Random Per Island'], ramp.inputs['Fac']); L.new(ramp.outputs['Color'], p.inputs['Base Color'])
    return m


# ---------------------------------------------------------------- geometry
LEAFLET_ST = np.array([0.0, 0.14, 0.34, 0.58, 0.8, 1.0])


def leaflets(buf, P, T, side, beta, sweep, length, width, droop, fold, age=0.0, limp=1.4):
    """Many leaflets at once. P (n,3) points on the rachis, T (n,3) rachis tangents, side (n,) -1/+1,
    beta (n,) angle out of the frond plane, sweep (n,) lean toward the frond tip, length, width,
    droop (n,) gravity bend toward the tip, fold: V of the blade. Each leaflet: a narrow V-folded
    blade arcing away from the rachis and hanging limp toward its point."""
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


def _tube(buf, pts, radii, sides=8, v0=0.0, flat=1.0, u0=0.0, **attrs):
    """A tube along pts (UV u around, v = metres along); flat < 1 squashes it (petioles)."""
    pts = np.asarray(pts, float)
    T = _norm(np.gradient(pts, axis=0))
    ref = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
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


def _move(src, dst, R, off):
    """Appends everything in src to dst, rotated by R and shifted by off."""
    dst.extend(src, R, off)


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


KIND = {
    #            leaflets/side, leaflet len, width, rachis r, fronds, frond len
    'foxtail': dict(n_side=175, leaf_len=1.15, width=0.025, rachis=0.032, fronds=(18, 23), L=(4.0, 5.0)),
    'coconut': dict(n_side=85, leaf_len=1.0, width=0.045, rachis=0.045, fronds=(20, 26), L=(3.8, 4.8)),
    'areca': dict(n_side=55, leaf_len=0.55, width=0.028, rachis=0.016, fronds=(7, 10), L=(1.6, 2.2)),
}


def _frond(leaf, stem, rng, kind, L, elev, droop, age):
    K = KIND[kind]
    axis = _frond_axis(L, elev, droop, twist=rng.uniform(-1, 1), rng=rng, power=2.3 if kind == 'foxtail' else 1.6)
    petiole = {'foxtail': 0.16, 'coconut': 0.12, 'areca': 0.12}[kind]       # bare stalk before the first leaflet
    u_ = np.linspace(0, 1, len(axis))
    _tube(stem, axis, K['rachis'] * (0.18 + 0.82 * (1 - u_) ** 1.3 + 0.9 * np.exp(-u_ * 25)), sides=6, flat=0.7, age=age)
    T = _norm(np.gradient(axis, axis=0))
    nr = np.random.default_rng(rng.randrange(1 << 30))
    m = len(axis) - 1
    def at(s):
        idx = s * m; i0 = np.minimum(idx.astype(int), m - 1); f = (idx - i0)[:, None]
        return axis[i0] * (1 - f) + axis[i0 + 1] * f, _norm(T[i0] * (1 - f) + T[i0 + 1] * f)
    if kind == 'foxtail':
        # leaflets in clusters of 2-5, leaving the rachis in several planes (plumose), limp toward the tip
        ns = K['n_side']; S, SIDE, BETA = [], [], []
        for side in (-1, 1):
            s = petiole
            while len(S) < ns * (1 if side < 0 else 2) and s < 0.995:
                c = nr.integers(2, 6)
                for j in range(c):
                    S.append(s + nr.uniform(0, 0.006)); SIDE.append(side)
                    BETA.append(-0.85 + 1.85 * (j + nr.uniform(0, 0.8)) / c)
                s += (1 - petiole) * c / ns * nr.uniform(0.85, 1.25)
        s = np.array(S); side = np.array(SIDE, float); beta = np.array(BETA)
        n = len(s)
        P, Tt = at(s)
        u = (s - petiole) / (1 - petiole)
        prof = np.sin(np.pi * (0.08 + 0.86 * u)) ** 0.7 * (1 - 0.35 * u)
        ln = K['leaf_len'] * prof * nr.uniform(0.75, 1.1, n)
        broken = nr.random(n) < 0.03; ln[broken] *= nr.uniform(0.25, 0.6, broken.sum())
        dr = (1.5 + 3.4 * u ** 0.8) * (0.85 + 0.5 * age) * nr.uniform(0.7, 1.3, n)
        leaflets(leaf, P, Tt, side, beta, nr.uniform(0.25, 0.55, n), ln, np.full(n, K['width']) * nr.uniform(0.85, 1.15, n),
                 dr, np.full(n, 0.28), age=np.full(n, age), limp=1.3)
    elif kind == 'coconut':
        n = K['n_side'] * 2
        s = np.sort(petiole + (1 - petiole) * (np.arange(n) // 2 + nr.uniform(0, 0.8, n)) / (n // 2))
        side = np.where(np.arange(n) % 2, 1.0, -1.0)
        P, Tt = at(s); u = (s - petiole) / (1 - petiole)
        prof = np.sin(np.pi * (0.1 + 0.85 * u)) ** 0.8 * (1 - 0.3 * u)
        leaflets(leaf, P, Tt, side, -0.55 + nr.uniform(-0.2, 0.2, n), nr.uniform(0.35, 0.55, n), 1.0 * prof * nr.uniform(0.85, 1.08, n),
                 np.full(n, K['width']), (0.9 + 1.0 * u) * nr.uniform(0.8, 1.2, n), np.full(n, 0.2), age=np.full(n, age))
    else:
        n = K['n_side'] * 2
        s = np.sort(petiole + (1 - petiole) * (np.arange(n) // 2 + nr.uniform(0, 0.8, n)) / (n // 2))
        side = np.where(np.arange(n) % 2, 1.0, -1.0)
        P, Tt = at(s); u = (s - petiole) / (1 - petiole)
        prof = np.sin(np.pi * (0.1 + 0.85 * u)) ** 0.8 * (1 - 0.3 * u)
        leaflets(leaf, P, Tt, side, 0.32 + nr.uniform(-0.12, 0.12, n), nr.uniform(0.5, 0.7, n), K['leaf_len'] * prof * nr.uniform(0.88, 1.06, n),
                 np.full(n, K['width']), (0.8 + 0.6 * u) * nr.uniform(0.8, 1.2, n), np.full(n, 0.3), age=np.full(n, age))


def _drupes(buf, centres, r, elong=1.2):
    """Small round fruit (octahedra, smooth shaded) at centres (n,3)."""
    n = len(centres)
    if not n: return
    d = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, elong), (0, 0, -elong)], float)
    V = centres[:, None, :] + r[:, None, None] * d[None]
    f = np.array([[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]])
    F = (f[None] + (np.arange(n) * 6)[:, None, None]).reshape(-1, 3)
    buf.add(V.reshape(-1, 3), F)


def crown_mesh(kind, seed, mats):
    """Fronds, spear, leaf bases, dead frond and fruit; origin at the top of the trunk, Z up."""
    rng = random.Random(seed)
    K = KIND[kind]
    leaf, stem, dead, fruit, base = MeshBuf(), MeshBuf(), MeshBuf(), MeshBuf(), MeshBuf()
    n = rng.randint(*K['fronds'])
    golden = math.radians(137.5)
    az0 = rng.uniform(0, 2 * math.pi)
    for k in range(n):
        age = k / (n - 1)                                  # 0 = newest (upright) .. 1 = oldest (hanging)
        if kind == 'foxtail':
            elev = math.radians(57 - 88 * age ** 0.85 + rng.uniform(-9, 9))
            droop = (1.15 + 0.9 * age) * rng.uniform(0.85, 1.2)
            drop = -0.55 * age                              # older fronds attach lower on the trunk
        elif kind == 'coconut':
            elev = math.radians(70 - 110 * age + rng.uniform(-8, 8)); droop = 1.1 * (0.6 + 0.6 * age) * rng.uniform(0.85, 1.15); drop = -0.3 * age
        else:
            elev = math.radians(78 - 62 * age + rng.uniform(-8, 8)); droop = 1.5 * (0.6 + 0.6 * age) * rng.uniform(0.85, 1.15); drop = -0.15 * age
        L = rng.uniform(*K['L']) * (0.85 if age < 0.12 else 1.0) * (rng.uniform(0.75, 1.0) if rng.random() < 0.25 else 1.0)
        lb, sb = MeshBuf(), MeshBuf()
        _frond(lb, sb, rng, kind, L, elev, droop, age)
        az = az0 + k * golden + rng.uniform(-0.35, 0.35)
        R = np.array(Matrix.Rotation(az, 3, 'Z'))
        r0 = {'foxtail': 0.1, 'coconut': 0.12}.get(kind, 0.03)
        off = R @ np.array([r0, 0, drop])
        _move(lb, leaf, R, off); _move(sb, stem, R, off)
        if kind == 'foxtail':                              # the fibrous sheath of the leaf base, wrapping the trunk
            hd = R @ np.array([1.0, 0, 0])
            p0 = np.array([0, 0, drop - 0.55]) + hd * 0.1
            p1 = off + hd * 0.08 + np.array([0, 0, 0.05])
            pts = [p0 + (p1 - p0) * t + hd * 0.08 * math.sin(math.pi * t) for t in np.linspace(0, 1, 5)]
            _tube(base, pts, [0.07, 0.095, 0.09, 0.07, 0.045], sides=6, flat=0.5, age=age)
    # unopened spear leaf
    _tube(stem, [[0, 0, 0], [0.02, 0, 0.6], [0.03, 0.01, 1.3]], [0.04, 0.03, 0.004], sides=6, age=0.0)
    # dry fronds hanging against the trunk
    for _ in range(rng.choice([0, 1, 1, 2]) if kind in ('foxtail', 'coconut') else 0):
        lb, sb = MeshBuf(), MeshBuf()
        _frond(lb, sb, rng, kind, rng.uniform(2.2, 3.0), math.radians(rng.uniform(-84, -70)), 0.25, 1.0)
        R = np.array(Matrix.Rotation(rng.uniform(0, 6.28), 3, 'Z'))
        _move(lb, dead, R, R @ np.array([0.12, 0, -0.6])); _move(sb, dead, R, R @ np.array([0.12, 0, -0.6]))
    nr = np.random.default_rng(seed)
    if kind == 'coconut':
        c = []
        for _ in range(rng.randint(6, 16)):
            a = rng.uniform(0, 6.28); c.append([math.cos(a) * 0.25, math.sin(a) * 0.25, rng.uniform(-0.55, -0.2)])
        _drupes(fruit, np.array(c), nr.uniform(0.1, 0.13, len(c)), 1.1)
    if kind == 'foxtail':
        # one to three panicles of drupes hanging below the crown on arching stalks
        for _ in range(rng.choice([0, 1, 1, 2, 3])):
            a = rng.uniform(0, 6.28); hd = np.array([math.cos(a), math.sin(a), 0.0])
            c0 = hd * 0.2 + np.array([0, 0, -0.45])
            stalk = [c0 + hd * 0.35 * t + np.array([0, 0, -0.45 * t * t]) for t in np.linspace(0, 1, 5)]
            _tube(stem, stalk, np.linspace(0.025, 0.014, 5), sides=5, age=0.3)
            top = stalk[-1]
            C = []
            for _ in range(rng.randint(18, 30)):            # rachillae hanging off the stalk, fruit along each
                b0 = top + np.array([rng.gauss(0, 0.08), rng.gauss(0, 0.08), rng.uniform(-0.1, 0.05)])
                bd = _norm(np.array([rng.gauss(0, 0.5), rng.gauss(0, 0.5), -1.0]))
                ln = rng.uniform(0.35, 0.8)
                _tube(stem, [b0 + bd * ln * t for t in (0, 0.5, 1)], [0.005, 0.004, 0.003], sides=3, age=0.5)
                for t in np.linspace(0.1, 1.0, rng.randint(8, 14)):
                    C.append(b0 + bd * ln * t + np.array([rng.gauss(0, 0.014), rng.gauss(0, 0.014), 0]))
            C = np.array(C); _drupes(fruit, C, nr.uniform(0.011, 0.016, len(C)), 1.25)
    J = MeshBuf(); ml = []
    for buf, m in ((leaf, mats['leaf_' + kind]), (stem, mats['rachis']), (dead, mats['dead']),
                   (fruit, mats['coconut' if kind == 'coconut' else 'fruit']), (base, mats['boot'])):
        if buf.parts: J.extend(buf, mat=len(ml)); ml.append(m)
    return [J.mesh(f'{kind}{seed}-crown', ml)]


def trunk_mesh(height, r0, lean_dir, bend, kind, seed, mats=None):
    """Trunk (and, for queen palms, the boots below the crown) as MeshBufs at the origin."""
    rng = random.Random(seed)
    n = max(10, int(height / (0.2 if kind == 'foxtail' else 0.4)))
    pts, radii = [], []
    for i in range(n + 1):
        t = i / n
        off = bend * height * t * t
        pts.append([math.cos(lean_dir) * off, math.sin(lean_dir) * off, height * t])
        if kind == 'foxtail':      # flared foot, a gentle swelling a third of the way up (queen palm)
            r = r0 * (1.0 + 0.4 * math.exp(-t * 22) + 0.1 * math.exp(-((t - 0.35) / 0.25) ** 2) - 0.12 * t)
        elif kind == 'coconut':
            r = r0 * (1.0 + 0.6 * math.exp(-t * 14) - 0.22 * t)
        else:
            r = r0 * (1.0 + 0.2 * math.exp(-t * 20) - 0.15 * t)
        radii.append(r)
    buf = MeshBuf()
    _tube(buf, pts, radii, sides={'foxtail': 16, 'coconut': 10}.get(kind, 7), u0=rng.random())   # v stays metres from the foot (the foot darkening reads it)
    top = np.array(pts[-1]); tdir = _norm(np.array(pts[-1]) - np.array(pts[-2]))
    sh = None
    if kind == 'foxtail':
        # the cut leaf bases ('boots') of old fronds in a spiral below the crown: flat, wedge-shaped
        # stubs standing up and out from the trunk, the older ones lower down and greyer
        sb = MeshBuf()
        rt = radii[-1]
        _tube(sb, [top + tdir * (h - 1.0) for h in np.linspace(0, 1, 6)], [rt * f for f in (1.0, 1.06, 1.12, 1.16, 1.12, 0.9)], sides=14, age=0.6)
        nb = rng.randint(16, 24); a0 = rng.uniform(0, 6.28)
        for k in range(nb):
            u = k / (nb - 1)
            a = a0 + k * math.radians(137.5) + rng.uniform(-0.2, 0.2); hd = np.array([math.cos(a), math.sin(a), 0.0])
            h0 = -0.55 - 1.3 * u + rng.uniform(-0.08, 0.08)
            if top[2] + h0 < 1.5: continue
            p0 = top + tdir * h0 + hd * rt * 0.75
            d = _norm(hd * rng.uniform(0.55, 1.1) + np.array([0, 0, 1.0]))
            ln = rng.uniform(0.28, 0.55) * (1 - 0.3 * u)
            w = rng.uniform(0.065, 0.095)
            _tube(sb, [p0 + d * ln * t + hd * 0.04 * t * t for t in np.linspace(0, 1, 4)], [w, w * 0.92, w * 0.8, w * 0.45], sides=6, flat=0.4, age=0.4 + 0.6 * u)
        sh = sb
    return buf, sh, Vector(top.tolist()), Vector(tdir.tolist())


def materials():
    lin = lambda r, g, b: (r, g, b, 1)
    photo = os.path.join(ASSETS, 'bark', 'palm_trunk')
    photo = photo if os.path.exists(os.path.join(photo, 'color.jpg')) else None
    return {
        'leaf_foxtail': _leaf_material('palm leaf', [lin(0.06, 0.09, 0.018), lin(0.085, 0.115, 0.022), lin(0.115, 0.14, 0.03), lin(0.16, 0.165, 0.045)], 0.4),
        'leaf_areca': _leaf_material('areca leaf', [lin(0.06, 0.12, 0.022), lin(0.095, 0.16, 0.03), lin(0.14, 0.2, 0.04)], 0.15, age_col=(0.3, 0.26, 0.06, 1)),
        'rachis': _plain('palm rachis', (0.2, 0.21, 0.09, 1), 0.5, var=0.15),
        'dead': _plain('palm dead frond', (0.2, 0.14, 0.07, 1), 0.8, var=0.2),
        'fruit': _fruit_material('palm fruit'),
        'boot': _boot_material('palm leaf base'),
        'shaft': _plain('palm crownshaft', (0.085, 0.07, 0.045, 1), 0.85, bump_scale=0.4, noise_scale=120),
        'trunk_foxtail': _trunk_material('palm trunk', (0.05, 0.048, 0.044, 1), (0.022, 0.021, 0.019, 1), (0.11, 0.11, 0.1, 1), 0.06,
                                         photo=photo, tint=(0.46, 0.44, 0.41), tile=(0.45, 0.9)),
        'trunk_areca': _trunk_material('areca stem', (0.2, 0.22, 0.09, 1), (0.08, 0.08, 0.04, 1), (0.25, 0.25, 0.12, 1), 0.12),
        'leaf_coconut': _leaf_material('coconut leaf', [lin(0.05, 0.09, 0.02), lin(0.08, 0.13, 0.03), lin(0.11, 0.15, 0.04), lin(0.15, 0.16, 0.05)], 0.25),
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


VARIANTS = {'foxtail': 6, 'areca': 5, 'coconut': 4}


def build(palms, b, variants=None, collection_name='palms'):
    """palms: [{kind, seed, base (three.js metres), height, trunkR, lean}]; b: three.js -> Blender.
    Trunks of a kind are merged into one mesh; crowns are a few variants per kind, instanced."""
    col = bpy.data.collections.new(collection_name); bpy.context.scene.collection.children.link(col)
    mats = materials()
    nvar = {k: (variants or v) for k, v in VARIANTS.items()}
    protos = {}
    for kind in ('foxtail', 'areca', 'coconut'):
        if any(p.get('kind', 'foxtail') == kind for p in palms):
            pc = bpy.data.collections.new('v-' + kind + '-crowns')
            for i in range(nvar[kind]):
                pc.objects.link(bpy.data.objects.new(f'{kind}-crown-{i:02d}', crown_mesh(kind, 100 + i, mats)[0]))
            protos[kind] = pc
    trunks, boots = {}, MeshBuf()
    inst = {k: ([], [], [], []) for k in protos}
    for p in palms:
        rng = random.Random(p['seed'])
        kind = p.get('kind', 'foxtail')
        base = b(p['base'])
        h = p['height'] * (0.92 if kind == 'areca' else 1.0)
        r0 = max(p.get('trunkR', 0.17), 0.04) * {'foxtail': 1.12, 'coconut': 0.95}.get(kind, 0.9)
        bend = (0.03 + rng.random() * 0.05) * min(p.get('lean', 1), 2.5) * {'foxtail': 0.5, 'coconut': 1.6}.get(kind, 1.0)
        tb, sh, top, tdir = trunk_mesh(h, r0, rng.uniform(0, 6.283), bend, kind, p['seed'])
        trunks.setdefault(kind, MeshBuf()).extend(tb, off=np.array(base[:]))      # all trunks of a kind: one mesh
        if sh: boots.extend(sh, off=np.array(base[:]))
        q = Vector((0, 0, 1)).rotation_difference(tdir)
        q = q @ Quaternion((0, 0, 1), rng.uniform(0, 6.283))
        s = (h / 10.0) ** 0.25 if kind in ('foxtail', 'coconut') else (h / 3.0) ** 0.35
        P, R, S, I = inst[kind]
        P.append(tuple(base + top)); R.append(tuple(q.to_euler('XYZ'))); S.append(s); I.append(rng.randrange(nvar[kind]))
        if kind == 'areca':
            # a young sucker or two at the foot of every cane: arecas grow as dense clumps
            for _ in range(rng.choice([1, 1, 2])):
                a_ = rng.uniform(0, 6.283); d_ = rng.uniform(0.15, 0.4)
                sb = base + Vector((math.cos(a_) * d_, math.sin(a_) * d_, -0.02)); hs = rng.uniform(0.35, 0.8)
                qs = Quaternion((0, 0, 1), rng.uniform(0, 6.283)); qs = Quaternion(Vector((math.cos(a_ + 1.57), math.sin(a_ + 1.57), 0)), rng.uniform(0.1, 0.35)) @ qs
                P.append(tuple(sb + Vector((0, 0, hs * 0.5)))); R.append(tuple(qs.to_euler('XYZ'))); S.append(hs); I.append(rng.randrange(nvar[kind]))
    for kind, (P, R, S, I) in inst.items():
        if P: _instancer('palms-' + kind, protos[kind], P, R, S, I, col)
    for kind, tb in trunks.items():
        col.objects.link(bpy.data.objects.new('trunks-' + kind, tb.mesh('trunks-' + kind, mats['trunk_' + kind])))
    if boots.parts:
        col.objects.link(bpy.data.objects.new('boots', boots.mesh('boots', mats['boot'])))
    return col
