"""Importing e2e.offline_app swaps voice.api._phone and sets environment variables for the
whole process (that is its job as a server). In a test run that leaked into every later
test: voice/tests/test_call.py got the offline replies and 6 tests failed. Put it back."""
import os

import pytest

import voice.api as v_api

ENV = ("GAMBIT_AGENTS", "VOICE_WIRETAP", "VOICE_MOCK", "MISTRAL_API_KEY")


@pytest.fixture(autouse=True, scope="module")
def _restore_voice_after_offline_app():
    phone, env = v_api._phone, {k: os.environ.get(k) for k in ENV}
    yield
    v_api._phone = phone
    for k, val in env.items():
        if val is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = val
