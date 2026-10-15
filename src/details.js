// Real-life details: the fixtures, hardware, utilities and styling a finished, lived-in house has
// (docs/real-life-details.md). Exterior kinds live in details_ext.js, interior kinds in
// details_int.js; plan.details lists the placed items ({ type, x, y, rot, elevation, ... }).
import * as THREE from 'three';
import { EXT } from './details_ext.js';
import { INT } from './details_int.js';

export function buildDetails(plan, ctx) {
  const g = new THREE.Group(); g.name = 'details';
  for (const item of plan.details ?? []) {
    const make = EXT[item.type] ?? INT[item.type];
    if (!make) { console.warn('unknown detail', item.type); continue; }
    const m = make(item, ctx);
    if (!m) continue;
    if (EXT[item.type]) m.traverse(o => { o.userData.shell = true; });   // exterior details repeat on the other Na Hiku homes
    g.add(m);
  }
  return g;
}
