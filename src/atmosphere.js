// Clear-sky physics for Kaua'i's south shore: a spherical atmosphere with Rayleigh scattering,
// sea-salt haze (Mie) and the ozone layer (which is what keeps the twilight sky blue rather than
// grey), single-scattered from the sun and the moon. Constants after Bruneton & Neyret 2008 and
// Hillaire 2020; aerosol optical depth ~0.05 at 550 nm on a clear trade-wind day.
// The same model runs on the CPU (light colours, sky illuminance, exposure, fog) and as GLSL
// (SKY_GLSL: the sky texture behind the dome and the image-based lighting).
// Distances in km. Radiance is per unit of sun (or moon) irradiance at the top of the atmosphere.

export const RE = 6360, RT = 6420, H0 = 0.045;             // ground, top of atmosphere, eye (km)
const BR = [5.802e-3, 13.558e-3, 33.1e-3], HR = 8;           // Rayleigh scattering, km^-1
const BO = [2.4e-3, 1.95e-3, 0.09e-3];                      // ozone absorption, km^-1 (red carries the Chappuis band's 600 nm peak: it is what turns the twilight zenith blue)
const HM = 1.2, ANG = [0.92, 1.0, 1.09];                     // haze scale height; sea-salt colour (Angstrom ~0.4)
const PI = Math.PI;

// aod: aerosol optical depth at 550 nm (0.05 clear trades .. 0.25 rain haze)
export function airParams({ aod = 0.05, g = 0.78 } = {}) { const b = aod / HM; return { mieS: b * 0.97, mieE: b, g }; }

const dens = h => [Math.exp(-h / HR), Math.exp(-h / HM), Math.max(0, 1 - Math.abs(h - 25) / 15)];
function hitSphere(r, mu, R) {                                // distance along the ray to radius R (far side), -1 if none
  const d = r * r * (mu * mu - 1) + R * R;
  return d < 0 ? -1 : -r * mu + Math.sqrt(d);
}
function hitGround(r, mu) {
  const d = r * r * (mu * mu - 1) + RE * RE;
  if (d < 0 || mu > 0) return -1;
  return -r * mu - Math.sqrt(d);
}
// optical depth (R, M, O) along a ray from radius r with direction cosine mu, length len
function depth(r, mu, len, n, out) {
  out[0] = out[1] = out[2] = 0;
  const ds = len / n;
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) * ds, ri = Math.sqrt(r * r + t * t + 2 * r * mu * t), h = ri - RE;
    out[0] += Math.exp(-h / HR) * ds; out[1] += Math.exp(-h / HM) * ds; out[2] += Math.max(0, 1 - Math.abs(h - 25) / 15) * ds;
  }
  return out;
}
const _d = [0, 0, 0];
function tauToRgb(dR, dM, dO, P, out) {
  for (let c = 0; c < 3; c++) out[c] = Math.exp(-(BR[c] * dR + P.mieE * ANG[c] * dM + BO[c] * dO));
  return out;
}
// Transmittance from height h toward a light at altitude alt (deg). 0 when the earth is in the way.
export function transmittance(altDeg, P = airParams(), h = H0, out = [0, 0, 0]) {
  const r = RE + h, mu = Math.sin(altDeg * PI / 180);
  if (hitGround(r, mu) > 0) { out[0] = out[1] = out[2] = 0; return out; }
  depth(r, mu, hitSphere(r, mu, RT), 48, _d);
  return tauToRgb(_d[0], _d[1], _d[2], P, out);
}

const phaseR = c => 3 / (16 * PI) * (1 + c * c);
const phaseM = (c, g) => { const g2 = g * g; return 3 / (8 * PI) * (1 - g2) * (1 + c * c) / ((2 + g2) * Math.pow(1 + g2 - 2 * g * c, 1.5)); };

// Single-scattered sky radiance in direction v (unit [x, y, z], y up) from a light in direction s,
// per unit irradiance. Below the horizon: the ground (albedo, lit by groundE) seen through the air.
export function skyRadiance(v, s, P = airParams(), out = [0, 0, 0], groundL = null) {
  const r = RE + H0, mu = v[1], nu = v[0] * s[0] + v[1] * s[1] + v[2] * s[2], mus = s[1];
  const tg = hitGround(r, mu), len = tg > 0 ? tg : hitSphere(r, mu, RT);
  const N = 20, pr = phaseR(nu), pm = phaseM(nu, P.g);
  let aR = 0, aM = 0, aO = 0;                                  // optical depth from the eye so far
  out[0] = out[1] = out[2] = 0;
  let prev = 0;
  for (let i = 0; i < N; i++) {
    const t1 = len * Math.pow((i + 1) / N, 2), t = (prev + t1) / 2, ds = t1 - prev; prev = t1;   // denser near the eye
    const ri = Math.sqrt(r * r + t * t + 2 * r * mu * t), h = ri - RE;
    const [dR, dM, dO] = dens(h);
    aR += dR * ds * 0.5; aM += dM * ds * 0.5; aO += dO * ds * 0.5;
    const musi = (r * mus + t * nu) / ri;
    if (hitGround(ri, musi) < 0) {
      depth(ri, musi, hitSphere(ri, musi, RT), 8, _d);
      for (let c = 0; c < 3; c++) {
        const T = Math.exp(-(BR[c] * (aR + _d[0]) + P.mieE * ANG[c] * (aM + _d[1]) + BO[c] * (aO + _d[2])));
        out[c] += T * (BR[c] * dR * pr + P.mieS * ANG[c] * dM * pm) * ds;
      }
    }
    aR += dR * ds * 0.5; aM += dM * ds * 0.5; aO += dO * ds * 0.5;
  }
  if (tg > 0 && groundL) for (let c = 0; c < 3; c++) out[c] += groundL[c] * Math.exp(-(BR[c] * aR + P.mieE * ANG[c] * aM + BO[c] * aO));
  return out;
}

// Deep twilight. Single scattering goes dark once the sun is ~8 deg down, but the real sky does not:
// light scattered more than once keeps a deep blue sky with a glowing arch toward the sun, falling
// ~0.44 dex per degree (horizontal illuminance 3.4 lux at -6, 0.6 at -8, 0.008 at -12; USNO).
// Radiance per unit irradiance, the same function as twilightGLSL below.
const TW_BLUE = [0.30, 0.47, 1.0], TW_GLOW = [1.0, 0.52, 0.22];
export function twilightLux(dep) { return dep <= 0 ? 0 : 3.4 * Math.pow(10, -0.44 * (dep - 6)) * smooth(4.5, 8, dep); }
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
export const TW_NORM = 1.39;          // makes the hemisphere integral of the shape below equal 1 (fitted numerically)
export function twilight(v, s, out = [0, 0, 0], E0 = 127500) {
  const dep = -Math.asin(Math.max(-1, Math.min(1, s[1]))) * 180 / PI;
  out[0] = out[1] = out[2] = 0;
  if (dep <= 0 || v[1] < 0) return out;
  const hs = Math.hypot(s[0], s[2]) || 1, hv = Math.hypot(v[0], v[2]) || 1;
  const c = (v[0] * s[0] + v[2] * s[2]) / (hs * hv);
  const glow = Math.exp(-v[1] / 0.16) * Math.pow(Math.max(0, c) * 0.5 + 0.5, 4) * Math.exp(-Math.max(0, dep - 6) / 5);
  const A = twilightLux(dep) / E0 / PI * TW_NORM;
  for (let k = 0; k < 3; k++) out[k] = A * (TW_BLUE[k] + (TW_GLOW[k] - TW_BLUE[k]) * Math.min(1, glow)) * (0.7 + 2.0 * glow) / (0.2126 * TW_BLUE[0] + 0.7152 * TW_BLUE[1] + 0.0722 * TW_BLUE[2]);
  return out;
}

export const luminance = c => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];

// Sky survey for one light: illuminance on the ground from the sky (per unit irradiance, RGB),
// the zenith, the horizon all round and toward the light. 6 x 12 directions.
const T2 = [0, 0, 0];
export function skySurvey(s, P = airParams()) {
  const E = [0, 0, 0], hor = [0, 0, 0], horSun = [0, 0, 0], zen = [0, 0, 0], v = [0, 0, 0], L = [0, 0, 0];
  const alts = [3, 12, 24, 40, 58, 78], nA = 12, sAz = Math.atan2(s[2], s[0]);
  let wsum = 0;
  for (let i = 0; i < alts.length; i++) {
    const a0 = i ? (alts[i - 1] + alts[i]) / 2 : 0, a1 = i < alts.length - 1 ? (alts[i] + alts[i + 1]) / 2 : 90;
    const dOmega = (Math.sin(a1 * PI / 180) - Math.sin(a0 * PI / 180)) * 2 * PI / nA;     // solid angle of the cell
    const ca = Math.cos(alts[i] * PI / 180), sa = Math.sin(alts[i] * PI / 180);
    for (let j = 0; j < nA; j++) {
      const az = sAz + (j / nA) * 2 * PI;
      v[0] = ca * Math.cos(az); v[1] = sa; v[2] = ca * Math.sin(az);
      skyRadiance(v, s, P, L); twilight(v, s, T2); L[0] += T2[0]; L[1] += T2[1]; L[2] += T2[2];
      const w = sa * dOmega;
      for (let c = 0; c < 3; c++) { E[c] += L[c] * w; if (i === 0) { hor[c] += L[c] / nA; if (j === 0) horSun[c] = L[c]; } }
      wsum += w;
    }
  }
  v[0] = 0; v[1] = 1; v[2] = 0; skyRadiance(v, s, P, zen); twilight(v, s, T2); for (let c = 0; c < 3; c++) zen[c] += T2[c];
  // the cells above cover up to 90 deg; the cosine-weighted hemisphere integrates to PI
  for (let c = 0; c < 3; c++) E[c] *= PI / wsum;
  return { E, hor, horSun, zen };
}

// ---------- GLSL: the same model for the sky texture ----------
export const SKY_GLSL = /* glsl */`
const float RE = ${RE.toFixed(1)}, RT = ${RT.toFixed(1)}, H0 = ${H0};
const vec3 BR = vec3(${BR.join(', ')});
const vec3 BO = vec3(${BO.join(', ')});
const vec3 ANG = vec3(${ANG.join(', ')});
const float HR = ${HR.toFixed(1)}, HM = ${HM};
uniform float uMieS, uMieE, uG;
float hitSphere(float r, float mu, float R) { float d = r * r * (mu * mu - 1.0) + R * R; return d < 0.0 ? -1.0 : -r * mu + sqrt(d); }
float hitGround(float r, float mu) { float d = r * r * (mu * mu - 1.0) + RE * RE; if (d < 0.0 || mu > 0.0) return -1.0; return -r * mu - sqrt(d); }
vec3 dens(float h) { return vec3(exp(-h / HR), exp(-h / HM), max(0.0, 1.0 - abs(h - 25.0) / 15.0)); }
vec3 depthTo(float r, float mu) {
  float len = hitSphere(r, mu, RT), ds = len / 8.0; vec3 o = vec3(0.0);
  for (int i = 0; i < 8; i++) { float t = (float(i) + 0.5) * ds; float ri = sqrt(r * r + t * t + 2.0 * r * mu * t); o += dens(ri - RE) * ds; }
  return o;
}
vec3 extinction(vec3 d) { return exp(-(BR * d.x + uMieE * ANG * d.y + BO * d.z)); }
float phaseR(float c) { return 3.0 / (16.0 * 3.14159265) * (1.0 + c * c); }
float phaseM(float c) { float g2 = uG * uG; return 3.0 / (8.0 * 3.14159265) * (1.0 - g2) * (1.0 + c * c) / ((2.0 + g2) * pow(1.0 + g2 - 2.0 * uG * c, 1.5)); }
vec3 twilight(vec3 v, vec3 s) {
  float dep = -asin(clamp(s.y, -1.0, 1.0)) * 57.29578;
  if (dep <= 0.0 || v.y < 0.0) return vec3(0.0);
  float c = dot(normalize(v.xz + 1e-6), normalize(s.xz + 1e-6));
  float glow = exp(-v.y / 0.16) * pow(max(0.0, c) * 0.5 + 0.5, 4.0) * exp(-max(0.0, dep - 6.0) / 5.0);
  float A = 3.4 * pow(10.0, -0.44 * (dep - 6.0)) * smoothstep(4.5, 8.0, dep) / 127500.0 / 3.14159265 * ${TW_NORM};
  vec3 blue = vec3(${TW_BLUE.join(", ")}), warm = vec3(${TW_GLOW.join(", ")});
  return A * mix(blue, warm, min(1.0, glow)) * (0.7 + 2.0 * glow) / dot(blue, vec3(0.2126, 0.7152, 0.0722));
}
// in-scattered radiance along v from lights s1 (irradiance e1) and s2 (e2); ground behind, if any, in gl
vec3 skyScatter(vec3 v, vec3 s1, vec3 e1, vec3 s2, vec3 e2, vec3 gl) {
  float r = RE + H0, mu = v.y;
  float tg = hitGround(r, mu), len = tg > 0.0 ? tg : hitSphere(r, mu, RT);
  float nu1 = dot(v, s1), nu2 = dot(v, s2);
  float pr1 = phaseR(nu1), pm1 = phaseM(nu1), pr2 = phaseR(nu2), pm2 = phaseM(nu2);
  vec3 acc = vec3(0.0), a = vec3(0.0); float prev = 0.0;
  for (int i = 0; i < 20; i++) {
    float t1 = len * pow(float(i + 1) / 20.0, 2.0), t = 0.5 * (prev + t1), ds = t1 - prev; prev = t1;
    float ri = sqrt(r * r + t * t + 2.0 * r * mu * t);
    vec3 dn = dens(ri - RE);
    a += dn * ds * 0.5;
    float m1 = (r * s1.y + t * nu1) / ri, m2 = (r * s2.y + t * nu2) / ri;
    if (hitGround(ri, m1) < 0.0 && dot(e1, e1) > 0.0) {
      vec3 T = extinction(a + depthTo(ri, m1));
      acc += e1 * T * (BR * dn.x * pr1 + uMieS * ANG * dn.y * pm1) * ds;
    }
    if (hitGround(ri, m2) < 0.0 && dot(e2, e2) > 0.0) {
      vec3 T = extinction(a + depthTo(ri, m2));
      acc += e2 * T * (BR * dn.x * pr2 + uMieS * ANG * dn.y * pm2) * ds;
    }
    a += dn * ds * 0.5;
  }
  if (tg > 0.0) acc += gl * extinction(a);
  return acc;
}
`;
