#!/usr/bin/env python3
"""Generates every SVG panel in ./assets for the MegaZroN profile README.
Run:  python3 generate_assets.py   (no dependencies beyond the standard library)
Style: megazron.com alien-tech HUD (green field, chevrons, notched plates, scanlines)."""
import os, math, random
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT, exist_ok=True)
random.seed(7)

# ---- tokens (copied from megazron.com styles.css) ----
VOID, DEEP, PANEL, PANEL_HI = "#030d05", "#06180a", "#0a2e11", "#114a1c"
OMNI, OMNI_HI, CYAN, HAZARD, ALERT = "#3dfa46", "#8dffb0", "#7ffcd5", "#ffb300", "#ff4423"
INK, INK_DIM, CORE, DIM = "#b8e8c0", "#6aa876", "#eafff0", "#1f7a2c"
DISP = "'Barlow Condensed','Roboto Condensed','Arial Narrow','Helvetica Neue',Arial,sans-serif"
MONO = "'Share Tech Mono','JetBrains Mono','Cascadia Code',Consolas,'Courier New',monospace"
BODY = "Saira,'Segoe UI',Helvetica,Arial,sans-serif"

def prep_hologram(src="avatar.jpg", dst="avatar-holo.png", size=380):
    """Turns assets/avatar.jpg into a green duotone hologram PNG with soft alpha edges. Needs Pillow; skipped if missing."""
    try:
        from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    except ImportError:
        print("Pillow not installed - keeping existing", dst); return
    im = Image.open(os.path.join(OUT, src)).convert("RGB")
    w, h = im.size
    side = int(min(w, h) * 0.86)
    left, top = (w - side) // 2 - int(w * 0.03), int(h * 0.02)
    im = im.crop((max(0, left), top, max(0, left) + side, top + side)).resize((size, size), Image.LANCZOS)
    g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(1.25)
    # duotone: void -> omni -> near-white green
    lut = []
    stops = [(0, (3, 13, 5)), (110, (18, 92, 34)), (200, (61, 250, 70)), (255, (216, 255, 224))]
    for v in range(256):
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= v <= b:
                t = (v - a) / (b - a); lut.append(tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))); break
    px = g.load(); out = Image.new("RGB", g.size)
    op = out.load()
    for y in range(size):
        for x in range(size):
            op[x, y] = lut[px[x, y]]
    # radial alpha mask so the figure floats in the field
    mask = Image.new("L", (size, size), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask); d.ellipse((size*0.04, size*0.02, size*0.96, size*1.06), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(size * 0.06))
    out.putalpha(mask)
    out = out.quantize(colors=160, method=Image.Quantize.FASTOCTREE).convert("RGBA")
    out.save(os.path.join(OUT, dst), optimize=True)
    print("hologram written", os.path.getsize(os.path.join(OUT, dst)) // 1024, "KB")

def holo_href(name="avatar-holo.png"):
    import base64
    p = os.path.join(OUT, name)
    if not os.path.exists(p): return None
    return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def defs(extra=""):
    return f"""<defs>
  <radialGradient id="field" cx="22%" cy="35%" r="80%">
    <stop offset="0" stop-color="{PANEL}"/><stop offset=".55" stop-color="{DEEP}"/><stop offset="1" stop-color="{VOID}"/>
  </radialGradient>
  <linearGradient id="cone" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{OMNI}" stop-opacity=".32"/><stop offset="1" stop-color="{OMNI}" stop-opacity=".02"/>
  </linearGradient>
  <linearGradient id="base" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#d8ffe0"/><stop offset=".38" stop-color="#7fd18c"/><stop offset="1" stop-color="#2c6b36"/>
  </linearGradient>
  <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{OMNI}" stop-opacity="0"/><stop offset=".5" stop-color="{OMNI}" stop-opacity=".35"/><stop offset="1" stop-color="{OMNI}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="glint" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{OMNI}" stop-opacity="0"/><stop offset=".5" stop-color="{OMNI}" stop-opacity=".22"/><stop offset="1" stop-color="{OMNI}" stop-opacity="0"/>
  </linearGradient>
  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
    <path d="M40 0H0V40" fill="none" stroke="{OMNI}" stroke-opacity=".07"/>
  </pattern>
  <pattern id="scanlines" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#000" fill-opacity=".28"/>
  </pattern>
  <pattern id="hazard" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
    <rect width="7" height="14" fill="{OMNI}" fill-opacity=".55"/>
    <animateTransform attributeName="patternTransform" type="translate" from="0 0" to="14 0" additive="sum" dur="1.2s" repeatCount="indefinite"/>
  </pattern>
  <pattern id="dashbar" width="1" height="7" patternUnits="userSpaceOnUse">
    <rect width="3" height="2" fill="{OMNI}"/>
  </pattern>
  <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="glowlg" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  {extra}
</defs>"""

def svg_open(w, h, extra_defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">\n{defs(extra_defs)}\n'
            f'<rect width="{w}" height="{h}" fill="url(#field)"/>\n<rect width="{w}" height="{h}" fill="url(#grid)"/>\n')

def svg_close(w, h):
    return f'<rect width="{w}" height="{h}" fill="url(#scanlines)" pointer-events="none"/>\n</svg>\n'

def plate(x, y, w, h, notch=14, fill=PANEL, stroke=DIM, op=".92"):
    """Notched header plate with dashed left accent bar (matches .hud-panel)."""
    return (f'<path d="M{x} {y}H{x+w-notch}L{x+w} {y+notch}V{y+h}H{x}Z" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="1"/>'
            f'<rect x="{x}" y="{y+h*0.12:.0f}" width="3" height="{h*0.76:.0f}" fill="url(#dashbar)" opacity=".7"/>'
            f'<path d="M{x+w-22} {y+1}h21v21" fill="none" stroke="{OMNI}" stroke-opacity=".8"/>')

def reveal(delay, fade=0.35):
    """opacity anim that starts at 0s, stays hidden until `delay`, then fades in. Element stays visible if SMIL never runs."""
    total = delay + fade
    k = delay / total if total else 0
    return f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{k:.4f};1" dur="{total:.2f}s" fill="freeze"/>'

def led(x, y, color=OMNI, r=4, dur="2.2s"):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" filter="url(#glow)">'
            f'<animate attributeName="r" values="{r};{r*0.6:.1f};{r}" dur="{dur}" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="1;.55;1" dur="{dur}" repeatCount="indefinite"/></circle>')

def hazard_bar(x, y, w, h=6):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#hazard)"/><line x1="{x}" y1="{y+h+1}" x2="{x+w}" y2="{y+h+1}" stroke="{OMNI}" stroke-opacity=".3"/>'

def ruler(x, y, w, step=10, major=50):
    out = [f'<g stroke="{OMNI}" stroke-opacity=".45">']
    for i in range(0, w+1, step):
        hgt = 8 if i % major == 0 else 4
        out.append(f'<line x1="{x+i}" y1="{y}" x2="{x+i}" y2="{y-hgt}"/>')
    out.append('</g>')
    return "".join(out)

def binary_rain(w, h, cols=16, op=".16"):
    out = []
    for c in range(cols):
        x = int((c + 0.5) * w / cols) + random.randint(-15, 15)
        rows = int(h / 13) * 2 + 4
        dur = random.uniform(9, 18)
        bits = "".join(random.choice("01") for _ in range(rows))
        tsp = "".join(f'<tspan x="{x}" dy="13">{b}</tspan>' for b in bits)
        out.append(f'<text y="{-h-13}" font-family="{MONO}" font-size="11" fill="{OMNI}" opacity="{op}">{tsp}'
                   f'<animateTransform attributeName="transform" type="translate" from="0 0" to="0 {h+13}" dur="{dur:.1f}s" repeatCount="indefinite"/></text>')
    return "".join(out)

def rings(cx, cy, r, n=3, op=".3"):
    out = []
    for i in range(n):
        rr = r - i * (r / (n + 0.5))
        dash = ["6 10", "2 9", "18 6"][i % 3]
        dur = 40 + i * 25
        d = "" if i % 2 == 0 else " keyTimes=\"0;1\" values=\"360 {cx} {cy};0 {cx} {cy}\"".format(cx=cx, cy=cy)
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{rr:.0f}" fill="none" stroke="{OMNI}" stroke-opacity="{op}" stroke-width="1.2" stroke-dasharray="{dash}">'
                   f'<animateTransform attributeName="transform" type="rotate" from="{0 if i%2==0 else 360} {cx} {cy}" to="{360 if i%2==0 else 0} {cx} {cy}" dur="{dur}s" repeatCount="indefinite"/></circle>')
    return "".join(out)

# =====================================================================
# HERO
# =====================================================================
def hero():
    W, H = 1200, 430
    s = [svg_open(W, H, f'<clipPath id="dialclip"><circle cx="960" cy="190" r="104"/></clipPath>'
                        f'<clipPath id="heroclip"><rect width="{W}" height="{H}"/></clipPath>'
                        f'<pattern id="holoscan" width="5" height="5" patternUnits="userSpaceOnUse"><rect width="5" height="2" fill="{VOID}" fill-opacity=".45"/></pattern>'
                        f'<linearGradient id="cyanscan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/><stop offset=".5" stop-color="{CYAN}" stop-opacity=".4"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>')]
    s.append(f'<g clip-path="url(#heroclip)">{binary_rain(W, H)}</g>')
    s.append(f'<ellipse cx="960" cy="210" rx="260" ry="200" fill="{OMNI}" fill-opacity=".05" filter="url(#glowlg)"/>')
    s.append(rings(960, 190, 190, 3))

    # ---- status line ----
    s.append(led(70, 58))
    s.append(f'<text x="84" y="62" font-family="{MONO}" font-size="12" fill="{INK_DIM}" letter-spacing="1.5">// MEGAZRON  ·  SYSTEM ONLINE  ·  BUILD 2026.09  ·  LONDON, UK</text>')

    # ---- name plate ----
    s.append(plate(60, 78, 640, 78))
    s.append(f'<text x="84" y="134" font-family="{DISP}" font-size="50" font-weight="800" fill="{CORE}" letter-spacing="1.5">GAUS MOHIUDDIN SAYYAD</text>')
    s.append(f'<rect x="60" y="78" width="0" height="78" fill="url(#glint)"><animate attributeName="x" values="60;700" dur="4s" repeatCount="indefinite"/><animate attributeName="width" values="120;120" dur="4s" repeatCount="indefinite"/></rect>')

    # ---- typewriter roles ----
    roles = ["ROBOTICS SOFTWARE ENGINEER", "VISION-LANGUAGE-ACTION POLICIES", "EMBODIED AI & DEEP RL",
             "PERCEPTION-TO-ACTION PIPELINES", "SPACE TECH RESEARCHER", "BRAIN-COMPUTER INTERFACES"]
    per, step, hold = 4.2, 0.055, 1.9
    total = per * len(roles)
    s.append(f'<text x="84" y="192" font-family="{MONO}" font-size="21" fill="{OMNI}">&gt;_</text>')
    for ri, role in enumerate(roles):
        start = ri * per
        end = start + per - 0.35
        chunks = []
        for ci, ch in enumerate(role):
            t1 = (start + 0.3 + ci * step) / total
            t2 = end / total
            chunks.append(f'<tspan opacity="0">{esc(ch)}<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;{t1:.4f};{t1:.4f};{t2:.4f};{t2:.4f};1" calcMode="discrete" dur="{total}s" repeatCount="indefinite"/></tspan>')
        cur_on = (start + 0.3 + len(role) * step) / total
        chunks.append(f'<tspan fill="{OMNI_HI}" opacity="0">▌<animate attributeName="opacity" values="0;0;1;0;1;0;1;0;1;0;0" keyTimes="0;{cur_on:.4f};{cur_on:.4f};{cur_on+0.011:.4f};{cur_on+0.022:.4f};{cur_on+0.033:.4f};{cur_on+0.044:.4f};{cur_on+0.055:.4f};{cur_on+0.066:.4f};{end/total:.4f};1" calcMode="discrete" dur="{total}s" repeatCount="indefinite"/></tspan>')
        s.append(f'<text x="116" y="192" font-family="{MONO}" font-size="21" fill="{OMNI}" filter="url(#glow)" xml:space="preserve">{"".join(chunks)}</text>')

    # ---- credentials + rule ----
    s.append(f'<text x="84" y="222" font-family="{MONO}" font-size="13" fill="{INK_DIM}" letter-spacing="1">MSc ROBOTICS \'26 @ IMPERIAL  ·  EX HUAWEI R&amp;D  ·  EX ISRO  ·  EX IIT BOMBAY  ·  3× GERMAN PATENTS</text>')
    s.append(hazard_bar(84, 236, 560, 4))

    # ---- headline ----
    s.append(f'<text x="84" y="290" font-family="{DISP}" font-size="38" font-weight="700" fill="{CORE}" letter-spacing=".5">BUILDS THE IMPOSSIBLE <tspan fill="{OMNI}">WITH SCIENCE...</tspan></text>')
    s.append(f'<text x="86" y="318" font-family="{BODY}" font-size="15" font-style="italic" fill="{INK}">Because science works — 10 Billion Percent!</text>')

    # ---- chevron tags ----
    def chev(x, y, w, label, color=OMNI, fill=False):
        c = 12
        pts = f"{x+c},{y} {x+w},{y} {x+w-c},{y+28} {x},{y+28}"
        f = color if fill else "none"
        tc = VOID if fill else color
        return (f'<polygon points="{pts}" fill="{f}" fill-opacity="{".95" if fill else "0"}" stroke="{color}" stroke-width="1.2"/>'
                f'<text x="{x+w/2}" y="{y+19}" text-anchor="middle" font-family="{MONO}" font-size="12" font-weight="700" fill="{tc}" letter-spacing="1.2">{esc(label)}</text>')
    s.append(chev(84, 340, 210, "PORTFOLIO  ▸ megazron.com", OMNI, True))
    s.append(chev(306, 340, 300, "OPEN TO ROBOTICS ROLES · SEP 2026", CYAN))

    # ---- main dial: holographic portrait ----
    cx, cy = 960, 190
    s.append(f'<circle cx="{cx}" cy="{cy}" r="104" fill="{DEEP}" fill-opacity=".85" stroke="{DIM}" stroke-width="2"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="96" fill="none" stroke="{OMNI}" stroke-opacity=".8" stroke-width="3" stroke-dasharray="2 8">'
             f'<animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="30s" repeatCount="indefinite"/></circle>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="82" fill="none" stroke="{OMNI}" stroke-opacity=".35" stroke-dasharray="1 6"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="70" fill="none" stroke="{OMNI}" stroke-opacity=".9" stroke-width="2" stroke-dasharray="40 400" stroke-linecap="round">'
             f'<animateTransform attributeName="transform" type="rotate" from="360 {cx} {cy}" to="0 {cx} {cy}" dur="6s" repeatCount="indefinite"/></circle>')
    s.append(f'<g stroke="{OMNI}" stroke-opacity=".35"><line x1="{cx-104}" y1="{cy}" x2="{cx-60}" y2="{cy}"/><line x1="{cx+60}" y1="{cy}" x2="{cx+104}" y2="{cy}"/>'
             f'<line x1="{cx}" y1="{cy-104}" x2="{cx}" y2="{cy-60}"/><line x1="{cx}" y1="{cy+60}" x2="{cx}" y2="{cy+104}"/></g>')
    href = holo_href()
    holo = ""
    if href:
        sz = 248
        holo = (f'<defs><image id="portrait" href="{href}" x="{cx-sz/2}" y="{cy-sz/2+16}" width="{sz}" height="{sz}"/></defs>'
                f'<g filter="url(#glow)"><animateTransform attributeName="transform" type="translate" values="0 0;0 -7;0 0" dur="4.4s" repeatCount="indefinite"/>'
                # ghost copies for a chromatic hologram fringe
                f'<use href="#portrait" x="-3" opacity=".28" style="mix-blend-mode:screen"/>'
                f'<use href="#portrait" x="3" opacity=".28" style="mix-blend-mode:screen"/>'
                f'<use href="#portrait">'
                f'<animate attributeName="opacity" values="1;1;.86;1;1;.72;.95;1;1;.9;1" keyTimes="0;.3;.32;.34;.6;.61;.63;.66;.85;.87;1" dur="5.7s" repeatCount="indefinite"/></use></g>'
                # dense hologram scanlines over the portrait only
                f'<rect x="{cx-104}" y="{cy-104}" width="208" height="208" fill="url(#holoscan)"/>')
    s.append(f'<g clip-path="url(#dialclip)">{holo}'
             f'<rect x="{cx-104}" y="{cy-130}" width="208" height="54" fill="url(#cyanscan)"><animate attributeName="y" values="{cy-130};{cy+104}" dur="3.4s" repeatCount="indefinite"/></rect></g>')
    s.append(f'<text x="{cx}" y="{cy+124}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{INK_DIM}" letter-spacing="2">HOLO FEED · LIVE</text>')
    s.append(f'<text x="{cx-98}" y="{cy-112}" font-family="{MONO}" font-size="10" fill="{OMNI}" letter-spacing="1.5">STATUS</text>')
    s.append(f'<text x="{cx+98}" y="{cy-112}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{OMNI}" letter-spacing="1.5">LIVE ●<animate attributeName="opacity" values="1;.4;1" dur="1.6s" repeatCount="indefinite"/></text>')
    s.append(f'<polygon points="{cx-48},{cy+136} {cx+48},{cy+136} {cx+96},{cy+192} {cx-96},{cy+192}" fill="url(#cone)"><animate attributeName="opacity" values=".85;.55;.85" dur="2.6s" repeatCount="indefinite"/></polygon>')
    s.append(f'<ellipse cx="{cx}" cy="{cy+192}" rx="100" ry="8" fill="url(#base)" filter="url(#glow)"/>')

    # ---- secondary dial: 7-DoF arm (teleop readout) ----
    ax, ay, ar = 786, 330, 42
    arm = (f'<g stroke="{OMNI_HI}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none" filter="url(#glow)">'
           f'<path d="M{cx-2} {cy+62} L{cx-2} {cy+40}"/>'
           f'<g><animateTransform attributeName="transform" type="rotate" values="-6 {cx-2} {cy+40};6 {cx-2} {cy+40};-6 {cx-2} {cy+40}" dur="5s" repeatCount="indefinite"/>'
           f'<path d="M{cx-2} {cy+40} L{cx-34} {cy-4}"/>'
           f'<g><animateTransform attributeName="transform" type="rotate" values="8 {cx-34} {cy-4};-10 {cx-34} {cy-4};8 {cx-34} {cy-4}" dur="4s" repeatCount="indefinite"/>'
           f'<path d="M{cx-34} {cy-4} L{cx+14} {cy-38}"/>'
           f'<g><animateTransform attributeName="transform" type="rotate" values="-14 {cx+14} {cy-38};14 {cx+14} {cy-38};-14 {cx+14} {cy-38}" dur="3.2s" repeatCount="indefinite"/>'
           f'<path d="M{cx+14} {cy-38} L{cx+44} {cy-30}"/>'
           f'<path d="M{cx+44} {cy-30} l10 -8 M{cx+44} {cy-30} l12 6" stroke-width="3.5"><animate attributeName="d" values="M{cx+44} {cy-30} l10 -8 M{cx+44} {cy-30} l12 6;M{cx+44} {cy-30} l12 -3 M{cx+44} {cy-30} l12 2;M{cx+44} {cy-30} l10 -8 M{cx+44} {cy-30} l12 6" dur="3.2s" repeatCount="indefinite"/></path>'
           f'<circle cx="{cx+14}" cy="{cy-38}" r="5" fill="{VOID}" stroke-width="3"/>'
           f'</g></g><circle cx="{cx-34}" cy="{cy-4}" r="5" fill="{VOID}" stroke-width="3"/></g>'
           f'<circle cx="{cx-2}" cy="{cy+40}" r="6" fill="{VOID}" stroke-width="3"/>'
           f'<path d="M{cx-22} {cy+62} h40" stroke-width="6"/></g>')
    s.append(f'<circle cx="{ax}" cy="{ay}" r="{ar}" fill="{DEEP}" fill-opacity=".85" stroke="{DIM}" stroke-width="1.5"/>'
             f'<circle cx="{ax}" cy="{ay}" r="{ar-5}" fill="none" stroke="{OMNI}" stroke-opacity=".7" stroke-width="2" stroke-dasharray="2 6">'
             f'<animateTransform attributeName="transform" type="rotate" from="360 {ax} {ay}" to="0 {ax} {ay}" dur="20s" repeatCount="indefinite"/></circle>')
    s.append(f'<g transform="translate({ax} {ay+6}) scale(.58) translate({-cx} {-cy-8})">{arm}</g>')
    s.append(f'<text x="{ax}" y="{ay+ar+14}" text-anchor="middle" font-family="{MONO}" font-size="9.5" fill="{INK_DIM}" letter-spacing="1.5">TELEOP · <tspan fill="{OMNI}">ARMED ●<animate attributeName="opacity" values="1;.4;1" dur="1.6s" repeatCount="indefinite"/></tspan></text>')

    # ---- bottom telemetry bar ----
    s.append(hazard_bar(0, H-28, W, 5))
    s.append(ruler(0, H-30, W))
    s.append(f'<text x="70" y="{H-9}" font-family="{MONO}" font-size="10.5" fill="{INK_DIM}" letter-spacing="1.2">LOC 51.4988N 0.1749W  //  IMPERIAL COLLEGE LONDON</text>')
    s.append(f'<text x="{W/2}" y="{H-9}" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{INK_DIM}" letter-spacing="1.2">PATENTS+PAPERS 10  //  DE PATENTS 03  //  AWARDS 53</text>')
    s.append(f'<text x="{W-70}" y="{H-9}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{INK_DIM}" letter-spacing="1.2">SIH ’23 ’24 WINNER  //  CANSAT ’22 WINNER</text>')
    s.append(svg_close(W, H))
    open(os.path.join(OUT, "hero.svg"), "w").write("".join(s))

# =====================================================================
# SECTION HEADER PLATES
# =====================================================================
def header(slug, label, title, readout):
    W, H = 1200, 56
    s = [svg_open(W, H)]
    s.append(plate(0, 4, W, 48, notch=16))
    s.append(f'<rect x="0" y="4" width="140" height="48" fill="url(#glint)"><animate attributeName="x" values="-140;1200" dur="5s" repeatCount="indefinite"/></rect>')
    s.append(led(24, 28, r=4))
    s.append(f'<text x="40" y="24" font-family="{MONO}" font-size="10" fill="{OMNI}" letter-spacing="2.5">{esc(label.upper())}</text>')
    s.append(f'<text x="40" y="45" font-family="{DISP}" font-size="24" font-weight="700" fill="{CORE}" letter-spacing="1.5">{esc(title.upper())}</text>')
    s.append(f'<text x="{W-36}" y="35" text-anchor="end" font-family="{MONO}" font-size="12" fill="{INK_DIM}" letter-spacing="1.5">{esc(readout)}</text>')
    s.append(f'<rect x="{W-24}" y="24" width="10" height="12" fill="url(#hazard)"/>')
    s.append(svg_close(W, H))
    open(os.path.join(OUT, f"h-{slug}.svg"), "w").write("".join(s))

# =====================================================================
# MISSION LOG TIMELINE
# =====================================================================
def timeline():
    W, H = 1200, 330
    nodes = [
        (2021, "MGM UNIVERSITY", "BTech ECE · Rank #1 in dept", 95),
        (2022, "CANSAT INDIA · IEEE-AESS", "Winner · led team of 8", 250),
        (2023, "SMART INDIA HACKATHON", "Winner · GDSC Lead (800+ mentored)", 405),
        (2024, "ISRO · NARL", "LiDAR + ML fellow · SIH ’24 Winner", 560),
        (2025, "IIT BOMBAY · IMPERIAL", "GeoTRACE @ InGARSS · 3× DE patents", 730),
        (2026, "HUAWEI R&D UK", "VLA benchmarking · Go2 graph datasets", 900),
        ("SEP 26", "MSc GRADUATION", "Dual-arm teleop · open to roles", 1080),
    ]
    ys = [215, 195, 172, 150, 126, 102, 80]
    s = [svg_open(W, H)]
    s.append(f'<g opacity=".8">{binary_rain(W, H, cols=10, op=".08")}</g>')
    # orbit path (smooth curve through nodes)
    pts = [(n[3], y) for n, y in zip(nodes, ys)]
    d = f"M{pts[0][0]} {pts[0][1]}"
    for i in range(1, len(pts)):
        x0, y0 = pts[i-1]; x1, y1 = pts[i]
        cx_ = (x0 + x1) / 2
        d += f" C{cx_} {y0} {cx_} {y1} {x1} {y1}"
    s.append(f'<path d="{d}" fill="none" stroke="{OMNI}" stroke-opacity=".18" stroke-width="10" stroke-linecap="round"/>')
    s.append(f'<path d="{d}" fill="none" stroke="{OMNI}" stroke-width="2" stroke-dasharray="1 0" pathLength="1" stroke-linecap="round" filter="url(#glow)">'
             f'<animate attributeName="stroke-dasharray" values="0 1;1 0" dur="4s" fill="freeze"/></path>')
    # satellite travelling the orbit
    s.append(f'<g filter="url(#glow)"><g><animateMotion dur="9s" repeatCount="indefinite" rotate="auto" path="{d}"/>'
             f'<rect x="-7" y="-4" width="14" height="8" fill="{CORE}"/><rect x="-22" y="-2" width="12" height="4" fill="{CYAN}"/><rect x="10" y="-2" width="12" height="4" fill="{CYAN}"/></g></g>')
    # nodes
    for i, ((yr, t, sub, x), y) in enumerate(zip(nodes, ys)):
        delay = 0.55 * i
        s.append(f'<g>{reveal(delay)}'
                 f'<circle cx="{x}" cy="{y}" r="16" fill="none" stroke="{OMNI}" stroke-opacity=".5"><animate attributeName="r" values="10;22" dur="2.4s" begin="{delay:.2f}s" repeatCount="indefinite"/><animate attributeName="stroke-opacity" values=".6;0" dur="2.4s" begin="{delay:.2f}s" repeatCount="indefinite"/></circle>'
                 f'<circle cx="{x}" cy="{y}" r="7" fill="{VOID}" stroke="{OMNI}" stroke-width="2.5" filter="url(#glow)"/>'
                 f'<circle cx="{x}" cy="{y}" r="2.5" fill="{OMNI_HI}"/>')
        up = i % 2 == 0
        ly = y + (52 if up else -46)
        s.append(f'<line x1="{x}" y1="{y + (9 if up else -9)}" x2="{x}" y2="{ly - (34 if up else -6)}" stroke="{OMNI}" stroke-opacity=".5" stroke-dasharray="2 3"/>')
        anchor = "middle"
        s.append(f'<text x="{x}" y="{ly-20 if up else ly-28}" text-anchor="{anchor}" font-family="{MONO}" font-size="11" fill="{OMNI}" letter-spacing="2">{esc(str(yr))}</text>'
                 f'<text x="{x}" y="{ly-4 if up else ly-12}" text-anchor="{anchor}" font-family="{DISP}" font-size="17" font-weight="700" fill="{CORE}" letter-spacing=".8">{esc(t)}</text>'
                 f'<text x="{x}" y="{ly+12 if up else ly+4}" text-anchor="{anchor}" font-family="{BODY}" font-size="11.5" fill="{INK_DIM}">{esc(sub)}</text></g>')
    s.append(f'<text x="24" y="{H-14}" font-family="{MONO}" font-size="10.5" fill="{INK_DIM}" letter-spacing="1.5">TRAJECTORY  //  CHH. SAMBHAJINAGAR → TIRUPATI → MUMBAI → LONDON</text>')
    s.append(f'<text x="{W-24}" y="{H-14}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{INK_DIM}" letter-spacing="1.5">ORBIT INSERTION NOMINAL</text>')
    s.append(ruler(0, H-30, W))
    s.append(svg_close(W, H))
    open(os.path.join(OUT, "timeline.svg"), "w").write("".join(s))

# =====================================================================
# SYSTEMS CHECK (skills)
# =====================================================================
def systems():
    W, H = 1200, 290
    groups = [
        ("ROBOTICS", ["ROS 2", "ROS", "Isaac Lab", "MuJoCo", "Gazebo", "Kortex API", "Diffusion Control", "ACT Policies", "RViz", "Webots", "CoppeliaSim", "URScript", "KRL", "RAPID"]),
        ("AI / ML", ["PyTorch", "TensorFlow", "OpenCV", "VLA", "SAC", "PPO", "GNNs", "LLMs", "Gemini Robotics", "Vertex AI", "gRPC", "Kaggle"]),
        ("LANGUAGES", ["Python", "C++", "C", "Embedded C", "Julia", "MATLAB", "TypeScript", "JavaScript", "Java", "Verilog"]),
        ("HW / TOOLS", ["Jetson Nano", "Raspberry Pi", "FPGA", "Arduino", "Docker", "Linux", "Git", "GCP", "Fusion 360", "Cadence", "Qiskit Metal", "ArcGIS", "Unity"]),
    ]
    s = [svg_open(W, H)]
    pw, gap, x0, y0 = 282, 12, 12, 12
    for gi, (name, items) in enumerate(groups):
        px = x0 + gi * (pw + gap)
        s.append(plate(px, y0, pw, H - 24))
        s.append(led(px + 18, y0 + 22, r=3.5, dur=f"{1.6 + gi*0.3:.1f}s"))
        s.append(f'<text x="{px+30}" y="{y0+26}" font-family="{DISP}" font-size="18" font-weight="700" fill="{CORE}" letter-spacing="2">{esc(name)}</text>')
        s.append(f'<text x="{px+pw-14}" y="{y0+26}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{OMNI}" letter-spacing="1.5">{len(items):02d} MODULES</text>')
        # load bar
        s.append(f'<rect x="{px+16}" y="{y0+38}" width="{pw-32}" height="3" fill="{PANEL_HI}"/>'
                 f'<rect x="{px+16}" y="{y0+38}" width="0" height="3" fill="{OMNI}" filter="url(#glow)"><animate attributeName="width" values="0;{pw-32}" begin="{gi*0.4:.1f}s" dur="1.6s" fill="freeze"/></rect>')
        # chips
        cx_, cy_ = px + 16, y0 + 56
        ci = 0
        for it in items:
            w = int(len(it) * 7.4 + 18)
            if cx_ + w > px + pw - 14:
                cx_ = px + 16; cy_ += 30
            delay = gi * 0.4 + 0.5 + ci * 0.09
            s.append(f'<g>{reveal(delay, 0.3)}'
                     f'<rect x="{cx_}" y="{cy_}" width="{w}" height="22" rx="2" fill="{PANEL_HI}" fill-opacity=".7" stroke="{DIM}"/>'
                     f'<rect x="{cx_}" y="{cy_}" width="3" height="22" fill="{OMNI}"/>'
                     f'<text x="{cx_+w/2+1}" y="{cy_+15}" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{INK}">{esc(it)}</text></g>')
            cx_ += w + 6; ci += 1
        s.append(f'<text x="{px+16}" y="{H-24}" font-family="{MONO}" font-size="10" fill="{INK_DIM}" letter-spacing="1.5">ALL SYSTEMS NOMINAL{reveal(gi*0.4+1.6, 0.4)}</text>')
    s.append(svg_close(W, H))
    open(os.path.join(OUT, "systems.svg"), "w").write("".join(s))

# =====================================================================
# TELEMETRY (stats strip)
# =====================================================================
def telemetry():
    W, H = 1200, 128
    cells = [("53", "AWARDS &amp; HONOURS"), ("10", "PATENTS &amp; PAPERS"), ("03", "GERMAN PATENTS · 2025"),
             ("2×", "SIH NATIONAL WINNER"), ("800+", "DEVELOPERS MENTORED"), ("15K", "LINKEDIN FOLLOWERS")]
    s = [svg_open(W, H)]
    cw = (W - 24) / len(cells)
    for i, (v, l) in enumerate(cells):
        x = 12 + i * cw
        s.append(plate(int(x) + 3, 10, int(cw) - 6, H - 20, notch=12))
        s.append(f'<text x="{x+cw/2}" y="72" text-anchor="middle" font-family="{DISP}" font-size="46" font-weight="800" fill="{OMNI}" filter="url(#glow)">{v}'
                 f'<animate attributeName="opacity" values="0;0;1;.2;1;.5;1" keyTimes="0;{(i*0.18)/(i*0.18+0.9):.3f};{(i*0.18+0.2)/(i*0.18+0.9):.3f};{(i*0.18+0.3)/(i*0.18+0.9):.3f};{(i*0.18+0.5)/(i*0.18+0.9):.3f};{(i*0.18+0.6)/(i*0.18+0.9):.3f};1" dur="{i*0.18+0.9:.2f}s" fill="freeze"/></text>')
        s.append(f'<text x="{x+cw/2}" y="96" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{INK_DIM}" letter-spacing="2">{l}</text>')
        s.append(f'<rect x="{x+22}" y="{H-24}" width="{cw-44}" height="2" fill="{PANEL_HI}"/><rect x="{x+22}" y="{H-24}" width="0" height="2" fill="{OMNI}"><animate attributeName="width" values="0;{cw-44}" begin="{i*0.18:.2f}s" dur="1.4s" fill="freeze"/></rect>')
    s.append(svg_close(W, H))
    open(os.path.join(OUT, "telemetry.svg"), "w").write("".join(s))

# =====================================================================
# PROJECT CARDS
# =====================================================================
def glyph(kind, cx, cy):
    g = []
    if kind == "arm":   # dual arms
        for sgn in (-1, 1):
            g.append(f'<g stroke="{OMNI_HI}" stroke-width="4" stroke-linecap="round" fill="none" filter="url(#glow)">'
                     f'<path d="M{cx} {cy+34} L{cx+sgn*22} {cy+6}"/><g><animateTransform attributeName="transform" type="rotate" values="{-12*sgn} {cx+sgn*22} {cy+6};{12*sgn} {cx+sgn*22} {cy+6};{-12*sgn} {cx+sgn*22} {cy+6}" dur="3s" repeatCount="indefinite"/>'
                     f'<path d="M{cx+sgn*22} {cy+6} L{cx+sgn*46} {cy-20}"/><path d="M{cx+sgn*46} {cy-20} l{sgn*8} -8 M{cx+sgn*46} {cy-20} l{sgn*10} 4" stroke-width="3"/></g>'
                     f'<circle cx="{cx+sgn*22}" cy="{cy+6}" r="4" fill="{VOID}"/></g>')
        g.append(f'<rect x="{cx-14}" y="{cy+34}" width="28" height="8" rx="2" fill="{OMNI_HI}"/>')
    elif kind == "eeg":
        pts = " ".join(f"{cx-60+i*4},{cy + (math.sin(i*0.9)*6 if i%9 else -28)}" for i in range(31))
        g.append(f'<path d="M{cx-38} {cy-40} a38 38 0 0 1 76 0" fill="none" stroke="{OMNI}" stroke-opacity=".4" stroke-width="2" stroke-dasharray="4 4"/>')
        g.append(f'<polyline points="{pts}" fill="none" stroke="{OMNI_HI}" stroke-width="2.5" stroke-linejoin="round" filter="url(#glow)" pathLength="1" stroke-dasharray="1 1">'
                 f'<animate attributeName="stroke-dashoffset" values="1;0" dur="2.5s" repeatCount="indefinite"/></polyline>')
        g.append(f'<rect x="{cx-30}" y="{cy+16}" width="60" height="22" rx="3" fill="none" stroke="{OMNI}" stroke-width="2"/><circle cx="{cx-22}" cy="{cy+44}" r="6" fill="none" stroke="{OMNI}" stroke-width="2"/><circle cx="{cx+22}" cy="{cy+44}" r="6" fill="none" stroke="{OMNI}" stroke-width="2"/>')
    elif kind == "cansat":
        g.append(f'<path d="M{cx-40} {cy-18} a40 30 0 0 1 80 0" fill="{OMNI}" fill-opacity=".18" stroke="{OMNI}" stroke-width="2"/>')
        g.append(f'<g stroke="{OMNI}" stroke-opacity=".6"><line x1="{cx-40}" y1="{cy-18}" x2="{cx-10}" y2="{cy+14}"/><line x1="{cx+40}" y1="{cy-18}" x2="{cx+10}" y2="{cy+14}"/></g>')
        g.append(f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 4;0 0" dur="2.2s" repeatCount="indefinite"/>'
                 f'<rect x="{cx-12}" y="{cy+14}" width="24" height="34" rx="4" fill="{PANEL_HI}" stroke="{OMNI_HI}" stroke-width="2" filter="url(#glow)"/><line x1="{cx-12}" y1="{cy+26}" x2="{cx+12}" y2="{cy+26}" stroke="{OMNI}"/>'
                 f'<circle cx="{cx}" cy="{cy+38}" r="3" fill="{ALERT}"><animate attributeName="opacity" values="1;.2;1" dur="1s" repeatCount="indefinite"/></circle></g>')
        for r in (56, 70):
            g.append(f'<path d="M{cx+r*0.7} {cy+30-r*0.7} a{r} {r} 0 0 1 {r*0.3} {r*0.7}" fill="none" stroke="{CYAN}" stroke-opacity=".5" stroke-width="2"><animate attributeName="stroke-opacity" values=".1;.7;.1" dur="1.6s" begin="{(r-56)/28:.1f}s" repeatCount="indefinite"/></path>')
    elif kind == "drone":
        g.append(f'<rect x="{cx-10}" y="{cy-6}" width="20" height="40" rx="5" fill="{PANEL_HI}" stroke="{OMNI_HI}" stroke-width="2" filter="url(#glow)"/>')
        for dy, dur in ((-14, "0.25s"), (-26, "0.2s")):
            g.append(f'<ellipse cx="{cx}" cy="{cy+dy}" rx="52" ry="5" fill="none" stroke="{OMNI}" stroke-width="2" stroke-dasharray="30 10"><animate attributeName="rx" values="52;8;52" dur="{dur}" repeatCount="indefinite"/></ellipse>')
        g.append(f'<line x1="{cx}" y1="{cy-30}" x2="{cx}" y2="{cy-6}" stroke="{OMNI_HI}" stroke-width="3"/>')
        g.append(f'<path d="M{cx-22} {cy+34} l-10 12 M{cx+22} {cy+34} l10 12 M{cx-10} {cy+30} h20" stroke="{OMNI}" stroke-width="2.5" stroke-linecap="round" fill="none"/>')
    elif kind == "sac":
        layers = [(-50, 3), (-17, 5), (17, 5), (50, 2)]
        coords = {}
        for li, (dx, n) in enumerate(layers):
            for k in range(n):
                coords[(li, k)] = (cx + dx, cy + (k - (n - 1) / 2) * 20)
        for li in range(len(layers) - 1):
            for a in range(layers[li][1]):
                for b in range(layers[li + 1][1]):
                    (x1, y1), (x2, y2) = coords[(li, a)], coords[(li + 1, b)]
                    g.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{OMNI}" stroke-opacity=".28" stroke-width="1"><animate attributeName="stroke-opacity" values=".1;.6;.1" dur="{1.2+((a*b)%5)*0.3:.1f}s" repeatCount="indefinite"/></line>')
        for (x, y) in coords.values():
            g.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{VOID}" stroke="{OMNI_HI}" stroke-width="2" filter="url(#glow)"/>')
    elif kind == "mesh":
        nodes = [(cx, cy - 36), (cx - 46, cy + 4), (cx + 46, cy + 4), (cx - 24, cy + 40), (cx + 24, cy + 40)]
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                (x1, y1), (x2, y2) = nodes[i], nodes[j]
                g.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{OMNI}" stroke-opacity=".3" stroke-dasharray="3 4"/>')
                g.append(f'<circle r="2.5" fill="{CYAN}"><animateMotion dur="{1.6+((i+j)%4)*0.5:.1f}s" repeatCount="indefinite" path="M{x1} {y1} L{x2} {y2}"/></circle>')
        for (x, y) in nodes:
            g.append(f'<rect x="{x-9}" y="{y-9}" width="18" height="18" rx="3" fill="{PANEL_HI}" stroke="{OMNI_HI}" stroke-width="2" filter="url(#glow)"/><circle cx="{x}" cy="{y}" r="2.5" fill="{OMNI}"/>')
    return "".join(g)

def card(slug, kind, title, tags, blurb, status):
    W, H = 390, 176
    s = [svg_open(W, H)]
    s.append(plate(4, 4, W - 8, H - 8, notch=16))
    s.append(f'<rect x="4" y="4" width="0" height="{H-8}" fill="url(#glint)"><animate attributeName="x" values="-120;400" dur="4.5s" repeatCount="indefinite"/><animate attributeName="width" values="120;120" dur="4.5s" repeatCount="indefinite"/></rect>')
    # glyph zone on the right
    s.append(f'<circle cx="{W-78}" cy="{H/2-2}" r="60" fill="{OMNI}" fill-opacity=".05"/><circle cx="{W-78}" cy="{H/2-2}" r="60" fill="none" stroke="{OMNI}" stroke-opacity=".35" stroke-dasharray="3 6"><animateTransform attributeName="transform" type="rotate" from="0 {W-78} {H/2-2}" to="360 {W-78} {H/2-2}" dur="24s" repeatCount="indefinite"/></circle>')
    s.append(glyph(kind, W - 78, H / 2 - 4))
    s.append(led(24, 30, r=3.5))
    s.append(f'<text x="36" y="34" font-family="{MONO}" font-size="10" fill="{OMNI}" letter-spacing="2">{esc(status)}</text>')
    # title (allow two lines)
    lines = title.split("|")
    for i, ln in enumerate(lines):
        s.append(f'<text x="22" y="{60 + i*24}" font-family="{DISP}" font-size="22" font-weight="700" fill="{CORE}" letter-spacing=".5">{esc(ln.upper())}</text>')
    ty = 60 + len(lines) * 24 - 6
    for i, ln in enumerate(blurb.split("|")):
        s.append(f'<text x="22" y="{ty + i*15}" font-family="{BODY}" font-size="11.5" fill="{INK}">{esc(ln)}</text>')
    # tags
    tx = 22
    for t in tags:
        w = int(len(t) * 6.6 + 14)
        s.append(f'<rect x="{tx}" y="{H-40}" width="{w}" height="18" fill="{PANEL_HI}" stroke="{DIM}"/><rect x="{tx}" y="{H-40}" width="2" height="18" fill="{OMNI}"/>'
                 f'<text x="{tx+w/2+1}" y="{H-27}" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{INK}">{esc(t)}</text>')
        tx += w + 5
    s.append(hazard_bar(4, H - 12, W - 8, 4))
    s.append(svg_close(W, H))
    open(os.path.join(OUT, f"p-{slug}.svg"), "w").write("".join(s))

# =====================================================================
# DIVIDER + FOOTER
# =====================================================================
def divider():
    W, H = 1200, 12
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{defs()}<rect width="{W}" height="{H}" fill="{VOID}"/>{hazard_bar(0, 3, W, 5)}</svg>']
    open(os.path.join(OUT, "divider.svg"), "w").write("".join(s))

def footer():
    W, H = 1200, 96
    s = [svg_open(W, H)]
    s.append(rings(1120, 48, 120, 2, ".2"))
    s.append(led(36, 40, r=4))
    s.append(f'<text x="52" y="44" font-family="{DISP}" font-size="22" font-weight="700" fill="{CORE}" letter-spacing="1.5">END OF TRANSMISSION</text>')
    s.append(f'<text x="52" y="66" font-family="{MONO}" font-size="11.5" fill="{INK_DIM}" letter-spacing="1.2">Open to robotics &amp; embodied-AI roles, research collaborations and interesting problems.</text>')
    s.append(f'<text x="{W-36}" y="44" text-anchor="end" font-family="{MONO}" font-size="11" fill="{OMNI}" letter-spacing="2">© 2026 GAUS MOHIUDDIN SAYYAD</text>')
    s.append(f'<text x="{W-36}" y="66" text-anchor="end" font-family="{MONO}" font-size="11" fill="{INK_DIM}" letter-spacing="2">SCIENCE WORKS · 10 BILLION PERCENT<animate attributeName="opacity" values="1;.4;1" dur="2.4s" repeatCount="indefinite"/></text>')
    s.append(ruler(0, H-2, W))
    s.append(svg_close(W, H))
    open(os.path.join(OUT, "footer.svg"), "w").write("".join(s))

if __name__ == "__main__":
    prep_hologram(); hero(); timeline(); systems(); telemetry(); divider(); footer()
    header("brief", "Mission brief", "Who I am", "ID 0x4D5A · CALLSIGN MEGAZRON")
    header("log", "Where I have been", "Mission log", "07 WAYPOINTS · 2021 → 2026")
    header("experience", "Where I have worked", "Experience", "09 ENTRIES")
    header("projects", "Selected work", "Featured projects", "REPOS SYNC LIVE FROM GITHUB")
    header("research", "Patents & publications", "Research", "10 RECORDS · 03 DE PATENTS")
    header("awards", "Recognition", "Awards & honours", "53 IN TOTAL")
    header("systems", "Tools I work with", "Systems check", "04 SUBSYSTEMS")
    header("telemetry", "Auto-synced from GitHub", "Telemetry", "LIVE")
    header("comms", "Get in touch", "Comms", "CHANNELS OPEN")
    card("dualarm", "arm", "Multimodal Dual-Arm|Robot Control", ["ROS 2", "Kinova Gen3", "Isaac Lab", "Kortex"],
         "7-DoF master mannequin teleoperating dual Kinova|arms on a wearable SRL. <0.8 N haptic error,|<200 ms latency target. MSc major project.", "MSc MAJOR PROJECT · 2026")
    card("sac", "sac", "SAC for Assistive|Robotics in MuJoCo", ["SAC", "MuJoCo", "Gymnasium", "PyTorch"],
         "Can one universal Soft Actor-Critic learn several|distinct assistive functions? Prosthetics and|exoskeleton tasks, one controller.", "DEEP RL · 2026")
    card("ran", "mesh", "Robot Agent Network|for VLAs", ["uAgents", "Raspberry Pi", "Edge AI", "VLA"],
         "Decentralised Pi-based robot agents that discover|each other, share data, negotiate tasks and|coordinate with no central server.", "MULTI-ROBOT · 2025")
    card("eeg", "eeg", "EEG Operated|Wheelchair", ["EEG", "ML", "Embedded", "3D Print"],
         "Brainwave-controlled hands-free mobility.|Final-year project, now German patent|DE202025101530U1.", "PATENTED · DE 2025")
    card("cansat", "cansat", "CanSat for|Debris Detection", ["LiDAR", "LoRa", "C++", "Avionics"],
         "Can-sized satellite mapping nearby objects with|LiDAR. IEEE-AESS CanSat 2022 winner,|team of 8 led.", "IEEE-AESS WINNER · 2022")
    card("drone", "drone", "Coaxial Surveillance|Drone", ["C++", "Autonomy", "Ports", "Patent"],
         "Autonomous coaxial drone for port surveillance.|Smart India Hackathon 2023 winner, German|patent DE202025102068U1.", "SIH WINNER · DE PATENT")
    print("wrote", sorted(os.listdir(OUT)))
