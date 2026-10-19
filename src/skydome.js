// The living sky: a physically based sky texture (src/atmosphere.js, re-rendered on the GPU when the
// sun or moon moves), trade-wind cumulus and cirrus drifting with the wind, the sun's disc and the
// moon's disc lit at its true phase, and the image-based light for the whole scene from the same sky.
// Clouds come from one tileable noise texture that the CPU samples too, so the sun dims exactly when
// a cloud on screen crosses it, and stars hide behind the clouds (CLOUD_GLSL is shared with them).
import * as THREE from 'three';
import { SKY_GLSL, RE, H0 } from './atmosphere.js';

// ---------- tileable gradient noise (CPU + GPU) ----------
const N = 256, CELLS = 8;
function makeNoise() {
  let seed = 90211;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const grad = Array.from({ length: CELLS * CELLS }, () => { const a = rnd() * Math.PI * 2; return [Math.cos(a), Math.sin(a)]; });
  const fade = t => t * t * t * (t * (t * 6 - 15) + 10);
  const data = new Uint8Array(N * N * 4), vals = new Float32Array(N * N);
  let lo = 1e9, hi = -1e9;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const fx = (x + 0.5) / N * CELLS, fy = (y + 0.5) / N * CELLS, ix = Math.floor(fx), iy = Math.floor(fy), tx = fx - ix, ty = fy - iy;
    const g = (i, j) => grad[((iy + j) % CELLS) * CELLS + ((ix + i) % CELLS)];
    const dot = (i, j) => { const q = g(i, j); return q[0] * (tx - i) + q[1] * (ty - j); };
    const u = fade(tx), v = fade(ty);
    const n = (dot(0, 0) * (1 - u) + dot(1, 0) * u) * (1 - v) + (dot(0, 1) * (1 - u) + dot(1, 1) * u) * v;
    vals[y * N + x] = n; lo = Math.min(lo, n); hi = Math.max(hi, n);
  }
  for (let i = 0; i < N * N; i++) { const b = Math.round((vals[i] - lo) / (hi - lo) * 255); data[i * 4] = data[i * 4 + 2] = b; data[i * 4 + 3] = 255; }
  // G: tileable Worley (1 - distance to the nearest feature point): round, billowy cells for cumulus
  const WC = 6, pts = [];
  for (let j = 0; j < WC; j++) for (let i = 0; i < WC; i++) pts.push([(i + 0.15 + rnd() * 0.7) / WC, (j + 0.15 + rnd() * 0.7) / WC]);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const u = (x + 0.5) / N, v = (y + 0.5) / N, ci = Math.floor(u * WC), cj = Math.floor(v * WC);
    let best = 9;
    for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
      const ii = (ci + di + WC) % WC, jj = (cj + dj + WC) % WC, q = pts[jj * WC + ii];
      let dx = q[0] - u, dy = q[1] - v; dx -= Math.round(dx); dy -= Math.round(dy);
      best = Math.min(best, Math.hypot(dx, dy) * WC);
    }
    data[(y * N + x) * 4 + 1] = Math.round(Math.max(0, 1 - best / 0.95) * 255);
  }
  const tex = new THREE.DataTexture(data, N, N, THREE.RGBAFormat);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.magFilter = THREE.LinearFilter; tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.generateMipmaps = true; tex.needsUpdate = true;
  // bilinear sample with repeat, matching the GPU at mip level 0
  const sample = (u, v, ch = 0) => {
    const x = u * N - 0.5, y = v * N - 0.5, x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0;
    const at = (i, j) => data[((((y0 + j) % N) + N) % N * N + ((((x0 + i) % N) + N) % N)) * 4 + ch] / 255;
    return (at(0, 0) * (1 - fx) + at(1, 0) * fx) * (1 - fy) + (at(0, 1) * (1 - fx) + at(1, 1) * fx) * fy;
  };
  return { tex, sample };
}

export const CLOUD_H = 1.1, CLOUD_TOP = 2.0, CIRRUS_H = 8.5, TILE_KM = 9.0;   // trade cumulus: base ~1.1 km, tops ~2 km under the trade inversion; a noise tile spans 9 km
const SIGMA = 9.0;                                             // extinction per km of cloud (soft edges, opaque cores)
// The sky's textures, shared with shaders that fade into it (src/realsite.js: the community view's far terrain and its sea
// skirt inland): the sky texture (scene units), the half-resolution cumulus pass of this frame (premultiplied), and a tint
// of the low sky (1 everywhere but in the community view by day, where src/daylight.js gives the sky near the horizon the
// hue of that view's haze, so distant land fades into a sky of its own colour; SKY_TINT_GLSL).
export const SKY_U = { lut: { value: null }, clouds: { value: null }, texel: { value: new THREE.Vector2(1, 1) }, tint: { value: new THREE.Vector3(1, 1, 1) } };
export const SKY_TINT_GLSL = (u = 'uSkyTint') => `vec3 skyTint(vec3 d) { return mix(vec3(1.0), ${u}, exp(-max(d.y, 0.0) / 0.12)); }`;
export const CLOUD_GLSL = /* glsl */`
uniform sampler2D uNoise; uniform vec2 uCloudOff, uCirrusOff; uniform float uCloudThr, uCloudSoft, uCirrus, uMountain, uDome, uMarchKm; uniform vec2 uNorth;
float nz(vec2 p) { return texture(uNoise, p).r; }
// smooth fbm (R) for where clouds gather, billowy Worley fbm (G) for their cauliflower edges
float cloudShape(vec2 p) {
  vec2 a = texture(uNoise, p).rg, b = texture(uNoise, p * 2.03 + vec2(0.37, 0.11)).rg, c = texture(uNoise, p * 4.07 + vec2(0.71, 0.53)).rg;
  return a.x * 0.57 + b.x * 0.29 + c.x * 0.14 + (a.y * 0.5 + b.y * 0.32 + c.y * 0.18 - 0.5) * 0.42;
}
// distance (km) along a view direction to a layer at height h, on the curved earth
float layerDist(float mu, float h) { float r = ${RE.toFixed(1)} + ${H0}, R = ${RE.toFixed(1)} + h; return -r * mu + sqrt(max(0.0, r * r * (mu * mu - 1.0) + R * R)); }
float inlandAt(vec3 dir, float t) { return uMountain * max(0.0, dot(normalize(dir.xz + 1e-6), uNorth)) * smoothstep(8.0, 40.0, t); }
// cumulus density 0..1 at a point (km from the eye), hf = height in the deck, 0 (flat base) .. 1 (top); uDome narrows the
// tops (0.06: tall, nearly straight sides; the community view's 0.3: rounded tops, the weaker cells shallow)
float cumulusAt(vec2 km, float inland, float hf) {
  float thr = uCloudThr - inland + uDome * hf * sqrt(hf);
  return smoothstep(thr, thr + uCloudSoft, cloudShape(km / ${TILE_KM.toFixed(2)} + uCloudOff));
}
// the stretch of a ray through the deck that is marched: base to top, or at most uMarchKm past the base (low rays cross
// many kilometres of deck; marched whole they smear each cloud into a tall column)
float marchEnd(float tb, float tt) { return min(tt, tb + uMarchKm); }
// opacity of the deck along a direction (a short march, for stars and the Milky Way)
float cloudCover(vec3 dir) {
  if (dir.y < 0.003) return 0.0;
  float tb = layerDist(dir.y, ${CLOUD_H.toFixed(2)}), tt = layerDist(dir.y, ${CLOUD_TOP.toFixed(2)}), te = marchEnd(tb, tt), hk = (te - tb) / max(tt - tb, 1e-3), inland = inlandAt(dir, tb), od = 0.0;
  for (int k = 0; k < 4; k++) { float f = (float(k) + 0.5) / 4.0; od += cumulusAt(dir.xz * mix(tb, te, f), inland, f * hk); }
  return (1.0 - exp(-od * ${SIGMA.toFixed(1)} * (te - tb) / 4.0)) * (1.0 - smoothstep(70.0, 125.0, tb));
}
`;

// the same cloud field on the CPU
function cpuCloud(noise) {
  const S = (u, v) => [noise.sample(u, v, 0), noise.sample(u, v, 1)];
  const shape = (u, v) => {
    const a = S(u, v), b = S(u * 2.03 + 0.37, v * 2.03 + 0.11), c = S(u * 4.07 + 0.71, v * 4.07 + 0.53);
    return a[0] * 0.57 + b[0] * 0.29 + c[0] * 0.14 + (a[1] * 0.5 + b[1] * 0.32 + c[1] * 0.18 - 0.5) * 0.42;
  };
  // the field's distribution, to turn a cloud-cover fraction into a threshold
  const vals = [];
  for (let i = 0; i < 4096; i++) vals.push(shape((i * 0.6180339) % 1 * 3.7, (i * 0.7548776) % 1 * 3.1));
  vals.sort((a, b) => a - b);
  const quantile = q => vals[Math.min(vals.length - 1, Math.max(0, Math.round(q * (vals.length - 1))))];
  return { shape, quantile };
}

const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
function layerDist(mu, h) { const r = RE + H0, R = RE + h; return -r * mu + Math.sqrt(Math.max(0, r * r * (mu * mu - 1) + R * R)); }

export function createSky(renderer, scene, { quality = 'high', north = [1, 0] } = {}) {
  const noise = makeNoise(), cc = cpuCloud(noise);
  const W = quality === 'low' ? 256 : 512;
  const lutRT = new THREE.WebGLRenderTarget(W, W / 2, { type: THREE.HalfFloatType, magFilter: THREE.LinearFilter, minFilter: THREE.LinearFilter, depthBuffer: false, generateMipmaps: false });
  lutRT.texture.mapping = THREE.EquirectangularReflectionMapping;
  lutRT.texture.wrapS = THREE.RepeatWrapping;

  const lutU = {
    uSunDir: { value: new THREE.Vector3(0, 1, 0) }, uSunE: { value: new THREE.Vector3() },
    uMoonDir: { value: new THREE.Vector3(0, -1, 0) }, uMoonE: { value: new THREE.Vector3() },
    uTwE: { value: new THREE.Vector3() }, uGroundL: { value: new THREE.Vector3() }, uFloor: { value: new THREE.Vector3() },
    uOvercast: { value: 0 }, uOvercastL: { value: new THREE.Vector3() }, uGlow: { value: new THREE.Vector3() }, uGlowDir: { value: new THREE.Vector2(0, 1) },
    uMieS: { value: 0 }, uMieE: { value: 0 }, uG: { value: 0.78 }, uGain: { value: 1 },
  };
  const lutMat = new THREE.ShaderMaterial({
    uniforms: lutU, depthTest: false, depthWrite: false,
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: `varying vec2 vUv;
      uniform vec3 uSunDir, uSunE, uMoonDir, uMoonE, uTwE, uGroundL, uFloor, uOvercastL, uGlow; uniform float uOvercast, uGain; uniform vec2 uGlowDir;
      ${SKY_GLSL}
      void main() {
        float phi = (vUv.x - 0.5) * 6.2831853, th = (vUv.y - 0.5) * 3.14159265;
        vec3 v = vec3(cos(th) * cos(phi), sin(th), cos(th) * sin(phi));
        vec3 L = skyScatter(v, uSunDir, uSunE, uMoonDir, uMoonE, uGroundL) * (v.y > 0.0 ? uGain : 1.0);
        if (v.y > 0.0) {
          L += twilight(v, uSunDir) * uTwE * uGain;
          float h = max(v.y, 0.0);
          // airglow and starlight, brighter toward the horizon; the faint glow of Koloa and Lihu'e to the east-north-east
          L += uFloor * (1.0 + 2.2 * pow(1.0 - h, 6.0));
          L += uGlow * pow(max(0.0, dot(normalize(v.xz + 1e-5), uGlowDir)), 3.0) * exp(-h / 0.08);
          // overcast: a grey dome, brighter overhead (CIE overcast sky)
          vec3 oc = uOvercastL * (1.0 + 2.0 * h) / 3.0 * (1.0 + 0.6 * pow(max(dot(v, uSunDir), 0.0), 4.0));
          L = mix(L, oc, uOvercast);
        }
        gl_FragColor = vec4(L, 1.0);
      }`,
  });
  const lutScene = new THREE.Scene(), lutCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), lutMat); quad.frustumCulled = false; lutScene.add(quad);

  // ---------- the dome ----------
  const cloudU = {
    uNoise: { value: noise.tex }, uCloudOff: { value: new THREE.Vector2(0.31, 0.77) }, uCirrusOff: { value: new THREE.Vector2(0.5, 0.2) },
    uCloudThr: { value: 0.6 }, uCloudSoft: { value: 0.11 }, uCirrus: { value: 0.25 }, uMountain: { value: 0.1 }, uNorth: { value: new THREE.Vector2(north[0], north[1]) },
    uDome: { value: 0.06 }, uMarchKm: { value: 1e4 },          // src/daylight.js: rounder, shorter-marched cumulus in the community view
  };
  const lightU = {
    uCloudLight: { value: new THREE.Vector3() }, uCloudLightDir: { value: new THREE.Vector3(0, 1, 0) }, uCloudAmb: { value: new THREE.Vector3() },
    uCloudDark: { value: 0 }, uCloudThick: { value: 1 },
  };
  const domeU = {
    ...cloudU, ...lightU, uLUT: SKY_U.lut,
    uSunDir: lutU.uSunDir, uSunDisc: { value: new THREE.Vector3() }, uSunR: { value: 0.00465 },
    uMoonDir: lutU.uMoonDir, uMoonDisc: { value: new THREE.Vector3() }, uMoonR: { value: 0.0045 }, uEarthshine: { value: 0.0 }, uPole: { value: new THREE.Vector3(0, 1, 0) },
    uClouds: SKY_U.clouds, uCloudTexel: SKY_U.texel,
    uNoGround: { value: 0 },          // 1: below the horizon the horizon's haze, not the ground (the community view's sea runs out there)
    uSkyTint: SKY_U.tint,
  };
  const domeMat = new THREE.ShaderMaterial({
    uniforms: domeU, side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false,
    vertexShader: 'varying vec3 vD; void main(){ vD = position; vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position = p.xyww; }',
    fragmentShader: `varying vec3 vD;
      uniform sampler2D uLUT; uniform float uNoGround;
      uniform vec3 uSunDir, uSunDisc, uMoonDir, uMoonDisc, uPole, uCloudLight, uCloudLightDir, uCloudAmb;
      uniform float uSunR, uMoonR, uEarthshine, uCloudDark, uCloudThick;
      uniform sampler2D uClouds; uniform vec2 uCloudTexel; uniform vec3 uSkyTint;
      ${CLOUD_GLSL}
      ${SKY_TINT_GLSL()}
      vec3 sky(vec3 d) { return texture(uLUT, vec2(atan(d.z, d.x) * 0.15915494 + 0.5, asin(clamp(d.y, -1.0, 1.0)) * 0.31830989 + 0.5)).rgb; }
      // the moon's near side: maria and bright highlands, lunar north toward the celestial pole
      float maria(vec2 p) {
        float a = 1.0;
        a -= 0.42 * smoothstep(0.13, 0.05, length((p - vec2(0.66, 0.30)) * vec2(1.0, 1.25)));   // Crisium
        a -= 0.38 * smoothstep(0.17, 0.07, length(p - vec2(0.55, -0.12)));                      // Fecunditatis
        a -= 0.42 * smoothstep(0.2, 0.08, length(p - vec2(0.33, 0.12)));                         // Tranquillitatis
        a -= 0.40 * smoothstep(0.15, 0.06, length(p - vec2(0.22, 0.40)));                        // Serenitatis
        a -= 0.40 * smoothstep(0.26, 0.1, length(p - vec2(-0.22, 0.50)));                        // Imbrium
        a -= 0.36 * smoothstep(0.36, 0.12, length((p - vec2(-0.58, 0.12)) * vec2(1.0, 0.7)));    // Procellarum
        a -= 0.34 * smoothstep(0.17, 0.06, length(p - vec2(-0.18, -0.34)));                       // Nubium
        a -= 0.32 * smoothstep(0.1, 0.03, length(p - vec2(-0.55, -0.42)));                        // Humorum
        a -= 0.30 * smoothstep(0.09, 0.03, length(p - vec2(0.42, -0.28)));                        // Nectaris
        a -= 0.25 * smoothstep(0.08, 0.0, abs(p.y - 0.78) + max(0.0, abs(p.x) - 0.45) * 0.5);    // Frigoris
        a += 0.35 * smoothstep(0.05, 0.0, length(p - vec2(-0.12, -0.70)));                        // Tycho
        return clamp(a + (nz(p * 0.6 + 0.2) - 0.5) * 0.25, 0.35, 1.25);
      }
      void main() {
        vec3 d = normalize(vD);
        vec3 c = sky(uNoGround > 0.5 && d.y < 0.01 ? normalize(vec3(d.x, 0.01, d.z)) : d) * skyTint(d);
        // sun's disc, limb-darkened; a little glare round it
        float sa = length(cross(d, uSunDir)), sd = dot(d, uSunDir);
        if (sd > 0.0) {
          float aa = max(fwidth(sa), 1e-5);
          float k = 1.0 - smoothstep(uSunR - aa, uSunR + aa, sa);
          float mu = sqrt(max(0.0, 1.0 - pow(min(sa / uSunR, 1.0), 2.0)));
          c += uSunDisc * k * (1.0 - 0.6 * (1.0 - mu));
          c += uSunDisc * 0.0006 * exp(-sa / 0.035) + uSunDisc * 0.00002 * exp(-sa / 0.2);
        }
        // moon's disc: sunlit at its true phase (Lommel-Seeliger, so a full moon is flat as it really is), earthshine on the dark part
        float ma = length(cross(d, uMoonDir)), md = dot(d, uMoonDir);
        if (md > 0.0 && ma < uMoonR * 1.6) {
          float aa = max(fwidth(ma), 1e-5);
          vec3 right = normalize(cross(uMoonDir, uPole)), up = cross(right, uMoonDir);
          vec2 q = vec2(dot(d, right), dot(d, up)) / uMoonR;
          float r2 = dot(q, q), mu = sqrt(max(0.0, 1.0 - r2));
          vec3 n = normalize(right * q.x + up * q.y - uMoonDir * mu);
          float mu0 = dot(n, uSunDir);
          float lit = mu0 > 0.0 ? 2.0 * mu0 / (mu0 + mu + 1e-4) : 0.0;
          lit = mix(lit, smoothstep(-0.03, 0.03, mu0) * lit, 0.5);
          float k = 1.0 - smoothstep(uMoonR - aa, uMoonR + aa, length(cross(d, uMoonDir)));
          vec3 mc = uMoonDisc * maria(vec2(-q.x, q.y)) * (lit + uEarthshine);
          c = mix(c, c * 0.15 + mc, k);       // the moon hides the sky behind it
        }
        // cirrus high above, then the cumulus from the half-resolution cloud pass, softly upsampled
        if (d.y > 0.003) {
          if (uCirrus > 0.0) {
            float tc = layerDist(d.y, ${CIRRUS_H.toFixed(2)});
            vec2 pc = d.xz * tc / 28.0 + uCirrusOff;
            float ci = nz(pc * vec2(1.0, 0.22)) * 0.65 + nz(pc * vec2(3.1, 0.5) + 0.3) * 0.35;
            ci = smoothstep(0.55, 0.85, ci) * uCirrus * (1.0 - smoothstep(60.0, 160.0, tc));
            c = mix(c, uCloudLight * 0.9 + uCloudAmb, ci * 0.55);
          }
          vec2 uv = gl_FragCoord.xy * uCloudTexel * 0.5;
          vec2 t = uCloudTexel * 1.5;
          vec4 cl = texture(uClouds, uv) * 0.28
            + (texture(uClouds, uv + vec2(t.x, 0.0)) + texture(uClouds, uv - vec2(t.x, 0.0)) + texture(uClouds, uv + vec2(0.0, t.y)) + texture(uClouds, uv - vec2(0.0, t.y))) * 0.12
            + (texture(uClouds, uv + t) + texture(uClouds, uv - t) + texture(uClouds, uv + vec2(t.x, -t.y)) + texture(uClouds, uv - vec2(t.x, -t.y))) * 0.06;
          c = c * (1.0 - cl.a) + cl.rgb;
        }
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
  domeMat.extensions = { derivatives: true };
  // ---------- cumulus: a half-resolution pass, marched with per-pixel jitter, blurred into the dome ----------
  const cloudRT = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, depthBuffer: false, magFilter: THREE.LinearFilter, minFilter: THREE.LinearFilter });
  const passU = { ...cloudU, ...lightU, uLUT: domeU.uLUT, uSkyTint: SKY_U.tint, uProjInv: { value: new THREE.Matrix4() }, uCamWorld: { value: new THREE.Matrix4() } };
  const cloudMat = new THREE.ShaderMaterial({
    uniforms: passU, depthTest: false, depthWrite: false,
    defines: { CLOUD_STEPS: quality === 'low' ? 8 : 14 },
    vertexShader: 'varying vec2 vNdc; void main(){ vNdc = position.xy; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: `varying vec2 vNdc;
      uniform sampler2D uLUT; uniform mat4 uProjInv, uCamWorld;
      uniform vec3 uCloudLight, uCloudLightDir, uCloudAmb, uSkyTint; uniform float uCloudDark, uCloudThick;
      ${CLOUD_GLSL}
      ${SKY_TINT_GLSL()}
      vec3 sky(vec3 d) { return texture(uLUT, vec2(atan(d.z, d.x) * 0.15915494 + 0.5, asin(clamp(d.y, -1.0, 1.0)) * 0.31830989 + 0.5)).rgb; }
      void main() {
        vec4 v = uProjInv * vec4(vNdc, 1.0, 1.0); v /= v.w;
        vec3 d = normalize((uCamWorld * vec4(v.xyz, 0.0)).xyz);
        vec3 acc = vec3(0.0); float tr = 1.0;
        float tb = layerDist(d.y, ${CLOUD_H.toFixed(2)}), tt0 = layerDist(d.y, ${CLOUD_TOP.toFixed(2)}), tt = marchEnd(tb, tt0), hk = (tt - tb) / max(tt0 - tb, 1e-3);
        float fade = 1.0 - smoothstep(70.0, 125.0, tb);
        if (d.y > 0.003 && fade > 0.0) {
          vec2 ld = uCloudLightDir.xz / max(length(uCloudLightDir.xz), 1e-3);
          float lift = clamp(uCloudLightDir.y, -0.1, 1.0);
          float g = 0.6, cs = dot(d, uCloudLightDir);
          float hg = (1.0 - g * g) / pow(1.0 + g * g - 2.0 * g * cs, 1.5) / 12.566;
          float inland = inlandAt(d, tb), ds = (tt - tb) / float(CLOUD_STEPS);
          vec3 hazeSky = sky(vec3(d.x, max(d.y, 0.02), d.z)) * skyTint(d);
          float haze = (1.0 - exp(-tb / 50.0)) * 0.8;                       // distant clouds sink into the haze over the sea
          vec2 sh = ld * 0.35 / max(0.3, lift + 0.2);                          // toward the light, further when it is low
          float jit = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);    // white-noise jitter: no pattern left after the blur
          for (int k = 0; k < CLOUD_STEPS; k++) {
            if (tr < 0.02) break;
            float f = (float(k) + jit) / float(CLOUD_STEPS), hf = f * hk;   // hf: height in the deck
            vec2 p = d.xz * mix(tb, tt, f);
            float den = cumulusAt(p, inland, hf);
            if (den < 0.003) continue;
            float occ = cumulusAt(p + sh, inland, min(1.0, hf + 0.25 * max(lift, 0.0)));
            float shade = exp(-occ * 2.4 * uCloudThick) * mix(0.5, 1.0, hf);  // shadowed by its own body; tops in the light
            vec3 lit = uCloudLight * (0.05 + 0.95 * shade) * (0.6 + 3.0 * hg * (1.0 - den * 0.6));
            vec3 amb = uCloudAmb * mix(0.55, 1.05, hf) * (1.0 - 0.45 * uCloudDark);
            vec3 cl = mix(lit * (1.0 - 0.75 * uCloudDark) + amb, hazeSky, haze);
            float al = (1.0 - exp(-den * ${SIGMA.toFixed(1)} * ds * uCloudThick)) * fade;
            acc += tr * al * cl; tr *= 1.0 - al;
          }
        }
        gl_FragColor = vec4(acc, 1.0 - tr);
      }`,
  });
  const cloudScene = new THREE.Scene();
  const cq = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), cloudMat); cq.frustumCulled = false; cloudScene.add(cq);
  const _sz = new THREE.Vector2();
  function renderClouds(camera) {
    renderer.getDrawingBufferSize(_sz);
    const w = Math.max(4, Math.ceil(_sz.x / 2)), h = Math.max(4, Math.ceil(_sz.y / 2));
    if (cloudRT.width !== w || cloudRT.height !== h) cloudRT.setSize(w, h);
    camera.updateMatrixWorld();
    passU.uProjInv.value.copy(camera.projectionMatrixInverse);
    passU.uCamWorld.value.copy(camera.matrixWorld);
    SKY_U.clouds.value = cloudRT.texture;
    SKY_U.texel.value.set(1 / w, 1 / h);
    const prev = renderer.getRenderTarget();
    renderer.setRenderTarget(cloudRT); renderer.render(cloudScene, lutCam); renderer.setRenderTarget(prev);
  }

  const dome = new THREE.Mesh(new THREE.SphereGeometry(30000, 48, 24), domeMat);
  dome.name = 'sky dome';
  dome.renderOrder = -20;
  dome.frustumCulled = false;
  dome.onBeforeRender = (r, s, cam) => dome.position.copy(cam.position);
  scene.add(dome);

  SKY_U.lut.value = lutRT.texture;
  // ---------- image-based light from the sky texture ----------
  const pmrem = new THREE.PMREMGenerator(renderer);
  let envRT = null;
  function render() {
    const prev = renderer.getRenderTarget(), xr = renderer.xr.enabled;
    renderer.xr.enabled = false;
    renderer.setRenderTarget(lutRT); renderer.render(lutScene, lutCam);
    renderer.setRenderTarget(prev); renderer.xr.enabled = xr;
    envRT = pmrem.fromEquirectangular(lutRT.texture, envRT);
    scene.environment = envRT.texture;
  }

  // CPU twin of cloudCover() for one direction: how much cloud lies in front of the sun
  function coverAt(dir) {
    if (dir[1] < 0.003) return 0;
    const h = Math.hypot(dir[0], dir[2]) || 1, ndot = Math.max(0, (dir[0] * north[0] + dir[2] * north[1]) / h);
    const tb = layerDist(dir[1], CLOUD_H), tt0 = layerDist(dir[1], CLOUD_TOP), tt = Math.min(tt0, tb + cloudU.uMarchKm.value), hk = (tt - tb) / Math.max(tt0 - tb, 1e-3);
    const inland = cloudU.uMountain.value * ndot * smooth(8, 40, tb), dome = cloudU.uDome.value;
    let od = 0;
    for (let k = 0; k < 4; k++) {
      const f = (k + 0.5) / 4, hf = f * hk, t = tb + (tt - tb) * f, thr = cloudU.uCloudThr.value - inland + dome * hf * Math.sqrt(hf);
      od += smooth(thr, thr + cloudU.uCloudSoft.value, cc.shape(dir[0] * t / TILE_KM + cloudU.uCloudOff.value.x, dir[2] * t / TILE_KM + cloudU.uCloudOff.value.y));
    }
    return (1 - Math.exp(-od * SIGMA * (tt - tb) / 4)) * (1 - smooth(70, 125, tb));
  }

  return { dome, lutU, domeU, cloudU, render, renderClouds, coverAt, threshold: cover => cc.quantile(1 - cover), lut: lutRT, get env() { return envRT?.texture; } };
}
