"""One raw decide() prompt per model, printed with finish_reason and token usage.
  python -m agents.probe [model ...]      (default: mistral-large-4 and mistral-large-2512)"""
import asyncio
import json
import os
import sys
import time

import httpx

from . import fixtures
from .leaders import DECIDE_RULES, _brief, _dump, _j, _label, _who
from .llm import reasons
from .personas import card


async def one(c: httpx.AsyncClient, model: str) -> None:
    v = fixtures.leader_view("ostrava")
    st = _dump(v.state)
    user = {"situation": _brief(st, "ostrava"),
            "options_ranked_by_your_advisers": [f"{i}. {_label(a.action.model_dump())} ({a.score:+.1f})"
                                                for i, a in enumerate(v.advice[:10])]}
    body = {"model": model, "max_tokens": 2500, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": card("ostrava") + "\n\n" + DECIDE_RULES.format(who=_who(st, "ostrava"))},
                         {"role": "user", "content": _j(user)}]}
    if reasons(model):
        body["reasoning_effort"] = "low"
    t = time.perf_counter()
    r = await c.post("https://api.mistral.ai/v1/chat/completions", json=body, timeout=120,
                     headers={"Authorization": f"Bearer {os.environ['MISTRAL_API_KEY']}"})
    dt = time.perf_counter() - t
    if r.status_code != 200:
        print(f"{model}: HTTP {r.status_code} {r.text[:300]}")
        return
    j = r.json()
    ch = j["choices"][0]
    content = ch["message"].get("content")
    kinds = [x.get("type") for x in content] if isinstance(content, list) else ["str"]
    text = content if isinstance(content, str) else "".join(x.get("text", "") for x in content if x.get("type") == "text")
    u = j.get("usage", {})
    print(f"{model}: {dt:.1f}s finish={ch.get('finish_reason')} chunks={kinds} completion={u.get('completion_tokens')} "
          f"reasoning={(u.get('completion_tokens_details') or {}).get('reasoning_tokens')}\n  {text[:300]!r}")


async def main() -> None:
    models = sys.argv[1:] or ["mistral-large-4", "mistral-large-2512"]
    async with httpx.AsyncClient() as c:
        await asyncio.gather(*[one(c, m) for m in models])


if __name__ == "__main__":
    asyncio.run(main())
