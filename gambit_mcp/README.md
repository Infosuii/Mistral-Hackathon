# gambit_mcp: Mistral Vibe plays GAMBIT

An MCP server that lets Mistral Vibe read and play the running game, plus two Vibe skills
in `.vibe/skills/`. Vibe can see the world, look behind a leader's public line, phone a
leader, tick the crisis clock and run the "what if I'd waited" replay.

Tools (Vibe prefixes the server name, so `gambit_state` shows as `gambit_gambit_state`): `gambit_state`, `gambit_leader`, `gambit_start`,
`gambit_turn`, `gambit_start_crisis`, `gambit_call`, `gambit_replay`, `gambit_end`.
Skills (slash commands): `/gambit-brief` (who is lying, next deadline, what to say) and
`/gambit-crisis-card <one sentence>` (writes a new `data/crises/<id>.json`).

## Set up (from the repo root)

```bash
pip install -r requirements.txt -r gambit_mcp/requirements.txt
uvicorn engine.app:app --port 8000          # the game; GAMBIT_AGENTS=stub for no model calls
uv tool install mistral-vibe                # Vibe itself (Python 3.12+)
vibe --setup                                # sign in, or paste a MISTRAL_API_KEY
```

Register the server with Vibe, from the repo root, with the Python that has `mcp`
installed active. This writes `~/.vibe/config.toml`. Note `--arg=-m`: Vibe rejects
`--arg -m` because `-m` looks like a flag.

```bash
vibe mcp add gambit --transport stdio --command "$(which python)" --arg=-m --arg gambit_mcp.server --env PYTHONPATH="$(pwd)" --tool-timeout-sec 120
```

Or add the same thing to `~/.vibe/config.toml` by hand. `tool_timeout_sec` is raised
because a phone call waits up to 25 s for the promises. Set `GAMBIT_URL` in `env` if the
game is not on `http://127.0.0.1:8000`.

```toml
[[mcp_servers]]
name = "gambit"
transport = "stdio"
command = "/absolute/path/to/python"
args = ["-m", "gambit_mcp.server"]
env = { "PYTHONPATH" = "/absolute/path/to/Mistral-Hackathon" }
tool_timeout_sec = 120
```

Then start `vibe` in the repo root and trust the folder when asked (project skills in
`.vibe/skills/` only load in a trusted folder). `/mcp gambit` lists the tools.

## Three things to type in Vibe

1. `Start a GAMBIT game on seed 7, start the One Berth crisis and tell me who decides first.`
2. `/gambit-brief`
3. `Call Ostrava and offer them the berth in the morning only. What did they promise?`

Bonus: `/gambit-crisis-card a cyberattack takes down Nordhaven's chip fabs`, then restart
the backend with `GAMBIT_EXTRA_CRISES=1` and start it.

## 20-second script for the presenter

"This is Mistral Vibe, Mistral's own coding agent, connected to our game through an MCP
server. I ask it to brief me. It reads the world, opens each leader's private intent, and
tells me Ostrava is bluffing and Nordhaven decides at tick six. It even gives me the line to
say. Then it places the call itself, and the promise lands in the game. With one sentence
it can also write a brand-new crisis that the engine loads without a code change."

## Test (no API key)

```bash
python -m pytest -q gambit_mcp
```

Starts the backend with `GAMBIT_AGENTS=stub` on a free port and drives every tool through a
real MCP stdio client.
