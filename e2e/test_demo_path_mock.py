"""Fast offline pytest check for the e2e.demo_path harness (no Mistral API calls)."""
from __future__ import annotations

import os
import threading
from unittest.mock import patch

import uvicorn

from contracts.models import CallOutput
import engine.app as eng_app
import voice.api as v_api
from e2e.demo_path import Client, _free_port, run_demo_path


def test_demo_path_harness_offline():
    async def fake_fast(view):
        return {"reply_text": f"Understood, President ({view.nation}).", "emotion": "tense"}

    async def fake_interp(view, reply_text):
        t = view.transcript.lower()
        promises, actions = [], []
        trust, resolve = 0.05, 0.05
        if view.state.phase == "strategy":
            actions = [{
                "type": "propose_trade",
                "by": view.nation,
                "target": "valdoria",
                "params": {"give": {"food": 10}, "get": {"chips": 10}},
            }]
        elif "tugs" in t:
            promises = [{"to": view.nation, "what": "send_tugs", "when": "now", "condition": None}]
        elif "whole day" in t or "entire day" in t:
            promises = [{"to": view.nation, "what": "berth", "when": "all_day", "condition": None}]
        elif "morning" in t:
            promises = [{"to": view.nation, "what": "berth", "when": "morning", "condition": None}]
            actions = [{"type": "wait", "by": view.nation}]
            resolve = 0.1
        return CallOutput(
            reply_text=reply_text,
            emotion="tense",
            promises=promises,
            actions=actions,
            belief_updates={"trust_in_player": trust, "resolve_of_player": resolve},
        )

    async def fake_speak(text, voice_id, emotion=None, fmt="mp3"):
        fn = sorted(os.listdir("voice/prerendered"))[0]
        return f"/audio/{fn}"

    port = _free_port()
    orig_decide = eng_app.GAME._decide_fn
    eng_app.GAME._decide_fn = None
    try:
        with patch.object(v_api, "_phone", return_value=(fake_fast, fake_interp, True)), \
             patch.object(v_api, "speak", side_effect=fake_speak):
            cfg = uvicorn.Config(eng_app.app, host="127.0.0.1", port=port, log_level="error")
            srv = uvicorn.Server(cfg)
            th = threading.Thread(target=srv.run, daemon=True)
            th.start()
            try:
                c = Client(f"http://127.0.0.1:{port}")
                c.wait_ready(10.0)
                beats = run_demo_path(c, mode="typed", seed=7, shift_ticks=3, check_replay_flip=False)
                assert all(b.passed for b in beats), [b for b in beats if not b.passed]
            finally:
                srv.should_exit = True
                th.join(timeout=5)
    finally:
        eng_app.GAME._decide_fn = orig_decide
