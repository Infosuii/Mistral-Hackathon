"""N1: End-to-end demo-path test for GAMBIT (ideas.md §17).

Runs the five-minute demo beat by beat against a live backend on the demo seed
and prints PASS or FAIL with the elapsed time for each beat.

    python -m e2e.demo_path                 # typed calls against a live backend
    python -m e2e.demo_path --mode audio    # real WAV clips through /call (covers STT)
    python -m e2e.demo_path --mode both     # typed, then audio
    python -m e2e.demo_path --url http://127.0.0.1:8000  # use a running server
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from contracts.models import (
    NATION_IDS,
    CallResponse,
    FuturesResponse,
    LeaderDetail,
    ReplayResponse,
    State,
    WiretapResponse,
)

ROOT = Path(__file__).resolve().parent.parent
CLIPS_DIR = Path(__file__).resolve().parent / "clips"

# Scripted player lines for the five-minute demo path.
DEMO_LINES = {
    "strategy_trade": (
        "Your Majesty, Valdoria wants to trade chips for your food today. "
        "Please agree to a trade deal with Valdoria."
    ),
    "promise_ostrava": (
        "General Dravic, I promise Ostrava the berth for the whole day. "
        "Your grain ships will dock and unload."
    ),
    "promise_zarnia": (
        "Premier, I promise Zarnia the berth for the entire day. "
        "Your grain ships will have the berth."
    ),
    "interrupt_blockade": (
        "Stop, hear me out before you announce anything! "
        "I offer Ostrava the berth in the morning right now if you wait and do not blockade."
    ),
}


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _snapshot_id(state: State) -> str:
    """Matches engine.snapshots.snapshot() deterministically over HTTP."""
    js = state.model_dump_json(by_alias=True)
    return "s_" + hashlib.sha256(js.encode()).hexdigest()[:12]


def _ensure_wav_clip(key: str, text: str) -> bytes:
    """Return a real spoken WAV clip for `text`, caching under e2e/clips/.

    Prefers Voxtral TTS (wav) so it works on any OS when MISTRAL_API_KEY is set,
    falling back to macOS `say` + `afconvert` if TTS fails.
    """
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    wav_path = CLIPS_DIR / f"{key}_{digest}.wav"
    if wav_path.exists() and wav_path.stat().st_size > 44:
        return wav_path.read_bytes()

    tts_err: Exception | None = None
    if os.environ.get("MISTRAL_API_KEY"):
        try:
            from voice.audio import speak_to_file
            casting = json.loads((ROOT / "voice" / "casting.json").read_text(encoding="utf-8"))
            voice_id = casting["_player_test_voice"]["voice_id"]
            src, _, _ = asyncio.run(speak_to_file(text, voice_id, "calm", "wav"))
            data = src.read_bytes()
            if data[:4] == b"RIFF":
                wav_path.write_bytes(data)
                return data
        except Exception as e:  # noqa: BLE001
            tts_err = e

    # Fallback: macOS speech synthesizer -> 16 kHz mono PCM WAV.
    if shutil.which("say") and shutil.which("afconvert"):
        with tempfile.TemporaryDirectory() as td:
            aiff = Path(td) / "clip.aiff"
            subprocess.run(["say", "-o", str(aiff), text], check=True)
            subprocess.run(
                ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav_path)],
                check=True,
            )
            return wav_path.read_bytes()

    raise RuntimeError(f"cannot generate WAV clip for {key!r} (TTS error: {tts_err})")


class Client:
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def request_json(self, method: str, path: str, body: Any = None, timeout: float | None = None) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"content-type": "application/json"} if data is not None else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from e

    def fetch_bytes(self, path: str, timeout: float = 30.0) -> tuple[int, bytes]:
        url = path if path.startswith("http") else self.base + path
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"GET {path} -> HTTP {e.code}: {detail}") from e

    def wait_ready(self, seconds: float = 20.0) -> None:
        deadline = time.perf_counter() + seconds
        last_err: Exception | None = None
        while time.perf_counter() < deadline:
            try:
                self.request_json("GET", "/state", timeout=3.0)
                return
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(0.2)
        raise RuntimeError(f"server at {self.base} did not become ready in {seconds:.0f}s: {last_err}")

    def state(self) -> State:
        return State.model_validate(self.request_json("GET", "/state"))

    def start(self, seed: int = 7, role: str = "president", nation: str = "valdoria") -> State:
        return State.model_validate(
            self.request_json("POST", "/start", {"seed": seed, "seat": {"role": role, "nation": nation}})
        )

    def turn(self) -> State:
        return State.model_validate(self.request_json("POST", "/turn", timeout=60.0))

    def start_crisis(self, crisis_id: str = "one_berth") -> State:
        return State.model_validate(self.request_json("POST", "/crisis/start", {"id": crisis_id}))

    def call_leader(
        self,
        to: str,
        *,
        text: str | None = None,
        audio_wav: bytes | None = None,
        interrupted: bool = False,
        hesitation_ms: int = 900,
        wait_interpret_s: float = 55.0,
    ) -> tuple[CallResponse, State, float, float]:
        """POST /call, fetch reply audio, and wait for split interpret() if pending.

        Returns (CallResponse, State after interpret, call_s, interpret_s).
        """
        payload: dict[str, Any] = {
            "to": to,
            "interrupted": interrupted,
            "hesitation_ms": hesitation_ms,
        }
        if audio_wav is not None:
            payload["audio"] = base64.b64encode(audio_wav).decode("ascii")
            payload["text"] = None
        else:
            payload["text"] = text
            payload["audio"] = None

        t0 = time.perf_counter()
        raw = self.request_json("POST", "/call", payload, timeout=45.0)
        call_s = time.perf_counter() - t0
        resp = CallResponse.model_validate(raw)

        if resp.reply_audio_url:
            status, audio_bytes = self.fetch_bytes(resp.reply_audio_url, timeout=30.0)
            if status != 200 or len(audio_bytes) < 256:
                raise RuntimeError(
                    f"reply audio {resp.reply_audio_url} invalid (status={status}, bytes={len(audio_bytes)})"
                )

        interp_t0 = time.perf_counter()
        st = self.state()
        if resp.pending and resp.call_id:
            deadline = time.perf_counter() + wait_interpret_s
            while time.perf_counter() < deadline:
                st = self.state()
                lc = st.last_call
                if lc is not None and lc.call_id == resp.call_id and not lc.pending:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(
                    f"interpret() for call {resp.call_id} to {to} stayed pending after {wait_interpret_s:.0f}s"
                )
        interp_s = time.perf_counter() - interp_t0
        return resp, st, call_s, interp_s


@dataclass
class BeatResult:
    name: str
    passed: bool
    elapsed_s: float
    detail: str


def _start_backend(port: int, extra_env: dict[str, str] | None = None) -> tuple[subprocess.Popen, Path]:
    env = os.environ.copy()
    env.setdefault("GAMBIT_DECIDE_MODEL", "mistral-large-2512")
    env.setdefault("VOICE_WIRETAP", "demo")
    if extra_env:
        env.update(extra_env)
    log_file = Path(tempfile.gettempdir()) / f"gambit_e2e_{port}.log"
    fh = log_file.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "engine.app:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "info"],
        cwd=str(ROOT),
        env=env,
        stdout=fh,
        stderr=subprocess.STDOUT,
    )
    proc._e2e_log_fh = fh  # type: ignore[attr-defined]
    return proc, log_file


def _stop_backend(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:  # noqa: BLE001
        proc.kill()
    fh = getattr(proc, "_e2e_log_fh", None)
    if fh is not None:
        fh.close()


def run_demo_path(
    client: Client,
    *,
    mode: str = "typed",
    seed: int = 7,
    shift_ticks: int = 3,
    allow_fallback_reply: bool = False,
) -> list[BeatResult]:
    results: list[BeatResult] = []
    ctx: dict[str, Any] = {}

    def send_call(to: str, line_key: str, *, interrupted: bool = False, hesitation_ms: int = 900):
        text = DEMO_LINES[line_key]
        if mode == "audio":
            wav = _ensure_wav_clip(line_key, text)
            resp, st, call_s, interp_s = client.call_leader(
                to, audio_wav=wav, interrupted=interrupted, hesitation_ms=hesitation_ms
            )
            if not resp.transcript.strip():
                raise AssertionError(f"STT returned empty transcript for audio clip {line_key}")
        else:
            resp, st, call_s, interp_s = client.call_leader(
                to, text=text, interrupted=interrupted, hesitation_ms=hesitation_ms
            )
        if not allow_fallback_reply and resp.reply_text == "The line is breaking up. Say that again.":
            raise AssertionError(f"/call {to} returned fallback line (API key missing or model error)")
        return resp, st, call_s, interp_s

    def beat(name: str, fn: Callable[[], str]) -> bool:
        t0 = time.perf_counter()
        try:
            detail = fn()
            elapsed = time.perf_counter() - t0
            results.append(BeatResult(name, True, elapsed, detail))
            print(f"PASS  {elapsed:6.2f}s  {name:<20}  {detail}")
            return True
        except Exception as e:  # noqa: BLE001
            elapsed = time.perf_counter() - t0
            msg = f"{type(e).__name__}: {e}"
            results.append(BeatResult(name, False, elapsed, msg))
            print(f"FAIL  {elapsed:6.2f}s  {name:<20}  {msg}")
            return False

    # Beat 1: start as President of Valdoria
    def beat_start() -> str:
        st = client.start(seed=seed, role="president", nation="valdoria")
        assert st.turn == 0, f"expected turn 0, got {st.turn}"
        assert st.phase == "strategy", f"expected strategy phase, got {st.phase}"
        assert st.seat.role == "president" and st.seat.nation == "valdoria", st.seat
        assert set(st.nations.keys()) == set(NATION_IDS)
        ctx["state"] = st
        return f"seed={st.seed} seat={st.seat.role}/{st.seat.nation} turn={st.turn}"

    if not beat("start_valdoria", beat_start):
        return results

    # Beat 2: one strategy-phase call that produces a visible change
    def beat_strategy_call() -> str:
        before: State = ctx["state"]
        target = "kessaria"
        b_beliefs = before.nations[target].beliefs
        b_links = {(l.type, tuple(sorted((l.a, l.b)))) for l in before.links if "valdoria" in (l.a, l.b)}
        b_rel = dict(before.relations)

        resp, after_call, call_s, interp_s = send_call(target, "strategy_trade")
        after_turn = client.turn()
        a_beliefs = after_call.nations[target].beliefs
        a_links = {(l.type, tuple(sorted((l.a, l.b)))) for l in after_turn.links if "valdoria" in (l.a, l.b)}
        lc = after_call.last_call

        changes = []
        if b_beliefs != a_beliefs:
            changes.append(
                f"beliefs trust {b_beliefs.trust_in_player}->{a_beliefs.trust_in_player}, "
                f"resolve {b_beliefs.resolve_of_player}->{a_beliefs.resolve_of_player}"
            )
        if lc and lc.actions:
            changes.append(f"actions={[a.type for a in lc.actions]}")
        if lc and lc.promises:
            changes.append(f"promises={len(lc.promises)}")
        new_links = a_links - b_links
        if new_links:
            changes.append(f"new_links={sorted(new_links)}")
        if after_call.relations != b_rel:
            changes.append("relations_changed")
        assert changes, (
            f"strategy call to {target} produced no visible change "
            f"(reply={resp.reply_text!r}, last_call={lc})"
        )
        ctx["state"] = after_turn
        return (
            f"to={target} call={call_s:.2f}s interp={interp_s:.2f}s "
            f"emotion={resp.emotion} ({'; '.join(changes)})"
        )

    beat("strategy_call", beat_strategy_call)

    # Beat 3: start One Berth
    def beat_start_crisis() -> str:
        st = client.start_crisis("one_berth")
        assert st.phase == "crisis" and st.crisis is not None
        assert st.crisis.id == "one_berth" and st.crisis.tick == 0
        ctx["crisis_start_sid"] = _snapshot_id(st)

        st1 = client.turn()
        assert st1.crisis is not None and st1.crisis.tick == 1
        assert st1.incoming_call is not None and st1.incoming_call.from_ == "ostrava", (
            f"expected tick-1 incoming_call from ostrava, got {st1.incoming_call}"
        )
        if st1.incoming_call.audio_url:
            code, raw = client.fetch_bytes(st1.incoming_call.audio_url)
            assert code == 200 and len(raw) > 256, f"bad ring audio: {code} ({len(raw)} bytes)"
        ctx["state"] = st1
        return f"crisis=one_berth tick=1 ring={st1.incoming_call.from_} sid={ctx['crisis_start_sid']}"

    if not beat("start_one_berth", beat_start_crisis):
        return results

    # Beat 4: promise the berth to Ostrava (tick 1) and to Zarnia (tick 3)
    def beat_double_promise() -> str:
        resp_o, st_o, co, io = send_call("ostrava", "promise_ostrava")
        assert st_o.crisis is not None
        o_promises = [p for p in st_o.crisis.promises if p.by == "player" and p.to == "ostrava" and p.what == "berth"]
        assert o_promises, (
            f"expected berth promise to ostrava, got promises={st_o.crisis.promises}, "
            f"last_call={st_o.last_call}"
        )

        # Advance to tick 3 before calling Zarnia so +3 replay shifts Zarnia past tick-5 compare_notes.
        st = st_o
        while st.crisis and st.crisis.tick < 3:
            st = client.turn()
        assert st.crisis is not None and st.crisis.tick == 3

        resp_z, st_z, cz, iz = send_call("zarnia", "promise_zarnia")
        assert st_z.crisis is not None
        z_promises = [p for p in st_z.crisis.promises if p.by == "player" and p.to == "zarnia" and p.what == "berth"]
        assert z_promises, (
            f"expected berth promise to zarnia, got promises={st_z.crisis.promises}, "
            f"last_call={st_z.last_call}"
        )
        ctx["state"] = st_z
        ctx["trust_before_compare"] = {
            "ostrava": st_z.nations["ostrava"].beliefs.trust_in_player,
            "zarnia": st_z.nations["zarnia"].beliefs.trust_in_player,
        }
        return (
            f"ostrava=({o_promises[-1].what}/{o_promises[-1].when}, {co:.2f}s+{io:.2f}s) "
            f"zarnia=({z_promises[-1].what}/{z_promises[-1].when}, {cz:.2f}s+{iz:.2f}s)"
        )

    beat("double_promise", beat_double_promise)

    # Beat 5: reach compare-notes tick (tick 5) and check trust in the player fell
    def beat_compare_notes() -> str:
        st: State = ctx["state"]
        before_trust = ctx.get("trust_before_compare") or {
            "ostrava": st.nations["ostrava"].beliefs.trust_in_player,
            "zarnia": st.nations["zarnia"].beliefs.trust_in_player,
        }
        while st.crisis and st.crisis.tick < 5:
            st = client.turn()
        assert st.crisis is not None and st.crisis.tick == 5
        cn = [e for e in st.events if e.type == "compare_notes"]
        assert cn, f"no compare_notes event at tick 5; events={[e.type for e in st.events[-6:]]}"
        contradiction = (cn[-1].model_extra or {}).get("contradiction")
        assert contradiction is True, f"expected contradiction=True in compare_notes, got {cn[-1]}"

        after_trust = {
            "ostrava": st.nations["ostrava"].beliefs.trust_in_player,
            "zarnia": st.nations["zarnia"].beliefs.trust_in_player,
        }
        assert after_trust["ostrava"] < before_trust["ostrava"], (
            f"Ostrava trust did not fall: {before_trust['ostrava']} -> {after_trust['ostrava']}"
        )
        assert after_trust["zarnia"] < before_trust["zarnia"], (
            f"Zarnia trust did not fall: {before_trust['zarnia']} -> {after_trust['zarnia']}"
        )
        ctx["state"] = st
        return (
            f"contradiction=True ostrava {before_trust['ostrava']}->{after_trust['ostrava']}, "
            f"zarnia {before_trust['zarnia']}->{after_trust['zarnia']}"
        )

    beat("compare_notes", beat_compare_notes)

    # Beat 6: intel + wiretap (ideas.md §17 2:10 beat)
    def beat_intel_wiretap() -> str:
        detail = LeaderDetail.model_validate(client.request_json("GET", "/leaders/ostrava"))
        assert detail.persona, "empty leader persona"
        assert detail.advice, "empty leader advice"
        wt = WiretapResponse.model_validate(client.request_json("GET", "/wiretap?a=ostrava&b=kessaria"))
        assert len(wt.lines) >= 2, f"expected >=2 wiretap lines, got {len(wt.lines)}"
        if wt.lines[0].audio_url:
            code, raw = client.fetch_bytes(wt.lines[0].audio_url)
            assert code == 200 and len(raw) > 256, f"wiretap audio failed: {code} ({len(raw)} bytes)"
        return f"leader_advice={len(detail.advice)} wiretap_lines={len(wt.lines)}"

    beat("intel_wiretap", beat_intel_wiretap)

    # Beat 7: answer Ostrava's blockade call (tick 7) with interrupted=true and an offer
    def beat_interrupt_blockade() -> str:
        st: State = ctx["state"]
        while st.crisis and st.crisis.tick < 7:
            st = client.turn()
        assert st.crisis is not None and st.crisis.tick == 7
        assert st.incoming_call is not None and st.incoming_call.from_ == "ostrava", (
            f"expected tick-7 blockade call from ostrava, got {st.incoming_call}"
        )
        if st.incoming_call.audio_url:
            code, raw = client.fetch_bytes(st.incoming_call.audio_url)
            assert code == 200 and len(raw) > 256, f"tick-7 ring audio failed: {code}"

        rel_before = st.relations.get("ostrava|valdoria", 0)
        resp, st_after, call_s, interp_s = send_call(
            "ostrava", "interrupt_blockade", interrupted=True, hesitation_ms=400
        )
        rel_after = st_after.relations.get("ostrava|valdoria", 0)
        assert rel_after < rel_before or rel_before == -100, (
            f"expected interrupting proud Ostrava to cut relations: {rel_before} -> {rel_after}"
        )

        # Advance to tick 8: interrupting should have stopped the public blockade announcement.
        st8 = client.turn()
        assert st8.crisis is not None and st8.crisis.tick == 8
        public_blockade = [
            pc for pc in st8.crisis.public_commitments if pc.nation == "ostrava" and pc.action == "blockade"
        ]
        assert not public_blockade, (
            f"interrupted blockade still became a public commitment: {public_blockade}"
        )
        ctx["state"] = st8
        return (
            f"call={call_s:.2f}s interp={interp_s:.2f}s rel={rel_before}->{rel_after} "
            f"public_blockade=blocked emotion={resp.emotion}"
        )

    beat("interrupt_blockade", beat_interrupt_blockade)

    # Beat 8: pass the deadlines and check every nation decided
    def beat_deadlines() -> str:
        st: State = ctx["state"]
        ticks = 0
        while st.phase == "crisis":
            st = client.turn()
            ticks += 1
            if ticks > 20:
                raise AssertionError("crisis did not resolve within 20 ticks")
        assert st.phase == "strategy" and st.crisis is None, f"expected strategy after crisis, got {st.phase}"
        resolved = [e for e in st.events if e.type == "crisis_resolved"]
        assert resolved, f"missing crisis_resolved event; events={[e.type for e in st.events[-6:]]}"
        decisions = (resolved[-1].model_extra or {}).get("decisions") or {}
        missing = [n for n in NATION_IDS if n not in decisions]
        assert not missing, f"nations missing crisis decision: {missing} (got {decisions})"
        ctx["state"] = st
        summary = ", ".join(f"{n}={decisions[n]}" for n in NATION_IDS)
        return f"resolved ({summary})"

    if not beat("deadlines_resolve", beat_deadlines):
        return results

    # Beat 9: POST /futures and check before and after odds
    def beat_futures() -> str:
        sid = ctx["crisis_start_sid"]
        fut = FuturesResponse.model_validate(
            client.request_json("POST", "/futures", {"snapshot_id": sid}, timeout=30.0)
        )
        assert 0.0 <= fut.before.war_p <= 1.0 and 0.0 <= fut.after.war_p <= 1.0
        assert fut.caption.strip(), "empty futures caption"
        st = client.state()
        assert st.last_futures is not None, "state.last_futures not updated after POST /futures"
        return f"war_p {fut.before.war_p:.1%} -> {fut.after.war_p:.1%} | {fut.caption}"

    beat("futures", beat_futures)

    # Beat 10: POST /replay with a shift and check it names who changed
    def beat_replay() -> str:
        rep = ReplayResponse.model_validate(
            client.request_json("POST", "/replay", {"shift_ticks": shift_ticks}, timeout=30.0)
        )
        assert rep.shift_ticks == shift_ticks
        assert rep.changed, f"POST /replay shift_ticks={shift_ticks} returned no changed nations"
        for ch in rep.changed:
            assert ch.was != ch.now, f"replay change had identical action: {ch}"
            assert ch.why.strip(), f"replay change missing why: {ch}"
        summary = ", ".join(f"{c.nation}:{c.was}->{c.now}" for c in rep.changed)
        return f"shift={shift_ticks:+d} changed=[{summary}]"

    beat("replay", beat_replay)

    # Beat 11: POST /end and check the ending + historian verdict
    def beat_end() -> str:
        st = State.model_validate(client.request_json("POST", "/end"))
        assert st.phase == "ended", f"expected phase=ended, got {st.phase}"
        assert st.ending is not None, "state.ending is None"
        deadline = time.perf_counter() + 35.0
        while not (st.ending and st.ending.verdict):
            if time.perf_counter() >= deadline:
                raise AssertionError("historian verdict did not arrive within 35s")
            time.sleep(0.25)
            st = client.state()
        sc = st.ending.score
        verdict_preview = st.ending.verdict.replace("\n", " ")[:80]
        return (
            f"reason={st.ending.reason} months={sc.months_in_power} "
            f"kept={sc.promises_kept} broken={sc.promises_broken} verdict={verdict_preview!r}"
        )

    beat("end_session", beat_end)
    return results


def main(argv: list[str] | None = None) -> int:
    _load_env(ROOT / ".env")
    ap = argparse.ArgumentParser(description="GAMBIT end-to-end demo-path test (N1)")
    ap.add_argument("--mode", choices=["typed", "audio", "both"], default="typed")
    ap.add_argument("--url", help="Already-running backend URL (starts a temporary server if omitted)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--shift", type=int, default=3, help="shift_ticks for POST /replay")
    ap.add_argument("--decide-model", default=os.environ.get("GAMBIT_DECIDE_MODEL", "mistral-large-2512"))
    args = ap.parse_args(argv)

    if not args.url and not os.environ.get("MISTRAL_API_KEY"):
        print("FAIL  MISTRAL_API_KEY is not set (add it to .env or the environment to run live demo_path)")
        return 1

    modes = ["typed", "audio"] if args.mode == "both" else [args.mode]
    proc: subprocess.Popen | None = None
    log_file: Path | None = None
    try:
        if args.url:
            base = args.url
        else:
            port = _free_port()
            proc, log_file = _start_backend(port, {"GAMBIT_DECIDE_MODEL": args.decide_model})
            base = f"http://127.0.0.1:{port}"
        client = Client(base)
        client.wait_ready(20.0)

        all_ok = True
        for mode in modes:
            print(f"=== GAMBIT demo_path (mode={mode}, seed={args.seed}, url={base}) ===")
            t0 = time.perf_counter()
            beats = run_demo_path(client, mode=mode, seed=args.seed, shift_ticks=args.shift)
            total = time.perf_counter() - t0
            passed = sum(1 for b in beats if b.passed)
            failed = sum(1 for b in beats if not b.passed)
            status = "PASS" if failed == 0 and passed > 0 else "FAIL"
            print(f"--- {status}: {passed}/{len(beats)} beats passed in {total:.2f}s ---")
            if failed > 0:
                all_ok = False
        if not all_ok and log_file and log_file.exists():
            tail = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            print("\n--- backend log tail ---")
            print("\n".join(tail))
        return 0 if all_ok else 1
    finally:
        _stop_backend(proc)


if __name__ == "__main__":
    raise SystemExit(main())
