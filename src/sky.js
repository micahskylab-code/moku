// Day: physically based sky + sun. Night: the real sky over Kukui'ula — ~5,000 catalogue
// stars (Yale Bright Star / Hipparcos via d3-celestial, BSD licence) and the Milky Way,
// placed by sidereal time for the given date, with Na Hiku (the Big Dipper) singled out.
// World axes: +x = plan x = north, +z = plan y = east, +y = up.
import * as THREE from 'three';
import { Sky } from 'three/addons/objects/Sky.js';

export const SITE = { lat: 21.895, lon: -159.47 };      // Kukui'ula, Kaua'i
export const NA_HIKU = [54061, 53910, 58001, 59774, 62956, 65378, 67301]; // Dubhe, Merak, Phecda, Megrez, Alioth, Mizar, Alkaid
const NA_HIKU_LINES = [[0, 1], [1, 2], [2, 3], [3, 0], [3, 4], [4, 5], [5, 6]];

const D = Math.PI / 180;

// Horizon direction (world) of a sun/star given azimuth from north (deg, clockwise) and altitude (deg).
export function dirFromAltAz(alt, az) {
  const ca = Math.cos(alt * D);
  return new THREE.Vector3(ca * Math.cos(az * D), Math.sin(alt * D), ca * Math.sin(az * D));
}

export function makeDaySky(scene, renderer, { sunAlt = 48, sunAz = 235 } = {}) {
  const sky = new Sky();
  sky.scale.setScalar(200000);
  const u = sky.material.uniforms;
  u.turbidity.value = 1.6; u.rayleigh.value = 2.2; u.mieCoefficient.value = 0.003; u.mieDirectionalG.value = 0.85;
  const sunDir = dirFromAltAz(sunAlt, sunAz);
  u.sunPosition.value.copy(sunDir).multiplyScalar(1000);
  scene.add(sky);
  sky.visible = false;
  const dome = new THREE.Mesh(new THREE.SphereGeometry(30000, 32, 16), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { uSun: { value: sunDir.clone() } },
    vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }',
    fragmentShader: `varying vec3 vD; uniform vec3 uSun;
      void main(){ float h = max(vD.y, 0.0);
        vec3 zen = vec3(0.05, 0.19, 0.55), mid = vec3(0.19, 0.42, 0.78), hor = vec3(0.60, 0.74, 0.86);
        vec3 c = mix(hor, mid, smoothstep(0.0, 0.18, h)); c = mix(c, zen, smoothstep(0.18, 0.75, h));
        float s = max(dot(normalize(vD), normalize(uSun)), 0.0); c += vec3(1.0,0.95,0.85) * pow(s, 60.0) * 0.6;
        gl_FragColor = vec4(c * 1.55, 1.0); }`,
  }));
  dome.renderOrder = -1;
  scene.add(dome);

  // Image-based light from the same sky, so shade and glass match the sky colour.
  const pm = new THREE.PMREMGenerator(renderer);
  const envScene = new THREE.Scene();
  const envSky = new Sky(); envSky.scale.setScalar(1000);
  Object.assign(envSky.material.uniforms.turbidity, { value: 2.6 });
  envSky.material.uniforms.rayleigh.value = 2.2; envSky.material.uniforms.mieCoefficient.value = 0.003; envSky.material.uniforms.turbidity.value = 1.6;
  envSky.material.uniforms.sunPosition.value.copy(sunDir).multiplyScalar(1000);
  envScene.add(envSky);
  // a darker ground half so reflections and ambient read as land, not sky
  const groundHemi = new THREE.Mesh(new THREE.SphereGeometry(500, 32, 16, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), new THREE.MeshBasicMaterial({ color: '#6c7a52', side: THREE.BackSide }));
  envScene.add(groundHemi);
  const env = pm.fromScene(envScene, 0.02).texture;
  scene.environment = env;
  return { sky, sunDir, env };
}

// ---------- night ----------
function gmstDeg(date) {
  const jd = date.getTime() / 86400000 + 2440587.5;
  return ((280.46061837 + 360.98564736629 * (jd - 2451545.0)) % 360 + 360) % 360;
}

export function equatorialToWorld(raDeg, decDeg, date, { lat = SITE.lat, lon = SITE.lon } = {}) {
  const H = (gmstDeg(date) + lon - raDeg) * D, d = decDeg * D, p = lat * D;
  const U = Math.sin(p) * Math.sin(d) + Math.cos(p) * Math.cos(d) * Math.cos(H);
  const N = Math.cos(p) * Math.sin(d) - Math.sin(p) * Math.cos(d) * Math.cos(H);
  const E = -Math.cos(d) * Math.sin(H);
  return new THREE.Vector3(N, U, E);
}

function bvToColor(bv) {
  // rough black-body tint from B-V colour index
  const t = Math.max(-0.4, Math.min(2.0, bv ?? 0.6));
  const c = new THREE.Color();
  if (t < 0) c.setRGB(0.68, 0.78, 1.0);
  else if (t < 0.4) c.setRGB(0.85 + t * 0.3, 0.9 + t * 0.15, 1.0);
  else if (t < 1.0) c.setRGB(1.0, 0.96 - (t - 0.4) * 0.2, 0.9 - (t - 0.4) * 0.45);
  else c.setRGB(1.0, 0.82 - (t - 1) * 0.15, 0.6 - (t - 1) * 0.2);
  return c;
}

export async function makeNightSky(scene, { date, radius = 50000 } = {}) {
  const [stars, mw] = await Promise.all([fetch('data/stars.6.json').then(r => r.json()), fetch('data/mw.json').then(r => r.json())]);
  const group = new THREE.Group();
  group.renderOrder = -10;

  // sky dome: deep blue zenith, faint airglow at the horizon
  const dome = new THREE.Mesh(new THREE.SphereGeometry(radius * 1.05, 48, 24), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: {},
    vertexShader: 'varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: `varying vec3 vDir; void main(){ float h = clamp(vDir.y, -0.2, 1.0);
      vec3 zen = vec3(0.004,0.008,0.022), hor = vec3(0.045,0.06,0.10);
      vec3 c = mix(hor, zen, pow(max(h,0.0), 0.45)); if (h < 0.0) c = hor * 0.6; gl_FragColor = vec4(c,1.0); }`,
  }));
  group.add(dome);

  // Milky Way: d3-celestial brightness contours painted onto an equatorial canvas, blurred.
  const cv = document.createElement('canvas'); cv.width = 2048; cv.height = 1024;
  const cx = cv.getContext('2d');
  cx.filter = 'blur(10px)';
  for (const f of mw.features) {
    const level = parseInt(String(f.id).replace(/\D/g, '')) || 1;
    cx.fillStyle = `rgba(190,200,230,${0.07 + level * 0.025})`;
    const polys = f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates : [f.geometry.coordinates];
    for (const poly of polys) for (const ring of poly) {
      cx.beginPath();
      ring.forEach(([lon, lat], i) => { const x = ((lon % 360) + 360) % 360 / 360 * cv.width, y = (90 - lat) / 180 * cv.height; i ? cx.lineTo(x, y) : cx.moveTo(x, y); });
      cx.closePath(); cx.fill();
    }
  }
  const mwTex = new THREE.CanvasTexture(cv); mwTex.colorSpace = THREE.SRGBColorSpace;
  const mwGeo = new THREE.SphereGeometry(radius, 128, 64);
  const p = mwGeo.attributes.position, uv = mwGeo.attributes.uv;
  for (let i = 0; i < p.count; i++) {
    const ra = uv.getX(i) * 360, dec = 90 - (1 - uv.getY(i)) * 180;
    const w = equatorialToWorld(ra, dec, date).multiplyScalar(radius);
    p.setXYZ(i, w.x, w.y, w.z);
    uv.setXY(i, uv.getX(i), uv.getY(i));
  }
  const mwMesh = new THREE.Mesh(mwGeo, new THREE.MeshBasicMaterial({ map: mwTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, fog: false, opacity: 0.55 }));
  group.add(mwMesh);

  // Stars as sized, coloured points.
  const pos = [], col = [], size = [], naHiku = [];
  for (const f of stars.features) {
    const [lon, lat] = f.geometry.coordinates, mag = f.properties.mag;
    const w = equatorialToWorld(((lon % 360) + 360) % 360, lat, date);
    if (w.y < -0.05) continue;
    // atmospheric extinction near the horizon
    const ext = 0.25 / Math.max(0.08, w.y);
    const m = mag + ext * 0.6;
    if (m > 6.2) continue;
    w.multiplyScalar(radius * 0.98);
    pos.push(w.x, w.y, w.z);
    const c = bvToColor(f.properties.bv);
    col.push(c.r, c.g, c.b);
    size.push(Math.pow(10, -0.4 * (m - 6.3)));
    const k = NA_HIKU.indexOf(Number(f.id));
    if (k >= 0) naHiku[k] = w.clone();
  }
  const sg = new THREE.BufferGeometry();
  sg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  sg.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  sg.setAttribute('flux', new THREE.Float32BufferAttribute(size, 1));
  const starMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
    uniforms: { uScale: { value: 1 }, uTwinkle: { value: 0 } },
    vertexShader: `attribute float flux; attribute vec3 color; varying vec3 vC; varying float vF; uniform float uScale; uniform float uTwinkle;
      void main(){ vC = color; float tw = 1.0 + 0.18 * sin(uTwinkle * 3.0 + position.x * 0.01 + position.z * 0.013);
        vF = clamp(flux * 0.16 * tw, 0.0, 1.6);
        gl_PointSize = clamp((1.5 + sqrt(flux) * 1.5) * uScale, 1.0, 14.0 * uScale);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec3 vC; varying float vF;
      void main(){ vec2 d = gl_PointCoord - 0.5; float r = length(d) * 2.0; if (r > 1.0) discard;
        float core = exp(-r * r * 9.0), halo = exp(-r * 3.5) * 0.25;
        gl_FragColor = vec4(vC * (core + halo) * (0.35 + vF), 1.0); }`,
  });
  const points = new THREE.Points(sg, starMat);
  group.add(points);

  // Na Hiku: faint guide lines for the reveal (opacity animated by the video).
  const lp = [];
  for (const [a, b] of NA_HIKU_LINES) if (naHiku[a] && naHiku[b]) lp.push(naHiku[a].x, naHiku[a].y, naHiku[a].z, naHiku[b].x, naHiku[b].y, naHiku[b].z);
  const lineGeo = new THREE.BufferGeometry(); lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(lp, 3));
  const lines = new THREE.LineSegments(lineGeo, new THREE.LineBasicMaterial({ color: '#cfe0ff', transparent: true, opacity: 0, depthWrite: false, fog: false }));
  group.add(lines);

  group.traverse(o => { o.frustumCulled = false; });
  scene.add(group);
  const center = naHiku.filter(Boolean).reduce((s, v) => s.add(v), new THREE.Vector3()).normalize();
  return { group, starMat, lines, naHiku, center };
}
