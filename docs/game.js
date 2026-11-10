// Teach the Arm: a learning-from-demonstration toy.
// The player moves a 6-axis arm by inverse kinematics and picks and places objects.
// Every placement is stored as one task-level step (object, target, offsets), never as raw
// pointer motion, so the robot can re-plan the same task after the scene is shuffled.
import * as THREE from './vendor/three.module.min.js';

const $ = (id) => document.getElementById(id);
const COL = { void: 0x030d05, omni: 0x3dfa46, cyan: 0x7ffcd5, hazard: 0xffb300, red: 0xff4d5e, amber: 0xffb300, line: 0x1f7a2c };
const CSS = { red: '#ff4d5e', amber: '#ffb300', cyan: '#7ffcd5', omni: '#3dfa46' };
const HOVER = 0.30, R_MIN = 0.30, R_MAX = 0.70, OPEN = 0.118, PAD_HALF = 0.10;
const TABLE = { x0: -0.70, x1: 0.70, z0: -0.22, z1: 0.82 };
const PAD_SLOTS = [[-0.36, 0.50], [0, 0.60], [0.36, 0.50], [-0.52, 0.14], [0.52, 0.14]];
const SITE = 'https://megazron.github.io/MegaZroN/';

// ------------------------------------------------------------------ small helpers
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const wrapPi = (a) => { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; };
const nearestStep = (a, ref, step) => a + Math.round((ref - a) / step) * step;   // a + k*step closest to ref
const rotY = (x, z, a) => [x * Math.cos(a) + z * Math.sin(a), -x * Math.sin(a) + z * Math.cos(a)];
const natYaw = (x, z) => Math.atan2(x, z);
let rngState = (Date.now() ^ 0x9e3779b9) >>> 0;
function rnd() { rngState |= 0; rngState = rngState + 0x6D2B79F5 | 0; let t = Math.imul(rngState ^ rngState >>> 15, 1 | rngState); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }
function clampWS(x, z) {
  for (let i = 0; i < 3; i++) {
    x = clamp(x, -0.60, 0.60); z = clamp(z, -0.10, 0.74);
    const r = Math.hypot(x, z) || 1e-6, rr = clamp(r, R_MIN, R_MAX);
    x *= rr / r; z *= rr / r;
  }
  return [x, z];
}

// ------------------------------------------------------------------ arm kinematics
const X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0);
const CHAIN = [
  { off: [0, 0.10, 0], axis: Y, lim: [-2.97, 2.97] },   // J1 base yaw
  { off: [0, 0.12, 0], axis: X, lim: [-1.60, 1.60] },   // J2 shoulder pitch
  { off: [0, 0.42, 0], axis: X, lim: [0.09, 2.70] },    // J3 elbow pitch (one sign: elbow stays up)
  { off: [0, 0.16, 0], axis: Y, lim: [-2.97, 2.97] },   // J4 forearm roll
  { off: [0, 0.24, 0], axis: X, lim: [0.09, 2.20] },    // J5 wrist pitch (one sign: no wrist flip)
  { off: [0, 0.07, 0], axis: Y, lim: [-3.40, 3.40] },   // J6 tool roll
];
const TCP_OFF = new THREE.Vector3(0, 0.13, 0);
const N = CHAIN.length, WR = 0.2, LAMBDA2 = 0.0009;
const HOME_Q = [0, 0.18, 1.62, 0, 1.34, 0];
const K = {
  p: CHAIN.map(() => new THREE.Vector3()), a: CHAIN.map(() => new THREE.Vector3()),
  tcp: new THREE.Vector3(), rot: new THREE.Quaternion(),
};
const _v = new THREE.Vector3(), _q = new THREE.Quaternion(), _qe = new THREE.Quaternion(), _tq = new THREE.Quaternion();
const _flip = new THREE.Quaternion().setFromAxisAngle(X, Math.PI);

function fk(q) {
  const pos = K.tcp.set(0, 0, 0), rot = K.rot.identity();
  for (let i = 0; i < N; i++) {
    _v.fromArray(CHAIN[i].off).applyQuaternion(rot); pos.add(_v); K.p[i].copy(pos);
    K.a[i].copy(CHAIN[i].axis).applyQuaternion(rot);
    rot.multiply(_q.setFromAxisAngle(CHAIN[i].axis, q[i]));
  }
  pos.add(_v.copy(TCP_OFF).applyQuaternion(rot));
}
const J = Array.from({ length: 6 }, () => new Float64Array(N));
const A = Array.from({ length: 6 }, () => new Float64Array(7));
const err = new Float64Array(6);
// Damped least squares on the 6D pose error: dq = J^T (J J^T + lambda^2 I)^-1 e
function ik(q, tx, ty, tz, yaw, iters) {
  _tq.setFromAxisAngle(Y, yaw).multiply(_flip);            // tool axis straight down, fingers at `yaw`
  let pe = 0, re = 0;
  for (let it = 0; it <= iters; it++) {
    fk(q);
    let ex = tx - K.tcp.x, ey = ty - K.tcp.y, ez = tz - K.tcp.z;
    pe = Math.hypot(ex, ey, ez);
    _qe.copy(K.rot).invert().premultiply(_tq);
    if (_qe.w < 0) { _qe.x = -_qe.x; _qe.y = -_qe.y; _qe.z = -_qe.z; _qe.w = -_qe.w; }
    const s = Math.hypot(_qe.x, _qe.y, _qe.z); re = 2 * Math.atan2(s, _qe.w);
    if (it === iters) break;
    const k = s < 1e-9 ? 0 : re / s; let rx = _qe.x * k, ry = _qe.y * k, rz = _qe.z * k;
    if (pe > 0.08) { const c = 0.08 / pe; ex *= c; ey *= c; ez *= c; }
    if (re > 0.5) { const c = 0.5 / re; rx *= c; ry *= c; rz *= c; }
    err[0] = ex; err[1] = ey; err[2] = ez; err[3] = rx * WR; err[4] = ry * WR; err[5] = rz * WR;
    for (let i = 0; i < N; i++) {
      const a = K.a[i]; _v.subVectors(K.tcp, K.p[i]);
      J[0][i] = a.y * _v.z - a.z * _v.y; J[1][i] = a.z * _v.x - a.x * _v.z; J[2][i] = a.x * _v.y - a.y * _v.x;
      J[3][i] = a.x * WR; J[4][i] = a.y * WR; J[5][i] = a.z * WR;
    }
    for (let r = 0; r < 6; r++) {
      for (let c = 0; c < 6; c++) { let sum = 0; for (let i = 0; i < N; i++) sum += J[r][i] * J[c][i]; A[r][c] = sum + (r === c ? LAMBDA2 : 0); }
      A[r][6] = err[r];
    }
    for (let c = 0; c < 6; c++) {                           // Gauss-Jordan with partial pivoting
      let piv = c; for (let r = c + 1; r < 6; r++) if (Math.abs(A[r][c]) > Math.abs(A[piv][c])) piv = r;
      const t = A[c]; A[c] = A[piv]; A[piv] = t;
      const d = A[c][c] || 1e-12;
      for (let r = 0; r < 6; r++) if (r !== c) { const f = A[r][c] / d; if (f) for (let cc = c; cc < 7; cc++) A[r][cc] -= f * A[c][cc]; }
    }
    for (let i = 0; i < N; i++) {
      let dq = 0; for (let r = 0; r < 6; r++) dq += J[r][i] * (A[r][6] / (A[r][r] || 1e-12));
      q[i] = clamp(q[i] + clamp(dq, -0.25, 0.25), CHAIN[i].lim[0], CHAIN[i].lim[1]);
    }
  }
  return { pe, re };
}

// ------------------------------------------------------------------ renderer and scene
const canvas = $('scene'), stage = $('stage');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(COL.void);
const scene = new THREE.Scene();
scene.fog = new THREE.Fog(COL.void, 3.2, 7);
const camera = new THREE.PerspectiveCamera(34, 1, 0.05, 30);
scene.add(new THREE.HemisphereLight(0xcfffe0, 0x04140a, 1.5));
const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(0.8, 2.2, 1.6); scene.add(sun);
const rim = new THREE.DirectionalLight(COL.omni, 1.0); rim.position.set(-1.5, 0.8, -1.2); scene.add(rim);

const lineMat = (color, opacity = 1) => new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity });
function edged(mesh, color = COL.omni, opacity = 0.55) {
  const e = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry, 30), lineMat(color, opacity));
  mesh.add(e); mesh.userData.edges = e; return mesh;
}

// table: a floating slab with a glowing rim, a 10 cm grid and the reach limits drawn on it
(function buildTable() {
  const w = TABLE.x1 - TABLE.x0, d = TABLE.z1 - TABLE.z0, cx = 0, cz = (TABLE.z0 + TABLE.z1) / 2;
  const slab = edged(new THREE.Mesh(new THREE.BoxGeometry(w, 0.05, d), new THREE.MeshStandardMaterial({ color: 0x0a2411, roughness: 0.85, metalness: 0.1 })), COL.omni, 0.9);
  slab.position.set(cx, -0.025, cz); scene.add(slab);
  const pts = [];
  for (let x = -0.6; x <= 0.601; x += 0.1) pts.push(x, 0.001, TABLE.z0, x, 0.001, TABLE.z1);
  for (let z = -0.2; z <= 0.801; z += 0.1) pts.push(TABLE.x0, 0.001, z, TABLE.x1, 0.001, z);
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  scene.add(new THREE.LineSegments(g, lineMat(COL.line, 0.45)));
  for (const r of [R_MIN, R_MAX]) {                          // reach arcs, clipped to the table
    const a = [];
    for (let i = 0; i <= 96; i++) {
      const t = -Math.PI + (i / 96) * 2 * Math.PI, x = r * Math.sin(t), z = r * Math.cos(t);
      const ok = x > TABLE.x0 && x < TABLE.x1 && z > TABLE.z0 && z < TABLE.z1;
      const t2 = -Math.PI + ((i + 1) / 96) * 2 * Math.PI, x2 = r * Math.sin(t2), z2 = r * Math.cos(t2);
      const ok2 = x2 > TABLE.x0 && x2 < TABLE.x1 && z2 > TABLE.z0 && z2 < TABLE.z1;
      if (ok && ok2 && i < 96 && i % 2 === 0) a.push(x, 0.002, z, x2, 0.002, z2);
    }
    const ag = new THREE.BufferGeometry(); ag.setAttribute('position', new THREE.Float32BufferAttribute(a, 3));
    scene.add(new THREE.LineSegments(ag, lineMat(COL.omni, 0.35)));
  }
  const floor = new THREE.GridHelper(8, 40, COL.line, 0x0c2a14); floor.position.y = -0.7;
  floor.material.transparent = true; floor.material.opacity = 0.5; scene.add(floor);
})();

// arm meshes: one group per joint, rotated every frame from the joint vector q
const armMat = new THREE.MeshStandardMaterial({ color: 0x16301d, roughness: 0.45, metalness: 0.6 });
const jointMat = new THREE.MeshStandardMaterial({ color: 0x0b1a10, roughness: 0.35, metalness: 0.7 });
const glowMat = new THREE.MeshStandardMaterial({ color: 0x0a2a10, emissive: COL.omni, emissiveIntensity: 1.6 });
const jointG = []; const fingers = [];
(function buildArm() {
  const box = (w, h, d, y, mat = armMat) => { const m = edged(new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat)); m.position.y = y; return m; };
  const cyl = (r, h, y, mat = armMat, seg = 24) => { const m = edged(new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), mat), COL.omni, 0.35); m.position.y = y; return m; };
  const hub = (r, len) => { const m = cyl(r, len, 0, jointMat); m.rotation.z = Math.PI / 2; const g = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.55, r * 0.55, len + 0.006, 20), glowMat); m.add(g); return m; };
  const ring = (r, y) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, 0.008, 28), glowMat); m.position.y = y; return m; };
  const base = new THREE.Group(); scene.add(base);
  base.add(cyl(0.105, 0.03, 0.015, jointMat, 32), cyl(0.082, 0.07, 0.065, armMat, 32), ring(0.084, 0.098));
  let parent = base;
  for (let i = 0; i < N; i++) {
    const hold = new THREE.Group(); hold.position.fromArray(CHAIN[i].off); parent.add(hold);
    const g = new THREE.Group(); hold.add(g); jointG.push(g); parent = g;
  }
  jointG[0].add(cyl(0.07, 0.085, 0.045, armMat, 28), box(0.15, 0.05, 0.085, 0.10, jointMat));
  jointG[1].add(hub(0.058, 0.17), box(0.075, 0.42, 0.065, 0.21), box(0.02, 0.30, 0.07, 0.21, glowMat));
  jointG[2].add(hub(0.05, 0.15), box(0.062, 0.14, 0.058, 0.08));
  jointG[3].add(ring(0.04, 0.0), cyl(0.034, 0.22, 0.11, armMat, 20), ring(0.036, 0.18));
  jointG[4].add(hub(0.04, 0.10), box(0.05, 0.055, 0.05, 0.035));
  jointG[5].add(ring(0.032, 0.002), box(0.15, 0.022, 0.046, 0.022, jointMat));
  for (const s of [-1, 1]) {
    const f = new THREE.Group();
    const body = box(0.012, 0.13, 0.034, 0.095, jointMat);
    const pad = box(0.004, 0.058, 0.03, 0.13, glowMat); pad.position.x = -s * 0.008;
    f.add(body, pad); jointG[5].add(f); fingers.push({ g: f, s });
  }
})();
function poseArm(q, grip) {
  for (let i = 0; i < N; i++) { if (CHAIN[i].axis === X) jointG[i].rotation.x = q[i]; else jointG[i].rotation.y = q[i]; }
  for (const f of fingers) f.g.position.x = f.s * (grip / 2 + 0.006 + 0.004);
}

// aiming aids: drop line, reticle on the surface below, ghost of a planned placement
const dropGeo = new THREE.BufferGeometry(); dropGeo.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 0, 1, 0], 3));
const dropLine = new THREE.Line(dropGeo, new THREE.LineDashedMaterial({ color: COL.cyan, dashSize: 0.012, gapSize: 0.01, transparent: true, opacity: 0.8 }));
scene.add(dropLine);
const reticle = new THREE.Mesh(new THREE.RingGeometry(0.8, 1, 40), new THREE.MeshBasicMaterial({ color: COL.cyan, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false }));
reticle.rotation.x = -Math.PI / 2; scene.add(reticle);
const ghost = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.08, 0.08, 0.08)), lineMat(COL.cyan, 0.9));
ghost.visible = false; scene.add(ghost);
const shadowGeo = new THREE.CircleGeometry(1, 24);
const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.55, depthWrite: false });

// ------------------------------------------------------------------ world: objects, pads, levels
let objs = [], pads = [];
const objGroup = new THREE.Group(), padGroup = new THREE.Group(); scene.add(padGroup, objGroup);
const objById = (id) => objs.find((o) => o.id === id);
const padById = (id) => pads.find((p) => p.id === id);
const padOf = (o) => { const p = pads.find((p) => Math.abs(o.pos.x - p.x) <= PAD_HALF && Math.abs(o.pos.z - p.z) <= PAD_HALF); return p ? p.id : null; };
const kindName = (k) => (k === 'cube' ? 'cube' : 'cylinder');

const tower = (ids) => ids.map(objById).sort((a, b) => a.pos.y - b.pos.y);
function checkTower(order) {
  const t = tower(['red', 'amber', 'cyan']);
  const inA = t.filter((o) => padOf(o) === 'A');
  if (inA.length < 3) return { ok: false, reason: `only ${inA.length} of 3 cubes ended on pad A` };
  const stacked = t[0].pos.y < 0.06 && t[1].on === t[0].id && t[2].on === t[1].id;
  if (!stacked) return { ok: false, reason: 'the cubes are on pad A but not stacked into one tower' };
  if (order && t.map((o) => o.id).join() !== order.join()) return { ok: false, reason: `the tower reads ${t.map((o) => o.id).join(', ')} from the bottom; it must be ${order.join(', ')}` };
  return { ok: true };
}
const LEVELS = [
  { name: 'SORT BY COLOUR', goal: 'Put each object on the pad of its own colour.', par: 3, task: 'sort by colour',
    objects: [{ id: 'red', kind: 'cube', x: -0.22, z: 0.30 }, { id: 'cyan', kind: 'cyl', x: 0, z: 0.36 }, { id: 'amber', kind: 'cube', x: 0.22, z: 0.30 }],
    pads: { A: 'amber', B: 'red', C: 'cyan' },
    check() {
      for (const o of objs) { const want = pads.find((p) => p.color === o.id); if (padOf(o) !== want.id || o.pos.y > 0.06) return { ok: false, reason: `the ${o.name} is not on the ${o.id} pad ${want.id}` }; }
      return { ok: true };
    } },
  { name: 'STACK A TOWER', goal: 'Stack all three cubes into one tower on pad A. Any order.', par: 3, task: 'stack a tower',
    objects: [{ id: 'red', kind: 'cube', x: -0.22, z: 0.30 }, { id: 'cyan', kind: 'cube', x: 0, z: 0.36 }, { id: 'amber', kind: 'cube', x: 0.22, z: 0.30 }],
    pads: { A: 'omni', B: 'omni', C: 'omni' }, check: () => checkTower(null) },
  { name: 'ORDER MATTERS', goal: 'Tower on pad A, bottom to top: red, amber, cyan. Amber is in the way.', par: 4, task: 'stack in the right order',
    objects: [{ id: 'red', kind: 'cube', x: -0.20, z: 0.32 }, { id: 'amber', kind: 'cube', on: 'red' }, { id: 'cyan', kind: 'cube', x: 0.20, z: 0.32 }],
    pads: { A: 'omni', B: 'omni', C: 'omni' }, check: () => checkTower(['red', 'amber', 'cyan']) },
];

function letterTexture(ch, css) {
  const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d');
  g.font = 'italic 110px "Barlow XB", "Arial Narrow", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillStyle = css; g.shadowColor = css; g.shadowBlur = 12; g.fillText(ch, 60, 70);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function buildPads(level) {
  padGroup.clear(); pads = [];
  Object.entries(level.pads).forEach(([id, color], i) => {
    const css = CSS[color], g = new THREE.Group(), h = PAD_HALF;
    const fill = new THREE.Mesh(new THREE.PlaneGeometry(2 * h, 2 * h), new THREE.MeshBasicMaterial({ color: css, transparent: true, opacity: 0.16, depthWrite: false }));
    fill.rotation.x = -Math.PI / 2; fill.position.y = 0.002; g.add(fill);
    const rimMat = new THREE.MeshStandardMaterial({ color: 0x0a2a10, emissive: css, emissiveIntensity: 1.3 });
    for (const [x, z, w, d] of [[0, -h, 2 * h + 0.008, 0.008], [0, h, 2 * h + 0.008, 0.008], [-h, 0, 0.008, 2 * h], [h, 0, 0.008, 2 * h]]) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, 0.004, d), rimMat); m.position.set(x, 0.002, z); g.add(m);
    }
    const label = new THREE.Mesh(new THREE.PlaneGeometry(0.085, 0.085), new THREE.MeshBasicMaterial({ map: letterTexture(id, css), transparent: true, depthWrite: false }));
    label.rotation.x = -Math.PI / 2; label.position.set(0, 0.003, h + 0.055); g.add(label);
    const p = { id, color, x: 0, z: 0, g }; pads.push(p); padGroup.add(g);
    movePad(p, PAD_SLOTS[i][0], PAD_SLOTS[i][1]);
  });
}
function movePad(p, x, z) { p.x = x; p.z = z; p.g.position.set(x, 0, z); }

function buildObjects(level) {
  objGroup.clear(); objs = [];
  for (const d of level.objects) {
    const hex = COL[d.id];
    const geo = d.kind === 'cube' ? new THREE.BoxGeometry(0.08, 0.08, 0.08) : new THREE.CylinderGeometry(0.038, 0.038, 0.08, 28);
    const mesh = edged(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: hex, emissive: hex, emissiveIntensity: 0.28, roughness: 0.4 })), 0xffffff, 0.5);
    const shadow = new THREE.Mesh(shadowGeo, shadowMat); shadow.rotation.x = -Math.PI / 2;
    objGroup.add(mesh, shadow);
    objs.push({ id: d.id, kind: d.kind, name: `${d.id} ${kindName(d.kind)}`, css: CSS[d.id], r: d.kind === 'cube' ? 0.04 : 0.038, h: 0.08,
      pos: new THREE.Vector3(), yaw: 0, vy: 0, state: 'rest', on: null, mesh, shadow, def: d });
  }
}
function layoutObjects(spots) {            // spots: id -> {x, z, yaw}; stacked objects follow their base
  for (const o of objs) if (!o.def.on) { const s = spots[o.id]; o.pos.set(s.x, o.h / 2, s.z); o.yaw = s.yaw || 0; o.on = null; }
  for (const o of objs) if (o.def.on) { const b = objById(o.def.on); o.pos.set(b.pos.x, b.pos.y + b.h / 2 + o.h / 2, b.pos.z); o.yaw = b.yaw; o.on = b.id; }
  for (const o of objs) { o.state = 'rest'; o.vy = 0; }
}
const homeSpots = () => Object.fromEntries(level.objects.filter((d) => !d.on).map((d) => [d.id, { x: d.x, z: d.z, yaw: 0 }]));
function randomSpots() {
  const out = {}, placed = [];
  for (const d of level.objects) {
    if (d.on) continue;
    let best = null;
    for (let tries = 0; tries < 400 && !best; tries++) {
      const r = 0.33 + rnd() * 0.33, a = (rnd() * 2 - 1) * 1.45, x = r * Math.sin(a), z = r * Math.cos(a);
      if (Math.abs(x) > 0.58 || z < -0.04 || z > 0.72) continue;
      if (pads.some((p) => Math.max(Math.abs(x - p.x), Math.abs(z - p.z)) < PAD_HALF + 0.085)) continue;
      if (placed.some((q) => Math.hypot(x - q.x, z - q.z) < 0.15)) continue;
      best = { x, z, yaw: d.kind === 'cube' ? (rnd() * 2 - 1) * 0.6 : 0 };
    }
    best = best || { x: d.x, z: d.z, yaw: 0 }; placed.push(best); out[d.id] = best;
  }
  return out;
}
function shufflePads() {
  const idx = PAD_SLOTS.map((_, i) => i);
  for (let i = idx.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [idx[i], idx[j]] = [idx[j], idx[i]]; }
  if (pads.every((p, i) => idx[i] === PAD_SLOTS.findIndex((s) => s[0] === p.x && s[1] === p.z))) idx.reverse();
  pads.forEach((p, i) => movePad(p, PAD_SLOTS[idx[i]][0], PAD_SLOTS[idx[i]][1]));
}
const resetPads = () => pads.forEach((p, i) => movePad(p, PAD_SLOTS[i][0], PAD_SLOTS[i][1]));

// highest surface under a footprint of radius r at (x, z), ignoring `skip`
function supportUnder(x, z, r, skip) {
  let top = 0, by = null;
  for (const p of objs) {
    if (p === skip || p.state === 'held') continue;
    if (Math.hypot(x - p.pos.x, z - p.pos.z) < (r + p.r) * 0.92 && p.pos.y + p.h / 2 > top) { top = p.pos.y + p.h / 2; by = p; }
  }
  return { top, by };
}
function physics(dt) {
  for (const o of objs) {
    if (o.state !== 'free') continue;
    let support = 0, sup = null, px = 0, pz = 0;
    const bot = o.pos.y - o.h / 2;
    for (const p of objs) {
      if (p === o || p.state === 'held') continue;
      let dx = o.pos.x - p.pos.x, dz = o.pos.z - p.pos.z; const d = Math.hypot(dx, dz);
      if (d >= (o.r + p.r) * 0.92) continue;
      const pTop = p.pos.y + p.h / 2;
      if (d < 1e-4) { dx = 1; dz = 0; } else { dx /= d; dz /= d; }
      if (pTop <= bot + 0.006) {                              // p is underneath
        if (pTop > support) { support = pTop; sup = d <= 0.8 * p.r ? p : null; }
        if (d > 0.8 * p.r) { px += dx; pz += dz; }            // not enough overlap: slide off
      } else if (p.pos.y - p.h / 2 < o.pos.y + o.h / 2) { px += dx; pz += dz; }   // side by side: push apart
    }
    const pushing = px !== 0 || pz !== 0;
    if (pushing) { const l = Math.hypot(px, pz) || 1; o.pos.x += (px / l) * 0.45 * dt; o.pos.z += (pz / l) * 0.45 * dt; }
    o.pos.x = clamp(o.pos.x, TABLE.x0 + o.r, TABLE.x1 - o.r); o.pos.z = clamp(o.pos.z, TABLE.z0 + o.r, TABLE.z1 - o.r);
    o.vy -= 9.81 * dt; o.pos.y += o.vy * dt;
    if (o.pos.y - o.h / 2 <= support) {
      o.pos.y = support + o.h / 2;
      if (o.vy < -0.9) { o.vy = -o.vy * 0.22; sfx('thunk'); }
      else { if (o.vy < -0.15) sfx('thunk'); o.vy = 0; if (!pushing) { o.state = 'rest'; o.on = sup ? sup.id : null; } }
    }
  }
}

// ------------------------------------------------------------------ game state
let level = LEVELS[0], levelIndex = 0, mode = 'teach';
let steps = [], program = [], demos = 0, streak = 0, score = 0, solved = false, result = null, runStep = -1, stepMarks = [];
const q = HOME_Q.slice(); const tgt = { x: 0, y: HOVER, z: 0.42, yaw: 0 }; const want = { x: 0, z: 0.42 };
let grip = OPEN, held = null, heldRel = null, pending = null, task = null, DT = 1 / 60, ikErr = 0, lock = null;
const toolYaw = () => q[0] - q[5];
const store = { get: (k, d) => { try { return JSON.parse(localStorage.getItem('tta.' + k)) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem('tta.' + k, JSON.stringify(v)); } catch { /* private mode */ } } };
let muted = store.get('muted', false);

// ------------------------------------------------------------------ sound (synthesised, no files)
let ac = null;
function audioOn() { if (!ac) { try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch { ac = null; } } if (ac && ac.state === 'suspended') ac.resume(); }
function beep(f, d, type = 'square', v = 0.05, f2 = 0, when = 0) {
  if (muted || !ac || ac.state !== 'running') return;
  const t = ac.currentTime + when, o = ac.createOscillator(), g = ac.createGain();
  o.type = type; o.frequency.setValueAtTime(f, t); if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + d);
  g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
  o.connect(g).connect(ac.destination); o.start(t); o.stop(t + d + 0.03);
}
function sfx(name) {
  if (name === 'grip') { beep(880, 0.05); beep(1320, 0.06, 'square', 0.04, 0, 0.05); }
  else if (name === 'release') beep(520, 0.09, 'triangle', 0.08, 260);
  else if (name === 'thunk') beep(150, 0.1, 'sine', 0.2, 60);
  else if (name === 'miss') beep(210, 0.16, 'sawtooth', 0.04, 120);
  else if (name === 'step') beep(660, 0.05, 'triangle', 0.05);
  else if (name === 'win') [523, 659, 784, 1047].forEach((f, i) => beep(f, 0.16, 'square', 0.05, 0, i * 0.09));
  else if (name === 'fail') { beep(300, 0.25, 'sawtooth', 0.05, 140); beep(200, 0.3, 'sawtooth', 0.05, 90, 0.2); }
  else if (name === 'ui') beep(990, 0.03, 'square', 0.03);
}

// ------------------------------------------------------------------ motion primitives (generators stepped once per frame)
function* moveTo(goal, speed = 0.55) {
  const s = { ...tgt }, g = { ...s, ...goal };
  const dist = Math.hypot(g.x - s.x, g.y - s.y, g.z - s.z);
  const T = Math.max((dist / speed) * 1.5, Math.abs(g.yaw - s.yaw) / 2.6, 0.08);
  for (let t = 0; t < T;) {
    yield; t += DT; const u = Math.min(1, t / T), e = u * u * u * (10 - 15 * u + 6 * u * u);   // minimum jerk
    tgt.x = s.x + (g.x - s.x) * e; tgt.y = s.y + (g.y - s.y) * e; tgt.z = s.z + (g.z - s.z) * e; tgt.yaw = s.yaw + (g.yaw - s.yaw) * e;
  }
  for (let n = 0; n < 40 && ikErr > 0.0012; n++) yield;      // let the joints settle on the target
}
function* gripTo(w, T = 0.16) { const s = grip; for (let t = 0; t < T;) { yield; t += DT; grip = s + (w - s) * Math.min(1, t / T); } }
function* wait(T) { for (let t = 0; t < T; t += DT) yield; }

// Pick `o` with the tool at (x, z, yaw). Returns the grasp as seen from the object frame.
function* doPick(o, x, z, yaw, dy = 0, speed) {
  yield* moveTo({ x, z, yaw, y: HOVER }, speed);
  setPhase('DESCEND'); yield* moveTo({ y: o.pos.y + dy }, speed);
  setPhase('GRASP'); yield* gripTo(o.r * 2 - 0.002);
  fk(q); const ty = toolYaw();
  const [ox, oz] = rotY(o.pos.x - K.tcp.x, o.pos.z - K.tcp.z, -ty);
  held = o; heldRel = { x: ox, z: oz, y: o.pos.y - K.tcp.y, yaw: o.yaw - ty };
  const [gx, gz] = rotY(K.tcp.x - o.pos.x, K.tcp.z - o.pos.z, -o.yaw);
  const grasp = { dx: gx, dz: gz, dy: K.tcp.y - o.pos.y, yaw: wrapPi(ty - o.yaw) };
  o.state = 'held'; o.on = null; sfx('grip');
  setPhase('LIFT'); yield* moveTo({ y: HOVER }, speed);
  return grasp;
}
// Put the held object down so that its centre lands on (ox, oz) with yaw oyaw.
function* doPlace(ox, oz, oyaw, psi, speed) {
  const o = held, [rx, rz] = rotY(heldRel.x, heldRel.z, psi);
  yield* moveTo({ x: ox - rx, z: oz - rz, yaw: psi, y: HOVER }, speed);
  setPhase('PLACE');
  const sup = supportUnder(o.pos.x, o.pos.z, o.r, o);
  yield* moveTo({ y: sup.top + o.h / 2 + 0.004 - heldRel.y }, speed);
  held = null; heldRel = null; o.state = 'free'; o.vy = 0; sfx('release');
  yield* gripTo(OPEN);
  for (let t = 0; t < 2.5 && o.state !== 'rest'; t += DT) yield;
  setPhase('RETREAT'); yield* moveTo({ y: HOVER }, speed);
  return o;
}
function* doMiss(x, z) {
  const sup = supportUnder(x, z, 0.06, null);
  yield* moveTo({ y: sup.top + 0.04 }); yield* gripTo(0.03); sfx('miss'); yield* wait(0.08); yield* gripTo(OPEN); yield* moveTo({ y: HOVER });
}

// ------------------------------------------------------------------ teach mode
function pickable(x, z) {
  let best = null;
  for (const o of objs) {
    if (o.state !== 'rest' || objs.some((p) => p.on === o.id)) continue;
    const d = Math.hypot(o.pos.x - x, o.pos.z - z);
    if (d < 0.05 && (!best || o.pos.y > best.pos.y + 0.01 || (Math.abs(o.pos.y - best.pos.y) <= 0.01 && d < best.d))) best = Object.assign(o, { d });
  }
  return best;
}
function* teachPick() {
  fk(q); const x = K.tcp.x, z = K.tcp.z, o = pickable(x, z);
  if (!o) { yield* doMiss(x, z); return; }
  const nat = natYaw(o.pos.x, o.pos.z);
  const yaw = o.kind === 'cube' ? nearestStep(o.yaw, nat, Math.PI / 2) : nat;         // fingers square to the faces
  let [lx, lz] = rotY(x - o.pos.x, z - o.pos.z, -yaw);                                // closing fingers centre the object
  lx = 0; lz = clamp(lz, -0.012, 0.012);
  const [wx, wz] = rotY(lx, lz, yaw);
  pending = { obj: o.id, grasp: yield* doPick(o, o.pos.x + wx, o.pos.z + wz, yaw) };
}
function* teachPlace() {
  const o = held, sup = supportUnder(o.pos.x, o.pos.z, o.r, o);
  const frameYaw = sup.by ? sup.by.yaw : 0;
  const oyaw = o.kind === 'cube' ? nearestStep(frameYaw, o.yaw, Math.PI / 2) : o.yaw;  // set it down square
  yield* doPlace(o.pos.x, o.pos.z, oyaw, oyaw - heldRel.yaw);
  steps.push(makeStep(o, pending.grasp)); pending = null; sfx('step');
}
function makeStep(o, grasp) {
  let target, fx, fz, fyaw;
  const base = o.on && objById(o.on), pad = padOf(o);
  if (base) { target = { type: 'on', id: base.id }; fx = base.pos.x; fz = base.pos.z; fyaw = base.yaw; }
  else if (pad) { const p = padById(pad); target = { type: 'pad', id: pad }; fx = p.x; fz = p.z; fyaw = 0; }
  else { target = { type: 'table', x: o.pos.x, z: o.pos.z }; fx = o.pos.x; fz = o.pos.z; fyaw = 0; }
  const [dx, dz] = rotY(o.pos.x - fx, o.pos.z - fz, -fyaw);
  return { obj: o.id, target, grasp, place: { dx, dz, yaw: wrapPi(o.yaw - fyaw) } };
}
function toggleGrip() {
  audioOn();
  if (mode !== 'teach' || task) return;
  task = held ? teachPlace() : teachPick();
}
function afterTask() {
  want.x = tgt.x; want.z = tgt.z; if (drag) rebaseDrag();
  setPhase(''); renderAll();
}

// ------------------------------------------------------------------ the robot: execute the learned program by re-planning
const targetText = (t) => (t.type === 'pad' ? `pad ${t.id}` : t.type === 'on' ? `${objById(t.id).name}` : 'table spot');
const stepText = (s) => `${objById(s.obj).name} ${s.target.type === 'on' ? 'onto' : 'to'} ${targetText(s.target)}`;
const cm = (v) => { const c = Math.round(v * 1000) / 10; return (c < 0 ? '-' : '+') + Math.abs(c).toFixed(1); };
const stepCode = (s) => `pick(${s.obj}) place(${s.target.type === 'on' ? 'on ' + s.target.id : s.target.type === 'pad' ? 'pad ' + s.target.id : 'table'}) offset ${cm(s.place.dx)} ${cm(s.place.dz)} cm`;
const targetKey = (t) => (t.type === 'table' ? 'table' : `${t.type}:${t.id}`);

function* robotStep(s, speed) {
  const o = objById(s.obj);
  if (objs.some((p) => p.on === o.id)) return `the ${o.name} had something on top of it`;
  setPhase('APPROACH');
  const [wx, wz] = rotY(s.grasp.dx, s.grasp.dz, o.yaw), x = o.pos.x + wx, z = o.pos.z + wz;
  const yaw = nearestStep(o.yaw + s.grasp.yaw, natYaw(x, z), Math.PI);                 // the gripper is symmetric
  yield* doPick(o, x, z, yaw, s.grasp.dy, speed);
  setPhase('TRANSFER');
  const t = s.target; let fx, fz, fyaw = 0;
  if (t.type === 'pad') { const p = padById(t.id); fx = p.x; fz = p.z; }
  else if (t.type === 'on') { const b = objById(t.id); fx = b.pos.x; fz = b.pos.z; fyaw = b.yaw; }
  else { fx = t.x; fz = t.z; }
  const [px, pz] = rotY(s.place.dx, s.place.dz, fyaw), ox = fx + px, oz = fz + pz, oyaw = fyaw + s.place.yaw;
  const [hx, hz] = rotY(heldRel.x, heldRel.z, natYaw(ox, oz));
  const nat = natYaw(ox - hx, oz - hz);
  const psi = o.kind === 'cube' ? nearestStep(oyaw - heldRel.yaw, nat, Math.PI / 2) : nat;
  const sup = supportUnder(ox, oz, o.r, o);
  ghost.visible = true; ghost.position.set(ox, sup.top + o.h / 2, oz); ghost.rotation.y = oyaw;
  yield* doPlace(ox, oz, oyaw, psi, speed);
  ghost.visible = false;
  const got = o.on ? `on:${o.on}` : padOf(o) ? `pad:${padOf(o)}` : 'table';
  if (got !== targetKey(t)) return `the ${o.name} did not end up ${t.type === 'on' ? 'on the' : 'on'} ${targetText(t)}`;
  return null;
}
function* robotRun(kind) {
  const speed = 0.62; let fail = null; const order = [];
  yield* wait(0.5);
  for (let i = 0; i < program.length && !fail; i++) {
    runStep = i; renderTimeline(); sfx('step');
    fail = yield* robotStep(program[i], speed);
    stepMarks[i] = fail ? 'fail' : 'done';
    if (!fail) order.push({ obj: program[i].obj, target: targetKey(program[i].target) });
  }
  ghost.visible = false; runStep = -1; setPhase('HOME');
  if (held) { held.state = 'free'; held.vy = 0; held = null; heldRel = null; grip = OPEN; }
  yield* moveTo({ x: 0, z: 0.42, y: HOVER, yaw: 0 }, 0.7);
  for (let t = 0; t < 2 && objs.some((o) => o.state !== 'rest'); t += DT) yield;
  const goal = fail ? { ok: false, reason: fail } : level.check();
  result = { ok: goal.ok, kind, reason: goal.reason || '', order };
  if (goal.ok) {
    if (kind === 'repeat') solved = true;
    if (kind === 'challenge') streak++;
    if (solved) { score = Math.max(100, 1000 - 200 * (demos - 1) - 60 * Math.max(0, program.length - level.par) + 150 * streak); const best = store.get('best' + levelIndex, 0); if (score > best) store.set('best' + levelIndex, score); }
    sfx('win');
  } else { if (kind !== 'repeat') streak = 0; sfx('fail'); }
  mode = 'result';
}
function startRun(kind) {
  if (task || !program.length) return;
  audioOn(); mode = 'robot'; result = null; stepMarks = []; runStep = -1;
  if (kind === 'repeat') { resetPads(); layoutObjects(homeSpots()); }
  else { if (kind === 'challenge') shufflePads(); else if (!solved) resetPads(); layoutObjects(randomSpots()); }
  held = null; heldRel = null; grip = OPEN; pending = null;
  task = robotRun(kind); renderAll();
}
function teachDone() { if (task || mode !== 'teach' || !steps.length || held) return; demos++; program = JSON.parse(JSON.stringify(steps)); sfx('ui'); startRun('repeat'); }
function teachAgain() {
  if (task) return;
  mode = 'teach'; steps = []; program = []; result = null; stepMarks = []; streak = 0; pending = null; held = null; heldRel = null; grip = OPEN;
  resetPads(); layoutObjects(homeSpots()); goHome(); renderAll();
}
function goHome() { for (let i = 0; i < N; i++) q[i] = HOME_Q[i]; tgt.x = 0; tgt.z = 0.42; tgt.y = HOVER; tgt.yaw = 0; want.x = 0; want.z = 0.42; ik(q, tgt.x, tgt.y, tgt.z, tgt.yaw, 60); }
function setLevel(i) {
  if (task) return;
  levelIndex = i; level = LEVELS[i]; demos = 0; streak = 0; score = 0; solved = false;
  buildPads(level); buildObjects(level); teachAgain(); fitCamera();
}

// ------------------------------------------------------------------ HUD
let phase = '';
function setPhase(p) { phase = p; renderStatus(); }
function renderStatus() {
  const st = $('status');
  if (mode === 'robot') st.textContent = runStep >= 0 ? `STEP ${runStep + 1}/${program.length} · ${phase}` : phase || 'PLANNING';
  else if (mode === 'teach') st.textContent = phase ? phase : held ? `HOLDING ${held.name.toUpperCase()}` : '';
  else st.textContent = '';
}
function renderTimeline() {
  const list = mode === 'teach' ? steps : program, tl = $('timeline');
  $('strip-title').textContent = mode === 'teach' ? 'DEMONSTRATION · WHAT I RECORD' : 'LEARNED PROGRAM · WHAT THE ROBOT RUNS';
  $('strip-info').textContent = `DEMOS ${demos}${streak ? ' · STREAK ' + streak : ''}`;
  tl.innerHTML = '';
  if (!list.length) { const li = document.createElement('li'); li.className = 'empty'; li.textContent = 'No steps yet. Pick something up and put it on a pad.'; tl.append(li); return; }
  list.forEach((s, i) => {
    const li = document.createElement('li'); li.dataset.obj = s.obj; li.dataset.target = targetKey(s.target);
    if (mode !== 'teach') li.className = i === runStep ? 'now' : stepMarks[i] || '';
    const dot = document.createElement('i'); dot.style.background = objById(s.obj).css;
    const b = document.createElement('b'); b.textContent = `${i + 1}. ${stepText(s)}`;
    const sm = document.createElement('small'); sm.textContent = stepCode(s);
    li.append(dot, b, sm); tl.append(li);
  });
  const cur = tl.querySelector('.now') || tl.lastElementChild; if (cur) tl.scrollLeft = Math.max(0, cur.offsetLeft - 20);
}
function button(label, cls, fn, disabled) { const b = document.createElement('button'); b.className = 'btn ' + cls; b.textContent = label; b.disabled = !!disabled; b.dataset.act = label.toLowerCase().replace(/[^a-z]+/g, '-'); b.addEventListener('click', fn); return b; }
function renderButtons() {
  const box = $('buttons'); box.innerHTML = '';
  if (mode === 'teach') box.append(button('START OVER', 'ghost', teachAgain, !!task || (!steps.length && !held)), button('TEACH DONE', 'primary', teachDone, !!task || !steps.length || !!held));
  else if (mode === 'robot') box.append(button('ROBOT AT WORK...', 'ghost', () => {}, true));
  else {
    const next = levelIndex < LEVELS.length - 1;
    if (solved) {
      box.append(button('SHUFFLE', 'primary', () => startRun('shuffle')), button('CHALLENGE THE ROBOT', 'hot', () => startRun('challenge')));
      if (next) box.append(button('NEXT LEVEL', '', () => setLevel(levelIndex + 1)));
      box.append(button('TEACH AGAIN', 'ghost', teachAgain));
    } else box.append(button('TEACH AGAIN', 'primary', teachAgain));
  }
}
function renderResult() {
  const box = $('result'), share = $('share');
  if (mode !== 'result' || !result) { box.hidden = true; share.hidden = true; return; }
  box.hidden = false; box.className = 'result' + (result.ok ? '' : ' bad'); box.innerHTML = '';
  const span = document.createElement('span'); let text;
  if (result.ok) {
    const stars = demos === 1 && program.length <= level.par ? 3 : demos <= 2 ? 2 : 1;
    span.className = 'stars'; span.textContent = '*'.repeat(stars) + '-'.repeat(3 - stars);
    text = result.kind === 'repeat' ? `Same order, goal met. The robot learned it from ${demos} demo${demos > 1 ? 's' : ''} and ${program.length} steps. Score ${score}. Now move things around.`
      : result.kind === 'shuffle' ? `Everything moved and it still did your ${program.length} steps in order. It re-planned, it did not replay. Score ${score}.`
      : `Pads moved too and it still won. Streak ${streak}. Score ${score}.`;
  } else {
    text = result.kind === 'repeat' ? `The robot copied your demo exactly, and the goal is not met: ${result.reason}. Teach it again.`
      : `The shuffle beat the robot: ${result.reason}. Table spots do not move with a shuffle. Pads and objects do.`;
  }
  box.append(span, document.createTextNode(text));
  share.hidden = !solved;
  $('share-text').textContent = `I taught a robot arm to ${level.task} in ${demos} demo${demos > 1 ? 's' : ''}. Score ${score}. Beat that: ${SITE}`;
}
function renderHud() {
  $('level-name').textContent = `LEVEL ${levelIndex + 1} · ${level.name}`;
  $('goal').textContent = level.goal;
  const tag = $('mode-tag');
  tag.textContent = mode === 'teach' ? 'TEACH' : mode === 'robot' ? 'ROBOT RUN' : result && result.ok ? 'SUCCESS' : 'FAILED';
  tag.className = 'mode' + (mode === 'robot' ? ' robot' : mode === 'result' && result && !result.ok ? ' bad' : '');
  const best = store.get('best' + levelIndex, 0);
  $('score').textContent = (score ? `SCORE ${score}` : `PAR ${level.par} STEPS`) + (best ? ` · BEST ${best}` : '');
  const gb = $('btn-grip'); gb.disabled = mode !== 'teach' || !!task; gb.textContent = held ? 'RELEASE' : 'GRIP'; gb.classList.toggle('hold', !!held);
  $('hint').textContent = mode === 'teach' ? (held ? 'Carry it over a pad or another object, then tap or press RELEASE.' : 'Drag to move the arm. Tap, GRIP or Space grabs what is under the ring.') : mode === 'robot' ? 'Hands off. The robot plans its own path from what you taught.' : '';
  [...$('levels').children].forEach((b, i) => b.classList.toggle('on', i === levelIndex));
  $('btn-mute').textContent = muted ? 'SND OFF' : 'SND ON';
}
function renderAll() { renderHud(); renderStatus(); renderTimeline(); renderButtons(); renderResult(); }

// ------------------------------------------------------------------ input
const ray = new THREE.Raycaster(), hoverPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -HOVER), _hit = new THREE.Vector3(), _ndc = new THREE.Vector2();
let drag = null; const keys = new Set();
function planeHit(cx, cy) {
  const r = canvas.getBoundingClientRect();
  _ndc.set(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(_ndc, camera);
  return ray.ray.intersectPlane(hoverPlane, _hit) ? { x: clamp(_hit.x, -3, 3), z: clamp(_hit.z, -3, 3) } : null;
}
function rebaseDrag() { const h = planeHit(drag.cx, drag.cy); if (h) { drag.hx = h.x; drag.hz = h.z; drag.wx = want.x; drag.wz = want.z; } }
canvas.addEventListener('pointerdown', (e) => {
  if (drag || (e.pointerType === 'mouse' && e.button !== 0)) return;
  audioOn(); e.preventDefault();
  drag = { id: e.pointerId, cx: e.clientX, cy: e.clientY, sx: e.clientX, sy: e.clientY, moved: false };
  rebaseDrag(); try { canvas.setPointerCapture(e.pointerId); } catch { /* synthetic pointer */ }
  canvas.classList.add('drag');
});
canvas.addEventListener('pointermove', (e) => {
  if (!drag || e.pointerId !== drag.id) return;
  drag.cx = e.clientX; drag.cy = e.clientY;
  if (Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 8) drag.moved = true;
  if (mode !== 'teach' || task || !drag.moved) return;
  const h = planeHit(e.clientX, e.clientY); if (!h || drag.hx === undefined) return;
  [want.x, want.z] = clampWS(drag.wx + h.x - drag.hx, drag.wz + h.z - drag.hz);
});
function endDrag(e) {
  if (!drag || e.pointerId !== drag.id) return;
  const tap = !drag.moved && e.type === 'pointerup'; drag = null; canvas.classList.remove('drag');
  if (tap) toggleGrip();
}
canvas.addEventListener('pointerup', endDrag); canvas.addEventListener('pointercancel', endDrag);
canvas.addEventListener('contextmenu', (e) => e.preventDefault());
window.addEventListener('keydown', (e) => {
  if (!$('how').hidden) { if (e.key === 'Escape') $('how').hidden = true; return; }
  if (e.target instanceof HTMLButtonElement && (e.key === ' ' || e.key === 'Enter')) return;
  if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); if (!e.repeat) toggleGrip(); }
  else if (/^Arrow|^[wasd]$/i.test(e.key)) { keys.add(e.key.toLowerCase()); e.preventDefault(); }
});
window.addEventListener('keyup', (e) => keys.delete(e.key.toLowerCase()));
window.addEventListener('blur', () => keys.clear());
// pointerdown, not click: instant on phones, and a tap right after a drag is never swallowed by the browser
$('btn-grip').addEventListener('pointerdown', (e) => { e.preventDefault(); toggleGrip(); });
$('btn-grip').addEventListener('click', (e) => { if (e.detail === 0) toggleGrip(); });   // keyboard activation
$('btn-mute').addEventListener('click', () => { muted = !muted; store.set('muted', muted); audioOn(); sfx('ui'); renderHud(); });
$('btn-how').addEventListener('click', () => { $('how').hidden = false; });
$('btn-how-close').addEventListener('click', () => { $('how').hidden = true; });
$('how').addEventListener('click', (e) => { if (e.target === $('how')) $('how').hidden = true; });
$('btn-copy').addEventListener('click', async () => {
  const text = $('share-text').textContent, b = $('btn-copy');
  try { if (navigator.share && matchMedia('(pointer:coarse)').matches) await navigator.share({ text }); else await navigator.clipboard.writeText(text); b.textContent = 'COPIED'; }
  catch { b.textContent = 'SELECT IT'; }
  setTimeout(() => { b.textContent = 'COPY'; }, 1500);
});
LEVELS.forEach((_, i) => { const b = document.createElement('button'); b.textContent = String(i + 1); b.setAttribute('aria-label', `Level ${i + 1}`); b.addEventListener('click', () => setLevel(i)); $('levels').append(b); });

// ------------------------------------------------------------------ camera fit and main loop
const FIT = [[TABLE.x0, 0, TABLE.z0], [TABLE.x1, 0, TABLE.z0], [TABLE.x0, 0, TABLE.z1], [TABLE.x1, 0, TABLE.z1], [0, 0.98, 0], [-0.45, 0.7, 0.2], [0.45, 0.7, 0.2], [-0.62, 0.35, 0.5], [0.62, 0.35, 0.5]];
function fitCamera() {
  const w = stage.clientWidth || 1, h = stage.clientHeight || 1;
  renderer.setSize(w, h, false); camera.aspect = w / h;
  const portrait = h > w * 1.05, el = (portrait ? 50 : 44) * Math.PI / 180;
  const look = new THREE.Vector3(0, 0.2, 0.3), dir = new THREE.Vector3(0, Math.sin(el), Math.cos(el));
  camera.fov = portrait ? 40 : 34;
  const topPad = Math.min(0.5, 150 / h), botPad = Math.min(0.4, 84 / h);                 // keep clear of the HUD text and GRIP
  const fits = (d) => {
    camera.position.copy(look).addScaledVector(dir, d); camera.lookAt(look); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
    return FIT.every((p, i) => { _v.fromArray(p).project(camera); return Math.abs(_v.x) < 0.95 && _v.y < (i === 4 ? 0.97 : 1 - topPad * (p[1] > 0.3 ? 0.4 : 0)) && _v.y > -1 + botPad * 0.5; });
  };
  let lo = 0.8, hi = 9;
  for (let i = 0; i < 22; i++) { const mid = (lo + hi) / 2; if (fits(mid)) hi = mid; else lo = mid; }
  fits(hi);
  if (ready) render();          // a resize clears the canvas, so draw again at once
}
let ready = false;
new ResizeObserver(fitCamera).observe(stage);

function step(dt) {
  DT = dt;
  if (task) { if (task.next().done) { task = null; afterTask(); } }
  else if (mode === 'teach') {
    let kx = 0, kz = 0;
    if (keys.has('arrowleft') || keys.has('a')) kx -= 1; if (keys.has('arrowright') || keys.has('d')) kx += 1;
    if (keys.has('arrowup') || keys.has('w')) kz -= 1; if (keys.has('arrowdown') || keys.has('s')) kz += 1;
    if (kx || kz) [want.x, want.z] = clampWS(want.x + kx * 0.45 * dt, want.z + kz * 0.45 * dt);
    const dx = want.x - tgt.x, dz = want.z - tgt.z, d = Math.hypot(dx, dz);
    if (d > 1e-5) { const m = Math.min(d, Math.min(1.4 * dt, d * Math.min(1, 14 * dt))); tgt.x += (dx / d) * m; tgt.z += (dz / d) * m; }
    tgt.y = HOVER;
    const dy = natYaw(tgt.x, tgt.z) - tgt.yaw; tgt.yaw += clamp(dy, -3 * dt, 3 * dt);
  }
  ikErr = ik(q, tgt.x, tgt.y, tgt.z, tgt.yaw, 5).pe;
  if (held) {
    const ty = toolYaw(), [wx, wz] = rotY(heldRel.x, heldRel.z, ty);
    held.pos.set(K.tcp.x + wx, K.tcp.y + heldRel.y, K.tcp.z + wz); held.yaw = ty + heldRel.yaw;
  }
  physics(dt);
}
function render() {
  poseArm(q, grip);
  for (const o of objs) {
    o.mesh.position.copy(o.pos); o.mesh.rotation.y = o.yaw;
    const sup = supportUnder(o.pos.x, o.pos.z, o.r * 0.6, o), gap = Math.max(0, o.pos.y - o.h / 2 - sup.top);
    o.shadow.position.set(o.pos.x, sup.top + 0.0035, o.pos.z); o.shadow.scale.setScalar(o.r * (1.25 + gap * 1.5));
    o.shadow.material.opacity = 0.55; o.shadow.visible = gap > 0.002 || sup.top < 0.01;
  }
  // reticle: where the gripper (or the held object) would come down
  const cx = held ? held.pos.x : K.tcp.x, cz = held ? held.pos.z : K.tcp.z;
  const cand = mode === 'teach' && !held && !task ? pickable(K.tcp.x, K.tcp.z) : null;
  if (cand !== lock) { if (lock) { lock.mesh.userData.edges.material.opacity = 0.5; lock.mesh.material.emissiveIntensity = 0.28; } lock = cand; if (lock) { lock.mesh.userData.edges.material.opacity = 1; lock.mesh.material.emissiveIntensity = 0.75; } }
  const sup = supportUnder(cx, cz, held ? held.r : 0.012, held), rr = held ? held.r * 1.35 : lock ? 0.062 : 0.03;
  reticle.position.set(cx, sup.top + 0.005, cz); reticle.scale.setScalar(rr);
  reticle.material.color.setHex(lock || (held && (sup.by || pads.some((p) => Math.abs(cx - p.x) <= PAD_HALF && Math.abs(cz - p.z) <= PAD_HALF))) ? 0xffffff : COL.cyan);
  const from = held ? held.pos.y - held.h / 2 : K.tcp.y - 0.03, pa = dropGeo.attributes.position;
  pa.setXYZ(0, cx, sup.top + 0.005, cz); pa.setXYZ(1, cx, Math.max(from, sup.top + 0.005), cz); pa.needsUpdate = true; dropLine.computeLineDistances();
  renderer.render(scene, camera);
}
let manual = false, last = performance.now();
function frame(now) {
  requestAnimationFrame(frame);
  if (manual) return;
  const dt = clamp((now - last) / 1000, 0.001, 0.05); last = now;
  step(dt); render();
}

// ------------------------------------------------------------------ test and capture hooks
function ikSweep() {
  let n = 0, maxErr = 0, maxRot = 0, minY = 9, fails = 0; const worst = [];
  for (let x = -0.6; x <= 0.601; x += 0.06) for (let z = -0.1; z <= 0.741; z += 0.06) {
    const r = Math.hypot(x, z); if (r < R_MIN || r > R_MAX) continue;
    for (const y of [0.04, 0.12, 0.2, HOVER]) for (const dyaw of [0, -0.75, 0.75]) {
      const qq = HOME_Q.slice(), res = ik(qq, x, y, z, natYaw(x, z) + dyaw, 150);
      n++; maxErr = Math.max(maxErr, res.pe); maxRot = Math.max(maxRot, res.re);
      const low = Math.min(...K.p.slice(1).map((p) => p.y)); minY = Math.min(minY, low);
      if (res.pe > 0.001 || res.re > 0.01 || low < 0.05) { fails++; if (worst.length < 5) worst.push({ x, y, z, dyaw, pe: res.pe, re: res.re, low }); }
    }
  }
  fk(q);
  return { n, fails, maxErr, maxRot, minJointY: minY, worst };
}
window.__game = {
  snapshot() {
    fk(q);
    return { level: levelIndex, mode, busy: !!task, demos, streak, score, solved, phase, holding: held ? held.id : null,
      tcp: [K.tcp.x, K.tcp.y, K.tcp.z], q: q.slice(), ikErr, grip,
      jointsMinY: Math.min(...K.p.slice(1).map((p) => p.y)),
      objects: objs.map((o) => ({ id: o.id, name: o.name, x: o.pos.x, y: o.pos.y, z: o.pos.z, yaw: o.yaw, state: o.state, on: o.on, pad: padOf(o) })),
      pads: pads.map((p) => ({ id: p.id, x: p.x, z: p.z, color: p.color })),
      steps: (mode === 'teach' ? steps : program).map((s) => ({ obj: s.obj, target: targetKey(s.target), text: stepText(s), code: stepCode(s) })),
      result };
  },
  project(x, y, z) { camera.updateMatrixWorld(); const r = canvas.getBoundingClientRect(); _v.set(x, y, z).project(camera); return { x: r.left + (_v.x + 1) / 2 * r.width, y: r.top + (1 - _v.y) / 2 * r.height }; },
  setManual(on) { manual = !!on; last = performance.now(); },
  advance(sec) { const n = Math.max(1, Math.round(sec * 60)); for (let i = 0; i < n; i++) step(1 / 60); render(); return n; },
  seed(n) { rngState = n >>> 0; },
  setLevel, ikSweep, HOVER,
};

// ------------------------------------------------------------------ boot
(async function boot() {
  try { await Promise.race([document.fonts.load('italic 40px "Barlow XB"'), new Promise((r) => setTimeout(r, 1200))]); } catch { /* fall back to system fonts */ }
  ready = true; setLevel(0); fitCamera(); step(1 / 60); render();
  $('boot').classList.add('gone'); window.__game.ready = true;
  requestAnimationFrame(frame);
})();
