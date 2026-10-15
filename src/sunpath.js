// "Where the sun goes": the sun's path over the house drawn on a dome round it — the chosen day's
// arc with hour marks, the June and December solstice arcs that bound every day of the year, a
// true-north compass ring on the lawn, and where the sun rises and sets. So a buyer can see which
// way the lanai and pool face the sunset in winter and in summer.
import * as THREE from 'three';
import { sunTrack, solstices, dayInfo, fmtTime, sunAltAz, worldDir, hstParts } from './ephemeris.js';

function label(text, { color = '#fff', bg = 'rgba(18,24,34,.62)', size = 0.034, weight = 500 } = {}) {
  const c = document.createElement('canvas'), x = c.getContext('2d'), F = 44;
  x.font = `${weight} ${F}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  const w = Math.ceil(x.measureText(text).width) + 36;
  c.width = w; c.height = 68;
  x.font = `${weight} ${F}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  if (bg) { x.fillStyle = bg; x.beginPath(); x.roundRect(0, 0, w, 68, 34); x.fill(); }
  x.fillStyle = color; x.textBaseline = 'middle'; x.fillText(text, 18, 36);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, sizeAttenuation: false, depthTest: false, depthWrite: false, toneMapped: false, fog: false, transparent: true }));
  s.scale.set(size * w / 68, size, 1);
  s.renderOrder = 30;
  return s;
}
const basic = (color, opacity = 0.95) => new THREE.MeshBasicMaterial({ color, toneMapped: false, fog: false, transparent: opacity < 1, opacity, depthWrite: opacity >= 1 });

export function createSunPath({ scene, center, radius = 95, north }) {
  const root = new THREE.Group(); root.name = 'sun path'; root.visible = false;
  scene.add(root);
  const C = new THREE.Vector3(...center);
  const at = (alt, az, r = radius) => { const d = worldDir(alt, az, north); return new THREE.Vector3(d[0], d[1], d[2]).multiplyScalar(r).add(C); };

  // compass ring on the ground, with true north
  const ring = new THREE.Group(); root.add(ring);
  const ringGeo = new THREE.RingGeometry(radius - 0.35, radius + 0.35, 180); ringGeo.rotateX(-Math.PI / 2);
  const rm = new THREE.Mesh(ringGeo, basic('#f4efe6', 0.75)); rm.position.copy(C).add(new THREE.Vector3(0, 0.25, 0)); ring.add(rm);
  for (let a = 0; a < 360; a += 15) {
    const long = a % 90 === 0, p0 = at(0, a, radius - (long ? 5 : 2.5)), p1 = at(0, a, radius + (long ? 5 : 2.5));
    const g = new THREE.BufferGeometry().setFromPoints([p0, p1]);
    const l = new THREE.Line(g, new THREE.LineBasicMaterial({ color: '#f4efe6', toneMapped: false, fog: false, transparent: true, opacity: 0.8 }));
    l.position.y = 0.3; ring.add(l);
  }
  for (const [t, a] of [['N', 0], ['E', 90], ['S', 180], ['W', 270]]) {
    const s = label(t, { bg: t === 'N' ? 'rgba(170,40,30,.8)' : 'rgba(18,24,34,.6)', size: 0.03, weight: 700 });
    s.position.copy(at(0, a, radius + 12)).add(new THREE.Vector3(0, 1.5, 0)); ring.add(s);
  }
  const dyn = new THREE.Group(); root.add(dyn);
  const sunNow = new THREE.Mesh(new THREE.SphereGeometry(2.6, 20, 12), basic('#fff3c4', 1));
  const sunHalo = new THREE.Mesh(new THREE.SphereGeometry(4.6, 20, 12), basic('#ffd27a', 0.35));
  root.add(sunNow, sunHalo);
  const ray = new THREE.Line(new THREE.BufferGeometry().setFromPoints([C, C]), new THREE.LineDashedMaterial({ color: '#ffe3a0', dashSize: 3, gapSize: 2.2, toneMapped: false, fog: false, transparent: true, opacity: 0.85 }));
  root.add(ray);

  const arc = (pts, color, r, opacity = 0.95) => {
    if (pts.length < 2) return null;
    const m = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), Math.max(8, pts.length * 2), r, 6), basic(color, opacity));
    dyn.add(m); return m;
  };
  const track = d => sunTrack(d, 5).filter(p => p.alt > -0.9);
  let key = '';
  function build(date) {
    for (const o of [...dyn.children]) { dyn.remove(o); o.traverse(c => { c.geometry?.dispose(); c.material?.map?.dispose(); c.material?.dispose(); }); }
    const y = hstParts(date).year, sol = solstices(y);
    // the year's bounds: June (long, high, sets WNW) and December (short, low, sets WSW)
    for (const [d, color, name] of [[sol.june, '#ff9a5a', 'Jun 21'], [sol.december, '#7fb2ff', 'Dec 21']]) {
      arc(track(d).map(p => at(p.alt, p.az)), color, 0.45, 0.8);
      const info = dayInfo(d);
      for (const [ev, txt] of [[info.sunset, 'sunset'], [info.sunrise, 'sunrise']]) {
        if (!ev) continue;
        const s = sunAltAz(ev), l = label(`${name} ${txt} ${fmtTime(ev)}`, { color, size: 0.026 });
        l.position.copy(at(0, s.az, radius + 16)).add(new THREE.Vector3(0, txt === 'sunset' ? 9 : 5, 0)); dyn.add(l);
        const pin = arc([at(0, s.az, radius - 4), at(0, s.az, radius + 4)], color, 0.5, 0.9); if (pin) pin.position.y += 0.4;
      }
    }
    // the chosen day, with hour marks
    const tr = track(date);
    arc(tr.map(p => at(p.alt, p.az)), '#ffd75e', 0.7, 1);
    for (const p of tr) {
      if (p.minutes % 60 !== 0 || p.alt < 1) continue;
      const pos = at(p.alt, p.az);
      const dot = new THREE.Mesh(new THREE.SphereGeometry(1.25, 12, 8), basic('#fff6d0', 1)); dot.position.copy(pos); dyn.add(dot);
      const h = p.minutes / 60, txt = h === 12 ? 'noon' : `${h % 12 || 12}${h < 12 ? 'am' : 'pm'}`;
      const l = label(txt, { size: 0.024 }); l.position.copy(pos).add(new THREE.Vector3(0, 5, 0)); dyn.add(l);
    }
    const info = dayInfo(date);
    for (const [ev, txt] of [[info.sunrise, 'Sunrise'], [info.sunset, 'Sunset']]) {
      if (!ev) continue;
      const s = sunAltAz(ev);
      const g = new THREE.BufferGeometry().setFromPoints([C.clone().setY(C.y + 0.4), at(0, s.az, radius).setY(C.y + 0.4)]);
      const l = new THREE.Line(g, new THREE.LineDashedMaterial({ color: '#ffd75e', dashSize: 4, gapSize: 3, toneMapped: false, fog: false })); l.computeLineDistances(); dyn.add(l);
      const lb = label(`${txt} ${fmtTime(ev)}`, { color: '#ffe9a8', size: 0.028, weight: 600 });
      lb.position.copy(at(0, s.az, radius + 16)).add(new THREE.Vector3(0, 1.5, 0)); dyn.add(lb);
    }
  }
  function update(date, sun) {
    const p = hstParts(date), k = `${p.year}-${p.doy}`;
    if (k !== key) { key = k; build(date); }
    const up = sun.alt > -0.9;
    sunNow.visible = sunHalo.visible = ray.visible = up;
    if (up) {
      const s = at(sun.alt, sun.az);
      sunNow.position.copy(s); sunHalo.position.copy(s);
      ray.geometry.setFromPoints([C, s]); ray.computeLineDistances();
    }
  }
  return { group: root, update, set visible(v) { root.visible = v; }, get visible() { return root.visible; } };
}
