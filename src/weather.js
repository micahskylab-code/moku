// Weather at Kukui'ula: live from Open-Meteo (free, no key, CORS), or simulated.
//   ?wx=clear|partly|trades|cloudy|rain|windy    a typical day of that kind
//   ?weather={"temperature_2m":80,"cloud_cover":40,...}   raw Open-Meteo "current" fields
// If the live request fails (offline, blocked) the walkthrough falls back to a typical trade-wind
// day: ~79 F, a third of the sky in cumulus, ENE trades at 14 mph gusting to 22.
import { SITE } from './ephemeris.js';

export const LIVE_URL = `https://api.open-meteo.com/v1/forecast?latitude=${SITE.lat}&longitude=${SITE.lon}` +
  '&current=temperature_2m,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,rain,weather_code,is_day' +
  '&wind_speed_unit=mph&temperature_unit=fahrenheit&timezone=Pacific%2FHonolulu';

// raw Open-Meteo "current" blocks for each simulated kind (temperature in F, wind in mph, from-direction in degrees true)
export const PRESETS = {
  clear: { temperature_2m: 81, cloud_cover: 8, wind_speed_10m: 9, wind_direction_10m: 70, wind_gusts_10m: 15, precipitation: 0, rain: 0, weather_code: 0 },
  partly: { temperature_2m: 79, cloud_cover: 35, wind_speed_10m: 14, wind_direction_10m: 65, wind_gusts_10m: 22, precipitation: 0, rain: 0, weather_code: 2 },
  cloudy: { temperature_2m: 76, cloud_cover: 92, wind_speed_10m: 12, wind_direction_10m: 60, wind_gusts_10m: 20, precipitation: 0, rain: 0, weather_code: 3 },
  rain: { temperature_2m: 73, cloud_cover: 100, wind_speed_10m: 19, wind_direction_10m: 55, wind_gusts_10m: 31, precipitation: 3.2, rain: 3.2, weather_code: 63 },
  windy: { temperature_2m: 78, cloud_cover: 45, wind_speed_10m: 25, wind_direction_10m: 70, wind_gusts_10m: 38, precipitation: 0, rain: 0, weather_code: 2 },
};
PRESETS.trades = PRESETS.partly;
export const TYPICAL = PRESETS.partly;

const WMO = { 0: 'Clear', 1: 'Mostly clear', 2: 'Partly cloudy', 3: 'Overcast', 45: 'Fog', 48: 'Fog', 51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle',
  56: 'Freezing drizzle', 57: 'Freezing drizzle', 61: 'Light rain', 63: 'Rain', 65: 'Heavy rain', 66: 'Freezing rain', 67: 'Freezing rain',
  80: 'Passing showers', 81: 'Showers', 82: 'Heavy showers', 95: 'Thunderstorm', 96: 'Thunderstorm, hail', 99: 'Thunderstorm, hail' };
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
export const compass = deg => COMPASS[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16];

// Open-Meteo "current" -> what the scene needs
export function normalize(c, source) {
  const code = Number(c.weather_code ?? 0);
  // the weather code can say "showers" while this quarter-hour's gauge reads zero: trust the larger
  const codeRain = { 51: 0.3, 53: 0.5, 55: 1, 61: 0.8, 63: 2.5, 65: 6, 80: 0.8, 81: 2.5, 82: 6, 95: 8, 96: 8, 99: 8 }[code] ?? 0;
  const rain = Math.max(Number(c.rain) || 0, Number(c.precipitation) || 0, codeRain);
  let wind = Number(c.wind_speed_10m ?? TYPICAL.wind_speed_10m);
  if (c._units === 'kmh') wind /= 1.609;
  const gust = Math.max(wind, Number(c.wind_gusts_10m ?? wind * 1.5) / (c._units === 'kmh' ? 1.609 : 1));
  let temp = Number(c.temperature_2m ?? TYPICAL.temperature_2m);
  if (c._units === 'c' || temp < 45) temp = temp * 9 / 5 + 32;               // Celsius slipped through: Kaua'i is never below 45 F
  const cloud = Math.min(1, Math.max(0, Number(c.cloud_cover ?? 35) / 100));
  return {
    source, time: c.time ?? null,
    tempF: temp, cloud, windMph: wind, gustMph: gust, windFrom: Number(c.wind_direction_10m ?? 65), rainMmH: rain, code,
    text: WMO[code] ?? (cloud > 0.85 ? 'Overcast' : cloud > 0.25 ? 'Partly cloudy' : 'Clear'),
    fog: code === 45 || code === 48,
    // aerosol haze: sea salt on the trades, more in rain and strong wind
    aod: 0.045 + Math.min(0.2, rain * 0.03) + Math.max(0, wind - 18) * 0.003 + (code === 45 || code === 48 ? 0.3 : 0),
  };
}

export function describe(w) {
  if (!w) return '';
  return `${Math.round(w.tempF)}°F · ${w.text} · ${compass(w.windFrom)} ${Math.round(w.windMph)} mph${w.gustMph > w.windMph + 3 ? `, gusts ${Math.round(w.gustMph)}` : ''}`;
}

export async function fetchLive({ timeout = 6000 } = {}) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(LIVE_URL, { signal: ctl.signal, cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    if (!j.current) throw new Error('no current block');
    return normalize(j.current, 'live');
  } finally { clearTimeout(timer); }
}

// The weather the page starts with: ?weather= JSON, ?wx= kind, else live (falling back to typical).
export function fromParams(params) {
  if (params.has('weather')) {
    try { return normalize(JSON.parse(params.get('weather')), 'simulated'); } catch (e) { console.warn('bad ?weather JSON', e.message); }
  }
  const k = params.get('wx');
  if (k && PRESETS[k]) return normalize(PRESETS[k], 'simulated');
  return null;
}
export const typical = () => normalize(TYPICAL, 'typical');
