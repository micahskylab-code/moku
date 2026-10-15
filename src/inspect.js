// Model view: this one home as an orbitable model with three displays, selectable spaces and local questions.
//  - Exterior: the house as built in the walkthrough. Cutaway: a section cut at 7 ft, with roofs, ceilings and
//    anything hung above the cut removed, and cut walls drawn solid dark. Translucent: walls, roofs and exterior
//    trim ghosted; floors, fixtures and furniture solid.
//  - Spaces are the p6 floor-plan rooms (plans/lot25.json), plus the pool and the modelled homesite. Each space's
//    card says what can be said about it and on what basis: SOURCE (stated in the brochure), ESTIMATE (scaled
//    from the p6 plan), ASSUMED (renderings, the p7 board, defaults) or UNKNOWN (no document). The wording lives in
//    plans/<plan>-spaces.json and follows docs/assumptions-register.md; areas are computed here from the traced
//    polygons.
//  - Buyer questions are drafted and saved in this browser only (localStorage) and exported as a local JSON file.
//    Nothing is sent anywhere.
// A concept visualization, not construction or as-built documentation.
import * as THREE from 'three';
import { inside } from './geom.js';

const CUT = 7.0;                     // section height, ft above the floor
const GHOST = 0.16;                  // wall and roof opacity in the translucent display
const DISPLAYS = ['exterior', 'cutaway', 'translucent'];
const FLOOR_NAMES = { oak: 'White oak plank', coral: 'Coral stone', pavers: 'Pavers', concrete: 'Concrete' };
const TAG_HELP = {
  SOURCE: 'Stated in the Nā Hiku brochure',
  ESTIMATE: 'Scaled from the p6 floor plan, which has no dimension strings (fitted scale, ±3–8 % linear)',
  ASSUMED: 'Inferred from the renderings, the p7 design board or a default, not from a plan',
  UNKNOWN: 'No document supplied',
};

export async function createInspector({ planId, plan, scene, camera, renderer, orbit, house, ceilingAt, center, aoPass, daylight }) {
  const res = await fetch(`plans/${planId}-spaces.json`).catch(() => null);
  if (!res?.ok) return null;
  const info = await res.json();
  const grade = plan.grade ?? -0.6;
  const [cx, cz] = center;

  // ---------- spaces ----------
  const rect = ([x0, y0, x1, y1]) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  const spaces = plan.rooms.map(r => ({ id: r.id, room: r, polygon: r.polygon, level: (r.floorLevel ?? 0) + (r.label_only ? 0.09 : 0.05), zone: !!r.label_only }));
  if (plan.site?.pool?.rect) spaces.push({ id: 'pool', polygon: rect(plan.site.pool.rect), level: grade + 0.02, site: true });
  if (plan.site?.lot) spaces.push({ id: 'homesite', polygon: rect(plan.site.lot), level: grade - 0.02, site: true });
  for (const s of spaces) {
    s.meta = info.spaces[s.id] ?? {};
    s.name = s.meta.name ?? s.room?.name ?? s.id;
    s.group = info.groups[s.meta.group] ?? null;
    s.area = polyArea(s.polygon);
    const xs = s.polygon.map(p => p[0]), ys = s.polygon.map(p => p[1]);
    s.box = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  const byId = new Map(spaces.map(s => [s.id, s]));

  // invisible floor plates to pick against (a ray passes through roofs and walls to the floor of the space under
  // the pointer, in every display); the kitchen zone sits just above the great room, rooms above the pool and lot
  const root = new THREE.Group(); root.name = 'inspect';
  const plateMat = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  const plates = spaces.map(s => {
    const m = new THREE.Mesh(flat(s.polygon, s.level), plateMat);
    m.visible = false; m.userData.space = s; root.add(m); return m;
  });
  const hl = {
    fill: new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: '#f0b429', transparent: true, opacity: 0.4, depthTest: false, depthWrite: false, side: THREE.DoubleSide })),
    line: new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: '#f5c542', depthTest: false, depthWrite: false, side: THREE.DoubleSide })),
    hover: new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 0.85, depthTest: false, depthWrite: false, side: THREE.DoubleSide })),
  };
  hl.fill.renderOrder = 20; hl.line.renderOrder = 21; hl.hover.renderOrder = 22;
  for (const m of Object.values(hl)) { m.visible = false; m.frustumCulled = false; root.add(m); }
  scene.add(root);

  // ---------- displays ----------
  // every mesh of the house, classified once: shell (walls, roofs, timber, exterior trim), ceiling, floor, contents
  const items = [];
  house.updateMatrixWorld(true);
  house.traverse(o => {
    if (!o.isMesh) return;
    let kind = 'contents';
    for (let p = o; p && p !== house.parent; p = p.parent) {
      if (p.userData.ceiling) { kind = 'ceiling'; break; }
      if (p.userData.floor) { kind = 'floor'; break; }
      if (p.userData.shell) { kind = 'shell'; break; }
    }
    items.push({ o, kind, orig: o.material, cast: o.castShadow, visible: o.visible, box: new THREE.Box3().setFromObject(o) });
  });
  const cutPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), CUT);   // keeps y <= CUT
  const variants = new Map();                                            // `${uuid}:${mode}` -> material
  function variant(m, mode) {
    if (!m || m.isShaderMaterial) return m;
    const key = `${m.uuid}:${mode}`;
    if (variants.has(key)) return variants.get(key).v;
    const ud = m.userData; m.userData = {};                              // keep clone() from serialising userData
    const v = m.clone(); m.userData = ud; v.userData = { ...ud };
    v.name = m.name;
    if (mode === 'cut') {
      v.clippingPlanes = [cutPlane]; v.clipShadows = true;
      if (!m.transparent) {
        // cut faces: the inside of a clipped solid shows its back faces; draw them flat dark, like a section's poche
        v.side = THREE.DoubleSide;
        v.onBeforeCompile = (sh, r) => {
          m.onBeforeCompile(sh, r);
          sh.fragmentShader = sh.fragmentShader.replace(/}\s*$/, '\tif (!gl_FrontFacing) gl_FragColor = vec4(0.035, 0.034, 0.032, 1.0);\n}\n');
        };
        v.customProgramCacheKey = () => m.customProgramCacheKey() + '|poche';
      } else { v.onBeforeCompile = m.onBeforeCompile; v.customProgramCacheKey = m.customProgramCacheKey; }
    } else {
      v.onBeforeCompile = m.onBeforeCompile; v.customProgramCacheKey = m.customProgramCacheKey;
      v.transparent = true; v.depthWrite = false; v.opacity = Math.min(m.opacity, m.transparent ? GHOST * 0.6 : GHOST);
    }
    variants.set(key, { m, v, mode });
    return v;
  }
  const mapMat = (mat, mode) => Array.isArray(mat) ? mat.map(x => variant(x, mode)) : variant(mat, mode);
  function apply(display) {
    for (const it of items) {
      const { o, kind, box } = it;
      let m = it.orig, vis = it.visible, cast = it.cast;
      if (display === 'cutaway') {
        const hung = kind !== 'shell' && kind !== 'floor' && box.min.y > CUT - 1.5 && box.max.y - box.min.y < 5;
        if (kind === 'ceiling' || box.min.y > CUT - 0.05 || hung) vis = false;
        else if (box.max.y > CUT) m = mapMat(it.orig, 'cut');
      } else if (display === 'translucent') {
        if (kind === 'ceiling') vis = false;
        else if (kind === 'shell') { m = mapMat(it.orig, 'ghost'); cast = false; }
      }
      o.material = m; o.visible = vis; o.castShadow = cast;
    }
    // screen-space AO reads the unclipped, opaque depth: wrong under a section or ghosted walls
    if (aoPass) aoPass.enabled = display === 'exterior';
  }
  // night lighting, daylight's interior reflections: keep the copies in step with the materials they copy
  function syncVariants() {
    for (const { m, v, mode } of variants.values()) {
      if (m.emissive) { v.emissive.copy(m.emissive); v.emissiveIntensity = m.emissiveIntensity; }
      if (v.envMap !== m.envMap) { v.envMap = m.envMap; v.needsUpdate = true; }
      v.envMapIntensity = m.envMapIntensity;
      if (mode === 'cut') v.opacity = m.opacity;
    }
  }

  // ---------- state ----------
  const params = new URLSearchParams(location.search);
  const S = {
    active: false, display: DISPLAYS.includes(params.get('display')) ? params.get('display') : 'exterior',
    selected: null, hover: null, trees: true, rotate: false, card: 'space', cardOpen: true,
    pointer: null, pointerMoved: false, lineW: 0.6, frame: '', ox: 0, oy: 0,
  };
  const store = {
    ok: true,
    read(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { this.ok = false; return d; } },
    write(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { this.ok = false; return false; } },
  };
  const KEY_Q = `nahiku.${planId}.questions.v1`, KEY_D = `nahiku.${planId}.drafts.v1`;
  let questions = store.read(KEY_Q, []); if (!Array.isArray(questions)) questions = [];
  let drafts = store.read(KEY_D, {}); if (typeof drafts !== 'object' || !drafts) drafts = {};

  // ---------- UI ----------
  const bar = h('div', { id: 'modelbar', hidden: true });
  const seg = h('div', { class: 'mb-seg', role: 'group', 'aria-label': 'Display' },
    DISPLAYS.map(d => h('button', { 'data-display': d, onclick: () => setDisplay(d) }, d[0].toUpperCase() + d.slice(1))));
  const rotBtn = h('button', { class: 'mb-toggle', onclick: () => setRotate(!S.rotate), title: 'Turn the model slowly' }, 'Rotate');
  const treeBtn = h('button', { class: 'mb-toggle', onclick: () => setTrees(!S.trees), title: 'Show or hide palms and trees' }, 'Trees');
  const infoBtn = h('button', { onclick: () => { select(null); S.card = 'space'; S.cardOpen = true; renderCard(); } }, 'Overview');
  const qBtn = h('button', { onclick: () => { S.card = S.card === 'questions' && S.cardOpen ? 'space' : 'questions'; S.cardOpen = true; renderCard(); } });
  const resetBtn = h('button', { onclick: () => home(), title: 'Back to the starting view' }, 'Reset view');
  bar.append(seg, rotBtn, treeBtn, infoBtn, qBtn, resetBtn);
  const card = h('aside', { id: 'inspect', hidden: true, 'aria-live': 'polite' });
  const tip = h('div', { id: 'insp-tip', hidden: true });
  document.body.append(bar, card, tip);

  function refreshBar() {
    for (const b of seg.children) b.classList.toggle('on', b.dataset.display === S.display);
    rotBtn.classList.toggle('on', S.rotate); treeBtn.classList.toggle('on', S.trees);
    qBtn.textContent = `Questions (${questions.length})`;
    qBtn.classList.toggle('on', S.card === 'questions' && S.cardOpen);
  }

  function renderCard() {
    refreshBar();
    card.hidden = !S.active || !S.cardOpen;
    if (card.hidden) return;
    card.replaceChildren();
    const close = h('button', { class: 'ic-close', 'aria-label': 'Close panel', onclick: () => { S.cardOpen = false; renderCard(); } }, '×');
    const parts = S.card === 'questions' ? questionsPanel() : S.selected ? spacePanel(S.selected) : overviewPanel();
    card.append(close, ...parts.flat(2).filter(x => x != null && x !== false));
    card.append(h('p', { class: 'ic-foot' }, info.concept, h('br'), 'Brochure: “Renderings and illustrations are an artistic representation only.” (p6)'));
  }

  const tag = t => h('span', { class: `tag t-${t.toLowerCase()}`, title: TAG_HELP[t] }, t);
  const row = ({ k, v, t, ref, ask }) => h('div', { class: 'ic-row' },
    h('div', { class: 'ic-k' }, k, ' ', tag(t)),
    h('div', { class: 'ic-v' }, v, ref ? h('span', { class: 'ic-ref' }, ` · ${ref}`) : null,
      ask && S.selected ? h('button', { class: 'ic-ask', onclick: () => addToDraft(ask), title: 'Add this to your question draft' }, 'Ask') : null));

  function spaceRows(s) {
    const n = s.name, rows = [], m = s.meta, r = s.room;
    const site = s.site, garage = s.meta.group === 'garage', ohana = s.meta.group === 'ohana';
    if (m.p6?.length) rows.push({ k: 'Name', v: `${n}`, t: 'SOURCE', ref: `p6 label ${m.p6.map(l => `“${l}”`).join(' · ')}` });
    else rows.push({ k: 'Name', v: n, t: 'ASSUMED', ref: m.nameBasis ?? 'not labelled on p6' });
    if (s.group) rows.push({ k: 'Part of', v: `${s.group.label}: ${s.group.stated}`, t: s.group.tag, ref: s.group.ref });
    for (const [k, v, ref] of m.source ?? []) rows.push({ k, v, t: 'SOURCE', ref: ref ?? 'p6' });
    const areaT = site || garage ? 'ASSUMED' : 'ESTIMATE', areaRef = site ? (s.id === 'pool' ? 'I-10' : 'I-6') : garage ? 'I-4' : ohana ? 'E-1, E-4' : 'E-1, E-2';
    rows.push({ k: s.zone ? 'Zone area' : 'Area', v: `≈ ${round(s.area, 5).toLocaleString('en-US')} sq ft (${site || garage ? 'modelled' : 'traced'} outline)`, t: areaT, ref: areaRef, ask: `What are the dimensioned measurements of the ${n}?` });
    rows.push({ k: 'Overall', v: `≈ ${round(s.box[2] - s.box[0], 0.5)} × ${round(s.box[3] - s.box[1], 0.5)} ft`, t: areaT, ref: areaRef });
    for (const [k, v, ref] of m.estimate ?? []) rows.push({ k, v, t: 'ESTIMATE', ref: ref ?? 'E-1' });
    for (const [k, v, ref] of m.assumed ?? []) rows.push({ k, v, t: 'ASSUMED', ref });
    if (r) {
      if (r.outdoor && !r.covered) rows.push({ k: 'Ceiling', v: 'Open to the sky', t: 'ASSUMED', ref: 'p4/p5 renderings' });
      else if (typeof r.ceiling === 'number') rows.push({ k: 'Ceiling', v: `Flat, ${fmtFt(r.ceiling)}`, t: 'ASSUMED', ref: 'I-1', ask: `What is the ceiling height in the ${n}?` });
      else { const [lo, hi] = ceilingRange(s.polygon); rows.push({ k: 'Ceiling', v: `Vaulted to the roof, ≈ ${fmtFt(lo)} to ${fmtFt(hi)}`, t: 'ASSUMED', ref: 'I-1, I-3', ask: `What is the ceiling height and vault profile in the ${n}?` }); }
      rows.push({ k: 'Floor', v: FLOOR_NAMES[r.floor] ?? r.floor, t: 'ASSUMED', ref: 'I-12 (p7 concept board)', ask: `What flooring is specified for the ${n}, and are there options?` });
      if (!site) {
        rows.push({ k: 'Doors & windows', v: garage ? 'Placed from the p4 rendering' : 'Positions and widths traced from p6', t: garage ? 'ASSUMED' : 'ESTIMATE', ref: garage ? 'I-4' : 'E-2' });
        rows.push({ k: 'Opening heights', v: 'From the renderings', t: 'ASSUMED', ref: 'I-2', ask: `What are the window and door sizes and types in the ${n}?` });
        if (!r.outdoor || r.covered) rows.push({ k: 'Fixtures & furniture', v: garage ? 'Staging only' : 'Layout from the p6 symbols; styling from the p7 board', t: garage ? 'ASSUMED' : 'ESTIMATE', ref: garage ? 'I-15' : 'E-3, I-15' });
      }
    }
    const unknown = site
      ? (s.id === 'pool' ? ['Pool plans and sections', 'Grading and drainage plan'] : ['Plat and boundary survey', 'Finished-floor elevation', 'Views from the lot (not verified)'])
      : ['Dimensioned drawings', 'Window and door schedule', 'Finish schedule and specification', 'Electrical and lighting plan'];
    for (const u of unknown) rows.push({ k: u, v: 'Not supplied', t: 'UNKNOWN', ask: `${n}: please share the ${u.toLowerCase().replace(/ \(.*\)$/, '')}.` });
    return rows;
  }

  function spacePanel(s) {
    const out = [h('h2', {}, s.name), h('div', { class: 'ic-sub' }, s.group?.label ?? '')];
    out.push(h('div', { class: 'ic-rows' }, spaceRows(s).map(row)));
    for (const n of s.meta.notes ?? []) out.push(h('p', { class: 'ic-note' }, n));
    out.push(...askBox(s));
    out.push(legend());
    return out;
  }

  function overviewPanel() {
    const H = info.home, sum = ids => ids.reduce((a, id) => a + (byId.get(id)?.area ?? 0), 0);
    const main = spaces.filter(s => s.meta.group === 'main' && !s.zone).map(s => s.id);
    const rows = [
      ...H.source.map(([k, v, ref]) => ({ k, v, t: 'SOURCE', ref })),
      { k: 'Main-house rooms, traced', v: `≈ ${round(sum(main), 10).toLocaleString('en-US')} sq ft against 2,300 stated`, t: 'ESTIMATE', ref: 'E-1' },
      { k: 'ʻOhana rooms, traced', v: `≈ ${round(sum(['ohana', 'ohbath']), 5)} sq ft against 352 stated`, t: 'ESTIMATE', ref: 'E-1, E-4' },
      { k: 'Lānai (+ entry), traced', v: `≈ ${round(sum(['lanai']), 5)} (${round(sum(['lanai', 'entry']), 5)}) sq ft against 494 stated`, t: 'ESTIMATE', ref: 'E-1' },
      ...H.estimate.map(([k, v, ref]) => ({ k, v, t: 'ESTIMATE', ref })),
      ...H.assumed.map(([k, v, ref]) => ({ k, v, t: 'ASSUMED', ref })),
      ...H.unknown.map(u => ({ k: u, v: 'Not supplied', t: 'UNKNOWN' })),
    ];
    return [h('h2', {}, H.name), h('div', { class: 'ic-sub' }, 'Tap or click a space on the model or the map'),
      h('div', { class: 'ic-rows' }, rows.map(row)), legend()];
  }

  const legend = () => h('div', { class: 'ic-legend' }, ...['SOURCE', 'ESTIMATE', 'ASSUMED', 'UNKNOWN'].flatMap(t => [tag(t), h('span', {}, ` ${TAG_HELP[t]}`), h('br')]));

  // ---------- questions (this browser only) ----------
  let ta = null;
  function askBox(s) {
    ta = h('textarea', { rows: 3, maxlength: 2000, placeholder: `Draft a question about the ${s.name} (saved in this browser only)`, 'aria-label': `Question about the ${s.name}` });
    ta.value = drafts[s.id] ?? '';
    let timer = 0;
    ta.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => saveDraft(s.id, ta.value), 250); });
    ta.addEventListener('keydown', e => e.stopPropagation());
    const mine = questions.filter(q => q.space.id === s.id);
    return [
      h('h3', {}, 'Your questions'),
      ta,
      h('div', { class: 'ic-actions' },
        h('button', { class: 'primary', onclick: () => saveQuestion(s) }, 'Save question'),
        h('span', { class: 'ic-local' }, store.ok ? 'Saved on this device only. Nothing is sent.' : 'This browser blocks storage: questions last until you reload.')),
      mine.length ? h('ol', { class: 'ic-qs' }, mine.map(qItem)) : null,
    ];
  }
  function qItem(q) {
    return h('li', {},
      h('div', { class: 'q-text' }, q.text),
      h('div', { class: 'q-meta' }, `${q.space.name} · ${q.display} · ${new Date(q.created).toLocaleString()}`, ' ',
        h('button', { onclick: () => goTo(q) }, 'View'), ' ',
        h('button', { onclick: () => { questions = questions.filter(x => x.id !== q.id); store.write(KEY_Q, questions); renderCard(); } }, 'Delete')));
  }
  function questionsPanel() {
    const groups = new Map();
    for (const q of questions) { if (!groups.has(q.space.name)) groups.set(q.space.name, []); groups.get(q.space.name).push(q); }
    return [
      h('h2', {}, `Questions (${questions.length})`),
      h('div', { class: 'ic-sub' }, 'Stored only in this browser. Nothing is sent. Export makes a file on this device that you can share yourself.'),
      ...(questions.length ? [...groups].flatMap(([name, qs]) => [h('h3', {}, name), h('ol', { class: 'ic-qs' }, qs.map(qItem))])
        : [h('p', { class: 'ic-note' }, 'No saved questions yet. Select a space, draft a question in its panel, or tap “Ask” next to any estimate, assumption or unknown.')]),
      h('div', { class: 'ic-actions' },
        h('button', { class: 'primary', disabled: !questions.length, onclick: exportQuestions }, 'Export JSON'),
        h('button', { disabled: !questions.length, onclick: copyQuestions }, 'Copy as text'),
        h('button', { disabled: !questions.length, onclick: () => { if (confirm(`Delete all ${questions.length} saved questions from this browser?`)) { questions = []; store.write(KEY_Q, questions); renderCard(); } } }, 'Delete all')),
    ];
  }
  function saveDraft(id, text) { if (text.trim()) drafts[id] = text; else delete drafts[id]; store.write(KEY_D, drafts); }
  function addToDraft(text) {
    if (!ta) return;
    ta.value = ta.value.trim() ? `${ta.value.trim()}\n${text}` : text;
    saveDraft(S.selected.id, ta.value); ta.focus();
  }
  function saveQuestion(s) {
    const text = ta.value.trim();
    if (!text) { ta.focus(); return; }
    const r2 = v => Math.round(v * 100) / 100;
    questions.push({
      id: globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
      created: new Date().toISOString(), space: { id: s.id, name: s.name }, display: S.display, text,
      camera: { position: camera.position.toArray().map(r2), target: orbit.target.toArray().map(r2) },
    });
    store.write(KEY_Q, questions); saveDraft(s.id, '');
    renderCard();
  }
  function exportDoc() {
    return { format: 'nahiku-questions/1', exported: new Date().toISOString(), home: info.home.name, label: info.concept,
      units: 'camera in feet, model coordinates', questions };
  }
  function exportQuestions() {
    const a = h('a', { href: URL.createObjectURL(new Blob([JSON.stringify(exportDoc(), null, 1)], { type: 'application/json' })), download: `nahiku-${planId}-questions.json` });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
  function copyQuestions() {
    const text = [`${info.home.name}: questions (${info.concept})`, ...questions.map((q, i) => `${i + 1}. [${q.space.name}] ${q.text}`)].join('\n');
    navigator.clipboard?.writeText(text).catch(() => {});
  }
  function goTo(q) {
    setDisplay(q.display);
    select(byId.get(q.space.id) ?? null);
    camera.position.fromArray(q.camera.position); orbit.target.fromArray(q.camera.target); orbit.update();
  }

  // ---------- selection ----------
  function select(s) {
    S.selected = s; S.card = 'space';
    if (s) { S.cardOpen = true; setOutline(hl.fill, hl.line, s); }
    hl.fill.visible = hl.line.visible = !!s && S.active;
    renderCard(); syncURL();
  }
  function setOutline(fill, line, s) {
    if (fill) { fill.geometry.dispose(); fill.geometry = flat(s.polygon, s.level + 0.02); }
    line.geometry.dispose(); line.geometry = ribbon(s.polygon, s.level + 0.04, S.lineW * (s.site ? 1.5 : 1));
  }
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(clientX, clientY) {
    const r = renderer.domElement.getBoundingClientRect();
    ndc.set((clientX - r.left) / r.width * 2 - 1, -(clientY - r.top) / r.height * 2 + 1);
    ray.setFromCamera(ndc, camera);
    return ray.intersectObjects(plates, false)[0]?.object.userData.space ?? null;
  }
  // plan point (minimap): the smallest space containing it
  const spaceAt = (x, y) => spaces.filter(s => inside([x, y], s.polygon)).sort((a, b) => a.area - b.area)[0] ?? null;
  const el = renderer.domElement;
  el.addEventListener('pointerdown', e => { if (S.active) S.pointer = { x: e.clientX, y: e.clientY, t: performance.now() }; });
  el.addEventListener('pointerup', e => {
    const p = S.pointer; S.pointer = null;
    if (!S.active || !p || Math.hypot(e.clientX - p.x, e.clientY - p.y) > 6 || performance.now() - p.t > 700) return;
    const s = pick(e.clientX, e.clientY);
    if (s !== S.selected) select(s);
  });
  let mouse = null;
  el.addEventListener('pointermove', e => { if (S.active && e.pointerType === 'mouse' && !e.buttons) { mouse = { x: e.clientX, y: e.clientY }; S.pointerMoved = true; } });
  el.addEventListener('pointerleave', () => { mouse = null; S.pointerMoved = true; });

  // ---------- camera ----------
  let saved = null;
  const start = () => ({ pos: new THREE.Vector3(cx + 96, 82, cz + 72), target: new THREE.Vector3(cx, 2, cz) });
  // keep the model centred in the part of the screen the panels leave free: shift the projection centre
  // (a view offset) rather than the orbit target, so the model still turns about its own middle
  function frame(dt = Infinity) {
    const W = innerWidth, H = innerHeight;
    let top = 0, right = W, bottom = H;
    if (S.active && !bar.hidden) top = bar.getBoundingClientRect().bottom;
    if (S.active && !card.hidden) { const r = card.getBoundingClientRect(); if (r.top > H * 0.3) bottom = r.top; else right = r.left; }
    // glide to the new centre when a panel opens or closes (no jump under the pointer)
    const tx = S.active ? W / 2 - right / 2 : 0, ty = S.active ? H / 2 - (top + bottom) / 2 : 0, k = Math.min(1, dt * 7);
    S.tx = tx; S.ty = ty; S.ox += (tx - S.ox) * k; S.oy += (ty - S.oy) * k;
    if (Math.abs(tx - S.ox) < 0.5) S.ox = tx;
    if (Math.abs(ty - S.oy) < 0.5) S.oy = ty;
    const dx = Math.round(S.ox), dy = Math.round(S.oy);
    const key = `${W}x${H}:${dx}:${dy}:${camera.aspect.toFixed(4)}`;
    if (key === S.frame) return;
    const F = W + 2 * Math.abs(dx), FH = H + 2 * Math.abs(dy);
    if (dx || dy) { camera.aspect = F / FH; camera.setViewOffset(F, FH, dx > 0 ? 2 * dx : 0, dy > 0 ? 2 * dy : 0, W, H); }
    else { camera.clearViewOffset(); camera.aspect = W / H; camera.updateProjectionMatrix(); }
    S.frame = `${W}x${H}:${dx}:${dy}:${camera.aspect.toFixed(4)}`;
    S.pointerMoved = true;                                               // the model moved under the pointer: re-pick the hover
  }
  function home() { const v = start(); camera.position.copy(v.pos); orbit.target.copy(v.target); orbit.update(); }
  function setRotate(on) { S.rotate = on; orbit.autoRotate = on && S.active; orbit.autoRotateSpeed = 0.55; refreshBar(); }
  orbit.addEventListener('start', () => { if (S.active && S.rotate) setRotate(false); });
  const B = spaces.filter(s => !s.site).reduce((b, s) => [Math.min(b[0], s.box[0]), Math.min(b[1], s.box[1]), Math.max(b[2], s.box[2]), Math.max(b[3], s.box[3])], [Infinity, Infinity, -Infinity, -Infinity]);
  orbit.addEventListener('change', () => {
    if (!S.active) return;
    const t = orbit.target;
    t.set(THREE.MathUtils.clamp(t.x, B[0] - 30, B[2] + 30), THREE.MathUtils.clamp(t.y, -2, 16), THREE.MathUtils.clamp(t.z, B[1] - 30, B[3] + 30));
  });

  // ---------- context: the other homes and the trees ----------
  const trees = [];
  scene.traverse(o => { if (o.userData.tree) trees.push(o); });
  function setTrees(on) { S.trees = on; for (const t of trees) t.visible = on || !S.active; refreshBar(); }

  function setDisplay(d) {
    if (!DISPLAYS.includes(d)) return;
    S.display = d;
    if (S.active) { apply(d); setTrees(d === 'exterior'); }
    refreshBar(); syncURL();
  }
  function syncURL() {
    if (!S.active) return;
    const p = new URLSearchParams(location.search);
    p.set('mode', 'model'); p.set('display', S.display);
    if (S.selected) p.set('space', S.selected.id); else p.delete('space');
    history.replaceState(null, '', `${location.pathname}?${p}`);
  }

  const api = {
    get active() { return S.active; },
    enter() {
      if (S.active) return;
      S.active = true;
      renderer.localClippingEnabled = true;
      saved = { min: orbit.minDistance, max: orbit.maxDistance, polar: orbit.maxPolarAngle, auto: orbit.autoRotate };
      Object.assign(orbit, { enabled: true, minDistance: 18, maxDistance: 300, maxPolarAngle: Math.PI * 0.47 });
      home();
      const homes = window.__neighborhood?.homes; if (homes) homes.visible = false;
      daylight?.autoSunPath(false);
      const sky = document.getElementById('skypanel'); if (sky?.classList.contains('open')) sky.querySelector('.sp-head')?.click();
      bar.hidden = false; S.cardOpen = !matchMedia('(max-width: 600px)').matches || !!S.selected;
      setDisplay(S.display); setRotate(S.rotate);
      const want = params.get('space'); if (want && byId.has(want) && !S.selected) select(byId.get(want)); else select(S.selected);
    },
    exit() {
      if (!S.active) return;
      apply('exterior'); S.active = false; setTrees(true); orbit.autoRotate = false;
      Object.assign(orbit, { minDistance: saved.min, maxDistance: saved.max, maxPolarAngle: saved.polar });
      const homes = window.__neighborhood?.homes; if (homes) homes.visible = true;
      for (const m of Object.values(hl)) m.visible = false;
      bar.hidden = card.hidden = tip.hidden = true;
      frame();
      const p = new URLSearchParams(location.search); for (const k of ['display', 'space']) p.delete(k); p.delete('mode');
      history.replaceState(null, '', `${location.pathname}${p.size ? `?${p}` : ''}`);
    },
    update(dt = 1 / 60) {
      if (!S.active) return;
      syncVariants();
      frame(dt);
      // outlines a few pixels wide at any zoom
      const w = THREE.MathUtils.clamp(camera.position.distanceTo(orbit.target) * 0.0075, 0.35, 2.5);
      if (Math.abs(w - S.lineW) > S.lineW * 0.15) {
        S.lineW = w;
        if (S.selected) setOutline(null, hl.line, S.selected);
        if (S.hover) setOutline(null, hl.hover, S.hover);
      }
      if (S.pointerMoved) {
        S.pointerMoved = false;
        const s = mouse ? pick(mouse.x, mouse.y) : null;
        if (s !== S.hover) { S.hover = s; if (s) setOutline(null, hl.hover, s); }
        hl.hover.visible = !!s && s !== S.selected;
        tip.hidden = !s;
        if (s) { tip.textContent = s.name; tip.style.transform = `translate(${mouse.x + 14}px, ${mouse.y + 12}px)`; }
        el.style.cursor = s ? 'pointer' : '';
      }
    },
    title() { return S.selected ? S.selected.name : 'Model view'; },
    selectedPolygon() { return S.selected?.polygon ?? null; },
    selectAt(x, y) { if (!S.active) return false; select(spaceAt(x, y)); return true; },
    // for QA scripts (scripts/inspect_qa.mjs)
    setDisplay, select: id => select(id ? byId.get(id) ?? null : null),
    screenOf(id) {
      const s = byId.get(id); if (!s) return null;
      const c = centroid(s.polygon), v = new THREE.Vector3(c[0], s.level, c[1]).project(camera), r = el.getBoundingClientRect();
      return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height };
    },
    table() { return spaces.map(s => ({ id: s.id, name: s.name, p6: s.meta.p6 ?? [], group: s.meta.group, area: round(s.area, 1), w: round(s.box[2] - s.box[0], 0.1), d: round(s.box[3] - s.box[1], 0.1), ceiling: s.room ? (typeof s.room.ceiling === 'number' ? s.room.ceiling : ceilingRange(s.polygon).map(v => round(v, 0.1))) : null })); },
    settled: () => S.ox === S.tx && S.oy === S.ty,
    questions: () => questions, state: () => ({ display: S.display, selected: S.selected?.id ?? null, trees: S.trees, rotate: S.rotate, storage: store.ok }),
  };
  window.__inspect = api;
  return api;

  function ceilingRange(poly) {
    const xs = poly.map(p => p[0]), ys = poly.map(p => p[1]);
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < 9; i++) for (let j = 0; j < 9; j++) {
      const x = Math.min(...xs) + (Math.max(...xs) - Math.min(...xs)) * (i + 0.5) / 9, y = Math.min(...ys) + (Math.max(...ys) - Math.min(...ys)) * (j + 0.5) / 9;
      if (!inside([x, y], poly)) continue;
      const c = ceilingAt(x, y); lo = Math.min(lo, c); hi = Math.max(hi, c);
    }
    return [lo, hi];
  }
}

// ---------- helpers ----------
function polyArea(p) { let a = 0; for (let i = 0; i < p.length; i++) { const [x0, y0] = p[i], [x1, y1] = p[(i + 1) % p.length]; a += x0 * y1 - x1 * y0; } return Math.abs(a) / 2; }
function centroid(p) { const xs = p.map(q => q[0]), ys = p.map(q => q[1]); return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2]; }
const round = (v, step) => Math.round(v / step) * step;
function fmtFt(v) { const ft = Math.floor(v + 1e-6), inch = Math.round((v - ft) * 12); return inch === 12 ? `${ft + 1} ft` : inch ? `${ft} ft ${inch} in` : `${ft} ft`; }
// a flat polygon at height y (plan x -> x, plan y -> z)
function flat(poly, y) {
  const g = new THREE.ShapeGeometry(new THREE.Shape(poly.map(([x, z]) => new THREE.Vector2(x, -z))));
  g.rotateX(-Math.PI / 2); g.translate(0, y, 0); return g;
}
// a flat band of width w along the polygon's edges, centred on them
function ribbon(poly, y, w) {
  const P = [];
  for (let i = 0; i < poly.length; i++) {
    const [ax, az] = poly[i], [bx, bz] = poly[(i + 1) % poly.length], L = Math.hypot(bx - ax, bz - az) || 1;
    const nx = -(bz - az) / L * w / 2, nz = (bx - ax) / L * w / 2, ex = (bx - ax) / L * w / 2, ez = (bz - az) / L * w / 2;
    const q = [[ax - nx - ex, az - nz - ez], [bx - nx + ex, bz - nz + ez], [bx + nx + ex, bz + nz + ez], [ax + nx - ex, az + nz - ez]];
    for (const k of [0, 1, 2, 0, 2, 3]) P.push(q[k][0], y, q[k][1]);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); return g;
}
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(2)) if (c != null && c !== false) e.append(c instanceof Node ? c : String(c));
  return e;
}
