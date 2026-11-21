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
    NATION_IDS, Action, Advice, CallOutput, CallResult, Decision, Ending, CrisisPromise, LeaderDetail, LeaderOutput,
    LeaderView, ReceivedMessage, Seat, State,
)
from engine.core import advise, is_legal, new_game, relation_key, step, weights
from engine.crisis import crisis_file, defiance_limit, rerun_crisis, scripted_now, start_crisis, with_announcement
from engine.snapshots import snapshot
from engine.calls import apply_call_effects
from engine.futures import futures
from engine.ending import plain_verdict, score

log = logging.getLogger("gambit.engine")
ROOT = Path(__file__).resolve().parent.parent
DECIDE_TIMEOUT_S = float(os.environ.get("GAMBIT_DECIDE_TIMEOUT", "8"))

Decide = Callable[[LeaderView], Awaitable[LeaderOutput]]


HISTORIAN_TIMEOUT_S = float(os.environ.get("GAMBIT_HISTORIAN_TIMEOUT", "30"))


MEDIATOR = os.environ.get("GAMBIT_MEDIATOR", "").lower() in ("1", "true", "on", "yes")


def available_roles() -> Optional[list[str]]:
    """Seats /start accepts beyond the president (DECIDED 13:09); None means president only."""
    return ["president", "mediator"] if MEDIATOR else None


EXTRA_CRISES = os.environ.get("GAMBIT_EXTRA_CRISES", "").lower() in ("1", "true", "on", "yes")


def available_crises() -> Optional[list[dict]]:
    """Crises /crisis/start accepts beyond One Berth (DECIDED 13:12): every file in
    data/crises/ that loads, One Berth first. None (One Berth only) unless the flag is on."""
    if not EXTRA_CRISES:
        return None
    from engine.crisis import available
    out = []
    for cid in available():
        try:
            out.append({"id": cid, "title": crisis_file(cid).title})
        except Exception as e:  # a broken file is simply not offered
            log.warning("crisis %s does not load: %s", cid, e)
    return sorted(out, key=lambda c: (c["id"] != "one_berth", c["id"]))


def allowed_crises() -> list[str]:
    return [c["id"] for c in available_crises() or []] or ["one_berth"]


PRIVATE_STRATEGY = os.environ.get("GAMBIT_PRIVATE_STRATEGY", "").lower() in ("1", "true", "on", "yes")


def _load_strategize():
    """agents.strategize_all, only when GAMBIT_PRIVATE_STRATEGY is on (DECIDED 13:07)."""
    if not PRIVATE_STRATEGY or os.environ.get("GAMBIT_AGENTS", "").lower() == "stub":
        return None
    try:
        from agents import strategize_all  # type: ignore
        return strategize_all
    except Exception:
        return None


def _load_historian():
    if os.environ.get("GAMBIT_AGENTS", "").lower() == "stub":
        return None
    try:
        from agents import historian  # type: ignore
        return historian
    except Exception:
        return None


def _new_items(old: list, new: list) -> list:
    """Items appended to an append-then-trim list (news, events) between two states."""
    if not old:
        return list(new)
    last = old[-1]
    for i in range(len(new) - 1, -1, -1):
        if new[i] == last:
            return list(new[i + 1:])
    return list(new)


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
        seat = seat or Seat(role="president", nation="valdoria")
        if seat.role not in (available_roles() or ["president"]):
            raise ValueError(f"the {seat.role} seat is not enabled")
        self.state = new_game(seed, seat)
        if available_roles():
            self.state = self.state.model_copy(update={"available_roles": available_roles()})
        if available_crises():
            self.state = State.model_validate({**self.state.model_dump(), "available_crises": available_crises()})
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
        self.crisis_own: dict[str, Decision] = {}  # each leader's own choice, before any phone deal
        self.crisis_announces: list[tuple[int, Action]] = []
        self.crisis_calls: list[tuple[int, str, CallOutput, bool]] = []
        self.last_crisis: Optional[dict] = None  # inputs of the finished crisis, for replay
        # End of session (W7): the whole session's log and the score counters.
        self.start_state = self.state
        self.session_log: list[dict] = [{"turn": 0, "type": "news", "text": n.text} for n in self.state.news]
        self.months_in_power = self.peace_months = 0
        self.promises_kept = self.promises_broken = 0
        self.peaceful_crises = 0
        seat_nation = self.state.seat.nation
        self.original_leader = self.state.nations[seat_nation].leader if seat_nation else "The mediator"
        # Private strategies by phase: "" for the game, a crisis id for that crisis.
        self.strategies: dict[str, dict[str, str]] = {}
        self._strategize("")
        return self.state

    def start_crisis(self, crisis_id: str) -> State:
        self.state = start_crisis(self.state, crisis_id)
        self.pending_announce, self.crisis_log = None, [self.state]
        self.crisis_advice, self.crisis_announces, self.crisis_calls, self.last_crisis = {}, [], [], None
        self.crisis_own = {}
        self._strategize(crisis_id)
        return self.state

    # --- private strategy (DECIDED 13:07, behind GAMBIT_PRIVATE_STRATEGY) ---------

    def _strategize(self, phase: str) -> None:
        """Ask the leaders for their private strategies in the background, off the turn path.
        A result that arrives after a reset is dropped."""
        fn = self._strategize_fn() if self._decide_fn is not None else None
        if fn is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # only inside the server
        epoch, snapshot_ = self.epoch, self.state

        async def run() -> None:
            try:
                out = await fn(snapshot_)
            except Exception as e:
                log.warning("strategize failed: %s", e)
                return
            if epoch == self.epoch:
                self.strategies[phase] = {n: str(t) for n, t in (out or {}).items() if t}
        self._strategy_task = loop.create_task(run())

    def _strategize_fn(self):
        return _load_strategize()

    def strategy_for(self, nation: str) -> Optional[str]:
        """This crisis's strategy if written, else the game's."""
        c = self.state.crisis
        return (self.strategies.get(c.id, {}) if c else {}).get(nation) or self.strategies.get("", {}).get(nation)

    def ai_nations(self) -> list[str]:
        return [n for n in NATION_IDS if n != self.state.seat.nation]

    async def _one_leader(self, nation: str, advice: list[Advice]) -> tuple[LeaderOutput, list[Action]]:
        s = self.state
        out: Optional[LeaderOutput] = None
        if self._decide_fn is not None:
            view = LeaderView(nation=nation, state=s, advice=advice,
                              messages_received=self.inbox[nation],
                              private_strategy=self.strategy_for(nation))
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
        out, legal = self._bounded(nation, advice, out, legal[:1])
        return out, legal[:1]

    def _bounded(self, nation: str, advice: list[Advice], out: LeaderOutput,
                 chosen: list[Action]) -> tuple[LeaderOutput, list[Action]]:
        """In a crisis a leader may defy its advisers, but not by any margin. The crisis file's
        rules.max_defiance is how far below the advisers' top a leader's own choice may score;
        beyond that the cabinet overrules him. Without the rule, leaders are unbounded.

        Why: with a second berth secured and docking scored 8.0 against 2.2, Ostrava's leader
        still chose the blockade four times out of four, so nothing the player did after a
        caught double promise could change the outcome (Reviewer, live probe 13:41)."""
        c = self.state.crisis
        if c is None or not chosen or not advice:
            return out, chosen
        scores = {a.action.type: a.score for a in advice}
        pick = chosen[0].type
        # Escalations (blockade, mobilise...) have their own, tighter limit: a leader does not
        # start a war against his cabinet. Live at 13:58, an interrupted Ostrava offered half a
        # day (dock 3.2 against blockade 2.2) still blockaded, so interrupting changed nothing.
        limit = defiance_limit(crisis_file(c.id).rules, pick)
        if limit is None or pick not in scores or scores[advice[0].action.type] - scores[pick] <= limit:
            return out, chosen
        top = advice[0].action
        log.info("%s wanted %s (%.1f) but the cabinet insists on %s (%.1f)", nation, pick, scores[pick],
                 top.type, advice[0].score)
        reason = f"Wanted to {pick.replace('_', ' ')}; overruled by the cabinet. {out.reason}".strip()
        return out.model_copy(update={"reason": reason}), [top]

    async def turn(self) -> State:
        async with self.lock:
            if self.state.phase == "ended":
                return self.state
            if self.state.phase == "crisis":
                return await self._crisis_tick()
            s = self.state
            ai = self.ai_nations()
            advice = {n: advise(s, n) for n in ai}
            epoch = self.epoch
            results = await asyncio.gather(*(self._one_leader(n, advice[n]) for n in ai))
            if epoch != self.epoch:  # /start arrived while the leaders were thinking
                return self.state
            # A phone call can land while the leaders think (apply_call does not take the
            # lock). Step from the state as it is now, or that call's promises, trust
            # changes and last_call would be overwritten.
            s = self.state

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
            self._record(s, new)
            self._after_month(s, new)
            return self.state

    async def _crisis_tick(self) -> State:
        s = self.state
        c = s.crisis
        nxt = c.tick + 1
        due = [n for n in self.ai_nations() if n not in c.decisions and c.deadlines.get(n) == nxt]
        seen = with_announcement(s, self.pending_announce)  # a threat going public this tick counts
        advice = {n: advise(seen, n) for n in due}
        epoch = self.epoch
        results = await asyncio.gather(*(self._one_leader(n, advice[n]) for n in due))
        if epoch != self.epoch or self.state.crisis is None:  # reset, or ended, meanwhile
            return self.state
        s = self.state  # keep any call that landed while the leaders were thinking

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
            own = chosen[0].type if chosen else (advice[n][0].action.type if advice[n] else None)
            if own:
                self.crisis_own[n] = Decision(action=own, tick=nxt)
            self.leaders[n] = LeaderDetail(
                public_statement=out.public_statement, private_intent=out.private_intent,
                advice=advice[n], chosen=chosen, reason=out.reason, persona=_persona(n))
        self.queued, self.pending_announce = [], None
        if new.crisis:
            for e in scripted_now(new):
                announces = (e.model_extra or {}).get("announces")
                if e.type == "incoming_call" and announces:
                    self.pending_announce = Action(type="announce", by=e.from_, params={"action": announces})
        new = _voice_line(new)
        self._record(s, new)
        self.crisis_log.append(new)
        if new.crisis is None:  # resolved: keep what a replay needs
            last = s.crisis
            done = next(e for e in reversed(new.events) if e.type == "crisis_resolved")
            decisions = dict(last.decisions)
            for n_, a_ in done.model_extra["decisions"].items():
                decisions.setdefault(n_, Decision(action=a_, tick=last.ticks_total))
            self.last_crisis = {
                "start": self.crisis_log[0], "calls": list(self.crisis_calls), "decisions": decisions,
                "advice": dict(self.crisis_advice), "own": dict(self.crisis_own),
                "announces": list(self.crisis_announces),
                "snapshot_id": snapshot(self.crisis_log[0]),
            }
        self.state = new
        return new

    # --- end of session --------------------------------------------------------

    def _record(self, old: State, new: State) -> None:
        for n in _new_items(old.news, new.news):
            self.session_log.append({"turn": n.turn, "type": "news", "text": n.text})
        for e in _new_items(old.events, new.events):
            d = e.model_dump(mode="json")
            self.session_log.append(d)
            if d["type"] == "crisis_resolved":
                self.promises_kept += d.get("promises_kept", 0)
                self.promises_broken += d.get("promises_broken", 0)
                self.peaceful_crises += 0 if d.get("war") else 1

    def _after_month(self, old: State, new: State) -> None:
        seat = new.seat.nation  # None for a mediator: no ouster, and peace means no war anywhere
        ousted = [e for e in _new_items(old.events, new.events)
                  if seat is not None and e.nation == seat and e.type in ("election", "coup")]
        if not ousted:
            self.months_in_power += 1
        if not any(l.type == "war" and (seat is None or seat in (l.a, l.b)) for l in new.links):
            self.peace_months += 1
        if ousted:
            self.end("voted_out" if ousted[0].type == "election" else "coup")
        elif new.turn >= weights()["politics"]["session_months"]:
            self.end("time")

    def end(self, reason: str = "ended") -> State:
        """Finish the session: phase "ended", the score, and the historian's verdict,
        which arrives in the background (a plain one is used if the historian fails)."""
        if self.state.phase == "ended":
            return self.state
        sc = score(self.start_state, self.state, self.months_in_power, self.peace_months,
                   self.promises_kept, self.promises_broken, self.peaceful_crises)
        self.state = self.state.model_copy(update={
            "phase": "ended", "crisis": None, "incoming_call": None,
            "ending": Ending(reason=reason, score=sc)})
        fallback = plain_verdict(self.state, reason, sc, self.original_leader)
        log_ = list(self.session_log) + [{"turn": self.state.turn, "type": "session_end", "reason": reason,
                                          "score": sc.model_dump()}]
        epoch = self.epoch

        def set_verdict(text: str) -> None:
            if epoch == self.epoch and self.state.ending:
                self.state = self.state.model_copy(update={
                    "ending": self.state.ending.model_copy(update={"verdict": text})})

        historian = _load_historian() if self._decide_fn is not None else None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if historian is None or loop is None:
            set_verdict(fallback)
        else:
            async def run() -> None:
                try:
                    text = await asyncio.wait_for(historian(log_), timeout=HISTORIAN_TIMEOUT_S)
                    set_verdict(str(text).strip() or fallback)
                except Exception as e:
                    log.warning("historian failed (%s); using the plain verdict", e)
                    set_verdict(fallback)
            self._historian_task = loop.create_task(run())
        return self.state

    def replay(self, shift_ticks: int) -> list[dict]:
        """Rerun the last crisis with the player's promises moved by `shift_ticks`.
        Returns [{nation, was, now}] for every leader whose decision changed (why() is Abi's)."""
        lc = self.last_crisis
        if lc is None:
            raise LookupError("no finished crisis to replay")
        total = lc["start"].crisis.ticks_total
        moved = [(min(total, max(0, t + shift_ticks)), to, out, intr) for t, to, out, intr in lc["calls"]]
        was = {n: d.action for n, d in lc["decisions"].items()}
        _, now = rerun_crisis(lc["start"], moved, lc["own"], lc["advice"],
                              lc["start"].seed)
        return [{"nation": n, "was": was[n], "now": now.get(n, was[n])}
                for n in NATION_IDS if n in was and now.get(n, was[n]) != was[n]]

    def leader(self, nation: str) -> LeaderDetail:
        strategy = self.strategy_for(nation)
        if nation in self.leaders:
            return self.leaders[nation].model_copy(update={"private_strategy": strategy})
        n = self.state.nations[nation]
        return LeaderDetail(public_statement=n.public_statement, private_intent="", advice=advise(self.state, nation),
                            chosen=[], reason="", persona=_persona(nation), private_strategy=strategy)

    def interrupt(self, to: str) -> bool:
        """The player cut this leader off. Cancels a threat that has not gone public yet.
        Called the moment /call arrives, so it does not wait for the reply to be worked
        out (interpret takes seconds; the next tick would make the threat public first)."""
        if self.pending_announce and self.pending_announce.by == to:
            self.pending_announce = None
            return True
        return False

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
        if interrupted:
            self.interrupt(to)  # normally already done when /call arrived
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


def public_view(state: State) -> State:
    """What the player may see (DECIDED 13:17). A mediator sees public positions only, so
    leaders' beliefs about the player are left out; the engine keeps scoring with them."""
    if state.seat.role != "mediator":
        return state
    s = state.model_copy(deep=True)
    for n in s.nations.values():
        n.beliefs = None
    return s


def public_leader(state: State, d: LeaderDetail) -> LeaderDetail:
    """/leaders/{id} for the player: a mediator gets the public statement and nothing private
    (no private intent, advice, chosen actions, reason, persona card or strategy)."""
    if state.seat.role != "mediator":
        return d
    return LeaderDetail(public_statement=d.public_statement, private_intent="", advice=[], chosen=[],
                        reason="", persona="", private_strategy=None)


GAME = Game()
