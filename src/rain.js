// Trade-wind showers: streaks of rain around the viewer slanting with the wind, and the garden's
// hard surfaces going dark and glossy as they soak (by material name; restored when dry).
import * as THREE from 'three';

// outdoor finishes that darken and shine when wet: [name, porosity (darkening), gloss (roughness drop)]
const WET = [['pavers', 0.35, 0.7], ['coral', 0.3, 0.6], ['stepping', 0.35, 0.7], ['concrete', 0.3, 0.6], ['asphalt', 0.45, 0.75],
  ['ashlar', 0.35, 0.6], ['grassPavers', 0.25, 0.5], ['terrain', 0.18, 0.35], ['grass', 0.18, 0.35], ['roof', 0.12, 0.6],
  ['roof bronze', 0.12, 0.6], ['roof slate', 0.12, 0.6], ['teak', 0.3, 0.5], ['cedar', 0.3, 0.5], ['siding', 0.06, 0.25], ['trunk', 0.3, 0.4], ['asphalt road', 0.45, 0.75]];

export function createRain(scene, { count = 9000 } = {}) {
  const BOX = [90, 60, 90];
  const pos = new Float32Array(count * 2 * 3), end = new Float32Array(count * 2);
  let s = 7;
  const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < count; i++) {
    const x = r() * BOX[0], y = r() * BOX[1], z = r() * BOX[2];
    for (let k = 0; k < 2; k++) { pos.set([x, y, z], (i * 2 + k) * 3); end[i * 2 + k] = k; }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('aEnd', new THREE.BufferAttribute(end, 1));
  const U = { uTime: { value: 0 }, uCam: { value: new THREE.Vector3() }, uVel: { value: new THREE.Vector3(0, -28, 0) }, uBox: { value: new THREE.Vector3(...BOX) },
    uColor: { value: new THREE.Color(0.6, 0.65, 0.7) }, uOpacity: { value: 0 }, uFrac: { value: 1 } };
  const mat = new THREE.ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, fog: false,
    vertexShader: `attribute float aEnd; uniform float uTime, uFrac; uniform vec3 uCam, uVel, uBox; varying float vA;
      void main() {
        vec3 p = position + uVel * uTime;
        p = mod(p - uCam + uBox * 0.5, uBox) + uCam - uBox * 0.5;      // wrap the box round the viewer
        p -= uVel * 0.045 * aEnd;                                        // streak: where the drop was 1/22 s ago
        vA = (1.0 - aEnd * 0.7) * step(fract(position.x * 7.13 + position.z * 3.71), uFrac);
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        vA *= smoothstep(1.0, 6.0, -mv.z) * (1.0 - smoothstep(25.0, 45.0, -mv.z));
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: 'uniform vec3 uColor; uniform float uOpacity; varying float vA; void main(){ gl_FragColor = vec4(uColor, uOpacity * vA); }',
  });
  const lines = new THREE.LineSegments(geo, mat);
  lines.frustumCulled = false; lines.visible = false; lines.renderOrder = 5; lines.name = 'rain';
  scene.add(lines);

  // wet surfaces
  const mats = [];
  scene.traverse(o => {
    if (!o.isMesh) return;
    for (const m of [].concat(o.material)) {
      // the real site's lidar terrain (src/realsite.js): darker when wet, no puddle sheen from that far
      const w = WET.find(([n]) => n === m.name) ?? (/^realsite (near|far|ground|terrain)/.test(m.name ?? '') ? [m.name, 0.15, 0.15] : null);
      if (!w || mats.some(x => x.m === m) || m.userData.interior) continue;
      mats.push({ m, color: m.color.clone(), rough: m.roughness, env: m.envMapIntensity ?? 1, por: w[1], gloss: w[2] });
    }
  });
  let wet = -1;
  function setWet(x) {
    if (Math.abs(x - wet) < 0.004) return;
    wet = x;
    for (const q of mats) {
      q.m.color.copy(q.color).multiplyScalar(1 - q.por * x);
      q.m.roughness = q.rough * (1 - q.gloss * x);
      q.m.envMapIntensity = q.env * (1 + 0.6 * x);
    }
  }
  setWet(0);
  // rain: mm/h; wind: downwind [x, z] and mph; ambient: THREE.Color of the light on the drops
  function update(dt, camera, { rain, windMph, dir, ambient }) {
    U.uTime.value = (U.uTime.value + dt) % 1000;
    U.uCam.value.copy(camera.position);
    const k = Math.min(1, rain / 6);
    lines.visible = rain > 0.05;
    U.uFrac.value = 0.15 + 0.85 * k;
    U.uOpacity.value = 0.22 + 0.25 * k;
    const side = windMph * 1.467 * 0.55;                  // mph -> ft/s, drops lag the wind a little
    U.uVel.value.set(dir[0] * side, -26 - 4 * k, dir[1] * side);
    if (ambient) U.uColor.value.copy(ambient);
  }
  return { update, setWet, get wet() { return wet; }, lines, materials: mats.map(q => q.m.name) };
}
