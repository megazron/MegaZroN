"""Checks the pre-rendered README games (arm/ and battle/) without a browser.

It only reads the generated files, and it restates the game rules on its own instead of importing
them from generate_games.py, so a bug in the generator cannot hide itself.

Run:  python tests/test_graph.py
"""

import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r'<a href="([^"]+)">(?:<img src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>|([^<]*))</a>')
IMG = re.compile(r'<img src="([^"]+)"')
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
        if len(fails) <= 25:
            print("FAIL", msg)


def links(md):
    """[(target path, button alt or link text)] for the relative links of a page."""
    text = md.read_text(encoding="utf-8")
    out = []
    for href, _, alt, plain in LINK.findall(text):
        if href.startswith("http") or href.startswith("mailto"):
            continue
        out.append(((md.parent / href.split("#")[0]).resolve(), alt or plain))
    return out


# ---------------------------------------------------------------- 1. every link and image resolves
def test_links():
    pages = [ROOT / "README.md"] + sorted((ROOT / "arm").rglob("*.md")) + sorted((ROOT / "battle").rglob("*.md"))
    for md in pages:
        text = md.read_text(encoding="utf-8")
        for target, label in links(md):
            check(target.is_file(), f"{md.relative_to(ROOT)}: link '{label}' -> missing {target}")
        for src in IMG.findall(text):
            if not src.startswith("http"):
                check((md.parent / src).resolve().is_file(), f"{md.relative_to(ROOT)}: image missing {src}")
        if md.name != "README.md" or md.parent != ROOT:
            check("Back to profile" in text and "Play the real-time 3D version" in text, f"{md.relative_to(ROOT)}: footer links missing")
            check("—" not in text, f"{md.relative_to(ROOT)}: em dash")
    print(f"links: {len(pages)} pages checked")
    return pages


# ---------------------------------------------------------------- 2. Teach the arm
NAMES = {"red": "r", "blue": "b", "yellow": "y"}


def anim_times(tag_body):
    m = re.search(r'values="([^"]+)" keyTimes="([^"]+)"', tag_body)
    return (m.group(1).split(";"), [float(x) for x in m.group(2).split(";")]) if m else (None, None)


def read_run(svg_path):
    """Reads the animation itself: which object is grasped when, where from, and where it is released."""
    s = svg_path.read_text(encoding="utf-8")
    grip = re.search(r'<animateTransform attributeName="transform" type="translate"[^>]*values="([^"]+)" keyTimes="([^"]+)"', s)
    wrist = [tuple(float(v) for v in p.split()) for p in grip.group(1).split(";")]
    times = [float(x) for x in grip.group(2).split(";")]

    def wrist_at(t):
        i = min(range(len(times)), key=lambda k: abs(times[k] - t))
        return wrist[i]

    carry_dy = float(re.search(r'<use id="c\w" href="#\w" y="([\d.]+)"', s).group(1))
    seq, starts = [], {}
    for o in "rby":
        src = re.search(rf'<use id="s{o}" href="#{o}" x="([\d.-]+)" y="([\d.-]+)">(.*?)</use>', s)
        car = re.search(rf'<use id="c{o}" href="#{o}"[^>]*>(.*?)</use>', s)
        dst = re.search(rf'<use id="b{o}([ABC])" href="#{o}" x="([\d.-]+)" y="([\d.-]+)"[^>]*>(.*?)</use>', s)
        check(bool(src and car and dst), f"{svg_path.name}: object {o} is not animated end to end")
        if not (src and car and dst):
            continue
        _, kt_src = anim_times(src.group(3))
        vals, kt_car = anim_times(car.group(1))
        _, kt_dst = anim_times(dst.group(4))
        t_grasp, t_release = kt_car[1], kt_car[2]
        check(vals == ["0", "1", "0"], f"{svg_path.name}: {o} carried copy has wrong visibility")
        check(abs(kt_src[1] - t_grasp) < 1e-6, f"{svg_path.name}: {o} leaves the table at a different time than the grasp")
        check(abs(kt_dst[1] - t_release) < 1e-6, f"{svg_path.name}: {o} appears in the bin at a different time than the release")
        sx, sy = float(src.group(1)), float(src.group(2))
        bx, by = float(dst.group(2)), float(dst.group(3))
        wx, wy = wrist_at(t_grasp)
        check(abs(wx - sx) <= 1.5 and abs(wy + carry_dy - sy) <= 1.5, f"{svg_path.name}: gripper is not on {o} when it grasps ({wx},{wy}) vs ({sx},{sy})")
        wx, wy = wrist_at(t_release)
        check(abs(wx - bx) <= 1.5 and abs(wy + carry_dy - by) <= 1.5, f"{svg_path.name}: gripper is not over bin {dst.group(1)} when it releases {o}")
        seq.append((t_grasp, t_release, o, dst.group(1)))
        starts[o] = (sx, sy)
    seq.sort()
    for (g1, r1, *_), (g2, r2, *_) in zip(seq, seq[1:]):
        check(g1 < r1 < g2 < r2, f"{svg_path.name}: steps overlap in time")
    return [(o, b) for _, _, o, b in seq], starts


def test_arm():
    arm = ROOT / "arm"
    readme_starts = {t for t, label in links(ROOT / "README.md") if label.startswith("Pick ")}
    folder_starts = {t for t, label in links(arm / "README.md") if label.startswith("Pick ")}
    check(readme_starts == folder_starts and len(readme_starts) == 3, "profile README and arm/README.md offer different start buttons")
    done, runs, visited = 0, set(), set()

    def walk(page, taught, holding):
        nonlocal done
        visited.add(page)
        opts = [(t, label) for t, label in links(page) if re.match(r"(Pick |Place in bin |Teach done)", label)]
        check(opts, f"{page.name}: dead end during teaching")
        for target, label in opts:
            if label.startswith("Pick "):
                check(holding is None, f"{page.name}: pick offered while holding")
                o = NAMES[label[5:]]
                check(o not in [x for x, _ in taught], f"{page.name}: {o} offered twice")
                walk(target, taught, o)
            elif label.startswith("Place in bin "):
                check(holding is not None, f"{page.name}: place offered with an empty gripper")
                walk(target, taught + [(holding, label[-1])], None)
            else:
                check(len(taught) == 3, f"{page.name}: teach done after {len(taught)} steps")
                order, start0 = read_run(arm / "img" / (target.stem + ".svg"))
                check(order == taught, f"{target.name}: robot order {order} != taught order {taught}")
                done += 1
                runs.add(target)
                visited.add(target)
                # shuffles: same order, different start layout, and the buttons cycle through all three
                seen, cur, layouts = [], target, [start0]
                for _ in range(4):
                    nxt = [t for t, label2 in links(cur) if label2 == "Shuffle"]
                    check(len(nxt) == 1, f"{cur.name}: no shuffle button")
                    check(any(label2 == "Teach again" and t == arm / "README.md" for t, label2 in links(cur)), f"{cur.name}: no teach again button")
                    cur = nxt[0]
                    if cur in seen:
                        break
                    seen.append(cur)
                    visited.add(cur)
                    order_s, start_s = read_run(arm / "img" / (cur.stem + ".svg"))
                    check(order_s == taught, f"{cur.name}: shuffled run does {order_s}, taught was {taught}")
                    check(start_s not in layouts, f"{cur.name}: shuffle does not move the objects")
                    layouts.append(start_s)
                check(len(seen) == 3, f"{target.name}: expected 3 shuffle variants, found {len(seen)}")

    for s in sorted(readme_starts):
        walk(s, [], NAMES[{"r": "red", "b": "blue", "y": "yellow"}[s.stem]])
    check(done == 36 and len(runs) == 36, f"expected 36 complete demonstrations, walked {done} ending in {len(runs)} run pages")
    orphans = {p for p in arm.glob("*.md") if p.name != "README.md"} - visited
    check(not orphans, f"arm: {len(orphans)} pages are unreachable, e.g. {sorted(orphans)[:3]}")
    print(f"arm: {done} complete paths from START, {len(visited)} state pages, every run and shuffle repeats the taught order")


# ---------------------------------------------------------------- 3. Robot battle (rules restated here)
PLAYER_HP, MAX_ENERGY, MAX_ROUNDS = 5, 3, 9
ENEMY = {1: (4, "JHR", None), 2: (5, "GHHJR", None), 3: (5, "JGGKHR", "GJGKH")}
ACT = {"Attack": "a", "Shield": "s", "Charge": "c", "Overdrive": "o"}
STATE = re.compile(r"r(\d\d)-p(\d)-e(\d)-n(\d)-([asco])$")


def enemy_move(stage, rnd, ehp):
    _, pat, rage = ENEMY[stage]
    if rage and ehp <= 2:
        pat = rage
    return pat[(rnd - 1) % len(pat)]


def expected(stage, rnd, php, ehp, en, act):
    em = enemy_move(stage, rnd, ehp)
    hit = {"a": 1, "o": 3, "s": 0, "c": 0}[act]
    if hit and em == "G":
        hit = max(0, hit - 2)
    if hit and em == "R":
        hit += 1
    hurt = {"J": 1, "H": 2, "K": 3, "G": 0, "R": 0}[em]
    if act == "s":
        hurt = max(0, hurt - 2)
    if act == "o" and em == "K":
        hurt = 0
    if act == "o":
        en -= 2
    if act == "c":
        en = min(MAX_ENERGY, en + 1)
    if ehp - hit <= 0:
        return "flawless" if php == PLAYER_HP else "win"
    if php - hurt <= 0:
        return "lose"
    if rnd == MAX_ROUNDS:
        return "timeout"
    return f"r{rnd+1:02d}-p{php-hurt}-e{ehp-hit}-n{en}-{act}"


def test_battle():
    total = 0
    for stage in (1, 2, 3):
        d = ROOT / "battle" / f"s{stage}"
        start = d / "start.md"
        ends = {"win", "flawless", "lose", "timeout"}
        seen, todo, reached = {start}, deque([start]), set()
        while todo:
            page = todo.popleft()
            text = page.read_text(encoding="utf-8")
            if page.stem == "start":
                rnd, php, ehp, en, last = 1, PLAYER_HP, ENEMY[stage][0], 0, None
            else:
                m = STATE.match(page.stem)
                check(bool(m), f"{page}: unexpected page name")
                rnd, php, ehp, en = (int(m.group(i)) for i in (1, 2, 3, 4))
                last = m.group(5)
            check(1 <= php <= PLAYER_HP and 1 <= ehp <= ENEMY[stage][0] and 0 <= en <= MAX_ENERGY and 1 <= rnd <= MAX_ROUNDS, f"{page.name}: value out of range")
            # the three images must show exactly this state
            imgs = IMG.findall(text)
            check(f"../img/hp-{stage}-{php}-{ehp}.svg" in imgs, f"{page.name}: health panel does not match the state")
            check(f"../img/m-{en}-{rnd:02d}.svg" in imgs, f"{page.name}: energy/round panel does not match the state")
            tell = enemy_move(stage, rnd, ehp).lower()
            scene = [i for i in imgs if "/x-" in i]
            check(len(scene) == 1 and scene[0].endswith(f"-{tell}.svg"), f"{page.name}: scene does not show the tell '{tell}'")
            if last:
                check(scene and f"-{stage}-{last}" in scene[0], f"{page.name}: scene does not replay my last move")
            moves = {ACT[label]: t for t, label in links(page) if label in ACT}
            want = {"a", "s", "c"} | ({"o"} if en >= 2 else set())
            check(set(moves) == want, f"{page.name}: buttons {sorted(moves)} but energy {en} allows {sorted(want)}")
            for act, target in moves.items():
                exp = expected(stage, rnd, php, ehp, en, act)
                check(target == d / f"{exp}.md", f"{page.name} --{act}--> {target.name}, rules say {exp}")
                if target.stem in ends:
                    reached.add(target.stem)
                elif target not in seen:
                    m2 = STATE.match(target.stem)
                    check(bool(m2) and int(m2.group(1)) == rnd + 1, f"{page.name} -> {target.name}: round must go up by one")   # so no loops, every path ends
                    seen.add(target)
                    todo.append(target)
        check({"win", "flawless", "lose"} <= reached, f"stage {stage}: endings reached {sorted(reached)}; a win, a flawless win and a loss must all be possible")
        for e in ends:
            t = (d / f"{e}.md")
            labels = [label for _, label in links(t)]
            check("Play again" in labels, f"stage {stage} {e}: no play again link")
            check(any("Teach the arm" in x for x in labels), f"stage {stage} {e}: no link to the other game")
            if e in ("win", "flawless") and stage < 3:
                check("Next stage" in labels, f"stage {stage} {e}: no next stage link")
        orphans = {p for p in d.glob("*.md")} - seen - {d / f"{e}.md" for e in ends}
        check(not orphans, f"stage {stage}: {len(orphans)} unreachable pages")
        total += len(seen)
        print(f"battle stage {stage}: {len(seen)} state pages, endings reachable: {sorted(reached)}, rounds strictly increase so every path ends")
    return total


def test_size():
    files = [f for d in ("arm", "battle") for f in (ROOT / d).rglob("*") if f.is_file()]
    size = sum(f.stat().st_size for f in files)
    check(size < 5 * 1024 * 1024, f"generated games are {size/1e6:.1f} MB, over the 5 MB budget")
    big = max((f for f in files if f.suffix == ".svg" and f.name != "card.svg"), key=lambda f: f.stat().st_size)
    check(big.stat().st_size < 12 * 1024, f"{big} is {big.stat().st_size} bytes")            # state pages stay tiny
    for d in ("arm", "battle"):
        card = ROOT / d / "card.svg"                                                        # the two README cards embed a font
        check(card.stat().st_size < 24 * 1024, f"{card} is {card.stat().st_size} bytes")
    for f in files:
        if f.suffix == ".svg":
            check("<script" not in f.read_text(encoding="utf-8"), f"{f}: script in SVG")
    print(f"size: {len(files)} files, {size/1024:.0f} KB, largest SVG {big.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    test_links()
    test_arm()
    test_battle()
    test_size()
    print("FAILED: %d problems" % len(fails) if fails else "ALL GRAPH TESTS PASSED")
    sys.exit(1 if fails else 0)
