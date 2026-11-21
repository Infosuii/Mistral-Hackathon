"""Coordinator REQUEST on #28 (13:34): seed 7, 20 turns on the demo's decide setting, with a
spoken call overlapping turn work, against the real server.

    uvicorn engine.app:app --port 8770 &      (with .env loaded)
    python -m agents.test_overlap [base_url]

Each month: POST /turn, and 0.3 s later (every other month) a typed POST /call to a leader,
so the call's reply and TTS share the API quota with the four decide() calls. Measures turn
time, adviser fallbacks (/leaders reason "Fell back..."), /call time and time to the first
audio byte (call start to first byte of reply_audio_url). The game ends at month 12, so a
fresh seed-7 game starts then; all 20 turns are real.
"""
import asyncio
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8770"
AI = ["ostrava", "kessaria", "nordhaven", "zarnia"]
LINES = ["General, what would it take to keep the strait open?",
         "Your Majesty, can we agree on fair harbour fees this month?",
         "Chancellor, will you trade chips for our grain?",
         "Chairman, Valdoria wants peace with Zarnia. What do you need?"]


async def call(c: httpx.AsyncClient, to: str, text: str) -> tuple[float, float, str]:
    t0 = time.perf_counter()
    r = await c.post(f"{BASE}/call", json={"to": to, "text": text, "interrupted": False, "hesitation_ms": 600})
    r.raise_for_status()
    t_call = time.perf_counter() - t0
    body = r.json()
    url = body.get("reply_audio_url")
    t_audio = float("nan")
    if url:
        async with c.stream("GET", url if url.startswith("http") else BASE + url) as a:
            async for _ in a.aiter_bytes():
                t_audio = time.perf_counter() - t0
                break
    return t_call, t_audio, body.get("reply_text", "")


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as c:
        start = {"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}
        (await c.post(f"{BASE}/start", json=start)).raise_for_status()
        turns, calls, fallbacks = [], [], 0
        for m in range(20):
            if (await c.get(f"{BASE}/state")).json()["phase"] == "ended":  # the game ends at month 12
                print("-- game ended; new seed-7 game --")
                (await c.post(f"{BASE}/start", json=start)).raise_for_status()
            t0 = time.perf_counter()
            turn = asyncio.create_task(c.post(f"{BASE}/turn"))
            ph = None
            if m % 2 == 0:
                await asyncio.sleep(0.3)
                to = AI[(m // 2) % 4]
                ph = asyncio.create_task(call(c, to, LINES[(m // 2) % 4]))
            r = await turn
            r.raise_for_status()
            dt = time.perf_counter() - t0
            turns.append(dt)
            fb = 0
            for n in AI:
                d = (await c.get(f"{BASE}/leaders/{n}")).json()
                fb += str(d.get("reason", "")).startswith("Fell back")
            fallbacks += fb
            line = f"month {r.json()['turn']:2d}: turn {dt:4.1f}s fallbacks {fb}"
            if ph:
                tc, ta, text = await ph
                calls.append((tc, ta))
                line += f" | call {tc:4.1f}s first audio {ta:4.1f}s: {text[:70]}"
            print(line, flush=True)
        turns.sort()
        ta = sorted(x[1] for x in calls)
        tc = sorted(x[0] for x in calls)
        print(f"\nturns: median {turns[10]:.1f}s max {turns[-1]:.1f}s; adviser fallbacks {fallbacks}/80; "
              f"calls {len(calls)}: reply+TTS median {tc[len(tc) // 2]:.1f}s max {tc[-1]:.1f}s; "
              f"first audio median {ta[len(ta) // 2]:.1f}s max {ta[-1]:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
