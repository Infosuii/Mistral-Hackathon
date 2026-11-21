"""N3: Live latency benchmark for GAMBIT pitch numbers.

Makes 10 live voice calls (real WAV clips -> Voxtral STT -> speak_fast ->
streamed Voxtral TTS first chunk -> Large 4 interpret) plus /futures and /replay,
and prints the median and worst (max) time for every stage.

    python -m e2e.timings
    python -m e2e.timings --calls 10 --url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

import httpx

from contracts.models import CallResponse, FuturesResponse, ReplayResponse, State
from e2e.demo_path import (
    ROOT,
    Client,
    _ensure_wav_clip,
    _free_port,
    _load_env,
    _snapshot_id,
    _start_backend,
    _stop_backend,
)

# Ten distinct realistic player lines across all four AI leaders so TTS never hits disk cache.
BENCH_CALLS: list[tuple[str, str, bool, int]] = [
    ("ostrava", "General Dravic, I promise Ostrava the berth in the morning if you hold your ships.", False, 650),
    ("zarnia", "Premier, Valdoria will secure the evening berth for Zarnia once the storm clears.", False, 800),
    ("nordhaven", "Chancellor Lindqvist, send your tugs to Port Kessar now and we can open a second berth.", False, 500),
    ("kessaria", "Your Majesty, split the port schedule today and Valdoria will sign a chip trade deal.", False, 700),
    ("ostrava", "Stop, hear me out before you announce anything! Take the morning berth and stand down.", True, 300),
    ("zarnia", "Zarnia gets grain priority after dusk; mobilising on the border helps nobody.", False, 900),
    ("nordhaven", "If Nordhaven stays out, Ostrava and Zarnia go to war by dawn. We need those tugs.", False, 600),
    ("kessaria", "Closing Port Kessar costs your treasury dearly; keep one berth open for Valdorian grain.", False, 750),
    ("ostrava", "Wait—do not blockade the strait. Give us six hours and both ships unload safely.", True, 250),
    ("zarnia", "Hold your troops at the border and I guarantee your grain ship docks before midnight.", False, 850),
]


def _summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"median": 0.0, "worst": 0.0, "min": 0.0}
    return {
        "median": round(statistics.median(values), 2),
        "worst": round(max(values), 2),
        "min": round(min(values), 2),
    }


def _measure_stt(http: httpx.Client, base: str, wav: bytes) -> tuple[str, float, list[str]]:
    errors: list[str] = []
    for attempt in range(2):
        t0 = time.perf_counter()
        r = http.post(f"{base}/transcribe", content=wav, headers={"content-type": "audio/wav"}, timeout=30.0)
        dt = time.perf_counter() - t0
        if r.status_code == 200:
            text = r.json().get("text", "").strip()
            if not text:
                raise RuntimeError("POST /transcribe returned empty transcript")
            return text, dt, errors
        detail = r.text[:300]
        errors.append(f"attempt {attempt + 1}: HTTP {r.status_code} {detail}")
        if attempt == 0 and r.status_code in (429, 502, 503, 504):
            time.sleep(0.5)
            continue
        raise RuntimeError(f"POST /transcribe failed: HTTP {r.status_code}: {detail}")
    raise RuntimeError("POST /transcribe exhausted retries")


def _measure_first_audio(http: httpx.Client, base: str, audio_url: str) -> tuple[float, int]:
    url = audio_url if audio_url.startswith("http") else f"{base}{audio_url}"
    t0 = time.perf_counter()
    first_s: float | None = None
    total_bytes = 0
    with http.stream("GET", url, timeout=30.0) as r:
        r.raise_for_status()
        for chunk in r.iter_bytes(chunk_size=1024):
            if chunk:
                if first_s is None:
                    first_s = time.perf_counter() - t0
                total_bytes += len(chunk)
    return (first_s if first_s is not None else time.perf_counter() - t0), total_bytes


def _wait_interpret(client: Client, call_id: str, timeout_s: float = 55.0) -> float:
    t0 = time.perf_counter()
    deadline = t0 + timeout_s
    while time.perf_counter() < deadline:
        st = client.state()
        lc = st.last_call
        if lc is not None and lc.call_id == call_id and not lc.pending:
            return time.perf_counter() - t0
        time.sleep(0.1)
    raise RuntimeError(f"interpret() for {call_id} did not finish within {timeout_s:.0f}s")


def run_timings(base: str, num_calls: int = 10, seed: int = 7) -> dict[str, Any]:
    client = Client(base)
    http = httpx.Client()
    try:
        # Pre-generate the WAV clips before starting the stopwatch.
        clips: list[tuple[str, str, bool, int, bytes]] = []
        for idx in range(num_calls):
            nation, line, interrupted, hes = BENCH_CALLS[idx % len(BENCH_CALLS)]
            wav = _ensure_wav_clip(f"bench_{idx + 1}", line)
            clips.append((nation, line, interrupted, hes, wav))

        # Start One Berth tick 1 so calls happen in realistic crisis context.
        client.start(seed=seed, role="president", nation="valdoria")
        client.start_crisis("one_berth")
        client.turn()

        call_rows: list[dict[str, Any]] = []
        stt_errors: list[str] = []
        for i, (nation, line, interrupted, hes, wav) in enumerate(clips, start=1):
            transcript, stt_s, errs = _measure_stt(http, base, wav)
            if errs:
                stt_errors.extend(f"call {i}: {e}" for e in errs)
                print(f"  [note] call {i} STT retried: {errs[-1]}")

            t_call = time.perf_counter()
            raw = client.request_json(
                "POST",
                "/call",
                {
                    "to": nation,
                    "audio": None,
                    "text": transcript,
                    "interrupted": interrupted,
                    "hesitation_ms": hes,
                },
                timeout=45.0,
            )
            reply_s = time.perf_counter() - t_call
            t_after_call = time.perf_counter()
            resp = CallResponse.model_validate(raw)

            tts_first_s, audio_bytes = (
                _measure_first_audio(http, base, resp.reply_audio_url)
                if resp.reply_audio_url
                else (0.0, 0)
            )
            first_audio_s = stt_s + reply_s + tts_first_s

            if resp.pending and resp.call_id:
                _wait_interpret(client, resp.call_id)
                interp_total_s = time.perf_counter() - t_after_call
            else:
                interp_total_s = 0.0

            row = {
                "n": i,
                "to": nation,
                "stt_s": round(stt_s, 2),
                "reply_s": round(reply_s, 2),
                "tts_first_s": round(tts_first_s, 2),
                "first_audio_s": round(first_audio_s, 2),
                "interpret_s": round(interp_total_s, 2),
                "emotion": resp.emotion,
                "audio_bytes": audio_bytes,
                "fallback": resp.reply_text == "The line is breaking up. Say that again.",
            }
            call_rows.append(row)
            print(
                f"call {i:2d}/{num_calls}  to={nation:<9}  stt={row['stt_s']:4.2f}s  "
                f"reply={row['reply_s']:4.2f}s  tts1={row['tts_first_s']:4.2f}s  "
                f"first_audio={row['first_audio_s']:4.2f}s  interp={row['interpret_s']:5.2f}s  "
                f"[{resp.emotion}]"
            )

        # Measure /futures and /replay across a fresh One Berth run with Nordhaven tugs.
        futures_times: list[float] = []
        replay_times: list[float] = []
        replay_flips: list[int] = []

        for run_idx, test_seed in enumerate((seed, seed + 1, seed + 2), start=1):
            client.start(seed=test_seed, role="president", nation="valdoria")
            cs = client.start_crisis("one_berth")
            sid = _snapshot_id(cs)
            st = client.turn()  # tick 1
            # Promise Ostrava (tick 1), Zarnia (tick 3), Nordhaven tugs (tick 4)
            for target, tick_target, msg in (
                ("ostrava", 1, "General Dravic, I promise Ostrava the berth for the whole day."),
                ("zarnia", 3, "Premier, I promise Zarnia the berth for the whole day."),
                ("nordhaven", 4, "Chancellor Lindqvist, please send tugs now to open a second berth."),
            ):
                while st.crisis and st.crisis.tick < tick_target:
                    st = client.turn()
                r_raw = client.request_json(
                    "POST",
                    "/call",
                    {"to": target, "audio": None, "text": msg, "interrupted": False, "hesitation_ms": 600},
                )
                cr = CallResponse.model_validate(r_raw)
                if cr.pending and cr.call_id:
                    _wait_interpret(client, cr.call_id)
                st = client.state()

            while st.phase == "crisis":
                st = client.turn()

            t_f = time.perf_counter()
            FuturesResponse.model_validate(client.request_json("POST", "/futures", {"snapshot_id": sid}, timeout=30.0))
            futures_times.append(time.perf_counter() - t_f)

            t_r = time.perf_counter()
            rep = ReplayResponse.model_validate(
                client.request_json("POST", "/replay", {"shift_ticks": 3}, timeout=30.0)
            )
            replay_times.append(time.perf_counter() - t_r)
            replay_flips.append(len(rep.changed))
            print(
                f"crisis {run_idx}/3 (seed={test_seed})  /futures={futures_times[-1]:.2f}s  "
                f"/replay(+3)={replay_times[-1]:.2f}s (flips={len(rep.changed)})"
            )

        summary = {
            "calls_count": len(call_rows),
            "fallbacks": sum(1 for r in call_rows if r["fallback"]),
            "stt_retries": stt_errors,
            "stt_s": _summary([r["stt_s"] for r in call_rows]),
            "spoken_reply_s": _summary([r["reply_s"] for r in call_rows]),
            "tts_first_chunk_s": _summary([r["tts_first_s"] for r in call_rows]),
            "first_audio_s": _summary([r["first_audio_s"] for r in call_rows]),
            "interpret_s": _summary([r["interpret_s"] for r in call_rows]),
            "futures_s": _summary(futures_times),
            "replay_s": _summary(replay_times),
            "replay_flips": replay_flips,
            "calls": call_rows,
        }
        return summary
    finally:
        http.close()


def print_report(summary: dict[str, Any]) -> None:
    print("\n=== GAMBIT Pitch Timings (N3) ===")
    print(f"{'Stage':<22} {'Median':>8} {'Worst':>8} {'Min':>8}")
    print("-" * 50)
    labels = [
        ("Speech to text (STT)", "stt_s"),
        ("Spoken reply (LLM)", "spoken_reply_s"),
        ("TTS first chunk", "tts_first_chunk_s"),
        ("First audio (total)", "first_audio_s"),
        ("Interpret (Large 4)", "interpret_s"),
        ("POST /futures", "futures_s"),
        ("POST /replay (+3)", "replay_s"),
    ]
    for label, key in labels:
        s = summary[key]
        print(f"{label:<22} {s['median']:7.2f}s {s['worst']:7.2f}s {s['min']:7.2f}s")
    print(f"\nCalls: {summary['calls_count']} (fallbacks: {summary['fallbacks']}); replay flips: {summary['replay_flips']}")


def main(argv: list[str] | None = None) -> int:
    _load_env(ROOT / ".env")
    ap = argparse.ArgumentParser(description="GAMBIT live call, /futures and /replay timings (N3)")
    ap.add_argument("--calls", type=int, default=10)
    ap.add_argument("--url", help="Already-running backend URL (starts a temporary server if omitted)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", help="Optional path to write JSON results")
    args = ap.parse_args(argv)

    if not args.url and not os.environ.get("MISTRAL_API_KEY"):
        print("FAIL  MISTRAL_API_KEY is not set", file=sys.stderr)
        return 1

    cache = tempfile.TemporaryDirectory()
    proc: subprocess.Popen | None = None
    try:
        if args.url:
            base = args.url.rstrip("/")
        else:
            port = _free_port()
            proc, _ = _start_backend(port, {"GAMBIT_DECIDE_MODEL": "mistral-medium-latest", "GAMBIT_VOICE_CACHE": cache.name})
            base = f"http://127.0.0.1:{port}"
        Client(base).wait_ready(20.0)
        summary = run_timings(base, num_calls=args.calls, seed=args.seed)
        print_report(summary)
        if args.out:
            Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(f"Wrote {args.out}")
        return 0
    finally:
        _stop_backend(proc)
        cache.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
