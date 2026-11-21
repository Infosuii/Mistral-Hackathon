"""N4: Playwright browser walk-through of the GAMBIT demo path.

Drives the real web UI beat by beat and saves a PNG screenshot of every beat
under `e2e/screens/`, plus checks for console/page errors and layout overflow.

    python -m e2e.walkthrough               # live backend + Vite web UI
    python -m e2e.walkthrough --offline     # offline cached backend + Vite web UI
    python -m e2e.walkthrough --url http://localhost:5173 --api http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

from e2e.demo_path import DEMO_LINES, ROOT, _free_port, _load_env

SCREENS_DIR = Path(__file__).resolve().parent / "screens"


def _wait_http(url: str, timeout_s: float = 25.0) -> None:
    deadline = time.perf_counter() + timeout_s
    last_err: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as r:
                if r.status < 500:
                    return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.25)
    raise RuntimeError(f"{url} did not become ready in {timeout_s:.0f}s: {last_err}")


def _api_state(api_base: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{api_base}/state", timeout=5.0) as r:
        return json.loads(r.read().decode("utf-8"))


def _check_layout(page: Page, beat: str) -> list[str]:
    """Programmatic readability/layout checks run on every beat."""
    return page.evaluate(
        """(beat) => {
          const notes = [];
          const vw = window.innerWidth, vh = window.innerHeight;
          const sw = document.documentElement.scrollWidth;
          if (sw > vw + 2) {
            notes.push(`${beat}: horizontal overflow scrollWidth=${sw} > viewport=${vw}`);
          }
          const topbar = document.querySelector('.topbar');
          if (topbar) {
            const r = topbar.getBoundingClientRect();
            if (r.height > 120) notes.push(`${beat}: topbar wrapped tall (${Math.round(r.height)}px)`);
          }
          // Check visible buttons/panels for clipping outside viewport right/bottom edges
          for (const sel of ['.phone', '.forecast', '.dossier', '.contacts', '.crisis-bar', '.replay-panel']) {
            const el = document.querySelector(sel);
            if (!el) continue;
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            if (r.right > vw + 4) notes.push(`${beat}: ${sel} clips right edge (${Math.round(r.right)} > ${vw})`);
            if (r.bottom > vh + 4) notes.push(`${beat}: ${sel} extends past viewport bottom (${Math.round(r.bottom)} > ${vh})`);
          }
          // Check if phone overlaps dossier or forecast
          const phone = document.querySelector('.phone')?.getBoundingClientRect();
          const dossier = document.querySelector('.dossier')?.getBoundingClientRect();
          if (phone && dossier && phone.top < dossier.bottom - 2 && phone.bottom > dossier.top + 2
              && phone.left < dossier.right - 2 && phone.right > dossier.left + 2) {
            notes.push(`${beat}: .phone overlaps .dossier`);
          }
          return notes;
        }""",
        beat,
    )


def _pause_if_running(page: Page) -> None:
    btn = page.locator(".session-controls button", has_text="Pause")
    if btn.count() > 0 and btn.first.is_visible() and btn.first.is_enabled():
        btn.first.click()


def _select_nation(page: Page, name: str) -> None:
    page.locator(".contacts .nation-button", has_text=name).first.click()


def _wait_not_pending(page: Page, api_base: str, timeout_s: float = 55.0) -> dict[str, Any]:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        st = _api_state(api_base)
        lc = st.get("last_call")
        if lc is None or not lc.get("pending"):
            # Let the 1s poll propagate to React state.
            page.wait_for_timeout(1200)
            return st
        page.wait_for_timeout(300)
    raise RuntimeError("call stayed pending beyond timeout")


def _send_typed_call(page: Page, api_base: str, nation_label: str, text: str) -> dict[str, Any]:
    _select_nation(page, nation_label)
    page.wait_for_timeout(300)
    inp = page.locator('input[aria-label="Type a line to the leader"]')
    inp.wait_for(state="visible", timeout=10000)
    inp.fill(text)
    prev_id = (_api_state(api_base).get("last_call") or {}).get("call_id")
    page.locator('.tb-typed button[type="submit"]').click()
    # Wait for transcript / reply to appear and for server interpret to finish.
    deadline = time.perf_counter() + 55.0
    while time.perf_counter() < deadline:
        st = _api_state(api_base)
        lc = st.get("last_call")
        if lc and lc.get("call_id") != prev_id and not lc.get("pending"):
            page.wait_for_timeout(1200)
            return st
        page.wait_for_timeout(300)
    raise RuntimeError(f"typed call to {nation_label} did not settle in 55s")


def _click_advance(page: Page, api_base: str, expect_phase: str | None = None, expect_tick: int | None = None) -> dict[str, Any]:
    _pause_if_running(page)
    btn = page.locator(".session-controls button").filter(has_text="Next")
    btn.first.wait_for(state="visible", timeout=10000)
    # Wait until enabled (not clock-held or pending)
    deadline = time.perf_counter() + 30.0
    while time.perf_counter() < deadline:
        if btn.first.is_enabled():
            break
        page.wait_for_timeout(250)
    before = _api_state(api_base)
    before_key = (before["phase"], before["turn"], (before.get("crisis") or {}).get("tick"))
    btn.first.click()
    deadline = time.perf_counter() + 45.0
    while time.perf_counter() < deadline:
        st = _api_state(api_base)
        key = (st["phase"], st["turn"], (st.get("crisis") or {}).get("tick"))
        if key != before_key:
            if expect_phase and st["phase"] != expect_phase:
                pass
            elif expect_tick is not None and (st.get("crisis") or {}).get("tick") != expect_tick:
                pass
            else:
                page.wait_for_timeout(1200)
                return st
        page.wait_for_timeout(250)
    raise RuntimeError(f"advance from {before_key} did not complete")


def run_walkthrough(
    web_url: str,
    api_base: str,
    *,
    screens_dir: Path = SCREENS_DIR,
    viewport: tuple[int, int] = (1440, 900),
) -> dict[str, Any]:
    screens_dir.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    http_errors: list[str] = []
    page_errors: list[str] = []
    layout_notes: list[str] = []
    saved: list[str] = []

    def snap(page: Page, filename: str) -> None:
        path = screens_dir / filename
        if path.suffix.lower() in (".jpg", ".jpeg"):
            page.screenshot(path=str(path), full_page=False, type="jpeg", quality=88)
        else:
            page.screenshot(path=str(path), full_page=False)
        saved.append(filename)
        notes = _check_layout(page, filename)
        layout_notes.extend(notes)
        print(f"SNAP  {filename:<28}  layout_issues={len(notes)}")
        for n in notes:
            print(f"      ! {n}")

    with sync_playwright() as p:
        launch_kwargs: dict[str, Any] = {"headless": True}
        chrome_bin = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome_bin.exists():
            launch_kwargs["executable_path"] = str(chrome_bin)
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        page = context.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("response", lambda r: http_errors.append(f"{r.status} {r.url}") if r.status >= 400 else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        page.goto(web_url, wait_until="networkidle")
        page.wait_for_timeout(1200)

        # Beat 1: Start game as President of Valdoria
        # Builds with a "New game" button start here; the campaign map build opens a live
        # session on load and keeps "New Seed" behind a confirmation instead.
        start_btn = page.locator(".session-controls button").filter(has_text="game")
        if start_btn.count():
            start_btn.first.click()
        page.wait_for_timeout(1200)
        _pause_if_running(page)
        page.wait_for_timeout(400)
        snap(page, "01_start_strategy.jpg")

        # Beat 2: Strategy-phase call to Kessaria + advance month
        _send_typed_call(page, api_base, "Kessaria", DEMO_LINES["strategy_trade"])
        snap(page, "02_strategy_call.jpg")
        _click_advance(page, api_base)

        # Beat 3: Start One Berth & tick 1 incoming call ring
        page.locator(".session-controls button", has_text="Start One Berth").click()
        page.wait_for_timeout(1200)
        _pause_if_running(page)
        _click_advance(page, api_base, expect_tick=1)
        snap(page, "03_one_berth_ring.jpg")

        # Beat 4: Double promise (Ostrava tick 1, Zarnia tick 3) + Nordhaven tugs (tick 4)
        _send_typed_call(page, api_base, "Ostrava", DEMO_LINES["promise_ostrava"])
        _click_advance(page, api_base, expect_tick=2)
        _click_advance(page, api_base, expect_tick=3)
        _send_typed_call(page, api_base, "Zarnia", DEMO_LINES["promise_zarnia"])
        _click_advance(page, api_base, expect_tick=4)
        _send_typed_call(page, api_base, "Nordhaven", DEMO_LINES["call_nordhaven_tugs"])
        snap(page, "04_promises_and_tugs.jpg")

        # Beat 5: Compare notes (tick 5)
        _click_advance(page, api_base, expect_tick=5)
        snap(page, "05_compare_notes.jpg")

        # Beat 6: Intel drawer + Wiretap on Ostrava
        _select_nation(page, "Ostrava")
        page.wait_for_timeout(300)
        page.locator(".intelligence button", has_text="Intel").click()
        page.wait_for_timeout(1200)
        snap(page, "06a_intel_drawer.jpg")
        page.locator(".intelligence button", has_text="Wiretap").click()
        page.wait_for_timeout(300)
        page.locator(".intelligence button", has_text="Listen").click()
        page.locator(".intel-drawer .transcript li").first.wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(400)
        snap(page, "06b_wiretap.jpg")
        # Close drawer so phone is clearly visible for blockade call
        page.locator(".intelligence button", has_text="Wiretap").click()

        # Beat 7: Ostrava blockade call at tick 7 + answer with morning offer
        _click_advance(page, api_base, expect_tick=6)
        _click_advance(page, api_base, expect_tick=7)
        snap(page, "07a_blockade_ring.jpg")
        _send_typed_call(page, api_base, "Ostrava", DEMO_LINES["interrupt_blockade"])
        snap(page, "07b_blockade_answered.jpg")

        # Beat 8: Advance through deadlines to resolution + War-Odds Needle + ReplayPanel
        st = _api_state(api_base)
        while st.get("phase") == "crisis":
            st = _click_advance(page, api_base)
        page.locator(".replay-panel").wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(1200)
        snap(page, "08_resolved_needle.jpg")

        # Beat 9: Run counterfactual replay (+3 ticks)
        page.locator(".replay-panel button", has_text="Run replay").click()
        page.locator(".replay-result ul li, .replay-result p").first.wait_for(state="visible", timeout=25000)
        page.wait_for_timeout(500)
        snap(page, "09_replay_panel.jpg")

        # Beat 10: End session & wait for historian verdict
        page.locator(".session-controls button", has_text="End session").click()
        page.locator(".historian-verdict blockquote").wait_for(state="visible", timeout=40000)
        page.wait_for_timeout(500)
        snap(page, "10_end_screen.jpg")

        # Also capture a 1280x720 laptop check on the live screen by clicking New game
        page.set_viewport_size({"width": 1280, "height": 720})
        new_game = page.locator(".session-controls button", has_text="New game")
        if new_game.count():
            new_game.click()
        else:  # the campaign map build: New Seed, then confirm in its dialog
            page.locator(".session-controls button", has_text="New Seed").click()
            page.locator("dialog[open] button", has_text="Start new world").click()
        page.wait_for_timeout(1200)
        _pause_if_running(page)
        snap(page, "11_laptop_1280x720.jpg")

        browser.close()

    return {
        "screens": saved,
        "console_errors": console_errors,
        "http_errors": http_errors,
        "page_errors": page_errors,
        "layout_notes": layout_notes,
    }


def main(argv: list[str] | None = None) -> int:
    _load_env(ROOT / ".env")
    ap = argparse.ArgumentParser(description="GAMBIT Playwright browser walk-through (N4)")
    ap.add_argument("--offline", action="store_true", help="Launch scripts/demo.sh --offline")
    ap.add_argument("--url", help="Already-running web UI URL")
    ap.add_argument("--api", help="Already-running backend URL (default http://127.0.0.1:8000)")
    ap.add_argument("--out-dir", default=str(SCREENS_DIR))
    args = ap.parse_args(argv)

    proc: subprocess.Popen | None = None
    try:
        if args.url:
            web_url = args.url.rstrip("/")
            api_base = (args.api or "http://127.0.0.1:8000").rstrip("/")
        else:
            bport = _free_port()
            wport = _free_port()
            cmd = [str(ROOT / "scripts" / "demo.sh"), "--backend-port", str(bport), "--web-port", str(wport)]
            if args.offline:
                cmd.insert(1, "--offline")
            proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            api_base = f"http://127.0.0.1:{bport}"
            web_url = f"http://127.0.0.1:{wport}"
            _wait_http(f"{api_base}/state", 30.0)
            _wait_http(f"{web_url}/", 30.0)

        report = run_walkthrough(web_url, api_base, screens_dir=Path(args.out_dir))
        print("\n=== N4 Walk-through Summary ===")
        print(f"Screenshots ({len(report['screens'])}): {', '.join(report['screens'])}")
        print(f"Console errors: {len(report['console_errors'])}")
        for e in report["console_errors"]:
            print(f"  [console.error] {e}")
        print(f"HTTP >=400 responses: {len(report['http_errors'])}")
        for e in report["http_errors"]:
            print(f"  [http] {e}")
        print(f"Page errors: {len(report['page_errors'])}")
        for e in report["page_errors"]:
            print(f"  [pageerror] {e}")
        print(f"Layout notes: {len(report['layout_notes'])}")
        return int(any(report[key] for key in ("page_errors", "console_errors", "http_errors", "layout_notes")))
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
