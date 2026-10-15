// Procedural, tileable PBR textures (colour + normal + roughness) drawn at load time,
// so the project ships no image files. Every generator works on a periodic grid,
// which is what makes the tiles seamless.
import * as THREE from 'three';

const SIZE = 1024;
const cache = new Map();

// ---------- periodic noise ----------
function rng(seed) { let s = seed >>> 0 || 1; return () => ((s = Math.imul(s ^ (s >>> 15), 2246822519) ^ Math.imul(s ^ (s >>> 13), 3266489917)) >>> 0) / 4294967296; }

function lattice(period, seed) {
  const r = rng(seed), v = new Float32Array(period * period);
  for (let i = 0; i < v.length; i++) v[i] = r();
  return (x, y) => v[(((y % period) + period) % period) * period + (((x % period) + period) % period)];
}

// Value noise that tiles every `period` cells; x, y in cell units.
function noise2(period, seed) {
  const L = lattice(period, seed);
  return (x, y) => {
    const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = L(xi, yi), b = L(xi + 1, yi), c = L(xi, yi + 1), d = L(xi + 1, yi + 1);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  };
}

// fbm over [0,1)^2, tiling, base frequency f (cells across the tile)
export function fbm(f, octaves = 4, seed = 1) {
  const layers = Array.from({ length: octaves }, (_, i) => noise2(f << i, seed + i * 101));
  return (u, v) => {
    let s = 0, a = 0.5, n = 0;
    for (let i = 0; i < octaves; i++) { s += a * layers[i](u * (f << i), v * (f << i)); n += a; a *= 0.5; }
    return s / n;
  };
}

// ---------- canvas helpers ----------
function grid(n = SIZE) { return { n, h: new Float32Array(n * n), c: new Float32Array(n * n * 3), r: new Float32Array(n * n).fill(0.8) }; }
function hex(c) { const v = new THREE.Color(c); return [v.r, v.g, v.b]; }
function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }

function toTextures(g, { normalStrength = 2, repeatFt = 8, alpha = null } = {}) {
  const { n, h, c, r } = g;
  const col = new Uint8ClampedArray(n * n * 4), nor = new Uint8ClampedArray(n * n * 4), rou = new Uint8ClampedArray(n * n * 4);
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const i = y * n + x;
    const hx = h[y * n + ((x + 1) % n)] - h[y * n + ((x - 1 + n) % n)];
    const hy = h[((y + 1) % n) * n + x] - h[((y - 1 + n) % n) * n + x];
    let nx = -hx * normalStrength, ny = hy * normalStrength, nz = 1;
    const l = Math.hypot(nx, ny, nz); nx /= l; ny /= l; nz /= l;
    nor.set([(nx * 0.5 + 0.5) * 255, (ny * 0.5 + 0.5) * 255, (nz * 0.5 + 0.5) * 255, 255], i * 4);
    col.set([lin2srgb(c[i * 3]) * 255, lin2srgb(c[i * 3 + 1]) * 255, lin2srgb(c[i * 3 + 2]) * 255, alpha ? alpha[i] * 255 : 255], i * 4);
    const rv = r[i] * 255; rou.set([rv, rv, rv, 255], i * 4);
  }
  const make = (data, srgb) => {
    const t = new THREE.DataTexture(data, n, n, THREE.RGBAFormat);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter; t.generateMipmaps = true;
    t.anisotropy = 8;
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    t.repeat.set(1 / repeatFt, 1 / repeatFt);
    t.needsUpdate = true;
    return t;
  };
  return { map: make(col, true), normalMap: make(nor, false), roughnessMap: make(rou, false), repeatFt };
}
// colours are authored in sRGB hex, converted to linear by THREE.Color; store linear, write sRGB
function lin2srgb(v) { v = Math.max(0, Math.min(1, v)); return v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055; }

// ---------- generators ----------
const GEN = {
  // White oak, 7.5" wide planks, random lengths, fine straight grain. 8 ft tile.
  oak: (o = {}) => wood({ tile: 8, boardFt: o.board ?? 0.625, base: o.base ?? '#c8a77e', light: o.light ?? '#dcc29c', dark: o.dark ?? '#a7845c', seed: o.seed ?? 3, ...o }),
  teak: (o = {}) => wood({ tile: 6, boardFt: 0.4, base: '#a07c58', light: '#b8936c', dark: '#7a5b3f', seed: 9, gap: 0, ...o }),
  oakVeneer: (o = {}) => wood({ tile: 4, boardFt: 4, base: '#cdb08a', light: '#dcc4a0', dark: '#b08f66', seed: 5, gap: 0, lengths: [4, 4], ...o }),
  deckBoards: (o = {}) => wood({ tile: 8, boardFt: 0.5, base: '#a07650', light: '#b88d63', dark: '#7c5a3c', seed: 13, ...o }),

  // Coral / limestone pavers, 2x4 ft running bond, porous.
  coral: () => {
    const g = grid(), { n } = g, tile = 8, px = n / tile;
    const pores = fbm(64, 2, 21), cloud = fbm(4, 4, 22), fine = fbm(128, 2, 23);
    const base = hex('#e4d9c6'), warm = hex('#d6c6ab'), pale = hex('#efe8dc');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, u = x / n, v = y / n;
      const row = Math.floor(y / (2 * px)), off = (row % 2) * 2 * px;
      const gx = ((x + off) % (4 * px)), gy = y % (2 * px);
      const joint = Math.min(gx, 4 * px - gx, gy, 2 * px - gy) < 1.5;
      const stone = (Math.floor((x + off) / (4 * px)) * 7 + row * 13) % 5 / 5;
      const p = pores(u, v), pit = p > 0.72 ? (p - 0.72) * 3 : 0;
      let col = mix(base, cloud(u, v) > 0.5 ? warm : pale, Math.abs(cloud(u, v) - 0.5) * 1.4 + stone * 0.15);
      col = mix(col, [col[0] * 0.75, col[1] * 0.72, col[2] * 0.68], pit + (fine(u, v) - 0.5) * 0.15);
      if (joint) col = mix(col, hex('#b9ad99'), 0.7);
      g.c.set(col, i * 3);
      g.h[i] = joint ? -0.8 : -pit * 0.9 + fine(u, v) * 0.15;
      g.r[i] = joint ? 0.95 : 0.78 + pit * 0.2;
    }
    return toTextures(g, { normalStrength: 3, repeatFt: tile });
  },

  // Horizontal lap siding, 7" exposure, painted white. Tile 7 boards tall.
  siding: () => {
    const g = grid(), { n } = g, boards = 8, bh = n / boards;
    const grain = fbm(8, 3, 31), drip = fbm(64, 2, 32);
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, t = (y % bh) / bh;           // t: 0 at the bottom lip, 1 under the next board
      g.h[i] = (1 - t) * 1.2 + (grain(x / n, y / n) - 0.5) * 0.05;
      const shade = t > 0.93 ? 0.72 : 1 - (1 - t) * 0.04;
      const w = 0.955 + (drip(x / n, y / n) - 0.5) * 0.02;
      g.c.set([w * shade, w * shade * 0.997, w * shade * 0.985], i * 3);
      g.r[i] = 0.6;
    }
    return toTextures(g, { normalStrength: 6, repeatFt: boards * 7 / 12 });
  },

  // Standing-seam metal roof, seams every 16". u runs along the eave, v up the slope.
  roofMetal: () => {
    const g = grid(), { n } = g, panels = 6, pw = n / panels;
    const streak = fbm(4, 3, 41);
    const base = hex('#6c7176');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, t = (x % pw) / pw, d = Math.min(t, 1 - t) * pw;
      const seam = d < 3 ? 1 - d / 3 : 0;
      const flat = 0.06 * Math.sin(t * Math.PI * 2) * 0.5;      // slight oil-canning between seams
      g.h[i] = seam * 1.4 + flat;
      const k = 0.94 + (streak(x / n, y / n) - 0.5) * 0.08 + seam * 0.1;
      g.c.set([base[0] * k, base[1] * k, base[2] * k], i * 3);
      g.r[i] = 0.42 + (streak(x / n, y / n)) * 0.1;
    }
    return toTextures(g, { normalStrength: 5, repeatFt: panels * 16 / 12 });
  },

  // Tongue-and-groove ceiling / soffit boards, 4" wide, painted white.
  planks: () => {
    const g = grid(), { n } = g, boards = 24, bw = n / boards;
    const grain = fbm(16, 3, 51);
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, t = (x % bw) / bw, d = Math.min(t, 1 - t) * bw;
      const groove = d < 1.6 ? 1 : 0;
      g.h[i] = groove ? -1 : (grain(x / n, y / n) - 0.5) * 0.08;
      const w = groove ? 0.78 : 0.95;
      g.c.set([w, w * 0.995, w * 0.98], i * 3);
      g.r[i] = 0.7;
    }
    return toTextures(g, { normalStrength: 4, repeatFt: boards * 4 / 12 });
  },

  // Interior wall paint: almost flat, faint roller texture.
  paint: () => {
    const g = grid(512), { n } = g, nz = fbm(32, 3, 61);
    for (let i = 0; i < n * n; i++) {
      const x = i % n, y = (i / n) | 0, v = nz(x / n, y / n);
      g.h[i] = v * 0.3; const w = 0.93 + (v - 0.5) * 0.015;
      g.c.set([w, w * 0.99, w * 0.97], i * 3); g.r[i] = 0.9;
    }
    return toTextures(g, { normalStrength: 1, repeatFt: 6 });
  },

  grass: () => {
    const g = grid(), { n } = g, big = fbm(4, 4, 71), mid = fbm(32, 3, 72), blade = fbm(256, 2, 73);
    const dark = hex('#3f5c26'), lite = hex('#68843e'), dry = hex('#8b9255');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, u = x / n, v = y / n;
      let col = mix(dark, lite, Math.min(1, mid(u, v) * 1.3));
      col = mix(col, dry, Math.max(0, big(u, v) - 0.6) * 1.2);
      const b = blade(u, v);
      col = mix(col, [col[0] * 0.6, col[1] * 0.7, col[2] * 0.6], Math.max(0, 0.45 - b));
      g.c.set(col, i * 3); g.h[i] = b; g.r[i] = 0.95;
    }
    return toTextures(g, { normalStrength: 2.5, repeatFt: 7 });
  },

  // Walkway pavers: 3x2 ft cut stone with grass joints.
  pavers: () => {
    const g = grid(), { n } = g, tile = 6, px = n / tile, nz = fbm(16, 3, 81), pores = fbm(96, 2, 82);
    const stone = hex('#ddd3c1'), joint = hex('#5e7d34');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, u = x / n, v = y / n;
      const gx = x % (3 * px), gy = y % (2 * px);
      const j = Math.min(gx, 3 * px - gx, gy, 2 * px - gy) < 0.22 * px;
      let col = mix(stone, hex('#c9bca5'), nz(u, v) * 0.6);
      col = mix(col, [col[0] * 0.8, col[1] * 0.78, col[2] * 0.74], Math.max(0, pores(u, v) - 0.7) * 2);
      g.c.set(j ? joint : col, i * 3); g.h[i] = j ? -1 : 0; g.r[i] = j ? 1 : 0.75;
    }
    return toTextures(g, { normalStrength: 3, repeatFt: tile });
  },

  // Front walk: 4 x 2 ft tan cut stones set in grass with wide joints.
  stepping: () => {
    const g = grid(), { n } = g, tile = 6, px = n / tile, nz = fbm(16, 3, 181), pores = fbm(96, 2, 182), gr = fbm(64, 2, 183);
    const stone = hex('#d8c6a0'), stone2 = hex('#cbb68d'), grass = hex('#4f7a2c'), grass2 = hex('#6a9440');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, u = x / n, v = y / n, row = Math.floor(y / (3 * px));
      const gy = y % (3 * px), off = (row % 2) * 0.25 * px;      // 2 ft stone + 1 ft grass per row, slight jog
      const inStone = gy < 2.0 * px && Math.abs(x - n / 2 - off) < 2.4 * px;
      let col;
      if (inStone) { col = mix(stone, stone2, nz(u, v)); col = mix(col, [col[0] * 0.8, col[1] * 0.78, col[2] * 0.74], Math.max(0, pores(u, v) - 0.68) * 2.5); }
      else col = mix(grass, grass2, gr(u, v));
      g.c.set(col, i * 3); g.h[i] = inStone ? 0.6 : -0.3 + gr(u, v) * 0.6; g.r[i] = inStone ? 0.8 : 1;
    }
    return toTextures(g, { normalStrength: 2.5, repeatFt: tile });
  },

  // Hexagonal grass pavers for the drive.
  grassPavers: () => {
    const g = grid(512), { n } = g, cells = 8, R = n / cells / 2, gr = fbm(32, 2, 191), nz = fbm(16, 2, 192);
    const conc = hex('#c9c2b4'), grass = hex('#4e7a2c'), grass2 = hex('#6b9442');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x;
      // distance to the nearest hex centre on a staggered grid (tiles at the period)
      let best = 1e9;
      for (let cy = -1; cy <= cells; cy++) for (let cx = -1; cx <= cells; cx++) {
        const hx = (cx + (cy % 2 ? 0.5 : 0)) * 2 * R, hy = cy * 2 * R * 0.866;
        const dx = Math.abs(((x - hx + n / 2) % n + n) % n - n / 2), dy = Math.abs(((y - hy + n / 2) % n + n) % n - n / 2);
        const d = Math.max(dx * 0.866 + dy * 0.5, dy);
        if (d < best) best = d;
      }
      const ring = best > R * 0.52 && best < R * 0.86;
      const col = ring ? mix(conc, hex('#b8b0a1'), nz(x / n, y / n)) : mix(grass, grass2, gr(x / n, y / n));
      g.c.set(col, i * 3); g.h[i] = ring ? 0.5 : 0; g.r[i] = ring ? 0.85 : 1;
    }
    return toTextures(g, { normalStrength: 2, repeatFt: 6 });
  },

  concrete: () => {
    const g = grid(512), { n } = g, nz = fbm(16, 4, 201), fine = fbm(128, 2, 202);
    for (let i = 0; i < n * n; i++) {
      const x = i % n, y = (i / n) | 0, v = 0.72 + (nz(x / n, y / n) - 0.5) * 0.08 + (fine(x / n, y / n) - 0.5) * 0.04;
      g.c.set([v, v * 0.985, v * 0.96], i * 3); g.h[i] = fine(x / n, y / n) * 0.3; g.r[i] = 0.8;
    }
    return toTextures(g, { normalStrength: 1, repeatFt: 8 });
  },

  // Wind ripples for water surfaces (height only matters: it becomes the normal map).
  ripple: () => {
    const g = grid(512), { n } = g, a = fbm(8, 4, 211), b = fbm(24, 3, 212);
    for (let i = 0; i < n * n; i++) { const x = i % n, y = (i / n) | 0, u = x / n, v = y / n; g.h[i] = a(u, v) * 0.7 + b(u, v) * 0.3; g.c.set([1, 1, 1], i * 3); g.r[i] = 0.05; }
    return toTextures(g, { normalStrength: 7, repeatFt: 9 });
  },

  // Glass mosaic pool tile, 1" squares, aqua.
  poolTile: () => {
    const g = grid(512), { n } = g, tiles = 24, tp = n / tiles, r = rng(91);
    const shades = Array.from({ length: tiles * tiles }, () => r());
    const a = hex('#3aa0bb'), b = hex('#1f7896'), c = hex('#7cc8d6');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, tx = (x / tp) | 0, ty = (y / tp) | 0, s = shades[ty * tiles + tx];
      const gx = x % tp, gy = y % tp, j = Math.min(gx, tp - gx, gy, tp - gy) < 1.2;
      g.c.set(j ? hex('#d9e7e6') : mix(s < 0.5 ? a : b, c, s > 0.85 ? 0.6 : 0), i * 3);
      g.h[i] = j ? -1 : 0; g.r[i] = j ? 0.8 : 0.15;
    }
    return toTextures(g, { normalStrength: 2, repeatFt: 2 });
  },

  // Cut limestone / coral block retaining wall.
  ashlar: () => {
    const g = grid(), { n } = g, r = rng(101), nz = fbm(8, 4, 102), pores = fbm(96, 2, 103);
    const rows = 6, rh = n / rows;
    const base = hex('#cdb994'), alt = hex('#b9a37c'), pale = hex('#dccaa8');
    const blocks = [];
    for (let k = 0; k < rows; k++) { let x = 0; const row = []; while (x < n) { const w = rh * (1.2 + r() * 1.6); row.push([x, Math.min(n, x + w), r()]); x += w; } row[row.length - 1][1] = n; blocks.push(row); }
    for (let y = 0; y < n; y++) {
      const k = (y / rh) | 0, row = blocks[k], gy = y - k * rh;
      for (let x = 0; x < n; x++) {
        const i = y * n + x, u = x / n, v = y / n;
        const b = row.find(b => x >= b[0] && x < b[1]);
        const gx = Math.min(x - b[0], b[1] - x);
        const j = Math.min(gx, gy, rh - gy) < 3;
        let col = mix(base, b[2] > 0.6 ? alt : pale, 0.5 + (nz(u, v) - 0.5));
        const p = Math.max(0, pores(u, v) - 0.66) * 2.5;
        col = mix(col, [col[0] * 0.7, col[1] * 0.68, col[2] * 0.62], p);
        g.c.set(j ? hex('#a99a80') : col, i * 3);
        g.h[i] = j ? -1.5 : (nz(u, v) - 0.5) * 0.6 - p * 0.6; g.r[i] = 0.9;
      }
    }
    return toTextures(g, { normalStrength: 3, repeatFt: 5 });
  },

  // Woven linen, neutral; tinted by material colour.
  linen: () => {
    const g = grid(512), { n } = g, nz = fbm(64, 2, 111), slub = fbm(8, 3, 112);
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, w = (Math.sin(x * 1.6) * Math.sin(y * 1.6)) * 0.5 + 0.5;
      const v = 0.9 + (nz(x / n, y / n) - 0.5) * 0.1 + (slub(x / n, y / n) - 0.5) * 0.05 + w * 0.04;
      g.c.set([v, v, v], i * 3); g.h[i] = w * 0.5 + nz(x / n, y / n) * 0.3; g.r[i] = 0.95;
    }
    return toTextures(g, { normalStrength: 1.5, repeatFt: 1.5 });
  },

  // Chunky jute / sisal rug weave.
  jute: () => {
    const g = grid(512), { n } = g, nz = fbm(32, 3, 121), cell = n / 32;
    const a = hex('#b39a72'), b = hex('#cdb68f');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, cx = (x % cell) / cell, cy = (y % cell) / cell;
      const over = ((Math.floor(x / cell) + Math.floor(y / cell)) % 2) ? cx : cy;
      const h = Math.sin(over * Math.PI);
      g.c.set(mix(a, b, h * 0.5 + (nz(x / n, y / n) - 0.5) * 0.4), i * 3); g.h[i] = h * 0.6; g.r[i] = 1;
    }
    return toTextures(g, { normalStrength: 1.6, repeatFt: 0.9 });
  },

  // Cane webbing (the mood-board octagon weave); alpha holes.
  cane: () => {
    const g = grid(512), { n } = g, cell = n / 8, alpha = new Float32Array(n * n);
    const a = hex('#c99d62'), b = hex('#e2c08a');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, cx = (x % cell) / cell - 0.5, cy = (y % cell) / cell - 0.5;
      const oct = Math.max(Math.abs(cx) + Math.abs(cy) * 0.414, Math.abs(cy) + Math.abs(cx) * 0.414);
      const hole = oct < 0.3;
      const diag = Math.abs(((x + y) % cell) - cell / 2) < cell * 0.08 || Math.abs(((x - y + n) % cell) - cell / 2) < cell * 0.08;
      alpha[i] = hole && !diag ? 0 : 1;
      g.c.set(mix(a, b, diag ? 0.8 : 0.3), i * 3); g.h[i] = diag ? 1 : 0.5; g.r[i] = 0.7;
    }
    return toTextures(g, { normalStrength: 2, repeatFt: 0.42, alpha });
  },

  // White quartz with faint veining.
  quartz: () => {
    const g = grid(512), { n } = g, vein = fbm(4, 5, 131), speck = fbm(128, 1, 132);
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, u = x / n, v = y / n;
      const vv = Math.abs(Math.sin((u * 3 + vein(u, v) * 4) * Math.PI));
      const w = 0.95 - Math.max(0, 0.08 - vv) * 2 - (speck(u, v) > 0.8 ? 0.04 : 0);
      g.c.set([w, w * 0.995, w * 0.99], i * 3); g.h[i] = 0; g.r[i] = 0.18;
    }
    return toTextures(g, { normalStrength: 0, repeatFt: 4 });
  },

  asphalt: () => {
    const g = grid(512), { n } = g, nz = fbm(64, 3, 141), big = fbm(4, 3, 142);
    for (let i = 0; i < n * n; i++) {
      const x = i % n, y = (i / n) | 0, v = 0.12 + nz(x / n, y / n) * 0.07 + (big(x / n, y / n) - 0.5) * 0.04;
      g.c.set([v, v, v * 1.02], i * 3); g.h[i] = nz(x / n, y / n); g.r[i] = 0.92;
    }
    return toTextures(g, { normalStrength: 3, repeatFt: 10 });
  },

  // Horizontal wood louvers for shutters / slatted gates.
  louver: () => {
    const g = grid(512), { n } = g, slats = 16, sh = n / slats, grain = fbm(4, 3, 151);
    const a = hex('#8a5f3b'), b = hex('#a67550');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, t = (y % sh) / sh;
      const col = mix(a, b, grain(x / n * 0.2, y / n * 4) * 0.8);
      const sh2 = t > 0.85 ? 0.45 : 1 - t * 0.15;
      g.c.set([col[0] * sh2, col[1] * sh2, col[2] * sh2], i * 3); g.h[i] = 1 - t; g.r[i] = 0.7;
    }
    return toTextures(g, { normalStrength: 6, repeatFt: 16 * 0.14 });
  },

  louverWhite: () => {
    const g = grid(512), { n } = g, slats = 16, sh = n / slats;
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, t = (y % sh) / sh, k = t > 0.85 ? 0.62 : 0.97 - t * 0.12;
      g.c.set([k, k * 0.995, k * 0.985], i * 3); g.h[i] = 1 - t; g.r[i] = 0.6;
    }
    return toTextures(g, { normalStrength: 6, repeatFt: 16 * 0.14 });
  },

  // Board-and-batten: 2.5" battens every 16", painted warm white (the concept board's walls).
  batten: () => {
    const g = grid(512), { n } = g, bays = 6, bw = n / bays, bat = bw * (2.5 / 16);
    const nz = fbm(32, 3, 171);
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, t = x % bw, d = Math.min(t, bat - t);
      const onBat = t < bat, edge = onBat && d < 1.5;
      const w = (onBat ? 0.955 : 0.94) - (edge ? 0.05 : 0) + (nz(x / n, y / n) - 0.5) * 0.012;
      g.c.set([w, w * 0.99, w * 0.965], i * 3); g.h[i] = onBat ? 1 : 0; g.r[i] = 0.85;
    }
    return toTextures(g, { normalStrength: 5, repeatFt: bays * 16 / 12 });
  },

  // Vertical slat screen with gaps (garden shower walls).
  slats: () => {
    const g = grid(512), { n } = g, slats = 12, sw = n / slats, grain = fbm(4, 3, 161), alpha = new Float32Array(n * n);
    const a = hex('#8d6440'), b = hex('#a87a52');
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = y * n + x, t = (x % sw) / sw;
      alpha[i] = t > 0.82 ? 0 : 1;
      g.c.set(mix(a, b, grain(x / n * 4, y / n * 0.3)), i * 3); g.h[i] = Math.sin(t / 0.82 * Math.PI); g.r[i] = 0.75;
    }
    return toTextures(g, { normalStrength: 2, repeatFt: 12 * 0.33, alpha });
  },
};

// Anisotropic periodic noise: pu cells across u, pv cells across v (both tile at 1).
function noiseA(pu, pv, seed) {
  const r = rng(seed), v = new Float32Array(pu * pv);
  for (let i = 0; i < v.length; i++) v[i] = r();
  const L = (x, y) => v[(((y % pv) + pv) % pv) * pu + (((x % pu) + pu) % pu)];
  return (u, w) => {
    const x = u * pu, y = w * pv, xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    const a = xf * xf * (3 - 2 * xf), b = yf * yf * (3 - 2 * yf);
    const p = L(xi, yi), q = L(xi + 1, yi), s = L(xi, yi + 1), t = L(xi + 1, yi + 1);
    return p + (q - p) * a + (s - p) * b + (p - q - s + t) * a * b;
  };
}
function fbmA(pu, pv, oct, seed) {
  const layers = Array.from({ length: oct }, (_, i) => noiseA(pu << i, pv << i, seed + i * 7));
  return (u, v) => { let s = 0, a = 0.5, n = 0; for (const l of layers) { s += a * l(u, v); n += a; a *= 0.5; } return s / n; };
}

// Planks run along u. Each row is a ring of boards around the tile, so boards may wrap the edge.
function wood({ tile, boardFt, base, light, dark, seed, gap = 1, lengths = [3, 7] }) {
  const g = grid(), { n } = g, px = n / tile, r = rng(seed);
  const rows = Math.max(1, Math.round(tile / boardFt)), bw = n / rows;
  const grain = fbmA(2, rows * 6, 4, seed + 1), streak = fbmA(4, rows * 40, 2, seed + 2), knot = fbm(8, 3, seed + 3);
  const B = hex(base), L = hex(light), D = hex(dark);
  const ring = [];
  for (let k = 0; k < rows; k++) {
    const start = r() * n, cuts = [0];
    let x = 0;
    while (true) { x += (lengths[0] + r() * (lengths[1] - lengths[0])) * px; if (x > n - lengths[0] * px * 0.6) break; cuts.push(x); }
    cuts.push(n);
    ring.push({ start, cuts, tone: cuts.map(() => [r(), r()]) });
  }
  for (let y = 0; y < n; y++) {
    const k = Math.min(rows - 1, (y / bw) | 0), gy = y - k * bw, R = ring[k];
    for (let x = 0; x < n; x++) {
      const i = y * n + x, u = x / n, v = y / n;
      const rel = (x - R.start + n) % n;
      let j = 0; while (R.cuts[j + 1] <= rel) j++;
      const gx = Math.min(rel - R.cuts[j], R.cuts[j + 1] - rel);
      const [t0, t1] = R.tone[j];
      const seam = gap && (gy < 1.2 || gx < 1.2);
      const gr = grain(u + t0, v), fine = streak(u + t1, v);
      let col = mix(B, gr > 0.5 ? L : D, Math.min(1, Math.abs(gr - 0.5) * 1.8));
      col = mix(col, D, Math.max(0, fine - 0.55) * 1.4);
      col = mix(col, t0 > 0.5 ? L : D, Math.abs(t1 - 0.5) * 0.35);
      const kn = knot(u, v); if (kn > 0.8) col = mix(col, D, (kn - 0.8) * 2.5);
      if (seam) col = mix(col, D, 0.8);
      g.c.set(col, i * 3);
      g.h[i] = seam ? -1 : (fine - 0.5) * 0.3;
      g.r[i] = seam ? 0.95 : 0.5 + (fine - 0.5) * 0.25;
    }
  }
  return toTextures(g, { normalStrength: 2.5, repeatFt: tile });
}

export function texture(name, opts) {
  const key = name + JSON.stringify(opts ?? {});
  if (!cache.has(key)) {
    const gen = GEN[name];
    if (!gen) throw new Error(`no texture ${name}`);
    cache.set(key, gen(opts));
  }
  return cache.get(key);
}

// A clone of a texture set with a different world-space tile size (ft per repeat).
export function retile(set, ft) {
  const out = {};
  for (const k of ['map', 'normalMap', 'roughnessMap']) { out[k] = set[k].clone(); out[k].repeat.set(1 / ft, 1 / ft); out[k].needsUpdate = true; }
  return out;
}
