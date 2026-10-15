// Material library. Names used in plan JSON map to these.
// Palette follows the Na Hiku interior concept board: white oak, cane, coral stone,
// white painted plank walls and ceilings, black fixtures; exterior white lap siding,
// grey standing-seam roof, black window frames, wood shutters and beams.
import * as THREE from 'three';
import { texture, retile } from './textures.js';

const cache = new Map();
const once = (key, make) => { if (!cache.has(key)) cache.set(key, make()); return cache.get(key); };

export function solid(color, roughness = 0.8, metalness = 0, extra = {}) {
  return once(`solid:${color}:${roughness}:${metalness}:${JSON.stringify(extra)}`, () => new THREE.MeshStandardMaterial({ name: `solid ${color}`, color, roughness, metalness, ...extra }));
}

function textured(name, { tex, ft, color = '#ffffff', roughness = 1, metalness = 0, side = THREE.FrontSide, normalScale = 1, env = 1, interior, extra = {} } = {}) {
  return once(`tex:${name}:${ft}:${color}:${side}`, () => {
    let set = texture(tex);
    if (ft && ft !== set.repeatFt) set = retile(set, ft);
    const mm = new THREE.MeshStandardMaterial({
      map: set.map, normalMap: set.normalMap, roughnessMap: set.roughnessMap,
      normalScale: new THREE.Vector2(normalScale, normalScale),
      color, roughness, metalness, side, envMapIntensity: env, ...extra,
    });
    mm.name = name;
    if (interior ?? env < 1) mm.userData.interior = true;
    return mm;
  });
}

const LIB = {
  oak: () => textured('oak', { tex: 'oak', env: 0.7, roughness: 1.1 }),
  coral: () => textured('coral', { tex: 'coral', env: 0.5 }),
  coralWall: () => textured('coralWall', { tex: 'coral', ft: 5, color: '#fbf6ee', env: 0.8, interior: true }),
  pavers: () => textured('pavers', { tex: 'pavers' }),
  stepping: () => textured('stepping', { tex: 'stepping' }),
  grassPavers: () => textured('grassPavers', { tex: 'grassPavers', env: 0.5, interior: false }),
  concrete: () => textured('concrete', { tex: 'concrete', env: 0.5 }),
  grass: () => textured('grass', { tex: 'grass' }),
  asphalt: () => textured('asphalt', { tex: 'asphalt' }),
  siding: () => textured('siding', { tex: 'siding', normalScale: 1.3, color: '#f4f2ec', env: 0.75, interior: false }),
  paint: () => textured('paint', { tex: 'paint', color: '#f7f5ef', env: 0.95 }),
  batten: () => textured('batten', { tex: 'batten', env: 0.95 }),
  louverWhite: () => textured('louverWhite', { tex: 'louverWhite', side: THREE.DoubleSide }),
  louverGrey: () => textured('louverGrey', { tex: 'louverWhite', color: '#a9aeb3', side: THREE.DoubleSide }),
  fascia: () => solid('#5f6368', 0.55, 0.1),
  planks: () => textured('planks', { tex: 'planks', side: THREE.DoubleSide, env: 1.15, interior: true }),
  soffit: () => textured('soffit', { tex: 'planks', side: THREE.DoubleSide, env: 1.15, interior: true }),
  roof: () => textured('roof', { tex: 'roofMetal', metalness: 0.15, color: '#ffffff', env: 0.7, side: THREE.DoubleSide }),
  ashlar: () => textured('ashlar', { tex: 'flagstone' }),
  cedar: () => textured('cedar', { tex: 'teak', color: '#c7865a' }),
  poolTile: () => textured('poolTile', { tex: 'poolTile' }),
  teak: () => textured('teak', { tex: 'teak' }),
  woodOak: () => textured('woodOak', { tex: 'oakVeneer', env: 0.8 }),       // furniture / cabinetry white oak
  woodBeam: () => textured('woodBeam', { tex: 'oakVeneer', color: '#b79a77' }),
  linen: () => textured('linen', { tex: 'linen', color: '#efe9de', env: 0.85 }),
  linenWhite: () => textured('linenWhite', { tex: 'linen', color: '#f3efe7', env: 0.85 }),
  linenSand: () => textured('linenSand', { tex: 'linen', color: '#d7c9b2' }),
  linenSea: () => textured('linenSea', { tex: 'linen', color: '#9fb5b3' }),
  jute: () => textured('jute', { tex: 'jute' }),
  quartz: () => textured('quartz', { tex: 'quartz', env: 0.9 }),
  cane: () => textured('cane', { tex: 'cane', side: THREE.DoubleSide, extra: { alphaTest: 0.5 } }),
  louver: () => textured('louver', { tex: 'louver' }),
  slats: () => textured('slats', { tex: 'slats', side: THREE.DoubleSide, extra: { alphaTest: 0.5 } }),
  trim: () => solid('#f6f5f1', 0.55),
  black: () => solid('#1a1a1a', 0.5, 0.05),
  blackMatte: () => solid('#232323', 0.8),
  steel: () => solid('#c9cdd0', 0.28, 0.9),
  brass: () => solid('#b08d57', 0.35, 0.9),
  porcelain: () => solid('#f7f7f4', 0.15),
  rattan: () => solid('#c8a06a', 0.75),
  glass: () => once('glass', () => new THREE.MeshPhysicalMaterial({ color: '#dde9ea', metalness: 0, roughness: 0.03, transparent: true, opacity: 0.16, envMapIntensity: 1.6, side: THREE.DoubleSide, depthWrite: false })),
  mirror: () => solid('#cfd8da', 0.02, 1),
  water: () => once('water', () => { const r = texture('ripple'); return new THREE.MeshPhysicalMaterial({ color: '#2fa3c2', roughness: 0.02, metalness: 0, transparent: true, opacity: 0.82, envMapIntensity: 1.35, depthWrite: false, normalMap: r.normalMap, normalScale: new THREE.Vector2(0.35, 0.35), clearcoat: 1, clearcoatRoughness: 0.02 }); }),
  leaf: () => solid('#3f6b2f', 0.7),
  screen: () => solid('#0c0d0f', 0.15, 0.2),
};

// Furnishings and fixtures reflect the room around them, not the open sky.
const INDOOR = new Set(['jute', 'linen', 'linenWhite', 'linenSand', 'linenSea', 'cane', 'rattan', 'woodOak', 'quartz', 'porcelain', 'steel', 'brass', 'black', 'blackMatte', 'mirror', 'screen', 'trim']);

export function mat(name) {
  if (!name) return LIB.paint();
  if (name.startsWith('#')) { const m = solid(name); m.userData.interior = true; return m; }
  const f = LIB[name];
  if (!f) { console.warn('unknown material', name); return LIB.paint(); }
  const m = f();
  if (!m.name || m.name.startsWith('solid ')) m.name = name;
  if (INDOOR.has(name)) m.userData.interior = true;
  return m;
}

// Emissive lamp shade / bulb material, brightened at night.
export const glow = once('glow', () => new THREE.MeshStandardMaterial({ name: 'glow', color: '#fff4e0', emissive: '#ffd9a0', emissiveIntensity: 0.4, roughness: 0.9 }));
