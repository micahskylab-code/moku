"""Pool, spa and vanishing-edge water for the Cycles renders (geometry: src/pool.js).

    import water_bpy; water_bpy.apply(meta=meta, night=False, log=print)     # after materials_bpy.apply()

Every material src/pool.js names is (re)built here:
  pool / spa / basin water   closed bodies: a rippled IOR 1.333 surface over Volume Absorption, so the colour
                             comes from the light path (turquoise over the steps, deep blue-green in the deep
                             end, the white plaster lit through it); the basin is churned where the falls land
  pool plaster               white marcite with fake caustics (Cycles caustics are too slow): a sharpened,
                             noise-warped Voronoi web brightening the floor and treads, fainter on the walls
  waterline tile             6" blue glass tiles in three blues, 1/8" grout, glossy and slightly pillowed
  pool coping / weir cap     honed sandstone in 2-3 ft pieces (per-piece tint), bullnosed; the weir cap wet
  falls face                 the garden-wall stone, wet: darker, glossy
  falls streamer             water IOR 1.33, glassy at the lip, whitening with entrained air as it falls
  falls foam                 aeration where the streams land (white, broken by noise, fading out)
  spa jet, pool light lens   stainless fittings; light lenses glow at night
"""
import math
import bpy
import materials_bpy as M

WATER = ('pool water', 'spa water', 'basin water')


def _uv(g):
    return g.texco().outputs['UV']


def _chop(g, scale=1.0, strength=1.0):
    """Wind chop on a water surface: stretched noise (~1.5 ft) plus a fine ripple; returns a normal."""
    P = g.P()
    mp = g.node('ShaderNodeMapping'); g.put(mp.inputs['Vector'], P)
    mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(32))
    mp.inputs['Scale'].default_value = (1.0, 2.4, 1.0)
    h1 = g.noise(mp.outputs[0], 2.2 * scale, 3.0, 0.55, distortion=0.4)
    h2 = g.noise(P, 9.0 * scale, 2.0, 0.5)
    h = g.add(h1, g.mul(h2, 0.3))
    return h, g.bump(h, strength=strength, distance=0.012)


def r_water(m, ctx, absorb=(0.42, 0.85, 0.93), density=1.0, chop=1.0, basin=False):
    g, p, out = M.fresh(m)
    if basin:
        # churned where the streams land (u = ft out from the falls), calming toward the far wall
        u, _, _ = g.sep(_uv(g))
        near = g.maprange(u, 0.1, 1.6, 1.0, 0.0, smooth=True)
        h, _ = _chop(g, 1.6, 1.0)
        boil = g.noise(g.vmath('SCALE', g.P(), scale=1.0), 22.0, 3.0, 0.6)
        h = g.add(g.mul(h, 0.7), g.mul(boil, g.mul(near, 1.4)))
        nrm = g.bump(h, strength=1.0, distance=0.01)
    else:
        _, nrm = _chop(g, 1.0, chop)
    M.finish(g, p, color=(1.0, 1.0, 1.0), rough=0.0, normal=nrm, ior=1.333, spec=0.5)
    p.inputs['Transmission Weight'].default_value = 1.0
    vol = g.node('ShaderNodeVolumeAbsorption')
    g.put(vol.inputs['Color'], absorb); vol.inputs['Density'].default_value = density
    g.L.new(vol.outputs[0], out.inputs['Volume'])


def _caustics(g, strength=1.0):
    """A bright web like sunlight focused by ripples: two warped Voronoi edge layers, sharpened."""
    P = g.P()
    warp = g.noise(P, 1.1, 2.0, 0.5, out='Color')
    Pw = g.vmath('ADD', P, g.vmath('SCALE', g.vmath('SUBTRACT', warp, (0.5, 0.5, 0.5)), scale=0.35))
    def web(scale, w):
        e = g.voronoi(Pw, scale, out='Distance', feature='DISTANCE_TO_EDGE')
        k = g.maprange(e, 0.0, w, 1.0, 0.0, smooth=True)
        return g.mul(k, k)
    c = g.math('MAXIMUM', web(2.3, 0.07), g.mul(web(3.7, 0.05), 0.7))
    _, _, nz = g.sep(g.Nrm())
    up = g.maprange(nz, 0.2, 0.9, 0.3, 1.0)
    return g.add(0.9, g.mul(c, g.mul(up, 0.55 * strength)))


def r_plaster(m, ctx):
    g, p, _ = M.fresh(m)
    uv = M.box_uv(g, 1.0, 1.0)
    ph = M.photo(g, 'pool_plaster_white', uv, target='#d3e4e3', sat=0.6, contrast=0.8, bump=0.4, bump_dist=0.001, rough=(0.4, 0.6))
    c = M.mottle(g, ph['color'], 2.0, 0.05)
    k = _caustics(g)
    c = g.mix(1.0, c, g.comb(k, k, k), 'MULTIPLY')
    M.finish(g, p, color=c, rough=ph.get('rough', 0.5), normal=ph.get('normal'), spec=0.5)


def r_tile(m, ctx):
    """6" glass tile, three blues at random, 1/8" grout; UV in feet (u along the face, v height)."""
    g, p, _ = M.fresh(m)
    u, v, _ = g.sep(_uv(g))
    tu, tv = g.math('DIVIDE', u, 0.5), g.math('DIVIDE', v, 0.5)
    cell = g.comb(g.math('FLOOR', tu), g.math('FLOOR', tv), 0.37)
    rnd = g.white(cell)
    rnd2 = g.white(g.vmath('ADD', cell, (5.1, 2.3, 0.0)))
    ramp = g.node('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
    els = ramp.color_ramp.elements
    els[0].position = 0.0; els[0].color = M.lin('#2c5872')
    els[1].position = 0.42; els[1].color = M.lin('#3d6f8a')
    e3 = els.new(0.78); e3.color = M.lin('#5f9fb5')
    g.put(ramp.inputs['Fac'], rnd)
    col = g.hsv(ramp.outputs['Color'], h=g.maprange(rnd2, 0.0, 1.0, 0.49, 0.51), v=g.maprange(rnd2, 0.0, 1.0, 0.85, 1.12))
    # inside each tile: the glass's depth (lighter centre, mottled)
    fu = g.math('ABSOLUTE', g.sub(g.math('FRACT', tu), 0.5)); fv = g.math('ABSOLUTE', g.sub(g.math('FRACT', tv), 0.5))
    edge = g.math('MAXIMUM', fu, fv)
    mott = g.noise(g.vmath('SCALE', g.P(), scale=1.0), 30.0, 3.0, 0.6)
    col = g.mix(g.maprange(mott, 0.3, 0.7, 0.0, 0.25), col, g.mix(1.0, col, (1.35, 1.35, 1.35), 'MULTIPLY'))
    grout = g.maprange(edge, 0.478, 0.49, 0.0, 1.0)
    col = g.mix(grout, col, M.lin('#b9bcb4'))
    pillow = g.sub(1.0, g.math('POWER', g.mul(edge, 2.0), 6.0))
    h = g.mul(pillow, g.sub(1.0, grout))
    nrm = g.bump(h, strength=0.5, distance=0.002)
    M.finish(g, p, color=col, rough=g.mixf(grout, 0.05, 0.8), normal=nrm, spec=0.6, coat=g.sub(1.0, grout), coat_rough=0.02)


def _color_attr(m):
    for o in bpy.data.objects:
        if o.type == 'MESH' and any(s is m for s in o.data.materials):
            ca = o.data.color_attributes
            return ca[0].name if len(ca) else None
    return None


def r_coping(m, ctx, wet=False):
    g, p, _ = M.fresh(m)
    uv = M.box_uv(g, 1.1, 1.1)
    ph = M.photo(g, 'travertine_honed', uv, target='#d2c09d', sat=0.85, contrast=0.85, bump=0.5, bump_dist=0.0012, rough=(0.5, 0.75))
    c = ph['color']
    an = _color_attr(m)
    if an:                                             # per-piece tint (src/pool.js puts it in the colour)
        t = g.attr(an, 'Color')
        c = g.mix(1.0, c, t, 'MULTIPLY')
    c = M.mottle(g, c, 1.5, 0.04)
    if wet:
        c = g.mix(1.0, c, (0.55, 0.57, 0.58), 'MULTIPLY')
        M.finish(g, p, color=c, rough=0.06, normal=ph.get('normal'), spec=0.5, coat=1.0, coat_rough=0.03)
    else:
        c = M.grime(g, c, 0.2, 0.15, '#8a7c66')
        M.finish(g, p, color=c, rough=ph.get('rough', 0.6), normal=ph.get('normal'), spec=0.5)


def r_wet_stone(m, ctx):
    """The garden-wall stone behind the falls, wet: whatever recipe 'ashlar' has, darker and glossy."""
    fn = M.RECIPES.get('ashlar')
    if fn: fn(m, ctx)
    g = M.G(m.node_tree)
    for p in [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']:
        bc = p.inputs['Base Color']
        src = bc.links[0].from_socket if bc.links else tuple(bc.default_value)
        if bc.links: m.node_tree.links.remove(bc.links[0])
        g.put(bc, g.mix(1.0, src, (0.55, 0.57, 0.58), 'MULTIPLY'))
        for l in list(p.inputs['Roughness'].links): m.node_tree.links.remove(l)
        p.inputs['Roughness'].default_value = 0.12
        p.inputs['Coat Weight'].default_value = 0.8
        p.inputs['Coat Roughness'].default_value = 0.04


def r_streamer(m, ctx):
    g, p, out = M.fresh(m)
    uvx, uvy, _ = g.sep(_uv(g))                      # x: 0 at the lip .. 1 at the basin; y: around the stream
    an = _color_attr(m)
    seed = g.sep(g.attr(an, 'Color'))[0] if an else 0.3
    streak = g.noise(g.comb(g.mul(seed, 37.0), g.mul(uvx, 3.0), g.mul(uvy, 0.7)), 2.0, 4.0, 0.6)
    air = g.mul(g.maprange(uvx, 0.08, 0.95, 0.0, 0.85, smooth=True), g.maprange(streak, 0.35, 0.7, 0.25, 1.0))
    nrm = g.bump(g.noise(g.comb(g.mul(seed, 11.0), g.mul(uvx, 14.0), g.mul(uvy, 2.0)), 3.0, 3.0, 0.6), strength=0.35, distance=0.003)
    M.finish(g, p, color=(0.92, 0.99, 1.0), rough=0.02, normal=nrm, ior=1.333, spec=0.5)
    p.inputs['Transmission Weight'].default_value = 1.0
    foam = g.node('ShaderNodeBsdfPrincipled')
    M.finish(g, foam, color=(0.93, 0.97, 0.98), rough=0.35, normal=nrm, spec=0.5)
    foam.inputs['Subsurface Weight'].default_value = 0.6
    foam.inputs['Subsurface Radius'].default_value = (0.01, 0.012, 0.014)
    foam.inputs['Transmission Weight'].default_value = 0.4
    mx = g.node('ShaderNodeMixShader'); g.put(mx.inputs[0], g.mul(air, 0.6))
    g.L.new(p.outputs[0], mx.inputs[1]); g.L.new(foam.outputs[0], mx.inputs[2])
    g.L.new(mx.outputs[0], out.inputs['Surface'])


def r_foam(m, ctx):
    g, p, _ = M.fresh(m)
    u, _, _ = g.sep(_uv(g))                          # ft out from the falls face
    near = g.maprange(u, 0.08, 0.85, 1.0, 0.0, smooth=True)
    P = g.P()
    n1 = g.noise(P, 14.0, 4.0, 0.65, distortion=0.6)
    n2 = g.voronoi(P, 55.0, out='Distance', feature='F1')
    a = g.mul(g.maprange(g.sub(n1, g.mul(n2, 0.4)), 0.32, 0.5, 0.0, 1.0), near)
    M.finish(g, p, color=(0.94, 0.97, 0.97), rough=0.3, spec=0.5)
    p.inputs['Subsurface Weight'].default_value = 0.5
    p.inputs['Subsurface Radius'].default_value = (0.01, 0.012, 0.014)
    g.put(p.inputs['Alpha'], g.mul(a, 0.9))
    try: m.blend_method = 'HASHED'
    except Exception: pass


def r_jet(m, ctx):
    g, p, _ = M.fresh(m)
    M.finish(g, p, color=(0.82, 0.83, 0.84), rough=0.16, metallic=1.0)


def r_lens(m, ctx):
    g, p, _ = M.fresh(m)
    M.finish(g, p, color=(0.9, 0.93, 0.93), rough=0.18, spec=0.5)
    if ctx.get('night'):
        p.inputs['Emission Color'].default_value = (1.0, 0.95, 0.86, 1)
        p.inputs['Emission Strength'].default_value = 25.0


RECIPES = {
    # absorption per metre = density x (1 - colour): ~(0.9, 0.3, 0.22)/m, red gone first -> turquoise
    'pool water': lambda m, c: r_water(m, c, (0.4, 0.8, 0.85), 1.5, 1.4),
    'spa water': lambda m, c: r_water(m, c, (0.4, 0.78, 0.84), 1.9, 0.8),
    'basin water': lambda m, c: r_water(m, c, (0.42, 0.82, 0.84), 1.5, 1.0, basin=True),
    'pool plaster': r_plaster, 'waterline tile': r_tile,
    'pool coping': r_coping, 'weir cap': lambda m, c: r_coping(m, c, wet=True),
    'falls face': r_wet_stone, 'falls streamer': r_streamer, 'falls foam': r_foam,
    'spa jet': r_jet, 'pool light lens': r_lens,
}
SHADOWLESS = set(WATER) | {'falls streamer', 'falls foam'}


def apply(meta=None, night=False, log=print):
    try:
        ctx = {'night': night, 'meta': meta}
        done = []
        for m in list(bpy.data.materials):
            key = M.base_name(m.name)
            fn = RECIPES.get(key)
            if not fn or not m.node_tree: continue
            try:
                fn(m, ctx); m['nh_done'] = 1; done.append(key)
            except Exception as e:
                import traceback; traceback.print_exc()
                log(f'water: {m.name} failed: {e}')
        n = 0
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.data.materials and all(s and M.base_name(s.name) in SHADOWLESS for s in o.data.materials):
                o.visible_shadow = False; n += 1
        log(f'water: {len(done)} materials ({", ".join(sorted(set(done)))}), {n} shadowless objects')
    except Exception:
        import traceback; traceback.print_exc()
