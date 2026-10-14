// Procedural finishes drawn on canvas, so the model needs no image assets.
// UVs on floors are in feet, so `repeat` below is "one texture tile per N feet".
import * as THREE from '../vendor/three.module.js';

const cache = new Map();

export function solid(color, roughness = 0.8) {
  const key = `solid:${color}:${roughness}`;
  if (!cache.has(key)) cache.set(key, new THREE.MeshStandardMaterial({ color, roughness, side: THREE.DoubleSide }));
  return cache.get(key);
}

const FINISHES = {
  oak: { tileFt: 8, draw: planks('#b48a5e', '#a07a50', 8, 0.5) },
  walnut: { tileFt: 8, draw: planks('#6e4f36', '#5d4230', 8, 0.5) },
  deck: { tileFt: 8, draw: planks('#8a6a4c', '#755a40', 8, 0.45, 3) },
  stone: { tileFt: 6, draw: tiles('#d9d3c7', '#c9c2b5', 3, 3) },
  tile: { tileFt: 4, draw: tiles('#eceae5', '#d6d3cc', 2, 2) },
  travertine: { tileFt: 6, draw: tiles('#e2d6c0', '#cdbfa6', 2, 3) },
  grass: { tileFt: 10, draw: noise('#6f8f4e', '#5f7f42') },
  concrete: { tileFt: 10, draw: noise('#b8b5ae', '#a9a69f') },
};

export function materialFor(name) {
  if (name?.startsWith('#')) return solid(name);
  const key = `finish:${name}`;
  if (cache.has(key)) return cache.get(key);
  const f = FINISHES[name] ?? FINISHES.oak;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 512;
  f.draw(canvas.getContext('2d'), 512);
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1 / f.tileFt, 1 / f.tileFt);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  const mat = new THREE.MeshStandardMaterial({ map: tex, roughness: name === 'tile' || name === 'stone' ? 0.45 : 0.7 });
  cache.set(key, mat);
  return mat;
}

function rng(seed) { return () => (seed = (seed * 16807) % 2147483647) / 2147483647; }

function planks(base, alt, boardsPerTile, boardFt, seed = 7) {
  return (ctx, S) => {
    const r = rng(seed), rows = boardsPerTile, h = S / rows;
    for (let i = 0; i < rows; i++) {
      let x = -r() * S;
      while (x < S) {
        const len = S * (0.35 + r() * 0.5);
        ctx.fillStyle = r() > 0.5 ? base : alt;
        ctx.fillRect(x, i * h, len, h);
        ctx.globalAlpha = 0.08;
        for (let k = 0; k < 6; k++) { ctx.fillStyle = r() > 0.5 ? '#000' : '#fff'; ctx.fillRect(x, i * h + r() * h, len, 1 + r() * 2); }
        ctx.globalAlpha = 1;
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.fillRect(x, i * h, 1.5, h);
        x += len;
      }
      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.fillRect(0, i * h, S, 1.5);
    }
  };
}

function tiles(base, grout, cols, rows) {
  return (ctx, S) => {
    const r = rng(11);
    ctx.fillStyle = grout; ctx.fillRect(0, 0, S, S);
    const w = S / cols, h = S / rows, g = 3;
    for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
      ctx.fillStyle = base; ctx.fillRect(i * w + g / 2, j * h + g / 2, w - g, h - g);
      ctx.globalAlpha = 0.05;
      for (let k = 0; k < 40; k++) { ctx.fillStyle = r() > 0.5 ? '#000' : '#fff'; ctx.beginPath(); ctx.arc(i * w + r() * w, j * h + r() * h, 2 + r() * 10, 0, 7); ctx.fill(); }
      ctx.globalAlpha = 1;
    }
  };
}

function noise(base, alt) {
  return (ctx, S) => {
    const r = rng(3);
    ctx.fillStyle = base; ctx.fillRect(0, 0, S, S);
    ctx.fillStyle = alt; ctx.globalAlpha = 0.4;
    for (let k = 0; k < 4000; k++) ctx.fillRect(r() * S, r() * S, 2, 2);
    ctx.globalAlpha = 1;
  };
}
