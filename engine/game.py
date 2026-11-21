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
    NATION_IDS, Action, Advice, CallOutput, CallResult, CrisisPromise, LeaderDetail, LeaderOutput,
    LeaderView, ReceivedMessage, Seat, State,
)
from engine.core import advise, is_legal, new_game, relation_key, step, weights
from engine.crisis import crisis_file, rerun_crisis, start_crisis
from engine.snapshots import snapshot
from engine.calls import apply_call_effects
from engine.futures import futures

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


def _voice_line(state: State) -> State:
    """Give a new incoming call its audio (Ashish's REQUEST on #27). Lives here, not in the
    pure crisis_step, because rendering is a side effect the rollouts must never trigger."""
    call = state.incoming_call
    if call is None or call.audio_url:
        return state
    try:
        from voice import audio_url_for  # type: ignore
        url = audio_url_for(call.from_, call.opening_line, call.emotion)
    except Exception as e:  # no /voice, or it failed: the page still shows the line
        log.info("no audio for incoming call from %s: %s", call.from_, e)
        return state
    if not url:
        return state
    return state.model_copy(update={"incoming_call": call.model_copy(update={"audio_url": url})})


def _persona(nation: str) -> str:
    path = ROOT / "agents" / "personas" / f"{nation}.md"
    return path.read_text() if path.exists() else ""


class Game:
    def __init__(self, seed: int = 7, seat: Optional[Seat] = None,
                 decide: Optional[Decide] = None, use_agents: bool = True, needle: bool = True):
        self.needle = needle  # recompute state.last_futures in the background after calls
        self._decide_fn = decide if decide is not None else (_load_decide() if use_agents else None)
        self.lock = asyncio.Lock()
        self.reset(seed, seat)

    def reset(self, seed: int, seat: Optional[Seat] = None) -> State:
        self.state = new_game(seed, seat or Seat(role="president", nation="valdoria"))
        self.leaders: dict[str, LeaderDetail] = {}
        self.inbox: dict[str, list[ReceivedMessage]] = {n: [] for n in NATION_IDS}
        self.queued: list[Action] = []  # agreed on the phone; applied next turn
        # Each reset starts a new epoch; call ids carry it, so a reply that finishes after
        # a reset is dropped instead of leaking into the new game.
        self.epoch = getattr(self, "epoch", 0) + 1
        self.call_count = 0
        self.latest_call_id: Optional[str] = None
        self.promises: list[CrisisPromise] = []  # strategy-phase promises (crisis ones live in state)
        self.pending_announce: Optional[Action] = None  # becomes public next tick unless interrupted
        self.crisis_log: list[State] = []  # every crisis tick, for replay and the needle
        self.crisis_advice: dict[str, list[Advice]] = {}  # each leader's advice when it decided
        self.crisis_announces: list[tuple[int, Action]] = []
        self.crisis_calls: list[tuple[int, str, CallOutput, bool]] = []
        self.last_crisis: Optional[dict] = None  # inputs of the finished crisis, for replay
        return self.state

    def start_crisis(self, crisis_id: str) -> State:
        self.state = start_crisis(self.state, crisis_id)
        self.pending_announce, self.crisis_log = None, [self.state]
        self.crisis_advice, self.crisis_announces, self.crisis_calls, self.last_crisis = {}, [], [], None
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
            self.crisis_announces.append((nxt, self.pending_announce))
        for n, (out, chosen) in zip(due, results):
            if n not in queued_by:
                actions += chosen
        new = step(s, actions, s.seed)

        for n, (out, chosen) in zip(due, results):
            new.nations[n].public_statement = out.public_statement
            self.crisis_advice[n] = advice[n]
            self.leaders[n] = LeaderDetail(
                public_statement=out.public_statement, private_intent=out.private_intent,
                advice=advice[n], chosen=chosen, reason=out.reason, persona=_persona(n))
        self.queued, self.pending_announce = [], None
        if new.crisis:
            for e in crisis_file(new.crisis.id).scripted:
                announces = (e.model_extra or {}).get("announces")
                if e.type == "incoming_call" and e.tick == new.crisis.tick and announces:
                    self.pending_announce = Action(type="announce", by=e.from_, params={"action": announces})
        new = _voice_line(new)
        self.crisis_log.append(new)
        if new.crisis is None:  # resolved: keep what a replay needs
            last = s.crisis
            done = next(e for e in reversed(new.events) if e.type == "crisis_resolved")
            from contracts.models import Decision
            decisions = dict(last.decisions)
            for n_, a_ in done.model_extra["decisions"].items():
                decisions.setdefault(n_, Decision(action=a_, tick=last.ticks_total))
            self.last_crisis = {
                "start": self.crisis_log[0], "calls": list(self.crisis_calls), "decisions": decisions,
                "advice": dict(self.crisis_advice), "announces": list(self.crisis_announces),
                "snapshot_id": snapshot(self.crisis_log[0]),
            }
        self.state = new
        return new

    def replay(self, shift_ticks: int) -> list[dict]:
        """Rerun the last crisis with the player's promises moved by `shift_ticks`.
        Returns [{nation, was, now}] for every leader whose decision changed (why() is Abi's)."""
        lc = self.last_crisis
        if lc is None:
            raise LookupError("no finished crisis to replay")
        total = lc["start"].crisis.ticks_total
        moved = [(min(total, max(0, t + shift_ticks)), to, out, intr) for t, to, out, intr in lc["calls"]]
        was = {n: d.action for n, d in lc["decisions"].items()}
        _, now = rerun_crisis(lc["start"], moved, lc["decisions"], lc["advice"], lc["announces"],
                              lc["start"].seed)
        return [{"nation": n, "was": was[n], "now": now.get(n, was[n])}
                for n in NATION_IDS if n in was and now.get(n, was[n]) != was[n]]

    def leader(self, nation: str) -> LeaderDetail:
        if nation in self.leaders:
            return self.leaders[nation]
        n = self.state.nations[nation]
        return LeaderDetail(public_statement=n.public_statement, private_intent="", advice=advise(self.state, nation),
                            chosen=[], reason="", persona=_persona(nation))

    def begin_call(self, to: str) -> str:
        """For split replies: call when the spoken reply goes out. state.last_call shows
        this call as pending until apply_call(..., call_id=...) fills it in."""
        call_id = self._new_call_id()
        s = self.state.model_copy(deep=True)
        s.last_call = CallResult(call_id=call_id, to=to, pending=True)
        self.state = s
        return call_id

    def _new_call_id(self) -> str:
        self.call_count += 1
        self.latest_call_id = f"g{self.epoch}c{self.call_count}"
        return self.latest_call_id

    def apply_call(self, to: str, out: CallOutput, interrupted: bool = False,
                   hesitation_ms: Optional[int] = None, call_id: Optional[str] = None) -> State:
        """For /call: apply a leader's reply to the world. Changes take effect at once,
        except actions, which are applied on the next turn.

        With a call_id from begin_call(): a reply from before the last /start is ignored,
        and state.last_call only shows it if no newer call has started since."""
        if call_id is not None and not call_id.startswith(f"g{self.epoch}c"):
            log.warning("dropping reply for %s: call %s started before the game was reset", to, call_id)
            return self.state
        if interrupted and self.pending_announce and self.pending_announce.by == to:
            self.pending_announce = None  # cut off before the threat went public
        before = self.state
        s, strategy_promises = apply_call_effects(self.state, to, out, interrupted, len(self.promises))
        self.promises += strategy_promises
        if s.crisis:
            self.crisis_calls.append((s.crisis.tick, to, out.model_copy(deep=True), interrupted))
        self.queued += out.actions
        if call_id is None:
            call_id = self._new_call_id()
        if call_id == self.latest_call_id:  # an older call finishing late does not hide a newer one
            s.last_call = CallResult(call_id=call_id, to=to, pending=False, promises=out.promises,
                                     actions=out.actions, ends_call=out.ends_call)
        self.state = s
        if self.needle and (out.promises or out.actions):
            self._needle(before, s, list(self.queued))
        return s

    def _needle(self, before: State, after: State, first: list[Action]) -> None:
        """Recompute the war-odds needle in the background after a call that changed something."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # not inside the server (tests, scripts): call futures() directly instead

        self.needle_seq = getattr(self, "needle_seq", 0) + 1
        seq, epoch = self.needle_seq, self.epoch

        async def run() -> None:
            try:
                result = await asyncio.to_thread(futures, before, after, first)
            except Exception:
                log.exception("needle rollouts failed")
                return
            if epoch == self.epoch and seq == self.needle_seq:  # not stale: no reset, no newer call
                self.state = self.state.model_copy(update={"last_futures": result})
        self._needle_task = loop.create_task(run())


GAME = Game()
