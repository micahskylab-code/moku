// The Na Hiku neighbourhood and its surroundings.
//
// Na Hiku is a row of fourteen homesites between the Na Hiku access road and fairway 7 of the
// Kukui'ula golf course. Lots 24 and 25 in Aepo Nei are where the developer drew the spec designs;
// this house goes on one of the fourteen. The other thirteen are built as the same spec design
// (instanced copies of our house's exterior and garden).
//
// Around them is the real place (src/realsite.js, geodata/): USGS lidar terrain and a Sentinel-2
// colour mosaic of south Kaua'i, OpenStreetMap roads, buildings and ponds. The row of lots is
// registered on the real Na Hiku strip, graded in 2025-26 and visible as bare soil in every clear
// Sentinel-2 scene since (scripts/geo_register.py): lots run north-west to south-east, ~70 ft apart,
// backs to the fairway in the south-west. Our lot is the seventh from the north-west end.
//
// If geodata/ is missing the neighbourhood falls back to the painted site plan below (pixels on the
// site-plan view, 1918 x 1524, ~1.66 ft per px): golf holes, ponds, field and massing homes. That
// painting is not to scale or to north (it is turned ~15-20 deg and squeezed), so with the real
// site loaded only the lots and the access road come from it.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { mat } from './materials.js';
import { loadRealSite, loadFeatures, blendModelledGround } from './realsite.js';

const K = 1.66;                                         // ft per site-plan px (painted plan)
export const NA_HIKU_LOTS = Array.from({ length: 14 }, (_, i) => [974 + (1419 - 974) * i / 13, 534 + (719 - 534) * i / 13]);
const OUR_LOT = 6;                                      // which of the fourteen (0 = north-west end)
const BACK = [-0.42, 0.91];                             // lot axis on the site plan, street -> fairway
// Real lot pitch along the row: the 2026 grading is ~340 m long for fourteen lots plus the road's turn
// down to the main road (scripts/geo_register.py).
// The painted plan gives 61.5 ft, exactly the lot width, i.e. no side yards at all.
export const LOT_PITCH = 70;
// Registration: grid bearing of world +x (the lot axis, fairway -> street) and UTM grid convergence.
// True north on the plan follows from them (see scripts/geo_common.py; geodata/realsite.json repeats it).
const X_BEARING = 46.3, CONVERGENCE = -0.18;
const TRUE_NORTH = (() => { const b = (X_BEARING + CONVERGENCE) * Math.PI / 180; return [Math.cos(b), -Math.sin(b)]; })();

const ROADS = [
  [[1045, 515], [1150, 535], [1280, 585], [1380, 640], [1435, 690], [1465, 760], [1490, 830], [1510, 880]],  // Na Hiku access road
  [[0, 795], [230, 760], [430, 640], [560, 650], [800, 760], [1000, 820], [1200, 850], [1490, 880], [1918, 905]], // main road
  [[430, 640], [330, 560], [270, 420], [220, 250], [130, 170], [20, 200]],                                       // Ala Haku Lei Loop
  [[760, 760], [900, 790], [1050, 830], [1120, 850]],                                                            // Kaimalino Pl
  [[230, 760], [300, 900], [330, 1000], [420, 1100], [600, 1140], [700, 1130]],                                  // Kahela / Pua Makalae
  [[100, 900], [300, 900]], [[110, 560], [230, 520], [300, 500]],
];
const HOLES = [
  { path: [[470, 330], [600, 470], [760, 600], [950, 690], [1150, 760], [1300, 790]], width: 95, green: [1330, 800, 26], bunkers: [[820, 640, 14], [1000, 720, 12], [1270, 770, 10]] },  // 7
  { path: [[410, 230], [385, 380], [420, 500]], width: 80, green: [440, 530, 22], bunkers: [[370, 440, 10], [460, 470, 9]] },                                                         // 8
  { path: [[620, 700], [690, 900], [760, 1100]], width: 100, green: [790, 1160, 24], bunkers: [[700, 980, 10]] },                                                                      // 9
  { path: [[1600, 150], [1640, 350], [1680, 560]], width: 90, green: [1700, 600, 24], bunkers: [[1650, 450, 10]] },                                                                   // 6
  { path: [[1820, 120], [1840, 330], [1850, 520]], width: 85, green: [1860, 560, 22], bunkers: [[1830, 400, 9]] },                                                                    // 5
  { path: [[60, 1250], [300, 1330], [520, 1380]], width: 100, green: [560, 1400, 24], bunkers: [[420, 1350, 12]] },                                                                   // 10/18
];
const PONDS = [
  [[1140, 740], [1230, 735], [1300, 770], [1290, 800], [1200, 790], [1150, 770]],
  [[1290, 790], [1400, 800], [1440, 840], [1370, 850], [1300, 825]],
  [[1520, 800], [1600, 700], [1700, 660], [1760, 700], [1720, 800], [1600, 840]],
  [[880, 1040], [960, 1050], [1000, 1150], [950, 1200], [900, 1120]],
  [[940, 1300], [1060, 1310], [1080, 1360], [960, 1370]],
];
const FIELD = [[420, 0], [1460, 0], [1450, 640], [1430, 660], [1045, 500], [900, 510], [560, 330], [420, 170]];
const HOMES = [
  // Kaimalino A-L
  [640, 705], [676, 735], [705, 765], [733, 800], [768, 830], [795, 860], [832, 840], [875, 850], [920, 860], [965, 875], [1010, 890],
  // Kaupili 19A-G
  [330, 800], [380, 790], [420, 775], [465, 770], [480, 740], [490, 705], [505, 670],
  // Kahela 1-17
  [370, 880], [455, 890], [530, 885], [150, 1005], [215, 995], [280, 985], [385, 1000], [455, 1030], [520, 1050], [590, 1055],
  [285, 1120], [372, 1150], [442, 1180], [510, 1200], [580, 1215], [662, 1220], [742, 1215],
  // Aepo Nei (upper left)
  [195, 65], [155, 80], [120, 95], [85, 105], [45, 115], [352, 150], [310, 160], [270, 170], [237, 185], [210, 205], [185, 230], [175, 268],
  [75, 250], [90, 310], [118, 370], [128, 430], [110, 470], [75, 485], [30, 500], [20, 380], [265, 580], [235, 605], [200, 630], [165, 650], [125, 665], [265, 40], [230, 55],
];
// The Club villas (red roofs) and cottages (blue roofs).
const VILLAS = Array.from({ length: 16 }, (_, i) => [800 + i * 23, 885 + i * 23]);
const COTTAGES = Array.from({ length: 24 }, (_, i) => [1420 + (i % 8) * 60, 1180 + Math.floor(i / 8) * 70]);

export function siteLayout(plan) {
  const S = plan.site ?? {};
  const lot = S.lot ?? [-34, -45, 150, 86];
  const P = [(lot[0] + lot[2]) / 2, (lot[1] + lot[3]) / 2];
  const ref = NA_HIKU_LOTS[OUR_LOT];
  // rotate so the lot's fairway -> street direction on the site plan becomes our +x
  const th = -Math.atan2(-BACK[1], -BACK[0]), c = Math.cos(th), s = Math.sin(th);
  const raw = ([x, y]) => { const dx = (x - ref[0]) * K, dy = (y - ref[1]) * K; return [P[0] + dx * c - dy * s, P[1] + dx * s + dy * c]; };
  // pin the Na Hiku access road to our frontage (the drawing is a painting; the lot is to scale)
  const road = ROADS[0].map(raw);
  let rx = null;
  for (let i = 0; i < road.length - 1 && rx === null; i++) { const [a, b] = [road[i], road[i + 1]]; if ((a[1] - P[1]) * (b[1] - P[1]) <= 0) rx = a[0] + (b[0] - a[0]) * (P[1] - a[1]) / ((b[1] - a[1]) || 1); }
  const roadX = S.roadX ?? lot[2] + 13;
  const shift = roadX - (rx ?? lot[2] + 13);
  const toPlan = p => { const [x, y] = raw(p); return [x + shift, y]; };
  // the fourteen lots: a straight row along z (the real strip is straight), LOT_PITCH apart
  const lots = NA_HIKU_LOTS.map((_, i) => [P[0], P[1] + (i - OUR_LOT) * LOT_PITCH]);
  const z0 = lots[0][1] - (lot[3] - lot[1]) / 2, z1 = lots[13][1] + (lot[3] - lot[1]) / 2;
  // Na Hiku access road along the street side of the row; at the south-east end it turns down to
  // the main road (realsite joins it to the real road; the painted plan has it run on south)
  const access = [[roadX, z0 - 40], [roadX, z1 + 30], [roadX - 25, z1 + 140], [roadX - 70, z1 + 330]];
  // the rectangle left to the modelled neighbourhood when the real site is loaded
  const keep = [lot[0] - 45, z0 - 45, roadX + 45, z1 + 45];   // keep in step with scripts/geo_common.py keep_rect()
  // every other lot from ours is the spec design mirrored across its own lot centreline (plan y -> 2 axisY - y,
  // before the lot offset), as spec rows are built: the copies next door are mirror images, not repeats
  const others = lots.map((_, i) => i).filter(i => i !== OUR_LOT);
  return {
    toPlan, lot, keep, lots, ourLot: OUR_LOT,
    nahiku: others.map(i => lots[i]),
    nahikuLot: others,                                  // which of the fourteen each entry of nahiku is
    nahikuMirror: others.map(i => Math.abs(i - OUR_LOT) % 2 === 1),
    axisY: P[1],                                        // our lot's centreline (plan y): the mirror axis, before the offset
    streets: [access, ...ROADS.slice(1).map(l => l.map(toPlan))],
    homes: HOMES.map(toPlan),
    villas: VILLAS.map(toPlan), cottages: COTTAGES.map(toPlan),
    golf: HOLES.map(h => ({ path: h.path.map(toPlan), width: h.width * K, green: [...toPlan(h.green), h.green[2] * K], bunkers: h.bunkers.map(b => [...toPlan(b), b[2] * K]) })),
    fields: [FIELD.map(toPlan)],
    ponds: PONDS.map(p => p.map(toPlan)),
    north: TRUE_NORTH,                                  // true north on our plan, from the registration on the real site
    planNorth: [s, -c],                                 // the painted site plan's "up" (was used as north before)
  };
}

export async function buildNeighborhood(plan, scene, H, shell) {
  const L = siteLayout(plan);
  const g = new THREE.Group(); g.name = 'neighbourhood';
  const homesG = new THREE.Group(); homesG.name = 'nahiku-homes'; g.add(homesG);   // the other homes (hidden in the model view)
  const params = new URLSearchParams(location.search);
  const low = (params.get('q') ?? (matchMedia('(pointer: coarse)').matches ? 'low' : 'high')) === 'low';
  const real = params.get('real') === '0' ? null : await loadRealSite('geodata/', { low });
  const center = [(L.lot[0] + L.lot[2]) / 2, (L.lot[1] + L.lot[3]) / 2];

  // The other thirteen Na Hiku homes: copies of our exterior + garden (src/shell.js, no staged furniture). Every
  // other lot is the mirrored variant (its own mirrored geometry, translation-only matrices, so winding, normals
  // and culling stay right in three.js, glTF and Cycles); each home has its own roof paint value, body white and
  // shutter / garage-door stain (LOT_FINISH below), the architecture unchanged.
  const offsets = shell ? L.nahiku.map(([x, y]) => [x - center[0], H(x, y) - H(...center), y - center[1]]) : [];
  const mirror = shell ? L.nahikuMirror : [];
  const finishes = shell ? L.nahikuLot.map(neighbourFinish) : [];
  if (shell) {
    const homes = offsets.map((o, k) => ({ k, lot: L.nahikuLot[k], mirror: mirror[k], m: new THREE.Matrix4().makeTranslation(...o) }));
    const flipped = new Map(), variants = new Map();
    const geoFor = (geo, mir) => { if (!mir) return geo; if (!flipped.has(geo)) flipped.set(geo, mirrorGeometry(geo, L.axisY)); return flipped.get(geo); };
    for (const { geometry, material } of shell) {
      const fam = FINISH_FAMILY[material.name];
      for (const mir of [false, true]) {
        const set = homes.filter(h => h.mirror === mir);
        if (!set.length) continue;
        const geo = geoFor(geometry, mir);
        if (fam) {
          // finishes that differ house to house: one mesh per home sharing the geometry, its own material
          for (const h of set) {
            const key = `${material.uuid}:${h.lot}`;
            if (!variants.has(key)) variants.set(key, finishVariant(material, fam, finishes[h.k], h.lot));
            const mesh = new THREE.Mesh(geo, variants.get(key));
            mesh.matrixAutoUpdate = false; mesh.matrix.copy(h.m);
            mesh.castShadow = mesh.receiveShadow = true;
            homesG.add(mesh);
          }
        } else {
          const inst = new THREE.InstancedMesh(geo, material, set.length);
          set.forEach((h, i) => inst.setMatrixAt(i, h.m));
          inst.castShadow = inst.receiveShadow = true;
          inst.frustumCulled = false;
          homesG.add(inst);
        }
      }
    }
  }
  const hood = { layout: L, offsets, mirror, axis: L.axisY, lots: shell ? L.nahikuLot : [], finishes };

  if (real) {
    // The real place takes over outside the modelled neighbourhood (L.keep).
    const t0 = performance.now();
    const [terrain] = await Promise.all([real.build({ keep: L.keep, H, blend: 320 }), loadFeatures(real)]);
    g.add(terrain);
    const t1 = performance.now();
    const ground = (x, z) => real.ground(x, z, H);
    const w = L.lot[3] - L.lot[1], roadX = L.streets[0][0][0];
    const lotsRect = [L.lot[0] - 8, L.lots[0][1] - w / 2 - 6, roadX + 2, L.lots[13][1] + w / 2 + 6];
    handOver(scene, L.keep, real, lotsRect);
    g.add(roads([joinAccessRoad(L.streets[0], real)], ground, 22));
    const b = real.buildings({ maxDist: low ? 12000 : Infinity, centre: center }); if (b) g.add(b);
    const t = real.trees(); if (t) g.add(t);
    window.__realsite = real;
    console.info(`[realsite] terrain ${real.tris} tris ${(t1 - t0).toFixed(0)} ms (${JSON.stringify(real.timing)}), ${real.buildingCount ?? 0} buildings, ${real.treeCount ?? 0} trees, total ${(performance.now() - t0).toFixed(0)} ms; sea level ${real.seaLevel.toFixed(1)} ft`);
    scene.add(g);
    window.__neighborhood = { ...hood, real, homes: homesG, night: () => real.night(true) };
    return g;
  }

  // ---- fallback: the painted site plan ----
  g.add(roads(L.streets, H));
  g.add(ponds(L.ponds, H));
  // Everything else: light massing in the same architecture, merged into a few draw calls.
  const walls = [], roofs = [], glass = [], pools = [], redRoofs = [], blueRoofs = [];
  const rnd = mulberry(7);
  const face = ([x, y]) => {
    let best = null;
    for (const line of L.streets) for (let i = 0; i < line.length - 1; i++) { const q = nearest([x, y], line[i], line[i + 1]); if (!best || q.d < best.d) best = q; }
    return Math.atan2(best.p[1] - y, best.p[0] - x);
  };
  for (const p of L.homes) house(p, face(p), H(...p), rnd, { walls, roofs, glass, pools });
  for (const p of L.villas) cottage(p, face(p), H(...p), { walls, roofs: redRoofs, glass });
  for (const p of L.cottages) cottage(p, face(p), H(...p), { walls, roofs: blueRoofs, glass });
  const add = (parts, m) => { if (!parts.length) return null; const mesh = new THREE.Mesh(mergeGeometries(parts), m); mesh.castShadow = mesh.receiveShadow = true; g.add(mesh); return mesh; };
  add(walls, mat('siding'));
  add(roofs, mat('roof'));
  // muted bronze and slate metal, as on the built Kukui'ula homes (not toy red and blue)
  add(redRoofs, new THREE.MeshStandardMaterial({ name: 'roof bronze', color: '#5e5249', roughness: 0.55, metalness: 0.2 }));
  add(blueRoofs, new THREE.MeshStandardMaterial({ name: 'roof slate', color: '#5d666d', roughness: 0.5, metalness: 0.2 }));
  const win = new THREE.MeshStandardMaterial({ color: '#6f8796', roughness: 0.08, metalness: 0.2, emissive: '#ffc77a', emissiveIntensity: 0 });
  add(glass, win);
  const poolMat = new THREE.MeshStandardMaterial({ color: '#2aa0bf', roughness: 0.1, emissive: '#0b7fa3', emissiveIntensity: 0 });
  add(pools, poolMat);
  scene.add(g);
  window.__neighborhood = { ...hood, homes: homesG, night: () => { win.emissiveIntensity = 0.9; poolMat.emissiveIntensity = 0.8; } };
  return g;
}

// With the real site loaded, the procedural ground and planting of site.js stay only inside keep:
// the terrain mesh is trimmed to it (plus a margin the real rings slide under), the background tree
// clumps and skyline palms outside it are dropped (they stood on invented ground), and the flat
// ocean plane goes (the real coast and sea are in the real terrain).
function handOver(scene, keep, real, lotsRect) {
  const m = 40, inside = (x, z, k = m) => x > keep[0] - k && x < keep[2] + k && z > keep[1] - k && z < keep[3] + k;
  const zero = new THREE.Matrix4().makeScale(0, 0, 0), mm = new THREE.Matrix4(), v = new THREE.Vector3();
  scene.traverse(o => {
    if (o.isMesh && o.material?.name === 'terrain' && o.geometry.index) {
      const pos = o.geometry.attributes.position, idx = o.geometry.index.array, keepIdx = [];
      for (let i = 0; i < idx.length; i += 3) {
        let cx = 0, cz = 0; for (let k = 0; k < 3; k++) { cx += pos.getX(idx[i + k]) / 3; cz += pos.getZ(idx[i + k]) / 3; }
        if (inside(cx, cz)) keepIdx.push(idx[i], idx[i + 1], idx[i + 2]);
      }
      o.geometry.setIndex(keepIdx);
      o.geometry.computeBoundingSphere();
      blendModelledGround(o, real, lotsRect);
    } else if (o.isMesh && o.material?.name === 'ocean') {
      o.visible = false;
    } else if (o.isInstancedMesh && !o.userData.realsite) {
      // site.js scatter trees and palms (instances far outside the lots)
      let changed = false;
      o.updateWorldMatrix(true, false);
      for (let i = 0; i < o.count; i++) {
        o.getMatrixAt(i, mm); v.setFromMatrixPosition(mm).applyMatrix4(o.matrixWorld);
        if (!inside(v.x, v.z, 0)) { o.setMatrixAt(i, zero); changed = true; }
      }
      if (changed) { o.instanceMatrix.needsUpdate = true; o.computeBoundingSphere?.(); }
    }
  });
  // the same for the path tracer's recorded background trees
  const rec = globalThis.__plantProxies;
  if (rec) for (let i = rec.length - 1; i >= 0; i--) {
    const p = rec[i];
    if ((p.type === 'tree' || p.type === 'farpalm') && !inside(p.x, p.y, 0)) rec.splice(i, 1);
  }
}

// ---- the other homes' own finishes (same spec architecture, owner-chosen paint and stain) ----
// Each is a multiplier (scene-linear) on our finish, so textures and recipes stay: the standing-seam roof paint
// (pans, ribs and caps, fascia, gable vents, flashing) +-5% in sRGB value; the body white of the lap siding and
// battens from the range of common exterior whites (LRV ~82-92, warm to cool; trim stays crisp white); the
// semi-transparent stain on the cedar shutters and carriage garage door. The variant material keeps our
// material's name plus '.<lot>' (scripts/materials_bpy.py base_name() finds the same recipe) and carries the
// multiplier to Blender as glTF extras: nhFinish (family), nhTint (linear rgb).
const FINISH_FAMILY = { roof: 'roof', roofSeam: 'roof', fascia: 'roof', gableLouver: 'roof', flashing: 'roof',
  siding: 'body', batten: 'body', shutterCedar: 'stain', cedar: 'stain' };
const BODY_WHITES = ['#f4f2ec',                  // ours (as src/materials.js siding)
  '#f1efe4', '#eeefea', '#f2efe1', '#ece9df', '#f5f5f1'];  // warm white, cool / extra white, creamy, greige-white (LRV ~82), bright white
const STAINS = ['#8a6040',                       // ours: natural cedar (as src/walls.js shutter)
  '#6e4a33', '#857a6c', '#9a6b45', '#7a4b36'];   // walnut, driftwood grey, honey teak, chestnut
// per lot (0 = north-west end; 6 is ours): sRGB roof value, body white, stain. Neighbours side by side never share
// a roof value, and the two next to ours differ from it in all three.
const LOT_FINISH = [
  [1.03, 3, 2], [0.96, 1, 3], [1.05, 4, 1], [0.98, 2, 4], [1.04, 5, 0], [0.95, 2, 1], [1, 0, 0],
  [1.05, 4, 2], [0.97, 1, 4], [1.03, 3, 1], [0.95, 5, 3], [1.02, 2, 0], [0.96, 4, 2], [1.04, 1, 4],
];
function neighbourFinish(lot) {
  const [roof, body, stain] = LOT_FINISH[lot] ?? [1, 0, 0];
  return { roof, body: BODY_WHITES[body], stain: STAINS[stain] };
}
function finishVariant(material, fam, f, lot) {
  const ratio = (a, b) => { const A = new THREE.Color(a), B = new THREE.Color(b); return new THREE.Color(A.r / B.r, A.g / B.g, A.b / B.b); };
  const tint = fam === 'roof' ? new THREE.Color().setScalar(Math.pow(f.roof, 2.2))
    : fam === 'body' ? ratio(f.body, BODY_WHITES[0]) : ratio(f.stain, STAINS[0]);
  const v = material.clone();
  v.color.multiply(tint);
  v.name = `${material.name}.${lot}`;
  v.userData = { ...v.userData, nhFinish: fam, nhTint: tint.toArray().map(x => Math.round(x * 1e4) / 1e4) };
  return v;
}

// A merged shell geometry mirrored across plan y = axis (three.js z): positions and normals reflected, triangle
// winding reversed so front faces stay front faces (a negative-scale instance matrix would turn them inside out).
function mirrorGeometry(src, axis) {
  const geo = src.clone();
  const p = geo.attributes.position, n = geo.attributes.normal;
  for (let i = 0; i < p.count; i++) p.setZ(i, 2 * axis - p.getZ(i));
  if (n) for (let i = 0; i < n.count; i++) n.setZ(i, -n.getZ(i));
  if (geo.index) {
    const a = geo.index.array;
    for (let i = 0; i < a.length; i += 3) { const t = a[i + 1]; a[i + 1] = a[i + 2]; a[i + 2] = t; }
  } else {
    for (const attr of Object.values(geo.attributes)) {
      const s = attr.itemSize, a = attr.array;
      for (let t = 0; t + 2 < attr.count; t += 3) for (let c = 0; c < s; c++) {
        const i1 = (t + 1) * s + c, i2 = (t + 2) * s + c, tmp = a[i1]; a[i1] = a[i2]; a[i2] = tmp;
      }
    }
  }
  geo.computeBoundingBox(); geo.computeBoundingSphere();
  return geo;
}

// The access road runs on past the end of the row and down to the real road network: end it on the
// nearest point of a real road (realsite roads), or leave it as drawn.
function joinAccessRoad(line, real) {
  const end = line[line.length - 1], hit = real.nearestRoad?.(end[0], end[1], 600);
  return hit ? [...line.slice(0, -1), hit] : line;
}

// Two or three wings of white siding under grey hip roofs, windows, a pool behind.
function house([x, y], ang, ground, rnd, out) {
  const m = new THREE.Matrix4().makeRotationY(-ang).setPosition(x, ground, y);
  const blocks = [[0, 0, 46 + rnd() * 14, 26 + rnd() * 6]];
  blocks.push([-6 - rnd() * 8, (rnd() > 0.5 ? 1 : -1) * (20 + rnd() * 6), 30 + rnd() * 10, 16]);
  if (rnd() > 0.4) blocks.push([18 + rnd() * 6, (rnd() > 0.5 ? 1 : -1) * -22, 18, 20]);
  for (const [bx, by, w, d] of blocks) {
    const body = new THREE.BoxGeometry(d, 10.6, w); body.translate(bx, 4.7, by); setUV(body); out.walls.push(body.applyMatrix4(m));
    out.roofs.push(hipRoof(d, w, 2.2, 0.55).translate(bx, 10, by).applyMatrix4(m));
    for (const sd of [-1, 1]) for (let k = 0; k < Math.floor(w / 9); k++) {
      const p = new THREE.PlaneGeometry(3.2, 5.5); p.rotateY(sd > 0 ? Math.PI / 2 : -Math.PI / 2);
      p.translate(bx + sd * (d / 2 + 0.05), 4.5, by - w / 2 + 6 + k * 9); out.glass.push(p.applyMatrix4(m));
    }
  }
  const pool = new THREE.BoxGeometry(14, 0.3, 30); pool.translate(-34, 0.0, 0); out.pools.push(pool.applyMatrix4(m));
}
function cottage([x, y], ang, ground, out) {
  const m = new THREE.Matrix4().makeRotationY(-ang).setPosition(x, ground, y);
  const body = new THREE.BoxGeometry(22, 9.5, 30); body.translate(0, 4.2, 0); setUV(body); out.walls.push(body.applyMatrix4(m));
  out.roofs.push(hipRoof(22, 30, 2, 0.6).translate(0, 9, 0).applyMatrix4(m));
  const p = new THREE.PlaneGeometry(6, 6); p.rotateY(Math.PI / 2); p.translate(11.05, 4.2, 0); out.glass.push(p.applyMatrix4(m));
}

function hipRoof(d, w, o, pitch) {
  const X = d / 2 + o, Z = w / 2 + o, h = Math.min(X, Z) * pitch, r = Math.max(0, Z - X), q = Math.max(0, X - Z);
  const v = [[-X, 0, -Z], [X, 0, -Z], [X, 0, Z], [-X, 0, Z], [-q, h, -r], [q, h, r]];
  const faces = [[0, 4, 1], [1, 4, 5], [1, 5, 2], [2, 5, 3], [3, 5, 4], [3, 4, 0]];
  const pos = [], uv = [];
  for (const f of faces) for (const i of f) { pos.push(...v[i]); uv.push(v[i][2], v[i][0] + v[i][1]); }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  return g;
}
function setUV(geo) {
  const p = geo.attributes.position, n = geo.attributes.normal, uv = geo.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, Math.abs(n.getX(i)) > 0.5 ? p.getZ(i) : p.getX(i), p.getY(i));
}

// One continuous asphalt ribbon per road line, draped on the ground 0.35 ft up (stations every ~4 ft, five
// points across, mitred at the bends), with a rolled apron down into the ground along both edges and at the
// ends. (Flat 16 ft planes stepped at different heights left open risers that rendered as black slots.)
function roads(lines, H, width = 24) {
  const pos = [], uv = [], idx = [], C = 4, LIFT = 0.35;
  const vert = (x, y, z, u, v) => { pos.push(x, y, z); uv.push(u, v); return pos.length / 3 - 1; };
  // triangle a b c, wound so its normal points along `want` (world vector)
  const tri = (a, b, c, want) => {
    const P = i => [pos[3 * i], pos[3 * i + 1], pos[3 * i + 2]], A = P(a), B = P(b), Cc = P(c);
    const u = [B[0] - A[0], B[1] - A[1], B[2] - A[2]], v = [Cc[0] - A[0], Cc[1] - A[1], Cc[2] - A[2]];
    const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    if (n[0] * want[0] + n[1] * want[1] + n[2] * want[2] >= 0) idx.push(a, b, c); else idx.push(a, c, b);
  };
  const quad = (a, b, c, d, want) => { tri(a, b, c, want); tri(a, c, d, want); };
  for (const line0 of lines) {
    const line = line0.filter((p, i) => i === 0 || Math.hypot(p[0] - line0[i - 1][0], p[1] - line0[i - 1][1]) > 0.01);
    if (line.length < 2) continue;
    // stations: [x, y, tx, ty, miter, s]
    const st = [];
    let s = 0;
    for (let i = 0; i < line.length - 1; i++) {
      const [ax, ay] = line[i], [bx, by] = line[i + 1], len = Math.hypot(bx - ax, by - ay), n = Math.max(1, Math.ceil(len / 4));
      const tx = (bx - ax) / len, ty = (by - ay) / len;
      for (let k = i === 0 ? 0 : 1; k <= n; k++) {
        let dx = tx, dy = ty, m = 1;
        if (k === n && i < line.length - 2) {                    // a bend: mitre on the bisector
          const [cx, cy] = line[i + 2], l2 = Math.hypot(cx - bx, cy - by), ux = (cx - bx) / l2, uy = (cy - by) / l2;
          const hx = tx + ux, hy = ty + uy, hl = Math.hypot(hx, hy);
          if (hl > 1e-6) { dx = hx / hl; dy = hy / hl; m = Math.min(2, 1 / Math.max(0.5, dx * tx + dy * ty)); }
        }
        st.push([ax + (bx - ax) * k / n, ay + (by - ay) * k / n, dx, dy, m, s + len * k / n]);
      }
      s += len;
    }
    // the deck: (C + 1) points across each station, each on the ground below it
    const deck = st.map(([x, y, dx, dy, m, sv]) => {
      const row = [];
      for (let j = 0; j <= C; j++) {
        const o = (j / C - 0.5) * width * m, px = x - dy * o, py = y + dx * o;
        row.push(vert(px, H(px, py) + LIFT, py, sv / width, j / C));
      }
      return row;
    });
    for (let k = 0; k < st.length - 1; k++) for (let j = 0; j < C; j++) quad(deck[k][j], deck[k + 1][j], deck[k + 1][j + 1], deck[k][j + 1], [0, 1, 0]);
    // aprons: from each deck edge 1 ft out and 1.4 ft down, so no edge ever floats over the ground
    for (const [j, side] of [[0, -1], [C, 1]]) {
      const ring = st.map(([x, y, dx, dy, m, sv], k) => {
        const e = deck[k][j], ex = pos[3 * e], ey = pos[3 * e + 1], ez = pos[3 * e + 2], ox = -dy * side, oy = dx * side;
        return [vert(ex, ey, ez, sv / width, 0), vert(ex + ox * 1.0, ey - 1.4, ez + oy * 1.0, sv / width, 0.06), [ox, 0.6, oy]];
      });
      for (let k = 0; k < st.length - 1; k++) quad(ring[k][0], ring[k + 1][0], ring[k + 1][1], ring[k][1], ring[k][2]);
    }
    // end caps: the same apron across both ends
    for (const [k, dir] of [[0, -1], [st.length - 1, 1]]) {
      const [, , dx, dy] = st[k], ox = dx * dir, oy = dy * dir;
      const cap = deck[k].map(e => [vert(pos[3 * e], pos[3 * e + 1], pos[3 * e + 2], 0, 0), vert(pos[3 * e] + ox, pos[3 * e + 1] - 1.4, pos[3 * e + 2] + oy, 0, 0.06)]);
      for (let j = 0; j < C; j++) quad(cap[j][0], cap[j + 1][0], cap[j + 1][1], cap[j][1], [ox, 0.6, oy]);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  const mesh = new THREE.Mesh(geo, mat('asphalt'));
  mesh.receiveShadow = true;
  return mesh;
}

function ponds(list, H) {
  const g = new THREE.Group();
  for (const poly of list) {
    const shape = new THREE.Shape(poly.map(([x, y]) => new THREE.Vector2(x, -y)));
    const geo = new THREE.ShapeGeometry(shape, 12); geo.rotateX(-Math.PI / 2);
    const lvl = Math.min(...poly.map(p => H(...p))) - 1.5;
    const m = new THREE.Mesh(geo, new THREE.MeshPhysicalMaterial({ color: '#3d7f86', roughness: 0.05, metalness: 0, envMapIntensity: 1.2 }));
    m.position.y = lvl; g.add(m);
  }
  return g;
}

function nearest(p, a, b) {
  const vx = b[0] - a[0], vy = b[1] - a[1], L = vx * vx + vy * vy || 1;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L));
  const q = [a[0] + t * vx, a[1] + t * vy];
  return { p: q, d: Math.hypot(p[0] - q[0], p[1] - q[1]) };
}
function mulberry(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
