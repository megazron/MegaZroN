"""End-to-end test of the real-time game in docs/ (Teach the Arm).

It serves docs/ on a free local port, drives the page with real pointer and touch events in
headless Chromium, and steps the simulation with the page's manual clock so the result does not
depend on how busy the machine is.

Run:  python tests/test_game.py [--shots DIR]      (needs playwright + chromium)
"""
import functools
import http.server
import math
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


class Game:
    def __init__(self, page, touch=False):
        self.page, self.touch = page, touch
        self.cdp = page.context.new_cdp_session(page) if touch else None

    def snap(self):
        return self.page.evaluate("__game.snapshot()")

    def adv(self, sec):
        self.page.evaluate("s => __game.advance(s)", sec)

    def shot(self, name):
        if SHOTS:
            SHOTS.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(SHOTS / name))

    def settle(self, limit=12.0):
        t = 0.0
        while t < limit:
            self.adv(0.5); t += 0.5
            if not self.snap()["busy"]:
                return True
        return False

    def project(self, x, y, z):
        return self.page.evaluate("p => __game.project(p[0], p[1], p[2])", [x, y, z])

    def _touch(self, kind, x=None, y=None):
        pts = [] if x is None else [{"x": x, "y": y, "id": 1}]
        self.cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": pts})

    def drag_to(self, x, z):
        """Drag the gripper over world point (x, z) with real pointer input, in up to three strokes."""
        hover = self.page.evaluate("__game.HOVER")
        for _ in range(3):
            tcp = self.snap()["tcp"]
            if math.hypot(tcp[0] - x, tcp[2] - z) < 0.006:
                return True
            a, b = self.project(tcp[0], hover, tcp[2]), self.project(x, hover, z)
            n = 8
            pts = [(a["x"] + (b["x"] - a["x"]) * i / n, a["y"] + (b["y"] - a["y"]) * i / n) for i in range(n + 1)]
            if self.touch:
                self._touch("touchStart", *pts[0])
                for p in pts[1:]:
                    self._touch("touchMove", *p)
                    self.adv(0.1)
                self.adv(0.8)
                self._touch("touchEnd")
            else:
                self.page.mouse.move(*pts[0]); self.page.mouse.down()
                for p in pts[1:]:
                    self.page.mouse.move(*p)
                    self.adv(0.1)
                self.adv(0.8)
                self.page.mouse.up()
            self.adv(0.3)
        tcp = self.snap()["tcp"]
        return math.hypot(tcp[0] - x, tcp[2] - z) < 0.012

    def grip(self, how="tap"):
        """Toggle the gripper: a tap on the scene, the GRIP button or the Space key."""
        if how == "button":
            self.page.locator("#btn-grip").tap() if self.touch else self.page.locator("#btn-grip").click()
        elif how == "key":
            self.page.keyboard.press("Space")
        else:
            tcp = self.snap()["tcp"]
            p = self.project(tcp[0], tcp[1] + 0.25, tcp[2])           # tap empty space above the wrist
            if self.touch:
                self.page.touchscreen.tap(p["x"], p["y"])
            else:
                self.page.mouse.click(p["x"], p["y"])
        return self.settle()

    def obj(self, oid):
        return next(o for o in self.snap()["objects"] if o["id"] == oid)

    def pad(self, pid):
        return next(p for p in self.snap()["pads"] if p["id"] == pid)

    def carry(self, oid, x, z, how="tap"):
        o = self.obj(oid)
        ok = self.drag_to(o["x"], o["z"]) and self.grip(how)
        if self.snap()["holding"] != oid:
            return False
        return ok and self.drag_to(x, z) and self.grip(how)

    def to_pad(self, oid, pid, how="tap"):
        p = self.pad(pid)
        return self.carry(oid, p["x"], p["z"], how)

    def onto(self, oid, base, how="tap"):
        b = self.obj(base)
        return self.carry(oid, b["x"], b["z"], how)

    def press(self, act):
        b = self.page.locator(f'#buttons [data-act="{act}"]')
        b.tap() if self.touch else b.click()

    def run_robot(self, limit=90.0, watch=None):
        """Advance until the robot run is over; returns (finished, worst lowest joint height, lowest object bottom)."""
        t, low, obj_low = 0.0, 9.0, 9.0
        while t < limit:
            self.adv(0.25); t += 0.25
            s = self.snap()
            low = min(low, s["jointsMinY"]); obj_low = min(obj_low, min(o["y"] for o in s["objects"]) - 0.04)
            if watch and not watch.get("done") and s["mode"] == "robot" and s["holding"] and s["phase"] == "TRANSFER":
                self.shot(watch["name"]); watch["done"] = True
            if s["mode"] == "result":
                return True, low, obj_low
        return False, low, obj_low


def resting_ok(s):
    """Nothing floats: every object rests on the table or exactly on top of the object it names."""
    by = {o["id"]: o for o in s["objects"]}
    for o in s["objects"]:
        want = by[o["on"]]["y"] + 0.08 if o["on"] else 0.04
        if o["state"] != "rest" or abs(o["y"] - want) > 0.002:
            return False
    return True


def order_of(s):
    return [(st["obj"], st["target"]) for st in s["steps"]]


def open_game(browser, errors, **ctx):
    context = browser.new_context(**ctx)
    page = context.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: errors.append("request failed " + r.url))
    page.on("request", lambda r: errors.append("external request " + r.url) if not r.url.startswith(BASE) and not r.url.startswith("data:") else None)
    page.goto(BASE + "/index.html")
    page.wait_for_function("window.__game && window.__game.ready", timeout=120000)
    page.evaluate("__game.setManual(true)")
    return page


def desktop(browser, errors):
    page = open_game(browser, errors, viewport={"width": 1280, "height": 720})
    g = Game(page)
    sweep = page.evaluate("__game.ikSweep()")
    check(f"IK sweep: {sweep['n']} poses converge under 1 mm, all joints above the table",
          sweep["fails"] == 0 and sweep["maxErr"] < 0.001 and sweep["minJointY"] > 0.05, str(sweep))

    # level 1: three steps, each toggled a different way (tap, GRIP button, Space)
    start = {o["id"]: (o["x"], o["z"]) for o in g.snap()["objects"]}
    check("L1 demo step 1: red cube to pad B by drag and tap", g.to_pad("red", "B", "tap"))
    g.shot("desktop-teach.png")
    check("L1 demo step 2: cyan cylinder to pad C with the GRIP button", g.to_pad("cyan", "C", "button"))
    check("L1 demo step 3: amber cube to pad A with the Space key", g.to_pad("amber", "A", "key"))
    taught = order_of(g.snap())
    check("timeline recorded the three steps in order", taught == [("red", "pad:B"), ("cyan", "pad:C"), ("amber", "pad:A")], str(taught))
    check("timeline strip shows three chips", page.locator("#timeline li[data-obj]").count() == 3)
    g.press("teach-done")
    s = g.snap()
    check("Teach done resets the scene and starts the robot",
          s["mode"] == "robot" and all(abs(o["x"] - start[o["id"]][0]) < 1e-6 and abs(o["z"] - start[o["id"]][1]) < 1e-6 for o in s["objects"]))
    done, low, obj_low = g.run_robot(watch={"name": "desktop-robot.png"})
    s = g.snap()
    check("robot repeats the same objects and targets in the same order", done and [(o["obj"], o["target"]) for o in s["result"]["order"]] == taught, str(s["result"]))
    check("robot run meets the level goal", done and s["result"]["ok"] and s["solved"], str(s["result"]))
    check("no joint dips to the table and no object sinks into it", low > 0.05 and obj_low > -0.002, f"{low} {obj_low}")
    check("objects rest on their pads, nothing floats", resting_ok(s) and {o["id"]: o["pad"] for o in s["objects"]} == {"red": "B", "cyan": "C", "amber": "A"})
    check("score for one demo at par is 1000", s["score"] == 1000 and s["demos"] == 1, str(s["score"]))
    g.shot("desktop-result.png")
    check("share line names the score", "Score 1000" in page.locator("#share-text").inner_text())

    for seed in (7, 21):
        page.evaluate("s => __game.seed(s)", seed)
        g.press("shuffle")
        s0 = g.snap()
        moved = all(math.hypot(o["x"] - start[o["id"]][0], o["z"] - start[o["id"]][1]) > 0.03 for o in s0["objects"])
        done, low, obj_low = g.run_robot()
        s = g.snap()
        check(f"shuffle (seed {seed}): objects start elsewhere and the robot still does the same order and meets the goal",
              moved and done and s["result"]["ok"] and [(o["obj"], o["target"]) for o in s["result"]["order"]] == taught and resting_ok(s) and low > 0.05, str(s["result"]))
    g.shot("desktop-shuffle.png")
    pads0 = {p["id"]: (p["x"], p["z"]) for p in g.snap()["pads"]}
    page.evaluate("__game.seed(5)")
    g.press("challenge-the-robot")
    pads1 = {p["id"]: (p["x"], p["z"]) for p in g.snap()["pads"]}
    done, low, obj_low = g.run_robot()
    s = g.snap()
    check("challenge: pads move too, the robot still succeeds, streak 1, score 1150",
          pads0 != pads1 and done and s["result"]["ok"] and s["streak"] == 1 and s["score"] == 1150 and resting_ok(s)
          and {o["id"]: o["pad"] for o in s["objects"]} == {"red": "B", "cyan": "C", "amber": "A"}, str(s["result"]))
    g.shot("desktop-challenge.png")

    # level 3: order matters, amber starts on top of red
    page.evaluate("__game.setLevel(2)")
    g.adv(0.5)
    ok = g.to_pad("amber", "B") and g.to_pad("red", "A") and g.onto("amber", "red") and g.onto("cyan", "amber")
    taught = order_of(g.snap())
    check("L3 demo: unstack amber, red to pad A, amber onto red, cyan onto amber",
          ok and taught == [("amber", "pad:B"), ("red", "pad:A"), ("amber", "on:red"), ("cyan", "on:amber")], str(taught))
    g.shot("desktop-l3-teach.png")
    g.press("teach-done")
    done, low, obj_low = g.run_robot()
    s = g.snap()
    check("L3 robot rebuilds the tower in the taught order", done and s["result"]["ok"] and [(o["obj"], o["target"]) for o in s["result"]["order"]] == taught and resting_ok(s), str(s["result"]))
    g.shot("desktop-l3-result.png")
    page.evaluate("__game.seed(11)")
    g.press("shuffle")
    done, low, obj_low = g.run_robot()
    s = g.snap()
    check("L3 shuffle: the stack moves and the robot still builds red, amber, cyan", done and s["result"]["ok"] and resting_ok(s) and low > 0.05, str(s["result"]))

    # a wrong demonstration is copied faithfully and fails the goal
    g.press("teach-again")
    g.adv(0.5)
    ok = g.to_pad("amber", "B") and g.to_pad("red", "A") and g.onto("cyan", "red") and g.onto("amber", "cyan")
    g.press("teach-done")
    done, low, obj_low = g.run_robot()
    s = g.snap()
    check("L3 wrong order: the robot copies the mistake and the level reports a failed goal",
          ok and done and not s["result"]["ok"] and len(s["result"]["order"]) == 4 and "must be red, amber, cyan" in s["result"]["reason"] and s["demos"] == 2, str(s["result"]))

    # level 2 with an off-centre, unstable drop: the cube slides off instead of hovering
    page.evaluate("__game.setLevel(1)")
    g.adv(0.5)
    r = g.obj("red")
    g.carry("cyan", r["x"] + 0.06, r["z"])
    s = g.snap()
    c = next(o for o in s["objects"] if o["id"] == "cyan")
    check("a cube dropped half off another slides down to the table instead of floating", resting_ok(s) and abs(c["y"] - 0.04) < 0.002 and c["on"] is None, str(c))

    page.locator("#btn-how").click()
    check("How it works panel opens and links text-to-robot", page.locator('#how a[href="https://github.com/megazron/text-to-robot"]').is_visible())
    page.locator("#btn-how-close").click()
    page.locator("#btn-mute").click()
    check("mute toggle flips and persists", page.locator("#btn-mute").inner_text() == "SND OFF" and page.evaluate("localStorage.getItem('tta.muted')") == "true")
    page.context.close()


def phone(browser, errors):
    page = open_game(browser, errors, viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    g = Game(page, touch=True)
    check("phone: page does not scroll or overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight"))
    check("phone step 1: red cube to pad B by touch drag and tap", g.to_pad("red", "B", "tap"))
    check("phone step 2: cyan cylinder to pad C with the GRIP button", g.to_pad("cyan", "C", "button"))
    g.shot("phone-teach.png")
    check("phone step 3: amber cube to pad A", g.to_pad("amber", "A", "tap"))
    taught = order_of(g.snap())
    g.press("teach-done")
    done, low, obj_low = g.run_robot(watch={"name": "phone-robot.png"})
    s = g.snap()
    check("phone: robot repeats the touch demo in order and meets the goal",
          done and s["result"]["ok"] and [(o["obj"], o["target"]) for o in s["result"]["order"]] == taught and len(taught) == 3 and resting_ok(s), str(s["result"]))
    g.shot("phone-result.png")
    boxes = page.evaluate("[...document.querySelectorAll('#buttons .btn, #btn-grip, #top button')].map(b => { const r = b.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })")
    check("phone: every button is inside the viewport", all(b[0] >= 0 and b[1] >= 0 and b[2] <= 390.5 and b[3] <= 844.5 for b in boxes), str(boxes))
    page.evaluate("__game.seed(3)")
    g.press("shuffle")
    done, low, obj_low = g.run_robot()
    s = g.snap()
    check("phone: shuffle run succeeds", done and s["result"]["ok"] and resting_ok(s), str(s["result"]))
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
