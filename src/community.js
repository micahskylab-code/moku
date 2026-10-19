// Community view: the home in Kukuiʻula. A camera high over the real place (USGS lidar ground, the reef's
// real depth from the USACE topobathy survey, Sentinel-2 colour, OSM/Overture roads, paths, pools, golf
// features and building footprints, Meta/WRI tree heights), drawn as half-metre map tiles baked by
// scripts/geo_community.py, with the walkthrough's sky, buildings and trees over them, and pins for the
// places around. A map rendering of open data, not an aerial photograph; not the developer's map.
//
// Tiles: 1 km squares in north-up UTM 4N (geodata/community/community.json). Each tile's ground is a
// 10 m mesh from the 5 m height grid, easing into the modelled neighbourhood's ground at its edge, with:
//   a_c_r.webp / s_c_r.webp  albedo (2048 px near the camera, 512 px elsewhere)
//   n_c_r.webp               lidar normals (east, north) and the height of what casts shadow (canopy,
//                            eaves): the live sun lights every slope and crown, and shadows are traced
//                            across it toward the sun
//   w_c_r.png                distance to the sea's edge, pond water and sea depth: glassy water, rolling
//                            surf over the shallow reef, swash at the shore
import * as THREE from 'three';
import { SEA_LIFT, SEA_DEEP, SINK, SINK_BOX, SINK_FRAME } from './realsite.js';

const ss = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export const CATEGORIES = {
  home:    { label: 'The modelled home', color: '#c8963e' },
  beach:   { label: 'Beaches', color: '#1f95a8' },
  ocean:   { label: 'Harbor & coast', color: '#2c5e8f' },
  garden:  { label: 'Gardens & culture', color: '#7a5aa6' },
  golf:    { label: 'Golf', color: '#4b8a3a' },
  dining:  { label: 'Shops & dining', color: '#cc6448' },
  club:    { label: 'Clubs & amenities', color: '#b07a2a' },
};

export async function createCommunity({ scene, camera, renderer, orbit, daylight, real, plan, center, low = false, base = 'geodata/community/' }) {
  const meta = await (await fetch(base + 'community.json')).json();
  const T = meta.toWorld, FT = T.ft;
  const toWorld = (E, N) => {
    const dE = (E - T.lotUTM[0]) / FT, dN = (N - T.lotUTM[1]) / FT;
    return [T.origin[0] + dE * T.east[0] + dN * T.north[0], T.origin[1] + dE * T.east[1] + dN * T.north[1]];
  };
  const toUTM = (x, z) => {
    const dx = x - T.origin[0], dz = z - T.origin[1];
    return [T.lotUTM[0] + (dx * T.east[0] + dz * T.east[1]) * FT, T.lotUTM[1] + (dx * T.north[0] + dz * T.north[1]) * FT];
  };
  const fromLatLon = (lat, lon) => toWorld(...utmFromLatLon(lat, lon));

  // ---- heights (world ft, 5 m grid, row 0 at the box's north edge)
  const hg = meta.heights;
  const hraw = await fetchBinary(base + hg.file);
  const hq = new Uint16Array(hraw);
  if (hq.length !== hg.cols * hg.rows) throw new Error('community heights: size');
  const [E0, N0, E1, N1] = meta.box;
  function heightUTM(E, N) {
    const u = Math.max(0, Math.min(hg.cols - 1.001, (E - E0) / hg.res_m - 0.5)), v = Math.max(0, Math.min(hg.rows - 1.001, (N1 - N) / hg.res_m - 0.5));
    const i = Math.floor(u), j = Math.floor(v), fu = u - i, fv = v - j, k = j * hg.cols + i;
    const h = (hq[k] * (1 - fu) + hq[k + 1] * fu) * (1 - fv) + (hq[k + hg.cols] * (1 - fu) + hq[k + hg.cols + 1] * fu) * fv;
    return hg.hmin + h / 65535 * (hg.hmax - hg.hmin);
  }
  const keep = real?.keep, blendFt = real?.blend ?? 300, Hm = real?.H;
  // ground under the community view: the real ground, easing into the modelled neighbourhood around our lot
  function groundAt(x, z) {
    const [E, N] = toUTM(x, z);
    const eb = Math.min(E - E0, E1 - E, N - N0, N1 - N);          // metres inside the box
    // the outer 150 m ease into the walkthrough's real terrain (as the albedo hands over to plain satellite colour)
    let h = !real ? heightUTM(E, N) : eb <= 0 ? real.heightAt(x, z) : eb >= 150 ? heightUTM(E, N) : (hr => hr + (heightUTM(E, N) - hr) * ss(0, 150, eb))(real.heightAt(x, z));
    if (keep && Hm) {
      const d = Math.hypot(Math.max(keep[0] - x, 0, x - keep[2]), Math.max(keep[1] - z, 0, z - keep[3]));
      if (d < blendFt) { const m = Hm(x, z); h = m + (h - m) * ss(0, blendFt, d); }
    }
    return h;
  }
  // From the air the tiles carry the ground everywhere, over the modelled neighbourhood too (at its modelled
  // heights, painted as its lawns by the bake): the walkthrough's own ground mesh is set aside meanwhile.
  const modelGround = [];
  scene.traverse(o => { if (o.isMesh && o.material?.name === 'terrain') modelGround.push(o); });

  // ---- shared shader uniforms
  const U = {
    uTime: { value: 0 }, uSun: { value: new THREE.Vector3(0, 1, 0) }, uShadowK: { value: 1 },
    uGrid: { value: new THREE.Vector2(meta.cols, meta.rows) }, uTileM: { value: meta.tile_m }, uSdfK: { value: meta.sdfPerM ?? 3 },
    // the open sea, drawn: a cobalt (linear) lifted from the bake's measured deep water (meta.deepSea, about 0.003 / 0.009 /
    // 0.025, which reads near black from the air); the sea beyond the tiles takes the same (realsite.js SEA_DEEP)
    uDeep: { value: new THREE.Vector3(0.006, 0.025, 0.09) },
    // the modelled lot, a soft feathered tint on the ground (no lot line: the brochure gives none, its size is assumed)
    uLotC: { value: new THREE.Vector2() }, uLotH: { value: new THREE.Vector2(-1, -1) },
    uEast: { value: new THREE.Vector2(T.east[0], T.east[1]) }, uNorth: { value: new THREE.Vector2(T.north[0], T.north[1]) },
  };
  const flat = new THREE.DataTexture(new Uint8Array([128, 128, 0, 255]), 1, 1); flat.needsUpdate = true;
  const lotR = plan.site?.lot;
  if (lotR) { U.uLotC.value.set((lotR[0] + lotR[2]) / 2, (lotR[1] + lotR[3]) / 2); U.uLotH.value.set((lotR[2] - lotR[0]) / 2, (lotR[3] - lotR[1]) / 2); }

  // ---- tiles
  const group = new THREE.Group(); group.name = 'community'; group.visible = false;
  const S = low ? 50 : 100;
  const tiles = [];
  for (const { c, r } of meta.tiles) {
    const tE0 = E0 + c * meta.tile_m, tN1 = N1 - r * meta.tile_m, step = meta.tile_m / S;
    const pos = new Float32Array((S + 1) * (S + 1) * 3), uv = new Float32Array((S + 1) * (S + 1) * 2);
    for (let j = 0; j <= S; j++) for (let i = 0; i <= S; i++) {
      const k = j * (S + 1) + i, [x, z] = toWorld(tE0 + i * step, tN1 - j * step);
      pos[3 * k] = x; pos[3 * k + 1] = groundAt(x, z); pos[3 * k + 2] = z;
      uv[2 * k] = i / S; uv[2 * k + 1] = j / S;
    }
    const idx = [];
    for (let j = 0; j < S; j++) for (let i = 0; i < S; i++) {
      const a = j * (S + 1) + i, b = a + 1, d = a + S + 1, e = d + 1;
      idx.push(a, d, b, b, d, e);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    // normals from the ground function itself (central differences), so neighbouring tiles agree along their edges
    const nrm = new Float32Array(pos.length), dd = step / FT;
    for (let k = 0; k < pos.length; k += 3) {
      const x = pos[k], z = pos[k + 2];
      const gx = (groundAt(x + dd, z) - groundAt(x - dd, z)) / (2 * dd), gz = (groundAt(x, z + dd) - groundAt(x, z - dd)) / (2 * dd);
      const l = Math.hypot(gx, 1, gz); nrm[k] = -gx / l; nrm[k + 1] = 1 / l; nrm[k + 2] = -gz / l;
    }
    geo.setAttribute('normal', new THREE.BufferAttribute(nrm, 3));
    geo.setIndex(idx); geo.computeBoundingSphere();
    const mat = tileMaterial(U, flat, low);
    mat.userData.u.uTileCR.value.set(c, r);
    mat.polygonOffset = true; mat.polygonOffsetFactor = 1; mat.polygonOffsetUnits = 1;   // over the far terrain, under the modelled ground
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = `community tile ${c},${r}`; mesh.receiveShadow = true;
    mesh.renderOrder = -1;                                     // drawn first: whatever lies beneath fails the depth test
    group.add(mesh);
    const [cx, cz] = toWorld(tE0 + meta.tile_m / 2, tN1 - meta.tile_m / 2);
    tiles.push({ c, r, mesh, mat, centre: new THREE.Vector3(cx, groundAt(cx, cz), cz), hi: 0, want: 0, busy: false });
  }
  // the 512 px albedo and the water data of every tile up front (small); the rest streams by distance
  const firstLoad = await Promise.allSettled(tiles.map(async t => {
    const [a, w] = await Promise.all([loadTex(`${base}s_${t.c}_${t.r}.webp`, { srgb: true, low, closeAfterUpload: true }), loadTex(`${base}w_${t.c}_${t.r}.png`, { srgb: false, mip: false, closeAfterUpload: true })]);
    t.low = a; t.mat.map = a; t.mat.userData.u.uW.value = w; t.mat.needsUpdate = true;
  }));
  firstLoad.forEach((res, k) => {
    if (res.status === 'fulfilled') return;
    const t = tiles[k]; console.warn('[community] tile', t.c, t.r, 'not loaded:', res.reason?.message);
    group.remove(t.mesh); t.mesh.geometry.dispose(); t.mat.dispose(); t.dropped = true;
  });
  for (let k = tiles.length - 1; k >= 0; k--) if (tiles[k].dropped) tiles.splice(k, 1);
  if (!tiles.length) throw new Error('no community tiles');

  scene.add(group);
  // The walkthrough's 10 m real terrain stays outside the box; inside it the tiles carry the ground, and the coarse
  // terrain (whose valleys sit above the lidar ground) is sunk 120 ft under them while the view is on (realsite.js SINK):
  // no clipped edge to see through at the box's rim. Its sea loses the mosaic's glint so it meets the tiles' sea.
  SINK_BOX.value.set(E0, N0, E1, N1); SINK_FRAME.lot.value.set(T.lotUTM[0], T.lotUTM[1]); SINK_FRAME.origin.value.set(T.origin[0], T.origin[1]);
  SINK_FRAME.east.value.set(T.east[0], T.east[1]); SINK_FRAME.north.value.set(T.north[0], T.north[1]); SINK_FRAME.ft.value = FT;
  SEA_DEEP.value.copy(U.uDeep.value);
  const realMats = [];
  scene.traverse(o => { if (o.isMesh && /^realsite (near|far|ocean)$/.test(o.material?.name ?? '')) realMats.push(o.material); });
  // the modelled access roads, darker from the air (their pale texture reads as a gravel slab at this distance)
  const roadMeshes = [], darkRoad = new THREE.MeshStandardMaterial({ name: 'community road', color: '#3c4046', roughness: 0.9 });
  scene.traverse(o => { if (o.isMesh && /asphalt/.test(o.material?.name ?? '') && !o.userData.realsite) roadMeshes.push(o); });

  const maxHi = low ? 4 : 10, dHi = (low ? 4200 : 7500), hiSize = low ? 1024 : 2048;
  let streamT = 0, inflight = 0;
  function stream(dt) {
    streamT -= dt; if (streamT > 0) return; streamT = 0.4;
    const cam = camera.position;
    const order = tiles.map(t => ({ t, d: t.centre.distanceTo(cam) })).sort((a, b) => a.d - b.d);
    order.forEach(({ t, d }, k) => { t.want = k < maxHi && d < dHi ? 1 : (t.hi && d < dHi * 1.35 && k < maxHi + 2 ? 1 : 0); });
    const now = performance.now();
    for (const { t } of order) {
      if (t.want && !t.hi && !t.busy && (t.fails ?? 0) < 3 && !(t.failUntil > now) && inflight < 2) {
        t.busy = true; inflight++;
        Promise.allSettled([loadTex(`${base}a_${t.c}_${t.r}.webp`, { srgb: true, size: hiSize, low }), loadTex(`${base}n_${t.c}_${t.r}.webp`, { srgb: false, size: low ? 512 : 1024 })])
          .then(([ra, rn]) => {
            const a = ra.value, n = rn.value;
            if (!a || !n || !t.want) {
              a?.dispose(); n?.dispose();
              if (!a || !n) { t.fails = (t.fails ?? 0) + 1; t.failUntil = performance.now() + 2000 * 2 ** t.fails; console.warn('[community] tile', t.c, t.r, (ra.reason ?? rn.reason)?.message); }
              return;
            }
            t.hiTex = [a, n]; t.hi = 1; t.mat.map = a; t.mat.userData.u.uN.value = n; t.mat.userData.u.uHasN.value = 1; t.mat.needsUpdate = true;
            edges();
          })
          .finally(() => { t.busy = false; inflight--; });
      } else if (!t.want && t.hi) dropHi(t);
    }
    edges();
  }
  // lidar normals and traced shadows fade out only toward an edge shared with a 2 m tile (or the box): no seam there
  const tileAt = new Map(tiles.map(t => [`${t.c},${t.r}`, t]));
  function edges() {
    const lo = (c, r) => !tileAt.get(`${c},${r}`)?.hi ? 1 : 0;
    for (const t of tiles) t.mat.userData.u.uEdgeLo.value.set(lo(t.c, t.r - 1), lo(t.c + 1, t.r), lo(t.c, t.r + 1), lo(t.c - 1, t.r));
  }
  function dropHi(t) {
    t.mat.map = t.low; t.mat.userData.u.uN.value = flat; t.mat.userData.u.uHasN.value = 0; t.mat.needsUpdate = true;
    for (const x of t.hiTex) x.dispose(); t.hiTex = null; t.hi = 0;
    edges();
  }

  // ---- places
  const places = await fetch(base + 'places.json').then(r => r.ok ? r.json() : { places: [] }).catch(() => ({ places: [] }));
  const home = { id: 'home', name: 'Concept home (modelled)', sub: 'The brochure’s “Lot 25” spec design, modelled on an assumed Nā Hiku lot', cat: 'home', world: [center[0], center[1]], prio: 10,
    note: 'This walkthrough’s concept model. The soft gold patch is its modelled lot (61.5 × 184.4 ft, an assumed size); the brochure gives no lot lines, and the position is registered to ±25 m. The other Nā Hiku homes shown are assumed copies of this design; in 2025–26 imagery the Nā Hiku strip is graded, unbuilt land, and the homes, pools and lawns on it are modelled. Views from the home are not shown or verified.' };
  const pins = [home, ...(places.places ?? []).map(p => ({ ...p, world: fromLatLon(p.lat, p.lon) }))];
  for (const p of pins) p.ground = new THREE.Vector3(p.world[0], groundAt(p.world[0], p.world[1]), p.world[1]);
  const ui = buildUI(pins, places, meta.attribution ?? []);

  // ---- camera: an orbit over the place, kept inside the box and above the ground
  const saved = {};
  const boxW = [toWorld(E0, N0), toWorld(E1, N0), toWorld(E1, N1), toWorld(E0, N1)];
  const inBoxW = (x, z) => { const [E, N] = toUTM(x, z); return E > E0 + 300 && E < E1 - 300 && N > N0 + 300 && N < N1 - 300; };
  const clampW = (x, z) => { const [E, N] = toUTM(x, z); return toWorld(Math.max(E0 + 300, Math.min(E1 - 300, E)), Math.max(N0 + 300, Math.min(N1 - 300, N))); };
  let fly = null, active = false, fogBase = null, fogSet = null, expBase = null, expSet = null, viewOff = null;
  // where the card stands as a column on the left (wide screens, where it is docked, and phones held in landscape, where
  // it folds to its title at the top left), the view is centred in the space to its right, at the same scale: the
  // place a flight aims at is never under the card
  function cardDock() {
    const c = ui.dock();
    if (c > 0 || innerWidth <= innerHeight) return c;
    const card = document.querySelector('#community .cm-card'), b = card && !card.closest('[hidden]') ? card.getBoundingClientRect() : null;
    return b && b.width && b.left < 40 && b.right < innerWidth * 0.5 ? Math.round(b.right + 12) : 0;
  }
  function frame() {
    const c = cardDock();
    const key = `${innerWidth}x${innerHeight}:${c}`;
    if (key === viewOff) return; viewOff = key;
    if (c > 0) { camera.aspect = (innerWidth + c) / innerHeight; camera.setViewOffset(innerWidth + c, innerHeight, 0, 0, innerWidth, innerHeight); }
    else { camera.clearViewOffset(); camera.aspect = innerWidth / innerHeight; }
    camera.updateProjectionMatrix();
  }

  function pose(target, dist, polar, azim) {          // azim: world angle of the camera from the target (0 = +x)
    const h = dist * Math.cos(polar), r = dist * Math.sin(polar);
    return { target: target.clone(), pos: new THREE.Vector3(target.x + r * Math.cos(azim), target.y + h, target.z + r * Math.sin(azim)) };
  }
  const worldAz = v => Math.atan2(v[1], v[0]);
  const northAz = worldAz(T.north), southAz = northAz + Math.PI;
  const homeG = pins[0].ground;

  function flyTo(to, secs = 3.2) {
    const from = { target: orbit.target.clone(), pos: camera.position.clone() };
    // through spherical coordinates around the moving target: no swing through the ground
    const sph = (p) => { const o = p.pos.clone().sub(p.target); return { d: o.length(), pol: Math.acos(Math.max(-1, Math.min(1, o.y / o.length()))), az: Math.atan2(o.z, o.x) }; };
    const a = sph(from), b = sph(to);
    let daz = b.az - a.az; daz = Math.atan2(Math.sin(daz), Math.cos(daz));
    fly = { from, to, a, b, daz, t: 0, secs };
  }
  function stepFly(dt) {
    if (!fly) return;
    fly.t = Math.min(1, fly.t + dt / fly.secs);
    const k = ease(fly.t), { a, b } = fly;
    const target = fly.from.target.clone().lerp(fly.to.target, k);
    // distance in log space, lifted a little mid-flight for a gentle arc
    const d = Math.exp(Math.log(a.d) + (Math.log(b.d) - Math.log(a.d)) * k) * (1 + 0.25 * Math.sin(Math.PI * k) * Math.min(1, Math.abs(fly.daz) / 1.5));
    const pol = a.pol + (b.pol - a.pol) * k, az = a.az + fly.daz * k;
    orbit.target.copy(target);
    camera.position.set(target.x + d * Math.sin(pol) * Math.cos(az), target.y + d * Math.cos(pol), target.z + d * Math.sin(pol) * Math.sin(az));
    camera.lookAt(target);
    if (fly.t >= 1) fly = null;
  }
  const cancelFly = () => { fly = null; };

  // The hero frame, at the end of the flight in: from inland of the home (north-north-west on wide screens), over the golf
  // course and across it to the coast, the reef and the sea, with the horizon near the upper third and sky above it, the
  // sun from the side, and the home on a
  // lower third point of the part of the screen the chrome leaves free. Per layout: b, the camera's compass bearing from
  // the home (degrees); d, its distance to the target (ft); pol, its polar angle; sx, sy, where the home sits in the free
  // area (fractions). Phones in portrait come closer, with the home near the middle.
  const HERO = {
    wide: { b: 345, d: 4000, pol: 1.29, sx: 0.4, sy: 0.69 },
    landscape: { b: 355, d: 3300, pol: 1.33, sx: 0.45, sy: 0.64 },   // flatter: the header takes a quarter of the height
    portrait: { b: 318, d: 3000, pol: 1.22, sx: 0.5, sy: 0.64 },     // a narrow view: from the north-west, over the fairways
  };
  const probeCam = new THREE.PerspectiveCamera();
  // the part of the screen no panel covers: below the header, above a bottom card (phones), right of a card column
  function freeRect() {
    const W = innerWidth, H = innerHeight, r = [0, 0, W, H];
    for (const id of ['hud', 'buttons']) { const e = document.getElementById(id); if (e && !e.hidden) { const b = e.getBoundingClientRect(); if (b.height && b.top < H * 0.3) r[1] = Math.max(r[1], b.bottom); } }
    for (const el of [document.querySelector('#community .cm-card'), document.querySelector('#community .cm-attr'), document.getElementById('skypanel')]) {
      if (!el || el.closest('[hidden]')) continue;
      const b = el.getBoundingClientRect();
      if (b.height && b.top > H * 0.5 && (b.width > W * 0.6 || el.id === 'skypanel')) r[3] = Math.min(r[3], b.top);
    }
    const c = cardDock(); if (c > 0) r[0] = c;
    if (r[3] - r[1] < H * 0.4) { r[1] = 0; r[3] = H; }
    return r;
  }
  function establishing(o = {}) {
    frame();
    const W = innerWidth, H = innerHeight, P = { ...(H > W * 1.05 ? HERO.portrait : W <= 600 || H <= 480 ? HERO.landscape : HERO.wide), ...o };
    const br = P.b * Math.PI / 180, az = Math.atan2(Math.sin(br) * T.east[1] + Math.cos(br) * T.north[1], Math.sin(br) * T.east[0] + Math.cos(br) * T.north[0]);
    const f = freeRect(), want = [((f[0] + (f[2] - f[0]) * P.sx) / W) * 2 - 1, 1 - ((f[1] + (f[3] - f[1]) * P.sy) / H) * 2];
    // find the target (on the ground) that puts the home there, with this camera's projection: a few Newton steps
    probeCam.copy(camera); probeCam.updateProjectionMatrix();
    const fwd = new THREE.Vector3(-Math.cos(az), 0, -Math.sin(az)), right = new THREE.Vector3(Math.sin(az), 0, -Math.cos(az)), v = new THREE.Vector3();
    const onGround = q => { q.y = groundAt(q.x, q.z); return q; };
    const at = q => { const p = pose(q, P.d, P.pol, az); probeCam.position.copy(p.pos); probeCam.lookAt(q); probeCam.updateMatrixWorld(); return v.copy(homeG).project(probeCam).clone(); };
    const t = homeG.clone().addScaledVector(fwd, P.d * Math.sin(P.pol) * 0.5); onGround(t);
    for (let i = 0; i < 10; i++) {
      const s = at(t), ex = want[0] - s.x, ey = want[1] - s.y;
      if (Math.abs(ex) + Math.abs(ey) < 2e-3) break;
      const h = 40, sF = at(onGround(t.clone().addScaledVector(fwd, h))), sR = at(onGround(t.clone().addScaledVector(right, h)));
      const a = (sF.x - s.x) / h, b = (sR.x - s.x) / h, c = (sF.y - s.y) / h, d = (sR.y - s.y) / h, det = a * d - b * c;
      if (Math.abs(det) < 1e-12) break;
      let mF = (d * ex - b * ey) / det, mR = (-c * ex + a * ey) / det;
      const m = Math.hypot(mF, mR), cap = P.d; if (m > cap) { mF *= cap / m; mR *= cap / m; }
      onGround(t.addScaledVector(fwd, mF).addScaledVector(right, mR));
    }
    return pose(t, P.d, P.pol, az);
  }
  function overview() {
    // low over the sea: the coast, the reef, the community rising to the mountains
    const [cx, cz] = toWorld(450300, 2421100);
    return pose(new THREE.Vector3(cx, groundAt(cx, cz), cz), 9000, 1.16, southAz + 0.12);
  }

  let entered = false;
  function enter({ intro = !entered } = {}) {
    active = true; entered = true;
    Object.assign(saved, { near: camera.near, far: camera.far, minD: orbit.minDistance, maxD: orbit.maxDistance, maxP: orbit.maxPolarAngle, ssp: orbit.screenSpacePanning, fog: scene.fog?.density });
    camera.near = 6; camera.far = 2.0e6; camera.updateProjectionMatrix();   // the sea skirt reaches the horizon (realsite.js)
    Object.assign(orbit, { minDistance: 180, maxDistance: 32000, maxPolarAngle: 1.36, screenSpacePanning: false });
    orbit.enabled = true;
    group.visible = true; ui.show(true);
    for (const m of modelGround) { m.userData.cmVisible = m.visible; m.visible = false; }
    SEA_LIFT.value = 1; SINK.value = 120;                     // realsite.js: glint off its sea; sunk under the tiles in the box
    for (const m of realMats) { m.userData.cmEnv = m.envMapIntensity; m.envMapIntensity = 1; }
    for (const o of roadMeshes) { o.userData.cmMat = o.material; o.material = darkRoad; }
    const dome = daylight?.sky?.domeU; if (dome?.uNoGround) dome.uNoGround.value = 1;   // haze below the horizon, not ground
    for (const t of tiles) t.want = 0;
    const sky = document.getElementById('skypanel'); if (sky?.classList.contains('open')) sky.querySelector('.sp-head')?.click();   // the card needs the left side
    if (intro) {
      // a first look in daylight: opened at night or in twilight, the sky moves to mid-morning today (Night sky and the
      // time panel still give any time)
      if (daylight && (daylight.light?.sun?.alt ?? 90) < 8) daylight.toDay?.();
      const o = overview(); orbit.target.copy(o.target); camera.position.copy(o.pos); camera.lookAt(o.target);
      setTimeout(() => active && !userMoved && flyTo(establishing(), 7.5), 600);
    } else {
      const e = establishing(); orbit.target.copy(e.target); camera.position.copy(e.pos);
    }
    userMoved = false; fogSet = null; expSet = null;
  }
  function exit() {
    active = false; fly = null;
    if (scene.fog && fogBase != null && scene.fog.density === fogSet) scene.fog.density = fogBase;
    if (expBase != null && renderer.toneMappingExposure === expSet) renderer.toneMappingExposure = expBase;
    camera.near = saved.near; camera.far = saved.far; camera.updateProjectionMatrix();
    Object.assign(orbit, { minDistance: saved.minD, maxDistance: saved.maxD, maxPolarAngle: saved.maxP, screenSpacePanning: saved.ssp });
    group.visible = false; ui.show(false);
    for (const m of modelGround) m.visible = m.userData.cmVisible ?? true;
    SEA_LIFT.value = 0; SINK.value = 0;
    for (const m of realMats) m.envMapIntensity = m.userData.cmEnv ?? 1;
    for (const o of roadMeshes) if (o.userData.cmMat) o.material = o.userData.cmMat;
    const dome = daylight?.sky?.domeU; if (dome?.uNoGround) dome.uNoGround.value = 0;
    camera.clearViewOffset(); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); viewOff = null;
    // give the full-size tiles back to the GPU; the 2 m ones stay for next time
    for (const t of tiles) { t.want = 0; if (t.hi) dropHi(t); }
  }
  let userMoved = false;
  for (const ev of ['pointerdown', 'wheel', 'touchstart']) renderer.domElement.addEventListener(ev, () => { if (active) { userMoved = true; cancelFly(); } }, { passive: true });

  const tmp = new THREE.Vector3();
  function update(dt) {
    if (!active) return;
    U.uTime.value += dt;
    const sd = daylight?.light?.sDir;
    if (sd) U.uSun.value.set(sd[0], sd[1], sd[2]);
    // the haze, the exposure, the sky fill and the grade of this view are daylight.js's community look (main.js switches it)
    stepFly(dt);
    if (!fly) {
      // keep the target on the ground inside the box, and the camera above the ground
      const t = orbit.target;
      if (!inBoxW(t.x, t.z)) {
        const [x, z] = clampW(t.x, t.z);
        const dx = x - t.x, dz = z - t.z; t.x += dx; t.z += dz; camera.position.x += dx; camera.position.z += dz;
      }
      const gy = groundAt(t.x, t.z); camera.position.y += (gy - t.y) * 0.15; t.y += (gy - t.y) * 0.15;
      const cg = groundAt(camera.position.x, camera.position.z) + 60;
      if (camera.position.y < cg) camera.position.y = cg;
    }
    stream(dt);
    frame();
    const wx = daylight?.state?.weather?.source === 'live'; if (wx !== ui.wx) ui.setWx(wx);
    ui.place(camera, renderer);
  }

  const jump = p => { fly = null; userMoved = true; orbit.target.copy(p.target); camera.position.copy(p.pos); camera.lookAt(p.target); };
  window.__community = { groundAt, toWorld, toUTM, fromLatLon, tiles, pins, flyTo, jump, pose, establishing, overview, northAz, settled: () => !fly && tiles.every(t => !t.busy && (!t.want || t.hi || (t.fails ?? 0) >= 3)) };
  // compile the tile shader and upload the small textures now, not in the first frame of the view (a long stall)
  try {
    // the composer draws into a half-float target: compile that variant, not the screen's
    const rt = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType }), prev = renderer.getRenderTarget();
    renderer.setRenderTarget(rt); const pc = renderer.compileAsync?.(group, camera, scene); renderer.setRenderTarget(prev);
    await pc; rt.dispose();
    for (const [k, t] of tiles.entries()) { renderer.initTexture(t.low); renderer.initTexture(t.mat.userData.u.uW.value); if (k % 6 === 5) await new Promise(requestAnimationFrame); }
  } catch (e) { console.warn('[community] precompile', e.message); }
  return { enter, exit, update, group, flyTo, establishing, title: () => ui.title(), get active() { return active; } };

  // ---------------------------------------------------------------------------------------------
  function buildUI(pins, data, credits) {
    const root = document.createElement('div'); root.id = 'community'; root.hidden = true;
    root.innerHTML = `
      <div class="cm-card">
        <button class="cm-fold" type="button" aria-controls="cm-body"><span class="cm-kicker">Kukuiʻula · Kōloa, Kauaʻi</span>
          <span class="cm-title">The neighbourhood around the home</span><span class="cm-chev" aria-hidden="true"></span></button>
        <div id="cm-body">
        <div class="cm-chips"></div>
        <div class="cm-actions"><button class="cm-btn" data-a="home">Back to the home</button><button class="cm-btn" data-a="overview">Whole community</button></div>
        <div class="cm-fine">A map rendering of open public data, not an aerial photograph or the developer's map. Places and distances are approximate. The home, its lot and the other Nā Hiku homes (assumed copies of this design, on a strip that is graded, unbuilt land in 2025–26 imagery) are a concept model; views are not shown or verified.</div>
        </div>
      </div>
      <div class="cm-pins"></div>
      <div class="cm-info" hidden></div>
      <div class="cm-attr"><b>Map rendering of open data, not an aerial photograph; the Nā Hiku homes are modelled.</b>
        <span class="cm-attr-full">${[...credits, data.attribution].filter(Boolean).map(linkify).join(' · ')}</span>
        <span class="cm-attr-short">${linkify('© OpenStreetMap contributors, Microsoft, TomTom (ODbL)')}, via Overture · Contains modified Copernicus Sentinel data 2023–26 · USGS · USACE/NOAA · Meta/WRI (${linkify('CC BY 4.0')}, modified)</span>
        <span class="cm-wx" hidden> · Weather: <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo.com</a> (<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>)</span>
        <button class="cm-credits" type="button" aria-expanded="false">Credits</button></div>`;
    document.body.appendChild(root);
    const card = root.querySelector('.cm-card'), chips = root.querySelector('.cm-chips'), layer = root.querySelector('.cm-pins'), info = root.querySelector('.cm-info');
    // phones: the card sits above the credits, however many lines they take (they must stay readable)
    const attr = root.querySelector('.cm-attr'), phone = matchMedia('(max-width: 600px)'), small = matchMedia('(max-width: 600px), (max-height: 480px)');
    // small screens: the card folds to its title (tap to open) and the credits to one line (Credits for the full list)
    const fold = root.querySelector('.cm-fold');
    const setFold = f => {
      card.classList.toggle('cm-folded', f);
      if (small.matches) { fold.setAttribute('aria-expanded', String(!f)); fold.tabIndex = 0; } else { fold.removeAttribute('aria-expanded'); fold.tabIndex = -1; }
      fitCard?.();
    };
    fold.addEventListener('click', e => { e.stopPropagation(); if (small.matches) setFold(!card.classList.contains('cm-folded')); });
    setFold(small.matches);
    small.addEventListener?.('change', () => setFold(small.matches));
    const credBtn = root.querySelector('.cm-credits');
    credBtn.addEventListener('click', e => { e.stopPropagation(); const o = !attr.classList.contains('cm-attr-open'); attr.classList.toggle('cm-attr-open', o); credBtn.setAttribute('aria-expanded', String(o)); credBtn.textContent = o ? 'Less' : 'Credits'; });
    var fitCard = () => { const lift = phone.matches && attr.offsetHeight ? `calc(${attr.offsetHeight + 54}px + env(safe-area-inset-bottom, 0px))` : ''; card.style.bottom = lift; info.style.bottom = lift; };
    if (typeof ResizeObserver === 'function') new ResizeObserver(fitCard).observe(attr);
    phone.addEventListener?.('change', fitCard);
    addEventListener('resize', () => { for (const p of pins) { p.w = undefined; p.stem = undefined; } });
    const setInfo = open => {
      info.hidden = !open; root.classList.toggle('cm-info-open', open);
      if (open && small.matches) { attr.classList.remove('cm-attr-open'); credBtn.setAttribute('aria-expanded', 'false'); credBtn.textContent = 'Credits'; }
      fitCard();
    };
    const on = Object.fromEntries(Object.keys(CATEGORIES).map(k => [k, true]));
    const counts = {}; for (const p of pins) counts[p.cat] = (counts[p.cat] ?? 0) + 1;
    for (const [k, c] of Object.entries(CATEGORIES)) {
      if (!counts[k] || k === 'home') continue;
      const b = document.createElement('button'); b.className = 'cm-chip'; b.dataset.cat = k; b.setAttribute('aria-pressed', 'true');
      b.innerHTML = `<span class="cm-dot" style="background:${c.color}"></span>${c.label}<span class="cm-n">${counts[k]}</span>`;
      b.addEventListener('click', e => { e.stopPropagation(); on[k] = !on[k]; b.setAttribute('aria-pressed', String(on[k])); });
      chips.appendChild(b);
    }
    root.querySelector('[data-a="home"]').addEventListener('click', e => { e.stopPropagation(); userMoved = true; flyTo(establishing()); });
    root.querySelector('[data-a="overview"]').addEventListener('click', e => { e.stopPropagation(); userMoved = true; flyTo(overview(), 3.6); });
    for (const p of pins) {
      const el = document.createElement('button'); el.className = 'cm-pin' + (p.cat === 'home' ? ' cm-hero' : ''); el.type = 'button';
      const c = CATEGORIES[p.cat] ?? CATEGORIES.club;
      el.style.setProperty('--c', c.color);
      el.innerHTML = `<span class="cm-stem"></span><span class="cm-label"><span class="cm-ico">${ICONS[p.cat] ?? ICONS.club}</span><span class="cm-name">${esc(p.name)}</span></span>`;
      el.addEventListener('click', e => { e.stopPropagation(); select(p); });
      layer.appendChild(el); p.el = el; p.vis = 0;
    }
    let sel = null;
    function select(p) {
      sel = p; userMoved = true;
      const d = homeG.distanceTo(p.ground) * FT / 1609.34;
      const c = CATEGORIES[p.cat] ?? CATEGORIES.club;
      info.innerHTML = `<button class="cm-x" aria-label="Close">×</button><div class="cm-ikick" style="color:${c.color}">${c.label}</div><div class="cm-iname">${esc(p.name)}</div>` +
        (p.sub ? `<div class="cm-isub">${esc(p.sub)}</div>` : '') +
        (p.cat !== 'home' ? `<div class="cm-imeta">≈ ${d < 0.1 ? (d * 5280).toFixed(0) + ' ft' : d.toFixed(1) + ' mi'} from the home, in a straight line</div>` : '') +
        (p.note ? `<div class="cm-inote">${esc(p.note)}</div>` : '') + (p.src ? `<div class="cm-isrc">${esc(p.src)}</div>` : '');
      setInfo(true);
      info.querySelector('.cm-x').addEventListener('click', e => { e.stopPropagation(); setInfo(false); sel = null; });
      // aim where the camera may rest (the target is kept 300 m inside the box)
      const [gx, gz] = clampW(p.ground.x, p.ground.z), aim = new THREE.Vector3(gx, groundAt(gx, gz), gz);
      const near = p.cat === 'home' ? establishing() : pose(aim, 1500, 0.92, Math.atan2(camera.position.z - aim.z, camera.position.x - aim.x));
      flyTo(near, 2.8);
    }
    const v = new THREE.Vector3(), rects = [];
    return {
      show(s) { root.hidden = !s; if (!s) { setInfo(false); sel = null; } else fitCard(); },
      // width of the docked card (wide screens), for framing the view beside it
      dock: () => (!root.hidden && !small.matches && !phone.matches) ? Math.round(card.getBoundingClientRect().right + 16) : 0,
      wx: false,
      setWx(v) { this.wx = v; root.querySelector('.cm-wx').hidden = !v; },
      title: () => sel ? sel.name : 'Kukuiʻula · community view',
      place(cam, rend) {
        cam.updateMatrixWorld();                         // this frame's camera, not last frame's (no lag in flights)
        const W = innerWidth, H = innerHeight;
        rects.length = 0; let ui0 = 0;
        for (const el of [card, info, attr, document.getElementById('hud'), document.getElementById('buttons'), document.getElementById('skypanel')]) {
          if (!el || el.hidden) continue;
          const b = el.getBoundingClientRect(); if (b.width) rects.push([b.left, b.top, b.right, b.bottom]);
        }
        ui0 = rects.length;
        const hit = (R, o, m = 4) => R[0] < o[2] + m && R[2] > o[0] - m && R[1] < o[3] + 3 && R[3] > o[1] - 3;
        const list = pins.map(p => {
          v.copy(p.ground); v.y += 6;
          const dist = v.distanceTo(cam.position);
          v.project(cam);
          return { p, x: (v.x * 0.5 + 0.5) * W, y: (-v.y * 0.5 + 0.5) * H, front: v.z < 1, dist };
        }).sort((a, b) => (b.p.prio ?? 1) - (a.p.prio ?? 1) || a.dist - b.dist);
        for (const q of list) {
          const { p } = q;
          const stem = Math.max(14, Math.min(70, 70 * 2500 / q.dist));
          let show = q.front && on[p.cat] !== false && q.x > -40 && q.x < W + 40 && q.y > 0 && q.y < H + 20;
          const w = p.w ??= (p.el.querySelector('.cm-label').offsetWidth || 120), h = p.cat === 'home' ? 34 : 26;
          const R = [q.x - w / 2, q.y - stem - h, q.x + w / 2, q.y - stem], S2 = [q.x - 5, q.y - stem, q.x + 5, q.y + 6];
          // at the screen's edge the label slides in along its stem rather than being cut off
          let dx = R[0] < 8 ? 8 - R[0] : R[2] > W - 8 ? W - 8 - R[2] : 0;
          if (Math.abs(dx) > w / 2 - 14) show = false;
          R[0] += dx; R[2] += dx;
          if (show) for (let k = 0; k < rects.length; k++) {
            const o = rects[k];
            if (!hit(R, o) && !hit(S2, o, 2)) continue;
            // the home's label slides sideways off a panel, unless its spot is under the panel itself
            if (p.cat === 'home' && k < ui0 && !(q.x > o[0] && q.x < o[2] && q.y > o[1] && q.y < o[3])) {
              const ndx = q.x >= o[2] ? (o[2] + 8) - (R[0] - dx) : (o[0] - 8) - (R[2] - dx);
              R[0] += ndx - dx; R[2] += ndx - dx; dx = ndx;
              if (Math.abs(dx) > w - 14) { show = false; break; }
              continue;
            }
            show = false; break;
          }
          if (show) rects.push(R, S2);                    // later labels keep off this label, its stem and its dot
          if (Math.round(dx) !== p.dx) { p.dx = Math.round(dx); p.el.style.setProperty('--dx', p.dx + 'px'); }
          p.el.style.transform = `translate(${q.x.toFixed(1)}px, ${q.y.toFixed(1)}px)`;
          if (Math.round(stem) !== p.stem) { p.stem = Math.round(stem); p.el.style.setProperty('--stem', p.stem + 'px'); }
          p.el.classList.toggle('cm-off', !show);
          p.el.classList.toggle('cm-sel', p === sel);
        }
      },
    };
  }
}

// ---------------------------------------------------------------------------------------------
function tileMaterial(U, flat, low) {
  const u = { uN: { value: flat }, uW: { value: flat }, uHasN: { value: 0 }, uTileCR: { value: new THREE.Vector2() }, uEdgeLo: { value: new THREE.Vector4(1, 1, 1, 1) } };
  const m = new THREE.MeshStandardMaterial({ name: 'community tile', roughness: 0.93, metalness: 0, envMapIntensity: 1 });   // as the real-site terrain
  if (low) m.defines = { CM_LOW: '' };                 // phones: a shorter shadow trace, nearer
  m.userData.u = u;
  m.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, U, u);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vCmWorld;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvCmWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    // the sea reflects the sky above the horizon, not the environment's ground half
    const ibl = THREE.ShaderChunk.envmap_physical_pars_fragment.replace('reflectVec = inverseTransformDirection( reflectVec, viewMatrix );',
      'reflectVec = inverseTransformDirection( reflectVec, viewMatrix );\n\t\t\treflectVec.y = mix( reflectVec.y, max( reflectVec.y, 0.06 + 0.5 * roughness ), cmWaterG );\n\t\t\treflectVec = normalize( reflectVec );');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
      uniform sampler2D uN, uW; uniform float uHasN, uTime, uShadowK, uTileM, uSdfK; uniform vec3 uSun, uDeep; uniform vec2 uEast, uNorth, uGrid, uTileCR, uLotC, uLotH; uniform vec4 uEdgeLo;
      varying vec3 vCmWorld; float cmWaterG = 0.0;
      float cmHash(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
      float cmNoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(cmHash(i), cmHash(i + vec2(1, 0)), f.x), mix(cmHash(i + vec2(0, 1)), cmHash(i + vec2(1, 1)), f.x), f.y); }
      float cmWaves(vec2 p){ return cmNoise(p * 0.11) * 0.5 + cmNoise(p * 0.23 + 3.1) * 0.3 + cmNoise(p * 0.51 + 7.7) * 0.2; }`)
      .replace('#include <envmap_physical_pars_fragment>', ibl)
      .replace('#include <map_fragment>', `#include <map_fragment>
      vec4 cmW = texture2D(uW, vMapUv);
      float cmSdf = (cmW.r * 255.0 - 128.0) / uSdfK;        // metres from the sea's edge, + in the sea
      float cmSdfMax = 127.0 / uSdfK;                         // where the encoding saturates
      float cmSea = smoothstep(-0.4, 0.8, cmSdf), cmPond = smoothstep(0.4, 0.7, cmW.g);
      float cmDepth = cmW.b * 25.5;
      float cmWater = max(cmSea, cmPond), cmFoam = 0.0;
      float cmDist = length(vCmWorld - cameraPosition);
      // lidar normals and traced shadows: full on a full-detail tile, fading out only toward an edge it shares with a 2 m tile
      vec2 cmUv = vMapUv;
      float cmHiFade = uHasN * min(min(mix(1.0, smoothstep(0.0, 0.12, cmUv.y), uEdgeLo.x), mix(1.0, smoothstep(0.0, 0.12, 1.0 - cmUv.x), uEdgeLo.y)),
                                   min(mix(1.0, smoothstep(0.0, 0.12, 1.0 - cmUv.y), uEdgeLo.z), mix(1.0, smoothstep(0.0, 0.12, cmUv.x), uEdgeLo.w)));
      // metres to the box's edge: over its last 300 m the sea takes the open-sea colour the view's outer sea is drawn in
      vec2 cmBoxM = vec2((uTileCR.x + cmUv.x) * uTileM, (uTileCR.y + cmUv.y) * uTileM);
      float cmEdgeM = min(min(cmBoxM.x, uGrid.x * uTileM - cmBoxM.x), min(cmBoxM.y, uGrid.y * uTileM - cmBoxM.y));
      // open water past about 10 m hands over to the open sea's cobalt (the bake's depth stops at 25.5 m and its albedo's dark
      // streaks run on below that); over the box's last 300 m the whole sea takes it
      diffuseColor.rgb = mix(diffuseColor.rgb, uDeep, cmSea * max(smoothstep(10.0, 24.0, cmDepth), 1.0 - smoothstep(0.0, 300.0, cmEdgeM)));
      // ponds: a lighter teal-grey margin where the water meets its bank, and the water itself a shade lighter
      float cmPondEdge = smoothstep(0.08, 0.3, cmW.g) * (1.0 - smoothstep(0.5, 0.85, cmW.g));
      diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * 1.15 + vec3(0.004, 0.01, 0.012), cmPond);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.085, 0.12, 0.105), 0.55 * cmPondEdge);
      if (cmSea > 0.0) {
        // sets of swell rolling in over the reef and breaking in the 1-3 m band at its crest, in groups; swash at the shore
        float n = cmNoise(vCmWorld.xz / 30.0 + vec2(uTime * 0.02, 0.0)), n2 = cmNoise(vCmWorld.xz / 7.0 - uTime * 0.05);
        float brk = smoothstep(0.8, 1.6, cmDepth) * (1.0 - smoothstep(1.6, 3.5, cmDepth));
        float inR = 1.0 - smoothstep(0.75 * cmSdfMax, 0.97 * cmSdfMax, cmSdf);
        float ph = cmSdf * 0.16 + uTime * 0.9 + n * 1.2;
        float crest = smoothstep(0.86, 1.0, sin(ph)) * brk * inR * smoothstep(0.35, 0.7, cmNoise(vCmWorld.xz / 60.0 + uTime * 0.01)) * (0.55 + 0.45 * n2);
        float swash = (1.0 - smoothstep(0.0, 1.0 + 1.0 * (0.5 + 0.5 * sin(uTime * 0.8 + n * 9.0)), cmSdf)) * step(-0.4, cmSdf) * (0.5 + 0.5 * n2);
        cmFoam = max(crest * 0.8, swash * 0.65) * (1.0 - smoothstep(5000.0, 16000.0, cmDist));
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.80, 0.82, 0.82), cmFoam);
      }
      // land: a little lighter from the air, and a fine mottle close up so a 0.5 m texel never reads as paint
      float cmLand = 1.0 - cmWater;
      diffuseColor.rgb *= mix(1.0, 1.12, cmLand);
      float cmDn = cmNoise(vCmWorld.xz / 2.3) * 0.4 + cmNoise(vCmWorld.xz / 7.0 + 1.7) * 0.35 + cmNoise(vCmWorld.xz / 23.0 + 5.1) * 0.25;
      diffuseColor.rgb *= mix(1.0, 0.82 + 0.36 * cmDn, cmLand * (1.0 - smoothstep(500.0, 4000.0, cmDist)));
      // the modelled lot: a soft gold tint with a 14 ft feather (houses and trees stand over it)
      if (uLotH.x > 0.0) {
        vec2 lq = abs(vCmWorld.xz - uLotC) - uLotH;
        float lsd = length(max(lq, 0.0)) + min(max(lq.x, lq.y), 0.0);
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.84, 0.64, 0.27), 0.24 * (1.0 - smoothstep(-4.0, 10.0, lsd)));
      }`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
      roughnessFactor = mix(roughnessFactor, mix(0.12, 0.5, smoothstep(300.0, 9000.0, cmDist)), cmWater * (1.0 - cmFoam));   // as the real-site sea in this view`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
      if (cmHiFade > 0.0 && cmWater < 0.99) {
        vec3 tn = texture2D(uN, vMapUv).xyz;
        vec2 ne = (tn.xy * 255.0 - 128.0) / 127.0;
        float up = sqrt(max(0.0, 1.0 - dot(ne, ne)));
        vec3 wn = normalize(vec3(ne.x * uEast.x + ne.y * uNorth.x, up, ne.x * uEast.y + ne.y * uNorth.y));
        normal = normalize(mix(normal, normalize((viewMatrix * vec4(wn, 0.0)).xyz), (1.0 - cmWater) * cmHiFade));
      }
      cmWaterG = cmWater;
      if (cmWater > 0.0) {
        vec2 p = vCmWorld.xz, g = vec2(0.0);
        float nearW = 1.0 - smoothstep(150.0, 1800.0, cmDist), farW = 1.0 - smoothstep(2000.0, 14000.0, cmDist);
        if (nearW > 0.0) { float e = 0.6, h0 = cmWaves(p + uTime * 0.6), hx = cmWaves(p + vec2(e, 0.0) + uTime * 0.6), hz = cmWaves(p + vec2(0.0, e) + uTime * 0.6); g = vec2(hx - h0, hz - h0) / e * 1.1 * nearW; }
        if (farW > 0.0) { vec2 P = p / 9.0 + uTime * 0.05; float E = 1.5; float H0 = cmWaves(P), Hx = cmWaves(P + vec2(E, 0.0)), Hz = cmWaves(P + vec2(0.0, E)); g += vec2(Hx - H0, Hz - H0) / E * 0.2 * farW; }
        vec3 wn = normalize(vec3(-g.x, 1.0, -g.y));
        normal = normalize(mix(normal, normalize((viewMatrix * vec4(wn, 0.0)).xyz), cmWater * (1.0 - cmFoam)));
      }`)
      .replace('#include <aomap_fragment>', `#include <aomap_fragment>
      // water: the sun's highlights on the ripples capped (no white speckles), the ponds' sky reflection a little stronger
      reflectedLight.directSpecular = mix(reflectedLight.directSpecular, min(reflectedLight.directSpecular, vec3(0.45)), cmWater);
      reflectedLight.indirectSpecular *= 1.0 + 0.7 * cmPond;`)
      .replace('#include <lights_fragment_end>', `#include <lights_fragment_end>
      // shadows of trees, scrub and buildings, traced over the tile's height map toward the live sun
      #ifdef CM_LOW
        #define CM_STEPS 8
        #define CM_FAR 5000.0
      #else
        #define CM_STEPS 18
        #define CM_FAR 16000.0
      #endif
      if (cmHiFade > 0.0 && uSun.y > 0.02 && cmDist < CM_FAR && cmWater < 0.99) {
        float h0 = textureLod(uN, vMapUv, 0.0).b * 25.5;
        vec2 sd = vec2(dot(uSun.xz, uEast), dot(uSun.xz, uNorth));
        float hl = max(length(sd), 1e-4);
        vec2 duv = vec2(sd.x, -sd.y) / hl / 1000.0;
        float tanA = uSun.y / hl, occ = 0.0;
        #ifdef CM_LOW
          float t = 2.0;
        #else
          float t = 0.6;
        #endif
        for (int k = 0; k < CM_STEPS; k++) {
          float hq = textureLod(uN, vMapUv + duv * t, 0.0).b * 25.5;
          occ = max(occ, smoothstep(0.15, 1.2, hq - (h0 + t * tanA)));
          #ifdef CM_LOW
            t = t * 1.35 + 0.5;
          #else
            t = t * 1.17 + 0.3;
          #endif
          if (h0 + t * tanA > 26.0) break;
        }
        float k = 1.0 - 0.6 * occ * uShadowK * cmHiFade * (1.0 - smoothstep(0.45 * CM_FAR, CM_FAR, cmDist)) * (1.0 - cmWater);
        reflectedLight.directDiffuse *= k; reflectedLight.directSpecular *= k;
      }`);
  };
  m.customProgramCacheKey = () => 'community-tile-3';
  return m;
}

async function fetchBinary(url) {
  // a host that serves no binary types gets the same bytes as base64 text (scripts/build_artifact.py)
  const r = globalThis.__NAHIKU_HOSTED ? null : await fetch(url);
  if (r?.ok) return r.arrayBuffer();
  const b = await fetch(url.replace(/\.bin$/, '.b64.txt'));
  if (!b.ok) throw new Error(`${url} ${b.status}`);
  const str = atob((await b.text()).trim()), u8 = new Uint8Array(str.length);
  for (let i = 0; i < str.length; i++) u8[i] = str.charCodeAt(i);
  return u8.buffer;
}

async function loadTex(url, { srgb = true, size = 0, mip = true, low = false, closeAfterUpload = false } = {}) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  const blob = await r.blob();
  let img;
  try { img = await createImageBitmap(blob, size ? { resizeWidth: size, resizeHeight: size, resizeQuality: 'high' } : {}); }
  catch {
    // no createImageBitmap (older Safari): an <img>, drawn down to the asked size
    img = await new Promise((ok, no) => {
      const i = new Image(), src = URL.createObjectURL(blob);
      i.onload = () => {
        URL.revokeObjectURL(src);
        if (!size) return ok(i);
        const c = document.createElement('canvas'); c.width = c.height = size; c.getContext('2d').drawImage(i, 0, 0, size, size); ok(c);
      };
      i.onerror = e => { URL.revokeObjectURL(src); no(e); };
      i.src = src;
    });
  }
  const t = new THREE.Texture(img);
  t.addEventListener('dispose', () => img.close?.());   // a decoded ImageBitmap holds its pixels until closed
  // textures that are never re-uploaded let go of the decoded copy once it is on the GPU
  if (closeAfterUpload && typeof img.close === 'function') t.onUpdate = () => { img.close(); t.onUpdate = null; };
  t.flipY = false;                                  // row 0 of every tile image is its north edge (uv v = 0)
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  t.anisotropy = srgb ? (low ? 4 : 8) : 1;
  if (!mip) { t.generateMipmaps = false; t.minFilter = THREE.LinearFilter; }
  t.needsUpdate = true;
  return t;
}

// WGS84 lat/lon -> UTM zone 4N (metres), the standard series (Snyder), good to millimetres here.
function utmFromLatLon(lat, lon) {
  const a = 6378137, f = 1 / 298.257223563, k0 = 0.9996, e2 = f * (2 - f), ep2 = e2 / (1 - e2);
  const L = lat * Math.PI / 180, l0 = -159 * Math.PI / 180, dl = lon * Math.PI / 180 - l0;
  const N = a / Math.sqrt(1 - e2 * Math.sin(L) ** 2), t = Math.tan(L) ** 2, C = ep2 * Math.cos(L) ** 2, A = Math.cos(L) * dl;
  const M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * L - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * Math.sin(2 * L)
    + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * Math.sin(4 * L) - (35 * e2 ** 3 / 3072) * Math.sin(6 * L));
  const E = 500000 + k0 * N * (A + (1 - t + C) * A ** 3 / 6 + (5 - 18 * t + t * t + 72 * C - 58 * ep2) * A ** 5 / 120);
  const Nn = k0 * (M + N * Math.tan(L) * (A * A / 2 + (5 - t + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * t + t * t + 600 * C - 330 * ep2) * A ** 6 / 720));
  return [E, Nn];
}

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// a credit line with its licence linked (the licences ask for a link or a notice)
const LICENCES = [[/ODbL/, 'https://opendatacommons.org/licenses/odbl/1-0/'], [/CC BY 4\.0/, 'https://creativecommons.org/licenses/by/4.0/'],
  [/CDLA-Permissive-2\.0/, 'https://cdla.dev/permissive-2-0/'], [/OpenStreetMap contributors/, 'https://www.openstreetmap.org/copyright']];
const linkify = s => LICENCES.reduce((h, [re, url]) => h.replace(re, m => `<a href="${url}" target="_blank" rel="noopener">${m}</a>`), esc(s));

// small line icons, drawn for this view (24 px grid)
const svg = d => `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICONS = {
  home: svg('<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v9.5h13V10"/><path d="M10 19.5v-5h4v5"/>'),
  beach: svg('<path d="M4 20h16"/><path d="M12 20V9"/><path d="M5 9a7 7 0 0 1 14 0z"/>'),
  ocean: svg('<path d="M3 15c2 0 2-1.5 4.5-1.5S10 15 12 15s2-1.5 4.5-1.5S19 15 21 15"/><path d="M3 19c2 0 2-1.5 4.5-1.5S10 19 12 19s2-1.5 4.5-1.5S19 19 21 19"/><path d="M12 11V4l5 3-5 2"/>'),
  garden: svg('<path d="M12 21v-8"/><path d="M12 13c-4 0-6-3-6-7 4 0 6 3 6 7z"/><path d="M12 13c4 0 6-3 6-7-4 0-6 3-6 7z"/>'),
  golf: svg('<path d="M8 21V3l9 4-9 4"/><path d="M5 21h8"/>'),
  dining: svg('<path d="M7 3v8a2 2 0 0 0 2 2v8"/><path d="M11 3v8a2 2 0 0 1-2 2"/><path d="M16 21V3c2 1 3 4 3 7h-3"/>'),
  club: svg('<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>'),
};
