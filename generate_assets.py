"""Builds the profile's two animated SVGs: the Omnitrix hero and the forms grid.

GitHub READMEs can't run CSS or JS, so everything is SMIL-animated SVG. The brand fonts
(Barlow Condensed, Share Tech Mono) are subset to the glyphs actually used and embedded,
so the images look like megazron.com everywhere without loading anything else.

Run:  python generate_assets.py      (needs fonttools + brotli + Pillow)
"""

import base64
import io
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
ASSETS, FONTS = ROOT / "assets", ROOT / "fonts"

VOID, FIELD, OMNI, CYAN, HAZARD = "#030d05", "#06180a", "#3dfa46", "#7ffcd5", "#ffb300"
CORE, INK, DIM, LINE = "#eafff0", "#b8e8c0", "#6aa876", "#1f7a2c"
DISP, DISP2, MONO = "BarlowXB", "BarlowSB", "ShareMono"

FORMS = [
    ("TWIN ARMS", "Multimodal dual-arm robot control", "7-DoF master mannequin teleoperates two Kinova Gen3 arms on a wearable platform",
     ["ROS 2", "KORTEX", "ISAAC LAB"], "MSc MAJOR PROJECT · IMPERIAL", "arms",
     "https://github.com/megazron/Multimodal-control-of-a-wearable-dual-arm-robotic-system-for-assisted-object-manipulation"),
    ("SAC PILOT", "Deep RL for assistive robotics", "Soft Actor-Critic agents learning multi-function assistive skills in MuJoCo",
     ["PyTorch", "SAC", "MuJoCo"], "DEEP RL · CONTINUOUS CONTROL", "brain",
     "https://github.com/megazron/SAC-for-Multi-Functional-Assistive-Robotics-in-MuJoCo"),
    ("AGENT NET", "Robot Agent Network for VLAs", "Benchmarked SmolVLA, OpenVLA, Octo and π0 on LIBERO — the Huawei R&D UK pipeline",
     ["VLA", "LIBERO", "GNN"], "HUAWEI R&D UK · 2026", "net",
     "https://github.com/megazron/Robot-Agent-Network-for-VLAs"),
    ("MIND DRIVE", "EEG-operated wheelchair", "Brain signals steer a wheelchair through an ML classifier on embedded hardware",
     ["EEG", "ML", "EMBEDDED"], "GERMAN PATENT DE202025101530U1", "mind",
     "https://github.com/megazron/eeg-operated-wheelchair"),
    ("DEBRIS HUNTER", "CanSat for space-debris detection", "LiDAR CanSat built and launched by a team of 8 — IEEE-AESS CanSat winner",
     ["LiDAR", "AVIONICS", "TELEMETRY"], "CANSAT 2022 · WINNER", "sat",
     "https://github.com/megazron/can-sat-for-debris-detection"),
    ("COAX EYE", "Coaxial surveillance drone", "Two-propeller coaxial drone for surveillance — Smart India Hackathon 2023 winner",
     ["DRONE", "CV", "CONTROL"], "SIH 2023 WINNER · DE PATENT", "drone",
     "https://github.com/megazron/autonmousdrone"),
]
STATS = [("53", "AWARDS"), ("10", "PATENTS + PAPERS"), ("03", "GERMAN PATENTS"), ("2×", "SIH WINNER"), ("800+", "DEVS MENTORED")]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def font_face(family, ttf, text):
    """Subset a font to exactly the characters in `text` and return an @font-face rule."""
    opts = subset.Options(); opts.flavor = "woff2"; opts.layout_features = ["kern", "liga"]; opts.name_IDs = []; opts.notdef_outline = True
    font = TTFont(FONTS / ttf)
    sub = subset.Subsetter(opts); sub.populate(text=text + " "); sub.subset(font)
    buf = io.BytesIO(); font.flavor = "woff2"; font.save(buf)
    return f"@font-face{{font-family:{family};src:url(data:font/woff2;base64,{base64.b64encode(buf.getvalue()).decode()}) format('woff2')}}"


def fonts_css(texts):
    return "".join(font_face(fam, ttf, texts[fam]) for fam, ttf in
                   [(DISP, "BarlowCondensed-ExtraBoldItalic.ttf"), (DISP2, "BarlowCondensed-SemiBoldItalic.ttf"), (MONO, "ShareTechMono-Regular.ttf")])


class Canvas:
    """Collects SVG markup and remembers which characters each font needs."""
    def __init__(self):
        self.parts, self.used = [], {DISP: "", DISP2: "", MONO: ""}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, fam, size, fill, anchor="start", ls=0, extra="", child=""):
        self.used[fam] += s
        self.add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{esc(s)}{child}</text>')


# ---------------------------------------------------------------- icons (48x48, line style)
def icon(kind, stroke, sw=2.2):
    a = f'fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"'
    return {
        "arms": f'<g {a}><path d="M8 40h32M18 40V30l-6-8 4-8M30 40V30l6-8-4-8"/><circle cx="12" cy="22" r="2.4"/><circle cx="36" cy="22" r="2.4"/><path d="M14 13l-3-4M16 13l2-5M34 13l3-4M32 13l-2-5"/></g>',
        "brain": f'<g {a}><path d="M24 10c-6-4-14 0-13 7-5 2-5 9 0 11-1 6 6 10 13 6 7 4 14 0 13-6 5-2 5-9 0-11 1-7-7-11-13-7z"/><path d="M24 10v26M17 20l7 4 7-4M17 30l7-6 7 6"/></g>',
        "net": f'<g {a}><circle cx="24" cy="24" r="5"/><circle cx="10" cy="12" r="3"/><circle cx="38" cy="12" r="3"/><circle cx="10" cy="36" r="3"/><circle cx="38" cy="36" r="3"/><path d="M13 14l7 7M35 14l-7 7M13 34l7-7M35 34l-7-7"/><circle cx="24" cy="24" r="1.6" fill="{stroke}"/></g>',
        "mind": f'<g {a}><path d="M16 40v-6c-5-3-7-8-6-13 1-7 7-11 14-11s12 5 12 11c0 2-1 4 0 6l3 4-4 1v4c0 2-2 3-4 3h-3v1"/><path d="M17 22h3l2-4 3 8 2-4h4"/></g>',
        "sat": f'<g {a}><rect x="17" y="14" width="14" height="22" rx="3"/><path d="M17 20H7v10h10M31 20h10v10H31M24 14V7M20 7h8M21 26h6"/></g>',
        "drone": f'<g {a}><rect x="18" y="20" width="12" height="9" rx="3"/><path d="M18 22l-8-6M30 22l8-6M18 27l-8 6M30 27l8 6M4 14h12M32 14h12M4 35h12M32 35h12"/><circle cx="24" cy="24.5" r="1.6" fill="{stroke}"/></g>',
    }[kind]


def common_defs(c, w, h):
    c.add(f'''<defs>
<radialGradient id="field" cx="72%" cy="42%" r="85%"><stop offset="0" stop-color="#0b3313"/><stop offset=".5" stop-color="{FIELD}"/><stop offset="1" stop-color="{VOID}"/></radialGradient>
<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{OMNI}" stroke-opacity=".06"/></pattern>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" fill-opacity=".3"/></pattern>
<pattern id="hz" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><rect width="6" height="12" fill="{OMNI}" fill-opacity=".6"/><animateTransform attributeName="patternTransform" type="translate" from="0 0" to="12 0" additive="sum" dur="1.1s" repeatCount="indefinite"/></pattern>
<linearGradient id="sweep" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{OMNI}" stop-opacity="0"/><stop offset=".5" stop-color="{OMNI}" stop-opacity=".16"/><stop offset="1" stop-color="{OMNI}" stop-opacity="0"/></linearGradient>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="glowlg" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="10" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="{w}" height="{h}" fill="url(#field)"/><rect width="{w}" height="{h}" fill="url(#grid)"/>''')


def notched(x, y, w, h, n, fill, stroke, sw=1.5, extra=""):
    p = f"M{x+n} {y}H{x+w}V{y+h-n}L{x+w-n} {y+h}H{x}V{y+n}Z"
    return f'<path d="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def brackets(c, x, y, w, h, s=18, col=OMNI):
    c.add(f'<g fill="none" stroke="{col}" stroke-width="2.2"><path d="M{x} {y+s}V{y}H{x+s}M{x+w-s} {y}H{x+w}V{y+s}M{x+w} {y+h-s}V{y+h}H{x+w-s}M{x+s} {y+h}H{x}V{y+h-s}"/></g>')


def holo_avatar(size=164):
    """Green duotone hologram of the avatar, small enough to embed."""
    img = Image.open(ASSETS / "avatar.jpg").convert("L")
    img = ImageOps.fit(img, (size, size))
    img = ImageOps.autocontrast(img, cutoff=2)
    duo = ImageOps.colorize(img, black="#020a03", mid="#1f8a2c", white="#d8ffe0")
    buf = io.BytesIO(); duo.save(buf, "JPEG", quality=62, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- the hero
def hero():
    W, H = 1200, 540
    c = Canvas(); common_defs(c, W, H)
    # top rail
    c.add(f'<rect x="0" y="0" width="{W}" height="6" fill="url(#hz)"/>')
    c.text(48, 40, "// MEGAZRON  ·  OMNITRIX v26  ·  ONLINE", MONO, 13, DIM, ls=1.6)
    c.text(W - 48, 40, "LONDON · 51.4988N 0.1749W", MONO, 13, DIM, anchor="end", ls=1.6)
    # left: identity
    greet = ["ASSALAMU ALAIKUM", "HELLO", "NAMASTE", "NAMASKAR"]
    for i, g in enumerate(greet):
        vals = ";".join("1" if k == i else "0" for k in range(len(greet))) + ";" + ("1" if i == 0 else "0")
        c.text(64, 108, g, DISP, 30, OMNI, ls=1, extra='filter="url(#glow)" opacity="0"',
               child=f'<animate attributeName="opacity" values="{vals}" keyTimes="0;.25;.5;.75;1" calcMode="discrete" dur="10s" repeatCount="indefinite"/>')
    c.text(64, 132, "I AM", MONO, 13, DIM, ls=4)
    c.text(62, 200, "GAUS MOHIUDDIN", DISP, 70, CORE, ls=1)
    c.text(62, 268, "SAYYAD", DISP, 70, CORE, ls=1, child=f'<tspan fill="{OMNI}" font-size="70">.</tspan>')
    c.text(64, 306, "ROBOTICS SOFTWARE ENGINEER", DISP2, 27, INK, ls=1.5)
    c.add(f'<rect x="64" y="322" width="470" height="2" fill="{OMNI}" opacity=".85"/><rect x="64" y="322" width="90" height="2" fill="{CORE}"><animate attributeName="x" values="64;444;64" dur="6s" repeatCount="indefinite"/></rect>')
    c.text(64, 350, "MSc ROBOTICS ’26 @ IMPERIAL  ·  EX HUAWEI R&D UK  ·  EX ISRO  ·  EX IIT BOMBAY", MONO, 13, INK, ls=.6)
    c.text(64, 402, "BUILDS THE IMPOSSIBLE", DISP, 34, CORE, ls=.5, child=f'<tspan fill="{OMNI}" filter="url(#glow)"> WITH SCIENCE…</tspan>')
    c.text(66, 428, "BECAUSE SCIENCE WORKS — 10 BILLION PERCENT!", MONO, 12.5, DIM, ls=2.4)
    # chevron status pill
    c.add(f'<path d="M64 452h300l14 16-14 16H64l14-16z" fill="{OMNI}"/>')
    c.text(221, 473, "OPEN TO ROBOTICS ROLES · SEP 2026", DISP, 17, VOID, anchor="middle", ls=1)
    c.add(f'<path d="M388 452h170l14 16-14 16H388l14-16z" fill="none" stroke="{OMNI}" stroke-width="1.6"/>')
    c.text(479, 473, "MEGAZRON.COM", DISP, 17, OMNI, anchor="middle", ls=1.5)

    # right: the dial
    cx, cy, R = 900, 236, 150
    c.add(f'<circle cx="{cx}" cy="{cy}" r="{R+40}" fill="{OMNI}" opacity=".05" filter="url(#glowlg)"/>')
    c.add(f'<g opacity=".55"><circle cx="{cx}" cy="{cy}" r="{R+26}" fill="none" stroke="{OMNI}" stroke-width="1.2" stroke-dasharray="2 9"><animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="60s" repeatCount="indefinite"/></circle></g>')
    c.add(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{LINE}" stroke-width="7"/>')
    c.add(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{OMNI}" stroke-width="2" opacity=".9"/>')
    c.add(f'<g><circle cx="{cx}" cy="{cy}" r="{R-24}" fill="none" stroke="{OMNI}" stroke-width="3" stroke-dasharray="6 14" opacity=".55"><animateTransform attributeName="transform" type="rotate" from="360 {cx} {cy}" to="0 {cx} {cy}" dur="40s" repeatCount="indefinite"/></circle></g>')
    # six form nodes around the ring
    step, hold = 2.6, 2.2
    N = len(FORMS); T = N * step
    import math
    for i, f in enumerate(FORMS):
        a = math.radians(-90 + i * 60); x, y = cx + R * math.cos(a), cy + R * math.sin(a)
        c.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="27" fill="{VOID}" stroke="{OMNI}" stroke-width="2"/>')
        c.add(f'<g transform="translate({x - 15:.1f} {y - 15:.1f}) scale(.625)">{icon(f[5], OMNI)}</g>')
    # selector that clicks from form to form
    vals, kts = [], []
    for i in range(N):
        t0 = i * step / T; t1 = (i * step + hold) / T
        vals += [f"{i * 60} {cx} {cy}", f"{i * 60} {cx} {cy}"]; kts += [t0, t1]
    vals.append(f"{N * 60} {cx} {cy}"); kts.append(1)
    kt = ";".join(f"{k:.4f}" for k in kts)
    c.add(f'<g><circle cx="{cx}" cy="{cy - R}" r="35" fill="none" stroke="{OMNI}" stroke-width="3.2" filter="url(#glow)"/>'
          f'<path d="M{cx - 8} {cy - R - 46}l8 9 8-9z" fill="{OMNI}"/>'
          f'<animateTransform attributeName="transform" type="rotate" values="{";".join(vals)}" keyTimes="{kt}" dur="{T}s" repeatCount="indefinite" calcMode="spline" keySplines="{";".join(["0 0 1 1", ".6 0 .2 1"] * N)}"/></g>')
    # hologram core
    c.add(f'<defs><clipPath id="holo"><circle cx="{cx}" cy="{cy - 6}" r="70"/></clipPath></defs>')
    c.add(f'<path d="M{cx - 64} {cy + 78}L{cx - 22} {cy + 8}h44l42 70z" fill="{OMNI}" opacity=".10"/>')
    c.add(f'<ellipse cx="{cx}" cy="{cy + 80}" rx="66" ry="9" fill="{OMNI}" opacity=".55" filter="url(#glow)"/>')
    c.add(f'<g clip-path="url(#holo)"><image href="{holo_avatar()}" x="{cx - 70}" y="{cy - 76}" width="140" height="140" opacity=".92"><animate attributeName="opacity" values=".92;.78;.92;.92;.6;.92" keyTimes="0;.04;.08;.6;.62;1" dur="5s" repeatCount="indefinite"/></image>'
          f'<rect x="{cx - 70}" y="{cy - 76}" width="140" height="140" fill="url(#scan)"/>'
          f'<rect x="{cx - 70}" y="{cy - 120}" width="140" height="40" fill="url(#sweep)"><animate attributeName="y" values="{cy - 120};{cy + 60}" dur="3s" repeatCount="indefinite"/></rect></g>')
    c.add(f'<circle cx="{cx}" cy="{cy - 6}" r="70" fill="none" stroke="{OMNI}" stroke-width="2.4" filter="url(#glow)"/>')
    # form readout below the dial, synced with the selector
    for i, f in enumerate(FORMS):
        on0 = (i * step + .35) / T
        vals = "0;1;0" if i else "1;0"
        kts = f"0;{on0:.4f};{min(.9999, (i * step + step) / T):.4f}" if i else f"0;{step / T:.4f}"
        anim = f'<animate attributeName="opacity" values="{vals}" keyTimes="{kts}" calcMode="discrete" dur="{T}s" repeatCount="indefinite"/>'
        c.add(f'<g opacity="{1 if i == 0 else 0}">{anim}')
        c.text(cx, cy + R + 66, f"FORM 0{i + 1}  //  {f[0]}", DISP, 26, OMNI, anchor="middle", ls=2, extra='filter="url(#glow)"')
        c.text(cx, cy + R + 89, f[4], MONO, 12.5, INK, anchor="middle", ls=1.6)
        c.add("</g>")
    # stat rail
    c.add(f'<rect x="0" y="{H - 46}" width="{W}" height="46" fill="{VOID}" opacity=".7"/><rect x="0" y="{H - 46}" width="{W}" height="1.5" fill="{LINE}"/>')
    sw = W / len(STATS)
    for i, (n, l) in enumerate(STATS):
        x = sw * i + sw / 2
        c.text(x - 8, H - 15, n, DISP, 26, OMNI, anchor="end", ls=.5)
        c.text(x - 2, H - 18, l, MONO, 11.5, INK, ls=1.4)
        if i: c.add(f'<rect x="{sw * i:.0f}" y="{H - 36}" width="1" height="26" fill="{LINE}"/>')
    c.add(f'<rect width="{W}" height="{H}" fill="url(#scan)" opacity=".5"/>')
    brackets(c, 18, 18, W - 36, H - 36)
    return finish(c, W, H, "Gaus Mohiuddin Sayyad — Robotics Software Engineer. Builds the impossible with science.")


# ---------------------------------------------------------------- the forms grid
def forms():
    W, H = 1200, 600
    c = Canvas(); common_defs(c, W, H)
    c.add(f'<rect x="0" y="0" width="{W}" height="6" fill="url(#hz)"/>')
    c.text(48, 52, "SELECT A FORM", DISP, 30, CORE, ls=2)
    c.text(274, 52, "// FLAGSHIP BUILDS — EACH ONE A DIFFERENT KIND OF ROBOT", MONO, 13, DIM, ls=1.5)
    c.text(W - 48, 52, "06 FORMS UNLOCKED", MONO, 13, OMNI, anchor="end", ls=1.5)
    cols, gx, gy, tw, th = 3, 36, 78, 362, 240
    for i, f in enumerate(FORMS):
        col, row = i % cols, i // cols
        x, y = 36 + col * (tw + 21), gy + row * (th + 24)
        c.add(notched(x, y, tw, th, 22, "#041407", LINE))
        c.add(f'<path d="M{x} {y + 22}V{y}H{x + 22}" fill="none" stroke="{OMNI}" stroke-width="2.4"/>')
        # icon in a mini dial
        ix, iy = x + 52, y + 56
        c.add(f'<circle cx="{ix}" cy="{iy}" r="32" fill="{VOID}" stroke="{OMNI}" stroke-width="2"/><circle cx="{ix}" cy="{iy}" r="38" fill="none" stroke="{OMNI}" stroke-width="1" stroke-dasharray="2 6" opacity=".6"><animateTransform attributeName="transform" type="rotate" from="0 {ix} {iy}" to="360 {ix} {iy}" dur="{18 + i * 3}s" repeatCount="indefinite"/></circle>')
        c.add(f'<g transform="translate({ix - 18} {iy - 18}) scale(.75)" filter="url(#glow)">{icon(f[5], OMNI)}</g>')
        c.text(x + 104, y + 44, f"FORM 0{i + 1}", MONO, 12, DIM, ls=2.5)
        c.text(x + 102, y + 76, f[0], DISP, 32, CORE, ls=1.2)
        c.text(x + 24, y + 124, f[1].upper(), DISP2, 19, OMNI, ls=.8)
        # one-liner wrapped to two lines
        words, lines, cur = f[2].split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > 46: lines.append(cur); cur = w
            else: cur = (cur + " " + w).strip()
        lines.append(cur)
        for k, ln in enumerate(lines[:2]):
            c.text(x + 24, y + 150 + k * 19, ln, MONO, 12.5, INK, ls=.2)
        cxp = x + 24
        for chip in f[3]:
            wch = 12 + len(chip) * 8.4
            c.add(notched(cxp, y + 188, wch, 22, 6, "none", OMNI, 1.2))
            c.text(cxp + wch / 2, y + 204, chip, MONO, 12, OMNI, anchor="middle", ls=.8)
            cxp += wch + 8
        c.text(x + tw - 18, y + th - 12, f[4], MONO, 10.5, DIM, anchor="end", ls=1.2)
    c.add(f'<rect width="{W}" height="{H}" fill="url(#scan)" opacity=".45"/>')
    brackets(c, 14, 14, W - 28, H - 28)
    return finish(c, W, H, "Six flagship projects")


def finish(c, W, H, title):
    css = fonts_css(c.used)
    body = "".join(c.parts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">'
            f'<title>{esc(title)}</title><style>{css}</style>{body}</svg>')


if __name__ == "__main__":
    for name, fn in [("omnitrix.svg", hero), ("forms.svg", forms)]:
        svg = fn(); (ASSETS / name).write_text(svg, encoding="utf-8")
        print(f"assets/{name}: {len(svg.encode()) / 1024:.1f} KB")
