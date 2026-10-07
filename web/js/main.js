// ─────────────────────────────────────────────────────────────
//  Resume, exploded.
//  WebGL renders the world (grid, glyph dust, leader lines);
//  CSS3D renders every resume layer as real HTML, so text stays
//  vector-sharp at any zoom level.
// ─────────────────────────────────────────────────────────────
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS3DRenderer, CSS3DObject } from 'three/addons/renderers/CSS3DRenderer.js';
import { PAGE, LAYERS, DEFAULT_THEME, APPEARANCE, RESUME_META } from './data.js';

const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = (s) => document.querySelector(s);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const pad = (n) => String(n).padStart(2, '0');
const THEME_KEY = 'aasoft.resume3d.theme';
const THEMES = {
  midnight: { void: 0x0b1120, primary: 0x22d3ee, secondary: 0x8b5cf6, particles: ['#22d3ee', '#8b5cf6', '#3b82f6', '#e2e8f0'], meta: '#0b1120' },
  aurora:   { void: 0x061713, primary: 0x5eead4, secondary: 0xc084fc, particles: ['#5eead4', '#c084fc', '#8b5cf6', '#d1fae5'], meta: '#061713' },
  ember:    { void: 0x190a10, primary: 0xfb7185, secondary: 0xf59e0b, particles: ['#fb7185', '#f59e0b', '#f97316', '#ffe4e6'], meta: '#190a10' },
  matrix:   { void: 0x020a05, primary: 0x4ade80, secondary: 0x22c55e, particles: ['#4ade80', '#22c55e', '#86efac', '#dcfce7'], meta: '#020a05' },
  mono:     { void: 0x08090b, primary: 0xe2e8f0, secondary: 0x64748b, particles: ['#f8fafc', '#94a3b8', '#64748b', '#e2e8f0'], meta: '#08090b' },
  ocean:    { void: 0x031523, primary: 0x38bdf8, secondary: 0x14b8a6, particles: ['#38bdf8', '#14b8a6', '#7dd3fc', '#ccfbf1'], meta: '#031523' },
  synthwave:{ void: 0x160b24, primary: 0xf472b6, secondary: 0x22d3ee, particles: ['#f472b6', '#22d3ee', '#a78bfa', '#fce7f3'], meta: '#160b24' },
  solar:    { void: 0x160e05, primary: 0xf59e0b, secondary: 0xef4444, particles: ['#f59e0b', '#f97316', '#ef4444', '#fef3c7'], meta: '#160e05' },
};
const readTheme = () => {
  try { const t = localStorage.getItem(THEME_KEY); return THEMES[t] ? t : DEFAULT_THEME; } catch { return 'midnight'; }
};
let activeTheme = readTheme();
document.body.dataset.theme = activeTheme;
const QUALITY_KEY = 'aasoft.resume3d.quality';
const SEEN_KEY = 'aasoft.resume3d.seen';
const QUALITY = {
  high: { dpr: 1.75, dust: 1, fps: 60 },
  balanced: { dpr: 1.35, dust: 0.62, fps: 45 },
  eco: { dpr: 1, dust: 0.3, fps: 30 },
};
const lowPowerDevice = (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4) || (navigator.deviceMemory && navigator.deviceMemory <= 4);
const resolveAutoQuality = () => lowPowerDevice || innerWidth < 720 ? 'eco' : (devicePixelRatio > 1.5 ? 'balanced' : 'high');
const readQuality = () => {
  try {
    const stored = localStorage.getItem(QUALITY_KEY);
    if (stored && ['high','balanced','eco','auto'].includes(stored)) return stored;
  } catch { /* storage can be disabled */ }
  return APPEARANCE.quality || 'auto';
};
let qualityPreference = readQuality();
let activeQuality = qualityPreference === 'auto' ? resolveAutoQuality() : qualityPreference;
document.body.dataset.quality = activeQuality;
const ease = {
  inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  out: (t) => 1 - Math.pow(1 - t, 3),
  outBack: (t) => 1 + 2.2 * Math.pow(t - 1, 3) + 1.2 * Math.pow(t - 1, 2),
  linear: (t) => t,
};

// ─────────────── renderers ───────────────
const stage = $('#stage');
const scene = new THREE.Scene();
const cssScene = new THREE.Scene();
scene.fog = new THREE.FogExp2(THEMES[activeTheme].void, 0.00016);

const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, 1, 30000);
camera.position.set(0, 0, 3200);

let gl = null;
try {
  gl = new THREE.WebGLRenderer({ antialias: activeQuality !== 'eco', alpha: true, powerPreference: activeQuality === 'eco' ? 'low-power' : 'high-performance' });
  gl.setPixelRatio(Math.min(devicePixelRatio, QUALITY[activeQuality].dpr));
  gl.setSize(innerWidth, innerHeight);
  gl.domElement.className = 'gl';
  stage.appendChild(gl.domElement);
} catch (err) {
  console.warn('WebGL unavailable, running CSS-only.', err);
  gl = null;
}

const css = new CSS3DRenderer();
css.setSize(innerWidth, innerHeight);
css.domElement.className = 'css';
stage.appendChild(css.domElement);

const controls = new OrbitControls(camera, css.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.075;
controls.rotateSpeed = 0.55;
controls.zoomSpeed = 0.9;
controls.panSpeed = 0.8;
controls.screenSpacePanning = true;
controls.zoomToCursor = true;
controls.minDistance = 90;
controls.maxDistance = 7000;
controls.enabled = false;

// ─────────────── helpers ───────────────
const toWorld = (b) => new THREE.Vector3(b.x + b.w / 2 - PAGE.w / 2, PAGE.h / 2 - (b.y + b.h / 2), 0);

const anims = new Set();
function animate(dur, fn, { delay = 0, curve = ease.inOut } = {}) {
  if (REDUCED) dur = Math.min(dur, 250);
  return new Promise((res) => anims.add({ start: performance.now() + delay, dur, fn, curve, res }));
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// ─────────────── the paper (ghost page) ───────────────
const paperEl = document.createElement('div');
paperEl.className = 'paper';
paperEl.style.width = PAGE.w + 'px';
paperEl.style.height = PAGE.h + 'px';
const scanEl = document.createElement('div');
scanEl.className = 'scan';
paperEl.appendChild(scanEl);
LAYERS.forEach((L, i) => {
  const s = document.createElement('div');
  s.className = 'slot';
  Object.assign(s.style, { left: L.box.x + 'px', top: L.box.y + 'px', width: L.box.w + 'px', height: L.box.h + 'px' });
  s.textContent = 'L' + pad(i + 1);
  paperEl.appendChild(s);
});
const paper = new CSS3DObject(paperEl);
paper.position.z = -3;
cssScene.add(paper);

// ─────────────── the layers ───────────────
const IDQ = new THREE.Quaternion();
const panels = LAYERS.map((L, i) => {
  const el = document.createElement('section');
  el.className = 'panel ' + (L.cls || '');
  el.style.width = L.box.w + 'px';
  el.style.height = L.box.h + 'px';
  el.dataset.index = i;
  el.setAttribute('aria-label', L.title);
  el.innerHTML = `<div class="tag"><b>L${pad(i + 1)}</b>${L.path}</div>${L.html}`;
  el.querySelectorAll('[data-pop]').forEach((n, k) => {
    n.style.setProperty('--i', k);
    n.style.setProperty('--z', (n.dataset.z || 10 + (k % 3) * 6) + 'px');
  });
  const obj = new CSS3DObject(el);
  cssScene.add(obj);
  const page = toWorld(L.box);
  const e = L.ex;
  const expl = new THREE.Vector3(page.x * 1.42 + (e.dx || 0) * 1.3, page.y * 1.34 + (e.dy || 0) * 1.3, e.z * 1.35);
  const explQ = new THREE.Quaternion().setFromEuler(new THREE.Euler(e.rx || 0, e.ry || 0, e.rz || 0));
  obj.position.copy(page);
  return { i, L, el, obj, page, expl, explQ, mix: 0, bob: 1, phase: Math.random() * Math.PI * 2 };
});

// ─────────────── the world (WebGL) ───────────────
const world = new THREE.Group();
scene.add(world);

// blueprint floor
const grid = new THREE.GridHelper(16000, 160, THEMES[activeTheme].primary, 0x1e293b);
grid.material.vertexColors = false;
grid.material.color.setHex(THEMES[activeTheme].primary);
grid.material.needsUpdate = true;
grid.material.transparent = true;
grid.material.opacity = 0.32;
grid.position.y = -1250;
world.add(grid);
const grid2 = new THREE.GridHelper(16000, 32, THEMES[activeTheme].secondary, THEMES[activeTheme].secondary);
grid2.material.vertexColors = false;
grid2.material.color.setHex(THEMES[activeTheme].secondary);
grid2.material.needsUpdate = true;
grid2.material.transparent = true;
grid2.material.opacity = 0.18;
grid2.position.y = -1249;
world.add(grid2);

// halo rings under the page
const ringMat = new THREE.MeshBasicMaterial({ color: THEMES[activeTheme].primary, transparent: true, opacity: 0.25, side: THREE.DoubleSide });
const rings = [900, 1300, 1800].map((r, k) => {
  const m = new THREE.Mesh(new THREE.RingGeometry(r, r + (k === 0 ? 4 : 2), 160), ringMat.clone());
  m.rotation.x = -Math.PI / 2;
  m.position.y = -1248;
  m.material.opacity = 0.28 - k * 0.07;
  world.add(m);
  return m;
});

// glyph dust: drifting code characters
function glyphTexture(ch, color) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  g.fillStyle = color;
  g.font = '600 64px "JetBrains Mono", monospace';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.shadowColor = color;
  g.shadowBlur = 18;
  g.fillText(ch, 64, 68);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const GLYPHS = ['{', '}', '</>', '$', '01', 'λ', ';', '#', '=>', '·'];
const dust = [];
function buildDust() {
  dust.forEach((d) => {
    world.remove(d);
    d.geometry.dispose();
    d.material.map?.dispose();
    d.material.dispose();
  });
  dust.length = 0;
  const colors = THEMES[activeTheme].particles;
  GLYPHS.forEach((ch, k) => {
    const col = colors[k % colors.length];
    const base = ch === '·' ? 360 : 56;
    const n = Math.max(ch === '·' ? 90 : 16, Math.round(base * QUALITY[activeQuality].dust));
    const pos = new Float32Array(n * 3);
    const spd = new Float32Array(n);
    for (let j = 0; j < n; j++) {
      pos[j * 3] = (Math.random() - 0.5) * 9000;
      pos[j * 3 + 1] = -1200 + Math.random() * 4200;
      pos[j * 3 + 2] = (Math.random() - 0.5) * 9000;
      spd[j] = 0.15 + Math.random() * 0.5;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const mat = new THREE.PointsMaterial({
      size: ch === '·' ? 18 : 46, map: glyphTexture(ch, col), transparent: true, opacity: 0,
      depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true,
    });
    const pts = new THREE.Points(geo, mat);
    pts.userData = { spd, target: ch === '·' ? 0.7 : 0.55 };
    world.add(pts);
    dust.push(pts);
  });
}
buildDust();
document.fonts?.ready.then(buildDust); // redraw glyphs once the mono font is in

// leader lines from each slot to its floating layer
const leadGeo = new THREE.BufferGeometry();
leadGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(panels.length * 6), 3));
const leadMat = new THREE.LineDashedMaterial({ color: THEMES[activeTheme].primary, dashSize: 14, gapSize: 10, transparent: true, opacity: 0, fog: false });
const leaders = new THREE.LineSegments(leadGeo, leadMat);
scene.add(leaders);

const nodeGeo = new THREE.BufferGeometry();
nodeGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(panels.length * 3), 3));
const dot = (() => {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d');
  const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, '#ffffff'); r.addColorStop(0.25, '#ffffff'); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
})();
const nodes = new THREE.Points(nodeGeo, new THREE.PointsMaterial({ size: 34, map: dot, color: THEMES[activeTheme].primary, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }));
panels.forEach((p, i) => nodeGeo.attributes.position.setXYZ(i, p.page.x, p.page.y, 2));
scene.add(nodes);

// ─────────────── themes / comfort ───────────────
const themePanel = $('#themePanel');
const themeButtons = [...document.querySelectorAll('[data-theme-choice]')];
function paintTheme(name, { persist = true, rebuild = true } = {}) {
  if (!THEMES[name]) return;
  activeTheme = name;
  const t = THEMES[name];
  document.body.dataset.theme = name;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', t.meta);
  scene.fog.color.setHex(t.void);
  grid.material.color.setHex(t.primary);
  grid2.material.color.setHex(t.secondary);
  rings.forEach((r) => r.material.color.setHex(t.primary));
  leadMat.color.setHex(t.primary);
  nodes.material.color.setHex(t.primary);
  themeButtons.forEach((b) => {
    const on = b.dataset.themeChoice === name;
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', String(on));
  });
  if (rebuild) buildDust();
  if (persist) { try { localStorage.setItem(THEME_KEY, name); } catch { /* storage can be disabled */ } }
}
paintTheme(activeTheme, { persist: false, rebuild: false });

let toastTimer = 0;
function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 1800);
}

function closeThemes() {
  themePanel.hidden = true;
  $('#btnTheme').setAttribute('aria-expanded', 'false');
}
$('#btnTheme').addEventListener('click', (e) => {
  e.stopPropagation();
  themePanel.hidden = !themePanel.hidden;
  $('#btnTheme').setAttribute('aria-expanded', String(!themePanel.hidden));
});
themeButtons.forEach((b) => b.addEventListener('click', () => {
  paintTheme(b.dataset.themeChoice);
  toast(`${b.querySelector('span').textContent} theme loaded`);
  closeThemes();
}));
document.addEventListener('pointerdown', (e) => {
  if (!themePanel.hidden && !themePanel.contains(e.target) && e.target !== $('#btnTheme')) closeThemes();
});

// ─────────────── state ───────────────
const state = { exploded: false, focus: -1, touring: false, busy: true, lines: 0, calm: false, eco: activeQuality === 'eco', reader: false, visited: new Set() };
$('#visitedLabel').textContent = `0 / ${panels.length} DISCOVERED`;
if (APPEARANCE.show_availability === false) $('.availability').hidden = true;

function setCalm(on = !state.calm) {
  state.calm = on;
  document.body.classList.toggle('is-calm', on);
  $('#btnCalm').setAttribute('aria-pressed', String(on));
  toast(on ? 'Calm mode · decoration reduced' : 'Full scene restored');
}
$('#btnCalm').addEventListener('click', () => setCalm());

function updateQualityUI(automatic = false) {
  state.eco = activeQuality === 'eco';
  document.body.dataset.quality = activeQuality;
  const label = qualityPreference === 'auto' ? `Auto · ${activeQuality}` : activeQuality;
  $('#qualityLabel').textContent = label.toUpperCase();
  $('#btnQuality').innerHTML = `<span>⚡</span> ${label}`;
  $('#btnQuality').classList.toggle('quality-eco', activeQuality === 'eco');
  $('#btnQuality').classList.toggle('quality-high', activeQuality === 'high');
  if (automatic) toast(`Adaptive rendering · ${activeQuality}`);
}
function setQuality(preference, automatic = false, persist = true) {
  if (!['auto','high','balanced','eco'].includes(preference)) return;
  if (!automatic) qualityPreference = preference;
  activeQuality = automatic ? 'eco' : (preference === 'auto' ? resolveAutoQuality() : preference);
  if (gl) {
    gl.setPixelRatio(Math.min(devicePixelRatio, QUALITY[activeQuality].dpr));
    gl.setSize(innerWidth, innerHeight, false);
  }
  buildDust();
  updateQualityUI(automatic);
  if (persist && !automatic) { try { localStorage.setItem(QUALITY_KEY, preference); } catch { /* noop */ } }
}
const qualityOrder = ['auto','high','balanced','eco'];
$('#btnQuality').addEventListener('click', () => {
  const next = qualityOrder[(qualityOrder.indexOf(qualityPreference) + 1) % qualityOrder.length];
  setQuality(next); toast(`Render quality · ${next}`);
});
updateQualityUI();

function overviewPose() {
  const portrait = camera.aspect < 1;
  const k = portrait ? 1.9 / Math.max(camera.aspect, 0.45) : Math.max(1, 1.5 / camera.aspect);
  return {
    pos: new THREE.Vector3(1700, 560, 2800).multiplyScalar(k * 1.06),
    target: new THREE.Vector3(portrait ? -60 : 40, 280, 260),
  };
}
function pagePose() {
  const v = THREE.MathUtils.degToRad(camera.fov) / 2;
  const d = Math.max((PAGE.h / 2) * 1.12 / Math.tan(v), (PAGE.w / 2) * 1.15 / (Math.tan(v) * camera.aspect));
  return { pos: new THREE.Vector3(0, 0, d), target: new THREE.Vector3(0, 0, 0) };
}

let flightId = 0;
function fly(pos, target, dur = 1500, arc = 0) {
  const id = ++flightId;
  controls.enabled = false;
  const p0 = camera.position.clone();
  const t0 = controls.target.clone();
  return animate(dur, (e) => {
    if (id !== flightId) return;
    camera.position.lerpVectors(p0, pos, e);
    camera.position.y += Math.sin(Math.PI * e) * arc;
    controls.target.lerpVectors(t0, target, e);
    camera.lookAt(controls.target);
  }).then(() => {
    if (id !== flightId) return false;
    controls.enabled = !state.reader;
    controls.update();
    return true;
  });
}

function setExplodedClass(on) {
  document.body.classList.toggle('is-exploded', on);
  $('#btnExplode').textContent = on ? 'Assemble' : 'Explode';
  $('#sceneMode').textContent = on ? 'EXPLODED' : 'ASSEMBLED';
}

function explode(on, { stagger = 70, dur = 1700 } = {}) {
  state.exploded = on;
  setExplodedClass(on);
  animate(dur, (e) => (state.lines = on ? e : 1 - e), { delay: on ? 300 : 0 });
  const order = on ? panels : [...panels].reverse();
  return Promise.all(
    order.map((p, k) => {
      const from = p.mix;
      const to = on ? 1 : 0;
      return animate(dur, (e) => (p.mix = from + (to - from) * e), { delay: k * stagger, curve: on ? ease.inOut : ease.inOut });
    }),
  );
}

// ─────────────── focus / navigation ───────────────
const caption = $('#caption');
const layerButtons = [];
const list = $('#layerList');
panels.forEach((p, i) => {
  const li = document.createElement('li');
  const b = document.createElement('button');
  b.innerHTML = `<span>L${pad(i + 1)}</span>${p.L.title}`;
  b.addEventListener('click', () => { stopTour(); focusLayer(i); });
  li.appendChild(b);
  list.appendChild(li);
  layerButtons.push(b);
});

function markFocus(i) {
  state.focus = i;
  panels.forEach((p, k) => {
    p.el.classList.toggle('is-focused', k === i);
    p.el.classList.toggle('is-dim', i >= 0 && k !== i);
    layerButtons[k].classList.toggle('on', k === i);
    layerButtons[k].setAttribute('aria-current', k === i ? 'true' : 'false');
  });
  if (i >= 0) {
    const wasNew = !state.visited.has(i);
    state.visited.add(i);
    $('#visitedLabel').textContent = `${state.visited.size} / ${panels.length} DISCOVERED`;
    if (wasNew && state.visited.size === 5) toast('Achievement · curious mind · 5 layers discovered');
    if (wasNew && state.visited.size === panels.length) toast('Achievement · full-stack explorer · all layers found');
    caption.innerHTML = `L${pad(i + 1)} / ${pad(panels.length)}<b>${panels[i].L.title}</b>`;
    caption.classList.add('show');
    const path = panels[i].L.path || panels[i].L.id;
    history.replaceState(null, '', `${location.pathname}${location.search}#${encodeURI(path)}`);
  } else {
    caption.classList.remove('show');
    history.replaceState(null, '', `${location.pathname}${location.search}`);
  }
}

function focusPose(p) {
  const q = p.explQ.clone();
  const center = p.expl.clone();
  const normal = new THREE.Vector3(0, 0, 1).applyQuaternion(q);
  const up = new THREE.Vector3(0, 1, 0).applyQuaternion(q);
  const right = new THREE.Vector3(1, 0, 0).applyQuaternion(q);
  // view slightly from the right and above so the lifted elements read as depth
  const dir = normal
    .applyAxisAngle(up, p.i % 2 ? 0.2 : -0.2)
    .applyAxisAngle(right, -0.08)
    .normalize();
  const v = THREE.MathUtils.degToRad(camera.fov) / 2;
  const { w, h } = p.L.box;
  // leave room for the HUD: layer list on the right, dock + caption at the bottom
  const side = innerWidth > 1100 ? 560 : 32;
  const availW = Math.max(innerWidth - side, 240);
  const availH = Math.max(innerHeight - (innerWidth < 720 ? 210 : 250), 240);
  const dH = ((h + 90) / 2 / Math.tan(v)) * (innerHeight / availH);
  const dW = ((w + 90) / 2 / (Math.tan(v) * camera.aspect)) * (innerWidth / availW);
  const d = Math.max(dH, dW);
  return { pos: center.clone().addScaledVector(dir, Math.max(d, 260)), target: center };
}

async function focusLayer(i) {
  i = (i + panels.length) % panels.length;
  if (!state.exploded) await explode(true, { stagger: 30, dur: 1100 });
  const p = panels[i];
  panels.forEach((q) => q !== p && q.bob < 1 && animate(900, (e) => (q.bob = Math.max(q.bob, e))));
  const b0 = p.bob;
  animate(500, (e) => (p.bob = b0 * (1 - e)));
  markFocus(i);
  const { pos, target } = focusPose(p);
  return fly(pos, target, 1400, 90);
}

function toOverview(dur = 1500) {
  markFocus(-1);
  panels.forEach((q) => { const b = q.bob; animate(900, (e) => (q.bob = b + (1 - b) * e)); });
  const { pos, target } = overviewPose();
  return fly(pos, target, dur, 160);
}

async function toggleExplode() {
  stopTour();
  if (state.exploded) {
    markFocus(-1);
    const { pos, target } = pagePose();
    fly(pos, target, 1700, 0);
    await explode(false, { stagger: 35, dur: 1400 });
  } else {
    explode(true);
    await toOverview(2200);
  }
}

// guided tour
async function tour() {
  if (state.touring) return stopTour();
  state.touring = true;
  $('#btnTour').classList.add('on');
  $('#btnTour').textContent = 'Stop';
  const start = state.focus >= 0 ? state.focus : 0;
  for (let k = 0; k < panels.length && state.touring; k++) {
    const ok = await focusLayer(start + k);
    if (!state.touring || ok === false) return;
    await wait(2600);
  }
  if (state.touring) { stopTour(); toOverview(); }
}
function stopTour() {
  if (!state.touring) return;
  state.touring = false;
  $('#btnTour').classList.remove('on');
  $('#btnTour').textContent = 'Tour';
}

// ─────────────── playful exploration + command palette ───────────────
const themeOrder = Object.keys(THEMES);
const projectIds = ['ai-exam-generator', 'flowtransfer', 'persian-voice-assistant', 'persian-poetry', 'skills'];
function cycleTheme() {
  const next = themeOrder[(themeOrder.indexOf(activeTheme) + 1) % themeOrder.length];
  paintTheme(next);
  toast(`${next} theme`);
}
function surprise() {
  if (state.busy) return;
  stopTour();
  const choices = themeOrder.filter((t) => t !== activeTheme);
  paintTheme(choices[Math.floor(Math.random() * choices.length)]);
  const id = projectIds[Math.floor(Math.random() * projectIds.length)];
  const i = panels.findIndex((p) => p.L.id === id);
  focusLayer(i);
  toast('✦ New scene unlocked');
}
$('#btnSurprise').addEventListener('click', surprise);

async function copyText(value, message) {
  try {
    await navigator.clipboard.writeText(value);
    toast(message);
  } catch {
    const ta = document.createElement('textarea');
    ta.value = value; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); ta.remove(); toast(message);
  }
}


// Recruiter-friendly 2D reader view reuses the generated layer HTML.
const reader = $('#readerMode');
let readerBuilt = false;
function buildReader() {
  if (readerBuilt) return;
  $('#readerName').textContent = `${RESUME_META.name || 'Resume'} · ${RESUME_META.title || ''}`;
  $('#readerContent').innerHTML = LAYERS.filter((L) => L.id !== 'footer').map((L) => {
    const wide = ['header','profile','projects','experience','motto'].includes(L.id) || L.id.startsWith('project');
    return `<article class="reader-card" data-wide="${wide}"><section class="panel ${L.cls || ''}">${L.html}</section></article>`;
  }).join('');
  readerBuilt = true;
}
function toggleReader(on = !state.reader) {
  state.reader = on;
  buildReader();
  reader.hidden = !on;
  document.body.classList.toggle('is-reader', on);
  $('#btnReader').setAttribute('aria-pressed', String(on));
  $('#btnReader').innerHTML = on ? '<span>×</span> 3D' : '<span>▤</span> Read';
  if (on) { stopTour(); controls.enabled = false; }
  else if (!state.busy) controls.enabled = true;
}
async function shareCurrent() {
  const payload = { title: `${RESUME_META.name || 'Resume'} · 3D Resume`, text: RESUME_META.title || '', url: location.href };
  if (navigator.share) {
    try { await navigator.share(payload); return; } catch (err) { if (err?.name === 'AbortError') return; }
  }
  copyText(location.href, 'Link copied');
}
$('#btnReader').addEventListener('click', () => toggleReader());
$('#readerClose').addEventListener('click', () => toggleReader(false));
$('#btnShare').addEventListener('click', shareCurrent);
$('#readerShare').addEventListener('click', shareCurrent);

const palette = $('#commandPalette');
const commandInput = $('#commandInput');
const commandResults = $('#commandResults');
let commandSelection = 0;
let visibleCommands = [];
const systemCommands = [
  { icon: '⌂', label: 'Return to overview', hint: 'reset camera', kind: 'view', run: () => toOverview() },
  { icon: '▶', label: 'Start guided tour', hint: 'walk through every layer', kind: 'view', run: () => tour() },
  { icon: '◫', label: 'Assemble / explode resume', hint: 'toggle physical view', kind: 'view', run: () => toggleExplode() },
  { icon: '✦', label: 'Surprise me', hint: 'random project + scene', kind: 'fun', run: surprise },
  { icon: '◐', label: 'Cycle theme', hint: 'switch visual atmosphere', kind: 'theme', run: cycleTheme },
  { icon: '≈', label: 'Toggle calm mode', hint: 'reduce decoration', kind: 'comfort', run: () => setCalm() },
  { icon: '▤', label: 'Open recruiter reader mode', hint: 'flat accessible resume', kind: 'view', run: () => toggleReader(true) },
  { icon: '↗', label: 'Share current view', hint: 'native share or copy link', kind: 'share', run: shareCurrent },
  { icon: '⚡', label: 'Cycle render quality', hint: 'auto / high / balanced / eco', kind: 'comfort', run: () => $('#btnQuality').click() },
  { icon: '@', label: 'Copy email address', hint: RESUME_META.email || '', kind: 'contact', run: () => copyText(RESUME_META.email || '', 'Email copied') },
  { icon: '↗', label: 'Copy link to this view', hint: 'deep link', kind: 'share', run: () => copyText(location.href, 'Link copied') },
  ...themeOrder.map((id) => ({ icon: '●', label: `Theme: ${id}`, hint: 'change scene colors', kind: 'theme', run: () => { paintTheme(id); toast(`${id} theme`); } })),
];
const layerCommands = panels.map((p, i) => ({ icon: `L${pad(i + 1)}`, label: p.L.title, hint: p.L.path, kind: 'layer', run: () => focusLayer(i) }));
const commands = [...layerCommands, ...systemCommands];

function renderCommands(query = '') {
  const q = query.trim().toLowerCase();
  visibleCommands = commands.filter((c) => !q || `${c.label} ${c.hint} ${c.kind}`.toLowerCase().includes(q)).slice(0, 12);
  commandSelection = clamp(commandSelection, 0, Math.max(visibleCommands.length - 1, 0));
  commandResults.innerHTML = visibleCommands.length ? visibleCommands.map((c, i) => `
    <button class="command-item ${i === commandSelection ? 'on' : ''}" data-command-index="${i}" role="option" aria-selected="${i === commandSelection}">
      <span class="cmd-icon">${c.icon}</span><span><strong>${c.label}</strong><small>${c.hint}</small></span><span class="cmd-kind">${c.kind}</span>
    </button>`).join('') : '<div class="command-item"><span class="cmd-icon">×</span><span><strong>No match</strong><small>Try a layer name, “theme”, or “tour”.</small></span></div>';
}
function openPalette() {
  if (state.busy) return;
  closeThemes(); palette.hidden = false; commandInput.value = ''; commandSelection = 0; renderCommands();
  requestAnimationFrame(() => commandInput.focus());
}
function closePalette() { palette.hidden = true; commandInput.blur(); }
function runCommand(i = commandSelection) {
  const c = visibleCommands[i]; if (!c) return; closePalette(); c.run();
}
$('#btnCommand').addEventListener('click', openPalette);
commandInput.addEventListener('input', () => { commandSelection = 0; renderCommands(commandInput.value); });
commandInput.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const d = e.key === 'ArrowDown' ? 1 : -1;
    commandSelection = (commandSelection + d + visibleCommands.length) % Math.max(visibleCommands.length, 1); renderCommands(commandInput.value);
    commandResults.querySelector('.on')?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') { e.preventDefault(); runCommand(); }
  else if (e.key === 'Escape') { e.preventDefault(); closePalette(); }
});
commandResults.addEventListener('click', (e) => {
  const item = e.target.closest('[data-command-index]'); if (item) runCommand(+item.dataset.commandIndex);
});
palette.addEventListener('pointerdown', (e) => { if (e.target === palette) closePalette(); });

// ─────────────── input ───────────────
$('#btnPrev').addEventListener('click', () => { stopTour(); focusLayer(state.focus < 0 ? panels.length - 1 : state.focus - 1); });
$('#btnNext').addEventListener('click', () => { stopTour(); focusLayer(state.focus + 1); });
$('#btnOverview').addEventListener('click', () => { stopTour(); if (!state.exploded) explode(true); toOverview(); });
$('#btnExplode').addEventListener('click', toggleExplode);
$('#btnTour').addEventListener('click', tour);

const hint = $('#hint');
let down = null;
document.addEventListener('pointerdown', (e) => {
  if (!stage.contains(e.target)) return;
  // let links inside cards behave like links (don't hand them to the orbit controls)
  if (e.target.closest('a')) { e.stopPropagation(); return; }
  stopTour();
  hint.classList.add('gone');
  down = { x: e.clientX, y: e.clientY, t: performance.now(), panel: e.target.closest('.panel') };
}, true);
document.addEventListener('pointerup', (e) => {
  if (!down || state.busy) return (down = null);
  const tap = Math.hypot(e.clientX - down.x, e.clientY - down.y) < 6 && performance.now() - down.t < 500;
  if (tap) {
    if (down.panel) {
      const i = +down.panel.dataset.index;
      if (i !== state.focus) focusLayer(i);
    } else if (state.focus >= 0) toOverview();
  }
  down = null;
}, true);
css.domElement.addEventListener('wheel', () => { stopTour(); hint.classList.add('gone'); }, { passive: true });

addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); return palette.hidden ? openPalette() : closePalette(); }
  if (!palette.hidden) return;
  if (state.busy || e.metaKey || e.ctrlKey || e.altKey || /input|textarea|select/i.test(document.activeElement?.tagName || '')) return;
  const k = e.key.toLowerCase();
  if (k === '/') { e.preventDefault(); openPalette(); return; }
  if (k === 'arrowright' || k === 'arrowdown' || k === 'n') { stopTour(); focusLayer(state.focus + 1); }
  else if (k === 'arrowleft' || k === 'arrowup' || k === 'p') { stopTour(); focusLayer(state.focus < 0 ? panels.length - 1 : state.focus - 1); }
  else if (k === 'escape' || k === 'r') { stopTour(); if (!state.exploded) explode(true); toOverview(); }
  else if (k === 'e') toggleExplode();
  else if (k === 't' || k === ' ') { e.preventDefault(); tour(); }
  else if (k === 's') surprise();
  else if (k === 'h') cycleTheme();
  else if (k === 'd') toggleReader();
  else return;
  hint.classList.add('gone');
});

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  gl?.setSize(innerWidth, innerHeight);
  css.setSize(innerWidth, innerHeight);
  if (qualityPreference === 'auto') { activeQuality = resolveAutoQuality(); updateQualityUI(); gl?.setPixelRatio(Math.min(devicePixelRatio, QUALITY[activeQuality].dpr)); buildDust(); }
});

// ─────────────── frame loop ───────────────
const tmp = new THREE.Vector3();
const clock = new THREE.Timer();
let perfFrames = 0;
let perfTime = 0;
let lastRender = 0;
let lastActivity = performance.now();
let renderedFrames = 0;
const noteActivity = () => { lastActivity = performance.now(); };
['pointerdown','wheel','keydown','touchstart'].forEach((name) => addEventListener(name, noteActivity, { passive: name !== 'keydown' }));
document.addEventListener('visibilitychange', () => { lastRender = 0; });

function frame(now) {
  requestAnimationFrame(frame);
  if (document.hidden) return;
  const idle = now - lastActivity > 4500 && anims.size === 0 && !state.touring;
  let targetFps = QUALITY[activeQuality].fps;
  if (idle) targetFps = Math.min(targetFps, 30);
  if (state.reader) targetFps = 5;
  if (now - lastRender < 1000 / targetFps) return;
  lastRender = now;
  renderedFrames++;

  clock.update(now);
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.getElapsed();

  for (const a of anims) {
    if (now < a.start) continue;
    const k = clamp((now - a.start) / a.dur, 0, 1);
    a.fn(a.curve(k), k);
    if (k >= 1) { anims.delete(a); a.res(); }
  }

  // layers: page ↔ exploded, with a lift arc and an idle float
  const pos = leadGeo.attributes.position;
  panels.forEach((p, i) => {
    const m = p.mix;
    p.obj.position.lerpVectors(p.page, p.expl, m);
    p.obj.position.z += Math.sin(Math.PI * m) * 120;
    if (!REDUCED && activeQuality !== 'eco' && !state.reader) {
      const f = m * p.bob;
      p.obj.position.y += Math.sin(t * 0.55 + p.phase) * 9 * f;
      p.obj.position.x += Math.cos(t * 0.4 + p.phase) * 4 * f;
    }
    p.obj.quaternion.slerpQuaternions(IDQ, p.explQ, m);
    pos.setXYZ(i * 2, p.page.x, p.page.y, 0);
    tmp.copy(p.obj.position);
    pos.setXYZ(i * 2 + 1, tmp.x, tmp.y, tmp.z - 2);
  });
  pos.needsUpdate = true;
  if (activeQuality !== 'eco' || renderedFrames % 3 === 0) leaders.computeLineDistances();
  leadMat.opacity = 0.55 * state.lines;
  nodes.material.opacity = state.lines;

  // world drift. Eco mode keeps the particles static and uses far fewer points.
  if (!REDUCED && !state.calm && !state.reader) {
    dust.forEach((d) => {
      const a = d.geometry.attributes.position;
      const speeds = d.userData.spd;
      if (activeQuality !== 'eco') {
        for (let j = 0; j < speeds.length; j++) {
          let y = a.getY(j) + speeds[j] * dt * 60;
          if (y > 3000) y = -1200;
          a.setY(j, y);
        }
        a.needsUpdate = true;
      }
      d.material.opacity += (d.userData.target * (state.busy ? 0.6 : 1) - d.material.opacity) * 0.025;
    });
    if (activeQuality !== 'eco') {
      world.rotation.y = Math.sin(t * 0.05) * 0.05;
      rings.forEach((r, k) => r.scale.setScalar(1 + Math.sin(t * 0.6 + k) * 0.015));
    }
  } else {
    dust.forEach((d) => (d.material.opacity += ((state.calm || state.reader ? 0.025 : d.userData.target) - d.material.opacity) * .06));
  }

  const gridTarget = state.calm || state.reader ? 0.05 : 0.32;
  grid.material.opacity += (gridTarget - grid.material.opacity) * .06;
  grid2.material.opacity += ((state.calm || state.reader ? 0.02 : 0.18) - grid2.material.opacity) * .06;
  rings.forEach((r, k) => { const target = state.calm || state.reader ? .025 : .28 - k * .07; r.material.opacity += (target - r.material.opacity) * .06; });

  // Conservative automatic downgrade only while preference is Auto.
  if (!state.busy && qualityPreference === 'auto' && activeQuality !== 'eco' && perfFrames < 120) {
    perfFrames++; perfTime += dt;
    if (perfFrames === 120 && perfTime / perfFrames > 0.03) setQuality('auto', true, false);
  }

  if (controls.enabled) controls.update();
  gl?.render(scene, camera);
  css.render(cssScene, camera);
}
requestAnimationFrame(frame);

// ─────────────── intro: parse → scan → explode → swing ───────────────
const log = $('#log');
const meter = $('#meter');
const line = (html) => { log.innerHTML += html + '\n'; };
let skipIntroRequested = false;
$('#skipIntro').addEventListener('click', () => { skipIntroRequested = true; $('#loader').classList.add('done'); });

function routeIndex() {
  const route = decodeURI(location.hash.replace(/^#/, ''));
  return route ? panels.findIndex((p) => p.L.path === route || p.L.id === route) : -1;
}
function finishBoot() {
  document.body.classList.remove('is-loading');
  state.busy = false;
  controls.enabled = !state.reader;
  try { localStorage.setItem(SEEN_KEY, '1'); } catch { /* noop */ }
  const deepIndex = routeIndex();
  if (deepIndex >= 0) setTimeout(() => focusLayer(deepIndex), REDUCED ? 40 : 260);
  else if (APPEARANCE.reader_default) setTimeout(() => toggleReader(true), 80);
  setTimeout(() => hint.classList.add('gone'), 9000);
}
function fastBoot() {
  $('#loader').classList.add('done');
  state.exploded = true;
  state.lines = 1;
  setExplodedClass(true);
  panels.forEach((p) => { p.mix = 1; p.bob = activeQuality === 'eco' ? 0 : 1; });
  const { pos, target } = overviewPose();
  camera.position.copy(pos);
  controls.target.copy(target);
  camera.lookAt(target);
  finishBoot();
}

async function intro() {
  let seen = false;
  try { seen = localStorage.getItem(SEEN_KEY) === '1'; } catch { /* noop */ }
  const deepLinked = routeIndex() >= 0;
  const smartSkip = APPEARANCE.intro === 'skip' || (APPEARANCE.intro === 'smart' && seen);
  if (REDUCED || deepLinked || smartSkip) return fastBoot();

  const fontWait = document.fonts ? Promise.race([document.fonts.ready, wait(2500)]) : Promise.resolve();
  const steps = [
    [`<span class="c">$</span> resume --explode ${RESUME_META.name || 'resume'}`, 10],
    ['<span class="d">  reading 1 page · A4 · vector text</span>', 30],
    [`<span class="d">  extracting text runs, vectors, typefaces</span>`, 52],
    [`<span class="d">  segmenting into ${panels.length} layers</span>`, 74],
    [`<span class="d">  render profile · ${activeQuality}</span>`, 90],
    ['<span class="ok">  ✓ ready</span>', 100],
  ];
  for (const [txt, pct] of steps) {
    line(txt);
    meter.style.width = pct + '%';
    await wait(skipIntroRequested ? 0 : 240);
    if (pct === 74) await fontWait;
  }
  if (skipIntroRequested) return fastBoot();
  await wait(220);
  $('#loader').classList.add('done');

  const pp = pagePose();
  camera.position.set(0, -120, pp.pos.z * 1.6);
  controls.target.set(0, 0, 0);
  camera.lookAt(0, 0, 0);
  await fly(pp.pos, pp.target, 1150, 0);

  if (!REDUCED && activeQuality !== 'eco') { scanEl.classList.add('run'); await wait(1250); }

  explode(true, { stagger: activeQuality === 'eco' ? 25 : 70, dur: activeQuality === 'eco' ? 900 : 1650 });
  await wait(activeQuality === 'eco' ? 80 : 300);
  const { pos, target } = overviewPose();
  await fly(pos, target, activeQuality === 'eco' ? 1100 : 2200, activeQuality === 'eco' ? 80 : 230);
  finishBoot();
}
intro();
