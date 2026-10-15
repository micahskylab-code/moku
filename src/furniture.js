// Furniture, fixtures and finishes, built from primitives to the Na Hiku interior concept:
// white oak, linen, cane, rattan, coral stone, black hardware, teak outdoors.
// Every item is centred on (x, y) in plan feet; w runs along its local x, d along local z;
// rot is degrees on the plan. Local -z is the item's back (the wall it stands against).
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { mat, glow } from './materials.js';

const geoCache = new Map();
function rgeo(w, h, d, r) {
  const k = `${w.toFixed(2)}|${h.toFixed(2)}|${d.toFixed(2)}|${r}`;
  if (!geoCache.has(k)) geoCache.set(k, new RoundedBoxGeometry(w, h, d, 3, Math.min(r, w / 2 - 0.001, h / 2 - 0.001, d / 2 - 0.001)));
  return geoCache.get(k);
}
const M = n => (typeof n === 'string' ? mat(n) : n);
function box(g, w, h, d, x, y, z, m, r = 0) {
  const mesh = new THREE.Mesh(r > 0 ? rgeo(w, h, d, r) : new THREE.BoxGeometry(w, h, d), M(m));
  mesh.position.set(x, y, z); g.add(mesh); return mesh;
}
function cyl(g, rt, rb, h, x, y, z, m, seg = 24) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), M(m));
  mesh.position.set(x, y, z); g.add(mesh); return mesh;
}
function lathe(g, profile, x, y, z, m, seg = 40) {
  const mesh = new THREE.Mesh(new THREE.LatheGeometry(profile.map(([r, h]) => new THREE.Vector2(r, h)), seg), M(m));
  mesh.position.set(x, y, z); g.add(mesh); return mesh;
}
const fabric = m => ({ linen: 'linen', white: 'linenWhite', sand: 'linenSand', sea: 'linenSea' }[m] ?? m ?? 'linen');

// Lamps register here so night mode can switch them on.
export const lamps = [];
function addLamp(g, x, y, z, intensity = 6, dist = 14) {
  const l = new THREE.PointLight('#ffcf94', 0, dist, 1.8);
  l.position.set(x, y, z); l.userData.nightIntensity = intensity; l.castShadow = false;
  g.add(l); lamps.push(l);
}

function tableLamp(g, x, z, top) {
  lathe(g, [[0, 0], [0.32, 0.02], [0.42, 0.45], [0.36, 0.9], [0.12, 1.05], [0.06, 1.25], [0, 1.25]], x, top, z, '#e9e3d8');
  const shade = cyl(g, 0.42, 0.6, 0.85, x, top + 1.55, z, glow, 32);
  shade.material = glow;
}

const B = {
  rug(g, { w, d, material = 'jute' }) {
    box(g, w, 0.04, d, 0, 0.02, 0, material);
    box(g, w + 0.02, 0.035, 0.25, 0, 0.02, d / 2 - 0.125, '#a68a62'); box(g, w + 0.02, 0.035, 0.25, 0, 0.02, -d / 2 + 0.125, '#a68a62');
  },

  sectional(g, { w, d, leg, material }) {
    const f = fabric(material === 'linen' ? 'white' : material);
    const seatH = 1.35, backH = 2.6, arm = 0.75;
    // main run against local -z
    box(g, w, 0.9, d, 0, 0.55, 0, f, 0.15);
    box(g, w, backH - 0.9, 0.85, 0, 0.9 + (backH - 0.9) / 2, -d / 2 + 0.425, f, 0.22);
    box(g, arm, 1.3, d, w / 2 - arm / 2, 1.3, 0, f, 0.2);
    // leg running from the left end toward +z
    const lw = leg?.w ?? 3.4, ld = leg?.d ?? 5.5;
    const lx = -w / 2 + lw / 2, lz = d / 2 + (ld - d) / 2 - (d - 0) / 2 + d / 2;
    box(g, lw, 0.9, ld - d, lx, 0.55, d / 2 + (ld - d) / 2, f, 0.15);
    box(g, 0.85, backH - 0.9, ld, -w / 2 + 0.425, 0.9 + (backH - 0.9) / 2, -d / 2 + ld / 2, f, 0.22);
    box(g, lw, 1.3, arm, lx, 1.3, -d / 2 + ld - arm / 2, f, 0.2);
    // seat and back cushions
    const n = Math.max(2, Math.round((w - lw - arm) / 3));
    const cw = (w - 0.85 - arm) / n;
    for (let k = 0; k < n; k++) {
      const x = -w / 2 + 0.85 + cw * (k + 0.5);
      box(g, cw - 0.05, 0.42, d - 0.95, x, seatH - 0.15, 0.4, f, 0.17);
      box(g, cw - 0.1, 1.45, 0.55, x, seatH + 0.75, -d / 2 + 1.05, f, 0.25).rotation.x = -0.12;
    }
    const ln = Math.max(1, Math.round((ld - d - arm) / 3));
    for (let k = 0; k < ln; k++) box(g, lw - 0.95, 0.42, (ld - d - arm) / ln - 0.05, lx + 0.4, seatH - 0.15, d / 2 + (ld - d - arm) / ln * (k + 0.5) - 0.2, f, 0.17);
    // throw pillows: sea-glass and sand, as on the concept board
    const pillow = (x, z, ry, m) => { const p = box(g, 1.55, 1.45, 0.42, x, seatH + 0.75, z, m, 0.2); p.rotation.set(-0.25, ry, 0); };
    pillow(-w / 2 + 1.8, -d / 2 + 1.5, 0.4, 'linenSea'); pillow(-w / 2 + 3.0, -d / 2 + 1.55, 0.1, 'linenSand');
    pillow(w / 2 - 1.7, -d / 2 + 1.5, -0.3, 'linenSand'); pillow(-w / 2 + 1.5, d / 2 + 1.2, 1.4, 'linenSea');
  },

  sofa(g, { w, d, material }) {
    const f = fabric(material ?? 'white');
    box(g, w, 0.9, d, 0, 0.55, 0, f, 0.15);
    box(g, w, 1.7, 0.85, 0, 1.75, -d / 2 + 0.425, f, 0.22);
    for (const s of [-1, 1]) box(g, 0.75, 1.3, d, s * (w / 2 - 0.375), 1.3, 0, f, 0.2);
    const n = Math.max(2, Math.round((w - 1.5) / 3)), cw = (w - 1.5) / n;
    for (let k = 0; k < n; k++) box(g, cw - 0.05, 0.42, d - 0.95, -w / 2 + 0.75 + cw * (k + 0.5), 1.2, 0.4, f, 0.17);
  },

  // lanai sofa and club chairs (p5 back rendering, p7 board): open teak frames, off-white canvas cushions
  // with welt piping, throw pillows
  'outdoor-sofa'(g, { w, d }) {
    teakLounge(g, w, d, { seats: 3, pillows: ['pillowStripe', 'linenSand', 'pillowStripe', 'linenSand', 'pillowStripe'] });
  },

  'outdoor-chair'(g, { w = 2.8, d = 2.8 }) {
    teakLounge(g, w, d, { seats: 1, pillows: ['linenSand'] });
  },

  armchair(g, { w = 2.9, d = 2.9, material, frame = 'oak' }) {
    const wood = frame === 'oak' ? 'woodOak' : 'teak', f = fabric(material ?? 'white');
    for (const s of [-1, 1]) {
      // open side frame: two legs, a wide flat arm and a low rail
      for (const z of [d / 2 - 0.12, -d / 2 + 0.12]) box(g, 0.2, 2.0, 0.2, s * (w / 2 - 0.12), 1.0, z, wood, 0.04);
      box(g, 0.42, 0.12, d + 0.05, s * (w / 2 - 0.16), 2.05, 0, wood, 0.04);
      box(g, 0.14, 0.14, d - 0.2, s * (w / 2 - 0.12), 0.55, 0, wood, 0.03);
    }
    box(g, w - 0.44, 0.15, d - 0.2, 0, 0.9, 0, wood, 0.03);
    box(g, w - 0.5, 0.45, d - 0.6, 0, 1.2, 0.2, f, 0.17);
    const back = box(g, w - 0.6, 1.5, 0.5, 0, 2.0, -d / 2 + 0.45, f, 0.22); back.rotation.x = -0.2;
    box(g, w - 0.44, 1.7, 0.12, 0, 1.75, -d / 2 + 0.1, wood, 0.03).rotation.x = -0.15;
  },

  'coffee-round'(g, { w, material }) {
    const r = w / 2;
    cyl(g, r, r, 0.12, 0, 1.33, 0, 'woodOak', 48);
    cyl(g, r * 0.62, r * 0.7, 1.27, 0, 0.635, 0, 'woodOak', 48);
    // a woven tray and a coffee-table book, like the concept board
    cyl(g, 0.75, 0.7, 0.12, r * 0.25, 1.45, -r * 0.15, 'rattan');
    box(g, 1.1, 0.12, 0.85, -r * 0.35, 1.45, r * 0.2, '#d9d2c3').rotation.y = 0.3;
  },

  'coffee-rect'(g, { w, d }) {
    box(g, w, 0.12, d, 0, 1.25, 0, 'teak', 0.03);
    for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) box(g, 0.18, 1.2, 0.18, sx * (w / 2 - 0.2), 0.6, sz * (d / 2 - 0.2), 'teak');
    box(g, w - 0.4, 0.06, d - 0.4, 0, 0.35, 0, 'teak');
  },

  'side-table'(g, { w = 1.7, lamp }) {
    cyl(g, w / 2, w / 2, 0.1, 0, 2.0, 0, 'woodOak', 32);
    cyl(g, 0.12, 0.12, 1.95, 0, 0.98, 0, 'black', 12);
    cyl(g, w / 2 * 0.7, w / 2 * 0.7, 0.05, 0, 0.03, 0, 'black', 24);
    if (lamp) tableLamp(g, 0, 0, 2.05);
  },

  nightstand(g, { w = 2.2, d = 1.6, lamp }) {
    box(g, w, 2.1, d, 0, 1.05, 0, 'woodOak', 0.03);
    for (const y of [0.6, 1.45]) { box(g, w - 0.2, 0.7, 0.03, 0, y, d / 2 + 0.01, 'woodOak'); box(g, 0.5, 0.05, 0.05, 0, y + 0.15, d / 2 + 0.05, 'black'); }
    if (lamp) tableLamp(g, 0, 0, 2.1);
  },

  bench(g, { w, d }) {
    box(g, w * 0.92, 0.55, d * 0.8, 0, 1.3, 0, 'linenSand', 0.15);
    for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) box(g, 0.15, 1.05, 0.15, sx * (w * 0.46 - 0.2), 0.52, sz * (d * 0.4 - 0.2), 'woodOak');
  },

  media(g, { w, d }) {
    box(g, w, 1.9, d, 0, 1.15, 0, 'woodOak', 0.03);
    const n = Math.round(w / 2);
    for (let k = 0; k < n; k++) for (let f = 0; f < 10; f++) box(g, 0.05, 1.5, 0.04, -w / 2 + (w / n) * (k + (f + 0.5) / 10), 1.15, d / 2 + 0.02, 'woodOak');
    box(g, w, 0.2, d - 0.1, 0, 0.1, 0, 'black');
    cyl(g, 0.35, 0.3, 0.9, w / 2 - 0.8, 2.55, 0, '#d8d3c8');
  },

  tv(g, { w = 6, elevation = 4.6 }) {
    const h = w * 0.5625;
    box(g, w, h, 0.12, 0, elevation, -0.0, 'screen');
    box(g, w + 0.06, h + 0.06, 0.08, 0, elevation, -0.05, 'blackMatte');
  },

  dining(g, { w, d, chairs = 8, ends = 2 }) {
    // white oak table with a chunky trestle base
    box(g, w, 0.16, d, 0, 2.42, 0, 'woodOak', 0.03);
    for (const s of [-1, 1]) { box(g, 0.35, 2.3, d * 0.7, s * (w / 2 - 1.2), 1.17, 0, 'woodOak', 0.03); box(g, 0.5, 0.15, d * 0.8, s * (w / 2 - 1.2), 0.08, 0, 'woodOak'); }
    box(g, w - 2.2, 0.3, 0.3, 0, 0.8, 0, 'woodOak');
    const side = (chairs - ends) / 2;
    for (let k = 0; k < side; k++) for (const s of [-1, 1]) {
      const c = new THREE.Group(); caneChair(c);
      c.position.set(-w / 2 + (k + 0.5) * w / side, 0, s * (d / 2 + 0.55)); c.rotation.y = s < 0 ? 0 : Math.PI; g.add(c);
    }
    for (let k = 0; k < ends; k++) {
      const c = new THREE.Group(); caneChair(c);
      const s = k ? 1 : -1;
      c.position.set(s * (w / 2 + 0.6), 0, 0); c.rotation.y = -s * Math.PI / 2; g.add(c);
    }
    // centrepiece: a long carved oak dough bowl with a few tropical leaves
    const bowl = lathe(g, [[0, 0], [0.5, 0.02], [0.75, 0.25], [0.8, 0.38], [0.7, 0.38], [0.55, 0.12], [0, 0.1]], 0, 2.5, 0, 'woodOak'); bowl.scale.set(2.6, 1, 0.8);
    monstera(g, -0.4, 2.75, 0, 0.45); monstera(g, 0.5, 2.75, 0.05, 0.4);
  },

  'outdoor-dining'(g, { w, d, chairs = 8, ends = 2 }) {
    box(g, w, 0.14, d, 0, 2.42, 0, 'teak', 0.03);
    for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) box(g, 0.28, 2.35, 0.28, sx * (w / 2 - 0.35), 1.17, sz * (d / 2 - 0.35), 'teak');
    const side = (chairs - ends) / 2;
    for (let k = 0; k < side; k++) for (const s of [-1, 1]) {
      const c = new THREE.Group(); teakDiningChair(c);
      c.position.set(-w / 2 + (k + 0.5) * w / side, 0, s * (d / 2 + 0.55)); c.rotation.y = s < 0 ? 0 : Math.PI; g.add(c);
    }
    for (let k = 0; k < ends; k++) { const c = new THREE.Group(); teakDiningChair(c); const s = k ? 1 : -1; c.position.set(s * (w / 2 + 0.6), 0, 0); c.rotation.y = -s * Math.PI / 2; g.add(c); }
    lathe(g, [[0, 0], [0.5, 0], [0.55, 0.25], [0, 0.25]], 0, 2.5, 0, 'rattan');
  },

  pendant(g, { drop = 9, style = 'rattan', size = 2.4, ceiling }) {
    const top = ceiling, y = top - drop;
    if (style === 'rattan') {
      const shade = lathe(g, Array.from({ length: 12 }, (_, k) => { const a = k / 11 * Math.PI * 0.62; return [Math.sin(a) * size / 2, -Math.cos(a) * size / 2 * 0.8 + size * 0.4]; }), 0, y, 0, 'cane');
      shade.material = mat('cane'); shade.scale.y = -1; shade.position.y = y + size * 0.6;
      cyl(g, 0.012, 0.012, top - y - size * 0.4, 0, (top + y + size * 0.4) / 2, 0, 'black', 6);
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.18, 12, 8), glow); bulb.position.set(0, y + 0.3, 0); g.add(bulb);
      addLamp(g, 0, y + 0.2, 0, 10, 22);
    } else {
      const ball = new THREE.Mesh(new THREE.SphereGeometry(size / 2, 24, 16), glow); ball.position.set(0, y, 0); g.add(ball);
      cyl(g, 0.1, 0.12, 0.2, 0, y + size / 2, 0, 'brass', 12);
      cyl(g, 0.01, 0.01, top - y - size / 2, 0, (top + y + size / 2) / 2, 0, 'black', 6);
      addLamp(g, 0, y - 0.2, 0, 5, 14);
    }
  },

  fan(g, { ceiling }) {
    // black three-blade fan from the concept board's lanai
    const y = Math.max(8.6, Math.min(ceiling - 1.6, 11));
    cyl(g, 0.04, 0.04, ceiling - y, 0, (ceiling + y) / 2, 0, 'black', 8);
    lathe(g, [[0, 0], [0.42, 0.04], [0.45, 0.28], [0.2, 0.42], [0, 0.42]], 0, y - 0.3, 0, 'black');
    const hub = new THREE.Group(); hub.position.y = y - 0.15; g.add(hub);
    for (let k = 0; k < 3; k++) {
      const blade = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 8), mat('blackMatte'));
      blade.scale.set(1.25, 0.035, 0.3);
      blade.position.set(Math.cos(k * 2.094) * 1.45, 0, Math.sin(k * 2.094) * 1.45);
      blade.rotation.set(0.12, -k * 2.094, 0);
      blade.scale.z = 1; hub.add(blade);
    }
    hub.rotation.y = 0.4;
  },

  plant(g, { w = 2, h = 6.5 }) {
    lathe(g, [[0, 0], [0.7, 0], [0.85, 1.4], [0.8, 1.5], [0, 1.5]], 0, 0, 0, 'rattan');
    cyl(g, 0.06, 0.08, h - 2, 0, 1.5 + (h - 2) / 2, 0, '#6b5640', 6);
    fiddle(g, 0, h, 0, w);
  },

  island(g, { w, d, sink = true, top = 'quartz' }) {
    // white oak shaker island, quartz top, 1 ft seating overhang on local -x
    box(g, w - 1, 3.0, d, 0.5, 1.5, 0, 'woodOak', 0.02);
    shakerFronts(g, d, 3.0, 0.5 + (w - 1) / 2 + 0.01, 0, Math.PI / 2);
    box(g, w, 0.13, d + 0.1, 0, 3.06, 0, top, 0.02);
    box(g, w - 1.2, 0.35, d - 0.2, 0.5, 0.17, 0, 'blackMatte');
    if (sink) {
      box(g, 1.1, 0.02, 2.0, 0.6, 3.13, 0, '#3a3a3a');
      faucet(g, 1.25, 3.12, 0, -Math.PI / 2);
    }
  },

  counter(g, { w, d, top = 'quartz', uppers, range }) {
    box(g, w, 3.0, d, 0, 1.5, 0, 'woodOak', 0.02);
    shakerFronts(g, w, 3.0, 0, d / 2 + 0.01, 0);
    box(g, w + 0.05, 0.13, d + 0.08, 0, 3.06, 0.04, top, 0.02);
    box(g, w, 0.35, d - 0.3, 0, 0.17, -0.15, 'blackMatte');
    // backsplash: coral-toned zellige-like tile band
    box(g, w, 1.6, 0.04, 0, 3.92, -d / 2 + 0.02, 'quartz');
    if (range) {
      box(g, 3.0, 3.05, d + 0.05, 0, 1.52, 0.03, 'steel', 0.03);
      box(g, 2.8, 0.06, d - 0.2, 0, 3.07, 0.02, '#1a1a1a');
      for (const x of [-0.7, 0.7]) for (const z of [-0.45, 0.45]) cyl(g, 0.28, 0.28, 0.05, x, 3.11, z, 'black', 16);
      for (let k = 0; k < 6; k++) cyl(g, 0.06, 0.06, 0.12, -1.2 + k * 0.48, 2.8, d / 2 + 0.09, 'steel', 10).rotation.x = Math.PI / 2;
      box(g, 2.5, 1.5, 0.05, 0, 1.4, d / 2 + 0.06, '#2b2b2b');
    }
    if (uppers === 'hood') {
      // white plaster hood that tapers into the ceiling
      lathe(g, [[1.9, 0], [1.9, 0.5], [1.2, 2.2], [1.2, 4.5], [0, 4.5]], 0, 5.9, -d / 2 + 1.0, 'paint', 4).rotation.y = Math.PI / 4;
    } else if (uppers === 'shelves') {
      for (const y of [5.3, 6.6]) {
        box(g, w - 0.2, 0.15, 1.0, 0, y, -d / 2 + 0.5, 'woodOak', 0.02);
        // dishes and jars on the shelves
        for (let k = 0; k < Math.floor(w / 0.9); k++) {
          const x = -w / 2 + 0.6 + k * 0.9;
          if ((k + (y > 6 ? 1 : 0)) % 3 === 0) cyl(g, 0.22, 0.2, 0.5, x, y + 0.33, -d / 2 + 0.5, '#f2efe8', 16);
          else if ((k + (y > 6 ? 1 : 0)) % 3 === 1) for (let p = 0; p < 4; p++) cyl(g, 0.38, 0.32, 0.04, x, y + 0.1 + p * 0.05, -d / 2 + 0.5, '#ebe6dc', 20);
          else lathe(g, [[0, 0], [0.18, 0], [0.22, 0.4], [0.1, 0.6], [0, 0.6]], x, y + 0.08, -d / 2 + 0.5, '#c9b89d');
        }
      }
    }
  },

  fridge(g, { w, d }) {
    box(g, w - 0.04, 7.2, d, 0, 3.6, 0, 'woodOak', 0.02);
    box(g, 0.02, 7.0, 0.02, 0, 3.6, d / 2 + 0.01, '#6d5a42');
    for (const s of [-1, 1]) box(g, 0.07, 2.4, 0.07, s * 0.2, 3.8, d / 2 + 0.12, 'black');
  },

  stool(g) {
    // woven rattan counter stool, oak legs
    lathe(g, [[0, 0], [0.75, 0], [0.75, 0.25], [0, 0.25]], 0, 2.05, 0, 'rattan');
    const back = lathe(g, Array.from({ length: 8 }, (_, k) => [0.78, k * 0.12]), 0, 2.3, 0, 'cane');
    back.material = mat('cane'); back.scale.z = 0.5; back.position.z = -0.3;
    for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) { const l = cyl(g, 0.05, 0.06, 2.1, sx * 0.48, 1.03, sz * 0.48, 'woodOak', 8); l.rotation.set(sz * 0.06, 0, -sx * 0.06); }
    box(g, 1.0, 0.05, 0.05, 0, 0.8, 0.5, 'woodOak'); box(g, 1.0, 0.05, 0.05, 0, 0.8, -0.5, 'woodOak');
  },

  bed(g, { w, d, material }) {
    const f = 'woodOak';
    box(g, w, 1.05, d, 0, 0.62, 0, f, 0.12);
    box(g, w + 0.2, 4.4, 0.5, 0, 2.2, -d / 2 + 0.25, f, 0.2);
    const cane = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.8, 2.3), mat('cane')); cane.position.set(0, 3.15, -d / 2 + 0.52); g.add(cane);
    box(g, w - 0.6, 0.1, 0.06, 0, 4.35, -d / 2 + 0.52, 'woodOak'); box(g, w - 0.6, 0.1, 0.06, 0, 1.95, -d / 2 + 0.52, 'woodOak');
    box(g, w - 0.3, 0.85, d - 0.55, 0, 1.55, 0.18, 'linenWhite', 0.2);                      // mattress + duvet
    box(g, w - 0.1, 0.3, d * 0.6, 0, 1.95, d * 0.18, 'linenWhite', 0.15);                  // duvet fold
    box(g, w + 0.05, 0.12, 1.4, 0, 2.06, d / 2 - 1.0, 'linenSea', 0.06);                  // throw at the foot
    for (const s of [-1, 1]) {
      box(g, w / 2 - 0.35, 1.6, 0.45, s * w / 4, 2.6, -d / 2 + 0.85, 'linenWhite', 0.22).rotation.x = -0.25;
      box(g, w / 2 - 0.6, 1.1, 0.4, s * w / 4, 2.35, -d / 2 + 1.25, 'linenWhite', 0.2).rotation.x = -0.2;
    }
    box(g, 1.4, 0.9, 0.35, 0, 2.3, -d / 2 + 1.55, 'linenSea', 0.18).rotation.x = -0.25;
  },

  tub(g, { w, d }) {
    // freestanding oval soaking tub with a black floor-mounted filler
    const t = lathe(g, [[0, 0], [0.9, 0], [1.25, 0.35], [1.38, 1.4], [1.42, 1.85], [1.3, 1.85], [1.18, 0.5], [0, 0.45]], 0, 0, 0, 'porcelain', 48);
    t.scale.set(w / 2.84, 1, d / 2.84);
    const water = new THREE.Mesh(new THREE.CircleGeometry(1.2, 40), mat('water')); water.rotation.x = -Math.PI / 2; water.position.y = 1.45; water.scale.set(w / 2.84, d / 2.84, 1); g.add(water);
    cyl(g, 0.06, 0.06, 3.2, -w / 2 - 0.4, 1.6, 0, 'black', 10);
    const spout = cyl(g, 0.04, 0.04, 0.9, -w / 2 - 0.05, 3.15, 0, 'black', 8); spout.rotation.z = Math.PI / 2;
  },

  shower(g, { w, d }) {
    box(g, w - 0.1, 0.08, d - 0.1, 0, 0.04, 0, 'coral');
    box(g, 0.08, 0.08, 0.6, 0, 6.8, -d / 2 + 0.35, 'black'); cyl(g, 0.45, 0.45, 0.04, 0, 6.75, -d / 2 + 0.7, 'black', 24);
    box(g, 0.1, 0.4, 0.1, w / 2 - 0.8, 3.8, -d / 2 + 0.06, 'black');
    // frameless glass on the open side with a slim black header
    const glass = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.1, 7.2), mat('glass')); glass.position.set(0, 3.65, d / 2 - 0.05); glass.renderOrder = 2; g.add(glass);
    box(g, w, 0.06, 0.06, 0, 7.25, d / 2 - 0.05, 'black');
    box(g, 0.05, 1.5, 0.05, w * 0.15, 3.6, d / 2 + 0.05, 'black');
  },

  toilet(g, { w = 1.6, d = 2.4 }) {
    box(g, 1.55, 1.3, 0.75, 0, 2.2, -d / 2 + 0.38, 'porcelain', 0.15);
    lathe(g, [[0, 0], [0.45, 0], [0.62, 0.9], [0.7, 1.35], [0, 1.35]], 0, 0, 0.15, 'porcelain', 32).scale.set(1, 1, 1.3);
    box(g, 1.3, 0.08, 1.7, 0, 1.4, 0.2, 'porcelain', 0.04);
  },

  vanity(g, { w, d, double }) {
    // white oak shaker vanity with open lower shelf, quartz top, black fixtures, rounded black mirrors
    box(g, w, 2.2, d, 0, 1.75, 0, 'woodOak', 0.02);
    shakerFronts(g, w, 2.0, 0, d / 2 + 0.01, 0, 1.75);
    box(g, w, 0.1, d, 0, 0.45, 0, 'woodOak');
    for (const sx of [-1, 1]) box(g, 0.2, 0.5, d, sx * (w / 2 - 0.1), 0.25, 0, 'woodOak');
    box(g, w + 0.05, 0.12, d + 0.05, 0, 2.91, 0.02, 'quartz', 0.02);
    // rolled towels on the open shelf
    for (let k = 0; k < Math.floor(w / 1.4); k++) { const t = cyl(g, 0.22, 0.22, 1.1, -w / 2 + 0.8 + k * 1.4, 0.73, 0, 'linenWhite', 16); t.rotation.z = Math.PI / 2; }
    const sinks = double ? [-w / 4, w / 4] : [0];
    for (const x of sinks) {
      box(g, 1.3, 0.02, 0.95, x, 2.98, 0.1, '#e9e7e2');
      faucet(g, x, 2.97, -d / 2 + 0.3, 0);
      mirror(g, x, 5.2, -d / 2 - 0.02, Math.min(2.3, w / sinks.length - 0.6), 3.2);
      sconce(g, x + (double ? -1 : 0) * 0 + Math.min(1.5, w / sinks.length / 2), 6.7, -d / 2 - 0.02);
    }
  },

  wardrobe(g, { w, d }) {
    box(g, w, 8, 0.1, 0, 4, -d / 2 + 0.05, 'woodOak');
    box(g, w, 0.1, d, 0, 7.0, 0, 'woodOak'); box(g, w, 0.1, d, 0, 1.0, 0, 'woodOak');
    cyl(g, 0.04, 0.04, w - 0.2, 0, 6.6, 0, 'brass', 8).rotation.z = Math.PI / 2;
    const tones = ['#f1ece2', '#d9cdb8', '#9fb5b3', '#e8e2d6', '#c6b39a', '#f6f4ef', '#8a9b9a'];
    for (let k = 0; k < Math.floor(w / 0.35); k++) box(g, 0.25, 3 + (k % 3) * 0.6, d * 0.8, -w / 2 + 0.3 + k * 0.35, 6.4 - (3 + (k % 3) * 0.6) / 2, 0, tones[k % tones.length], 0.08);
  },

  washer(g, { w, d }) {
    box(g, w, 6.2, d, 0, 3.1, 0, '#f2f2ef', 0.08);
    for (const y of [1.5, 4.6]) { const ring = new THREE.Mesh(new THREE.TorusGeometry(0.75, 0.08, 8, 32), mat('steel')); ring.position.set(0, y, d / 2 + 0.02); g.add(ring); const door = new THREE.Mesh(new THREE.CircleGeometry(0.7, 32), mat('glass')); door.position.set(0, y, d / 2 + 0.03); g.add(door); }
  },

  grill(g, { w, d }) {
    // outdoor kitchen: coral stone base, quartz top, built-in stainless grill
    box(g, w, 3.0, d, 0, 1.5, 0, 'coral', 0.02);
    box(g, w + 0.15, 0.15, d + 0.15, 0, 3.07, 0.02, 'quartz', 0.02);
    // stainless grill with a domed lid, teak doors either side
    box(g, 3.0, 0.5, d * 0.8, 0, 3.4, 0, 'steel', 0.05);
    const lid = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 3.0, 24, 1, false, 0, Math.PI), mat('steel')); lid.rotation.z = Math.PI / 2; lid.position.set(0, 3.65, 0); g.add(lid);
    box(g, 2.8, 0.06, 0.06, 0, 3.4, d * 0.4 + 0.1, 'steel');
    for (const sx of [-1, 1]) for (let k = 0; k < 2; k++) {
      const x = sx * (2.0 + k * 1.8);
      if (Math.abs(x) + 0.85 > w / 2) continue;
      box(g, 1.6, 2.3, 0.06, x, 1.45, d / 2 + 0.03, 'teak', 0.02);
      box(g, 0.05, 0.6, 0.05, x - sx * 0.6, 1.9, d / 2 + 0.1, 'black');
    }
    box(g, 2.6, 2.0, 0.04, 0, 1.45, d / 2 + 0.02, 'steel');
  },

  lounger(g, { w = 2.3, d = 6.3 }) { chaiseInto(g, w, d); },

  // Framed art: an abstract ocean horizon or a kapa-pattern print, oak frame, linen mat.
  art(g, { w = 4, h = 3, style = 'ocean', elevation = 5.4 }) {
    box(g, w + 0.3, h + 0.3, 0.12, 0, elevation, 0.06, 'woodOak');
    const pic = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.3, h - 0.3), new THREE.MeshStandardMaterial({ map: artTexture(style), roughness: 0.85 }));
    pic.position.set(0, elevation, 0.16); g.add(pic);
    box(g, w - 0.05, h - 0.05, 0.02, 0, elevation, 0.12, 'linenWhite');
  },

  basket(g, { w = 1.6, h = 1.5, plant }) {
    lathe(g, [[0, 0], [w * 0.42, 0], [w * 0.5, h * 0.8], [w * 0.48, h], [w * 0.44, h], [w * 0.4, 0.1], [0, 0.1]], 0, 0, 0, 'jute');
    if (plant) fiddle(g, 0, h + 3.5, 0, w * 1.2);
  },

  // Coral-stone feature wall panel (the concept board's porous coral).
  stonepanel(g, { w, h = 10, d = 0.35 }) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat('coralWall'));
    m.position.set(0, h / 2, 0); g.add(m);
  },

  golfcart(g) {
    // two-seat golf cart, white body, black seats and roof posts
    box(g, 3.9, 1.2, 8.0, 0, 1.4, 0, '#f2f2ef', 0.3);
    box(g, 3.7, 0.8, 1.6, 0, 2.2, 0.4, '#202020', 0.2); box(g, 3.7, 1.8, 0.4, 0, 2.9, -0.5, '#202020', 0.15);
    for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) box(g, 0.1, 3.4, 0.1, sx * 1.75, 3.9, sz * 2.0 + 0.3, 'black');
    box(g, 4.1, 0.15, 5.0, 0, 5.65, 0.3, '#f2f2ef', 0.05);
    for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) { const w = cyl(g, 0.75, 0.75, 0.55, sx * 1.75, 0.75, sz * 2.7, '#1b1b1b', 18); w.rotation.z = Math.PI / 2; }
    box(g, 2.6, 0.08, 0.9, 0, 3.4, 2.4, 'glass');
  },

  'outdoor-shower'(g) {
    box(g, 0.2, 7.5, 0.2, 0, 3.75, 0, 'teak');
    box(g, 0.08, 0.08, 1.2, 0, 7.3, 0.5, 'black'); cyl(g, 0.4, 0.4, 0.04, 0, 7.25, 1.0, 'black', 24);
    box(g, 2.6, 0.15, 1.2, 1.8, 1.5, -0.4, 'teak');
    monstera(g, 2.6, 0, 2.4, 1.6);
  },
};

// ---------- shared parts ----------
// ---------- outdoor upholstery (p5 back rendering, p7 board) ----------
// Own named finishes the Blender pass can target (scripts/materials_bpy.py): 'cushionPiping' (welt cord,
// a shade under the canvas), 'towel' (white terry), 'pillowStripe' (striped outdoor canvas). Cushions stay on
// 'linenWhite' (outdoor canvas recipe: albedo ~0.75, weave normal, pucker); frames 'teak'; woven seats 'rattan'.
const ownMats = new Map();
function ownMat(name, make) { if (!ownMats.has(name)) { const m = make(); m.name = name; ownMats.set(name, m); } return ownMats.get(name); }
const PIPING = () => ownMat('cushionPiping', () => new THREE.MeshStandardMaterial({ color: '#d4cbbb', roughness: 0.85 }));
const TOWEL = () => ownMat('towel', () => new THREE.MeshStandardMaterial({ color: '#efede7', roughness: 0.97 }));
const STRIPE = () => ownMat('pillowStripe', () => {
  const c = document.createElement('canvas'); c.width = 64; c.height = 64;
  const x = c.getContext('2d'); x.fillStyle = '#ece7dd'; x.fillRect(0, 0, 64, 64);
  x.fillStyle = '#8d8a84'; for (let k = 0; k < 64; k += 16) x.fillRect(0, k + 5, 64, 5);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return new THREE.MeshStandardMaterial({ map: t, roughness: 0.9 });
});

// welt piping: a closed cord round a rounded rectangle (w along x, d along z) in the y = 0 plane
const pipeCache = new Map();
function pipeLoop(w, d, rc, rad = 0.022) {
  const k = `${w.toFixed(2)}|${d.toFixed(2)}|${rc.toFixed(3)}|${rad}`;
  if (pipeCache.has(k)) return pipeCache.get(k);
  const pts = [], cx = w / 2 - rc, cz = d / 2 - rc;
  for (const [sx, sz, a0] of [[1, 1, 0], [-1, 1, 90], [-1, -1, 180], [1, -1, 270]])
    for (let i = 0; i <= 3; i++) { const a = (a0 + i * 30) * Math.PI / 180; pts.push(new THREE.Vector3(sx * cx + rc * Math.cos(a), 0, sz * cz + rc * Math.sin(a))); }
  const geo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true, 'centripetal'), 96, rad, 6, true);
  pipeCache.set(k, geo); return geo;
}
// A filled cushion lying flat (w x, t thick in y, d z) with 1-2 cm rounded edges and a welt at both seams.
function cushion(g, w, t, d, x, y, z, m = 'linenWhite', r = 0.05) {
  const c = new THREE.Group(); c.position.set(x, y, z); g.add(c);
  box(c, w, t, d, 0, 0, 0, m, r);
  const e = r * 0.293;                                     // the seam: halfway round the edge radius
  for (const s of [-1, 1]) {
    const p = new THREE.Mesh(pipeLoop(w - 2 * e, d - 2 * e, Math.max(0.02, r * 0.707)), PIPING());
    p.position.y = s * (t / 2 - e); c.add(p);
  }
  return c;
}
// A back cushion: a cushion stood up against the back (its face toward local +z), raked back by `lean`.
function backCushion(g, w, t, h, x, y, z, lean = 0.18, m = 'linenWhite') {
  const c = cushion(g, w, t, h, x, y, z, m, 0.07); c.rotation.x = -Math.PI / 2 - lean; return c;
}
// Throw pillow: a soft square leaned on the back cushions.
function pillow(g, x, y, z, ry, m, s = 1.45) {
  const p = box(g, s, s, 0.38, x, y, z, m === 'pillowStripe' ? STRIPE() : m, 0.17); p.rotation.set(-0.28, ry, 0); return p;
}

// Open teak frame (2 1/2" legs, flat 5" arm planks, open sides, slatted back) with seat and back cushions.
// Local -z is the back; seats across w.
function teakLounge(g, w, d, { seats = 3, pillows = [], backH = 2.45, armH = 1.95 } = {}) {
  const T = 'teak', leg = 0.2, armW = 0.42, inW = w - 2 * leg, inD = d - 2 * leg;
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    const h = sz < 0 ? backH : armH;
    box(g, leg, h, leg, sx * (w / 2 - leg / 2), h / 2, sz * (d / 2 - leg / 2), T, 0.02);
  }
  for (const sx of [-1, 1]) {
    box(g, armW, 0.1, d + 0.06, sx * (w / 2 - armW / 2 + 0.04), armH + 0.05, 0.03, T, 0.03);     // flat arm plank
    box(g, 0.14, 0.24, inD, sx * (w / 2 - leg / 2), 0.9, 0, T, 0.02);                            // seat rail
    box(g, 0.1, 0.1, inD, sx * (w / 2 - leg / 2), 0.3, 0, T, 0.02);                              // low stretcher
  }
  for (const sz of [-1, 1]) box(g, inW, 0.24, 0.14, 0, 0.9, sz * (d / 2 - leg / 2), T, 0.02);
  box(g, inW, 0.06, inD, 0, 0.99, 0, T);                                                         // slatted deck
  box(g, w, 0.15, 0.17, 0, backH - 0.075, -d / 2 + leg / 2, T, 0.03);                            // back top rail
  const ns = Math.max(3, Math.round(inW / 0.42)), sh = backH - 0.15 - 1.02;
  for (let k = 0; k < ns; k++) box(g, 0.22, sh, 0.06, -inW / 2 + (k + 0.5) * inW / ns, 1.02 + sh / 2, -d / 2 + leg / 2, T);
  // cushions: 6" seats on the deck, 5" backs on the seats leaning on the frame
  const cw = inW / seats, seatT = 0.5, seatTop = 1.02 + seatT;
  for (let k = 0; k < seats; k++) {
    const x = -inW / 2 + cw * (k + 0.5);
    cushion(g, cw - 0.03, seatT, inD - 0.02, x, 1.02 + seatT / 2, 0, 'linenWhite', 0.06);
    backCushion(g, cw - 0.05, 0.45, 1.45, x, seatTop + 0.68, -inD / 2 + 0.36, 0.2);
  }
  pillows.forEach((m, k) => {
    const n = pillows.length, x = n === 1 ? 0 : -inW / 2 + 0.85 + k * (inW - 1.7) / (n - 1);
    pillow(g, x, seatTop + 0.66, -inD / 2 + 0.78, n === 1 ? 0 : (x < 0 ? 0.18 : -0.18) * (k % 2 ? 0.5 : 1), m, n > 3 ? 1.3 : 1.45);
  });
}

// Chaise lounge (p5): low teak frame with side rails, a thin canvas pad on the seat and on a raised back,
// welted, and rolled white towels. Local -z is the raised back. Also used by site.js for the pool deck.
export function chaiseInto(g, w = 2.3, d = 6.3) {
  const T = 'teak', leg = 0.22, railH = 0.32, top = 1.0;
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) box(g, leg, top, leg, sx * (w / 2 - leg / 2), top / 2, sz * (d / 2 - leg / 2), T, 0.02);
  for (const sx of [-1, 1]) box(g, 0.13, railH, d, sx * (w / 2 - 0.065), top - railH / 2, 0, T, 0.02);
  for (const sz of [-1, 1]) box(g, w - 0.26, railH, 0.13, 0, top - railH / 2, sz * (d / 2 - 0.065), T, 0.02);
  const hinge = -0.55, inW = w - 0.3, padT = 0.2;
  box(g, inW, 0.05, d / 2 - hinge - 0.15, 0, top - 0.06, (hinge + d / 2 - 0.15) / 2, T);                  // seat slats
  cushion(g, inW, padT, d / 2 - 0.12 - hinge, 0, top - 0.035 + padT / 2, (hinge + d / 2 - 0.12) / 2, 'linenWhite', 0.05);
  // raised back: slatted panel hinged at the seat, propped at ~35 deg, its own pad
  const bl = hinge + d / 2 - 0.15, back = new THREE.Group(); back.position.set(0, top - 0.035, hinge); back.rotation.x = 0.6; g.add(back);
  box(back, inW, 0.05, bl, 0, -0.025, -bl / 2, T);
  for (const sx of [-1, 1]) box(back, 0.1, 0.14, bl, sx * (inW / 2 - 0.05), -0.1, -bl / 2, T, 0.02);
  cushion(back, inW, padT, bl - 0.05, 0, padT / 2, -bl / 2, 'linenWhite', 0.05);
  box(g, inW - 0.2, 0.08, 0.1, 0, top + 0.52, hinge - 1.0, T);                                            // prop bar under the back
  for (const sx of [-1, 1]) box(g, 0.08, 0.52, 0.08, sx * (inW / 2 - 0.15), top + 0.26, hinge - 1.0, T);
  // rolled towels: two side by side and one on top, on the seat just below the back
  const seatTop = top - 0.035 + padT, rr = 0.17, tl = 1.25, tz = hinge + 0.75;
  for (const [x, y] of [[0, rr], [0, 3 * rr]]) {
    const n = y > rr ? 1 : 2;
    for (let i = 0; i < n; i++) {
      const tw = new THREE.Mesh(new THREE.CylinderGeometry(rr, rr, tl, 18), TOWEL());
      tw.rotation.z = Math.PI / 2; tw.position.set(x + 0.04 * (i ? 1 : -1) * (n - 1), seatTop + y - 0.02 - (y > rr ? 0.05 : 0), tz + (n > 1 ? (i - 0.5) * 2 * rr : 0)); g.add(tw);
      for (const s of [-1, 1]) {                                                                       // rolled ends
        const end = new THREE.Mesh(new THREE.TorusGeometry(rr * 0.55, 0.02, 4, 18), PIPING());
        end.rotation.y = Math.PI / 2; end.position.set(tw.position.x + s * (tl / 2 + 0.003), tw.position.y, tw.position.z); g.add(end);
      }
    }
  }
}

function caneChair(g) {
  // oak frame, cane back panel, upholstered seat
  for (const [sx, sz] of [[-1, 1], [1, 1]]) cyl(g, 0.06, 0.06, 1.55, sx * 0.72, 0.78, sz * 0.7, 'woodOak', 8);
  for (const sx of [-1, 1]) { const p = box(g, 0.13, 3.2, 0.13, sx * 0.72, 1.6, -0.72, 'woodOak', 0.03); p.rotation.x = -0.08; }
  box(g, 1.6, 0.3, 1.6, 0, 1.55, 0, 'linenWhite', 0.1);
  const back = new THREE.Mesh(new THREE.PlaneGeometry(1.32, 1.3), mat('cane')); back.position.set(0, 2.5, -0.78); back.rotation.x = -0.08; g.add(back);
  box(g, 1.5, 0.13, 0.13, 0, 3.15, -0.82, 'woodOak', 0.03);
  box(g, 1.5, 0.1, 0.1, 0, 1.85, -0.74, 'woodOak');
}

function teakDiningChair(g) {
  // p5 lanai dining chair: teak frame, woven seat and a woven back panel in a raked teak frame
  for (const sx of [-1, 1]) {
    box(g, 0.14, 1.5, 0.14, sx * 0.7, 0.75, 0.66, 'teak', 0.02);                                 // front legs
    box(g, 0.14, 2.95, 0.14, sx * 0.7, 1.47, -0.68, 'teak', 0.02).rotation.x = -0.05;              // back legs / stiles
    box(g, 0.1, 0.16, 1.2, sx * 0.7, 1.42, -0.01, 'teak', 0.02);                                  // side rails
    box(g, 0.07, 0.07, 1.2, sx * 0.7, 0.45, -0.01, 'teak');                                       // stretchers
  }
  for (const z of [0.66, -0.68]) box(g, 1.26, 0.16, 0.1, 0, 1.42, z, 'teak', 0.02);
  box(g, 1.28, 0.08, 1.26, 0, 1.53, -0.01, 'rattan', 0.03);                                       // woven seat
  const back = new THREE.Group(); back.position.set(0, 2.35, -0.73); back.rotation.x = -0.1; g.add(back);
  box(back, 1.28, 0.95, 0.05, 0, 0, 0, 'rattan', 0.02);                                             // woven back
  box(back, 1.54, 0.14, 0.12, 0, 0.53, 0, 'teak', 0.03);                                            // top rail
  box(back, 1.28, 0.08, 0.08, 0, -0.5, 0, 'teak', 0.02);
}

function shakerFronts(g, w, h, x, z, ry, yc = h / 2) {
  const n = Math.max(1, Math.round(w / 1.8)), dw = w / n;
  const grp = new THREE.Group(); grp.position.set(x, 0, z); grp.rotation.y = ry; g.add(grp);
  for (let k = 0; k < n; k++) {
    const cx = -w / 2 + dw * (k + 0.5);
    for (const [ox, oy, ww, hh] of [[0, h / 2 - 0.12, dw - 0.08, 0.2], [0, -h / 2 + 0.25, dw - 0.08, 0.2], [-dw / 2 + 0.14, 0, 0.2, h - 0.2], [dw / 2 - 0.14, 0, 0.2, h - 0.2]])
      box(grp, ww, hh, 0.05, cx + ox, yc + oy, 0.03, 'woodOak');
    box(grp, 0.05, 0.6, 0.05, cx + dw / 2 - 0.3, yc + h / 2 - 0.55, 0.09, 'black');
  }
}

function faucet(g, x, y, z, ry) {
  const f = new THREE.Group(); f.position.set(x, y, z); f.rotation.y = ry; g.add(f);
  cyl(f, 0.06, 0.07, 1.0, 0, 0.5, 0, 'black', 12);
  const arc = new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.045, 8, 16, Math.PI), mat('black')); arc.position.set(0, 1.0, 0.28); arc.rotation.y = Math.PI / 2; f.add(arc);
  cyl(f, 0.04, 0.04, 0.2, 0, 0.9, 0.56, 'black', 8);
}

function mirror(g, x, y, z, w, h) {
  const shape = new THREE.Shape(), r = Math.min(w, h) * 0.22;
  shape.moveTo(-w / 2 + r, -h / 2); shape.lineTo(w / 2 - r, -h / 2); shape.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
  shape.lineTo(w / 2, h / 2 - r); shape.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2); shape.lineTo(-w / 2 + r, h / 2);
  shape.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r); shape.lineTo(-w / 2, -h / 2 + r); shape.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
  const frame = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.08, bevelEnabled: false }), mat('black'));
  frame.position.set(x, y, z + 0.0); g.add(frame);
  const glassM = new THREE.Mesh(new THREE.ShapeGeometry(shape), mat('mirror'));
  glassM.scale.set((w - 0.12) / w, (h - 0.12) / h, 1); glassM.position.set(x, y, z + 0.09); g.add(glassM);
}

function sconce(g, x, y, z) {
  box(g, 0.12, 0.12, 0.6, x, y, z + 0.3, 'black');
  const b = new THREE.Mesh(new THREE.SphereGeometry(0.14, 12, 8), glow); b.position.set(x, y + 0.12, z + 0.6); g.add(b);
}

const LEAF = new THREE.Shape(); LEAF.moveTo(0, 0); LEAF.quadraticCurveTo(0.5, 0.4, 0, 1.2); LEAF.quadraticCurveTo(-0.5, 0.4, 0, 0);
const leafGeo = new THREE.ShapeGeometry(LEAF, 6);
function fiddle(g, x, top, z, w) {
  const r = mulberry(Math.round(x * 100 + z * 7 + top));
  const m = mat('#3d5f2c');
  for (let k = 0; k < 46; k++) {
    const leaf = new THREE.Mesh(leafGeo, m);
    const h = top - r() * (top - 2.2) * 0.85, a = r() * Math.PI * 2, rad = r() * w * 0.45;
    leaf.position.set(x + Math.cos(a) * rad, h, z + Math.sin(a) * rad);
    leaf.rotation.set(-0.6 - r() * 0.8, a, 0); leaf.scale.setScalar(0.6 + r() * 0.5);
    leaf.material.side = THREE.DoubleSide;
    g.add(leaf);
  }
}
function monstera(g, x, y, z, s) {
  const r = mulberry(Math.round(x * 31 + z * 17 + y * 5) + 3), m = mat('#2f5a2a');
  for (let k = 0; k < 7; k++) {
    const leaf = new THREE.Mesh(leafGeo, m);
    leaf.material.side = THREE.DoubleSide;
    leaf.position.set(x, y, z); leaf.rotation.set(-0.3 - r() * 0.9, r() * Math.PI * 2, 0); leaf.scale.set(s * 1.4, s, 1);
    g.add(leaf);
  }
}
function mulberry(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

const artCache = new Map();
function artTexture(style) {
  if (artCache.has(style)) return artCache.get(style);
  const c = document.createElement('canvas'); c.width = 768; c.height = 576; const x = c.getContext('2d');
  let s = style.length * 97; const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  if (style === 'kapa') {
    // Hawaiian kapa: earth-brown bands of triangles and chevrons on cream bark cloth
    x.fillStyle = '#e9dcc4'; x.fillRect(0, 0, 768, 576);
    for (let i = 0; i < 4000; i++) { x.fillStyle = `rgba(150,120,80,${r() * 0.06})`; x.fillRect(r() * 768, r() * 576, 2 + r() * 6, 1); }
    const bands = 6;
    for (let b = 0; b < bands; b++) {
      const y0 = 30 + b * 88, kind = b % 3;
      x.fillStyle = '#4a2f1d';
      for (let k = 0; k < 24; k++) {
        const x0 = 20 + k * 30;
        x.beginPath();
        if (kind === 0) { x.moveTo(x0, y0 + 50); x.lineTo(x0 + 15, y0 + 10); x.lineTo(x0 + 30, y0 + 50); }
        else if (kind === 1) { x.moveTo(x0, y0 + 10); x.lineTo(x0 + 15, y0 + 30); x.lineTo(x0 + 30, y0 + 10); x.lineTo(x0 + 30, y0 + 18); x.lineTo(x0 + 15, y0 + 38); x.lineTo(x0, y0 + 18); }
        else { x.rect(x0 + 8, y0 + 18, 14, 14); }
        x.fill();
      }
      x.fillRect(16, y0 + 62, 736, 5);
    }
  } else {
    // abstract seascape: layered washes of sky, sea and sand, loose brush texture
    const g = x.createLinearGradient(0, 0, 0, 576);
    g.addColorStop(0, '#dfe7e8'); g.addColorStop(0.42, '#c9d9dc'); g.addColorStop(0.47, '#5d8c98'); g.addColorStop(0.7, '#8fb5b8'); g.addColorStop(0.8, '#d9cbb0'); g.addColorStop(1, '#efe6d6');
    x.fillStyle = g; x.fillRect(0, 0, 768, 576);
    for (let i = 0; i < 900; i++) {
      const y = r() * 576, a = 0.03 + r() * 0.06;
      x.strokeStyle = y < 250 ? `rgba(255,255,255,${a})` : y < 420 ? `rgba(40,90,105,${a})` : `rgba(180,150,110,${a})`;
      x.lineWidth = 2 + r() * 10; x.beginPath(); x.moveTo(r() * 768, y); x.lineTo(r() * 768, y + (r() - 0.5) * 12); x.stroke();
    }
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; artCache.set(style, t); return t;
}

export function buildFurniture(item, ctx) {
  const g = new THREE.Group();
  const build = B[item.type];
  if (!build) { console.warn('no furniture type', item.type); return { mesh: g, blocks: false }; }
  const ceiling = ctx.ceilingAt(item.x, item.y);
  build(g, { ...item, ceiling, elevation: item.elevation });
  g.position.set(item.x, 0, item.y);
  g.rotation.y = -(item.rot ?? 0) * Math.PI / 180;
  g.traverse(o => { if (o.isMesh) { o.castShadow = o.material !== mat('glass'); o.receiveShadow = true; } });
  const passable = ['rug', 'tv', 'pendant', 'fan', 'shower', 'outdoor-shower'];
  return { mesh: g, blocks: !passable.includes(item.type) && item.blocks !== false };
}
