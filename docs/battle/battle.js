// Robot Battle: a real-time duel against three bots, in order.
// The fight runs at a fixed 60 ticks a second and every enemy follows a fixed script, so the same
// inputs always give the same fight and the rhythm can be learned. Heavy moves are telegraphed
// by a wind-up (eye glow and pose) long enough to react to.
import * as THREE from '../vendor/three.module.min.js';

const $ = (id) => document.getElementById(id);
const HZ = 60;
const C = { void: 0x030d05, omni: 0x3dfa46, cyan: 0x7ffcd5, hazard: 0xffb300, red: 0xff4d5e, core: 0xeafff0, line: 0x1f7a2c, hot: 0xff2030, white: 0xffffff };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };

// ------------------------------------------------------------------ rules (all times in ticks)
const PLAYER_HP = 100, EMAX = 3, ROUND = 60 * HZ, HOME = 1.3;
const ATK = { start: 7, rec: 17, dmg: 6 };
const CHG = 34;
const OD = { start: 14, rec: 28, dmg: 30, cost: 2 };
const PARRY = 10, HITSTUN = 18, RECOIL = 18, BUFFER = 9, PARRY_STUN = 44, OD_STUN = 64;
const MOVES = {
  J: { name: 'JAB', wind: 26, rec: 22, dmg: 8, block: 0, lunge: 0.55 },
  H: { name: 'HEAVY HIT', wind: 64, rec: 36, dmg: 22, block: 5, lunge: 0.85, heavy: true },
  K: { name: 'CRUSHER', wind: 92, rec: 46, dmg: 40, block: 20, heavy: true, beam: true, noParry: true },
  G: { name: 'GUARD', len: 90 },
  R: { name: 'VENTING', len: 100 },
};
const STAGES = [
  { name: 'SCRAP ROVER', hp: 90, col: 0xffb300, css: '#ffb300', build: buildRover,
    hint: 'Red eye and raised claw: a heavy hit. Hold SHIELD. Steam: it is venting, hit it for double damage.',
    tip: 'Shield when its eye turns red, and punch while it steams. Tap SHIELD just before the hit for a parry.',
    phases: [{ at: 1, speed: 1, script: 'W40 J W30 H R' }] },
  { name: 'HEAVY MECH', hp: 120, col: 0xff8a3d, css: '#ff8a3d', build: buildMech,
    hint: 'Plates up: a guard, attacks bounce off. CHARGE instead, or break the guard with OVERDRIVE.',
    tip: 'Do not punch the plates. Charge while it guards, then spend the energy on an overdrive.',
    phases: [{ at: 1, speed: 1, script: 'W30 G W16 H W10 H W26 J R' }] },
  { name: 'OMEGA CORE', hp: 150, col: 0xff4d5e, css: '#ff4d5e', build: buildCore,
    hint: 'White ring: the crusher. A shield only takes half. An OVERDRIVE during the ring stops it cold.',
    tip: 'Save 2 energy for every white ring. It speeds up at 60% and again at 25% health.',
    phases: [{ at: 1, speed: 1, script: 'W30 J W20 G W16 K W24 H R' },
      { at: 0.6, speed: 1.2, name: 'PHASE 2', script: 'G J W12 J W20 K H R' },
      { at: 0.25, speed: 1.35, name: 'PHASE 3', script: 'K W16 J H W10 K R' }] },
];
for (const s of STAGES) for (const ph of s.phases) ph.items = ph.script.split(' ').map((w) => (w[0] === 'W' ? { m: 'W', len: +w.slice(1) } : { m: w }));

// ------------------------------------------------------------------ renderer and arena
const canvas = $('scene'), stageEl = $('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(C.void);
const scene = new THREE.Scene();
scene.fog = new THREE.Fog(C.void, 7, 17);
const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 60);
scene.add(new THREE.HemisphereLight(0xcfffe0, 0x04140a, 1.4));
const sun = new THREE.DirectionalLight(0xffffff, 2.0); sun.position.set(1.5, 4, 3); scene.add(sun);
const rim = new THREE.DirectionalLight(C.omni, 1.2); rim.position.set(-2, 1.5, -3); scene.add(rim);
const eyeLight = new THREE.PointLight(C.hazard, 2, 4, 2); scene.add(eyeLight);
const coreLight = new THREE.PointLight(C.cyan, 1, 3, 2); scene.add(coreLight);

let lineList = [];
const lineMat = (color, opacity = 1) => { const m = new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }); m.userData.base = new THREE.Color(color); lineList.push(m); return m; };
function edged(mesh, color, opacity = 0.6) { mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry, 25), lineMat(color, opacity))); return mesh; }
const std = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.6, ...o });
const glow = (color, i = 1.6) => new THREE.MeshStandardMaterial({ color: 0x000000, emissive: color, emissiveIntensity: i });
const add = (parent, mesh, x = 0, y = 0, z = 0) => { mesh.position.set(x, y, z); parent.add(mesh); return mesh; };
const box = (w, h, d, mat, edge) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); return edge == null ? m : edged(m, edge); };
const cyl = (rt, rb, h, mat, edge, seg = 20) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), mat); return edge == null ? m : edged(m, edge, 0.4); };
const sph = (r, mat) => new THREE.Mesh(new THREE.SphereGeometry(r, 20, 14), mat);

(function buildArena() {
  const lines = lineList; lineList = [];
  const disc = edged(new THREE.Mesh(new THREE.CylinderGeometry(3.4, 3.55, 0.18, 6), std(0x0a2411, { roughness: 0.85, metalness: 0.1 })), C.omni, 0.9);
  disc.rotation.y = Math.PI / 6; disc.position.y = -0.09; scene.add(disc);
  const pts = [];
  for (const r of [0.9, 1.8, 2.7]) for (let i = 0; i < 72; i += 2) {
    const a = (i / 72) * Math.PI * 2, b = ((i + 1) / 72) * Math.PI * 2;
    pts.push(Math.cos(a) * r, 0.003, Math.sin(a) * r, Math.cos(b) * r, 0.003, Math.sin(b) * r);
  }
  for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; pts.push(Math.cos(a) * 0.9, 0.003, Math.sin(a) * 0.9, Math.cos(a) * 2.95, 0.003, Math.sin(a) * 2.95); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  scene.add(new THREE.LineSegments(g, lineMat(C.line, 0.55)));
  for (const x of [-HOME, HOME]) {                       // start pads
    const pad = new THREE.Mesh(new THREE.RingGeometry(0.42, 0.5, 6), new THREE.MeshBasicMaterial({ color: x < 0 ? C.omni : C.hazard, transparent: true, opacity: 0.5, side: THREE.DoubleSide }));
    pad.rotation.x = -Math.PI / 2; pad.position.set(x, 0.004, 0); scene.add(pad);
    if (x > 0) scene.userData.foePad = pad;
  }
  const floor = new THREE.GridHelper(40, 40, C.line, 0x0c2a14); floor.position.y = -1.2;
  floor.material.transparent = true; floor.material.opacity = 0.5; scene.add(floor);
  const pm = glow(C.omni, 1.2), pd = std(0x0a2010);
  for (let i = 0; i < 14; i++) {                          // a ring of light pylons for depth
    const a = Math.PI * 0.08 + (i / 14) * Math.PI * 2, r = 7.5;
    const x = Math.cos(a) * r, z = Math.sin(a) * r - 1.5;
    if (z > 3) continue;
    add(scene, box(0.22, 3.2, 0.22, pd, C.line), x, 0.4, z);
    add(scene, box(0.24, 0.12, 0.24, pm), x, 2.05, z);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(5.2, 0.03, 6, 120), new THREE.MeshBasicMaterial({ color: C.omni, transparent: true, opacity: 0.22 }));
  ring.position.set(0, 2.2, -7); scene.add(ring);
  const ring2 = new THREE.Mesh(new THREE.TorusGeometry(4.5, 0.015, 6, 120), new THREE.MeshBasicMaterial({ color: C.cyan, transparent: true, opacity: 0.18 }));
  ring2.position.set(0, 2.2, -7); scene.add(ring2);
  lineList = lines;
})();

const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.6, depthWrite: false });
function blob(r) { const m = new THREE.Mesh(new THREE.CircleGeometry(r, 28), shadowMat); m.rotation.x = -Math.PI / 2; m.position.y = 0.006; scene.add(m); return m; }

// ------------------------------------------------------------------ robots (built facing +x; the enemy is turned around)
function buildPlayer() {
  lineList = [];
  const plate = std(0x173a20), dark = std(0x0b1a10, { roughness: 0.35, metalness: 0.7 });
  const vis = glow(C.cyan, 2.2), g = glow(C.omni, 1.6), coreMat = glow(C.cyan, 1.5);
  const root = new THREE.Group(), body = new THREE.Group(); root.add(body);
  for (const z of [-0.17, 0.17]) {
    add(body, box(0.2, 0.44, 0.2, plate, C.omni), 0, 0.32, z);
    add(body, box(0.34, 0.1, 0.24, dark, C.omni), 0.05, 0.05, z);
    add(body, box(0.1, 0.07, 0.21, g), 0.06, 0.5, z);
  }
  add(body, box(0.42, 0.16, 0.52, dark, C.omni), 0, 0.62, 0);
  const torso = add(body, new THREE.Group(), 0, 0.68, 0);
  add(torso, box(0.5, 0.5, 0.6, plate, C.omni), 0, 0.27, 0);
  add(torso, box(0.08, 0.36, 0.46, dark, C.omni), -0.27, 0.3, 0);                    // back pack
  add(torso, box(0.46, 0.12, 0.74, dark, C.omni), 0, 0.56, 0);
  const core = add(torso, new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.05, 6), coreMat), 0.26, 0.3, 0); core.rotation.z = Math.PI / 2;
  const head = add(torso, new THREE.Group(), 0.02, 0.74, 0);
  add(head, box(0.3, 0.22, 0.3, plate, C.omni), 0, 0, 0);
  add(head, box(0.04, 0.07, 0.25, vis), 0.155, 0.02, 0);
  add(head, box(0.02, 0.18, 0.02, dark), -0.08, 0.18, 0.1);
  add(head, sph(0.025, g), -0.08, 0.28, 0.1);
  const arm = (z) => {
    const p = add(torso, new THREE.Group(), 0, 0.52, z);
    add(p, box(0.15, 0.14, 0.15, dark, C.omni), 0, 0, 0);
    add(p, box(0.13, 0.28, 0.13, plate, C.omni), 0, -0.2, 0);
    add(p, box(0.15, 0.24, 0.15, plate, C.omni), 0, -0.44, 0);
    return p;
  };
  const armR = arm(0.43), armL = arm(-0.43);
  const fist = add(armR, box(0.2, 0.16, 0.2, dark, C.omni), 0, -0.62, 0);
  add(fist, box(0.21, 0.04, 0.21, g), 0, -0.05, 0);
  const emitter = add(armL, new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, 0.05, 6), vis), 0, -0.6, 0);
  const shieldMat = new THREE.MeshBasicMaterial({ color: C.cyan, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending });
  const shield = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 0.8, 1.45, 12, 1, true, Math.PI / 2 - 0.75, 1.5), shieldMat);
  const shieldLines = new THREE.LineSegments(new THREE.EdgesGeometry(shield.geometry, 1), new THREE.LineBasicMaterial({ color: C.cyan, transparent: true, opacity: 0 }));
  shield.add(shieldLines); add(root, shield, -0.1, 0.9, 0);
  const lines = lineList; lineList = [];
  return { root, body, torso, head, armR, armL, fist, emitter, core, coreMat, shield, shieldMat, shieldLines, lines, shadow: blob(0.42) };
}

function foeMats(col) { return { plate: std(0x2a1a0c, { color: new THREE.Color(col).multiplyScalar(0.16) }), dark: std(0x120a06), eye: glow(col, 1.5), g: glow(col, 1.2) }; }

function buildRover(col) {
  lineList = [];
  const m = foeMats(col), root = new THREE.Group(), body = new THREE.Group(); root.add(body);
  add(body, box(0.95, 0.26, 0.66, m.plate, col), 0, 0.36, 0);
  for (const x of [-0.3, 0.3]) for (const z of [-0.37, 0.37]) {
    const w = add(body, cyl(0.17, 0.17, 0.11, m.dark, col, 14), x, 0.18, z); w.rotation.x = Math.PI / 2;
    add(w, new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.12, 6), m.g));
  }
  add(body, box(0.5, 0.3, 0.5, m.plate, col), -0.1, 0.64, 0);
  for (const z of [-0.14, 0.14]) add(body, cyl(0.05, 0.06, 0.3, m.dark, col, 8), -0.32, 0.92, z);
  add(body, cyl(0.035, 0.035, 0.36, m.dark, null, 8), 0, 0.96, 0);
  const head = add(body, new THREE.Group(), 0.02, 1.18, 0);
  add(head, box(0.36, 0.24, 0.32, m.plate, col), 0, 0, 0);
  const eye = add(head, sph(0.085, m.eye), 0.19, 0, 0);
  const lid = add(head, new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.018, 6, 20), m.dark), 0.19, 0, 0); lid.rotation.y = Math.PI / 2;
  add(head, box(0.015, 0.25, 0.015, m.dark), -0.1, 0.24, 0.08);
  add(head, sph(0.03, m.g), -0.1, 0.37, 0.08);
  const arm = add(body, new THREE.Group(), 0.24, 0.68, -0.38);   // local -z faces the camera once turned
  add(arm, box(0.1, 0.4, 0.1, m.plate, col), 0, -0.2, 0);
  const claw = add(arm, new THREE.Group(), 0, -0.42, 0);
  add(claw, box(0.16, 0.08, 0.14, m.dark, col), 0, 0, 0);
  for (const s of [-1, 1]) { const p = add(claw, box(0.04, 0.2, 0.04, m.g), s * 0.05, -0.12, 0); p.rotation.z = s * 0.35; }
  const lines = lineList; lineList = [];
  return { root, body, head, eye, eyeMat: m.eye, arm, armRest: 1.0, plates: [], vents: [new THREE.Vector3(-0.32, 1.1, -0.14), new THREE.Vector3(-0.32, 1.1, 0.14)], lines, eyeY: 1.18, chestY: 0.6, shadow: blob(0.6) };
}

function buildMech(col) {
  lineList = [];
  const m = foeMats(col), root = new THREE.Group(), body = new THREE.Group(); root.add(body);
  for (const z of [-0.26, 0.26]) {
    add(body, box(0.3, 0.62, 0.3, m.plate, col), 0, 0.36, z);
    add(body, box(0.46, 0.12, 0.34, m.dark, col), 0.06, 0.06, z);
    add(body, box(0.12, 0.1, 0.32, m.g), 0.1, 0.55, z);
  }
  add(body, box(0.82, 0.74, 0.9, m.plate, col), 0, 1.06, 0);
  for (let i = 0; i < 3; i++) add(body, box(0.02, 0.04, 0.5, m.g), 0.42, 0.9 + i * 0.1, 0);
  for (const z of [-0.25, 0.25]) add(body, cyl(0.07, 0.09, 0.34, m.dark, col, 8), -0.46, 1.38, z);
  const head = add(body, new THREE.Group(), 0.12, 1.56, 0);
  add(head, box(0.32, 0.2, 0.34, m.plate, col), 0, 0, 0);
  add(head, box(0.03, 0.05, 0.26, m.g), 0.165, 0, 0);
  const eye = add(head, sph(0.07, m.eye), 0.17, 0, 0);
  const mkArm = (z) => {
    const p = add(body, new THREE.Group(), 0.02, 1.3, z);
    add(p, box(0.22, 0.42, 0.22, m.plate, col), 0, -0.2, 0);
    const f = add(p, box(0.34, 0.32, 0.34, m.dark, col), 0, -0.56, 0);
    add(f, box(0.35, 0.05, 0.35, m.g), 0, 0.08, 0);
    return p;
  };
  const arm = mkArm(-0.58), arm2 = mkArm(0.58);
  const plates = [-1, 1].map((s) => {
    const pl = add(body, box(0.08, 0.66, 0.42, m.plate, C.cyan), 0, 1.58, s * 0.36);
    pl.userData.s = s; return pl;
  });
  const lines = lineList; lineList = [];
  return { root, body, head, eye, eyeMat: m.eye, arm, arm2, armRest: 0.25, plates, vents: [new THREE.Vector3(-0.46, 1.58, -0.25), new THREE.Vector3(-0.46, 1.58, 0.25)], lines, eyeY: 1.56, chestY: 1.05, shadow: blob(0.75) };
}

function buildCore(col) {
  lineList = [];
  const m = foeMats(col), root = new THREE.Group(), body = new THREE.Group(); root.add(body);
  const hover = add(body, new THREE.Group(), 0, 1.3, 0);
  add(hover, edged(new THREE.Mesh(new THREE.IcosahedronGeometry(0.44, 0), m.plate), col, 0.9));
  const inner = add(hover, new THREE.Mesh(new THREE.IcosahedronGeometry(0.3, 1), glow(col, 0.5)));
  const eye = add(hover, sph(0.12, m.eye), 0.38, 0.02, 0);
  const rings = [0, 1].map((i) => { const r = add(hover, new THREE.Mesh(new THREE.TorusGeometry(0.68 + i * 0.12, 0.022, 6, 72), m.g)); r.rotation.x = i ? 1.1 : -0.5; return r; });
  const spikes = [];
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2 + Math.PI / 4, g = add(hover, new THREE.Group());
    g.rotation.x = a;
    const s = add(g, edged(new THREE.Mesh(new THREE.ConeGeometry(0.08, 0.36, 4), m.dark), col, 0.8), 0, 0.62, 0);
    s.userData.base = 0.62; spikes.push(s);
  }
  const guardMat = new THREE.MeshBasicMaterial({ color: C.cyan, transparent: true, opacity: 0, wireframe: true, depthWrite: false, blending: THREE.AdditiveBlending });
  const guard = add(hover, new THREE.Mesh(new THREE.IcosahedronGeometry(0.98, 1), guardMat));
  const pylon = add(body, cyl(0.3, 0.45, 0.12, m.dark, col, 6), 0, 0.06, 0);
  add(pylon, new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.14, 6), m.g));
  const lines = lineList; lineList = [];
  return { root, body, hover, inner, head: hover, eye, eyeMat: m.eye, rings, spikes, guard, guardMat, arm: null, armRest: 0, plates: [], vents: [new THREE.Vector3(0, 1.8, 0), new THREE.Vector3(-0.3, 1.7, 0.2)], lines, eyeY: 1.3, chestY: 1.3, shadow: blob(0.55), core: true };
}

const player = buildPlayer(); scene.add(player.root); player.root.position.x = -HOME;
let foe = null;
function setFoe(i) {
  if (foe) { scene.remove(foe.root); scene.remove(foe.shadow); }
  const s = STAGES[i];
  foe = s.build(s.col); foe.root.rotation.y = Math.PI; foe.root.position.x = HOME; scene.add(foe.root);
  scene.userData.foePad.material.color.setHex(s.col);
  document.documentElement.style.setProperty('--foe', s.css);
}

// effects: telegraph ring, beams, particles
const crushRing = new THREE.Mesh(new THREE.TorusGeometry(1, 0.035, 6, 64), new THREE.MeshBasicMaterial({ color: C.white, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }));
crushRing.rotation.y = Math.PI / 2; scene.add(crushRing);
function beam(color) {
  const g = new THREE.Group();
  const outer = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 1, 14, 1, true), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
  const inner = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 1, 10), new THREE.MeshBasicMaterial({ color: C.white, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }));
  g.add(outer, inner); g.rotation.z = Math.PI / 2; g.visible = false; scene.add(g);
  return { g, outer, inner };
}
const odBeam = beam(C.cyan), crushBeam = beam(C.hot);
function showBeam(b, x0, x1, y, w, a) {
  b.g.visible = a > 0.01; b.g.position.set((x0 + x1) / 2, y, 0); b.g.scale.set(w, Math.abs(x1 - x0), w);
  b.outer.material.opacity = 0.55 * a; b.inner.material.opacity = a;
}
const chargeRing = new THREE.Mesh(new THREE.TorusGeometry(0.7, 0.025, 6, 48), new THREE.MeshBasicMaterial({ color: C.cyan, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }));
chargeRing.rotation.x = Math.PI / 2; scene.add(chargeRing);

let seed = 1;
function rand() { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
const NP = 420;
const pPos = new Float32Array(NP * 3), pCol = new Float32Array(NP * 3), parts = Array.from({ length: NP }, () => ({ life: 0 }));
const pGeo = new THREE.BufferGeometry();
pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3)); pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 3));
const pMat = new THREE.PointsMaterial({ size: 0.075, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true });
const points = new THREE.Points(pGeo, pMat); points.frustumCulled = false; scene.add(points);
let pNext = 0;
const _c = new THREE.Color();
function emit(x, y, z, n, color, speed, opt = {}) {
  _c.setHex(color);
  for (let i = 0; i < n; i++) {
    const p = parts[pNext]; pNext = (pNext + 1) % NP;
    const a = rand() * Math.PI * 2, b = (rand() - 0.5) * Math.PI, s = speed * (0.4 + rand() * 0.8);
    p.x = x; p.y = y; p.z = z;
    p.vx = Math.cos(a) * Math.cos(b) * s + (opt.dx || 0); p.vy = Math.sin(b) * s + (opt.up || 0); p.vz = Math.sin(a) * Math.cos(b) * s * 0.6;
    p.life = p.max = (opt.life || 0.45) * (0.6 + rand() * 0.6); p.g = opt.g ?? 6; p.r = _c.r; p.gg = _c.g; p.b = _c.b; p.drag = opt.drag || 0;
  }
}
function stepParticles(dt) {
  for (let i = 0; i < NP; i++) {
    const p = parts[i];
    if (p.life > 0) {
      p.life -= dt; p.vy -= p.g * dt; const d = 1 - p.drag * dt; p.vx *= d; p.vy *= d; p.vz *= d;
      p.x += p.vx * dt; p.y += p.vy * dt; p.z += p.vz * dt;
      if (p.y < 0.01) { p.y = 0.01; p.vy *= -0.35; }
    }
    const k = p.life > 0 ? p.life / p.max : 0;
    pPos[i * 3] = p.x || 0; pPos[i * 3 + 1] = k ? p.y : -50; pPos[i * 3 + 2] = p.z || 0;
    pCol[i * 3] = (p.r || 0) * k; pCol[i * 3 + 1] = (p.gg || 0) * k; pCol[i * 3 + 2] = (p.b || 0) * k;
  }
  pGeo.attributes.position.needsUpdate = true; pGeo.attributes.color.needsUpdate = true;
}

// ------------------------------------------------------------------ sound (synthesised, no files)
const store = { get: (k, d) => { try { return JSON.parse(localStorage.getItem('rb.' + k)) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem('rb.' + k, JSON.stringify(v)); } catch { /* private mode */ } } };
let muted = store.get('muted', false), ac = null, noiseBuf = null;
function audioOn() { if (!ac) { try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch { ac = null; } } if (ac && ac.state === 'suspended') ac.resume(); }
function beep(f, d, type = 'square', v = 0.05, f2 = 0, when = 0) {
  if (muted || !ac || ac.state !== 'running') return;
  const t = ac.currentTime + when, o = ac.createOscillator(), g = ac.createGain();
  o.type = type; o.frequency.setValueAtTime(f, t); if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + d);
  g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
  o.connect(g).connect(ac.destination); o.start(t); o.stop(t + d + 0.03);
}
function noise(d, v = 0.12, f = 1200, when = 0) {
  if (muted || !ac || ac.state !== 'running') return;
  if (!noiseBuf) { noiseBuf = ac.createBuffer(1, ac.sampleRate * 0.5, ac.sampleRate); const ch = noiseBuf.getChannelData(0); for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1; }
  const t = ac.currentTime + when, s = ac.createBufferSource(), fl = ac.createBiquadFilter(), g = ac.createGain();
  s.buffer = noiseBuf; fl.type = 'lowpass'; fl.frequency.value = f; g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
  s.connect(fl).connect(g).connect(ac.destination); s.start(t); s.stop(t + d + 0.02);
}
function sfx(n) {
  if (n === 'swing') beep(320, 0.06, 'triangle', 0.05, 180);
  else if (n === 'hit') { noise(0.12, 0.16, 2400); beep(180, 0.1, 'square', 0.05, 70); }
  else if (n === 'crit') { noise(0.2, 0.2, 3000); beep(140, 0.18, 'sawtooth', 0.06, 50); }
  else if (n === 'hurt') { noise(0.2, 0.2, 900); beep(110, 0.22, 'sawtooth', 0.07, 45); }
  else if (n === 'block') { beep(1400, 0.05, 'square', 0.04, 900); noise(0.06, 0.06, 5000); }
  else if (n === 'clank') { beep(700, 0.08, 'square', 0.05, 500); beep(1050, 0.06, 'square', 0.03, 0, 0.02); }
  else if (n === 'parry') [1320, 1760, 2640].forEach((f, i) => beep(f, 0.1, 'square', 0.04, 0, i * 0.04));
  else if (n === 'charge') beep(300, 0.5, 'sine', 0.06, 900);
  else if (n === 'full') beep(1200, 0.08, 'triangle', 0.06);
  else if (n === 'od') { beep(200, 0.45, 'sawtooth', 0.06, 1600); noise(0.4, 0.1, 6000, 0.1); }
  else if (n === 'tell') beep(90, 0.3, 'sawtooth', 0.05, 160);
  else if (n === 'crushtell') { beep(60, 0.9, 'sawtooth', 0.05, 240); beep(1800, 0.08, 'square', 0.02, 0, 0.1); }
  else if (n === 'jabtell') beep(520, 0.05, 'square', 0.025);
  else if (n === 'deny') beep(160, 0.12, 'square', 0.04, 120);
  else if (n === 'count') beep(660, 0.08, 'square', 0.04);
  else if (n === 'go') beep(990, 0.25, 'square', 0.05, 1320);
  else if (n === 'phase') { beep(80, 0.8, 'sawtooth', 0.07, 40); noise(0.7, 0.12, 700); }
  else if (n === 'ko') { noise(0.8, 0.25, 1600); beep(220, 0.8, 'sawtooth', 0.06, 40); }
  else if (n === 'win') [523, 659, 784, 1047, 1319].forEach((f, i) => beep(f, 0.16, 'square', 0.05, 0, i * 0.09));
  else if (n === 'lose') { beep(300, 0.3, 'sawtooth', 0.05, 140); beep(200, 0.4, 'sawtooth', 0.05, 80, 0.25); }
  else if (n === 'ui') beep(990, 0.03, 'square', 0.03);
}

// ------------------------------------------------------------------ game state
const G = { state: 'boot', stage: 0, clock: 0, t: 0, fight: 0, hitstop: 0, shake: 0, flash: 0, scores: [null, null, null], result: null };
const P = {}, E = {};
const input = { buf: null, bufT: 0, shield: false, keys: new Set(), padHold: new Set() };
const best = () => store.get('best', 0);

function resetFighters() {
  Object.assign(P, { hp: PLAYER_HP, shown: PLAYER_HP, en: 0, act: null, t: 0, shield: false, onset: -99, x: -HOME, flash: 0, sflash: 0, parries: 0, dealt: 0, taken: 0, ko: 0 });
  const s = STAGES[G.stage];
  Object.assign(E, { hp: s.hp, max: s.hp, shown: s.hp, phase: 0, idx: -1, move: 'W', part: 'hold', t: 0, len: 30, wind: 0, rec: 0, stun: 0, trans: 0, flash: 0, lunge: 0, broken: false, ko: 0, tellShown: false, strikeT: -99 });
  nextMove(true);
}
function phaseOf() { return STAGES[G.stage].phases[E.phase]; }
function nextMove(first) {
  const ph = phaseOf(), sp = ph.speed;
  E.idx = first ? 0 : (E.idx + 1) % ph.items.length;
  const it = ph.items[E.idx], mv = MOVES[it.m];
  E.move = it.m; E.t = 0; E.broken = false; E.tellShown = false;
  if (it.m === 'W') { E.part = 'hold'; E.len = Math.round(it.len / sp); }
  else if (mv.len) { E.part = 'hold'; E.len = Math.round(mv.len / sp); }
  else { E.part = 'wind'; E.wind = Math.round(mv.wind / sp); E.rec = Math.round(mv.rec / sp); E.len = E.wind + E.rec; }
}
function startStage(i) {
  G.stage = i; setFoe(i); resetFighters();
  G.state = 'intro'; G.t = 0; G.fight = 0; G.result = null;
  input.buf = null; hideCard(); renderStatic();
}

// ------------------------------------------------------------------ fight logic, one tick
function press(a) {
  if (a === 'shd') return;
  if (G.state !== 'fight') return;
  input.buf = a; input.bufT = BUFFER;
}
const enemyGuarding = () => (E.move === 'G' && !E.broken && E.part === 'hold' && E.t >= 6 && !E.stun);
const enemyVenting = () => E.move === 'R' && !E.stun;
const shieldUp = () => input.shield;

function damageFoe(n, kind) {
  n = Math.min(n, E.hp); E.hp -= n; P.dealt += n; E.flash = 1;
  const y = foe.chestY + 0.15;
  floater(HOME - 0.2, y + 0.5, `-${n}`, kind === 'od' ? 'cy big' : kind === 'crit' ? 'amb big' : 'om', kind === 'od' ? 1.2 : 1);
  emit(HOME - 0.35, y, 0.15, kind === 'od' ? 46 : kind === 'crit' ? 30 : 18, kind === 'od' ? C.cyan : kind === 'crit' ? C.hazard : C.omni, kind === 'od' ? 5 : 3.6, { dx: 1.2 });
  emit(HOME - 0.35, y, 0.15, 8, C.white, 4.5, { dx: 1.5, life: 0.25 });
  G.shake = Math.max(G.shake, kind === 'od' ? 0.9 : kind === 'crit' ? 0.5 : 0.28);
  G.hitstop = Math.max(G.hitstop, kind === 'od' ? 6 : kind === 'crit' ? 4 : 2);
  sfx(kind === 'od' || kind === 'crit' ? 'crit' : 'hit');
  const ph = STAGES[G.stage].phases, nx = ph[E.phase + 1];
  if (E.hp > 0 && nx && E.hp <= Math.round(E.max * nx.at)) {      // boss phase change: a short invulnerable roar, then a new rhythm
    E.phase++; E.trans = 80; E.stun = 0; E.move = 'W'; E.part = 'hold'; E.t = 0; E.len = 80; E.idx = -1;
    banner(nx.name, E.phase === 1 ? 'IT SPEEDS UP' : 'LAST STAND'); sfx('phase'); G.shake = 1;
  }
  if (E.hp <= 0) endFight(P.hp === PLAYER_HP ? 'flawless' : 'win');
}
function hurtPlayer(n, kind) {
  n = Math.min(n, P.hp); P.hp -= n; P.taken += n;
  if (n > 0) {
    P.flash = 1; G.flash = Math.max(G.flash, 0.6);
    floater(-HOME + 0.1, 2.1, `-${n}`, 'rd' + (n >= 20 ? ' big' : ''), 1);
    emit(-HOME + 0.3, 1.0, 0.15, n >= 20 ? 34 : 18, C.hot, 3.6, { dx: -1.2 });
    G.shake = Math.max(G.shake, n >= 30 ? 1 : n >= 15 ? 0.7 : 0.35); G.hitstop = Math.max(G.hitstop, n >= 20 ? 6 : 3);
    sfx('hurt');
  }
  if (P.hp <= 0) endFight('lose');
}

function playerTick() {
  if (input.bufT > 0 && --input.bufT === 0) input.buf = null;
  if (P.act) {
    P.t++;
    if (P.act === 'atk') {
      if (P.t === ATK.start) {
        if (E.trans) floater(HOME - 0.2, foe.chestY + 0.6, 'IMMUNE', 'dim small', 1);
        else if (enemyGuarding()) {
          floater(HOME - 0.3, foe.chestY + 0.6, 'BLOCKED', 'cy', 1); emit(HOME - 0.5, foe.chestY + 0.2, 0.15, 12, C.cyan, 3, { dx: -1 }); sfx('clank');
          P.act = 'recoil'; P.t = 0; G.shake = Math.max(G.shake, 0.2);
        } else {
          const crit = enemyVenting() ? 2 : E.stun ? 1.5 : 1;
          damageFoe(Math.round(ATK.dmg * crit), crit > 1 ? 'crit' : 'hit');
        }
      } else if (P.t >= ATK.start + ATK.rec) P.act = null;
    } else if (P.act === 'chg') {
      if (P.t % 6 === 0) emit(-HOME, 0.2, 0, 4, C.cyan, 0.8, { up: 2.4, g: -1, life: 0.6 });
      if (P.t >= CHG) { P.en = Math.min(EMAX, P.en + 1); P.act = null; floater(-HOME, 2.0, '+1 ENERGY', 'cy small', 1); sfx('full'); }
    } else if (P.act === 'od') {
      if (P.t === OD.start) {
        const y = foe.chestY;
        emit(HOME - 0.3, y, 0, 40, C.cyan, 5, { dx: 1 });
        if (E.trans) floater(HOME - 0.2, y + 0.6, 'IMMUNE', 'dim small', 1);
        else {
          let dmg = OD.dmg, note = null;
          if (enemyGuarding()) { E.broken = true; E.stun = OD_STUN; dmg = 20; note = 'GUARD BROKEN'; }
          else if (E.part === 'wind' && (E.move === 'H' || E.move === 'K' || E.move === 'J')) { E.stun = OD_STUN; note = E.move === 'K' ? 'CRUSHER STOPPED' : 'STOPPED'; }
          else if (enemyVenting()) dmg = 45;
          if (note) floater(HOME - 0.2, y + 1.0, note, 'cy', 1.4);
          damageFoe(dmg, 'od');
        }
      } else if (P.t >= OD.start + OD.rec) P.act = null;
    } else if (P.act === 'hit') { if (P.t >= HITSTUN) P.act = null; }
    else if (P.act === 'recoil') { if (P.t >= RECOIL) P.act = null; }
  }
  if (!P.act && input.buf) {
    const a = input.buf;
    if (a === 'od' && P.en < OD.cost) { input.buf = null; floater(-HOME, 2.0, 'NEED 2 ENERGY', 'dim small', 1); sfx('deny'); }
    else if (a === 'chg' && P.en >= EMAX) { input.buf = null; floater(-HOME, 2.0, 'ENERGY FULL', 'dim small', 1); sfx('deny'); }
    else {
      input.buf = null; P.act = a; P.t = 0;
      if (a === 'atk') sfx('swing'); else if (a === 'chg') sfx('charge'); else if (a === 'od') { P.en -= OD.cost; sfx('od'); }
    }
  }
  const up = !P.act && shieldUp();
  if (up && !P.shield) P.onset = G.fight;
  P.shield = up;
}

function enemyTick() {
  if (E.stun > 0) { if (--E.stun === 0) nextMove(); return; }
  if (E.trans > 0) { if (--E.trans === 0) nextMove(true); return; }
  E.t++;
  const mv = MOVES[E.move];
  if (E.part === 'wind') {
    if (E.t === 1) sfx(E.move === 'K' ? 'crushtell' : E.move === 'H' ? 'tell' : 'jabtell');
    if (E.t >= E.wind) { E.part = 'rec'; strike(mv); }
  } else if (E.part === 'rec') {
    if (E.t >= E.len) nextMove();
  } else {
    if (E.move === 'R' && E.t % 3 === 0) for (const v of foe.vents) { const w = foe.root.localToWorld(v.clone()); emit(w.x, w.y, w.z, 1, 0x8fd09a, 0.25, { up: 1.3, g: -0.6, life: 1.1, drag: 0.6 }); }
    if (E.move === 'G' && E.t === 6) sfx('clank');
    if (E.t >= E.len) nextMove();
  }
}
function strike(mv) {
  E.strikeT = G.fight;
  if (P.act === 'od' && P.t < OD.start) { floater(-HOME + 0.1, 2.1, 'EVADED', 'cy small', 1); return; }
  if (P.shield) {
    const parry = !mv.noParry && G.fight - P.onset <= PARRY;
    P.sflash = 1;
    if (parry) {
      P.parries++; P.en = Math.min(EMAX, P.en + 0.5); E.stun = PARRY_STUN; E.part = 'rec';
      floater(-HOME + 0.6, 2.2, 'PARRY', 'cy big', 1.3); emit(-HOME + 0.75, 1.0, 0.1, 30, C.white, 4, { dx: 0.5 });
      G.flash = Math.max(G.flash, 0.5); G.flashCy = true; G.hitstop = 6; G.shake = Math.max(G.shake, 0.3); sfx('parry');
      return;
    }
    emit(-HOME + 0.75, 1.0, 0.1, mv.heavy ? 22 : 10, C.cyan, 3, { dx: -0.5 }); sfx('block');
    if (mv.block) { floater(-HOME + 0.6, 2.1, `-${mv.block}`, 'cy', 1); hurtPlayer(mv.block, 'block'); } else floater(-HOME + 0.6, 2.1, 'BLOCKED', 'cy', 1);
    G.shake = Math.max(G.shake, mv.heavy ? 0.45 : 0.15);
    return;
  }
  if (P.act === 'chg') floater(-HOME, 2.5, 'CHARGE LOST', 'dim small', 1);
  P.act = 'hit'; P.t = 0;
  hurtPlayer(mv.dmg, mv.heavy ? 'heavy' : 'jab');
}

function endFight(kind) {
  if (G.state !== 'fight') return;
  G.state = 'ko'; G.t = 0; G.result = kind;
  if (kind === 'win' || kind === 'flawless') { E.ko = 1; sfx('ko'); banner(kind === 'flawless' ? 'FLAWLESS' : 'K.O.', ''); }
  else if (kind === 'lose') { P.ko = 1; sfx('ko'); banner('SYSTEM DOWN', ''); }
  else { sfx('lose'); banner('TIME UP', 'REACTOR OVERHEAT'); }
  input.buf = null;
}

function stageScore() {
  const left = Math.ceil((ROUND - G.fight) / HZ), flaw = G.result === 'flawless';
  const rows = [['Damage dealt', P.dealt * 10], ['Time left ' + left + ' s', left * 20], ['Health left ' + P.hp, P.hp * 10], ['Parries ' + P.parries, P.parries * 150]];
  if (flaw) rows.push(['Flawless', 2000]);
  return { rows, total: rows.reduce((a, r) => a + r[1], 0), flaw, left };
}

function tick() {
  G.clock++;
  if (G.state === 'intro') {
    G.t++;
    if (G.t === 1) { banner(`STAGE ${G.stage + 1}`, STAGES[G.stage].name); sfx('count'); }
    if (G.t === 70) { banner('FIGHT', ''); sfx('go'); }
    if (G.t >= 84) { G.state = 'fight'; G.t = 0; }
  } else if (G.state === 'fight') {
    if (G.hitstop > 0) { G.hitstop--; }
    else {
      G.fight++;
      playerTick();
      if (G.state === 'fight') enemyTick();
      if (G.state === 'fight' && G.fight >= ROUND) endFight('timeout');
    }
  } else if (G.state === 'ko') {
    G.t++;
    if (E.ko && G.t % 5 === 0 && G.t < 70) emit(HOME + (rand() - 0.5) * 0.6, 0.4 + rand() * 1.2, (rand() - 0.5) * 0.4, 14, [C.hazard, C.white, STAGES[G.stage].col][G.t % 3], 4, { up: 1 });
    if (P.ko && G.t % 7 === 0 && G.t < 60) emit(-HOME + (rand() - 0.5) * 0.4, 0.5 + rand(), 0, 10, C.hot, 3, { up: 1 });
    if (G.t === 8 && E.ko) G.shake = 1;
    if (G.t >= 110) showResult();
  }
  G.shake = Math.max(0, G.shake - 1 / 24); G.flash = Math.max(0, G.flash - 1 / 14);
  P.flash = Math.max(0, P.flash - 1 / 10); P.sflash = Math.max(0, P.sflash - 1 / 14); E.flash = Math.max(0, E.flash - 1 / 10);
  stepParticles(1 / HZ);
  stepFloaters(1 / HZ);
}

// ------------------------------------------------------------------ result cards
function showCard(html) { const c = $('card'); c.innerHTML = html; c.hidden = false; c.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => { audioOn(); sfx('ui'); go(b.dataset.go); })); }
function hideCard() { $('card').hidden = true; }
function go(what) {
  if (what === 'next') startStage(G.stage + 1);
  else if (what === 'retry') startStage(G.stage);
  else if (what === 'restart') { G.scores = [null, null, null]; startStage(0); }
  else if (what === 'start') { G.scores = [null, null, null]; startStage(0); }
}
const fmt = (n) => n.toLocaleString('en-US');
function showResult() {
  G.state = 'result';
  const s = STAGES[G.stage], won = G.result === 'win' || G.result === 'flawless';
  if (won) {
    const sc = stageScore(); G.scores[G.stage] = sc; sfx('win');
    const total = G.scores.reduce((a, x) => a + (x ? x.total : 0), 0);
    if (G.stage === 2) {
      const b = Math.max(best(), total), isBest = total >= best(); store.set('best', b);
      showCard(`<h2 class="${G.scores.every((x) => x.flaw) ? 'cy' : ''}">ALL BOTS DOWN</h2>
        <p class="sub">The Scrap Rover, the Heavy Mech and the Omega Core are scrap.</p>
        <table>${G.scores.map((x, i) => `<tr><td>Stage ${i + 1} · ${STAGES[i].name}${x.flaw ? ' · FLAWLESS' : ''}</td><td>${fmt(x.total)}</td></tr>`).join('')}
        <tr class="tot"><td>FINAL SCORE</td><td id="final-score">${fmt(total)}</td></tr></table>
        <p class="tip">${isBest ? 'New best score on this device.' : `Best on this device: ${fmt(b)}.`} Three flawless stages is the perfect run.</p>
        <div class="row"><button class="btn primary" data-go="restart">PLAY AGAIN</button><a class="btn ghost" href="../">TEACH THE ARM</a></div>
        <p class="links"><a href="https://github.com/megazron" target="_blank" rel="noopener">Back to my GitHub</a></p>`);
    } else {
      showCard(`<h2 class="${sc.flaw ? 'cy' : ''}">${sc.flaw ? 'FLAWLESS' : 'STAGE CLEAR'}</h2>
        ${sc.flaw ? '<p class="stars">&#9733;&#9733;&#9733;</p>' : ''}
        <p class="sub">${s.name} is scrap${sc.flaw ? ' and never touched you' : ''}.</p>
        <table>${sc.rows.map((r) => `<tr><td>${r[0]}</td><td>${fmt(r[1])}</td></tr>`).join('')}
        <tr class="tot"><td>STAGE SCORE · TOTAL ${fmt(total)}</td><td>${fmt(sc.total)}</td></tr></table>
        ${sc.flaw ? '' : '<p class="tip">A flawless win (no health lost) is worth 2,000 more.</p>'}
        <p class="tip">Next: ${STAGES[G.stage + 1].name}. ${STAGES[G.stage + 1].tip}</p>
        <div class="row"><button class="btn primary" data-go="next">NEXT STAGE</button><button class="btn ghost" data-go="retry">RETRY STAGE</button></div>`);
    }
    renderStatic();
  } else {
    sfx('lose');
    const time = G.result === 'timeout';
    showCard(`<h2 class="${time ? 'amb' : 'bad'}">${time ? 'REACTOR OVERHEAT' : 'SYSTEM DOWN'}</h2>
      <p class="sub">${time ? `60 seconds were not enough against the ${s.name}.` : `The ${s.name} wins this one.`} It had ${E.hp} of ${E.max} health left.</p>
      <p class="tip">${s.tip}</p>
      <div class="row"><button class="btn primary" data-go="retry">RETRY STAGE</button><button class="btn ghost" data-go="restart">FROM STAGE 1</button></div>`);
  }
}
function showTitle() {
  G.state = 'title'; G.stage = 0; setFoe(0); resetFighters();
  const touch = matchMedia('(pointer:coarse)').matches;
  showCard(`<h2>ROBOT BATTLE</h2>
    <p class="sub">A real-time duel against three bots, in order. Read each tell, then answer it.</p>
    <ul><li><b>ATTACK</b> a quick punch. Double damage while it vents steam.</li>
    <li><b>SHIELD</b> hold to block. Raise it just before a hit to parry.</li>
    <li><b>CHARGE</b> fill an energy cell. A hit cancels it.</li>
    <li><b>OVERDRIVE</b> 2 energy: breaks a guard, stops a wind-up.</li></ul>
    <p class="keys">${touch ? 'Use the four buttons below. Hold SHIELD.' : 'Keys: A attack · hold S shield · D charge · F overdrive (or J K L ;). Enter starts.'}${best() ? ` Best score: ${fmt(best())}.` : ''}</p>
    <div class="row"><button class="btn primary" data-go="start" id="btn-start">FIGHT</button></div>`);
  renderStatic();
}

// ------------------------------------------------------------------ DOM effects: floating numbers and banners
const fxEl = $('fx'), floaters = [];
function floater(x, y, text, cls, scale) {
  const el = document.createElement('span'); el.textContent = text;
  const [c, ...rest] = cls.split(' ');
  el.className = rest.join(' ');
  el.style.color = { om: '#3dfa46', cy: '#7ffcd5', amb: '#ffb300', rd: '#ff6070', dim: '#b8e8c0' }[c] || '#eafff0';
  fxEl.append(el); floaters.push({ el, x, y, life: 0.9 * (scale || 1), max: 0.9 * (scale || 1) });
  while (floaters.length > 14) floaters.shift().el.remove();
}
function stepFloaters(dt) { for (const f of floaters) { f.life -= dt; f.y += dt * 0.7; } for (let i = floaters.length - 1; i >= 0; i--) if (floaters[i].life <= 0) { floaters[i].el.remove(); floaters.splice(i, 1); } }
const _v = new THREE.Vector3();
function drawFloaters() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  for (const f of floaters) {
    _v.set(f.x, f.y, 0.2).project(camera);
    const k = f.life / f.max, pop = k > 0.85 ? 1 + (k - 0.85) * 3 : 1;
    f.el.style.transform = `translate(${((_v.x + 1) / 2) * w}px,${((1 - _v.y) / 2) * h}px) translate(-50%,-50%) scale(${pop.toFixed(2)})`;
    f.el.style.opacity = Math.min(1, k * 3).toFixed(2);
  }
}
let bannerTimer = 0;
function banner(big, small) {
  const b = $('banner'); b.innerHTML = big + (small ? `<small>${small}</small>` : '');
  b.classList.remove('go'); void b.offsetWidth; b.classList.add('go'); bannerTimer = 0;
}

// ------------------------------------------------------------------ poses, drawn from the state every frame
function posePlayer(k) {
  const pr = player, a = P.act, t = P.t;
  let lean = 0, lunge = 0, aR = 0.15, aL = 0.12, drop = 0, tw = 0;
  if (a === 'atk') {
    if (t < ATK.start) { const w = t / ATK.start; aR = lerp(0.15, -0.45, w); lean = 0.05 * w; }
    else { const w = (t - ATK.start) / ATK.rec, pun = w < 0.3 ? 1 : 1 - ease((w - 0.3) / 0.7); aR = lerp(0.15, 1.6, pun); lunge = 0.42 * pun; lean = -0.14 * pun; tw = -0.25 * pun; }
  } else if (a === 'chg') { const w = Math.min(1, t / 8); aR = -0.55 * w; aL = -0.55 * w; lean = 0.06 * w; drop = 0.04 * w; }
  else if (a === 'od') {
    if (t < OD.start) { const w = t / OD.start; aR = lerp(0.15, 1.57, ease(w * 1.6)); lean = 0.12 * w; drop = 0.06 * w; }
    else { const w = (t - OD.start) / OD.rec; aR = 1.57; lean = lerp(0.18, 0, ease(w)); lunge = -0.12 * (1 - w); }
  } else if (a === 'hit') { const w = 1 - t / HITSTUN; lean = 0.32 * w; lunge = -0.2 * w; aR = 0.5 * w; aL = 0.5 * w; }
  else if (a === 'recoil') { const w = 1 - t / RECOIL; lean = 0.2 * w; lunge = -0.12 * w; aR = lerp(0.15, 1.0, w); }
  if (P.shield) { aL = 1.35; lean = -0.04; }
  if (P.ko) { const w = ease(G.t / 40); lean = 1.35 * w; drop = 0.35 * w; lunge = -0.35 * w; }
  const bob = Math.sin(k * 3.4) * 0.018;
  pr.root.position.set(-HOME + lunge, 0, 0);
  pr.body.position.y = bob - drop; pr.body.rotation.z = lean; pr.torso.rotation.y = tw;
  pr.armR.rotation.z = aR; pr.armL.rotation.z = aL;
  pr.head.rotation.z = -lean * 0.4;
  const shieldA = P.shield ? 0.22 + P.sflash * 0.6 : P.sflash * 0.5;
  pr.shieldMat.opacity = shieldA; pr.shieldLines.material.opacity = Math.min(1, shieldA * 2.6);
  const sp = 1 + P.sflash * 0.08; pr.shield.scale.set(sp, sp, sp);
  pr.shield.position.x = -0.1 + lunge * 0.5;
  pr.shield.visible = shieldA > 0.01;
  const cg = a === 'chg' ? 2 + Math.sin(k * 30) * 1.2 : 1.4 + Math.min(P.en, 3) * 0.5;
  pr.coreMat.emissiveIntensity = cg;
  chargeRing.position.set(-HOME, a === 'chg' ? 0.15 + ((t % 17) / 17) * 1.6 : -5, 0);
  chargeRing.material.opacity = a === 'chg' ? 0.9 * (1 - (t % 17) / 17) : 0;
  coreLight.position.set(-HOME + 0.5, 1.1, 0.4); coreLight.intensity = a === 'chg' ? 3 : a === 'od' ? 6 : 0.6 + P.sflash * 4;
  flashLines(pr.lines, P.flash, 0xff4050);
  pr.shadow.position.x = pr.root.position.x; pr.shadow.scale.setScalar(1 - drop * 0.5);
  // overdrive beam from the fist
  const odOn = a === 'od' && t >= OD.start - 2 && t < OD.start + 12;
  const odA = odOn ? (t < OD.start ? 0.6 : 1 - (t - OD.start) / 12) : 0;
  showBeam(odBeam, pr.root.position.x + 0.85, HOME - 0.2, 1.2, odOn ? 0.12 + 0.08 * Math.sin(k * 60) : 0.1, odA);
}
function flashLines(lines, f, hex) { _c.setHex(hex); for (const m of lines) m.color.copy(m.userData.base).lerp(_c, f); }

function poseFoe(k) {
  const f = foe, s = STAGES[G.stage], mv = MOVES[E.move];
  let lean = 0, lunge = 0, arm = f.armRest, eyeCol = s.col, eyeI = 1.4, eyeS = 1, plate = 0, ringA = 0, ringR = 1;
  const wind = E.part === 'wind' && !E.stun && !E.trans, w = wind ? E.t / E.wind : 0;
  const sinceStrike = G.fight - E.strikeT;
  if (wind && E.move === 'J') { arm = f.armRest - 0.5 * ease(w); lean = 0.08 * w; eyeCol = C.hazard; eyeI = 2 + (Math.floor(E.t / 4) % 2) * 2; }
  if (wind && E.move === 'H') { arm = f.armRest - 2.3 * ease(w * 1.3); lean = 0.22 * ease(w); eyeCol = C.hot; eyeI = 2 + 7 * w; eyeS = 1 + 0.7 * w; }
  if (wind && E.move === 'K') { eyeCol = Math.floor(E.t / 5) % 2 ? C.white : C.hot; eyeI = 3 + 6 * w; eyeS = 1 + 0.9 * w; ringA = 0.35 + 0.65 * w; ringR = lerp(1.7, 0.25, w); lean = 0.12 * w; }
  if (E.part === 'rec' && !E.stun && (E.move === 'J' || E.move === 'H')) {
    const r = clamp(sinceStrike / 10, 0, 1), back = 1 - ease((sinceStrike - 6) / 18);
    arm = lerp(f.armRest - (E.move === 'H' ? 2.3 : 0.5), 1.55, ease(r * 3)) * back + f.armRest * (1 - back);
    lunge = (mv.lunge || 0) * back; lean = -0.2 * back; eyeCol = E.move === 'H' ? C.hot : C.hazard; eyeI = 3 * back + 1.4;
  }
  if (E.part === 'rec' && !E.stun && E.move === 'K') { const r = clamp(sinceStrike / 14, 0, 1); eyeCol = C.white; eyeI = 6 * (1 - r) + 1.4; lean = -0.2 * (1 - r); }
  if (E.move === 'G' && !E.broken && !E.stun) { plate = ease(E.t / 6) * (1 - ease((E.t - E.len + 8) / 8)); eyeCol = C.cyan; eyeI = 1.8; }
  if (E.move === 'R' && !E.stun) { eyeI = 0.4 + Math.sin(k * 8) * 0.15; lean = 0.1; arm = f.armRest + 0.3; }
  if (E.stun) { eyeCol = C.core; eyeI = (Math.floor(k * 10) % 2) ? 0.3 : 2.5; lean = 0.25; arm = f.armRest + 0.6; }
  if (E.trans) { eyeCol = C.white; eyeI = 4 + Math.sin(k * 40) * 2; G.shake = Math.max(G.shake, 0.2); }
  if (E.ko) { const kw = ease(G.t / 50); lean = 1.1 * kw; eyeI = 1.4 * (1 - kw); }
  const bob = Math.sin(k * 2.6 + 1) * 0.02;
  f.root.position.set(HOME - lunge, 0, 0);
  f.body.position.y = bob - (E.ko ? 0.3 * ease(G.t / 50) : 0);
  f.body.rotation.z = lean;
  if (f.arm) f.arm.rotation.z = arm;
  if (f.arm2) f.arm2.rotation.z = f.armRest + (plate ? 0.9 * plate : 0) + Math.sin(k * 2) * 0.04;
  for (const p of f.plates) {                         // guard: shoulder plates swing in front of the chest
    p.position.set(lerp(0, 0.5, plate), lerp(1.58, 1.08, plate), p.userData.s * lerp(0.36, 0.22, plate));
    p.rotation.x = lerp(p.userData.s * 0.9, 0, plate);
    p.rotation.y = lerp(0, -p.userData.s * 0.35, plate);
  }
  if (f.core) {
    const sp = 1 + E.phase * 0.8 + (wind && E.move === 'K' ? 6 * w : 0) + (E.trans ? 8 : 0);
    f.hover.position.y = 1.3 + Math.sin(k * 2.2) * 0.07 - (E.ko ? 0.9 * ease(G.t / 50) : 0);
    f.rings[0].rotation.y = k * 0.9 * sp; f.rings[1].rotation.z = k * 0.7 * sp;
    f.inner.material.emissiveIntensity = 0.4 + E.phase * 0.6 + (wind ? w * 2 : 0);
    f.inner.material.emissive.setHex(E.phase === 2 ? 0xff8090 : s.col);
    for (const sp2 of f.spikes) sp2.position.y = sp2.userData.base + E.phase * 0.08 + (wind && E.move !== 'K' ? 0.12 * w : 0);
    f.hover.rotation.x = E.move === 'R' ? 0.25 : 0;
    const gA = E.move === 'G' && !E.broken && !E.stun ? plate : 0;
    f.guardMat.opacity = gA * 0.55; f.guard.visible = gA > 0.01; f.guard.rotation.y = k * 0.5;
  }
  f.eyeMat.emissive.setHex(eyeCol); f.eyeMat.emissiveIntensity = eyeI; f.eye.scale.setScalar(eyeS);
  f.eye.getWorldPosition(_v);
  eyeLight.position.copy(_v).add(new THREE.Vector3(-0.4, 0, 0.3)); eyeLight.color.setHex(eyeCol); eyeLight.intensity = eyeI * 0.9;
  crushRing.position.set(_v.x - 0.5, _v.y, 0); crushRing.scale.setScalar(ringR); crushRing.material.opacity = ringA;
  const cb = E.move === 'K' && E.part === 'rec' && !E.stun && sinceStrike < 12;
  showBeam(crushBeam, -HOME + 0.3, _v.x - 0.1, _v.y - 0.1, 0.22 + 0.06 * Math.sin(k * 70), cb ? 1 - sinceStrike / 12 : 0);
  flashLines(f.lines, E.flash, 0xffffff);
  f.shadow.position.x = f.root.position.x;
  E.eyeGlow = eyeI; E.ringA = ringA;
}

// ------------------------------------------------------------------ HUD
const hpYou = $('hp-you'), hpFoe = $('hp-foe'), lagYou = $('lag-you'), lagFoe = $('lag-foe'), timerEl = $('timer'), tellEl = $('tell');
const cells = [...$('energy').querySelectorAll('span')];
const padBtn = Object.fromEntries([...document.querySelectorAll('.pad')].map((b) => [b.dataset.act, b]));
function tellInfo() {
  if (G.state !== 'fight' && G.state !== 'intro') return null;
  if (E.trans) return ['heavy', 'RAGE: NEW RHYTHM'];
  if (E.stun) return ['stun', 'STAGGERED: HIT IT'];
  if (E.part === 'wind') return E.move === 'H' ? ['heavy', 'HEAVY HIT: SHIELD'] : E.move === 'K' ? ['crush', 'CRUSHER: OVERDRIVE'] : ['jab', 'JAB'];
  if (E.move === 'G' && !E.broken) return ['guard', 'GUARD: CHARGE UP'];
  if (E.move === 'R') return ['vent', 'VENTING: ATTACK'];
  return null;
}
function renderHud() {
  P.shown += (P.hp - P.shown) * 0.08; E.shown += (E.hp - E.shown) * 0.08;
  hpYou.style.transform = `scaleX(${P.hp / PLAYER_HP})`; lagYou.style.transform = `scaleX(${P.shown / PLAYER_HP})`;
  hpFoe.style.transform = `scaleX(${E.hp / E.max})`; lagFoe.style.transform = `scaleX(${E.shown / E.max})`;
  hpYou.parentElement.classList.toggle('low', P.hp > 0 && P.hp <= 25);
  cells.forEach((c, i) => { const f = clamp(P.en - i, 0, 1); c.firstChild.style.transform = `scaleX(${f})`; c.classList.toggle('full', f >= 1); });
  const ready = P.en >= OD.cost; const lbl = $('en-label'); lbl.textContent = ready ? 'OVERDRIVE READY' : 'ENERGY'; lbl.classList.toggle('ready', ready);
  const left = G.state === 'fight' || G.state === 'ko' ? Math.ceil((ROUND - G.fight) / HZ) : 60;
  const tt = String(Math.max(0, left)); if (timerEl.textContent !== tt) timerEl.textContent = tt;
  timerEl.classList.toggle('warn', left <= 10 && G.state === 'fight');
  const ti = tellInfo();
  if (ti) { tellEl.textContent = ti[1]; tellEl.className = 'tell on ' + ti[0]; } else tellEl.className = 'tell';
  const live = G.state === 'fight';
  padBtn.atk.classList.toggle('on', P.act === 'atk');
  padBtn.shd.classList.toggle('on', P.shield);
  padBtn.chg.classList.toggle('on', P.act === 'chg');
  padBtn.od.classList.toggle('on', P.act === 'od');
  padBtn.od.classList.toggle('off', P.en < OD.cost);
  padBtn.od.classList.toggle('ready', live && P.en >= OD.cost && !P.act);
  stageEl.classList.toggle('flash', G.flash > 0.05);
  stageEl.classList.toggle('cy', !!G.flashCy && G.flash > 0.05); if (G.flash <= 0.05) G.flashCy = false;
}
function renderStatic() {
  const s = STAGES[G.stage];
  $('foe-name').textContent = s.name;
  $('stage-label').textContent = `STAGE ${G.stage + 1}/3`;
  [...$('stages').children].forEach((b, i) => { b.classList.toggle('on', i === G.stage); b.classList.toggle('done', !!G.scores[i] && i !== G.stage); });
  $('hint').textContent = G.state === 'title' ? 'Three bots, in order. Same rhythm every time: learn it.' : s.hint;
  $('btn-mute').textContent = muted ? 'SND OFF' : 'SND ON';
}

// ------------------------------------------------------------------ camera
const _look = new THREE.Vector3(0, 0.95, 0);
let camBase = new THREE.Vector3(), camYaw = 0;
const FIT = [[-HOME - 0.65, 0, 0.5], [-HOME - 0.65, 2.1, 0], [HOME + 0.75, 0, -0.5], [HOME + 0.75, 2.1, 0], [-HOME - 0.65, 0, -0.5], [HOME + 0.75, 0, 0.5]];
function fitCamera() {
  const w = stageEl.clientWidth || 1, h = stageEl.clientHeight || 1;
  renderer.setSize(w, h, false); camera.aspect = w / h;
  const portrait = h > w * 0.95;
  camYaw = portrait ? -0.62 : -0.12;
  camera.fov = portrait ? 44 : 34;
  const el = portrait ? 0.3 : 0.2;
  const hudTop = Math.min(0.42, 110 / h);
  const dir = new THREE.Vector3(Math.sin(camYaw) * Math.cos(el), Math.sin(el), Math.cos(camYaw) * Math.cos(el));
  const fits = (d) => {
    camera.position.copy(_look).addScaledVector(dir, d); camera.lookAt(_look); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
    return FIT.every((p) => { _v.fromArray(p).project(camera); return Math.abs(_v.x) < 0.94 && _v.y < 1 - hudTop * 2 && _v.y > -0.94; });
  };
  let lo = 1, hi = 30;
  for (let i = 0; i < 24; i++) { const mid = (lo + hi) / 2; if (fits(mid)) hi = mid; else lo = mid; }
  fits(hi); camBase.copy(camera.position);
  if (ready) render();
}
let ready = false;
new ResizeObserver(fitCamera).observe(stageEl);

function render() {
  const k = G.clock / HZ;
  posePlayer(k); poseFoe(k);
  const sh = G.shake * G.shake * 0.12;
  camera.position.set(camBase.x + Math.sin(G.clock * 1.7) * sh, camBase.y + Math.sin(G.clock * 2.3 + 1) * sh, camBase.z);
  camera.lookAt(_look.x + Math.sin(G.clock * 1.3) * sh * 0.5, _look.y, _look.z);
  renderer.render(scene, camera);
  drawFloaters(); renderHud();
}

// ------------------------------------------------------------------ input: keys, buttons, touch
const KEYMAP = { a: 'atk', j: 'atk', s: 'shd', k: 'shd', d: 'chg', l: 'chg', f: 'od', ';': 'od' };
function syncShield() { input.shield = input.keys.has('shd') || input.padHold.size > 0; }
window.addEventListener('keydown', (e) => {
  if (!$('how').hidden) { if (e.key === 'Escape' || e.key === 'Enter') $('how').hidden = true; return; }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const a = KEYMAP[e.key.toLowerCase()];
  if (a) {
    e.preventDefault(); audioOn();
    if (a === 'shd') { input.keys.add('shd'); syncShield(); } else if (!e.repeat) press(a);
    return;
  }
  if (e.key === 'Enter' && !$('card').hidden) {
    const b = $('card').querySelector('.btn.primary'); if (b) { e.preventDefault(); b.click(); }
  }
});
window.addEventListener('keyup', (e) => { if (KEYMAP[e.key.toLowerCase()] === 'shd') { input.keys.delete('shd'); syncShield(); } });
window.addEventListener('blur', () => { input.keys.clear(); input.padHold.clear(); syncShield(); });
for (const [act, b] of Object.entries(padBtn)) {
  b.addEventListener('pointerdown', (e) => {
    e.preventDefault(); audioOn();
    if (act === 'shd') { input.padHold.add(e.pointerId); syncShield(); try { b.setPointerCapture(e.pointerId); } catch { /* synthetic */ } }
    else press(act);
  });
  if (act === 'shd') {
    const up = (e) => { input.padHold.delete(e.pointerId); syncShield(); };
    b.addEventListener('pointerup', up); b.addEventListener('pointercancel', up); b.addEventListener('lostpointercapture', up);
  }
  b.addEventListener('click', (e) => { if (e.detail === 0 && act !== 'shd') press(act); });   // keyboard activation
  b.addEventListener('contextmenu', (e) => e.preventDefault());
}
canvas.addEventListener('contextmenu', (e) => e.preventDefault());
if (matchMedia('(pointer:coarse)').matches) {
  const sub = { atk: 'TAP', shd: 'HOLD', chg: 'TAP', od: '2 ENERGY' };
  for (const [a, b] of Object.entries(padBtn)) b.querySelector('small').textContent = sub[a];
}
$('btn-mute').addEventListener('click', () => { muted = !muted; store.set('muted', muted); audioOn(); sfx('ui'); renderStatic(); });
$('btn-how').addEventListener('click', () => { $('how').hidden = false; });
$('btn-how-close').addEventListener('click', () => { $('how').hidden = true; });
$('how').addEventListener('click', (e) => { if (e.target === $('how')) $('how').hidden = true; });
STAGES.forEach((s, i) => { const b = document.createElement('button'); b.textContent = String(i + 1); b.tabIndex = -1; b.setAttribute('aria-label', `Stage ${i + 1}: ${s.name}`); $('stages').append(b); });

// ------------------------------------------------------------------ main loop: fixed 60 Hz ticks
let manual = false, last = performance.now(), acc = 0, frames = 0, fpsT = 0, fps = 0;
function frame(now) {
  requestAnimationFrame(frame);
  if (manual) return;
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  frames++; fpsT += dt; if (fpsT >= 1) { fps = frames / fpsT; frames = 0; fpsT = 0; }
  acc += dt; let n = 0;
  while (acc >= 1 / HZ && n < 6) { tick(); acc -= 1 / HZ; n++; }
  if (n === 6) acc = 0;
  render();
}

// ------------------------------------------------------------------ test hooks
window.__battle = {
  snapshot() {
    const ti = tellInfo();
    return { state: G.state, stage: G.stage, result: G.result, fight: G.fight, timeLeft: Math.ceil((ROUND - G.fight) / HZ), hitstop: G.hitstop,
      player: { hp: P.hp, en: P.en, act: P.act, t: P.t, shield: P.shield, parries: P.parries, dealt: P.dealt },
      enemy: { hp: E.hp, max: E.max, move: E.move, part: E.part, t: E.t, wind: E.wind, phase: E.phase, stun: E.stun, trans: E.trans, eyeGlow: E.eyeGlow, ring: E.ringA },
      tell: ti ? ti[1] : '', scores: G.scores.map((x) => (x ? x.total : null)), fps, card: !$('card').hidden };
  },
  setManual(on) { manual = !!on; last = performance.now(); acc = 0; },
  advance(sec) { const n = Math.max(1, Math.round(sec * HZ)); for (let i = 0; i < n; i++) tick(); render(); return n; },
  ticks(n) { for (let i = 0; i < n; i++) tick(); render(); },
  start(i = 0) { G.scores = [null, null, null]; startStage(i); },
  project(x, y, z) { camera.updateMatrixWorld(); const r = canvas.getBoundingClientRect(); _v.set(x, y, z).project(camera); return { x: r.left + (_v.x + 1) / 2 * r.width, y: r.top + (1 - _v.y) / 2 * r.height }; },
  HZ, MOVES, STAGES: STAGES.map((s) => ({ name: s.name, hp: s.hp })),
};

// ------------------------------------------------------------------ boot
(async function boot() {
  try { await Promise.race([document.fonts.load('italic 40px "Barlow XB"'), new Promise((r) => setTimeout(r, 1200))]); } catch { /* system fonts */ }
  ready = true; showTitle(); fitCamera(); render();
  $('boot').classList.add('gone'); window.__battle.ready = true;
  requestAnimationFrame(frame);
})();
