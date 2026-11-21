"""Drive the GAMBIT MCP server as a real MCP client over stdio. No API key needed.

    python -m pytest -q gambit_mcp

Starts the backend on a free port with GAMBIT_AGENTS=stub (as scripts/smoke.sh does),
spawns `python -m gambit_mcp.server` with the SDK's stdio client, and calls every tool.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

mcp = pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

TOOLS = {"gambit_state", "gambit_leader", "gambit_start", "gambit_turn", "gambit_start_crisis",
         "gambit_call", "gambit_replay", "gambit_end"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def backend():
    port = _free_port()
    env = {**os.environ, "GAMBIT_AGENTS": "stub"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "engine.app:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(url + "/state", timeout=1).read()
                break
            except Exception:
                if proc.poll() is not None:
                    pytest.fail("backend exited during startup")
                time.sleep(0.2)
        else:
            pytest.fail("backend did not start")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _text(result) -> str:
    assert not result.isError, result
    return "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")


async def _play(url: str) -> dict[str, str]:
    params = StdioServerParameters(command=sys.executable, args=["-m", "gambit_mcp.server"],
                                   env={**os.environ, "GAMBIT_URL": url}, cwd=str(ROOT))
    out: dict[str, str] = {}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name: t for t in (await session.list_tools()).tools}
            assert TOOLS <= set(tools), set(tools)
            assert all(tools[name].description for name in TOOLS)

            async def call(name, **args):
                text = _text(await session.call_tool(name, args))
                out.setdefault(name, text)
                return text

            await call("gambit_start", seed=7)
            await call("gambit_state")
            await call("gambit_turn")
            await call("gambit_start_crisis", crisis_id="one_berth")
            await call("gambit_call", to="ostrava",
                       text="You can have the berth in the morning, not all day.")
            await call("gambit_leader", nation="ostrava")
            out["bad_leader"] = await call("gambit_leader", nation="atlantis")
            for _ in range(15):
                text = await call("gambit_turn")
                if "CRISIS one_berth" not in text:
                    break
            out["after_crisis"] = text
            await call("gambit_replay", shift_ticks=3)
            await call("gambit_end")
    return out


def test_every_tool_over_stdio(backend):
    out = asyncio.run(asyncio.wait_for(_play(backend), timeout=120))

    assert "New game started" in out["gambit_start"] and "Turn 0" in out["gambit_start"]
    s = out["gambit_state"]
    assert "you are the president of valdoria" in s
    for nation in ("ostrava", "kessaria", "nordhaven", "zarnia"):
        assert f"- {nation} (" in s
    assert "relation with you" in s and "{" not in s  # a summary, not raw JSON
    assert "Turn 1" in out["gambit_turn"]
    assert "CRISIS one_berth: tick 0 of 12" in out["gambit_start_crisis"]
    assert "Deadlines:" in out["gambit_start_crisis"]
    c = out["gambit_call"]
    assert "ostrava (" in c and "Recorded promises:" in c, c
    l = out["gambit_leader"]
    assert "Really intends:" in l and "Leader chose:" in l and "Reason:" in l
    assert "Unknown nation" in out["bad_leader"]
    assert "CRISIS one_berth" not in out["after_crisis"], "crisis never resolved"
    assert out["gambit_replay"].startswith("Making your calls 3 ticks later"), out["gambit_replay"]
    assert "GAME OVER (ended)" in out["gambit_end"]


def test_backend_down_is_one_plain_line(monkeypatch):
    from gambit_mcp import server

    monkeypatch.setattr(server, "GAMBIT_URL", f"http://127.0.0.1:{_free_port()}")
    text = asyncio.run(server.gambit_state())
    assert "not reachable" in text and "Traceback" not in text


def test_overlapping_calls_each_report_their_own_result(monkeypatch):
    from gambit_mcp import server

    async def request(method, path, body=None, **kwargs):
        if path == "/call":
            return {"call_id": body["to"], "pending": True, "reply_text": "Agreed."}
        assert method == "GET" and path.startswith("/calls/")
        nation = path.split("/")[-1]
        return {"call_id": nation, "promises": [{"to": nation, "what": nation + " goods"}]}

    async def calls():
        return await asyncio.gather(server.gambit_call("kessaria", "Trade?"),
                                    server.gambit_call("zarnia", "Trade?"))
    monkeypatch.setattr(server, "_request", request)
    first, second = asyncio.run(calls())
    assert "kessaria goods" in first and "zarnia goods" not in first
    assert "zarnia goods" in second and "kessaria goods" not in second
