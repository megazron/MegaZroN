"""Plays both README games on github.com like a visitor would: real clicks, real pages.

Run:  python tests/play_github.py <start url> <screenshot dir> [battle]     (battle: skip the arm game)
      start url is the repo page that shows the README, for example
      https://github.com/megazron/MegaZroN  or  .../tree/<branch>
"""
import io
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import generate_games as g  # noqa: E402  (only used to look up a winning line of play)

start, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
BODY = "article.markdown-body"


def line(stage, goal):
    @lru_cache(None)
    def f(s):
        for a in g.actions(s[3]):
            kind, nxt, _ = g.step(stage, s, a)
            if kind == goal:
                return a
            if kind == "go" and (r := f(nxt)):
                return a + r
        return None
    return f((1, g.PHP, g.STAGES[stage]["hp"], 0))


with sync_playwright() as p:
    browser = p.chromium.launch()
    pg = browser.new_page(viewport={"width": 1280, "height": 1100})

    def steady(fn):
        """GitHub re-renders after load and can detach an element mid-action. Try again like a person would."""
        def run(*args):
            for attempt in range(6):
                try:
                    return fn(*args)
                except AssertionError:
                    raise
                except Exception as e:
                    if attempt == 5:
                        raise
                    print("  (retry:", str(e).splitlines()[0][:70] + ")")
                    pg.wait_for_timeout(1500)
        return run

    @steady
    def shot(name):
        pg.locator(f"{BODY} img").first.scroll_into_view_if_needed()
        pg.wait_for_timeout(700)
        pg.screenshot(path=str(out / f"{name}.png"))
        print("shot", name)

    @steady
    def click(alt):
        a = pg.locator(f'{BODY} a:has(img[alt="{alt}"])').first
        href = a.get_attribute("href")
        a.scroll_into_view_if_needed()
        pg.wait_for_timeout(1200)                                   # be polite to github.com
        a.click()
        pg.wait_for_url("**" + href, timeout=45000)                 # GitHub swaps pages in place, so wait for the new address
        try:
            pg.wait_for_selector(f"{BODY} img", timeout=12000)
        except Exception:                                           # GitHub's in-place page swap sometimes stalls: reload like a visitor would
            print("  (page swap stalled, reloading)")
            pg.reload()
            pg.wait_for_selector(f"{BODY} img", timeout=45000)
        pg.wait_for_timeout(400)
        print("  click", alt, "->", pg.url.split("MegaZroN")[-1])

    @steady
    def animating(what, index=0):
        img = pg.locator(f"{BODY} img").nth(index)
        img.scroll_into_view_if_needed()
        pg.wait_for_function("i => i.complete && i.naturalWidth > 0", arg=img.element_handle(), timeout=30000)
        pg.wait_for_timeout(600)
        a = Image.open(io.BytesIO(img.screenshot())).convert("RGB")
        moved = False
        for _ in range(6):
            pg.wait_for_timeout(450)
            if ImageChops.difference(a, Image.open(io.BytesIO(img.screenshot())).convert("RGB")).getbbox():
                moved = True
                break
        print(f"  {what}: image loaded, animation playing = {moved}")
        assert moved, what

    @steady
    def home():
        pg.goto(start)
        pg.wait_for_selector(f'{BODY} img[alt^="Teach the arm"]')
        pg.wait_for_timeout(1500)
        pg.locator('img[alt^="Teach the arm"]').first.scroll_into_view_if_needed()

    home()
    pg.wait_for_timeout(2500)
    broken = pg.evaluate(f"[...document.querySelectorAll('{BODY} img')].filter(i => !(i.complete && i.naturalWidth > 0)).map(i => i.alt)")
    assert not broken, broken
    pg.screenshot(path=str(out / "readme-play.png"))
    print("shot readme-play; all README images loaded")

    # Teach the arm
    if "battle" not in sys.argv[3:]:
        click("Pick red"); animating("pick"); shot("arm-1-start-pick")
        click("Place in bin B"); click("Pick blue"); animating("mid teach"); shot("arm-2-mid-teach")
        click("Place in bin A"); click("Pick yellow"); click("Place in bin C"); shot("arm-3-taught")
        click("Teach done: let the robot do it")
        assert pg.url.endswith("arm/run-rB-bA-yC.md"), pg.url
        animating("robot repeat"); pg.wait_for_timeout(2500); shot("arm-4-repeat")
        click("Shuffle")
        assert pg.url.endswith("run-rB-bA-yC-s1.md"), pg.url
        animating("shuffle"); pg.wait_for_timeout(3000); shot("arm-5-shuffle")
        click("Shuffle")
        assert pg.url.endswith("-s2.md"), pg.url
        click("Teach again")
        assert pg.url.endswith("arm/README.md"), pg.url

    # Robot battle
    names = {"A": "Attack", "S": "Shield", "C": "Charge", "O": "Overdrive"}
    home(); click("Fight the Scrap Rover"); animating("battle start", 1); shot("battle-1-start")
    for stage, goal in ((1, "flawless"), (2, "win"), (3, "flawless")):
        seq = line(stage, goal)
        print(f" stage {stage}: {goal} with {seq}")
        for i, a in enumerate(seq):
            click(names[a])
            if stage == 1 and i == 1:
                animating("exchange", 1); shot("battle-2-mid")
            if stage == 3 and i == 3:
                shot("battle-4-boss")
        assert pg.url.endswith(f"s{stage}/{goal}.md"), pg.url
        shot(f"battle-3-end-s{stage}")
        if stage < 3:
            click("Next stage")
    click("Teach the arm")
    assert pg.url.endswith("arm/README.md"), pg.url
    home(); click("Fight the Heavy Mech")
    for a in line(2, "lose"):
        click(names[a])
    assert pg.url.endswith("s2/lose.md"), pg.url
    shot("battle-5-lose")
    click("Play again")
    assert pg.url.endswith("s2/start.md"), pg.url
    print("GITHUB PLAYTHROUGH OK")
    browser.close()
