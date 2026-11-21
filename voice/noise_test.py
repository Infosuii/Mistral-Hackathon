"""Noise test: how well transcribe() holds up in a noisy room.

    python -m voice.noise_test            # live: about 80 transcriptions, ~1 minute
    python -m voice.noise_test --json out.json

Takes the spoken player lines from the e2e suite (e2e/demo_path.py DEMO_LINES and
e2e/timings.py BENCH_CALLS, rendered as WAV by e2e's own _ensure_wav_clip), mixes in
synthetic room noise at three levels, and transcribes each with voice.audio.transcribe()
(the same call /call and /transcribe use, with the game's context_bias names).

Room noise = babble (three other player lines played over each other, quieter, as if
people talk nearby) + pink noise (air conditioning / fan hum). It is synthetic: we have
no recording of the venue. Levels are signal-to-noise ratios over the whole clip:
  quiet room 20 dB, busy room 10 dB, loud hall 0 dB (noise as loud as the speaker).

Reports word accuracy (1 - WER, case and punctuation ignored) and, separately, whether
each game name in the line (Ostrava, Zarnia, Nordhaven, Kessaria, Valdoria, Port Kessar,
Dravic, Lindqvist) came through, and "intruders": names heard that the speaker never said
(picked up from the background talkers), which could send a promise to the wrong leader.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np  # dev tool only; not in requirements.txt

from . import audio  # loads .env before e2e checks for the key
from .audio import transcribe

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from e2e.demo_path import DEMO_LINES, _ensure_wav_clip  # noqa: E402
from e2e.timings import BENCH_CALLS  # noqa: E402

LEVELS = [("clean", None), ("quiet room 20 dB", 20.0), ("busy room 10 dB", 10.0), ("loud hall 0 dB", 0.0)]
NAMES = ["Ostrava", "Zarnia", "Nordhaven", "Kessaria", "Valdoria", "Port Kessar", "Dravic", "Lindqvist"]


def lines() -> list[tuple[str, str]]:
    out = [(k, v) for k, v in DEMO_LINES.items()]
    out += [(f"bench_{i + 1}", text) for i, (_, text, _, _) in enumerate(BENCH_CALLS)]
    return out


def read_wav(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data)) as w:
        assert w.getsampwidth() == 2, "expected 16-bit PCM"
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        if w.getnchannels() > 1:
            x = x.reshape(-1, w.getnchannels()).mean(axis=1)
        return x, w.getframerate()


def write_wav(x: np.ndarray, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def pink(n: int, rng: np.random.Generator) -> np.ndarray:
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(len(spec))
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0
    return np.fft.irfft(spec, n)


def room_noise(n: int, others: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    babble = np.zeros(n, dtype=np.float32)
    for o in others:
        start = rng.integers(0, max(1, len(o) - 1))
        seg = np.roll(o, -start)
        seg = np.resize(seg, n)  # loop if shorter
        babble += seg
    babble /= np.sqrt(np.mean(babble ** 2)) + 1e-9
    hum = pink(n, rng)
    hum /= np.sqrt(np.mean(hum ** 2)) + 1e-9
    return 0.8 * babble + 0.6 * hum


def mix(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    ps, pn = np.mean(speech ** 2), np.mean(noise ** 2)
    noise = noise * np.sqrt(ps / (pn * 10 ** (snr_db / 10)))
    out = speech + noise
    peak = np.max(np.abs(out))
    return out / peak * 0.9 if peak > 0.99 else out


def said(name: str, text: str) -> bool:
    """Whole-name match: "Port Kessaria" does not count as "Port Kessar"."""
    return re.search(r"\b" + re.escape(name.lower()) + r"\b", text.lower()) is not None


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]+", " ", s.lower().replace("—", " ").replace("-", " ")).split()


def wer(ref: str, hyp: str) -> float:
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r))


def load_clips() -> list[tuple[str, str, np.ndarray, int]]:
    """Outside the event loop: e2e's _ensure_wav_clip renders missing clips with asyncio.run."""
    return [(key, text, *read_wav(_ensure_wav_clip(key, text))) for key, text in lines()]


async def run(clips: list) -> dict:
    rng = np.random.default_rng(7)
    results = {name: [] for name, _ in LEVELS}
    for i, (key, text, x, rate) in enumerate(clips):
        others = [c[2] for j, c in enumerate(clips) if j != i and c[3] == rate]
        others = [others[k] for k in rng.choice(len(others), 3, replace=False)]
        noise = room_noise(len(x), others, rng)
        for name, snr in LEVELS:
            y = x if snr is None else mix(x, noise, snr)
            t0 = time.perf_counter()
            try:
                hyp = await transcribe(write_wav(y, rate), "audio/wav")
            except Exception as e:  # noqa: BLE001
                hyp = f"<error: {e}>"
            names = [n for n in NAMES if said(n, text)]
            intruders = [n for n in NAMES if n not in names and said(n, hyp)]
            kept = [n for n in names if said(n, hyp)]  # "Port Kessaria" != "Port Kessar"
            results[name].append({"key": key, "ref": text, "hyp": hyp, "wer": round(wer(text, hyp), 3),
                                  "names": names, "names_kept": kept, "intruders": intruders, "s": round(time.perf_counter() - t0, 2)})
    return results


def summary(results: dict) -> list[dict]:
    rows = []
    for name, rs in results.items():
        names = sum(len(r["names"]) for r in rs)
        kept = sum(len(r["names_kept"]) for r in rs)
        rows.append({"level": name, "clips": len(rs),
                     "word_accuracy": round(1 - float(np.mean([min(1.0, r["wer"]) for r in rs])), 3),
                     "exact_lines": sum(r["wer"] == 0 for r in rs),
                     "names_kept": f"{kept}/{names}",
                     "intruding_names": sum(len(r["intruders"]) for r in rs),
                     "missed": sorted({n for r in rs for n in r["names"] if n not in r["names_kept"]}),
                     "stt_median_s": round(float(np.median([r["s"] for r in rs])), 2)})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write every transcript here")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    results = asyncio.run(run(load_clips()))
    rows = summary(results)
    print(f"{'level':18} {'clips':>5} {'word acc':>9} {'exact':>6} {'names kept':>11} {'intruders':>9}  missed")
    for r in rows:
        print(f"{r['level']:18} {r['clips']:>5} {r['word_accuracy']:>9.1%} {r['exact_lines']:>6} "
              f"{r['names_kept']:>11} {r['intruding_names']:>9}  {', '.join(r['missed']) or '-'}")
    for name, rs in results.items():
        for r in rs:
            if r["names"] != r["names_kept"] or r["intruders"] or r["wer"] > 0.2:
                print(f"  [{name}] {r['key']}: {r['hyp']}")
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": rows, "results": results}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
