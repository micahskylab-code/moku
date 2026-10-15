// Trade winds in the garden: palm fronds, areca, shrubs and the far palms sway and flutter with the
// wind's speed, gusts and direction; their shadows move with them; the pool ripples run downwind.
// Works on the built scene by material name (it does not touch plants.js / site.js):
//   foliage-frond (frondMaterial)  -> fronds, bending from the crown (uv.x = 0) to the tip (uv.x = 1)
//   foliage-*, *leaf*, *frond*      -> leaf cards and leaves: flutter, a little sway
//   the distant palms' cone crowns -> the rim moves, the centre stays
// One cheap vertex-shader term (onBeforeCompile), no extra draw calls.
import * as THREE from 'three';

const GLSL = /* glsl */`
uniform float uWindTime, uWindLean, uWindAmp, uGust, uFlutter, uWindMode, uWindScale;
uniform vec2 uWindDir;
vec3 windOffset(vec3 wp, vec2 tuv) {
  float w = uWindMode < 0.5 ? 1.0 : uWindMode < 1.5 ? clamp(tuv.x, 0.0, 1.0) : clamp(1.0 - tuv.y, 0.0, 1.0);
  float w2 = w * w;
  float ph = dot(wp.xz, vec2(0.11, 0.07));
  // gust fronts sweep downwind across the lot every few seconds
  float g = 0.5 + 0.5 * sin(uWindTime * 0.55 - dot(wp.xz, uWindDir) * 0.018 + 1.3 * sin(uWindTime * 0.21 + ph * 0.1));
  g = g * g * uGust;
  float sway = sin(uWindTime * 1.7 + ph) * 0.65 + sin(uWindTime * 3.1 + ph * 1.7) * 0.35;
  vec3 dir = vec3(uWindDir.x, 0.0, uWindDir.y), side = vec3(-uWindDir.y, 0.0, uWindDir.x);
  vec3 o = dir * (uWindLean + g) * w2 * (1.0 + 0.25 * sway) + (dir * 0.6 + side * 0.45) * sway * uWindAmp * w2;
  o.y -= (uWindLean + g) * 0.3 * w2;
  float f = sin(uWindTime * 11.0 + wp.x * 3.1 + wp.z * 2.3 + wp.y * 4.7) + 0.5 * sin(uWindTime * 17.0 + wp.x * 5.3 - wp.z * 4.1);
  o += vec3(0.3, 1.0, 0.3) * f * uFlutter * (0.4 + 0.6 * w);
  return o * uWindScale;
}
`;
const PROJECT = /* glsl */`
vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_BATCHING
  mvPosition = batchingMatrix * mvPosition;
#endif
#ifdef USE_INSTANCING
  mvPosition = instanceMatrix * mvPosition;
#endif
vec4 windWorld = modelMatrix * mvPosition;
windWorld.xyz += windOffset(windWorld.xyz, uv);
mvPosition = viewMatrix * windWorld;
gl_Position = projectionMatrix * mvPosition;
`;

// mode 0: leaf cards, 1: fronds (uv.x along), 2: cone crowns (uv.y up); scale in feet per unit
function classify(m, mesh) {
  const n = (m.name || '').toLowerCase();
  if (!m.isMeshStandardMaterial) return null;
  if (n === 'foliage-frond' || /frond|leaflet|palm-leaf/.test(n)) return { mode: 1, scale: 1 };
  if (n.startsWith('foliage-') || /leaf|leaves|foliage|shrub|hedge|canopy/.test(n)) return { mode: 0, scale: n.includes('hedge') && mesh.isInstancedMesh ? 2.5 : 1 };
  // the far palms' crowns in site.js scatterTrees: an unnamed double-sided cone
  if (!n && m.side === THREE.DoubleSide && mesh.isInstancedMesh && mesh.geometry.type === 'ConeGeometry') return { mode: 2, scale: 2.2 };
  return null;
}

export function createWind(scene) {
  const U = {
    uWindTime: { value: 0 }, uWindDir: { value: new THREE.Vector2(-0.4, -0.9) },
    uWindLean: { value: 0 }, uWindAmp: { value: 0 }, uGust: { value: 0 }, uFlutter: { value: 0 },
  };
  const done = new Map(), names = new Set();
  const patch = (m, { mode, scale }) => {
    const prev = m.onBeforeCompile;
    m.onBeforeCompile = (sh, r) => {
      prev?.call(m, sh, r);
      Object.assign(sh.uniforms, U, { uWindMode: { value: mode }, uWindScale: { value: scale } });
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\n' + GLSL).replace('#include <project_vertex>', PROJECT);
    };
    const key = m.customProgramCacheKey?.bind(m);
    m.customProgramCacheKey = () => (key ? key() : '') + `|wind${mode}:${scale}`;
    m.needsUpdate = true;
  };
  function depthFor(m, kind) {
    const d = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, map: m.map, alphaTest: m.alphaTest || 0, side: THREE.DoubleSide });
    patch(d, kind);
    return d;
  }
  function scan() {
    scene.traverse(o => {
      if (!o.isMesh || Array.isArray(o.material)) return;
      const m = o.material;
      let rec = done.get(m);
      if (rec === undefined) {
        const kind = classify(m, o);
        rec = kind ? { kind, depth: depthFor(m, kind) } : null;
        if (kind) { patch(m, kind); names.add(m.name || `(cone crowns)`); }
        done.set(m, rec);
      }
      if (rec && o.castShadow && !o.customDepthMaterial) o.customDepthMaterial = rec.depth;
    });
    return [...names];
  }

  // pool water ripples drift downwind; the vanishing-edge sheet falls
  let water = null, sheet = null;
  scene.traverse(o => {
    if (!o.isMesh) return;
    const m = o.material;
    if (m?.name === 'water' && m.normalMap && !water) { m.normalMap = m.normalMap.clone(); m.normalMap.needsUpdate = true; water = { m, base: m.normalScale.x }; }
    if (m?.isMeshPhysicalMaterial && m.transparent && m.normalMap && m.color?.getHexString() === '8fd3df' && !sheet) { m.normalMap = m.normalMap.clone(); m.normalMap.needsUpdate = true; sheet = m; }
  });

  let speed = 0;
  // wind: { windMph, gustMph, dir: [x, z] downwind unit vector in world }, rain mm/h
  function update(dt, wind, rain = 0) {
    const v = wind.windMph, gust = Math.max(0, wind.gustMph - v);
    speed += (v - speed) * Math.min(1, dt * 0.5 + (speed === 0 ? 1 : 0));
    U.uWindTime.value += dt * (0.55 + Math.min(1.4, speed / 22));
    U.uWindDir.value.set(wind.dir[0], wind.dir[1]).normalize();
    U.uWindLean.value = 0.045 * speed;
    U.uWindAmp.value = 0.012 + 0.018 * speed;
    U.uGust.value = 0.03 * gust;
    U.uFlutter.value = 0.004 * speed + 0.01;
    if (water) {
      const t = water.m.normalMap;
      t.offset.x += wind.dir[0] * dt * (0.02 + speed * 0.004);
      t.offset.y -= wind.dir[1] * dt * (0.02 + speed * 0.004);
      const s = Math.min(0.9, water.base * (0.6 + speed / 25) + rain * 0.08);
      water.m.normalScale.set(s, s);
    }
    if (sheet) sheet.normalMap.offset.y += dt * 0.35;
  }
  return { scan, update, uniforms: U };
}
