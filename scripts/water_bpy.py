"""Pool, spa and vanishing-edge water for the Cycles renders (geometry: src/pool.js).

    import water_bpy; water_bpy.apply(meta=meta, night=False, log=print)     # after materials_bpy.apply()

Every material src/pool.js names is (re)built here:
  pool / spa / basin water   closed bodies: an IOR 1.333 surface with 2-5 mm ripples over Volume Absorption, so
                             the colour comes from the light path (turquoise over the steps, deeper blue-teal
                             over the 4.5 ft floor); shadow rays cross it as a Transparent BSDF tinted by a
                             caustic web (Cycles caustics are too slow), so the sun reaching the shell is both
                             absorbed by depth and patterned; the basin is churned where the falls land
  pool plaster               white marcite (the caustic light arrives through the water surface)
  waterline tile             6" blue glass tiles in three blues, 1/8" grout, glossy and slightly pillowed
  pool coping / weir cap     honed sandstone in 2-3 ft pieces (per-piece tint), bullnosed; the weir cap wet
  falls sheet                clear water slab (IOR 1.33, rough 0.02-0.05) refracting the wet stone under an
                             aerated veil thickening from the lip to the foot, in soft vertical bands (r5)
  falls face                 the garden-wall stone, wet: albedo x0.6, roughness 0.15, glossy film
  falls streamer             water IOR 1.33, glassy at the lip, whitening with entrained air as it falls
  falls foam                 aeration where the streams land (white, broken by noise, fading out)
  falls spray                mist curtains on the impact line (soft white puffs fading upward)
  spa jet, pool light lens   stainless fittings; light lenses glow at night
"""
import math
import bpy
import materials_bpy as M

WATER = ('pool water', 'spa water', 'basin water')


def _uv(g):
    return g.texco().outputs['UV']


def _surface(g, scale=1.0, amp=1.0):
    """Height of a water surface in metres (world space; the bump node takes it at distance 1): wind chop
    (~0.5 m, stretched across the wind, ~+-2.5 mm), ripples (~15 cm, ~+-2 mm) and capillary wrinkles (~5 cm,
    <1 mm) -- an RMS slope of ~0.06, a pool with the pump running, so the surface breaks the reflected sky,
    house and palms into ripples instead of mirroring one flat tint."""
    P = g.P()
    mp = g.node('ShaderNodeMapping'); g.put(mp.inputs['Vector'], P)
    mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(32))
    mp.inputs['Scale'].default_value = (1.0, 2.4, 1.0)
    h1 = g.noise(mp.outputs[0], 1.6 * scale, 2.0, 0.45, distortion=0.3)
    h2 = g.noise(P, 6.0 * scale, 1.5, 0.5)
    h3 = g.noise(P, 18.0 * scale, 1.0, 0.5)
    return g.add(g.mul(h1, 0.02 * amp), g.add(g.mul(h2, 0.016 * amp), g.mul(h3, 0.004 * amp)))


def _caustics(g, scale=4.5, lo=0.7, gain=1.1):
    """Sunlight focused by the ripples: two warped Voronoi edge webs (cells ~15-25 cm), sharpened; returns
    lo .. lo + gain (mean ~0.9), used as the water surface's transmittance for shadow rays, so the web lands
    only where the sun reaches through the water (floor, steps, walls), projected along the sun direction."""
    P = g.P()
    warp = g.noise(P, 0.45 * scale, 2.0, 0.5, out='Color')
    Pw = g.vmath('ADD', P, g.vmath('SCALE', g.vmath('SUBTRACT', warp, (0.5, 0.5, 0.5)), scale=0.7 / scale))
    def web(s, w):
        e = g.voronoi(Pw, s, out='Distance', feature='DISTANCE_TO_EDGE')
        k = g.maprange(e, 0.0, w, 1.0, 0.0, smooth=True)
        return g.mul(k, k)
    c = g.math('MAXIMUM', web(scale, 0.09), g.mul(web(1.63 * scale, 0.07), 0.7))
    return g.add(lo, g.mul(c, gain))


def r_water(m, ctx, absorb=(0.4, 0.8, 0.86), density=1.0, amp=1.0, basin=False, caustic=1.0, cscale=4.5):
    """Closed water body: a rippled IOR 1.333 surface (Fresnel: mostly sky at grazing views, the shell seen
    through it from above) over Volume Absorption. Shadow rays pass the surface as a Transparent BSDF tinted by
    the caustic web, and so cross the volume too: sunlight reaching the floor is absorbed on the way down as
    well as on the way back up, so the 4.5 ft floor runs well darker and bluer than the steps and bench."""
    g, p, out = M.fresh(m)
    h = _surface(g, 1.0, amp)
    if basin:
        # u = ft out from the line where the sheet lands (negative between it and the wall): boiling on the
        # line, wavefronts parallel to it running out (~2" apart, bent by noise), calm by the far coping
        # r5 (critique-preview4-back #1): calmer away from the line (amp 0.9, so the falls and wall reflect), ripple
        # rings ~2" apart running out from the impact line and dying out by ~1.5 ft
        u, v, _ = g.sep(_uv(g))
        near = g.maprange(u, 0.0, 1.6, 1.0, 0.12, smooth=True)
        boil = g.noise(g.P(), 22.0, 3.0, 0.6)
        line = g.maprange(g.math('ABSOLUTE', u), 0.05, 0.35, 1.0, 0.0, smooth=True)
        bend = g.noise(g.comb(g.mul(v, 1.4), g.mul(u, 0.6), 3.3), 1.0, 2.0, 0.5)
        wave = g.math('SINE', g.add(g.mul(u, 2 * math.pi / 0.17), g.mul(bend, 7.0)))
        wave2 = g.math('SINE', g.add(g.mul(u, 2 * math.pi / 0.41), g.mul(bend, 4.0)))   # longer swell behind them
        h = g.add(h, g.add(g.mul(boil, g.mul(line, 0.02)), g.mul(g.add(wave, g.mul(wave2, 0.8)), g.mul(near, 0.0045))))
    nrm = g.bump(h, strength=1.0, distance=1.0)
    M.finish(g, p, color=(1.0, 1.0, 1.0), rough=0.0, normal=nrm, ior=1.333, spec=0.5)
    p.inputs['Transmission Weight'].default_value = 1.0
    k = _caustics(g, cscale, 1.0 - 0.3 * caustic, 1.1 * caustic)
    tr = g.node('ShaderNodeBsdfTransparent'); g.put(tr.inputs['Color'], g.comb(k, k, k))
    lp = g.node('ShaderNodeLightPath')
    mx = g.node('ShaderNodeMixShader'); g.L.new(lp.outputs['Is Shadow Ray'], mx.inputs[0])
    g.L.new(p.outputs[0], mx.inputs[1]); g.L.new(tr.outputs[0], mx.inputs[2])
    g.L.new(mx.outputs[0], out.inputs['Surface'])
    vol = g.node('ShaderNodeVolumeAbsorption')
    g.put(vol.inputs['Color'], absorb); vol.inputs['Density'].default_value = density
    g.L.new(vol.outputs[0], out.inputs['Volume'])


def r_plaster(m, ctx):
    """White marcite; the caustic web is not painted on: it comes in with the sun through the water surface."""
    g, p, _ = M.fresh(m)
    uv = M.box_uv(g, 1.0, 1.0)
    ph = M.photo(g, 'pool_plaster_white', uv, target='#d3e4e3', sat=0.6, contrast=0.8, bump=0.4, bump_dist=0.001, rough=(0.4, 0.6))
    c = M.mottle(g, ph['color'], 2.0, 0.05)
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
        r = ph.get('rough', 0.6)
        bb = _basin_bounds()
        if bb:   # r5 (critique-preview4-back #10): the basin's low coping damp along its water side, in patches
            (bx0, _, _), (_, _, bzt) = bb
            px, _, pz = g.sep(g.P())
            low = g.maprange(pz, bzt + 0.45, bzt + 0.3, 0.0, 1.0)
            edge = g.maprange(px, bx0 - 0.28, bx0 + 0.03, 0.0, 1.0, smooth=True)
            rag = g.maprange(g.noise(g.vmath('SCALE', g.P(), scale=5.0), 1.0, 3.0, 0.6), 0.3, 0.7, 0.45, 1.25)
            d = g.math('MINIMUM', g.mul(g.mul(low, edge), rag), 1.0)
            c = g.mix(g.mul(d, 0.8), c, g.mix(1.0, c, (0.66, 0.65, 0.63), 'MULTIPLY'))
            r = g.sub(r, g.mul(d, 0.3))
        M.finish(g, p, color=c, rough=r, normal=ph.get('normal'), spec=0.5)


def _basin_bounds():
    """World bounds ((x, y, z) min, max) of the catch-basin water, or None."""
    from mathutils import Vector
    bb = None
    for o in bpy.data.objects:
        if o.type == 'MESH' and any(s and M.base_name(s.name) == 'basin water' for s in o.data.materials):
            vs = [o.matrix_world @ Vector(c) for c in o.bound_box]
            lo, hi = [min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]
            bb = (lo, hi) if bb is None else ([min(a, b) for a, b in zip(bb[0], lo)], [max(a, b) for a, b in zip(bb[1], hi)])
    return bb


def r_wet_stone(m, ctx):
    """The garden-wall stone behind the falls, soaked: whatever recipe 'ashlar' has, albedo x~0.6 (a touch
    deeper, a touch cooler from the film), roughness 0.15 under a glossy water film that runs in faint vertical rivulets."""
    fn = M.RECIPES.get('ashlar')
    if fn: fn(m, ctx)
    g = M.G(m.node_tree)
    P = g.P()
    _, _, pz = g.sep(P)
    px, py, _ = g.sep(P)
    film = g.noise(g.comb(g.mul(g.add(px, py), 9.0), g.mul(pz, 1.2), 0.7), 1.0, 3.0, 0.55)   # streaks run down
    for p in [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']:
        bc = p.inputs['Base Color']
        src = bc.links[0].from_socket if bc.links else tuple(bc.default_value)
        if bc.links: m.node_tree.links.remove(bc.links[0])
        k = g.maprange(film, 0.3, 0.7, 0.52, 0.62)                    # x~0.6, wet stone a touch more saturated
        g.put(bc, g.hsv(g.mix(1.0, src, g.comb(k, g.mul(k, 1.0), g.mul(k, 1.04)), 'MULTIPLY'), s=1.15))
        for l in list(p.inputs['Roughness'].links): m.node_tree.links.remove(l)
        p.inputs['Roughness'].default_value = 0.15
        p.inputs['Coat Weight'].default_value = 1.0
        g.put(p.inputs['Coat Roughness'], g.maprange(film, 0.3, 0.7, 0.02, 0.06))
        g.put(p.inputs['Coat Normal'], g.bump(film, strength=0.15, distance=0.002))


def r_sheet(m, ctx):
    """The vanishing-edge sheet (src/pool.js): one closed slab, uv x = fall fraction f (0 on the cap .. 1 in
    the basin), y = ft along the weir. One continuous clear sheet (IOR 1.33, roughness 0.02-0.06) refracting
    the wet stone behind it: glassy at the lip, then a ropy relief that grows down the fall -- low strands ~4"
    across, fine ribs ~1.2" across (~5 deg tilts that pick up sky in thin vertical lines) and faint waves.
    r4 broke the lower ~30% into strands and slits; r5 replaced that with a continuous aerated veil (below).
    A whiter foot merges into the foam band at the impact line; a few thin white lines run the full height
    from disturbances on the lip, as on the brochure's falls."""
    g, p, out = M.fresh(m)
    f, v, _ = g.sep(_uv(g))
    brk = g.maprange(g.noise(g.comb(g.mul(v, 0.45), 0.0, 7.7), 1.0, 2.0, 0.5), 0.35, 0.65, 0.64, 0.8)
    fb = g.sub(f, brk)                                                             # > 0 below the break
    lo = g.maprange(fb, 0.0, 0.2, 0.0, 1.0, smooth=True)
    s1 = g.noise(g.comb(g.mul(v, 3.2), g.mul(f, 0.5), 0.3), 1.0, 2.0, 0.5)         # strands down the fall
    s2 = g.noise(g.comb(g.mul(v, 0.9), g.mul(f, 9.0), 4.1), 1.0, 1.0, 0.5)         # waves travelling down it
    rib = g.noise(g.comb(g.mul(v, 10.0), g.mul(f, 1.2), 2.2), 1.0, 2.0, 0.5)       # fine ribs
    h = g.add(g.mul(s1, 0.026), g.mul(s2, 0.012))
    h = g.add(h, g.mul(rib, g.maprange(f, 0.15, 0.9, 0.0, 0.014)))
    h = g.mul(h, g.maprange(f, 0.0, 0.45, 0.12, 1.0, smooth=True))
    nrm = g.bump(h, strength=1.0, distance=1.0)
    M.finish(g, p, color=(0.96, 0.99, 1.0), rough=g.maprange(f, 0.2, 1.0, 0.02, 0.06), normal=nrm, ior=1.33, spec=0.5)
    p.inputs['Transmission Weight'].default_value = 1.0
    # r5 (critique-preview4-back #1: a sparse bead curtain of white hairlines over dry stone): one continuous
    # visible sheet -- an aerated veil over the clear water, its cover rising down the fall (see below) to the
    # foot, in soft vertical bands (broad ~6" and fine ~2", +-20%), greyer-aqua near the lip and whiter below;
    # the full-height white lines halved in count and contrast; no slits (the sheet never opens onto dry stone)
    band = g.noise(g.comb(g.mul(v, 2.2), g.mul(f, 0.35), 6.1), 1.0, 2.0, 0.5)
    fine = g.noise(g.comb(g.mul(v, 7.0), g.mul(f, 0.6), 2.7), 1.0, 3.0, 0.55)
    # (the r5 test at 0.3 -> 0.7 with a 0.25-transmission veil read as a uniform white panel, sRGB ~215 +-5:
    # the veil now 0.16 -> 0.5, greyer and more transmissive, in stronger bands, so the dark wet wall shows through)
    mod = g.maprange(g.add(g.mul(band, 0.6), g.mul(fine, 0.4)), 0.3, 0.7, 0.5, 1.5)
    # (lead, r5 check render: still a frosted white panel next to p5's see-through sheet: veil halved near the lip
    # and thinned toward the foot so the wet stone reads through; the white lines and the foot stay)
    air = g.mul(g.maprange(f, 0.0, 1.0, 0.07, 0.32), mod)
    air = g.add(air, g.mul(lo, 0.06))                                              # a little more air below the break
    line = g.maprange(g.noise(g.comb(g.mul(v, 14.0), g.mul(f, 0.25), 9.1), 1.0, 2.0, 0.5), 0.62, 0.68, 0.0, 1.0, smooth=True)
    air = g.add(air, g.mul(line, g.maprange(f, 0.03, 0.45, 0.0, 0.16)))
    air = g.math('MINIMUM', g.add(air, g.maprange(f, 0.9, 1.0, 0.0, 0.2, smooth=True)), 0.9)
    foam = g.node('ShaderNodeBsdfPrincipled')
    vc = g.mix(g.maprange(f, 0.0, 0.7), (0.6, 0.7, 0.73), (0.82, 0.87, 0.88))
    M.finish(g, foam, color=vc, rough=0.3, normal=nrm, spec=0.5)
    foam.inputs['Subsurface Weight'].default_value = 0.6
    foam.inputs['Subsurface Radius'].default_value = (0.01, 0.012, 0.014)
    foam.inputs['Transmission Weight'].default_value = 0.45
    mx = g.node('ShaderNodeMixShader'); g.put(mx.inputs[0], air)
    g.L.new(p.outputs[0], mx.inputs[1]); g.L.new(foam.outputs[0], mx.inputs[2])
    # shadow rays pass the sheet as a transparent film dimmed by its aeration (the wall behind sits in a
    # light, banded half-shade instead of full sun; the clear water itself would be opaque to shadow rays)
    k = g.sub(1.0, g.mul(air, 0.55))
    trs = g.node('ShaderNodeBsdfTransparent'); g.put(trs.inputs['Color'], g.comb(k, k, k))
    lp = g.node('ShaderNodeLightPath')
    sh = g.node('ShaderNodeMixShader'); g.L.new(lp.outputs['Is Shadow Ray'], sh.inputs[0])
    g.L.new(mx.outputs[0], sh.inputs[1]); g.L.new(trs.outputs[0], sh.inputs[2])
    g.L.new(sh.outputs[0], out.inputs['Surface'])


def r_spray(m, ctx):
    """Mist at the impact line (src/pool.js: two thin curtains, uv x = height fraction, y = ft along): soft
    white puffs, densest on the water and gone by the top, broken up along the weir and by fine droplets."""
    g, p, _ = M.fresh(m)
    hf, v, _ = g.sep(_uv(g))
    puff = g.noise(g.P(), 9.0, 3.0, 0.55, distortion=0.3)                         # rounded puffs ~4-6" (world, isotropic)
    drop = g.noise(g.P(), 60.0, 3.0, 0.6)
    fade = g.math('POWER', g.math('MAXIMUM', g.sub(1.0, hf), 0.0), 2.2)
    a = g.mul(g.mul(fade, g.maprange(puff, 0.35, 0.65, 0.15, 1.0, smooth=True)), g.maprange(drop, 0.3, 0.7, 0.6, 1.0))
    M.finish(g, p, color=(0.93, 0.95, 0.96), rough=0.5, spec=0.3)
    p.inputs['Subsurface Weight'].default_value = 0.6
    p.inputs['Subsurface Radius'].default_value = (0.01, 0.012, 0.014)
    g.put(p.inputs['Alpha'], g.mul(a, 0.3))
    try: m.blend_method = 'HASHED'
    except Exception: pass


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
    """The aerated line where the sheet lands (src/pool.js): u = ft out from the impact line (negative between
    the sheet and the wall), colour = the layer's opacity (surface foam 1, the bubble plume under it 0.35).
    A dense aerated band 5-10 cm wide on the impact (white core ~2" either side, broken edges), churned white
    behind the sheet, patches trailing out ~9"; a bubbly relief so it catches the light."""
    g, p, _ = M.fresh(m)
    u, _, _ = g.sep(_uv(g))
    P = g.P()
    n1 = g.noise(P, 14.0, 4.0, 0.65, distortion=0.6)
    n2 = g.voronoi(P, 55.0, out='Distance', feature='F1')
    patchy = g.maprange(g.sub(n1, g.mul(n2, 0.4)), 0.32, 0.5, 0.0, 1.0)
    line = g.mul(g.maprange(g.math('ABSOLUTE', g.sub(u, 0.03)), 0.09, 0.2, 1.0, 0.0, smooth=True), g.maprange(n1, 0.28, 0.48, 0.65, 1.0))
    behind = g.mul(g.maprange(u, -0.05, -0.15, 0.0, 0.85), g.maprange(n1, 0.35, 0.55, 0.5, 1.0))
    trail = g.mul(g.maprange(u, 0.15, 0.75, 1.0, 0.0, smooth=True), patchy)
    a = g.math('MAXIMUM', line, g.math('MAXIMUM', behind, trail))
    an = _color_attr(m)
    if an: a = g.mul(a, g.sep(g.attr(an, 'Color'))[0])
    bub = g.bump(g.add(g.mul(n1, 0.002), g.mul(n2, 0.0015)), strength=1.0, distance=1.0)
    M.finish(g, p, color=(0.95, 0.97, 0.97), rough=0.3, normal=bub, spec=0.5)
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
    # absorption per metre = density x (1 - colour): ~(1.0, 0.32, 0.17)/m, red gone first -> turquoise over
    # the steps, blue over the 4.5 ft floor (sun ~2 m down + ~2 m back up there): the floor ~25-30% darker
    'pool water': lambda m, c: r_water(m, c, (0.3, 0.78, 0.88), 1.45, 1.0),
    'spa water': lambda m, c: r_water(m, c, (0.4, 0.78, 0.84), 1.6, 0.6),
    # the basin: r5 (critique-preview4-back #1: an opaque flat pale-mint slab) the pool's own water (same blue-teal
    # absorption, ~2x denser: the 1.5 ft basin over white plaster read pale and flat, now teal with depth), the chop
    # calmed so it reflects the falls and wall, ripple rings off the impact line
    'basin water': lambda m, c: r_water(m, c, (0.3, 0.78, 0.88), 3.2, 0.9, basin=True, caustic=0.9, cscale=6.0),
    'pool plaster': r_plaster, 'waterline tile': r_tile,
    'pool coping': r_coping, 'weir cap': lambda m, c: r_coping(m, c, wet=True),
    'falls face': r_wet_stone, 'falls sheet': r_sheet, 'falls streamer': r_streamer, 'falls foam': r_foam, 'falls spray': r_spray,
    'spa jet': r_jet, 'pool light lens': r_lens,
}
# the water bodies stay shadow-visible: their shaders turn transparent (caustic-tinted) for shadow rays, which
# then cross the absorbing volume; the thin falls parts are simply skipped by shadow rays
SHADOWLESS = {'falls streamer', 'falls foam', 'falls spray'}     # r5: the sheet casts its own (aeration-dimmed) shadow


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
        n = nw = 0
        for o in bpy.data.objects:
            if o.type != 'MESH' or not o.data.materials: continue
            keys = [M.base_name(s.name) if s else None for s in o.data.materials]
            if all(k in SHADOWLESS for k in keys):
                o.visible_shadow = False; n += 1
            elif all(k in WATER for k in keys):
                o.visible_shadow = True; nw += 1
        log(f'water: {len(done)} materials ({", ".join(sorted(set(done)))}), {n} shadowless objects, {nw} water bodies passing caustic-tinted shadow rays')
    except Exception:
        import traceback; traceback.print_exc()
