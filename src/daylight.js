// Real sun, moon, sky and weather over the house, for any minute of any day.
//
// Light levels: everything is computed physically first (lux, cd/m2: the sun through the air at its
// altitude, the sky from atmosphere.js, the moon from its magnitude, airglow), then mapped to the
// screen the way an eye or a camera adapts — a white wall in full sun, at dusk and under a full
// moon keeps its real ordering and colour but not the 10^8 ratio. One scale applies to every natural
// source at a given moment, so sky, sun, moon and their shadows always agree; house lights are fixed,
// so they glow at dusk and dominate on a new-moon night, as they do.
import * as THREE from 'three';
import * as EPH from './ephemeris.js';
import { airParams, transmittance, skySurvey, luminance } from './atmosphere.js';
import { createSky, CLOUD_GLSL, CLOUD_H, TILE_KM } from './skydome.js';
import { makeNightSky, SITE as SKY_SITE } from './sky.js';
import { createWind } from './wind.js';
import { createRain } from './rain.js';
import { createSunPath } from './sunpath.js';
import { createPanel } from './timepanel.js';
import * as WX from './weather.js';

const D = Math.PI / 180;
const E0 = 127500;                  // the sun's illuminance outside the atmosphere, lux
const K = 4.45e-5;                  // scene light units per lux at full daylight adaptation
const E_REF = 1.1e5;                // "full daylight"
const SKY_GAIN = 2.4;               // multiple scattering + a photographer's sky: single scattering alone renders a clear sky too dark
const FLOOR_LUX = 8e-4, FLOOR_L = 2.2e-4;    // airglow + starlight: ground illuminance, sky luminance (21.8 mag/arcsec2)
const MOON_L = 2900;                // full moon's mean luminance, cd/m2, above the air
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;
const norm = c => { const m = Math.max(c[0], c[1], c[2], 1e-12); return [c[0] / m, c[1] / m, c[2] / m]; };
// a camera white-balanced for daylight: the noon sun reads a touch warm, shade a touch blue
const WB = [1, 1.047, 1.123];

// How bright a white wall lit by ambient illuminance E (lux) is drawn, relative to full sun: falls ~3x
// from noon to sunset and ~6x more by the end of dusk, then is held up by night vision so a full-moon
// night reads (silvery, ~1/8 of day) while a new-moon night is dark. (log10 lux, brightness)
const KEY = [[-3.1, 0.022], [-2.2, 0.04], [-1.5, 0.07], [-0.7, 0.115], [0, 0.12], [1, 0.125], [2, 0.165], [3, 0.29], [4, 0.6], [5.05, 1.0], [6, 1.2]];
function key(E) {
  const x = Math.log10(Math.max(E, 1e-4));
  if (x <= KEY[0][0]) return KEY[0][1] * Math.pow(10, (x - KEY[0][0]) * 0.4);
  for (let i = 1; i < KEY.length; i++) if (x <= KEY[i][0]) {
    const [x0, y0] = KEY[i - 1], [x1, y1] = KEY[i], t = (x - x0) / (x1 - x0);
    return Math.pow(10, Math.log10(y0) + (Math.log10(y1) - Math.log10(y0)) * t);
  }
  return KEY[KEY.length - 1][1];
}
const exposureFor = E => lerp(0.58, 1.25, smooth(Math.log10(3e4), Math.log10(3), Math.log10(E)));

export async function createDaylight({ scene, renderer, camera, plan, quality, north, center, terrainH, ceilingAt, lamps, glow, mat, params, bloom = null, shot }) {
  const [cx, cz] = center;
  const sky = createSky(renderer, scene, { quality, north });
  const ultra = quality === 'ultra';

  // ---------- lights ----------
  const keyLight = new THREE.DirectionalLight('#ffffff', 0);
  keyLight.castShadow = true;
  const sm = quality === 'low' ? 2048 : ultra ? 8192 : 4096;
  keyLight.shadow.mapSize.set(sm, sm);
  Object.assign(keyLight.shadow.camera, { left: -110, right: 110, top: 110, bottom: -110, near: 50, far: 900 });
  keyLight.shadow.bias = -0.0004; keyLight.shadow.normalBias = 0.04; keyLight.shadow.radius = 3;
  keyLight.target.position.set(cx, 0, cz);
  scene.add(keyLight, keyLight.target);
  const hemi = new THREE.HemisphereLight('#e8eef5', '#a99b83', 0.12);
  scene.add(hemi);
  const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
  const roomEnv = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(renderer), 0.04).texture;
  const interiors = [];
  scene.traverse(o => { if (!o.isMesh) return; for (const m of [].concat(o.material)) if (m.userData.interior && !m.envMap) { m.envMap = roomEnv; m.needsUpdate = true; interiors.push([m, m.envMapIntensity ?? 1]); } });

  // emissive finishes switched on at dusk (ours and the neighbours')
  const water = mat('water'), tile = mat('poolTile');
  const waterBase = { opacity: water.opacity };
  water.emissive = new THREE.Color('#0c8fb5'); water.emissiveIntensity = 0;
  tile.emissive = new THREE.Color('#0a6a86'); tile.emissiveIntensity = 0;
  const hoodWin = [], hoodPool = [];
  scene.traverse(o => { if (!o.isMesh) return; const m = o.material; if (!m?.emissive) return; const h = m.emissive.getHexString(); if (h === 'ffc77a' && !hoodWin.includes(m)) hoodWin.push(m); if (h === '0b7fa3' && !hoodPool.includes(m)) hoodPool.push(m); });

  // house, pool and garden lights, built the first time it gets dark (adding lights recompiles shaders once)
  let nightLights = null;
  function buildNightLights() {
    const list = [];
    const lit = plan.rooms.filter(r => !r.label_only && (!r.outdoor || r.covered)).map(r => {
      const xs = r.polygon.map(p => p[0]), ys = r.polygon.map(p => p[1]);
      return { area: (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys)), xs, ys };
    }).sort((a, b) => b.area - a.area).slice(0, 8);
    for (const { xs, ys, area } of lit) {
      const x = (Math.min(...xs) + Math.max(...xs)) / 2, y = (Math.min(...ys) + Math.max(...ys)) / 2;
      const l = new THREE.PointLight('#ffc98a', 0, Math.sqrt(area) * 2.4, 1.6);
      l.position.set(x, Math.min(ceilingAt(x, y) - 1.5, 9), y); l.userData.on = Math.min(40, 6 + area / 12);
      scene.add(l); list.push(l);
    }
    const P = plan.site?.pool;
    if (P) {
      const [x0, y0, x1, y1] = P.rect;
      for (const t of [0.25, 0.75]) { const pl = new THREE.PointLight('#38d6ff', 0, 40, 1.4); pl.position.set(x0 + (x1 - x0) / 2, (plan.grade ?? -0.6) - 3, y0 + (y1 - y0) * t); pl.userData.on = 60; scene.add(pl); list.push(pl); }
    }
    for (const p of (plan.site?.palms ?? []).filter(p => Math.hypot(p[0] - cx, p[1] - cz) < 70).slice(0, 8)) {
      const s = new THREE.SpotLight('#ffd7a0', 0, (p[2] ?? 30) + 12, 0.35, 0.6, 1.2);
      s.position.set(p[0] + 1.5, terrainH(p[0], p[1]) + 0.3, p[1] + 1.5);
      s.target.position.set(p[0], terrainH(p[0], p[1]) + (p[2] ?? 30), p[1]);
      s.userData.on = 90; scene.add(s, s.target); list.push(s);
    }
    return list;
  }

  // ---------- stars (loaded when first needed) ----------
  let stars = null, starsLoading = null;
  const loadStars = () => starsLoading ??= makeNightSky(scene, { date: new Date('2026-01-01T10:00:00Z'), north, dynamic: true, cloud: { glsl: CLOUD_GLSL, uniforms: sky.cloudU } }).then(s => { stars = s; S.dirty = true; return s; });
  const pole = (() => { const d = EPH.worldDir(SKY_SITE.lat, 0, north); return new THREE.Vector3(d[0], d[1], d[2]).normalize(); })();

  // ---------- weather, wind, rain, sun path, panel ----------
  const wind = createWind(scene);
  const windNames = wind.scan();
  const rain = createRain(scene, { count: quality === 'low' ? 4000 : 9000 });
  const B0 = (() => { let a = [1e9, 1e9, -1e9, -1e9]; for (const r of plan.rooms) for (const [x, y] of r.polygon) { a = [Math.min(a[0], x), Math.min(a[1], y), Math.max(a[2], x), Math.max(a[3], y)]; } return a; })();
  const sunPath = createSunPath({ scene, center: [cx, (plan.grade ?? -0.6), cz], radius: Math.max(70, Math.hypot(B0[2] - B0[0], B0[3] - B0[1]) * 0.55), north });

  const S = {
    date: new Date(), live: true, weather: WX.typical(), wxKind: 'live', preset: null,
    tween: null, dirty: true, lastLut: 0, lutSig: '', wet: 0, cloudOcc: 0,
  };
  let lastWeatherFetch = 0, fetching = false;
  async function refreshWeather() {
    if (fetching) return; fetching = true; lastWeatherFetch = performance.now();
    try { S.weather = await WX.fetchLive(); }
    catch (e) { if (S.weather?.source !== 'live') S.weather = WX.typical(); console.info('live weather unavailable, using typical trades:', e.message); }
    fetching = false; S.dirty = true;
  }

  // ---------- presets ----------
  function presetDate(id, from = S.date) {
    const p = EPH.hstParts(from), di = EPH.dayInfo(from), y = p.year;
    const sol = EPH.solstices(y), now = new Date();
    switch (id) {
      case 'sunrise': return new Date((di.sunrise ?? from).getTime() + 4 * 60e3);
      case 'golden': return di.goldenPM[0] ? new Date((di.goldenPM[0].getTime() * 0.35 + di.sunset.getTime() * 0.65)) : from;
      case 'sunset': return new Date((di.sunset ?? from).getTime() - 3 * 60e3);
      case 'fullmoon': {
        let fm = EPH.nextMoonPhase(new Date(from.getTime() - 3 * 864e5), 180);
        // the evening of the full moon, when it stands ~25 deg over the sea-side horizon
        const d = EPH.dayInfo(fm), rise = d.moonrise ?? EPH.dayInfo(new Date(fm.getTime() - 864e5)).moonrise ?? fm;
        let t = new Date(rise.getTime() + 2.2 * 3600e3);
        if (EPH.sunAltAz(t).alt > -12) t = new Date(EPH.dayInfo(t).astroDusk?.getTime() ?? t.getTime() + 3600e3);
        return t;
      }
      case 'stars': return EPH.bestNaHikuNight(now);
      case 'winter': { const d = EPH.dayInfo(sol.december); return new Date(d.sunset.getTime() - 3 * 60e3); }
      case 'summer': { const d = EPH.dayInfo(sol.june); return new Date(d.sunset.getTime() - 3 * 60e3); }
      default: return now;
    }
  }
  function goTo(date, { animate = !shot } = {}) {
    S.preset = S.preset ?? null;
    if (!animate) { S.date = date; S.tween = null; S.dirty = true; return; }
    let from = S.date;
    // a different day: jump to that day at the current clock time, then sweep the clock
    if (Math.abs(date - from) > 20 * 3600e3) {
      const a = EPH.hstParts(from), b = EPH.hstParts(date);
      from = EPH.fromHST(b.year, b.doy, a.minutes);
    }
    S.tween = { from: from.getTime(), to: date.getTime(), t: 0, dur: Math.min(3.2, 0.8 + Math.abs(date - from) / 3600e3 * 0.28) };
    S.date = from; S.dirty = true;
  }
  function setLive(on) {
    S.live = on;
    if (on) { S.preset = 'live'; goTo(new Date()); if (S.wxKind === 'live') refreshWeather(); }
  }
  function setWeather(kind) {
    S.wxKind = kind;
    if (kind === 'live') refreshWeather();
    else S.weather = WX.normalize(WX.PRESETS[kind], 'simulated');
    S.dirty = true;
  }

  const panel = shot ? null : createPanel({
    onDay: doy => { const p = EPH.hstParts(S.date); S.live = false; S.preset = null; S.tween = null; S.date = EPH.fromHST(p.year, doy, p.minutes); S.dirty = true; },
    onMinutes: m => { const p = EPH.hstParts(S.date); S.live = false; S.preset = null; S.tween = null; S.date = EPH.fromHST(p.year, p.doy, m); S.dirty = true; },
    onPreset: id => { if (id === 'live') return setLive(true); S.live = false; S.preset = id; goTo(presetDate(id)); onPresetHook?.(id); },
    onWeather: setWeather,
    onSunPath: v => { sunPath.visible = v; S.sunPathUser = true; S.dirty = true; },
    onLive: setLive,
  });
  let onPresetHook = null;

  // ---------- initial state from the URL ----------
  const wxp = WX.fromParams(params);
  if (wxp) { S.weather = wxp; S.wxKind = params.get('wx') ?? 'custom'; }
  const presetId = params.get('preset');
  const explicit = EPH.parseHST(params.get('date')) ?? (params.get('time') === 'night' ? new Date(plan.night?.date ?? '2026-03-20T07:00:00Z') : null);
  if (explicit || params.has('hst') || params.has('doy') || presetId || params.get('live') === '0') {
    S.live = false;
    let d = explicit ?? new Date();
    const p = EPH.hstParts(d);
    if (params.has('doy')) d = EPH.fromHST(p.year, Number(params.get('doy')), p.minutes);
    if (params.has('hst')) { const [h, m = 0] = params.get('hst').split(':').map(Number); const q = EPH.hstParts(d); d = EPH.fromHST(q.year, q.doy, h * 60 + m); }
    if (presetId) { S.preset = presetId; d = presetId === 'live' ? new Date() : presetDate(presetId, d); if (presetId === 'live') S.live = true; }
    S.date = d;
  } else { S.preset = 'live'; }
  if (!wxp) { if (shot) S.weather = WX.typical(); else refreshWeather(); }
  sunPath.visible = params.has('sunpath') ? params.get('sunpath') !== '0' : false;

  // ---------- the physics ----------
  const surveyCache = new Map();
  function survey(alt, aod) {
    const k = `${Math.round(alt * 4)}|${aod.toFixed(3)}`;
    if (!surveyCache.has(k)) {
      if (surveyCache.size > 600) surveyCache.clear();
      const a = Math.round(alt * 4) / 4;
      surveyCache.set(k, skySurvey([Math.cos(a * D), Math.sin(a * D), 0], airParams({ aod })));
    }
    return surveyCache.get(k);
  }
  const tmp = new THREE.Vector3(), col = new THREE.Color();
  let L = null;            // last computed light state
  function compute() {
    const date = S.date, w = S.weather;
    const sun = EPH.sunAltAz(date), moon = EPH.moonState(date);
    const P = airParams({ aod: w.aod });
    const sDir = EPH.worldDir(sun.alt, sun.az, north), mDir = EPH.worldDir(moon.alt, moon.az, north);
    const overcast = smooth(0.75, 1.0, w.cloud) * (w.rainMmH > 0.2 ? 1 : 0.85);
    const cumulus = Math.min(0.85, w.cloud * 0.95);
    sky.cloudU.uCloudThr.value = sky.threshold(cumulus);
    // sun
    const Ts = transmittance(Math.max(sun.alt, -0.27), P), Tcloud = transmittance(Math.max(sun.alt, -1.2), P, CLOUD_H);
    const disc = smooth(-0.27, 0.27, sun.alt);                       // how much of the disc is above the horizon
    const sv = survey(sun.alt, w.aod);
    const EsunDir = E0 * luminance(Ts) * Math.max(0, Math.sin(sun.alt * D)) * disc;
    const EsunSky = E0 * luminance(sv.E) * SKY_GAIN;
    // moon: illuminance from its magnitude (Allen: E = 10^-0.4(m + 13.98) lux)
    const Emoon0 = Math.pow(10, -0.4 * (moon.mag + 13.98));
    const Tm = transmittance(Math.max(moon.alt, -0.27), P), mv = survey(moon.alt, w.aod);
    const mdisc = smooth(-0.3, 0.3, moon.alt);
    const EmoonDir = Emoon0 * luminance(Tm) * Math.max(0, Math.sin(moon.alt * D)) * mdisc;
    const EmoonSky = Emoon0 * luminance(mv.E) * SKY_GAIN;
    // what the camera adapts to: the clear-sky light, a little less under overcast
    const shadeK = 1 - 0.55 * overcast - 0.25 * smooth(0.3, 0.9, w.cloud) * (1 - overcast);
    const Etot = Math.max(1e-4, (EsunDir + EmoonDir) * shadeK + (EsunSky + EmoonSky) * (1 - 0.4 * overcast) + FLOOR_LUX);
    const e = exposureFor(Etot);
    const s = (key(Etot) / key(E_REF)) * (exposureFor(E_REF) / e) * (E_REF / Etot);
    const U = K * s;                                                  // scene units per lux (and per cd/m2)
    // dark-adapted vision: below a few lux the eye loses colour and shifts blue (Purkinje)
    const pk = smooth(Math.log10(3), Math.log10(0.003), Math.log10(Etot)) * 0.8;
    const night = c => { const l = luminance(c); return [lerp(c[0], l * 0.66, pk), lerp(c[1], l * 0.84, pk), lerp(c[2], l * 1.22, pk)]; };
    const wb = c => [c[0] * WB[0], c[1] * WB[1], c[2] * WB[2]];
    return { date, sun, moon, sDir, mDir, P, Ts, Tcloud, Tm, sv, mv, EsunDir, EsunSky, Emoon0, EmoonDir, EmoonSky, Etot, e, s, U, pk, night, wb, overcast, cumulus, disc, mdisc, w };
  }

  function apply(L, { lut = true } = {}) {
    const { sun, moon, sDir, mDir, U, night, wb, overcast, w } = L;
    // key light: the sun by day, the moon by night (whichever is up and brighter)
    const occ = sky.coverAt(sDir) * (1 - overcast);                   // a cumulus in front of the sun
    S.cloudOcc = occ;
    const sunK = (1 - 0.88 * occ) * (1 - 0.86 * overcast) * (1 - 0.5 * smooth(0.5, 4, w.rainMmH));
    const useSun = sun.alt > -2 || L.EmoonDir <= 0;
    const lightDir = useSun ? sDir : mDir;
    keyLight.position.set(cx + lightDir[0] * 400, lightDir[1] * 400, cz + lightDir[2] * 400);
    if (useSun) {
      const c = wb(norm(L.Ts));
      keyLight.color.setRGB(c[0], c[1], c[2]);
      keyLight.intensity = L.EsunDir > 0 ? L.EsunDir * U * sunK / luminance(c) : 0;   // the light's illuminance is intensity x colour
    } else {
      const c = norm(night(wb(norm([L.Tm[0], L.Tm[1] * 0.97, L.Tm[2] * 0.9]))));
      keyLight.color.setRGB(c[0], c[1], c[2]);
      keyLight.intensity = L.EmoonDir * U * (1 - 0.88 * sky.coverAt(mDir) * (1 - overcast)) * (1 - 0.86 * overcast) / luminance(c);
    }
    keyLight.castShadow = true;
    // sky light: hemisphere fill, the interiors' room light
    const EskyU = (L.EsunSky + L.EmoonSky + FLOOR_LUX) * U * (1 - 0.35 * overcast);
    const skyCol = night(wb(norm([L.sv.E[0] * L.EsunSky + L.mv.E[0] * L.EmoonSky + 1e-9, L.sv.E[1] * L.EsunSky + L.mv.E[1] * L.EmoonSky + 1e-9, L.sv.E[2] * L.EsunSky + L.mv.E[2] * L.EmoonSky + 1.5e-9])));
    hemi.color.setRGB(...norm(skyCol)); hemi.intensity = 0.12 * EskyU / 1.0;
    const day = Math.min(1.2, (EskyU + keyLight.intensity * 0.12) / 1.5);
    for (const [m, base] of interiors) m.envMapIntensity = base * Math.max(0.03, day);

    // house lights from dusk
    const on = Math.max(smooth(3, -4, sun.alt), smooth(0.9, 1.0, w.cloud) * smooth(14, 4, sun.alt) * 0.6);
    if (on > 0.001 && !nightLights) nightLights = buildNightLights();
    for (const l of nightLights ?? []) l.intensity = l.userData.on * on;
    for (const l of lamps) l.intensity = l.userData.nightIntensity * on;
    glow.emissiveIntensity = 0.4 + 1.8 * on;
    water.emissiveIntensity = 1.1 * on; water.opacity = lerp(waterBase.opacity, 0.85, on);
    tile.emissiveIntensity = 0.5 * on;
    for (const m of hoodWin) m.emissiveIntensity = 0.9 * on;
    for (const m of hoodPool) m.emissiveIntensity = 0.8 * on;
    if (bloom) { bloom.strength = 0.55 * Math.sqrt(on) + 0.25 * smooth(-4, -10, sun.alt) * moon.illum * (moon.alt > 0 ? 1 : 0); bloom.enabled = bloom.strength > 0.02; }
    renderer.toneMappingExposure = L.e;

    // sky texture uniforms (in scene units)
    const u = sky.lutU, sunE = E0 * U, wbs = wb([1, 1, 1]);
    u.uSunDir.value.set(...sDir); u.uMoonDir.value.set(...mDir);
    u.uSunE.value.set(sunE * wbs[0], sunE * wbs[1], sunE * wbs[2]);
    u.uTwE.value.copy(u.uSunE.value);
    const me = night(wb([L.Emoon0, L.Emoon0 * 0.97, L.Emoon0 * 0.9]));
    const moonSkyLift = 1 + 1.5 * L.pk;                              // a moonlit sky reads bluer and brighter than a meter says
    u.uMoonE.value.set(me[0] * U * moonSkyLift, me[1] * U * moonSkyLift, me[2] * U * moonSkyLift);
    u.uGain.value = SKY_GAIN;
    u.uMieS.value = L.P.mieS; u.uMieE.value = L.P.mieE; u.uG.value = L.P.g;
    const fl = night([0.55, 0.7, 1.0]), fll = luminance(fl);
    u.uFloor.value.set(fl[0] / fll * FLOOR_L * U, fl[1] / fll * FLOOR_L * U, fl[2] / fll * FLOOR_L * U);
    u.uGlow.value.set(1.0, 0.72, 0.45).multiplyScalar(FLOOR_L * 1.5 * U);
    const glowDir = EPH.worldDir(0, 60, north); u.uGlowDir.value.set(glowDir[0], glowDir[2]).normalize();
    const Eg = (L.EsunDir * sunK + L.EmoonDir + L.EsunSky + L.EmoonSky + FLOOR_LUX) * U;
    u.uGroundL.value.set(0.09, 0.1, 0.07).multiplyScalar(Eg / Math.PI);
    u.uOvercast.value = overcast;
    const oc = ((L.EsunDir * 0.35 + L.EsunSky) + (L.EmoonDir * 0.35 + L.EmoonSky) + FLOOR_LUX) * U / Math.PI * (w.rainMmH > 0.2 ? 0.55 : 0.8);
    const occ0 = night([0.93, 0.96, 1.0]);
    u.uOvercastL.value.set(occ0[0] * oc, occ0[1] * oc, occ0[2] * oc);

    // the dome: sun and moon discs, clouds
    const d = sky.domeU;
    const sc = norm(L.Ts), sunB = Math.min(L.EsunDir * U / 6.8e-5, lerp(3.5, 60, smooth(0.5, 18, sun.alt))) * (1 - 0.97 * overcast);
    d.uSunDisc.value.set(sc[0], sc[1], sc[2]).multiplyScalar(sun.alt > -1 ? sunB : 0);
    const mc = norm(L.Tm), moonB = Math.min(MOON_L * L.Tm[0] * U, 7) * (1 - 0.95 * overcast) * (moon.alt > -1 ? 1 : 0);
    d.uMoonDisc.value.set(mc[0], mc[1] * 0.97, mc[2] * 0.9).multiplyScalar(moonB);
    d.uMoonR.value = moon.radiusDeg * D;
    d.uEarthshine.value = 0.012 * Math.pow(1 - moon.illum, 2);
    d.uPole.value.copy(pole);
    const cloudSun = sun.alt > -2 || L.EmoonDir <= 0;
    const cl = cloudSun ? wb(L.Tcloud.map(x => x * E0 * U)) : night(wb([L.Emoon0 * L.Tm[0] * U, L.Emoon0 * L.Tm[1] * U * 0.97, L.Emoon0 * L.Tm[2] * U * 0.9]));
    d.uCloudLight.value.set(cl[0], cl[1], cl[2]).multiplyScalar(0.85 / Math.PI * (1 - 0.6 * overcast));
    d.uCloudLightDir.value.set(...(cloudSun ? sDir : mDir));
    const amb = night(wb(norm(skyCol)));
    d.uCloudAmb.value.set(amb[0], amb[1], amb[2]).multiplyScalar(EskyU * 0.75 / Math.PI + FLOOR_L * U * 2);
    d.uCloudDark.value = Math.min(1, overcast * 0.35 + smooth(0.2, 4, w.rainMmH) * 0.65);
    d.uCloudThick.value = 1 + smooth(0.2, 4, w.rainMmH) * 0.6;
    sky.cloudU.uMountain.value = 0.1 + 0.05 * w.cloud;
    sky.cloudU.uCirrus.value = w.cloud > 0.9 ? 0.0 : 0.12 + 0.25 * smooth(0.1, 0.7, w.cloud);

    // aerial haze in the colour of the horizon
    const hz = night(wb([0, 1, 2].map(c => (L.sv.hor[c] * E0 * SKY_GAIN * 0.75 + L.mv.hor[c] * L.Emoon0 * SKY_GAIN * moonSkyLift + FLOOR_L * 2.5 * [0.55, 0.7, 1][c]) * U)));
    const hzOver = [0.62, 0.66, 0.7].map(x => x * oc * 2.4);
    const fogc = hz.map((x, i) => lerp(x, hzOver[i], overcast));
    if (!scene.fog) scene.fog = new THREE.FogExp2('#c9dbe8', 0.000045);
    scene.fog.color.setRGB(...fogc);
    scene.fog.density = 0.000045 * (1 + 3 * smooth(0.2, 5, w.rainMmH) + (w.fog ? 8 : 0) + Math.max(0, (w.aod - 0.05) * 12));

    // stars
    if (stars) {
      // naked-eye limiting magnitude from the zenith sky brightness (Schaefer), and the zenith in cd/m2
      const Lz = (L.sv.zen[1] * E0 * SKY_GAIN + L.mv.zen[1] * L.Emoon0 * SKY_GAIN + FLOOR_L) * (1 - overcast * 0.0) ;
      const Bmag = -2.5 * Math.log10(Math.max(Lz, 1e-9) / 1.08e5);
      const lim = 7.93 - 5 * Math.log10(Math.pow(10, 4.316 - Bmag / 5) + 1);
      stars.setLimit(lim, 1.25 / L.e);
      stars.lines.material.opacity = S.preset === 'stars' ? 0.22 * smooth(2.5, 4.5, lim) * (1 - overcast) : 0;
      stars.group.visible = lim > -0.5;
      stars.setTime(S.date);
    }
    sunPath.update(S.date, sun);

    // the sky texture and image-based light: only when something visible changed
    const sig = [sDir.map(x => x.toFixed(3)), mDir.map(x => x.toFixed(3)), Math.log(U).toFixed(2), overcast.toFixed(2), L.P.mieE.toFixed(4), L.pk.toFixed(2)].join('|');
    const now = performance.now();
    if (lut && sig !== S.lutSig) {
      if (now - S.lastLut > (quality === 'low' ? 120 : 50) || shot) { S.lutSig = sig; S.lastLut = now; S.lutPending = false; sky.render(); }
      else S.lutPending = true;                                        // dragging fast: catch up on a later frame
    }
  }

  // ---------- per frame ----------
  let liveTick = 0, occTick = 0;
  const windDir = [0, 0];
  function update(dt) {
    if (S.tween) {
      const T = S.tween; T.t = Math.min(1, T.t + dt / T.dur);
      const k = T.t < 0.5 ? 4 * T.t ** 3 : 1 - Math.pow(-2 * T.t + 2, 3) / 2;
      S.date = new Date(lerp(T.from, T.to, k)); S.dirty = true;
      if (T.t >= 1) S.tween = null;
    } else if (S.live && !shot) {
      liveTick += dt;
      if (liveTick > 1) { liveTick = 0; const n = new Date(); if (Math.abs(n - S.date) > 30e3) { S.date = n; S.dirty = true; } }
      if (S.wxKind === 'live' && performance.now() - lastWeatherFetch > 600e3) refreshWeather();
    }
    const w = S.weather;
    const down = EPH.worldDir(0, w.windFrom + 180, north); windDir[0] = down[0]; windDir[1] = down[2];
    // clouds drift downwind at ~1.3x the surface wind
    const kmps = w.windMph * 0.447 * 1.3 / 1000;
    sky.cloudU.uCloudOff.value.x -= windDir[0] * kmps * dt / TILE_KM;
    sky.cloudU.uCloudOff.value.y -= windDir[1] * kmps * dt / TILE_KM;
    sky.cloudU.uCirrusOff.value.x -= windDir[0] * kmps * 2 * dt / 28;
    sky.cloudU.uCirrusOff.value.y -= windDir[1] * kmps * 2 * dt / 28;
    wind.update(dt, { windMph: w.windMph, gustMph: w.gustMph, dir: windDir }, w.rainMmH);
    // wet surfaces soak in a couple of minutes of rain and dry over ~10
    const wetTarget = smooth(0.1, 2, w.rainMmH);
    S.wet = shot ? wetTarget : wetTarget > S.wet ? Math.min(wetTarget, S.wet + dt / 90) : Math.max(wetTarget, S.wet - dt / 600);
    rain.setWet(S.wet);
    rain.update(dt, camera, { rain: w.rainMmH, windMph: w.windMph, dir: windDir, ambient: hemi.color.clone().multiplyScalar(Math.min(1.2, 0.25 + hemi.intensity * 3)) });
    if (stars) stars.starMat.uniforms.uTwinkle.value += dt;
    if (S.lutPending && performance.now() - S.lastLut > 150) S.dirty = true;
    if (S.dirty) { S.dirty = false; L = compute(); apply(L); }
    else if (L && (occTick += dt) > 0.25) {                           // clouds crossing the sun
      occTick = 0;
      const occ = sky.coverAt(L.sDir) * (1 - L.overcast);
      if (Math.abs(occ - S.cloudOcc) > 0.01) apply(L, { lut: false });
    }
    if (panel && (panelTick += dt) > 0.2) { panelTick = 0; updatePanel(); }
  }
  let panelTick = 1;
  function updatePanel() {
    if (!L) return;
    panel.update({ date: S.date, parts: EPH.hstParts(S.date), info: EPH.dayInfo(S.date), moon: L.moon, sun: L.sun, weather: S.weather, live: S.live, sunPath: sunPath.visible, wxKind: S.wxKind, preset: S.preset });
  }
  function beforeRender(cam) {
    sky.renderClouds(cam);
    if (stars) { stars.group.position.copy(cam.position); stars.starMat.uniforms.uScale.value = renderer.getPixelRatio() * innerHeight / 1000; }
  }

  // first light, and the stars if it is (or may soon be) dark
  L = compute(); apply(L); S.dirty = false;
  if (L.sun.alt < -3 || shot === false) { const p = loadStars(); if (L.sun.alt < -3) { await p; S.dirty = true; L = compute(); apply(L); S.dirty = false; } }
  if (params.has('debugsky')) console.info('[sky]', { windMaterials: windNames, wet: rain.materials, sunAlt: L.sun.alt.toFixed(2), sunAz: L.sun.az.toFixed(1), moon: L.moon.name, illum: L.moon.illum.toFixed(2), Etot: L.Etot.toExponential(2), s: L.s.toExponential(2), exposure: L.e.toFixed(2), key: keyLight.intensity.toFixed(3), hemi: hemi.intensity.toFixed(3), weather: S.weather });

  return {
    update, beforeRender, state: S, get light() { return L; }, keyLight, sky, sunPath, panel, wind, rain,
    set onPreset(f) { onPresetHook = f; },
    set bloom(p) { bloom = p; S.dirty = true; },
    // the sun path shows itself in the fly-over, unless the viewer has switched it on or off
    autoSunPath(v) { if (!S.sunPathUser) { sunPath.visible = v; S.dirty = true; } },
    toDay() { const p = EPH.hstParts(S.date); S.live = false; S.preset = null; goTo(EPH.fromHST(p.year, p.doy, 10 * 60 + 30)); },
    // where to look after a preset: the sun, the moon or Na Hiku (world unit vector)
    target(id) {
      const d = new Date(S.tween ? S.tween.to : S.date.getTime());
      const h = id === 'stars' ? EPH.naHikuAltAz(d) : id === 'fullmoon' ? EPH.moonState(d) : EPH.sunAltAz(d);
      return EPH.worldDir(h.alt, h.az, north);
    },
    preset: id => (id === 'live' ? setLive(true) : (S.live = false, S.preset = id, goTo(presetDate(id)), onPresetHook?.(id))),
    setLive, setWeather, presetDate, goTo,
    async ready() { if (L.sun.alt < -3) await loadStars(); S.dirty = true; update(0); },
    get isNight() { return L ? L.sun.alt < -6 : false; },
  };
}
