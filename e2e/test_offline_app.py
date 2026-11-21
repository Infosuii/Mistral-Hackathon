"""Offline tests for e2e/offline_app.py (zero network, zero Mistral API calls).

Verifies Coordinator's #67 REQUEST:
- Uncached offline replies (strategy trade deals to all four leaders, Nordhaven tug request)
  return substantive written replies with `reply_audio_url=None` — never an unrelated clip
  such as 'The line is breaking up'.
- Pre-rendered lines (Wiretap scripts and crisis incoming calls) still return their exact
  matching `/audio/<hash>.mp3` URLs and serve real audio bytes.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from contracts.models import CallResponse, State, WiretapResponse
from voice.audio import cache_key

ROOT = Path(__file__).resolve().parent.parent
CASTING = json.loads((ROOT / "voice" / "casting.json").read_text(encoding="utf-8"))
FALLBACK_LINE = ("The line is breaking up. Say that again.", "tense")
FALLBACK_URLS = {
    f"/audio/{cache_key(FALLBACK_LINE[0], c['voice_id'], FALLBACK_LINE[1], 'mp3')}.mp3"
    for n, c in CASTING.items()
    if not n.startswith("_")
}


def _settle(client: TestClient, call_id: str | None) -> State:
    for _ in range(40):
        st = State.model_validate(client.get("/state").json())
        if not call_id or (st.last_call and st.last_call.call_id == call_id and not st.last_call.pending):
            return st
        time.sleep(0.05)
    raise AssertionError(f"call {call_id} stayed pending")


def test_offline_app_audio_matches_reply_and_never_plays_unrelated_fallback():
    import e2e.offline_app as offline_mod

    with TestClient(offline_mod.app) as client:
        st = State.model_validate(
            client.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}).json()
        )
        assert st.phase == "strategy"

        # 1. Typed trade offer to every opposing leader: substantive reply, never fallback/unrelated audio.
        for nation in ("kessaria", "ostrava", "zarnia", "nordhaven"):
            r = client.post(
                "/call",
                json={
                    "to": nation,
                    "audio": None,
                    "text": f"Let us sign a trade deal between Valdoria and {nation.title()} today.",
                    "interrupted": False,
                    "hesitation_ms": 600,
                },
            )
            assert r.status_code == 200, r.text
            resp = CallResponse.model_validate(r.json())
            assert "trade" in resp.reply_text.lower()
            assert resp.reply_audio_url not in FALLBACK_URLS
            assert resp.reply_audio_url is None, f"unexpected audio URL for uncached reply: {resp.reply_audio_url}"
            _settle(client, resp.call_id)

        # 2. One Berth crisis: scripted tick-1 ring plays its exact pre-rendered audio.
        client.post("/crisis/start", json={"id": "one_berth"})
        st1 = State.model_validate(client.post("/turn").json())
        assert st1.incoming_call is not None and st1.incoming_call.from_ == "ostrava"
        expected_ring = (
            f"/audio/{cache_key(st1.incoming_call.opening_line, CASTING['ostrava']['voice_id'], st1.incoming_call.emotion, 'mp3')}.mp3"
        )
        assert st1.incoming_call.audio_url == expected_ring
        ring_audio = client.get(expected_ring)
        assert ring_audio.status_code == 200 and len(ring_audio.content) > 1024

        # 3. Nordhaven tug request: records send_tugs, text-only reply (never unrelated fallback audio).
        r_tugs = client.post(
            "/call",
            json={
                "to": "nordhaven",
                "audio": None,
                "text": "I need your tugs at Port Kessar today to open a second berth. Valdoria pays the full cost.",
                "interrupted": False,
                "hesitation_ms": 500,
            },
        )
        assert r_tugs.status_code == 200, r_tugs.text
        resp_tugs = CallResponse.model_validate(r_tugs.json())
        assert "tug" in resp_tugs.reply_text.lower()
        assert resp_tugs.reply_audio_url not in FALLBACK_URLS
        assert resp_tugs.reply_audio_url is None
        st_after = _settle(client, resp_tugs.call_id)
        assert any(p.to == "nordhaven" and p.what == "send_tugs" for p in st_after.crisis.promises)

        # 4. Wiretap (pre-rendered demo script): serves exact matching audio clips.
        wt = WiretapResponse.model_validate(client.get("/wiretap?a=ostrava&b=kessaria").json())
        assert len(wt.lines) >= 2
        for line in wt.lines:
            assert line.audio_url is not None
            assert line.audio_url not in FALLBACK_URLS
            audio_resp = client.get(line.audio_url)
            assert audio_resp.status_code == 200 and len(audio_resp.content) > 1024


def test_offline_app_supports_all_extra_crises_without_berth_wording(monkeypatch):
    import engine.game as eng_game
    import e2e.offline_app as offline_mod

    monkeypatch.setattr(eng_game, "EXTRA_CRISES", True)

    cases = [
        ("outbreak", "zarnia", "Zarnia gets the first doses from Nordhaven.", "first_doses"),
        ("coup", "ostrava", "Valdoria stands with Ostrava with full backing today.", "valdoria_backing"),
        ("pipeline_cut", "nordhaven", "Nordhaven should pay the fair price to reopen supply.", "pay_price"),
        ("pipeline_cut", "ostrava", "Ostrava will be named sole supplier.", "sole_supplier"),
    ]
    with TestClient(offline_mod.app) as client:
        for cid, nation, line, expected_what in cases:
            client.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}})
            r_start = client.post("/crisis/start", json={"id": cid})
            assert r_start.status_code == 200, r_start.text
            st1 = State.model_validate(client.post("/turn").json())
            assert st1.incoming_call is not None and st1.incoming_call.audio_url is not None
            aud = client.get(st1.incoming_call.audio_url)
            assert aud.status_code == 200 and len(aud.content) > 1024

            r_call = client.post(
                "/call",
                json={"to": nation, "audio": None, "text": line, "interrupted": False, "hesitation_ms": 400},
            )
            assert r_call.status_code == 200, r_call.text
            resp = CallResponse.model_validate(r_call.json())
            low = resp.reply_text.lower()
            assert not any(w in low for w in ("berth", "ship", "tug")), f"One Berth wording leaked on {cid}: {resp.reply_text}"
            st_after = _settle(client, resp.call_id)
            assert any(p.to == nation and p.what == expected_what for p in st_after.crisis.promises)
