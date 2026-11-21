"""Play all four GAMBIT crisis cards offline in Chromium at 1600x900 (#67 Job 2).

    python -m e2e.crisis_cards --offline
    python -m e2e.crisis_cards --url http://localhost:5173 --api http://127.0.0.1:8000

For each crisis card (`one_berth`, `outbreak`, `coup`, `pipeline_cut`), this script:
  1. Picks the card in the session crisis selector and starts it.
  2. Advances to tick 1, verifies the opening call appears and its audio loads & plays.
  3. Answers the opening call and makes two typed promises via the Red Phone UI.
  4. Advances through deadlines until the crisis resolves.
  5. Records the War-Odds Needle caption.
  6. Runs Replay at shift 0 (expects 0 changes) and shift +5.
  7. Reaches the End Screen (waits for the Historian verdict).
  8. Scans all non-One-Berth cards for any leaked berth/ship/tug text and reports
     per-step PASS/FAIL, console/HTTP/page errors, and saves one screenshot per card
     in `e2e/screens/card_<id>.jpg`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

from e2e.demo_path import ROOT, _free_port
from e2e.walkthrough import (
    SCREENS_DIR,
    _api_state,
    _check_layout,
    _click_advance,
    _pause_if_running,
    _send_typed_call,
    _wait_http,
)

LEAK_RE = re.compile(r"\b(berths?|grain\s+ships?|ships?(?!\s+it\b)|shipping|tugs?|port\s+kessar)\b", re.IGNORECASE)


@dataclass
class CardPlan:
    id: str
    title: str
    opening_nation: str
    opening_label: str
    promise_1_tick: int
    promise_1_label: str
    promise_1_text: str
    promise_2_tick: int
    promise_2_label: str
    promise_2_text: str


CARDS: list[CardPlan] = [
    CardPlan(
        id="one_berth",
        title="One Berth",
        opening_nation="ostrava",
        opening_label="Ostrava",
        promise_1_tick=1,
        promise_1_label="Ostrava",
        promise_1_text="I promise Ostrava the berth for the whole day. Hold your ships.",
        promise_2_tick=3,
        promise_2_label="Zarnia",
        promise_2_text="Zarnia has my word: the berth is yours all day.",
    ),
    CardPlan(
        id="outbreak",
        title="Grey Fever",
        opening_nation="zarnia",
        opening_label="Zarnia",
        promise_1_tick=1,
        promise_1_label="Zarnia",
        promise_1_text="Zarnia has my word: you will get the first doses from Nordhaven.",
        promise_2_tick=3,
        promise_2_label="Kessaria",
        promise_2_text="Kessaria has my word: you will get the first doses, keep your border open.",
    ),
    CardPlan(
        id="coup",
        title="Colonels' Coup",
        opening_nation="ostrava",
        opening_label="Ostrava",
        promise_1_tick=1,
        promise_1_label="Ostrava",
        promise_1_text="Valdoria stands with Ostrava. You have Valdoria's backing today.",
        promise_2_tick=3,
        promise_2_label="Zarnia",
        promise_2_text="Zarnia has Valdoria's backing while the capital settles.",
    ),
    CardPlan(
        id="pipeline_cut",
        title="Pipeline Cut",
        opening_nation="nordhaven",
        opening_label="Nordhaven",
        promise_1_tick=1,
        promise_1_label="Nordhaven",
        promise_1_text="Valdoria backs a fair settlement—pay the price and we will guarantee supply.",
        promise_2_tick=3,
        promise_2_label="Ostrava",
        promise_2_text="Reopen the pipeline and Ostrava will be named sole supplier.",
    ),
]


@dataclass
class CardReport:
    id: str
    title: str
    steps: dict[str, str] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    console_errors: list[str] = field(default_factory=list)
    http_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    layout_notes: list[str] = field(default_factory=list)
    leaks: list[str] = field(default_factory=list)
    screenshot: str = ""


def _set_range_value(page: Page, selector: str, value: int) -> None:
    page.locator(selector).evaluate(
        """(el, val) => {
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(el, String(val));
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        value,
    )


def _visible_page_text_excluding_picker(page: Page) -> str:
    """Return visible page text excluding crisis-picker <option> labels, plus SVG <title>/aria-labels."""
    return page.evaluate(
        """() => {
          const clone = document.body.cloneNode(true);
          clone.querySelectorAll('select[aria-label="Crisis scenario"] option').forEach((o) => o.remove());
          const parts = [clone.innerText || ''];
          document.querySelectorAll('svg title').forEach((t) => {
            if (t.textContent) parts.push(t.textContent.trim());
          });
          document.querySelectorAll('svg [aria-label]').forEach((el) => {
            const lbl = el.getAttribute('aria-label');
            if (lbl) parts.push(lbl.trim());
          });
          return parts.join('\\n');
        }"""
    )


def _scan_leaks(surface: str, text: str, out: list[str]) -> None:
    if not text:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = LEAK_RE.search(line)
        if m:
            entry = f"[{surface}] matched '{m.group(0)}': {line[:160]}"
            if entry not in out:
                out.append(entry)


def _run_replay(page: Page, shift: int) -> str:
    _set_range_value(page, "#replay-shift", shift)
    page.wait_for_timeout(150)
    prev_text = page.locator(".replay-result").inner_text() if page.locator(".replay-result").count() else ""
    with page.expect_response(lambda r: r.url.endswith("/replay") and r.request.method == "POST", timeout=25000) as resp_info:
        page.locator(".replay-panel button", has_text="Run replay").click()
    resp = resp_info.value
    if resp.status != 200:
        raise RuntimeError(f"POST /replay ({shift}) returned HTTP {resp.status}")
    data = resp.json()
    # Wait for UI to render the new replay result
    page.locator(".replay-result ul li, .replay-result p").first.wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(400)
    rendered = page.locator(".replay-result").inner_text().strip()
    if rendered == prev_text and shift != 0:
        page.wait_for_timeout(400)
        rendered = page.locator(".replay-result").inner_text().strip()
    return json.dumps({"status": resp.status, "changed": data.get("changed", []), "rendered": rendered})


def run_card(
    page: Page,
    api_base: str,
    web_url: str,
    plan: CardPlan,
    screens_dir: Path,
) -> CardReport:
    rep = CardReport(id=plan.id, title=plan.title)
    c_errs: list[str] = []
    h_errs: list[str] = []
    p_errs: list[str] = []

    def on_console(m: Any) -> None:
        if m.type == "error":
            c_errs.append(m.text)

    def on_resp(r: Any) -> None:
        if r.status >= 400:
            h_errs.append(f"{r.status} {r.url}")

    def on_pageerr(e: Any) -> None:
        p_errs.append(str(e))

    page.on("console", on_console)
    page.on("response", on_resp)
    page.on("pageerror", on_pageerr)

    try:
        # Fresh page load & start game
        page.goto(web_url, wait_until="networkidle")
        page.wait_for_timeout(1000)
        start_btn = page.locator(".session-controls button").filter(has_text=re.compile("Start game|New game")).first
        start_btn.click()
        page.wait_for_timeout(1000)
        _pause_if_running(page)

        # Reset audio play probe log on window
        page.evaluate("() => { window.__playedAudio = []; }")

        # Step 1: Pick the crisis card and start it
        sel = page.locator('select[aria-label="Crisis scenario"]')
        sel.wait_for(state="visible", timeout=10000)
        sel.select_option(plan.id)
        page.wait_for_timeout(200)
        page.locator(".session-controls button", has_text=f"Start {plan.title}").click()
        page.wait_for_timeout(1000)
        _pause_if_running(page)
        st = _api_state(api_base)
        picked_ok = st.get("phase") == "crisis" and (st.get("crisis") or {}).get("id") == plan.id
        rep.steps["pick_card"] = "PASS" if picked_ok else "FAIL"
        rep.details["crisis_title_loaded"] = (st.get("crisis") or {}).get("title")

        # Step 2: Advance to tick 1, verify opening call + audio plays
        st = _click_advance(page, api_base, expect_tick=1)
        inc = st.get("incoming_call") or {}
        audio_url = inc.get("audio_url")
        audio_bytes = 0
        audio_status = 0
        if audio_url:
            with urllib.request.urlopen(f"{api_base}{audio_url}", timeout=5.0) as ar:
                audio_status = ar.status
                audio_bytes = len(ar.read())

        # Ensure opening line button or autoplay invoked HTMLMediaElement.play()
        played_urls: list[str] = page.evaluate("() => window.__playedAudio || []")
        play_btn = page.locator(".incoming-call button", has_text="Play opening line")
        if not played_urls and play_btn.count() > 0 and play_btn.first.is_visible():
            play_btn.first.click()
            page.wait_for_timeout(500)
            played_urls = page.evaluate("() => window.__playedAudio || []")

        opening_visible = page.locator(".incoming-call p").is_visible()
        opening_ok = (
            inc.get("from") == plan.opening_nation
            and opening_visible
            and bool(audio_url)
            and audio_status == 200
            and audio_bytes > 1024
            and len(played_urls) > 0
        )
        rep.steps["opening_call_audio"] = "PASS" if opening_ok else "FAIL"
        rep.details["opening_call"] = {
            "from": inc.get("from"),
            "opening_line": inc.get("opening_line"),
            "audio_url": audio_url,
            "audio_http": audio_status,
            "audio_bytes": audio_bytes,
            "play_invocations": played_urls,
        }
        if plan.id != "one_berth":
            _scan_leaks("tick1_dom", _visible_page_text_excluding_picker(page), rep.leaks)

        # Step 3: Answer opening call (Promise 1) + advance to Promise 2 tick and make Promise 2
        st = _send_typed_call(page, api_base, plan.promise_1_label, plan.promise_1_text)
        p1_count = len((st.get("crisis") or {}).get("promises") or [])
        while (st.get("crisis") or {}).get("tick", 0) < plan.promise_2_tick and st.get("phase") == "crisis":
            st = _click_advance(page, api_base)
        st = _send_typed_call(page, api_base, plan.promise_2_label, plan.promise_2_text)
        promises = (st.get("crisis") or {}).get("promises") or []
        rep.steps["two_typed_promises"] = "PASS" if (p1_count >= 1 and len(promises) >= 2) else "FAIL"
        rep.details["promises"] = [
            {"to": p.get("to"), "what": p.get("what"), "when": p.get("when"), "kept": p.get("kept")}
            for p in promises
        ]
        if plan.id != "one_berth":
            _scan_leaks("after_promises_dom", _visible_page_text_excluding_picker(page), rep.leaks)

        # Step 4: Let deadlines resolve
        while st.get("phase") == "crisis":
            st = _click_advance(page, api_base)
        resolved_ev = [e for e in st.get("events", []) if e.get("type") == "crisis_resolved"]
        rep.steps["deadlines_resolve"] = "PASS" if (st.get("phase") == "strategy" and bool(resolved_ev)) else "FAIL"
        rep.details["decisions"] = resolved_ev[-1].get("decisions") if resolved_ev else None

        # Step 5: Check War-Odds Needle caption (wait up to 25s for background rollout task)
        page.locator(".replay-panel").wait_for(state="visible", timeout=15000)
        needle_deadline = time.perf_counter() + 25.0
        while time.perf_counter() < needle_deadline:
            st = _api_state(api_base)
            if st.get("last_futures"):
                page.wait_for_timeout(1200)
                break
            page.wait_for_timeout(400)
        caption_el = page.locator(".forecast-caption").first
        caption_text = caption_el.inner_text().strip() if caption_el.count() > 0 else ""
        lf = st.get("last_futures") or {}
        needle_ok = bool(caption_text) and ("Awaiting a call" not in caption_text)
        rep.steps["needle_caption"] = "PASS" if needle_ok else "FAIL"
        rep.details["needle"] = {
            "caption_ui": caption_text,
            "caption_api": lf.get("caption"),
            "before_war_p": (lf.get("before") or {}).get("war_p"),
            "after_war_p": (lf.get("after") or {}).get("war_p"),
        }

        # Step 6: Replay at 0 and +5
        r0 = json.loads(_run_replay(page, 0))
        r5 = json.loads(_run_replay(page, 5))
        rep.steps["replay_0"] = "PASS" if (r0["status"] == 200 and r0["changed"] == []) else "FAIL"
        rep.steps["replay_plus5"] = "PASS" if r5["status"] == 200 else "FAIL"
        rep.details["replay_0"] = r0
        rep.details["replay_plus5"] = r5

        # Capture one crisp screenshot showing resolved crisis, needle caption & replay +5
        shot_name = f"card_{plan.id}.jpg"
        shot_path = screens_dir / shot_name
        page.screenshot(path=str(shot_path), full_page=False, type="jpeg", quality=84)
        rep.screenshot = f"e2e/screens/{shot_name}"
        rep.layout_notes.extend(_check_layout(page, f"{plan.id}_resolved_replay"))

        if plan.id != "one_berth":
            _scan_leaks("resolved_dom", _visible_page_text_excluding_picker(page), rep.leaks)
            for item in st.get("news") or []:
                _scan_leaks("api_news", item.get("text", ""), rep.leaks)
            _scan_leaks("needle_caption", caption_text, rep.leaks)
            _scan_leaks("replay_plus5", r5.get("rendered", ""), rep.leaks)

        # Step 7: Reach End Screen
        page.locator(".session-controls button", has_text="End session").click()
        page.locator(".historian-verdict blockquote").wait_for(state="visible", timeout=40000)
        page.wait_for_timeout(500)
        verdict = page.locator(".historian-verdict blockquote").inner_text().strip()
        rep.steps["end_screen"] = "PASS" if bool(verdict) else "FAIL"
        rep.details["historian_verdict"] = verdict
        rep.layout_notes.extend(_check_layout(page, f"{plan.id}_end_screen"))
        if plan.id != "one_berth":
            _scan_leaks("end_screen_dom", _visible_page_text_excluding_picker(page), rep.leaks)
            _scan_leaks("historian_verdict", verdict, rep.leaks)

    finally:
        page.remove_listener("console", on_console)
        page.remove_listener("response", on_resp)
        page.remove_listener("pageerror", on_pageerr)
        rep.console_errors = c_errs
        rep.http_errors = h_errs
        rep.page_errors = p_errs

    return rep


def run_all_cards(
    web_url: str,
    api_base: str,
    *,
    screens_dir: Path = SCREENS_DIR,
    viewport: tuple[int, int] = (1600, 900),
) -> list[CardReport]:
    screens_dir.mkdir(parents=True, exist_ok=True)
    reports: list[CardReport] = []
    with sync_playwright() as p:
        launch_kwargs: dict[str, Any] = {
            "headless": True,
            "args": ["--autoplay-policy=no-user-gesture-required"],
        }
        chrome_bin = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome_bin.exists():
            launch_kwargs["executable_path"] = str(chrome_bin)
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        context.add_init_script(
            """
            (() => {
              window.__playedAudio = [];
              const origPlay = HTMLMediaElement.prototype.play;
              HTMLMediaElement.prototype.play = function(...args) {
                try {
                  window.__playedAudio.push(this.currentSrc || this.src || '(audio)');
                } catch {}
                return origPlay.apply(this, args);
              };
            })();
            """
        )
        page = context.new_page()
        for plan in CARDS:
            print(f"\n=== Playing card: {plan.id} ({plan.title}) @ {viewport[0]}x{viewport[1]} ===", flush=True)
            rep = run_card(page, api_base, web_url, plan, screens_dir)
            reports.append(rep)
            for step, status in rep.steps.items():
                print(f"  {step:<22} {status}", flush=True)
            print(f"  needle:   {rep.details.get('needle', {}).get('caption_ui')}", flush=True)
            print(f"  replay 0: {rep.details.get('replay_0', {}).get('changed')}", flush=True)
            print(f"  replay+5: {rep.details.get('replay_plus5', {}).get('changed')}", flush=True)
            print(f"  errors:   console={len(rep.console_errors)} http={len(rep.http_errors)} page={len(rep.page_errors)} layout={len(rep.layout_notes)}", flush=True)
            print(f"  leaks:    {len(rep.leaks)}", flush=True)
            for lk in rep.leaks:
                print(f"    ! LEAK: {lk}", flush=True)
            print(f"  shot:     {rep.screenshot}", flush=True)
        browser.close()
    return reports


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Play all four crisis cards offline in Chromium at 1600x900")
    ap.add_argument("--offline", action="store_true", help="Launch scripts/demo.sh --offline")
    ap.add_argument("--url", help="Already-running web UI URL")
    ap.add_argument("--api", help="Already-running backend URL")
    ap.add_argument("--out-dir", default=str(SCREENS_DIR))
    ap.add_argument("--json-out", help="Optional path to save full JSON report")
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
            if args.offline or not args.url:
                cmd.insert(1, "--offline")
            proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            api_base = f"http://127.0.0.1:{bport}"
            web_url = f"http://127.0.0.1:{wport}"
            _wait_http(f"{api_base}/state", 30.0)
            _wait_http(f"{web_url}/", 30.0)

        reports = run_all_cards(web_url, api_base, screens_dir=Path(args.out_dir))
        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps([asdict(r) for r in reports], indent=2),
                encoding="utf-8",
            )
        any_fail = any(
            status != "PASS"
            for r in reports
            for status in r.steps.values()
        ) or any(r.console_errors or r.http_errors or r.page_errors for r in reports)
        return 1 if any_fail else 0
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
