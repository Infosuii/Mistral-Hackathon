"""The live session: one game in memory, and the turn loop that calls the leaders.

The engine core (engine/core.py) stays pure. This module holds what changes between
requests: the current state, what each leader last decided, messages in flight and
actions agreed on the phone.

    from engine.game import GAME
    GAME.state                      # current State
    await GAME.turn()               # advance one month
    GAME.apply_call("ostrava", call_output, interrupted=True, hesitation_ms=900)
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Awaitable, Callable, Optional

from contracts.models import (
    NATION_IDS, Action, Advice, CallOutput, CrisisPromise, LeaderDetail, LeaderOutput,
    LeaderView, ReceivedMessage, Seat, State,
)
from engine.core import advise, is_legal, new_game, relation_key, step, weights
from engine.crisis import crisis_file, start_crisis

log = logging.getLogger("gambit.engine")
ROOT = Path(__file__).resolve().parent.parent
DECIDE_TIMEOUT_S = float(os.environ.get("GAMBIT_DECIDE_TIMEOUT", "8"))

Decide = Callable[[LeaderView], Awaitable[LeaderOutput]]


def _load_decide() -> Optional[Decide]:
    """agents.decide if Abi's module is importable, unless GAMBIT_AGENTS=stub."""
    if os.environ.get("GAMBIT_AGENTS", "").lower() == "stub":
        return None
    try:
        from agents import decide  # type: ignore
        return decide
    except Exception as e:  # not written yet, or broken: the world must still run
        log.warning("agents.decide unavailable (%s); leaders follow their advisers", e)
        return None


def advisers_choice(state: State, nation: str, advice: list[Advice], why: str) -> LeaderOutput:
    top = advice[0].action
    return LeaderOutput(
        public_statement=state.nations[nation].public_statement,
        private_intent="Follow the advisers.",
        actions=[] if top.type == "wait" else [top],
        followed_advice=True,
        reason=why,
    )


def _persona(nation: str) -> str:
    path = ROOT / "agents" / "personas" / f"{nation}.md"
    return path.read_text() if path.exists() else ""


class Game:
    def __init__(self, seed: int = 7, seat: Optional[Seat] = None,
                 decide: Optional[Decide] = None, use_agents: bool = True):
        self._decide_fn = decide if decide is not None else (_load_decide() if use_agents else None)
        self.lock = asyncio.Lock()
        self.reset(seed, seat)

    def reset(self, seed: int, seat: Optional[Seat] = None) -> State:
        self.state = new_game(seed, seat or Seat(role="president", nation="valdoria"))
        self.leaders: dict[str, LeaderDetail] = {}
        self.inbox: dict[str, list[ReceivedMessage]] = {n: [] for n in NATION_IDS}
        self.queued: list[Action] = []  # agreed on the phone; applied next turn
        self.promises: list[CrisisPromise] = []  # strategy-phase promises (crisis ones live in state)
        self.pending_announce: Optional[Action] = None  # becomes public next tick unless interrupted
        self.crisis_log: list[State] = []  # every crisis tick, for replay and the needle
        return self.state

    def start_crisis(self, crisis_id: str) -> State:
        self.state = start_crisis(self.state, crisis_id)
        self.pending_announce, self.crisis_log = None, [self.state]
        return self.state

    def ai_nations(self) -> list[str]:
        return [n for n in NATION_IDS if n != self.state.seat.nation]

    async def _one_leader(self, nation: str, advice: list[Advice]) -> tuple[LeaderOutput, list[Action]]:
        s = self.state
        out: Optional[LeaderOutput] = None
        if self._decide_fn is not None:
            view = LeaderView(nation=nation, state=s, advice=advice,
                              messages_received=self.inbox[nation])
            try:
                raw = await asyncio.wait_for(self._decide_fn(view), timeout=DECIDE_TIMEOUT_S)
                out = raw if isinstance(raw, LeaderOutput) else LeaderOutput.model_validate(raw)
            except Exception as e:
                log.warning("decide(%s) failed: %s: %s", nation, type(e).__name__, e)
                out = advisers_choice(s, nation, advice, f"Fell back to advisers ({type(e).__name__}).")
        if out is None:
            out = advisers_choice(s, nation, advice, "Followed the advisers.")
        legal = [a for a in out.actions if a.by == nation and is_legal(s, a)]
        if out.actions and not legal:
            log.warning("decide(%s) chose no legal action; using the advisers' top", nation)
            top = advice[0].action
            legal = [] if top.type == "wait" else [top]
        return out, legal[:1]

    async def turn(self) -> State:
        async with self.lock:
            if self.state.phase == "crisis":
                return await self._crisis_tick()
            s = self.state
            ai = self.ai_nations()
            advice = {n: advise(s, n) for n in ai}
            results = await asyncio.gather(*(self._one_leader(n, advice[n]) for n in ai))

            queued_by = {a.by for a in self.queued}
            actions = list(self.queued)
            for n, (out, chosen) in zip(ai, results):
                if n not in queued_by:  # a deal struck on the phone beats the leader's own plan
                    actions += chosen
            new = step(s, actions, s.seed)

            inbox: dict[str, list[ReceivedMessage]] = {n: [] for n in NATION_IDS}
            for n, (out, chosen) in zip(ai, results):
                new.nations[n].public_statement = out.public_statement
                for m in out.messages:
                    inbox[m.to].append(ReceivedMessage(**{"from": n, "text": m.text}))
                self.leaders[n] = LeaderDetail(
                    public_statement=out.public_statement, private_intent=out.private_intent,
                    advice=advice[n], chosen=chosen, reason=out.reason, persona=_persona(n))
            self.inbox, self.queued, self.state = inbox, [], new
            return new

    async def _crisis_tick(self) -> State:
        s = self.state
        c = s.crisis
        nxt = c.tick + 1
        due = [n for n in self.ai_nations() if n not in c.decisions and c.deadlines.get(n) == nxt]
        advice = {n: advise(s, n) for n in due}
        results = await asyncio.gather(*(self._one_leader(n, advice[n]) for n in due))

        queued_by = {a.by for a in self.queued}
        actions = list(self.queued)
        if self.pending_announce:
            actions.append(self.pending_announce)
        for n, (out, chosen) in zip(due, results):
            if n not in queued_by:
                actions += chosen
        new = step(s, actions, s.seed)

        for n, (out, chosen) in zip(due, results):
            new.nations[n].public_statement = out.public_statement
            self.leaders[n] = LeaderDetail(
                public_statement=out.public_statement, private_intent=out.private_intent,
                advice=advice[n], chosen=chosen, reason=out.reason, persona=_persona(n))
        self.queued, self.pending_announce = [], None
        if new.crisis:
            for e in crisis_file(new.crisis.id).scripted:
                announces = (e.model_extra or {}).get("announces")
                if e.type == "incoming_call" and e.tick == new.crisis.tick and announces:
                    self.pending_announce = Action(type="announce", by=e.from_, params={"action": announces})
        self.crisis_log.append(new)
        self.state = new
        return new

    def leader(self, nation: str) -> LeaderDetail:
        if nation in self.leaders:
            return self.leaders[nation]
        n = self.state.nations[nation]
        return LeaderDetail(public_statement=n.public_statement, private_intent="", advice=advise(self.state, nation),
                            chosen=[], reason="", persona=_persona(nation))

    def apply_call(self, to: str, out: CallOutput, interrupted: bool = False,
                   hesitation_ms: Optional[int] = None) -> State:
        """For /call: apply a leader's reply to the world. Changes take effect at once,
        except actions, which are applied on the next turn."""
        s = self.state.model_copy(deep=True)
        b = s.nations[to].beliefs
        if b is not None:
            b.trust_in_player = round(min(1.0, max(0.0, b.trust_in_player + out.belief_updates.trust_in_player)), 3)
            b.resolve_of_player = round(min(1.0, max(0.0, b.resolve_of_player + out.belief_updates.resolve_of_player)), 3)
        seat = s.seat.nation
        call = weights()["call"]
        if interrupted and self.pending_announce and self.pending_announce.by == to:
            self.pending_announce = None  # cut off before the threat went public
        if interrupted and to in call["proud"] and to != seat:
            k = relation_key(seat, to)
            s.relations[k] = max(-100, s.relations.get(k, 0) + call["interrupt_relation_proud"])
        tick = s.crisis.tick if s.crisis else s.turn
        ledger = s.crisis.promises if s.crisis else self.promises
        for p in out.promises:
            ledger.append(CrisisPromise(id=f"p{len(ledger) + 1}", tick=tick, by="player",
                                        to=p.to, what=p.what, when=p.when, condition=p.condition))
        self.queued += out.actions
        if s.incoming_call and s.incoming_call.from_ == to:
            s.incoming_call = None  # answered
        self.state = s
        return s


GAME = Game()
