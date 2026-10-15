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
  return {
    toPlan, lot, keep, lots, ourLot: OUR_LOT,
    nahiku: lots.filter((_, i) => i !== OUR_LOT),
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
  const params = new URLSearchParams(location.search);
  const low = (params.get('q') ?? (matchMedia('(pointer: coarse)').matches ? 'low' : 'high')) === 'low';
  const real = params.get('real') === '0' ? null : await loadRealSite('geodata/', { low });
  const center = [(L.lot[0] + L.lot[2]) / 2, (L.lot[1] + L.lot[3]) / 2];

  // The other thirteen Na Hiku homes: instanced copies of our exterior + garden.
  if (shell) {
    const mats = L.nahiku.map(([x, y]) => new THREE.Matrix4().makeTranslation(x - center[0], H(x, y) - H(...center), y - center[1]));
    for (const { geometry, material } of shell) {
      const inst = new THREE.InstancedMesh(geometry, material, mats.length);
      mats.forEach((m, i) => inst.setMatrixAt(i, m));
      inst.castShadow = inst.receiveShadow = true;
      inst.frustumCulled = false;
      g.add(inst);
    }
  }
  const offsets = shell ? L.nahiku.map(([x, y]) => [x - center[0], H(x, y) - H(...center), y - center[1]]) : [];

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
    window.__neighborhood = { layout: L, offsets, real, night: () => real.night(true) };
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
  window.__neighborhood = { layout: L, offsets, night: () => { win.emissiveIntensity = 0.9; poolMat.emissiveIntensity = 0.8; } };
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

function roads(lines, H, width = 24) {
  const parts = [];
  for (const line of lines) for (let i = 0; i < line.length - 1; i++) {
    const [ax, ay] = line[i], [bx, by] = line[i + 1], len = Math.hypot(bx - ax, by - ay), n = Math.ceil(len / 16);
    for (let k = 0; k < n; k++) {
      const t0 = k / n, t1 = (k + 1) / n;
      const x0 = ax + (bx - ax) * t0, y0 = ay + (by - ay) * t0, x1 = ax + (bx - ax) * t1, y1 = ay + (by - ay) * t1;
      const seg = new THREE.PlaneGeometry(Math.hypot(x1 - x0, y1 - y0) + 1.5, width);
      seg.rotateX(-Math.PI / 2); seg.rotateY(-Math.atan2(y1 - y0, x1 - x0));
      seg.translate((x0 + x1) / 2, Math.max(H(x0, y0), H(x1, y1), H((x0 + x1) / 2, (y0 + y1) / 2)) + 0.35, (y0 + y1) / 2);
      parts.push(seg);
    }
  }
  const mesh = new THREE.Mesh(mergeGeometries(parts), mat('asphalt'));
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
