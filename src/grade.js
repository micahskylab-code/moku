// The community view's display grade (main.js puts it after the tone mapping; src/daylight.js sets uAmount from the
// sun's altitude and switches it off outside that view, at dusk and at night). It works on the display image (sRGB,
// 0..1), as a photographer's grade would:
//   - the darks lifted a little (a gentle gamma below the mid-tones), so shade reads as sunlit-day shade;
//   - vibrance: dull colours gain saturation, already vivid ones (reef, roofs, pins) hardly any;
//   - olive greens pulled toward a fresh yellow-green, the dull ones given a little more colour and light;
//   - pale blues (the sky, the horizon's haze, the sea) a little deeper.
// No colour is invented: every hue stays the hue the light and the data give it, within a few degrees.
export const CommunityGrade = {
  name: 'CommunityGrade',
  uniforms: { tDiffuse: { value: null }, uAmount: { value: 0 } },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse; uniform float uAmount; varying vec2 vUv;
    const vec3 W = vec3(0.2126, 0.7152, 0.0722);
    vec3 rgb2hsv(vec3 c) {
      vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
      vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
      vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
      float d = q.x - min(q.w, q.y);
      return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
    }
    vec3 hsv2rgb(vec3 c) {
      vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
      return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
    }
    void main() {
      vec4 t = texture2D(tDiffuse, vUv);
      vec3 c = clamp(t.rgb, 0.0, 1.0), g = c;
      // shadow lift
      float y = dot(g, W);
      g = pow(g, vec3(mix(0.85, 1.0, smoothstep(0.06, 0.7, y))));
      // vibrance
      float mx = max(g.r, max(g.g, g.b)), mn = min(g.r, min(g.g, g.b)), s = (mx - mn) / max(mx, 1e-4);
      y = dot(g, W);
      g = clamp(y + (g - y) * (1.0 + 0.34 * (1.0 - s) * (1.0 - s)), 0.0, 1.0);
      // olive (about 40-160 deg) toward yellow-green (88 deg)
      vec3 h = rgb2hsv(g);
      float gw = smoothstep(0.11, 0.17, h.x) * (1.0 - smoothstep(0.36, 0.45, h.x)) * smoothstep(0.05, 0.18, h.y);
      h.x = mix(h.x, 0.245, 0.3 * gw);
      h.y = min(1.0, h.y * (1.0 + 0.2 * gw * (1.0 - h.y) * (1.0 - h.y)));   // the dull ones most: fairways stay grass, not lime
      h.z = min(1.0, h.z * (1.0 + 0.08 * gw * (1.0 - h.y)));
      // pale blues (sky, the haze at the horizon, the sea) a little deeper: a clear day, not a grey one
      float bw = smoothstep(0.47, 0.53, h.x) * (1.0 - smoothstep(0.65, 0.71, h.x)) * smoothstep(0.03, 0.12, h.y);
      h.x = mix(h.x, 0.59, 0.25 * bw);
      h.y = min(1.0, h.y * (1.0 + 0.5 * bw * (1.0 - h.y) * (1.0 - h.y)));
      g = hsv2rgb(h);
      gl_FragColor = vec4(mix(c, g, uAmount), t.a);
    }`,
};
