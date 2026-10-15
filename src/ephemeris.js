// Sun and moon over Kukui'ula for any instant: positions, moon phase, rise/set, golden hour.
// astronomy-engine (MIT, vendor/astronomy.module.min.js) does the astronomy, accurate to about an
// arcminute: topocentric moon, refraction, the real rise/set definition (upper limb on the horizon).
// Hawai'i keeps Hawaii-Aleutian Standard Time all year: HST = UTC-10, no daylight saving.
//
// Directions: azimuth is true, from north clockwise through east (degrees); altitude above the
// horizon (degrees). worldDir() turns them into three.js world vectors given true north on the plan
// (siteLayout(plan).north): +y up, east = north turned clockwise seen from above.
import * as A from '../vendor/astronomy.module.min.js';

export const SITE = { lat: 21.886, lon: -159.474, elevM: 40, name: 'Kukuiʻula, Poʻipū, Kauaʻi' };
const OBS = new A.Observer(SITE.lat, SITE.lon, SITE.elevM);
const HST_MS = -10 * 3600e3;
const D = Math.PI / 180;

// ---------- Hawaii time ----------
const shifted = date => new Date(date.getTime() + HST_MS);           // a Date whose UTC fields read HST
export function hstParts(date) {
  const s = shifted(date), y = s.getUTCFullYear();
  const doy = Math.floor((Date.UTC(y, s.getUTCMonth(), s.getUTCDate()) - Date.UTC(y, 0, 1)) / 864e5) + 1;
  return { year: y, month: s.getUTCMonth(), day: s.getUTCDate(), weekday: s.getUTCDay(), doy, minutes: s.getUTCHours() * 60 + s.getUTCMinutes() + s.getUTCSeconds() / 60 };
}
export const daysInYear = y => (y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0) ? 366 : 365);
// HST calendar day `doy` (1-based) of `year`, `minutes` after local midnight -> Date
export const fromHST = (year, doy, minutes) => new Date(Date.UTC(year, 0, doy) + minutes * 60e3 - HST_MS);
export const hstMidnight = date => { const p = hstParts(date); return fromHST(p.year, p.doy, 0); };
// "2026-06-21" or "2026-06-21T19:10" (no zone = HST) or a full ISO time with a zone
export function parseHST(s) {
  if (!s) return null;
  if (/[zZ]|[+-]\d\d:?\d\d$/.test(s)) return new Date(s);
  const m = s.match(/^(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d?):(\d\d))?/);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] ?? 12), +(m[5] ?? 0)) - HST_MS);
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
export { MONTHS };
export function fmtTime(date, { short = false } = {}) {
  if (!date) return '—';
  const p = hstParts(date), h = Math.floor(p.minutes / 60) % 24, m = Math.floor(p.minutes % 60);
  const ap = h < 12 ? 'am' : 'pm', h12 = h % 12 || 12;
  return short ? `${h12}${m ? ':' + String(m).padStart(2, '0') : ''}${ap[0]}` : `${h12}:${String(m).padStart(2, '0')} ${ap}`;
}
export function fmtDate(date, { year = false } = {}) {
  const p = hstParts(date);
  return `${DAYS[p.weekday]} ${p.day} ${MONTHS[p.month]}${year ? ' ' + p.year : ''}`;
}

// ---------- positions ----------
function altAz(body, date) {
  const eq = A.Equator(body, date, OBS, true, true);
  const h = A.Horizon(date, OBS, eq.ra, eq.dec, 'normal');
  return { alt: h.altitude, az: h.azimuth, dist: eq.dist };
}
export function sunAltAz(date) { return altAz(A.Body.Sun, date); }

const PHASES = ['New moon', 'Waxing crescent', 'First quarter', 'Waxing gibbous', 'Full moon', 'Waning gibbous', 'Last quarter', 'Waning crescent'];
export function phaseName(deg) { return PHASES[Math.floor(((deg + 22.5) % 360) / 45)]; }

// Kaulana mahina: the thirty named nights of the Hawaiian lunar month, Hilo (first thin crescent)
// to Muku (the moon gone). Counted here from the moon's age at the instant; almanacs that count
// from the first sighted crescent can differ by a night.
const PO = ['Hilo', 'Hoaka', 'Kū Kahi', 'Kū Lua', 'Kū Kolu', 'Kū Pau', 'ʻOle Kū Kahi', 'ʻOle Kū Lua', 'ʻOle Kū Kolu', 'ʻOle Pau',
  'Huna', 'Mohalu', 'Hua', 'Akua', 'Hoku', 'Māhealani', 'Kulu', 'Lāʻau Kū Kahi', 'Lāʻau Kū Lua', 'Lāʻau Pau',
  'ʻOle Kū Kahi', 'ʻOle Kū Lua', 'ʻOle Pau', 'Kāloa Kū Kahi', 'Kāloa Kū Lua', 'Kāloa Pau', 'Kāne', 'Lono', 'Mauli', 'Muku'];
export function hawaiianNight(phaseDeg) {
  const age = phaseDeg / 360 * 29.530589;                                // days since new moon
  const n = Math.min(30, Math.max(1, Math.floor(age + 0.5)));            // Hilo ~ the evening after new moon
  return { n, name: PO[n - 1] };
}

export function moonState(date) {
  const p = altAz(A.Body.Moon, date);
  const ill = A.Illumination(A.Body.Moon, date);
  const phase = A.MoonPhase(date);                                      // 0 new, 90 first quarter, 180 full, 270 last quarter
  const km = p.dist * 149597870.7;
  return {
    alt: p.alt, az: p.az, distKm: km,
    radiusDeg: Math.asin(1737.4 / km) / D,
    illum: ill.phase_fraction, phase, phaseAngle: ill.phase_angle, mag: ill.mag,
    waxing: phase < 180, name: phaseName(phase), hawaiian: hawaiianNight(phase),
  };
}

// ---------- events of one HST day ----------
const t = x => (x ? x.date : null);
const rs = (body, dir, start) => t(A.SearchRiseSet(body, OBS, dir, start, 1.02));
const altCross = (dir, start, alt) => t(A.SearchAltitude(A.Body.Sun, OBS, dir, start, 1.02, alt));
const dayCache = new Map();
// Golden hour as photographers use it: sun between 6 deg above and 4 deg below the horizon;
// blue hour between 4 and 8 deg below.
export function dayInfo(date) {
  const p = hstParts(date), key = `${p.year}-${p.doy}`;
  if (dayCache.has(key)) return dayCache.get(key);
  const m0 = fromHST(p.year, p.doy, 0);
  const noon = A.SearchHourAngle(A.Body.Sun, OBS, 0, m0, +1)?.time.date ?? null;
  const info = {
    midnight: m0,
    sunrise: rs(A.Body.Sun, +1, m0), sunset: rs(A.Body.Sun, -1, m0),
    noon, noonAlt: noon ? sunAltAz(noon).alt : null,
    goldenAM: [altCross(+1, m0, -4), altCross(+1, m0, 6)],
    goldenPM: [altCross(-1, m0, 6), altCross(-1, m0, -4)],
    blueAM: [altCross(+1, m0, -8), altCross(+1, m0, -4)],
    bluePM: [altCross(-1, m0, -4), altCross(-1, m0, -8)],
    civilDawn: altCross(+1, m0, -6), civilDusk: altCross(-1, m0, -6),
    nauticalDusk: altCross(-1, m0, -12), astroDusk: altCross(-1, m0, -18), astroDawn: altCross(+1, m0, -18),
    moonrise: rs(A.Body.Moon, +1, m0), moonset: rs(A.Body.Moon, -1, m0),
  };
  // a search that runs past this day's midnight found tomorrow's event: this day has none
  const end = m0.getTime() + 864e5;
  for (const k of Object.keys(info)) {
    const v = info[k];
    if (v instanceof Date && v.getTime() >= end) info[k] = null;
    if (Array.isArray(v)) info[k] = v.map(x => (x && x.getTime() < end ? x : null));
  }
  if (dayCache.size > 800) dayCache.clear();
  dayCache.set(key, info);
  return info;
}

// next time the moon reaches a phase (0 new, 180 full) after `date`
export function nextMoonPhase(date, deg) { return t(A.SearchMoonPhase(deg, date, 40)); }

// The sun's track across one HST day, every `step` minutes, plus the stretch just below the horizon.
export function sunTrack(date, step = 6) {
  const m0 = hstMidnight(date), out = [];
  for (let k = 0; k <= 1440; k += step) { const d = new Date(m0.getTime() + k * 60e3), s = sunAltAz(d); out.push({ date: d, minutes: k, ...s }); }
  return out;
}

// Na Hiku (the Big Dipper): J2000 positions of Dubhe, Merak, Phecda, Megrez, Alioth, Mizar, Alkaid.
const NA_HIKU_RADEC = [[165.93, 61.75], [165.46, 56.38], [178.46, 53.69], [183.86, 57.03], [193.51, 55.96], [200.98, 54.93], [206.89, 49.31]];
export function naHikuAltitude(date) {
  let s = 0;
  for (const [ra, dec] of NA_HIKU_RADEC) s += A.Horizon(date, OBS, ra / 15, dec, 'normal').altitude;
  return s / NA_HIKU_RADEC.length;
}
// the middle of the seven stars as altitude / azimuth
export function naHikuAltAz(date) {
  let x = 0, y = 0, z = 0;
  for (const [ra, dec] of NA_HIKU_RADEC) { const h = A.Horizon(date, OBS, ra / 15, dec, 'normal'); const a = h.altitude * D, b = h.azimuth * D; x += Math.cos(a) * Math.cos(b); y += Math.cos(a) * Math.sin(b); z += Math.sin(a); }
  return { alt: Math.atan2(z, Math.hypot(x, y)) / D, az: (Math.atan2(y, x) / D + 360) % 360 };
}
// The best evening in the next year to see Na Hiku: the seven stars high over the house at
// 9:30 pm, the sky fully dark and the moon down or new.
export function bestNaHikuNight(from) {
  const p = hstParts(from);
  let best = null;
  for (let k = 0; k < 366; k++) {
    const d = fromHST(p.year, p.doy + k, 21 * 60 + 30);
    const alt = naHikuAltitude(d);
    if (alt < 35) continue;
    const m = moonState(d), sun = sunAltAz(d).alt;
    const score = alt - 25 * m.illum - (m.alt > -2 ? 80 * m.illum + 8 : 0) - (sun > -18 ? 50 : 0);
    if (!best || score > best.score) best = { date: d, score, alt };
  }
  return best?.date ?? fromHST(p.year, p.doy, 21 * 60 + 30);
}

// June / December solstice of a year (Date)
export function solstices(year) {
  const s = A.Seasons(year);
  return { june: s.jun_solstice.date, december: s.dec_solstice.date, march: s.mar_equinox.date, september: s.sep_equinox.date };
}

// world direction (three.js: +y up) of altitude/azimuth given true north on the plan [nx, nz]
export function worldDir(alt, az, north, out = [0, 0, 0]) {
  const [nx, nz] = north, ex = -nz, ez = nx;                              // east = north turned clockwise
  const ca = Math.cos(alt * D), cn = Math.cos(az * D) * ca, ce = Math.sin(az * D) * ca;
  out[0] = cn * nx + ce * ex; out[1] = Math.sin(alt * D); out[2] = cn * nz + ce * ez;
  return out;
}
