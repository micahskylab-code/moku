// The sun & sky panel: any day of the year and any minute, Live (Hawaii time now + live weather),
// presets, the day's sun and moon times, and the weather. Compact pill; collapses on phones.
import { MONTHS, daysInYear, fmtTime, fmtDate, sunAltAz, fromHST } from './ephemeris.js';
import { describe } from './weather.js';

export const PRESETS = [
  ['live', 'Live now', 'Hawaiʻi time now, live weather'], ['sunrise', 'Sunrise'], ['golden', 'Golden hour'], ['sunset', 'Sunset'],
  ['fullmoon', 'Full moon', 'the next full-moon night'], ['stars', 'Nā Hiku stars', 'the year’s best night for the Big Dipper over the house'],
  ['winter', 'Dec 21 sunset', 'winter-solstice sunset: furthest south'], ['summer', 'Jun 21 sunset', 'summer-solstice sunset: furthest north'],
];
const WX = [['live', 'Live'], ['clear', 'Clear'], ['partly', 'Trades'], ['cloudy', 'Cloudy'], ['rain', 'Showers'], ['windy', 'Windy']];

// a small drawing of the moon at its phase (lit side toward the sun as seen from Hawai'i: right when waxing)
export function moonIcon(cv, phaseDeg, size = 18) {
  const r = size / 2, x = cv.getContext('2d'), dpr = Math.min(2, devicePixelRatio || 1);
  cv.width = cv.height = size * dpr; cv.style.width = cv.style.height = size + 'px';
  x.scale(dpr, dpr); x.clearRect(0, 0, size, size);
  x.fillStyle = '#2b3445'; x.beginPath(); x.arc(r, r, r - 0.5, 0, 7); x.fill();
  const k = Math.cos(phaseDeg * Math.PI / 180), waxing = phaseDeg < 180;
  x.fillStyle = '#f3ecd8'; x.beginPath();
  x.arc(r, r, r - 0.5, -Math.PI / 2, Math.PI / 2, !waxing);               // the lit limb
  x.ellipse(r, r, Math.abs(k) * (r - 0.5), r - 0.5, 0, Math.PI / 2, -Math.PI / 2, (k > 0) === waxing ? true : false);
  x.fill();
}
function sunIcon(cv, size = 18) {
  const r = size / 2, x = cv.getContext('2d'), dpr = Math.min(2, devicePixelRatio || 1);
  cv.width = cv.height = size * dpr; cv.style.width = cv.style.height = size + 'px';
  x.scale(dpr, dpr); x.clearRect(0, 0, size, size);
  x.strokeStyle = x.fillStyle = '#e8a33c'; x.lineWidth = 1.6; x.lineCap = 'round';
  x.beginPath(); x.arc(r, r, r * 0.42, 0, 7); x.fill();
  for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4; x.beginPath(); x.moveTo(r + Math.cos(a) * r * 0.62, r + Math.sin(a) * r * 0.62); x.lineTo(r + Math.cos(a) * r * 0.9, r + Math.sin(a) * r * 0.9); x.stroke(); }
}

export function createPanel(handlers) {
  const el = document.createElement('div'); el.id = 'skypanel';
  el.innerHTML = `
    <button class="sp-head" type="button" aria-expanded="true">
      <canvas class="sp-icon"></canvas><span class="sp-when"></span><span class="sp-live">LIVE</span><span class="sp-temp"></span><span class="sp-chev">▾</span>
    </button>
    <div class="sp-body">
      <label class="sp-row"><span class="sp-k">Day</span><input class="sp-date" type="range" min="1" max="365" step="1"></label>
      <div class="sp-months"></div>
      <label class="sp-row"><span class="sp-k">Time</span><input class="sp-time" type="range" min="0" max="1439" step="1"></label>
      <div class="sp-hours"><span>12a</span><span>6a</span><span>noon</span><span>6p</span><span>12a</span></div>
      <div class="sp-chips sp-presets"></div>
      <div class="sp-chips sp-wx"><span class="sp-k">Weather</span></div>
      <div class="sp-info"></div>
    </div>`;
  document.body.append(el);
  const $ = s => el.querySelector(s);
  const head = $('.sp-head'), date = $('.sp-date'), time = $('.sp-time'), info = $('.sp-info');
  for (const m of MONTHS) { const s = document.createElement('span'); s.textContent = m[0]; s.title = m; $('.sp-months').append(s); }
  for (const [id, name, title] of PRESETS) { const b = document.createElement('button'); b.type = 'button'; b.className = 'sp-chip'; b.dataset.id = id; b.textContent = name; if (title) b.title = title; $('.sp-presets').append(b); }
  { const b = document.createElement('button'); b.type = 'button'; b.className = 'sp-toggle sp-path'; b.textContent = 'Sun path'; b.title = 'the sun’s arc over the house today and at both solstices'; $('.sp-presets').append(b); }
  for (const [id, name] of WX) { const b = document.createElement('button'); b.type = 'button'; b.className = 'sp-chip'; b.dataset.wx = id; b.textContent = name; $('.sp-wx').append(b); }

  // the panel is a UI island: keep its pointer/touch/keys away from the walk controls
  for (const ev of ['pointerdown', 'mousedown', 'click', 'touchstart', 'touchmove', 'touchend', 'wheel']) el.addEventListener(ev, e => e.stopPropagation(), { passive: ev.startsWith('touch') || ev === 'wheel' });
  el.addEventListener('keydown', e => { e.stopPropagation(); });
  for (const r of [date, time]) r.addEventListener('change', () => r.blur());

  const collapsed = matchMedia('(max-width: 640px), (pointer: coarse)').matches;
  const setOpen = open => { el.classList.toggle('open', open); head.setAttribute('aria-expanded', String(open)); };
  setOpen(!collapsed);
  head.addEventListener('click', () => setOpen(!el.classList.contains('open')));
  date.addEventListener('input', () => handlers.onDay(Number(date.value)));
  time.addEventListener('input', () => handlers.onMinutes(Number(time.value)));
  $('.sp-presets').addEventListener('click', e => { const id = e.target.dataset?.id; if (id) handlers.onPreset(id); });
  $('.sp-wx').addEventListener('click', e => { const id = e.target.dataset?.wx; if (id) handlers.onWeather(id); });
  $('.sp-path').addEventListener('click', () => handlers.onSunPath(!$('.sp-path').classList.contains('on')));

  let dayKey = '';
  // the time slider's track shows the chosen day: night, twilight, golden hour, day
  function paintTrack(p) {
    const stops = [];
    for (let m = 0; m <= 1440; m += 20) {
      const a = sunAltAz(fromHST(p.year, p.doy, m)).alt;
      const c = a > 8 ? '#cfe2f3' : a > -1 ? '#f0b071' : a > -6 ? '#6d7fb8' : a > -12 ? '#33406e' : '#151c33';
      stops.push(`${c} ${(m / 1440 * 100).toFixed(1)}%`);
    }
    time.style.setProperty('--track', `linear-gradient(90deg, ${stops.join(',')})`);
  }
  function update({ date: d, parts, info: di, moon, sun, weather, live, sunPath, wxKind, preset }) {
    const k = `${parts.year}-${parts.doy}`;
    date.max = daysInYear(parts.year);
    if (document.activeElement !== date) date.value = parts.doy;
    if (document.activeElement !== time) time.value = Math.floor(parts.minutes);
    if (k !== dayKey) { dayKey = k; paintTrack(parts); }
    const night = sun.alt < -4;
    if (night) moonIcon($('.sp-icon'), moon.phase); else sunIcon($('.sp-icon'));
    $('.sp-when').textContent = `${fmtDate(d)} · ${fmtTime(d)}`;
    $('.sp-live').hidden = !live;
    $('.sp-temp').textContent = weather ? `${Math.round(weather.tempF)}°F` : '';
    $('.sp-path').classList.toggle('on', !!sunPath);
    for (const b of el.querySelectorAll('[data-wx]')) b.classList.toggle('on', b.dataset.wx === wxKind);
    for (const b of el.querySelectorAll('[data-id]')) b.classList.toggle('on', b.dataset.id === preset);
    const g = di.goldenPM, m = moon;
    const rise = di.moonrise ? fmtTime(di.moonrise) : 'no rise today', set = di.moonset ? fmtTime(di.moonset) : 'no set today';
    info.innerHTML = `
      <div><b>Sun</b> rises ${fmtTime(di.sunrise)} · sets ${fmtTime(di.sunset)} · now ${sun.alt.toFixed(0)}° up${sun.alt < 0 ? ' (below)' : ''}</div>
      <div><b>Golden hour</b> ${fmtTime(g[0])} – ${fmtTime(g[1])} · dusk ${fmtTime(di.civilDusk)}</div>
      <div><b>Moon</b> ${m.name}, ${Math.round(m.illum * 100)}% lit · ${m.hawaiian.name} · rises ${rise} · sets ${set}</div>
      <div><b>Weather</b> ${describe(weather)} <i>(${weather?.source === 'live' ? 'live, Open-Meteo' : weather?.source === 'typical' ? 'typical trades — live data unavailable' : 'simulated'})</i></div>`;
  }
  return { el, update, setOpen };
}
