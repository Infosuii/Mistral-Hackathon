"""GAMBIT as an MCP server, so Mistral Vibe can read and play the game.

    python -m gambit_mcp.server          # stdio; talks to the backend at GAMBIT_URL

The backend must already be running (`uvicorn engine.app:app --port 8000`). Every tool
returns short plain text. Backend failures come back as one plain-English line, never
a traceback, so the model can tell the player what to do.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import time
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

GAMBIT_URL = os.environ.get("GAMBIT_URL", "http://127.0.0.1:8000").rstrip("/")
NATIONS = ("valdoria", "ostrava", "kessaria", "nordhaven", "zarnia")
CALL_WAIT_S = float(os.environ.get("GAMBIT_CALL_WAIT_S", "25"))

logging.getLogger("httpx").setLevel(logging.WARNING)

mcp = FastMCP(
    "gambit",
    log_level="WARNING",
    instructions=(
        "GAMBIT is a strategy game: five AI-run nations (valdoria, ostrava, kessaria, "
        "nordhaven, zarnia) and one human player, usually the president of Valdoria. "
        "Use gambit_state first to see the world, gambit_leader to see what a leader "
        "really intends, and gambit_call to speak to a leader. During a crisis each "
        "gambit_turn is one tick of the crisis clock."
    ),
)


class GameError(Exception):
    """A failure already phrased for the player."""


async def _request(method: str, path: str, body: dict | None = None,
                   params: dict | None = None, timeout: float = 30) -> Any:
    try:
        async with httpx.AsyncClient(base_url=GAMBIT_URL, timeout=timeout) as client:
            r = await client.request(method, path, json=body, params=params)
    except httpx.ConnectError:
        raise GameError(
            f"The GAMBIT backend is not reachable at {GAMBIT_URL}. Start it from the repo "
            "root with `uvicorn engine.app:app --port 8000`, or set GAMBIT_URL.")
    except httpx.TimeoutException:
        raise GameError(f"The game did not answer {method} {path} within {timeout:.0f} s. "
                        "The leaders may still be thinking; try again or check the server log.")
    except httpx.HTTPError as e:
        raise GameError(f"Could not reach the game ({type(e).__name__}: {e}).")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        if isinstance(detail, list):  # FastAPI validation errors
            detail = "; ".join(str(d.get("msg", d)) for d in detail if isinstance(d, dict)) or str(detail)
        raise GameError(f"The game refused {method} {path} (HTTP {r.status_code}): {str(detail)[:300]}")
    try:
        return r.json()
    except ValueError:
        raise GameError(f"The game sent a non-JSON answer to {method} {path}.")


def _safe(fn):
    """Turn GameError (and anything unexpected) into a one-line message."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except GameError as e:
            return str(e)
        except Exception as e:  # never hand the model a traceback
            return f"Something went wrong talking to the game: {type(e).__name__}: {e}"
    return wrapper


# --- formatting -------------------------------------------------------------


def _rel_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def _action(a: dict) -> str:
    text = a.get("type", "?")
    if a.get("by"):
        text = f"{a['by']} {text}"
    if a.get("target"):
        text += f" -> {a['target']}"
    params = a.get("params") or {}
    if params:
        text += " " + ", ".join(f"{k}={v}" for k, v in params.items())
    return text


def _short(text: str, limit: int = 500) -> str:
    """One paragraph from a Markdown persona: headings and bullet marks dropped."""
    parts = [ln.strip().lstrip("-*").strip().replace("**", "") for ln in text.splitlines()]
    flat = " ".join(p for p in parts if p and not p.startswith("#"))
    return flat if len(flat) <= limit else flat[:limit].rsplit(" ", 1)[0] + "..."


def _promise(p: dict) -> str:
    text = f"{p.get('by', 'player')} to {p.get('to')}: {p.get('what')} ({p.get('when')})"
    if p.get("condition"):
        text += f" if {p['condition']}"
    if "kept" in p and p["kept"] is not None:
        text += " [kept]" if p["kept"] else " [broken]"
    return text


def _summary(s: dict, news: int = 3) -> str:
    seat = s.get("seat") or {}
    me = seat.get("nation")
    who = f"{seat.get('role', '?')} of {me}" if me else seat.get("role", "?")
    lines = [f"Turn {s.get('turn')} | phase: {s.get('phase')} | seed {s.get('seed')} | you are the {who}"]

    lines.append("")
    lines.append("Nations:")
    rel = s.get("relations") or {}
    for nid, n in (s.get("nations") or {}).items():
        st = n.get("stats") or {}
        stats = " ".join(f"{k} {round(st[k])}" for k in ("gdp", "army", "food", "oil", "stability", "approval") if k in st)
        head = f"- {nid} ({n.get('system')}, {n.get('leader')})"
        if me and nid != me:
            head += f" | relation with you {rel.get(_rel_key(me, nid), 0):+d}"
            b = n.get("beliefs") or {}
            if b:
                head += f" | trusts you {b.get('trust_in_player', 0):.2f}, thinks your resolve {b.get('resolve_of_player', 0):.2f}"
        if nid == me:
            head += " (you)"
        if n.get("status"):
            head += " | status " + ", ".join(n["status"])
        lines.append(head)
        lines.append(f"    {stats}")
        if n.get("public_statement"):
            lines.append(f"    says: \"{n['public_statement']}\"")
    if not me and rel:  # mediator: show the tensest pairs
        worst = sorted(rel.items(), key=lambda kv: kv[1])[:4]
        lines.append("Tensest relations: " + ", ".join(f"{k} {v:+d}" for k, v in worst))
    wars = [f"{l['a']}-{l['b']}" for l in s.get("links") or [] if l.get("type") == "war"]
    if wars:
        lines.append("AT WAR: " + ", ".join(wars))

    c = s.get("crisis")
    if c:
        tick, total = c.get("tick", 0), c.get("ticks_total", 0)
        lines.append("")
        lines.append(f"CRISIS {c.get('id')}: tick {tick} of {total}")
        deadlines = sorted((c.get("deadlines") or {}).items(), key=lambda kv: kv[1])
        decided = c.get("decisions") or {}
        parts = []
        for nid, d in deadlines:
            if nid in decided:
                parts.append(f"{nid} DECIDED {decided[nid].get('action')} at tick {decided[nid].get('tick')}")
            else:
                parts.append(f"{nid} decides by tick {d} ({d - tick} to go)")
        lines.append("Deadlines: " + "; ".join(parts))
        if c.get("promises"):
            lines.append("Promises: " + "; ".join(_promise(p) for p in c["promises"]))
        if c.get("public_commitments"):
            lines.append("Public commitments: " + "; ".join(
                f"{p.get('nation')} committed to {p.get('action')} at tick {p.get('tick')}"
                for p in c["public_commitments"]))

    ring = s.get("incoming_call")
    if ring:
        lines.append(f"INCOMING CALL from {ring.get('from')} ({ring.get('emotion')}): \"{ring.get('opening_line')}\"")

    lc = s.get("last_call")
    if lc:
        if lc.get("pending"):
            lines.append(f"Last call to {lc.get('to')}: still being interpreted")
        else:
            got = [_promise(p) for p in lc.get("promises") or []] + [_action(a) for a in lc.get("actions") or []]
            lines.append(f"Last call to {lc.get('to')}: " + ("; ".join(got) if got else "nothing agreed"))

    f = s.get("last_futures")
    if f:
        lines.append(f"War odds (six months): {f['before']['war_p']:.0%} -> {f['after']['war_p']:.0%}. {f.get('caption', '')}")

    if s.get("news"):
        lines.append("")
        lines.append("Latest news: " + " | ".join(f"t{n.get('turn')} {n.get('text')}" for n in s["news"][-news:]))

    crises = s.get("available_crises")
    if s.get("phase") == "strategy":
        ids = ", ".join(c["id"] for c in crises) if crises else "one_berth"
        lines.append(f"Crises you can start: {ids}")

    e = s.get("ending")
    if e:
        sc = e.get("score") or {}
        lines.append("")
        lines.append(f"GAME OVER ({e.get('reason')}): " + ", ".join(f"{k} {v}" for k, v in sc.items() if v is not None))
        if e.get("verdict"):
            lines.append(f"Historian: {e['verdict']}")
    return "\n".join(lines)


# --- tools ------------------------------------------------------------------


@mcp.tool()
@_safe
async def gambit_state() -> str:
    """Summarise the current GAMBIT world: turn, phase, each nation's system, key stats,
    public statement and relation with the player, plus (during a crisis) the crisis
    clock, each leader's deadline, promises and public commitments, the last phone
    call's result, the war-odds forecast and recent news. Call this first, and again
    after any turn or call, to see what changed."""
    return _summary(await _request("GET", "/state"))


@mcp.tool()
@_safe
async def gambit_leader(nation: str) -> str:
    """Look behind one leader's mask. Returns their public statement against their
    private intent, what their advisers recommended (ranked, with scores), what the
    leader actually chose and why. Use it to tell who is bluffing or lying.
    nation: one of valdoria, ostrava, kessaria, nordhaven, zarnia."""
    nation = nation.strip().lower()
    if nation not in NATIONS:
        return f"Unknown nation {nation!r}. Pick one of: {', '.join(NATIONS)}."
    d = await _request("GET", f"/leaders/{nation}")
    lines = [
        f"{nation}",
        f"Persona: {_short(d.get('persona') or '')}",
        f"Says in public: \"{d.get('public_statement')}\"",
        f"Really intends: \"{d.get('private_intent')}\"",
    ]
    if d.get("private_strategy"):
        lines.append(f"Private strategy: {d['private_strategy']}")
    adv = d.get("advice") or []
    if adv:
        lines.append("Advisers recommended:")
        lines += [f"  {i}. {_action(a['action'])} (score {a.get('score', 0):.2f})" for i, a in enumerate(adv[:5], 1)]
    chosen = d.get("chosen") or []
    lines.append("Leader chose: " + ("; ".join(_action(a) for a in chosen) if chosen else "nothing yet"))
    lines.append(f"Reason: {d.get('reason')}")
    return "\n".join(lines)


@mcp.tool()
@_safe
async def gambit_start(seed: int = 7, role: str = "president", nation: str = "valdoria") -> str:
    """Start a new game, wiping the current one. seed 7 is the demo world. role is
    "president" (you run a nation, valdoria by default) or "mediator" (no nation; the
    backend must allow it). Returns the opening state summary."""
    seat = {"role": role, "nation": None if role == "mediator" else nation}
    s = await _request("POST", "/start", {"seed": seed, "seat": seat})
    return "New game started.\n\n" + _summary(s)


@mcp.tool()
@_safe
async def gambit_turn() -> str:
    """Advance the world by one turn: every AI leader decides and acts at once. During a
    crisis one turn is one tick of the crisis clock, and leaders at their deadline
    commit. Can take several seconds with live models. Returns the new state summary."""
    s = await _request("POST", "/turn", timeout=90)
    return _summary(s, news=5)


@mcp.tool()
@_safe
async def gambit_start_crisis(crisis_id: str = "one_berth") -> str:
    """Start a crisis (only from the strategy phase). "one_berth" is the main one: a
    storm leaves Port Kessar with a single berth for 12 ticks and three nations want
    it. Other ids work only if the backend lists them under "Crises you can start".
    Returns the state summary with the crisis clock and deadlines."""
    s = await _request("POST", "/crisis/start", {"id": crisis_id})
    return f"Crisis {crisis_id} started.\n\n" + _summary(s)


@mcp.tool()
@_safe
async def gambit_call(to: str, text: str, interrupted: bool = False) -> str:
    """Phone a leader and say one line to them, as the player. Returns the leader's spoken
    reply and emotion, then waits (up to about 25 s) while the game works out what was
    agreed, and returns the promises and actions it recorded. Promises bind you: a broken
    promise costs trust. to: valdoria, ostrava, kessaria, nordhaven or zarnia.
    interrupted: true if you are cutting the leader off mid-sentence (for example, to
    stop them announcing a threat on an incoming call)."""
    to = to.strip().lower()
    if to not in NATIONS:
        return f"Unknown nation {to!r}. Pick one of: {', '.join(NATIONS)}."
    if not text.strip():
        return "Say something: text is empty."
    r = await _request("POST", "/call", {"to": to, "text": text, "interrupted": interrupted,
                                         "hesitation_ms": 0}, timeout=45)
    lines = [f"You said: \"{r.get('transcript', text)}\"",
             f"{to} ({r.get('emotion', 'calm')}): \"{r.get('reply_text')}\""]
    promises, actions = r.get("promises") or [], r.get("actions") or []
    if r.get("pending"):
        call_id, waited = r.get("call_id"), False
        deadline = time.monotonic() + CALL_WAIT_S
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            lc = (await _request("GET", "/state")).get("last_call") or {}
            if lc.get("call_id") == call_id and not lc.get("pending"):
                promises, actions, waited = lc.get("promises") or [], lc.get("actions") or [], True
                if lc.get("ends_call"):
                    lines.append(f"{to} hung up.")
                break
        if not waited:
            lines.append(f"The game is still working out what was agreed (after {CALL_WAIT_S:.0f} s); "
                         "check gambit_state in a moment.")
            return "\n".join(lines)
    lines.append("Recorded promises: " + ("; ".join(_promise({"by": "player", **p}) for p in promises) or "none"))
    lines.append("Recorded actions: " + ("; ".join(_action(a) for a in actions) or "none"))
    return "\n".join(lines)


@mcp.tool()
@_safe
async def gambit_replay(shift_ticks: int) -> str:
    """The "what if I had waited" replay of the last finished crisis: replays it with
    every one of your calls moved by shift_ticks (positive = later, negative = earlier)
    and names each leader who would have decided differently, and why. Needs a crisis
    that has already run to the end of its clock."""
    r = await _request("POST", "/replay", {"shift_ticks": shift_ticks}, timeout=45)
    changed = r.get("changed") or []
    when = f"{abs(shift_ticks)} tick{'s' if abs(shift_ticks) != 1 else ''} {'later' if shift_ticks >= 0 else 'earlier'}"
    if not changed:
        return f"Making your calls {when}: no leader would have decided differently."
    lines = [f"Making your calls {when}, {len(changed)} leader(s) would have flipped:"]
    lines += [f"- {c['nation']}: {c['was']} -> {c['now']}. {c.get('why', '')}" for c in changed]
    return "\n".join(lines)


@mcp.tool()
@_safe
async def gambit_end() -> str:
    """End the session now and show the final score (months in power, peace, GDP and
    stability change, promises kept and broken) and the historian's verdict if written."""
    s = await _request("POST", "/end")
    return _summary(s)


def main() -> None:
    mcp.run()  # stdio


if __name__ == "__main__":
    main()
