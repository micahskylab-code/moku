#!/usr/bin/env python3
"""Sun and moon over Kukui'ula for any date and time, in the walkthrough's world coordinates.

So the Blender renders can be lit for a real moment, the same way the three.js walkthrough is
(src/ephemeris.js, src/daylight.js):

    python3 scripts/sun_moon.py 2026-12-21T17:55            # HST when no zone is given
    python3 scripts/sun_moon.py 2026-06-21T19:20 --meta blender/nahiku-meta.json
    python3 scripts/sun_moon.py now
    python3 scripts/sun_moon.py --table 2026                # sunrise/sunset check, solstices and equinoxes

Prints JSON. Directions are unit vectors toward the body:
  dir_three    three.js world (y up; the frame of nahiku-meta.json 'views[*].sunDir'), so
               blender_render.set_sun(result['sun']['dir_three']) lights the scene for that moment
  dir_blender  the same in Blender's frame (x, -z, y), as blender_render.b() converts
True north comes from nahiku-meta.json night.north (the site plan's north on our plan), default
[0.9080, -0.4191]. Uses astronomy-engine (pip install astronomy-engine, MIT) when available, else
the NOAA solar equations and a truncated Meeus lunar theory (sun ~0.01 deg, moon ~0.3 deg).
"""
import argparse, datetime as dt, json, math, os, sys

LAT, LON, ELEV_M = 21.886, -159.474, 40.0
HST = dt.timezone(dt.timedelta(hours=-10), 'HST')
NORTH = [0.9079593845004517, -0.4190581774617469]
D = math.pi / 180

try:
    import astronomy as A
except Exception:  # pragma: no cover
    A = None


# ---------------------------------------------------------------- time
def parse_when(s):
    if s in (None, 'now'):
        return dt.datetime.now(dt.timezone.utc)
    t = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    if t.tzinfo is None:
        t = t.replace(tzinfo=HST)
    return t.astimezone(dt.timezone.utc)


def hst(t):
    return t.astimezone(HST).strftime('%Y-%m-%d %H:%M HST') if t else None


# ---------------------------------------------------------------- world directions
def world_dir(alt, az, north=NORTH):
    """altitude/azimuth (deg, azimuth from true north through east) -> three.js world unit vector"""
    nx, nz = north
    ex, ez = -nz, nx                        # east = north turned clockwise, seen from above
    ca = math.cos(alt * D)
    cn, ce = math.cos(az * D) * ca, math.sin(az * D) * ca
    return [cn * nx + ce * ex, math.sin(alt * D), cn * nz + ce * ez]


def to_blender(v):
    return [v[0], -v[2], v[1]]


# ---------------------------------------------------------------- the air (as src/atmosphere.js)
RE, RT, H0 = 6360.0, 6420.0, 0.045
BR = [5.802e-3, 13.558e-3, 33.1e-3]
BO = [2.4e-3, 1.95e-3, 0.09e-3]
HR, HM, ANG = 8.0, 1.2, [0.92, 1.0, 1.09]


def transmittance(alt, aod=0.05, h=H0):
    """direct light colour (RGB, 0..1) after the atmosphere at apparent altitude alt (deg)"""
    r, mu = RE + h, math.sin(max(alt, -0.27) * D)
    d = r * r * (mu * mu - 1) + RE * RE
    if mu < 0 and d >= 0:
        return [0.0, 0.0, 0.0]
    L = -r * mu + math.sqrt(r * r * (mu * mu - 1) + RT * RT)
    n, dR, dM, dO = 64, 0.0, 0.0, 0.0
    for i in range(n):
        t = (i + 0.5) * L / n
        hh = math.sqrt(r * r + t * t + 2 * r * mu * t) - RE
        dR += math.exp(-hh / HR) * L / n
        dM += math.exp(-hh / HM) * L / n
        dO += max(0.0, 1 - abs(hh - 25) / 15) * L / n
    mie = aod / HM
    return [math.exp(-(BR[c] * dR + mie * ANG[c] * dM + BO[c] * dO)) for c in range(3)]


# ---------------------------------------------------------------- ephemeris: astronomy-engine
PHASES = ['New moon', 'Waxing crescent', 'First quarter', 'Waxing gibbous', 'Full moon', 'Waning gibbous', 'Last quarter', 'Waning crescent']
PO = ['Hilo', 'Hoaka', 'Kū Kahi', 'Kū Lua', 'Kū Kolu', 'Kū Pau', 'ʻOle Kū Kahi', 'ʻOle Kū Lua', 'ʻOle Kū Kolu', 'ʻOle Pau',
      'Huna', 'Mohalu', 'Hua', 'Akua', 'Hoku', 'Māhealani', 'Kulu', 'Lāʻau Kū Kahi', 'Lāʻau Kū Lua', 'Lāʻau Pau',
      'ʻOle Kū Kahi', 'ʻOle Kū Lua', 'ʻOle Pau', 'Kāloa Kū Kahi', 'Kāloa Kū Lua', 'Kāloa Pau', 'Kāne', 'Lono', 'Mauli', 'Muku']


def ae_time(t):
    return A.Time.Make(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)


def ae_dt(at):
    return at.Utc().replace(tzinfo=dt.timezone.utc) if at else None


def positions_ae(t):
    obs, at = A.Observer(LAT, LON, ELEV_M), ae_time(t)
    out = {}
    for name, body in (('sun', A.Body.Sun), ('moon', A.Body.Moon)):
        eq = A.Equator(body, at, obs, True, True)
        hor = A.Horizon(at, obs, eq.ra, eq.dec, A.Refraction.Normal)
        out[name] = {'alt': hor.altitude, 'az': hor.azimuth, 'dist_au': eq.dist}
    ill = A.Illumination(A.Body.Moon, at)
    out['moon'].update(phase_deg=A.MoonPhase(at), fraction=ill.phase_fraction, mag=ill.mag)
    return out


def events_ae(t):
    obs = A.Observer(LAT, LON, ELEV_M)
    loc = t.astimezone(HST)
    m0 = dt.datetime(loc.year, loc.month, loc.day, tzinfo=HST).astimezone(dt.timezone.utc)
    s0, end = ae_time(m0), m0 + dt.timedelta(days=1)
    keep = lambda x: x if x and x < end else None
    rs = lambda body, d: keep(ae_dt(A.SearchRiseSet(body, obs, d, s0, 1.02)))
    alt = lambda d, a: keep(ae_dt(A.SearchAltitude(A.Body.Sun, obs, d, s0, 1.02, a)))
    return {'sunrise': rs(A.Body.Sun, A.Direction.Rise), 'sunset': rs(A.Body.Sun, A.Direction.Set),
            'golden_pm': [alt(A.Direction.Set, 6), alt(A.Direction.Set, -4)], 'golden_am': [alt(A.Direction.Rise, -4), alt(A.Direction.Rise, 6)],
            'civil_dusk': alt(A.Direction.Set, -6), 'moonrise': rs(A.Body.Moon, A.Direction.Rise), 'moonset': rs(A.Body.Moon, A.Direction.Set)}


# ---------------------------------------------------------------- ephemeris: NOAA sun + Meeus moon (fallback)
def jd(t):
    return t.timestamp() / 86400.0 + 2440587.5


def sun_radec(t):
    T = (jd(t) - 2451545.0) / 36525
    L0 = (280.46646 + T * (36000.76983 + T * 0.0003032)) % 360
    M = 357.52911 + T * (35999.05029 - 0.0001537 * T)
    C = math.sin(M * D) * (1.914602 - T * (0.004817 + 0.000014 * T)) + math.sin(2 * M * D) * (0.019993 - 0.000101 * T) + math.sin(3 * M * D) * 0.000289
    lam = L0 + C - 0.00569 - 0.00478 * math.sin((125.04 - 1934.136 * T) * D)
    eps = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60 + 0.00256 * math.cos((125.04 - 1934.136 * T) * D)
    ra = math.atan2(math.cos(eps * D) * math.sin(lam * D), math.cos(lam * D)) / D
    dec = math.asin(math.sin(eps * D) * math.sin(lam * D)) / D
    return ra % 360, dec, 1.0


def moon_radec(t):
    T = (jd(t) - 2451545.0) / 36525
    Lp = 218.3164477 + 481267.88123421 * T
    Dm = 297.8501921 + 445267.1114034 * T
    M = 357.5291092 + 35999.0502909 * T
    Mp = 134.9633964 + 477198.8675055 * T
    F = 93.2720950 + 483202.0175233 * T
    lon = Lp + 6.289 * math.sin(Mp * D) + 1.274 * math.sin((2 * Dm - Mp) * D) + 0.658 * math.sin(2 * Dm * D) + 0.214 * math.sin(2 * Mp * D) \
        - 0.186 * math.sin(M * D) - 0.114 * math.sin(2 * F * D) + 0.059 * math.sin((2 * Dm - 2 * Mp) * D) + 0.057 * math.sin((2 * Dm - M - Mp) * D) \
        + 0.053 * math.sin((2 * Dm + Mp) * D) + 0.046 * math.sin((2 * Dm - M) * D) - 0.041 * math.sin((M - Mp) * D)
    lat = 5.128 * math.sin(F * D) + 0.281 * math.sin((Mp + F) * D) + 0.278 * math.sin((Mp - F) * D) + 0.173 * math.sin((2 * Dm - F) * D)
    dist = 385000.56 - 20905.355 * math.cos(Mp * D) - 3699.111 * math.cos((2 * Dm - Mp) * D) - 2955.968 * math.cos(2 * Dm * D)
    eps = 23.439291 - 0.0130042 * T
    ra = math.atan2(math.sin(lon * D) * math.cos(eps * D) - math.tan(lat * D) * math.sin(eps * D), math.cos(lon * D)) / D
    dec = math.asin(math.sin(lat * D) * math.cos(eps * D) + math.cos(lat * D) * math.sin(eps * D) * math.sin(lon * D)) / D
    return ra % 360, dec, dist / 149597870.7


def to_horizon(t, ra, dec, dist_au=None):
    gmst = (280.46061837 + 360.98564736629 * (jd(t) - 2451545.0)) % 360
    H, p, d = (gmst + LON - ra) * D, LAT * D, dec * D
    alt = math.asin(math.sin(p) * math.sin(d) + math.cos(p) * math.cos(d) * math.cos(H)) / D
    az = math.atan2(-math.sin(H), math.tan(d) * math.cos(p) - math.sin(p) * math.cos(H)) / D % 360
    if dist_au and dist_au < 0.01:                               # the moon's parallax
        alt -= math.asin(6378.14 / (dist_au * 149597870.7)) / D * math.cos(alt * D)
    if alt > -1.5:                                               # Saemundsson refraction
        alt += 1.02 / math.tan((alt + 10.3 / (alt + 5.11)) * D) / 60
    return alt, az


def positions_fallback(t):
    sra, sdec, _ = sun_radec(t)
    mra, mdec, mdist = moon_radec(t)
    s_alt, s_az = to_horizon(t, sra, sdec)
    m_alt, m_az = to_horizon(t, mra, mdec, mdist)
    # elongation -> phase
    T = (jd(t) - 2451545.0) / 36525
    elong = math.acos(math.sin(sdec * D) * math.sin(mdec * D) + math.cos(sdec * D) * math.cos(mdec * D) * math.cos((sra - mra) * D)) / D
    i = 180 - elong
    frac = (1 + math.cos(i * D)) / 2
    lon_s = math.atan2(math.sin(sra * D), math.cos(sra * D))
    phase = (moon_ecl_lon(T) - sun_ecl_lon(T)) % 360
    mag = -12.73 + 0.026 * abs(i) + 4e-9 * i ** 4
    return {'sun': {'alt': s_alt, 'az': s_az, 'dist_au': 1.0},
            'moon': {'alt': m_alt, 'az': m_az, 'dist_au': mdist, 'phase_deg': phase, 'fraction': frac, 'mag': mag}}


def sun_ecl_lon(T):
    L0 = 280.46646 + 36000.76983 * T
    M = 357.52911 + 35999.05029 * T
    return (L0 + 1.914602 * math.sin(M * D) + 0.019993 * math.sin(2 * M * D)) % 360


def moon_ecl_lon(T):
    Lp, Dm, M, Mp = 218.3164477 + 481267.88123421 * T, 297.8501921 + 445267.1114034 * T, 357.5291092 + 35999.0502909 * T, 134.9633964 + 477198.8675055 * T
    return (Lp + 6.289 * math.sin(Mp * D) + 1.274 * math.sin((2 * Dm - Mp) * D) + 0.658 * math.sin(2 * Dm * D) + 0.214 * math.sin(2 * Mp * D) - 0.186 * math.sin(M * D)) % 360


def noaa_rise_set(day):
    """NOAA sunrise/sunset (sun centre at -0.833 deg) for an HST calendar date, iterated twice"""
    out = []
    for sign in (-1, +1):
        t = dt.datetime(day.year, day.month, day.day, 12, tzinfo=HST).astimezone(dt.timezone.utc)
        for _ in range(3):
            ra, dec, _ = sun_radec(t)
            cosH = (math.sin(-0.833 * D) - math.sin(LAT * D) * math.sin(dec * D)) / (math.cos(LAT * D) * math.cos(dec * D))
            H = math.acos(max(-1, min(1, cosH))) / D
            gmst = (280.46061837 + 360.98564736629 * (jd(t) - 2451545.0)) % 360
            ha_now = ((gmst + LON - ra + 180) % 360) - 180         # current hour angle
            t = t + dt.timedelta(hours=(sign * H - ha_now) / 15.04107)
        out.append(t)
    return out


def events_fallback(t):
    loc = t.astimezone(HST)
    rise, set_ = noaa_rise_set(loc)
    return {'sunrise': rise, 'sunset': set_, 'golden_pm': [None, None], 'golden_am': [None, None], 'civil_dusk': None, 'moonrise': None, 'moonset': None}


# ---------------------------------------------------------------- the answer
def compute(when, north=NORTH, aod=0.05):
    t = (parse_when(when) if isinstance(when, str) or when is None else when).astimezone(dt.timezone.utc)
    pos = positions_ae(t) if A else positions_fallback(t)
    ev = events_ae(t) if A else events_fallback(t)
    s, m = pos['sun'], pos['moon']
    sd, md = world_dir(s['alt'], s['az'], north), world_dir(m['alt'], m['az'], north)
    T = transmittance(s['alt'], aod)
    k = max(T) or 1
    age = m['phase_deg'] / 360 * 29.530589
    lux_moon = 10 ** (-0.4 * (m['mag'] + 13.98)) * (sum(transmittance(m['alt'], aod)) / 3) * max(0.0, math.sin(m['alt'] * D))
    lux_sun = 127500 * (0.2126 * T[0] + 0.7152 * T[1] + 0.0722 * T[2]) * max(0.0, math.sin(s['alt'] * D))
    b = to_blender(sd)
    return {
        'utc': t.strftime('%Y-%m-%dT%H:%M:%SZ'), 'hst': hst(t), 'north': north,
        'source': 'astronomy-engine' if A else 'NOAA sun + Meeus moon (fallback)',
        'sun': {'alt': round(s['alt'], 3), 'az': round(s['az'], 3), 'up': s['alt'] > -0.27,
                'dir_three': [round(x, 6) for x in sd], 'dir_blender': [round(x, 6) for x in b],
                # Blender sky texture (Nishita) angles, as blender_render.set_sun derives them
                'sun_elevation_rad': round(math.asin(max(-1, min(1, b[2]))), 6), 'sun_rotation_rad': round(math.atan2(b[0], -b[1]), 6),
                'color_rgb': [round(x / k, 4) for x in T], 'direct_lux': round(lux_sun, 1)},
        'moon': {'alt': round(m['alt'], 3), 'az': round(m['az'], 3), 'up': m['alt'] > -0.27,
                 'dir_three': [round(x, 6) for x in md], 'dir_blender': [round(x, 6) for x in to_blender(md)],
                 'phase_deg': round(m['phase_deg'], 2), 'illuminated_fraction': round(m['fraction'], 4),
                 'phase_name': PHASES[int(((m['phase_deg'] + 22.5) % 360) // 45)],
                 'hawaiian_night': PO[min(29, max(0, int(age + 0.5) - 1))], 'magnitude': round(m['mag'], 2),
                 'angular_radius_deg': round(math.asin(1737.4 / (m['dist_au'] * 149597870.7)) / D, 4), 'direct_lux': round(lux_moon, 4)},
        'day': {k2: ([hst(x) for x in v] if isinstance(v, list) else hst(v)) for k2, v in ev.items()},
    }


def table(year):
    rows = []
    cases = [('Mar equinox', dt.date(year, 3, 20)), ('Jun solstice', dt.date(year, 6, 21)), ('Sep equinox', dt.date(year, 9, 22)), ('Dec solstice', dt.date(year, 12, 21))]
    print(f'{"":14} {"sunrise":>9} {"sunset":>9}  {"rise az":>7} {"set az":>7}   NOAA check (rise / set)')
    for name, d in cases:
        t = dt.datetime(d.year, d.month, d.day, 12, tzinfo=HST).astimezone(dt.timezone.utc)
        r = compute(t)
        rise, set_ = noaa_rise_set(d)
        az = lambda x: compute(dt.datetime.strptime(x, '%Y-%m-%d %H:%M HST').replace(tzinfo=HST))['sun']['az']
        print(f'{name:14} {r["day"]["sunrise"][11:16]:>9} {r["day"]["sunset"][11:16]:>9}  {az(r["day"]["sunrise"]):7.1f} {az(r["day"]["sunset"]):7.1f}   {hst(rise)[11:16]} / {hst(set_)[11:16]}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('when', nargs='?', default='now', help='ISO date-time (HST if no zone), or "now"')
    ap.add_argument('--meta', help='nahiku-meta.json: take true north from night.north')
    ap.add_argument('--aod', type=float, default=0.05, help='aerosol optical depth for the sun colour (0.05 clear trades)')
    ap.add_argument('--table', type=int, metavar='YEAR', help='print sunrise/sunset for the solstices and equinoxes')
    a = ap.parse_args()
    if a.table:
        table(a.table); sys.exit(0)
    north = NORTH
    if a.meta and os.path.exists(a.meta):
        north = json.load(open(a.meta)).get('night', {}).get('north', NORTH)
    try:
        print(json.dumps(compute(a.when, north, a.aod), indent=2, ensure_ascii=False))
    except BrokenPipeError:
        pass
