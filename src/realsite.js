// The real place around Nā Hiku: south Kauaʻi terrain (USGS lidar / 3DEP) and colour (Sentinel-2),
// baked into geodata/ by scripts/geo_build.py in this model's world frame (feet, y up, our floor = 0).
//
// Terrain is a set of nested square rings around our lot, each twice the size and twice the grid
// spacing of the one inside (a static clipmap): ~12 ft spacing next to the neighbourhood, ~1500 ft at
// the far edge ten miles out. Rings inside the near square (+-6000 ft) use the near texture (1.8 m per
// texel, Sentinel-2 sharpened with lidar-era canopy, OSM roads and building footprints), the rest the
// far texture (8 m per texel). Odd vertices on a ring's outer edge are snapped onto the coarser ring's
// edge so there are no cracks. Where the modelled neighbourhood is (keep), the rings have a hole and
// the heights ease from the modelled ground to the real ground.
//
// Also here: real buildings (OSM + Microsoft footprints) and trees (Meta/WRI canopy height), and the
// colour hand-over of the modelled ground. Sources and licences: geodata/realsite.json, scripts/geo_*.py.
import * as THREE from 'three';

const ss = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export async function loadRealSite(base = 'geodata/', { low = false } = {}) {
  try {
    const r = await fetch(base + 'realsite.json');
    if (!r.ok) throw new Error(`realsite.json ${r.status}`);
    const meta = await r.json();
    const grid = async g => {
      const b = await fetch(base + g.height);
      if (!b.ok) throw new Error(`${g.height} ${b.status}`);
      // a host that serves no binary types gets the same bytes as base64 text (scripts/build_artifact.py)
      const raw = g.height.endsWith('.b64.txt') ? Uint8Array.from(atob((await b.text()).trim()), c => c.charCodeAt(0)).buffer : await b.arrayBuffer();
      const data = new Uint16Array(raw);
      if (data.length !== g.hsize * g.hsize) throw new Error(`${g.height}: size`);
      return { ...g, data, cell: (g.box[2] - g.box[0]) / g.hsize };
    };
    const [far, near] = await Promise.all([grid(meta.far), grid(meta.near)]);
    return new RealSite(meta, far, near, base, low);
  } catch (e) {
    console.warn('[realsite] real terrain not loaded:', e.message);
    return null;
  }
}

class RealSite {
  constructor(meta, far, near, base, low) {
    Object.assign(this, { meta, far, near, base, low });
    this.seaLevel = meta.seaLevel;
    this.north = meta.north;
  }

  // Bilinear height (world ft) from one grid; NaN outside it.
  sample(g, x, z) {
    const n = g.hsize, u = (x - g.box[0]) / g.cell - 0.5, v = (z - g.box[1]) / g.cell - 0.5;
    if (u < 0 || v < 0 || u > n - 1 || v > n - 1) return NaN;
    const i = Math.min(n - 2, Math.floor(u)), j = Math.min(n - 2, Math.floor(v)), fu = u - i, fv = v - j, d = g.data, k = j * n + i;
    const h = (d[k] * (1 - fu) + d[k + 1] * fu) * (1 - fv) + (d[k + n] * (1 - fu) + d[k + n + 1] * fu) * fv;
    return g.hmin + h / 65535 * (g.hmax - g.hmin);
  }

  // Real ground height (world ft) at world (x, z): the near grid, blended into the far one at its edge.
  heightAt(x, z) {
    const hf = this.sample(this.far, x, z);
    const b = this.near.box, m = 8 * this.near.cell;
    const d = Math.min(x - b[0], b[2] - x, z - b[1], b[3] - z);
    if (d <= 0) return Number.isNaN(hf) ? this.seaLevel : hf;
    const hn = this.sample(this.near, x, z);
    if (Number.isNaN(hn)) return Number.isNaN(hf) ? this.seaLevel : hf;
    return Number.isNaN(hf) ? hn : hf + (hn - hf) * ss(0, m, d);
  }

  // The ground everything stands on: the modelled ground (H) inside keep, easing to the real ground
  // over `blend` ft outside it, the real ground beyond.
  ground(x, z, H = this.H) {
    const h = this.heightAt(x, z), k = this.keep;
    if (!k || !H) return h;
    const d = Math.hypot(Math.max(k[0] - x, 0, x - k[2]), Math.max(k[1] - z, 0, z - k[3]));
    if (d >= this.blend) return h;
    const m = H(x, z);
    return m + (h - m) * ss(0, this.blend, d);
  }

  async texture(file, srgb = true) {
    const tex = await new THREE.TextureLoader().loadAsync(this.base + file);
    tex.flipY = false;                          // row 0 of the image is the low-z edge of the box
    tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
    tex.anisotropy = 8;
    tex.name = file;
    return tex;
  }

  // Roughness map from the water mask: glassy water, matt land (glTF reads roughness from green).
  async roughness(file) {
    const img = await new THREE.ImageLoader().loadAsync(this.base + file);
    const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
    const x = c.getContext('2d'); x.drawImage(img, 0, 0);
    const d = x.getImageData(0, 0, c.width, c.height);
    for (let i = 0; i < d.data.length; i += 4) { const w = d.data[i] / 255, r = Math.round(255 * (1 - w * 0.93)); d.data[i] = d.data[i + 1] = d.data[i + 2] = r; d.data[i + 3] = 255; }
    x.putImageData(d, 0, 0);
    const t = new THREE.CanvasTexture(c); t.flipY = false; t.colorSpace = THREE.NoColorSpace; t.name = file; t.anisotropy = 4;
    return t;
  }

  async material(which) {
    const g = this[which];
    const [map, rough] = await Promise.all([this.texture(which === 'far' && this.low && g.texLow ? g.texLow : g.tex), this.roughness(g.water)]);
    const m = new THREE.MeshStandardMaterial({ name: `realsite ${which}`, map, roughnessMap: rough, roughness: 0.96, metalness: 0, envMapIntensity: 1 });
    m.polygonOffset = true; m.polygonOffsetFactor = 2; m.polygonOffsetUnits = 2;   // the modelled ground wins where they overlap
    m.userData.box = g.box;
    rippleShader(m);
    return m;
  }

  // Terrain rings. keep: [x0, z0, x1, z1] world rect left to the modelled neighbourhood; H: the modelled
  // ground there (heights ease from H to the real ground over `blend` ft outside keep).
  async build({ keep = null, H = null, blend = 300, n = this.low ? 64 : 128, centre = null } = {}) {
    const c = centre ?? [(this.near.box[0] + this.near.box[2]) / 2, (this.near.box[1] + this.near.box[3]) / 2];
    const nearHalf = (this.near.box[2] - this.near.box[0]) / 2, farHalf = (this.far.box[2] - this.far.box[0]) / 2 - 1000;
    const R0 = nearHalf / 8;                                  // ring half-sizes R0 * 2^L; ring 3 ends at the near square
    Object.assign(this, { keep, H, blend });
    const tBuild = performance.now();
    const inKeep = (x, z) => keep && x > keep[0] && x < keep[2] && z > keep[1] && z < keep[3];
    const height = (x, z) => this.ground(x, z);
    const parts = { near: { pos: [], uv: [], idx: [] }, far: { pos: [], uv: [], idx: [] } };
    for (let L = 0; ; L++) {
      const R = R0 * 2 ** L, s = 2 * R / n, inner = L ? R / 2 : 0;
      if (R / 2 >= farHalf) break;
      const P = R <= nearHalf ? parts.near : parts.far, box = this[R <= nearHalf ? 'near' : 'far'].box;
      const base = P.pos.length / 3, N1 = n + 1;
      for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) {
        const x = c[0] - R + i * s, z = c[1] - R + j * s;
        let y;
        const edge = i === 0 || j === 0 || i === n || j === n;
        if (edge && ((i === 0 || i === n) ? j % 2 : i % 2)) {
          // odd vertex on the outer edge: on the straight line between its even neighbours (no crack)
          const [ax, az, bx, bz] = (i === 0 || i === n) ? [x, z - s, x, z + s] : [x - s, z, x + s, z];
          y = (height(ax, az) + height(bx, bz)) / 2;
        } else y = height(x, z);
        P.pos.push(x, y, z);
        P.uv.push((x - box[0]) / (box[2] - box[0]), (z - box[1]) / (box[3] - box[1]));
      }
      for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
        const x = c[0] - R + (i + 0.5) * s, z = c[1] - R + (j + 0.5) * s;
        if (Math.max(Math.abs(x - c[0]), Math.abs(z - c[1])) < inner) continue;
        if (Math.max(Math.abs(x - c[0]), Math.abs(z - c[1])) > farHalf) continue;
        // hole under the modelled neighbourhood (a quad is dropped only if all of it is inside)
        if (inKeep(x - s / 2, z - s / 2) && inKeep(x + s / 2, z + s / 2)) continue;
        const a = base + j * N1 + i, b = a + 1, d = a + N1, e = d + 1;
        // split along the diagonal that follows the ground better
        const ya = P.pos[a * 3 + 1], yb = P.pos[b * 3 + 1], yd = P.pos[d * 3 + 1], ye = P.pos[e * 3 + 1];
        if (Math.abs(ya - ye) < Math.abs(yb - yd)) P.idx.push(a, d, e, a, e, b); else P.idx.push(a, d, b, b, d, e);
      }
    }
    const tMesh = performance.now();
    const group = new THREE.Group(); group.name = 'realsite';
    for (const which of ['near', 'far']) {
      const P = parts[which]; if (!P.idx.length) continue;
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(P.pos, 3));
      geo.setAttribute('uv', new THREE.Float32BufferAttribute(P.uv, 2));
      geo.setIndex(P.idx); geo.computeVertexNormals();
      const mat = await this.material(which);
      if (which === 'near') this.nearMaterial = mat;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.name = `realsite ${which}`; mesh.receiveShadow = true; mesh.castShadow = false;
      group.add(mesh);
    }
    group.add(this.oceanSkirt(farHalf));
    this.timing = { rings: tMesh - tBuild, materials: performance.now() - tMesh };
    this.tris = parts.near.idx.length / 3 + parts.far.idx.length / 3;
    return group;
  }

  // Open sea beyond the far square, out to the horizon, in the deep-water colour of the imagery.
  oceanSkirt(half) {
    const g = new THREE.RingGeometry(half * 0.98, 400000, 64, 1);
    g.rotateX(-Math.PI / 2);
    // linear albedo of the deep water off Po'ipū in the mosaic
    const m = new THREE.MeshStandardMaterial({ name: 'realsite ocean', color: new THREE.Color().setRGB(0.021, 0.042, 0.075), roughness: 0.07, metalness: 0 });
    rippleShader(m, true);
    const mesh = new THREE.Mesh(g, m);
    const c = [(this.far.box[0] + this.far.box[2]) / 2, (this.far.box[1] + this.far.box[3]) / 2];
    mesh.position.set(c[0], this.seaLevel - 0.5, c[1]);
    mesh.name = 'realsite ocean';
    return mesh;
  }
}

// Shared GLSL: value noise.
const NOISE = `
  float rsHash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float rsNoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(rsHash(i), rsHash(i + vec2(1, 0)), f.x), mix(rsHash(i + vec2(0, 1)), rsHash(i + vec2(1, 1)), f.x), f.y); }
  float rsWaves(vec2 p){ return rsNoise(p * 0.11) * 0.5 + rsNoise(p * 0.23 + 3.1) * 0.3 + rsNoise(p * 0.51 + 7.7) * 0.2; }`;

// Terrain shader additions: close up, a fine mottle of grass and soil on the 10 m satellite colour
// (fading out with distance, so it never shimmers). On water (where the roughness map says glassy):
// a level surface with wind ripples near by and longer waves further out, fading before they alias,
// and rougher (blurrier, darker) reflections with distance as the eye averages the wave facets.
function rippleShader(m, all = false) {
  m.onBeforeCompile = sh => {
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vRsWorld;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvRsWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    // waves tilt their facets toward the sky: water reflects the sky above the horizon, not the
    // environment's ground half (which only the land below would see)
    const ibl = THREE.ShaderChunk.envmap_physical_pars_fragment.replace('reflectVec = inverseTransformDirection( reflectVec, viewMatrix );',
      'reflectVec = inverseTransformDirection( reflectVec, viewMatrix );\n\t\t\treflectVec.y = mix( reflectVec.y, max( reflectVec.y, 0.06 + 0.5 * roughness ), rsWetG );\n\t\t\treflectVec = normalize( reflectVec );');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
      varying vec3 vRsWorld; float rsWetG = 0.0;${NOISE}`)
      .replace('#include <envmap_physical_pars_fragment>', ibl)
      .replace('#include <map_fragment>', `#include <map_fragment>
      float rsDist = length(vRsWorld - cameraPosition);
      ${all ? '' : `{
        float wet0 = 1.0 - smoothstep(0.2, 0.6, texture2D(roughnessMap, vRoughnessMapUv).g);
        float fade = (1.0 - smoothstep(250.0, 1800.0, rsDist)) * (1.0 - wet0);
        if (fade > 0.0) {
          vec2 q = vRsWorld.xz;
          float n = rsNoise(q / 2.3) * 0.4 + rsNoise(q / 7.0 + 1.7) * 0.35 + rsNoise(q / 23.0 + 5.1) * 0.25;
          diffuseColor.rgb *= mix(1.0, 0.8 + 0.4 * n, fade);
        }
      }`}`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
      float rsWet = ${all ? '1.0' : '1.0 - smoothstep(0.2, 0.6, roughnessFactor)'};
      roughnessFactor = mix(roughnessFactor, mix(0.06, 0.42, smoothstep(300.0, 9000.0, rsDist)), rsWet);`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
      rsWetG = rsWet;
      if (rsWet > 0.0) {
        vec2 p = vRsWorld.xz;
        float near = 1.0 - smoothstep(150.0, 1500.0, rsDist), far = 1.0 - smoothstep(2000.0, 12000.0, rsDist);
        float e = 0.6, h0 = rsWaves(p), hx = rsWaves(p + vec2(e, 0.0)), hz = rsWaves(p + vec2(0.0, e));
        vec2 g = vec2(hx - h0, hz - h0) / e * 1.2 * near;
        vec2 P = p / 9.0; float E = 1.5;
        float H0 = rsWaves(P), Hx = rsWaves(P + vec2(E, 0.0)), Hz = rsWaves(P + vec2(0.0, E));
        g += vec2(Hx - H0, Hz - H0) / E * 0.18 * far;
        vec3 wn = normalize(vec3(-g.x, 1.0, -g.y));
        normal = normalize(mix(normal, normalize((viewMatrix * vec4(wn, 0.0)).xyz), rsWet));
      }`);
  };
  m.customProgramCacheKey = () => 'realsite-ground4' + (all ? '-sea' : '');
}

// ---------------------------------------------------------------------------------------------
// Buildings, trees and road lines of the real place (geodata/features.json, scripts/geo_features.py)

const sRGB = c => new THREE.Color().setRGB(c[0], c[1], c[2]);         // features store linear albedo

export async function loadFeatures(real, base = 'geodata/') {
  try {
    const r = await fetch(base + 'features.json');
    if (!r.ok) throw new Error(`features.json ${r.status}`);
    real.features = await r.json();
    return real.features;
  } catch (e) { console.warn('[realsite] no features:', e.message); return null; }
}

// Nearest point on a real road (world ft) within maxD of (x, z), or null.
RealSite.prototype.night = function (on = true) {
  if (this.windowMaterial) this.windowMaterial.emissiveIntensity = on ? 0.8 : 0;
};

RealSite.prototype.nearestRoad = function (x, z, maxD = 500) {
  let best = null;
  for (const r of this.features?.roads ?? []) {
    if (r.c === 'service') continue;
    const p = r.p;
    for (let i = 0; i + 3 < p.length; i += 2) {
      const ax = p[i], az = p[i + 1], bx = p[i + 2], bz = p[i + 3], vx = bx - ax, vz = bz - az, L = vx * vx + vz * vz || 1;
      const t = Math.max(0, Math.min(1, ((x - ax) * vx + (z - az) * vz) / L)), qx = ax + t * vx, qz = az + t * vz, d = Math.hypot(x - qx, z - qz);
      if (d < maxD && (!best || d < best.d)) best = { d, p: [qx, qz] };
    }
  }
  return best?.p ?? null;
};

// Buildings: footprints extruded to the eave, hip roofs over the footprint's oriented rectangle (most
// footprints are rectangles) or, for irregular ones, a roof rising from the footprint to a ridge.
RealSite.prototype.buildings = function ({ maxDist = Infinity, centre = [0, 0] } = {}) {
  const F = this.features; if (!F) return null;
  const wall = { pos: [], col: [], uv: [] }, roof = { pos: [], col: [] };
  const tri = (P, a, b, c, col) => { P.pos.push(...a, ...b, ...c); for (let k = 0; k < 3; k++) P.col.push(col.r, col.g, col.b); };
  const quad = (P, a, b, c, d, col) => { tri(P, a, b, c, col); tri(P, a, c, d, col); };
  // wall quad with (distance along the wall, height above the floor) uvs for the window pattern
  const wallQuad = (a, b, c, d, col, len, h0, h1, floor) => {
    quad(wall, a, b, c, d, col);
    const A = [0, h0 - floor], B = [0, h1 - floor], Cc = [len, h1 - floor], D = [len, h0 - floor];
    wall.uv.push(...A, ...B, ...Cc, ...A, ...Cc, ...D);
  };
  // painted plaster and siding, not paper white: albedo ~0.55-0.7
  const walls = ['#cbc5b8', '#d3cfc6', '#c1b6a2', '#bab7af', '#cdc0a9', '#b1a898'].map(c => new THREE.Color(c));
  let n = 0;
  for (const b of F.buildings) {
    const p = b.p, m = p.length / 2;
    let cx = 0, cz = 0; for (let i = 0; i < m; i++) { cx += p[2 * i] / m; cz += p[2 * i + 1] / m; }
    if (Math.hypot(cx - centre[0], cz - centre[1]) > maxDist) continue;
    let gmin = Infinity, gmax = -Infinity;
    for (let i = 0; i < m; i++) { const g = this.ground(p[2 * i], p[2 * i + 1]); gmin = Math.min(gmin, g); gmax = Math.max(gmax, g); }
    if (gmax < this.seaLevel + 1) continue;                       // stale footprint in the sea
    const base = gmin - 3, eave = gmax + b.e, wc = walls[(n++ * 7) % walls.length], rc = sRGB(b.r);
    // walls (footprint ring is CCW or CW: emit both windings' outward faces by checking the area sign)
    let area = 0; for (let i = 0; i < m; i++) { const j = (i + 1) % m; area += p[2 * i] * p[2 * j + 1] - p[2 * j] * p[2 * i + 1]; }
    // export: a belt of mixed canopy along the foot of each background building, crowns kept below its eave, so a
    // footprint box 100 m - 1.2 km off shows its roof over trees, as every Kukui'ula / Po'ipu house does, instead of
    // a bare sunlit wall (critique-preview4-front #3). Blender grows them (scripts/plants_bpy.py; seed >= 700000 =
    // belt: no grove companions). Within ~300 ft of our lot the modelled neighbourhood and the plan decide.
    const dc = Math.hypot(cx - centre[0], cz - centre[1]);
    if (globalThis.__palmProxies && dc > 300 && dc < 4000) {
      const rec = (globalThis.__plantProxies ??= []), hsh = k => { const s = Math.sin(k * 12.9898 + n * 78.233) * 43758.5453; return s - Math.floor(s); };
      for (let i = 0; i < m; i++) {
        const j = (i + 1) % m, ax = p[2 * i], az = p[2 * i + 1], ex = p[2 * j] - ax, ez = p[2 * j + 1] - az, L = Math.hypot(ex, ez);
        if (L < 14) continue;
        let nx = -ez / L, nz = ex / L;
        if (nx * (ax + ex / 2 - cx) + nz * (az + ez / 2 - cz) < 0) { nx = -nx; nz = -nz; }
        const k = Math.max(1, Math.floor((L - 8) / 24));
        for (let t = 0; t < k; t++) {
          const u = (t + 0.5 + (hsh(i * 31 + t) - 0.5) * 0.5) / k, size = 9 + hsh(i * 17 + t * 5 + 1) * 6, off = size * (0.35 + 0.3 * hsh(i * 7 + t));
          const x = ax + ex * u + nx * off, z = az + ez * u + nz * off, gr = this.ground(x, z);
          if (gr < this.seaLevel + 2) continue;
          const top = (eave - gr) * (0.72 + 0.2 * hsh(i * 3 + t * 11 + 2));            // crown top under the eave
          rec.push({ type: 'tree', x: Math.round(x * 100) / 100, y: Math.round(z * 100) / 100, ground: Math.round(gr * 100) / 100, size: Math.round(size * 100) / 100,
            sy: Math.round(Math.max(0.45, Math.min(1.3, 0.533 * top / size)) * 100) / 100, seed: 700000 + rec.length, real: true });
        }
      }
    }
    for (let i = 0; i < m; i++) {
      const j = (i + 1) % m, [i0, j0] = area > 0 ? [i, j] : [j, i];
      const ax = p[2 * i0], az = p[2 * i0 + 1], bx = p[2 * j0], bz = p[2 * j0 + 1];
      wallQuad([ax, base, az], [ax, eave, az], [bx, eave, bz], [bx, base, bz], wc, Math.hypot(bx - ax, bz - az), base, eave, gmax);
    }
    // roof
    const obb = orientedRect(p);
    if (b.q >= 0.62) {
      const { c, u, v, hu, hv } = obb, o = 1.6, X = hu + o, Z = hv + o, h = Math.min(X, Z) * 0.42, r = Math.max(0, X - Z), s2 = Math.max(0, Z - X);
      const P = (a, bb, y) => [c[0] + u[0] * a + v[0] * bb, eave + y, c[1] + u[1] * a + v[1] * bb];
      const A = P(-X, -Z, 0), B = P(X, -Z, 0), C = P(X, Z, 0), D = P(-X, Z, 0), R1 = P(-r, -s2, h), R2 = P(r, s2, h);
      for (const [a, bq, cq] of [[A, R1, B], [B, R1, R2], [B, R2, C], [C, R2, D], [D, R2, R1], [D, R1, A]]) tri(roof, a, bq, cq, rc);
    } else {
      const h = Math.min(obb.hu, obb.hv) * 0.42;
      let px = 0, pz = 0; for (let i = 0; i < m; i++) { px += p[2 * i] / m; pz += p[2 * i + 1] / m; }
      const sh = 0.3;
      for (let i = 0; i < m; i++) {
        const j = (i + 1) % m, [i0, j0] = area > 0 ? [i, j] : [j, i];
        const a = [p[2 * i0], eave, p[2 * i0 + 1]], bq = [p[2 * j0], eave, p[2 * j0 + 1]];
        const ai = [px + (a[0] - px) * sh, eave + h, pz + (a[2] - pz) * sh], bi = [px + (bq[0] - px) * sh, eave + h, pz + (bq[2] - pz) * sh];
        quad(roof, a, ai, bi, bq, rc);
      }
      for (let i = 1; i < m - 1; i++) {
        const k = [0, i, i + 1].map(t => [px + (p[2 * t] - px) * sh, eave + h, pz + (p[2 * t + 1] - pz) * sh]);
        if (area > 0) tri(roof, k[0], k[1], k[2], rc); else tri(roof, k[0], k[2], k[1], rc);
      }
    }
  }
  const g = new THREE.Group(); g.name = 'realsite buildings';
  for (const [P, name, rough, metal] of [[wall, 'realsite walls', 0.85, 0], [roof, 'realsite roofs', 0.55, 0.25]]) {
    if (!P.pos.length) continue;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(P.pos, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(P.col, 3));
    if (P.uv) geo.setAttribute('uv', new THREE.Float32BufferAttribute(P.uv, 2));
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ name, vertexColors: true, roughness: rough, metalness: metal, side: THREE.DoubleSide });
    if (P.uv) { mat.map = windowTexture(); mat.emissiveMap = windowTexture(true); mat.emissive = new THREE.Color('#ffc27a'); mat.emissiveIntensity = 0; this.windowMaterial = mat; }
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = mesh.receiveShadow = true; mesh.name = name;
    g.add(mesh);
  }
  this.buildingCount = n;
  return g;
};

// One storey-high, 10 ft wide bay of wall in world feet: a dark window with a frame in the middle,
// a darker plinth at the foot; tiled along the walls (uv = feet along the wall, feet above the floor).
let winTex = null, glowTex = null;
function windowTexture(glow = false) {
  if (glow) {
    // the glass only, for lit windows at night (every other bay dark)
    if (glowTex) return glowTex;
    const c = document.createElement('canvas'); c.width = 128; c.height = 64;
    const x = c.getContext('2d'); x.fillStyle = '#000'; x.fillRect(0, 0, 128, 64);
    const ft = 64 / 10, fy = 64 / 10.5, Y = h => 64 - h * fy;
    x.fillStyle = '#fff'; x.fillRect(3.0 * ft, Y(8.2), 4 * ft, 5.4 * fy);
    x.fillStyle = '#5a5a5a'; x.fillRect(64 + 3.0 * ft, Y(8.2), 4 * ft, 5.4 * fy);
    glowTex = new THREE.CanvasTexture(c);
    glowTex.wrapS = glowTex.wrapT = THREE.RepeatWrapping; glowTex.repeat.set(1 / 20, 1 / 10.5);
    glowTex.colorSpace = THREE.SRGBColorSpace; glowTex.name = 'realsite window glow';
    return glowTex;
  }
  if (winTex) return winTex;
  const c = document.createElement('canvas'); c.width = 64; c.height = 64;
  const x = c.getContext('2d');
  x.fillStyle = '#ffffff'; x.fillRect(0, 0, 64, 64);
  // 64 px = 10 ft across, 10.5 ft up (one storey); y = 0 at the top of the canvas = 10.5 ft
  const ft = 64 / 10, fy = 64 / 10.5, Y = h => 64 - h * fy;
  x.fillStyle = '#e9e6df'; x.fillRect(3.0 * ft - 2, Y(8.2) - 2, 4 * ft + 4, 5.4 * fy + 4);      // frame
  x.fillStyle = '#2a3036'; x.fillRect(3.0 * ft, Y(8.2), 4 * ft, 5.4 * fy);                      // glass
  x.fillStyle = '#4a545c'; x.fillRect(3.0 * ft, Y(8.2), 4 * ft, 1.2 * fy);                      // sky in the glass
  x.fillStyle = '#9d978c'; x.fillRect(0, Y(0.9), 64, 0.9 * fy);                                  // plinth
  winTex = new THREE.CanvasTexture(c);
  winTex.wrapS = winTex.wrapT = THREE.RepeatWrapping; winTex.repeat.set(1 / 10, 1 / 10.5);
  winTex.colorSpace = THREE.SRGBColorSpace; winTex.anisotropy = 4; winTex.name = 'realsite windows';
  return winTex;
}

// Trees found in the 1 m canopy height map: a crown (lumpy ellipsoid) and a trunk per tree, instanced,
// in the measured canopy colour. In export mode they are recorded for the path tracer instead
// (scripts/plants_bpy.py grows them), nearest first, at most `record`.
RealSite.prototype.trees = function ({ max = this.low ? 2500 : 9000, record = 2600 } = {}) {
  const T = this.features?.trees; if (!T) return null;
  const n = Math.min(max, T.x.length);
  if (globalThis.__palmProxies) {                     // export: Blender grows them (src/export.js -> meta.plants)
    const rec = (globalThis.__plantProxies ??= []);
    for (let i = 0; i < Math.min(n, record); i++) {
      const g = this.ground(T.x[i], T.z[i]);
      rec.push({ type: 'tree', x: T.x[i], y: T.z[i], ground: Math.round(g * 100) / 100, size: T.r[i], sy: Math.max(0.6, Math.min(2.2, T.h[i] / (2 * T.r[i]))), seed: 9000 + i, real: true });
    }
    return null;
  }
  const crownMat = new THREE.MeshStandardMaterial({ name: 'realsite tree crowns', roughness: 0.9, metalness: 0 });
  leafShader(crownMat);
  const trunkMat = new THREE.MeshStandardMaterial({ name: 'realsite trunks', color: '#4f4438', roughness: 1 });
  // trees are sorted nearest first: the first ones get the detailed crown
  const nNear = Math.min(n, this.low ? 250 : 700);
  const lods = [[0, nNear, crownCluster(2), trunkGeometry()], [nNear, n, crownCluster(1), null]];
  const g = new THREE.Group(); g.name = 'realsite trees';
  const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), V = new THREE.Vector3(), Y = new THREE.Vector3(0, 1, 0), col = new THREE.Color();
  for (const [i0, i1, crownGeo, trunkGeo] of lods) {
    if (i1 <= i0) continue;
    const crown = new THREE.InstancedMesh(crownGeo, crownMat, i1 - i0), trunk = trunkGeo ? new THREE.InstancedMesh(trunkGeo, trunkMat, i1 - i0) : null;
    for (let i = i0; i < i1; i++) {
      const x = T.x[i], z = T.z[i], h = Math.max(9, T.h[i]), r = Math.max(5, T.r[i] * 1.1), gr = this.ground(x, z) - 0.4;
      const ch = Math.min(h * 0.8, Math.max(r * 1.3, h * 0.55));     // crown depth: broad, low canopies
      const k = i - i0, rot = (i * 2.399) % (Math.PI * 2), sq = 0.85 + 0.3 * ((i * 0.381) % 1);
      Q.setFromAxisAngle(Y, rot);
      M.compose(V.set(x, gr + h - ch, z), Q, S.set(r * sq, ch, r / sq)); crown.setMatrixAt(k, M);
      if (trunk) { M.compose(V.set(x, gr, z), Q, S.set(Math.max(0.6, h * 0.03), h - ch * 0.5, Math.max(0.6, h * 0.03))); trunk.setMatrixAt(k, M); }
      const c = T.c; col.setRGB(c[3 * i], c[3 * i + 1], c[3 * i + 2]);
      // the 10 m pixel mixes crown with ground and shade: toward a leaf colour, with some spread
      const l = (col.r + col.g + col.b) / 3;
      col.setRGB(col.r * 0.6 + l * 0.05, col.g * 0.78 + 0.006, col.b * 0.55).multiplyScalar(0.85 + 0.35 * ((i * 0.618) % 1));
      crown.setColorAt(k, col);
    }
    for (const m of [crown, trunk]) if (m) { m.userData.realsite = true; m.castShadow = true; m.receiveShadow = true; m.frustumCulled = false; m.instanceMatrix.needsUpdate = true; g.add(m); }
    crown.instanceColor.needsUpdate = true;
  }
  this.treeCount = n;
  return g;
};

// A crown of unit radius sitting on y = 0 and 1 high: a broad base lump and a few smaller lumps on top
// and around it (lod 2: 240 triangles, lod 1: 20).
function crownCluster(lod) {
  const parts = lod >= 2
    ? [[0, 0.45, 0, 0.95, 0.5], [0.42, 0.66, 0.22, 0.6, 0.38], [-0.38, 0.7, -0.22, 0.62, 0.36]]
    : [[0, 0.5, 0, 1, 0.5]];
  const geos = parts.map(([x, y, z, r, ry], k) => {
    const g = lumpyCrown(lod >= 2 ? 1 : 0, k);
    g.scale(r, ry, r); g.translate(x, y, z);
    return g;
  });
  return mergeIndexed(geos);
}
function trunkGeometry() {
  const g = new THREE.CylinderGeometry(0.7, 1, 1, 7, 1, true); g.translate(0, 0.5, 0); g.deleteAttribute('uv');
  return g;
}

// A rounded, lumpy blob of unit radius (icosphere with clumps pushed out).
function lumpyCrown(detail = 2, seed = 0) {
  const g = new THREE.IcosahedronGeometry(1, detail);
  const p = g.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const k = 0.84 + 0.16 * Math.sin(v.x * 5.1 + 1.3 + seed) * Math.sin(v.y * 4.3 + 0.7) * Math.sin(v.z * 5.7 + 2.1 + seed * 2) + 0.07 * Math.sin(v.x * 11 + v.z * 9 + seed);
    v.multiplyScalar(k * (v.y < -0.3 ? 0.9 : 1)); p.setXYZ(i, v.x, v.y, v.z);
  }
  g.deleteAttribute('uv');
  const m = mergeVerts(g); m.computeVertexNormals();
  return m;
}
function mergeIndexed(geos) {
  const pos = [], idx = [];
  for (const g of geos) { const b = pos.length / 3, p = g.attributes.position; for (let i = 0; i < p.count; i++) pos.push(p.getX(i), p.getY(i), p.getZ(i)); for (const i of g.index.array) idx.push(b + i); }
  const out = new THREE.BufferGeometry(); out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); out.setIndex(idx); out.computeVertexNormals();
  return out;
}
function mergeVerts(g) {
  const p = g.attributes.position, map = new Map(), pos = [], idx = [];
  for (let i = 0; i < p.count; i++) {
    const key = `${p.getX(i).toFixed(4)},${p.getY(i).toFixed(4)},${p.getZ(i).toFixed(4)}`;
    let k = map.get(key); if (k === undefined) { k = pos.length / 3; map.set(key, k); pos.push(p.getX(i), p.getY(i), p.getZ(i)); }
    idx.push(k);
  }
  const out = new THREE.BufferGeometry(); out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); out.setIndex(idx);
  return out;
}
// Leaf clumps on the crowns: light and dark mottling and a bumpy normal from world-space noise.
function leafShader(m) {
  m.onBeforeCompile = sh => {
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vLeafW;')
      .replace('#include <worldpos_vertex>', `#include <worldpos_vertex>
      vLeafW = (modelMatrix * instanceMatrix * vec4(transformed, 1.0)).xyz;`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
      varying vec3 vLeafW;${NOISE}
      float leaf3(vec3 p){ return rsNoise(p.xz * 0.9 + p.y * 0.7) * 0.6 + rsNoise(p.xy * 1.9 + p.z) * 0.4; }`)
      .replace('#include <color_fragment>', `#include <color_fragment>
      float lf = leaf3(vLeafW);
      diffuseColor.rgb *= 0.62 + 0.75 * lf;`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
      { float e = 0.35, h0 = leaf3(vLeafW), hx = leaf3(vLeafW + vec3(e, 0.0, 0.0)), hy = leaf3(vLeafW + vec3(0.0, e, 0.0)), hz = leaf3(vLeafW + vec3(0.0, 0.0, e));
        vec3 gw = vec3(hx - h0, hy - h0, hz - h0) / e;
        normal = normalize(normal - (viewMatrix * vec4(gw, 0.0)).xyz * 0.9); }`);
  };
  m.customProgramCacheKey = () => 'realsite-leaves';
}

// Oriented bounding rectangle of a footprint (flat [x, z, ...]): minimum area over its edge directions.
function orientedRect(p) {
  const m = p.length / 2;
  let best = null;
  for (let i = 0; i < m; i++) {
    const j = (i + 1) % m, dx = p[2 * j] - p[2 * i], dz = p[2 * j + 1] - p[2 * i + 1], L = Math.hypot(dx, dz);
    if (L < 1e-6) continue;
    const u = [dx / L, dz / L], v = [-u[1], u[0]];
    let a0 = Infinity, a1 = -Infinity, b0 = Infinity, b1 = -Infinity;
    for (let k = 0; k < m; k++) { const a = p[2 * k] * u[0] + p[2 * k + 1] * u[1], b = p[2 * k] * v[0] + p[2 * k + 1] * v[1]; a0 = Math.min(a0, a); a1 = Math.max(a1, a); b0 = Math.min(b0, b); b1 = Math.max(b1, b); }
    const area = (a1 - a0) * (b1 - b0);
    if (!best || area < best.area) {
      const ca = (a0 + a1) / 2, cb = (b0 + b1) / 2;
      best = { area, u, v, hu: (a1 - a0) / 2, hv: (b1 - b0) / 2, c: [u[0] * ca + v[0] * cb, u[1] * ca + v[1] * cb] };
    }
  }
  return best;
}

// The modelled ground (site.js terrain) outside the lots takes the real colour: in the shader, the
// satellite colour times the grass texture's own detail, fading in from the lot lines; for the path
// tracer the same is written into the vertex colours.
export function blendModelledGround(mesh, real, lots, feather = 40) {
  const near = real.nearMaterial?.map; if (!near) return;
  const m = mesh.material, prev = m.onBeforeCompile, box = real.near.box;
  m.onBeforeCompile = (sh, r) => {
    prev?.call(m, sh, r);
    sh.uniforms.uRsMap = { value: near };
    sh.uniforms.uRsBox = { value: new THREE.Vector4(box[0], box[1], box[2] - box[0], box[3] - box[1]) };
    sh.uniforms.uRsLots = { value: new THREE.Vector4(...lots) };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec2 vRsXZ;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvRsXZ = (modelMatrix * vec4(transformed, 1.0)).xz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec2 vRsXZ; uniform sampler2D uRsMap; uniform vec4 uRsBox; uniform vec4 uRsLots;')
      .replace('#include <alphamap_fragment>', `{
        vec2 d2 = max(max(uRsLots.xy - vRsXZ, vRsXZ - uRsLots.zw), vec2(0.0));
        float w = smoothstep(0.0, ${feather.toFixed(1)}, length(d2));
        if (w > 0.0) {
          vec3 sat = texture2D(uRsMap, (vRsXZ - uRsBox.xy) / uRsBox.zw).rgb;
          #ifdef USE_MAP
            vec3 det = clamp(texture2D(map, vMapUv).rgb / max(textureLod(map, vMapUv, 10.0).rgb, vec3(0.02)), 0.55, 1.6);
          #else
            vec3 det = vec3(1.0);
          #endif
          diffuseColor.rgb = mix(diffuseColor.rgb, sat * det, w);
        }
      }
      #include <alphamap_fragment>`);
  };
  const key = m.customProgramCacheKey?.() ?? '';
  m.customProgramCacheKey = () => key + '|realsite-blend';
  m.needsUpdate = true;
  // vertex colours for the export (grass map x vertex colour ~ satellite colour outside the lots)
  const img = near.image, col = mesh.geometry.attributes.color, pos = mesh.geometry.attributes.position;
  if (!img || !col) return;
  const cv = document.createElement('canvas'), S = 512; cv.width = cv.height = S;
  const cx = cv.getContext('2d'); cx.drawImage(img, 0, 0, S, S);
  const px = cx.getImageData(0, 0, S, S).data, lin = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const grass = mapMean(m.map) ?? [0.18, 0.26, 0.09];
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i);
    const dx = Math.max(lots[0] - x, 0, x - lots[2]), dz = Math.max(lots[1] - z, 0, z - lots[3]);
    const w = ss(0, feather, Math.hypot(dx, dz)); if (w <= 0) continue;
    const u = Math.min(S - 1, Math.max(0, Math.floor((x - box[0]) / (box[2] - box[0]) * S))), v = Math.min(S - 1, Math.max(0, Math.floor((z - box[1]) / (box[3] - box[1]) * S)));
    const k = (v * S + u) * 4;
    for (let c = 0; c < 3; c++) col.setComponent(i, c, col.getComponent(i, c) * (1 - w) + Math.min(2, lin(px[k + c]) / grass[c]) * w);
  }
  col.needsUpdate = true;
}
function mapMean(t) {
  try {
    const img = t?.image; if (!img) return null;
    let data, n;
    if (img.data) { data = img.data; n = img.width * img.height; }
    else { const c = document.createElement('canvas'); c.width = c.height = 64; const x = c.getContext('2d'); x.drawImage(img, 0, 0, 64, 64); data = x.getImageData(0, 0, 64, 64).data; n = 4096; }
    const lin = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const s = [0, 0, 0], step = Math.max(1, Math.floor(n / 4096));
    let k = 0; for (let i = 0; i < n; i += step, k++) for (let c = 0; c < 3; c++) s[c] += lin(data[i * 4 + c]);
    return s.map(v => Math.max(0.02, v / k));
  } catch { return null; }
}
