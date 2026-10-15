// Bakes the exterior of our house and garden (everything tagged userData.shell) into one merged
// geometry per material, in world space — the template the other Na Hiku homes are instanced from.
// Loose outdoor furniture (chaises and loungers, outdoor dining and lounge pieces, cushions, towels) is left
// out: only our lot is staged; a neighbour's chaise next to our lot line read as part of our yard
// (critique-preview3-back #5). Staged = a userData.staged / userData.furniture flag on the object or a parent,
// or a furniture finish (STAGED below).
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const STAGED = /^(teak|linen|cushion|towel|pillow|rattan|cane|jute|throw|umbrella|parasol)/i;
const stagedObject = o => { for (let p = o; p; p = p.parent) if (p.userData.staged || p.userData.furniture) return true; return false; };
const stagedMaterial = m => STAGED.test((m?.userData?.base ?? m)?.name ?? '');

export function bakeShell(root) {
  root.updateMatrixWorld(true);
  const buckets = new Map();
  const put = (material, geo) => {
    const base = material.userData.base ?? material;   // roof materials carry a world-space clip; copies use the plain one
    if (!buckets.has(base.uuid)) buckets.set(base.uuid, { material: base, parts: [] });
    buckets.get(base.uuid).parts.push(geo);
  };
  const tagged = [];
  root.traverse(o => { if (o.userData.shell) tagged.push(o); });
  const seen = new Set();
  for (const t of tagged) t.traverse(o => {
    if (!o.isMesh || o.isInstancedMesh || seen.has(o)) return;
    seen.add(o);
    if (stagedObject(o) || (!Array.isArray(o.material) && stagedMaterial(o.material))) return;
    let g = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone();
    g.applyMatrix4(o.matrixWorld);
    const keep = ['position', 'normal', 'uv', ...(o.material.vertexColors ? ['color'] : [])];
    for (const k of Object.keys(g.attributes)) if (!keep.includes(k)) g.deleteAttribute(k);
    if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    if (!g.attributes.normal) g.computeVertexNormals();
    if (Array.isArray(o.material)) {
      for (const gr of g.groups) {
        if (stagedMaterial(o.material[gr.materialIndex])) continue;
        const part = new THREE.BufferGeometry();
        for (const k of Object.keys(g.attributes)) { const a = g.attributes[k]; part.setAttribute(k, new THREE.BufferAttribute(a.array.slice(gr.start * a.itemSize, (gr.start + gr.count) * a.itemSize), a.itemSize)); }
        put(o.material[gr.materialIndex], part);
      }
    } else { g.clearGroups(); put(o.material, g); }
  });
  const out = [];
  for (const { material, parts } of buckets.values()) {
    const sig = p => Object.keys(p.attributes).sort().join();
    const bySig = new Map();
    for (const p of parts) { const k = sig(p); if (!bySig.has(k)) bySig.set(k, []); bySig.get(k).push(p); }
    for (const ps of bySig.values()) { const geometry = mergeGeometries(ps); if (geometry) out.push({ geometry, material }); }
  }
  return out;
}
