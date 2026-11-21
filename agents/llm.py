"""Thin async client for Mistral chat completions with JSON output.

Uses httpx directly so the SDK version does not matter. Every call either returns a
validated object or raises quickly, so the engine can fall back to advise()[0].

Model choice (measured 21 Nov, see agents/A0_RESULTS.md): mistral-large-4 cannot turn
reasoning off (low is the minimum) and spends 1,800-2,500 thinking tokens on a leader
prompt, 26-72 s per decision, often hitting max_tokens before any text. mistral-large-2512
has no thinking and answers in 2-4 s. So the default is large-2512; set
GAMBIT_LEADER_MODEL=mistral-large-4 to switch back without code changes.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import time
from typing import Any, Callable, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

API_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = os.environ.get("GAMBIT_LEADER_MODEL", "mistral-large-2512")
CALL_MODEL = os.environ.get("GAMBIT_CALL_MODEL", MODEL)

T = TypeVar("T", bound=BaseModel)

_client: Optional[httpx.AsyncClient] = None
STATS: dict[str, Any] = {"calls": 0, "retries": 0, "failures": 0, "latencies": []}


class LLMError(RuntimeError):
    pass


class EmptyReply(LLMError):
    """HTTP 200 but no text chunk (a reasoning model spent its budget thinking)."""


class RateLimited(LLMError):
    """HTTP 429. The limit is shared by the whole workspace, so back off and retry."""


def _key() -> str:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise LLMError("MISTRAL_API_KEY is not set")
    return key


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(limits=httpx.Limits(max_connections=16))
    return _client


def reasons(model: str) -> bool:
    """Models that think before answering and take reasoning_effort."""
    return "large-4" in model or model in ("mistral-large-latest",)


def _text(content: Any) -> str:
    """A string, or a list of thinking/text chunks when the model reasons."""
    if isinstance(content, str):
        return content
    return "".join(c.get("text", "") for c in content or []
                   if isinstance(c, dict) and c.get("type") == "text")


def loads(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0]
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")
    return json.loads(raw[start: end + 1])


async def chat(messages: list[dict], *, model: Optional[str] = None, effort: str = "low",
               max_tokens: int = 600, temperature: float = 0.8, json_mode: bool = True,
               timeout: float = 20.0, seed: Optional[int] = None) -> str:
    model = model or MODEL
    body: dict[str, Any] = {"model": model, "messages": messages,
                            "max_tokens": max_tokens if not reasons(model) else max(max_tokens, 4000),
                            "temperature": temperature}
    if reasons(model):
        body["reasoning_effort"] = effort
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if seed is not None:
        body["random_seed"] = seed
    t0 = time.perf_counter()
    STATS["calls"] += 1
    try:
        r = await client().post(API_URL, json=body, timeout=timeout,
                                headers={"Authorization": f"Bearer {_key()}"})
    except httpx.TimeoutException as e:
        STATS["failures"] += 1
        raise LLMError(f"timeout after {timeout:.1f}s") from e
    except httpx.HTTPError as e:
        STATS["failures"] += 1
        raise LLMError(f"{type(e).__name__}: {e}") from e
    STATS["latencies"].append(time.perf_counter() - t0)
    if r.status_code == 429:
        STATS["rate_limited"] = STATS.get("rate_limited", 0) + 1
        raise RateLimited(f"HTTP 429: {r.text[:200]}")
    if r.status_code != 200:
        STATS["failures"] += 1
        raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
    choice = r.json()["choices"][0]
    text = _text(choice["message"].get("content"))
    if not text.strip():
        raise EmptyReply(f"no text (finish_reason={choice.get('finish_reason')})")
    return text


async def chat_json(messages: list[dict], parse: Callable[[Any], T], *, deadline: float,
                    **kw: Any) -> T:
    """Ask for JSON and parse it with `parse`. One retry on bad JSON, an empty reply or a
    validation error; backs off and retries on 429. All before `deadline` (perf_counter)."""
    last: Exception | None = None
    bad, waits = 0, 0
    while bad < 2:
        left = deadline - time.perf_counter()
        if left < 1.0:
            break
        try:
            raw = await chat(messages, timeout=left, **kw)
        except RateLimited as e:
            last, waits = e, waits + 1
            pause = min(0.3 * 2 ** waits + random.uniform(0, 0.3), deadline - time.perf_counter() - 1.5)
            if pause <= 0:
                break
            await asyncio.sleep(pause)
            continue
        except EmptyReply as e:
            last, bad = e, bad + 1
            STATS["retries"] += 1
            continue
        try:
            return parse(loads(raw))
        except (ValueError, ValidationError, KeyError, TypeError) as e:
            last, bad = e, bad + 1
            STATS["retries"] += 1
            messages = messages + [
                {"role": "assistant", "content": raw[:2000]},
                {"role": "user", "content": f"That was not valid: {str(e)[:300]}. "
                                            "Reply again with only the corrected JSON object."},
            ]
    STATS["failures"] += 1
    raise LLMError(f"no valid reply in time: {last}")


async def chat_model(model_cls: Type[T], messages: list[dict], *, timeout: float = 20.0,
                     **kw: Any) -> T:
    return await chat_json(messages, model_cls.model_validate,
                           deadline=time.perf_counter() + timeout, **kw)
