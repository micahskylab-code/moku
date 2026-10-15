// Exports the built scene for path tracing in Blender (scripts/blender_render.py):
//  - nahiku.glb: everything visible, scaled to metres, glTF PBR materials named by finish
//  - nahiku-meta.json: viewpoint cameras, per-view sun, the night camera path, night lights
import * as THREE from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { dirFromAltAz, equatorialToWorld, NA_HIKU } from './sky.js';
import { nightCameraPath } from './video.js';

const FT = 0.3048;
const STARS = [[165.93, 61.75], [165.46, 56.38], [178.46, 53.69], [183.86, 57.03], [193.51, 55.96], [200.98, 54.93], [206.89, 49.31]];

export async function exportForBlender({ scene, plan, terrainH, lamps, siteLayout, groundAt }) {
  const meta = { units: 'm', views: {}, night: { frames: [], fps: 24 }, lamps: [], rooms: [], pool: plan.site?.pool, palms: plan.site?.palms ?? [] };
  const cam = new THREE.PerspectiveCamera(70, 16 / 9, 0.25, 40000);
  const toM = v => [v.x * FT, v.y * FT, v.z * FT];
  for (const v of plan.viewpoints) {
    const g = groundAt(v.pos[0], v.pos[1]);
    const p = new THREE.Vector3(v.pos[0], v.absolute ? v.eye : g + (v.eye ?? 5.4), v.pos[1]);
    const t = new THREE.Vector3(v.look[0], v.lookH ?? p.y - 0.4, v.look[1]);
    const [alt, az] = v.sun ?? plan.sun ?? [50, 230];
    meta.views[v.id] = { pos: toM(p), target: toM(t), fov: v.fov ?? 70, sunDir: dirFromAltAz(alt, az).toArray(), interior: !v.sun };
  }
  // night film camera, frame by frame
  const north = siteLayout(plan).north, date = new Date(plan.night?.date ?? '2026-03-20T07:00:00Z');
  const center = STARS.map(([ra, de]) => equatorialToWorld(ra, de, date, { north })).reduce((s, v) => s.add(v), new THREE.Vector3()).normalize();
  const move = nightCameraPath(cam, { center }, terrainH);
  const n = 24 * 16;
  for (let i = 0; i < n; i++) { move(i / (n - 1)); meta.night.frames.push({ pos: toM(cam.position), quat: cam.quaternion.toArray() }); }
  meta.night.fov = 58; meta.night.date = date.toISOString(); meta.night.north = north;
  // lamps (pendants, globes) and the warm fill in the main rooms
  scene.updateMatrixWorld(true);
  for (const l of lamps) { const w = new THREE.Vector3(); l.getWorldPosition(w); meta.lamps.push({ pos: toM(w), power: l.userData.nightIntensity }); }
  for (const r of plan.rooms.filter(r => !r.label_only && (!r.outdoor || r.covered))) {
    const xs = r.polygon.map(p => p[0]), ys = r.polygon.map(p => p[1]);
    meta.rooms.push({ id: r.id, rect: [Math.min(...xs) * FT, Math.min(...ys) * FT, Math.max(...xs) * FT, Math.max(...ys) * FT], ceiling: (typeof r.ceiling === 'number' ? r.ceiling : 10) * FT, outdoor: !!r.outdoor });
  }
  // palms: ours (house 0) and the same planting on every other Na Hiku lot
  const offsets = [[0, 0, 0], ...(window.__neighborhood?.offsets ?? [])];
  meta.palms = [];
  offsets.forEach(([dx, dy, dz], house) => {
    for (const p of globalThis.__palmProxies ?? []) meta.palms.push({
      house, kind: p.kind, seed: Math.round(p.x * 13 + p.y * 7 + p.seed) + house * 1000,
      base: [(p.x + dx) * FT, (p.ground + dy) * FT, (p.y + dz) * FT], height: p.height * FT, trunkR: p.trunkR * FT, frondLen: p.frondLen, lean: p.lean,
    });
  });

  // geometry: drop helpers that glTF can't carry or Blender replaces (sky, lights, stars)
  const root = new THREE.Group(); root.name = 'nahiku'; root.scale.setScalar(FT);
  const keep = [];
  for (const o of [...scene.children]) {
    if (o.isLight || o.isCamera || o.type === 'Sky') continue;
    let bad = false; o.traverse(c => { if (c.material?.isShaderMaterial || c.isPoints || c.isLine) bad = true; });
    if (bad && o.isMesh) continue;
    keep.push(o);
  }
  for (const o of keep) { o.traverse(c => { if (c.isLight) c.visible = false; if (c.isMesh && c.material?.isShaderMaterial) c.visible = false; }); root.add(o); }
  scene.add(root);
  // the lawn shader cuts the pools out per pixel; for export, cut the triangles instead
  const holes = plan.site?.holes ?? [];
  root.traverse(o => {
    if (!o.isMesh || o.material?.name !== 'terrain' || !o.geometry.index) return;
    const pos = o.geometry.attributes.position, idx = o.geometry.index.array, keep = [];
    for (let i = 0; i < idx.length; i += 3) {
      let cx = 0, cz = 0; for (let k = 0; k < 3; k++) { cx += pos.getX(idx[i + k]) / 3; cz += pos.getZ(idx[i + k]) / 3; }
      const inHole = holes.some(([x0, y0, x1, y1]) => cx > x0 - 1.5 && cx < x1 + 1.5 && cz > y0 - 1.5 && cz < y1 + 1.5);
      if (!inHole) keep.push(idx[i], idx[i + 1], idx[i + 2]);
    }
    o.geometry.setIndex(keep);
  });
  // the exporter reads canvases, not raw pixel arrays: give every DataTexture a canvas image
  const done = new Map();
  root.traverse(o => {
    if (!o.isMesh) return;
    for (const m of [].concat(o.material)) for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap', 'aoMap', 'alphaMap']) {
      const t = m[k];
      if (!t || !t.image || !t.image.data || t.image instanceof HTMLCanvasElement) continue;
      if (!done.has(t.image)) {
        const { data, width, height } = t.image, c = document.createElement('canvas'); c.width = width; c.height = height;
        c.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(data.buffer, data.byteOffset, data.byteLength), width, height), 0, 0);
        done.set(t.image, c);
      }
      const nt = new THREE.CanvasTexture(done.get(t.image));
      nt.wrapS = t.wrapS; nt.wrapT = t.wrapT; nt.repeat.copy(t.repeat); nt.offset.copy(t.offset); nt.flipY = t.flipY; nt.colorSpace = t.colorSpace; nt.name = t.name;
      m[k] = nt;
    }
  });
  const glb = await new GLTFExporter().parseAsync(root, { binary: true, onlyVisible: true, maxTextureSize: 2048 });
  download(new Blob([glb], { type: 'model/gltf-binary' }), 'nahiku.glb');
  download(new Blob([JSON.stringify(meta)], { type: 'application/json' }), 'nahiku-meta.json');
}

function download(blob, name) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.append(a); a.click();
}
