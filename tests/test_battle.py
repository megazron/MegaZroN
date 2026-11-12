"""End-to-end test of the real-time Robot Battle in docs/battle/.

It serves docs/ on a free local port, plays the fights in headless Chromium with real key and
touch input, and steps the simulation with the page's manual clock so the result does not depend
on how busy the machine is. A small policy reads the enemy tells from the page state each tick.

Run:  python tests/test_battle.py [--shots DIR]      (needs playwright + chromium)
"""
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parent.parent / "docs"
SHOTS = Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
results = []


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name + (f"  [{detail}]" if detail and not cond else ""), flush=True)


class Fight:
    """Drives one page. Keys on desktop, CDP touch on the pads on a phone."""

    def __init__(self, page, touch=False):
        self.page, self.touch = page, touch
        self.cdp = page.context.new_cdp_session(page) if touch else None
        self.holding = False

    def snap(self):
        return self.page.evaluate("__battle.snapshot()")

    def ticks(self, n=1):
        self.page.evaluate("n => __battle.ticks(n)", n)

    def shot(self, name):
        if SHOTS:
            SHOTS.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(SHOTS / name))

    def _pad(self, act):
        r = self.page.evaluate("a => { const b = document.querySelector(`.pad[data-act=${a}]`).getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; }", act)
        return {"x": r[0], "y": r[1], "id": 1 if act == "shd" else 2}

    def tap(self, act):
        if self.touch:
            p = self._pad(act)
            self.cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [p]})
            self.cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        else:
            self.page.keyboard.press({"atk": "a", "chg": "d", "od": "f"}[act])

    def shield(self, on):
        if on == self.holding:
            return
        self.holding = on
        if self.touch:
            p = self._pad("shd")
            self.cdp.send("Input.dispatchTouchEvent", {"type": "touchStart" if on else "touchEnd", "touchPoints": [p] if on else []})
        else:
            (self.page.keyboard.down if on else self.page.keyboard.up)("s")

    def wait_state(self, want, limit=400):
        for _ in range(limit):
            if self.snap()["state"] == want:
                return True
            self.ticks(2)
        return False

    def play(self, policy=True, limit=60 * 22, shot_at=None):
        """Play until the fight ends. Returns the snapshot on the result card and stats."""
        self.wait_state("fight")
        low_fps_ok, shots_done, parries_seen = True, False, 0
        for i in range(limit):
            s = self.snap()
            if s["state"] != "fight":
                break
            if not policy:
                self.ticks(30)
                continue
            self.decide(s)
            if shot_at and not shots_done and s["enemy"]["hp"] <= s["enemy"]["max"] * 0.5:
                self.shot(shot_at); shots_done = True
            self.ticks(3)       # one decision every 3 ticks (50 ms of game time)
        self.shield(False)
        self.wait_state("result", 300)
        return self.snap()

    def decide(self, s):
        e, p = s["enemy"], s["player"]
        free = p["act"] is None
        if e["trans"] or e["stun"]:
            self.shield(False)
            if free:
                self.tap("atk")
            return
        if e["part"] == "wind":
            rem = e["wind"] - e["t"]
            if e["move"] == "K" and p["en"] >= 2 and rem > 18 and free:
                self.shield(False); self.tap("od"); return
            if rem <= 7:
                self.shield(True); return
            self.shield(False)
            if free and rem > 34:
                self.tap("atk")
            return
        if e["part"] == "rec":
            self.shield(False)
            if free:
                self.tap("atk")
            return
        self.shield(False)
        if not free:
            return
        if e["move"] == "G":
            self.tap("chg" if p["en"] < 3 else "od")
        elif e["move"] == "R":
            self.tap("od" if p["en"] >= 2 and e["hp"] > 20 else "atk")
        else:
            self.tap("atk")


def open_page(browser, errors, **ctx):
    context = browser.new_context(**ctx)
    page = context.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: errors.append("request failed " + r.url))
    page.on("request", lambda r: errors.append("external request " + r.url) if not r.url.startswith(BASE) and not r.url.startswith("data:") else None)
    page.goto(BASE + "/battle/")
    page.wait_for_function("window.__battle && window.__battle.ready", timeout=120000)
    return page


def desktop(browser, errors):
    page = open_page(browser, errors, viewport={"width": 1280, "height": 720})
    f = Fight(page)
    try:      # fps is reported once a second of (clamped) frame time has passed; software GL is slow
        page.wait_for_function("__battle.snapshot().fps > 0", timeout=30000)
    except Exception:
        pass
    fps = f.snap()["fps"]
    check(f"real-time loop runs on its own clock ({fps:.0f} fps in software GL)", fps > 5, str(fps))
    s = f.snap()
    check("title card shows with a FIGHT button", s["state"] == "title" and s["card"] and page.locator("#btn-start").is_visible())
    f.shot("desktop-title.png")
    check("the arm game link goes to the arm game", page.get_attribute("#link-arm", "href") == "../")
    page.evaluate("__battle.setManual(true)")
    page.keyboard.press("Enter")
    s = f.snap()
    check("Enter starts stage 1", s["state"] == "intro" and s["stage"] == 0, str(s))

    # loss: stand still and let the Scrap Rover win
    s = f.play(policy=False)
    check("doing nothing loses stage 1 (health or time runs out)", s["result"] in ("lose", "timeout") and s["card"], str(s))
    check("lose card offers RETRY STAGE", page.locator("#card [data-go=retry]").is_visible())
    f.shot("desktop-lose.png")
    page.click("#card [data-go=retry]")
    s = f.snap()
    check("retry restarts stage 1 with full health", s["state"] == "intro" and s["stage"] == 0 and s["player"]["hp"] == 100 and s["enemy"]["hp"] == s["enemy"]["max"], str(s))

    # win all three stages with keyboard play
    for stage in range(3):
        s = f.play(shot_at=f"desktop-fight-s{stage + 1}.png")
        won = s["result"] in ("win", "flawless")
        check(f"keyboard: stage {stage + 1} ({['SCRAP ROVER', 'HEAVY MECH', 'OMEGA CORE'][stage]}) won, {s['player']['hp']} health left, {s['player']['parries']} parries",
              won and s["enemy"]["hp"] == 0, str(s))
        if not won:
            break
        if stage < 2:
            page.click("#card [data-go=next]")
            check(f"NEXT STAGE goes to stage {stage + 2}", f.snap()["stage"] == stage + 1)
    s = f.snap()
    check("final card shows a score for every stage", s["card"] and all(x is not None for x in s["scores"]) and page.locator("#final-score").is_visible(), str(s["scores"]))
    f.shot("desktop-final.png")
    page.click("#card [data-go=restart]")
    s = f.snap()
    check("PLAY AGAIN restarts from stage 1", s["state"] == "intro" and s["stage"] == 0 and s["scores"] == [None, None, None], str(s))
    page.context.close()


def phone(browser, errors):
    page = open_page(browser, errors, viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    f = Fight(page, touch=True)
    check("phone: page does not scroll or overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight"))
    boxes = page.evaluate("[...document.querySelectorAll('.pad, #top button, #top a, #btn-start')].map(b => { const r = b.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })")
    check("phone: every button is inside the viewport", all(b[0] >= 0 and b[1] >= 0 and b[2] <= 390.5 and b[3] <= 844.5 for b in boxes), str(boxes))
    page.evaluate("__battle.setManual(true)")
    page.tap("#btn-start")
    s = f.play(shot_at="phone-fight.png")
    check(f"touch: stage 1 won with the pads, {s['player']['hp']} health left", s["result"] in ("win", "flawless"), str(s))
    f.shot("phone-result.png")
    page.tap("#card [data-go=retry]")
    f.wait_state("fight")
    hp = f.snap()["enemy"]["hp"]
    f.tap("atk"); f.ticks(30)       # punch lands at tick 7, recovery ends at tick 24
    check("touch: ATTACK pad lands a punch", f.snap()["enemy"]["hp"] < hp)
    f.shield(True); f.ticks(1)
    check("touch: holding SHIELD raises the shield", f.snap()["player"]["shield"])
    f.shield(False); f.ticks(1)
    check("touch: releasing SHIELD lowers it", not f.snap()["player"]["shield"])
    page.context.close()


if __name__ == "__main__":
    srv = serve()
    BASE = f"http://127.0.0.1:{srv.server_address[1]}"
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        desktop(browser, errors)
        phone(browser, errors)
        browser.close()
    check("no console errors, failed requests or external requests", not errors, "; ".join(errors[:5]))
    srv.shutdown()
    bad = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
    sys.exit(1 if bad else 0)
