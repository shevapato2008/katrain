"""Pure decisions for the self-owned PvP lobby bot population."""

from __future__ import annotations

import random
import asyncio
import json
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from katrain.core import ladder


@dataclass(frozen=True)
class PlayableRung:
    rung: int
    rank_label: str


def playable_rungs() -> tuple[PlayableRung, ...]:
    """Use the current fitted, certified catalog rather than legacy user ranks."""
    return tuple(
        PlayableRung(level.rung, level.rank_name)
        for level in ladder.LADDER_LEVELS
        if level.recipe is not None and level.certification_status == "certified" and level.availability == "available"
    )


def human_ladder_rungs(session_factory, user_ids: Iterable[int]) -> dict[int, int | None]:
    """Read authoritative human placement in one query from the app's database."""
    ids = {user_id for user_id in user_ids if user_id > 0}
    if not ids:
        return {}
    from katrain.web.core.models_db import AiLadderProfile

    db = session_factory()
    try:
        rows = db.query(AiLadderProfile.user_id, AiLadderProfile.ai_ladder_rung).filter(
            AiLadderProfile.user_id.in_(ids)
        ).all()
        return {user_id: rung for user_id, rung in rows}
    finally:
        db.close()


def validate_config(config: Mapping[str, object]) -> dict[str, object]:
    """Validate and fill a version-one JSON configuration without changing its input."""
    if not isinstance(config, Mapping) or set(config) != {"version", "enabled", "bot_game_limit", "idle_targets"}:
        raise ValueError("invalid PvP lobby bot config fields")
    if type(config["version"]) is not int or config["version"] != 1:
        raise ValueError("unsupported PvP lobby bot config version")
    if type(config["enabled"]) is not bool:
        raise ValueError("enabled must be a boolean")
    limit = config["bot_game_limit"]
    if type(limit) is not int or not 0 <= limit <= 6:
        raise ValueError("bot_game_limit must be 0..6")
    supplied = config["idle_targets"]
    if not isinstance(supplied, Mapping):
        raise ValueError("idle_targets must be an object")
    playable = {str(level.rung) for level in playable_rungs()}
    if any(type(key) is not str or key not in playable for key in supplied):
        raise ValueError("idle_targets contains an unknown rung")
    if any(type(target) is not int or not 1 <= target <= 20 for target in supplied.values()):
        raise ValueError("idle_targets must be 1..20 per rung")
    return {
        "version": 1,
        "enabled": config["enabled"],
        "bot_game_limit": limit,
        "idle_targets": {str(level.rung): supplied.get(str(level.rung), 2) for level in playable_rungs()},
    }


def _check_identity_coordinates(rung: int, slot: int) -> None:
    if type(rung) is not int or rung < 1 or type(slot) is not int or slot < 1:
        raise ValueError("bot rung and slot must be positive integers")


def bot_id(rung: int, slot: int) -> int:
    """A stable negative ID, injective even if a rung needs many slots."""
    _check_identity_coordinates(rung, slot)
    pair_sum = rung + slot
    return -(pair_sum * (pair_sum + 1) // 2 + slot + 1)


def bot_name(rung: int, slot: int) -> str:
    _check_identity_coordinates(rung, slot)
    return f"棋友·{rung}·{slot}"


def idle_reserve_deficit(config: Mapping[str, object], idle_now: Mapping[int, int]) -> dict[int, int]:
    """Count missing unreserved bots independently at each playable rung."""
    normalized = validate_config(config)
    targets = normalized["idle_targets"]
    assert isinstance(targets, dict)
    if any(type(count) is not int or count < 0 for count in idle_now.values()):
        raise ValueError("idle bot counts must be nonnegative integers")
    if not normalized["enabled"]:
        return {int(rung): 0 for rung in targets}
    return {int(rung): max(0, target - idle_now.get(int(rung), 0)) for rung, target in targets.items()}


def choose_next_rung(eligible_rungs: Iterable[int], *, after_rung: int | None = None) -> int | None:
    """Select the next eligible rung in catalog order, wrapping at the end."""
    raw_rungs = tuple(eligible_rungs)
    playable = {level.rung for level in playable_rungs()}
    if any(type(rung) is not int or rung not in playable for rung in raw_rungs):
        raise ValueError("rotation contains an unplayable rung")
    if after_rung is not None and type(after_rung) is not int:
        raise ValueError("after_rung must be an integer or None")
    eligible = sorted(set(raw_rungs))
    return next(
        (rung for rung in eligible if after_rung is None or rung > after_rung),
        eligible[0] if eligible else None,
    )


def next_move_delay(rng: random.Random | None = None) -> int:
    """Draw an independent 5..30-second delay for each bot turn."""
    return (rng or random).randint(5, 30)


class PvpLobbyBotRuntime:
    """Central process owner of virtual identities and their reservations.

    Idle bots are rows only. Sessions and engines are attached only after a seat
    has been reserved for a real game.
    """

    def __init__(self, app):
        self.app = app
        self._lock = threading.RLock()
        self.config = validate_config({"version": 1, "enabled": False, "bot_game_limit": 3, "idle_targets": {}})
        self.config_revision = 0
        self._slots: dict[int, set[int]] = {}
        self._busy: dict[int, int] = {}
        self._generation = 0
        self._rotation_games = 0
        self._last_rung: int | None = None
        self.engine_errors = 0
        self._sessions: dict[str, tuple] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._stall_tasks: dict[str, asyncio.Task] = {}
        self._poll_task: asyncio.Task | None = None
        self._waiting_tasks: dict[int, asyncio.Task] = {}
        self._waiting_sockets: dict[int, object] = {}
        self._move_slots = asyncio.Semaphore(2)
        self._move_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pvp-bot")
        self.human_wait_seconds = 3.0

    def apply_config(self, config: Mapping[str, object], *, revision: int) -> None:
        normalized = validate_config(config)
        if type(revision) is not int or revision < 0:
            raise ValueError("config revision must be a nonnegative integer")
        with self._lock:
            self.config = normalized
            self.config_revision = revision
            if normalized["enabled"]:
                for rung in (level.rung for level in playable_rungs()):
                    self._fill_idle_reserve(rung)

    def _idle_slots(self, rung: int) -> list[int]:
        return [slot for slot in sorted(self._slots.get(rung, set())) if bot_id(rung, slot) not in self._busy]

    def _fill_idle_reserve(self, rung: int) -> None:
        target = self.config["idle_targets"][str(rung)]
        slots = self._slots.setdefault(rung, set())
        while len(self._idle_slots(rung)) < target:
            slots.add(max(slots, default=0) + 1)

    def _reserve(self, rung: int, *, protect_target: bool) -> tuple[int, int]:
        slots = self._slots.setdefault(rung, set())
        idle = self._idle_slots(rung)
        if protect_target and len(idle) <= self.config["idle_targets"][str(rung)]:
            slots.add(max(slots, default=0) + 1)
            idle = self._idle_slots(rung)
        if not idle:
            slots.add(max(slots, default=0) + 1)
            idle = self._idle_slots(rung)
        identity = bot_id(rung, idle[0])
        self._generation += 1
        self._busy[identity] = self._generation
        self._fill_idle_reserve(rung)
        return identity, self._generation

    def reserve_bot(self, rung: int) -> tuple[int, int] | None:
        with self._lock:
            if not self.config["enabled"] or str(rung) not in self.config["idle_targets"]:
                return None
            return self._reserve(rung, protect_target=False)

    def reservation_valid(self, identity: int, generation: int) -> bool:
        with self._lock:
            return self._busy.get(identity) == generation

    def release_bot(self, identity: int, generation: int) -> None:
        with self._lock:
            if self._busy.get(identity) == generation:
                del self._busy[identity]

    def reserve_rotation_pair(self, *, human_waiting: bool) -> tuple[int, int, int, int, int] | None:
        with self._lock:
            if human_waiting or not self.config["enabled"] or self._rotation_games >= self.config["bot_game_limit"]:
                return None
            rung = choose_next_rung((level.rung for level in playable_rungs()), after_rung=self._last_rung)
            if rung is None:
                return None
            first, first_generation = self._reserve(rung, protect_target=True)
            second, second_generation = self._reserve(rung, protect_target=True)
            self._rotation_games += 1
            self._last_rung = rung
            return rung, first, first_generation, second, second_generation

    def release_rotation_pair(self, rung: int, first: int, first_generation: int,
                              second: int, second_generation: int) -> None:
        with self._lock:
            if self.reservation_valid(first, first_generation) and self.reservation_valid(second, second_generation):
                self._rotation_games = max(0, self._rotation_games - 1)
            self.release_bot(first, first_generation)
            self.release_bot(second, second_generation)

    def public_online_rows(self) -> list[dict]:
        with self._lock:
            labels = {level.rung: level.rank_label for level in playable_rungs()}
            return [
                {"id": bot_id(rung, slot), "username": bot_name(rung, slot), "ladder_rung": rung,
                 "rank_label": labels[rung], "presence": "playing" if bot_id(rung, slot) in self._busy else "idle"}
                for rung, slots in self._slots.items() for slot in sorted(slots)
                if self.config["enabled"] or bot_id(rung, slot) in self._busy
            ]

    def bot_rung(self, identity: int) -> int | None:
        with self._lock:
            return next((rung for rung, slots in self._slots.items()
                         if any(bot_id(rung, slot) == identity for slot in slots)), None)

    def reserve_exact_bot(self, identity: int) -> tuple[int, int] | None:
        with self._lock:
            rung = self.bot_rung(identity)
            if rung is None or not self.config["enabled"] or identity in self._busy:
                return None
            self._generation += 1
            self._busy[identity] = self._generation
            self._fill_idle_reserve(rung)
            return rung, self._generation

    def _attach(self, session, rung: int, reservations: tuple[tuple[int, int], ...], *, rotation=False):
        session.bot_game = True
        session.bot_rung = rung
        session.bot_reservations = reservations
        session.katrain.deliver_analysis = False
        session.katrain.suppress_auto_eval = True
        session.katrain.pvp_bot_session = True
        session.last_state = session.katrain.get_state()
        with self._lock:
            self._sessions[session.session_id] = (rung, reservations, rotation)
        event = asyncio.Event()
        event.set()
        self._events[session.session_id] = event
        self._tasks[session.session_id] = asyncio.create_task(self._run_game(session))

    def create_human_bot_game(self, human_id: int, human_name: str, identity: int, *, human_reserved=False):
        """Reserve one exact visible bot and create a nonranking central room."""
        matchmaker = self.app.state.matchmaker
        if not human_reserved and not matchmaker.reserve_invitation(human_id, identity):
            return None
        reserved = self.reserve_exact_bot(identity)
        if reserved is None:
            matchmaker.release_users(human_id, identity)
            return None
        rung, generation = reserved
        session = None
        try:
            black_human = random.random() < 0.5
            black_id, white_id = (human_id, identity) if black_human else (identity, human_id)
            black_name, white_name = (human_name, self._bot_username(identity)) if black_human else (
                self._bot_username(identity), human_name)
            session = self.app.state.session_manager.create_multiplayer_session(
                black_id, white_id, b_name=black_name, w_name=white_name,
                initial_game_type="free", skip_initial_analysis=True,
            )
            self._attach(session, rung, ((identity, generation),))
            return session
        except Exception:
            if session is not None:
                self.app.state.session_manager.remove_session(session.session_id)
            self.release_bot(identity, generation)
            matchmaker.release_users(human_id, identity)
            raise

    def _bot_username(self, identity: int) -> str:
        for row in self.public_online_rows():
            if row["id"] == identity:
                return row["username"]
        raise ValueError("unknown bot identity")

    async def match_waiting_human(self, human_id: int, human_name: str, rung: int, websocket):
        await asyncio.sleep(self.human_wait_seconds)
        if not self.config["enabled"]:
            return
        if human_ladder_rungs(self.app.state.session_factory, [human_id]).get(human_id) != rung:
            self.app.state.matchmaker.remove_from_queue(human_id, websocket)
            try:
                await websocket.send_json({"type": "error", "code": "PLACEMENT_REQUIRED"})
            except Exception:
                pass
            return
        matchmaker = self.app.state.matchmaker
        reserved = self.reserve_bot(rung)
        if reserved is None:
            return
        identity, generation = reserved
        if not matchmaker.reserve_queued_for_bot(human_id, rung, websocket):
            self.release_bot(identity, generation)
            return
        # create_human_bot_game needs an exact reservation, so attach directly.
        session = None
        try:
            black_human = random.random() < 0.5
            black_id, white_id = (human_id, identity) if black_human else (identity, human_id)
            black_name, white_name = (human_name, self._bot_username(identity)) if black_human else (
                self._bot_username(identity), human_name)
            session = self.app.state.session_manager.create_multiplayer_session(
                black_id, white_id, b_name=black_name, w_name=white_name,
                initial_game_type="free", skip_initial_analysis=True,
            )
            self._attach(session, rung, ((identity, generation),))
        except Exception:
            if session is not None:
                self.app.state.session_manager.remove_session(session.session_id)
            self.release_bot(identity, generation)
            matchmaker.release_users(human_id)
            logging.getLogger("katrain_web").exception("delayed bot match could not start")
            try:
                await websocket.send_json({"type": "error", "code": "SESSION_UNAVAILABLE"})
            except Exception:
                pass
            return
        try:
            await websocket.send_json({"type": "match_found", "session_id": session.session_id,
                                       "game_type": "free", "players": {"player_b": black_id,
                                       "player_w": white_id, "player_b_name": black_name,
                                       "player_w_name": white_name},
                                       "my_color": "B" if black_human else "W"})
        except Exception:
            self.app.state.session_manager.remove_session(session.session_id)
            return
        await self.app.state.lobby_manager.broadcast({"type": "lobby_update"})

    def schedule_human_wait(self, human_id: int, human_name: str, rung: int, websocket) -> None:
        self.cancel_human_wait(human_id)
        task = asyncio.create_task(self.match_waiting_human(human_id, human_name, rung, websocket))
        self._waiting_tasks[human_id] = task
        self._waiting_sockets[human_id] = websocket

        def forget_completed(done):
            if self._waiting_tasks.get(human_id) is done:
                self._waiting_tasks.pop(human_id, None)
                self._waiting_sockets.pop(human_id, None)

        task.add_done_callback(forget_completed)

    def cancel_human_wait(self, human_id: int, websocket=None) -> None:
        if websocket is not None and self._waiting_sockets.get(human_id) is not websocket:
            return
        task = self._waiting_tasks.pop(human_id, None)
        self._waiting_sockets.pop(human_id, None)
        if task is not None:
            task.cancel()

    def session_removed(self, session) -> None:
        with self._lock:
            info = self._sessions.pop(session.session_id, None)
        task = self._tasks.pop(session.session_id, None)
        stall_task = self._stall_tasks.pop(session.session_id, None)
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        if task is not None and task is not current:
            task.get_loop().call_soon_threadsafe(task.cancel)
        if stall_task is not None and stall_task is not current:
            stall_task.get_loop().call_soon_threadsafe(stall_task.cancel)
        self._events.pop(session.session_id, None)
        if info is not None:
            rung, reservations, rotation = info
            if rotation:
                self.release_rotation_pair(rung, reservations[0][0], reservations[0][1],
                                           reservations[1][0], reservations[1][1])
            else:
                for identity, generation in reservations:
                    self.release_bot(identity, generation)

    def notify_state(self, session_id: str) -> None:
        event = self._events.get(session_id)
        if event is not None:
            event.set()

    def commit_candidate(self, session, identity: int, generation: int, candidate) -> bool:
        """The only bot play site: all validity checks and play share a lock."""
        node, move, thoughts = candidate
        manager = self.app.state.session_manager
        with session.lock:
            with manager._lock:
                if manager._sessions.get(session.session_id) is not session:
                    return False
            game = session.katrain.game
            color = "B" if session.player_b_id == identity else "W" if session.player_w_id == identity else None
            with session.katrain.ai_ladder_commit_lock:
                if (not self.reservation_valid(identity, generation) or session.game_ended
                        or game.current_node is not node or node.next_player != color
                        or getattr(game, "end_result", None)):
                    return False
                played = game.play(move, analyze=False)
                played.ai_thoughts = thoughts
                record_end = getattr(game, "record_two_pass_end", None)
                if record_end is not None:
                    record_end(played)
                session.last_state = session.katrain.get_state()
        session.katrain.update_state()
        return True

    async def _run_game(self, session):
        sid = session.session_id
        try:
            while sid in self._sessions and not session.game_ended and not getattr(session, "bot_degraded", False):
                state = session.katrain.get_state()
                identity = session.player_b_id if state.get("player_to_move") == "B" else session.player_w_id
                reservation = next(((bid, generation) for bid, generation in session.bot_reservations
                                    if bid == identity), None)
                if reservation is None:
                    event = self._events[sid]
                    event.clear()
                    await event.wait()
                    continue
                await asyncio.sleep(next_move_delay())
                if sid not in self._sessions or session.game_ended:
                    return
                try:
                    from katrain.core.ai import generate_ladder_candidate

                    async with self._move_slots:
                        game = session.katrain.game
                        candidate = await asyncio.get_running_loop().run_in_executor(
                            self._move_executor, generate_ladder_candidate, game, session.bot_rung
                        )
                    committed = self.commit_candidate(session, reservation[0], reservation[1], candidate)
                    terminal = getattr(session.katrain.game, "terminal", None)
                    if committed and terminal is not None and getattr(terminal, "node", None) is session.katrain.game.current_node:
                        await self.finish_terminal(session, terminal)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logging.getLogger("katrain_web").exception("certified bot move failed for %s", sid)
                    self.mark_degraded(session)
                    return
        except asyncio.CancelledError:
            pass

    async def _abort_stalled(self, session):
        try:
            await asyncio.sleep(600)
            if session.session_id in self._sessions and not getattr(session, "bot_finalized", False):
                await self.finish(session, reason="engine_abort", result="Void")
        except asyncio.CancelledError:
            pass

    def mark_degraded(self, session) -> None:
        self.engine_errors += 1
        session.bot_degraded = True
        session.katrain.pvp_lobby_degraded = True
        terminal = getattr(session.katrain.game, "terminal", None)
        if terminal is not None and not getattr(terminal.node, "end_state", None):
            session.katrain.pvp_lobby_awaiting_count = True
        # A two-pass terminal awaiting a score must stay visible during recovery.
        session.game_ended = False
        session.katrain.update_state()
        sid = session.session_id
        task = self._tasks.get(sid)
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        if task is not None and task is not current:
            task.cancel()
        if sid not in self._stall_tasks:
            self._stall_tasks[sid] = asyncio.create_task(self._abort_stalled(session))

    async def finish_terminal(self, session, end):
        """Score a bot room's second pass and close it through the one terminal path."""
        async with session.end_game_lock:
            if getattr(session, "bot_finalized", False) or session.katrain.game is not end.game:
                return
            if (session.katrain.game.current_node is not end.node
                    or getattr(end.node, "end_state", None)
                    or session.session_id not in self._sessions):
                return
            try:
                score = await asyncio.to_thread(session.katrain.ensure_current_score, node=end.node)
            except Exception:
                score = None
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
                self.mark_degraded(session)
                return
            result = f"{'B' if score >= 0 else 'W'}+{abs(score):.1f}"
            with session.lock:
                if (session.katrain.game is not end.game or session.katrain.game.current_node is not end.node
                        or session.session_id not in self._sessions):
                    return
                try:
                    session.katrain._commit_end_state(result, node=end.node, fill_pending=True)
                except Exception as exc:
                    if getattr(exc, "reason", None) in {"already_ended", "position_changed"}:
                        return
                    raise
                session.game_ended = True
                session.last_state = session.katrain.get_state()
            session.katrain.update_state()
            await self.finish(session, reason="two_pass", result=result)

    async def finish(self, session, *, reason: str, result: str, recorded: bool = False):
        """Idempotent terminal path for a bot room."""
        with session.lock:
            if getattr(session, "bot_finalized", False):
                return
            session.bot_finalized = True
            session.game_ended = True
            session.last_state = session.katrain.get_state()
        if not recorded and result != "Void":
            try:
                sgf = session.katrain.get_sgf()
                if isinstance(sgf, bytes):
                    sgf = sgf.decode("utf-8")
                self.app.state.game_repo.record_multiplayer_game(
                    sgf_content=sgf, result=result, game_type="free",
                    black_id=session.player_b_id, white_id=session.player_w_id,
                )
            except Exception:
                logging.getLogger("katrain_web").exception("bot game record failed for %s", session.session_id)
        winner_id = session.player_b_id if result.startswith("B+") else session.player_w_id if result.startswith("W+") else None
        await self.app.state.session_manager._broadcast_payload(
            session, {"type": "game_end", "data": {"reason": reason, "result": result, "winner_id": winner_id}}
        )
        self.app.state.session_manager.remove_session(session.session_id)
        await self.app.state.lobby_manager.broadcast({"type": "lobby_update"})

    def build_snapshot(self) -> dict:
        """Admin-only aggregate and complete active participant snapshot."""
        if self.app is None:
            raise RuntimeError("runtime is not attached to an app")
        sessions = [session for session in self.app.state.session_manager.list_active_multiplayer_sessions()
                    if not session.game_ended]
        game_by_user = {user_id: session.session_id for session in sessions
                        for user_id in (session.player_b_id, session.player_w_id)
                        if user_id is not None and user_id > 0}
        online_ids = set(self.app.state.lobby_manager.get_online_user_ids()) | set(game_by_user)
        humans = {row["id"]: row for row in self.app.state.user_repo.list_users() if row["id"] in online_ids}
        ranks = human_ladder_rungs(self.app.state.session_factory, online_ids)
        labels = {level.rung: level.rank_label for level in playable_rungs()}
        participants = [
            {"id": user_id, "username": user["username"], "ladder_rung": ranks.get(user_id),
             "rank_label": labels.get(ranks.get(user_id)), "presence": "playing" if user_id in game_by_user else "idle",
             "session_id": game_by_user.get(user_id), "kind": "human"}
            for user_id, user in humans.items()
        ]
        with self._lock:
            bot_session = {identity: sid for sid, (_, reservations, _) in self._sessions.items()
                           for identity, _ in reservations}
            active_bot_games = len(self._sessions)
        participants.extend({**row, "session_id": bot_session.get(row["id"]), "kind": "bot"}
                            for row in self.public_online_rows())
        rungs = []
        for level in playable_rungs():
            rows = [row for row in participants if row["kind"] == "bot" and row["ladder_rung"] == level.rung]
            rungs.append({"rung": level.rung, "rank_label": level.rank_label,
                          "idle_target": self.config["idle_targets"][str(level.rung)],
                          "idle_now": sum(row["presence"] == "idle" for row in rows),
                          "playing_now": sum(row["presence"] == "playing" for row in rows)})
        return {"reported_at": datetime.now(timezone.utc).isoformat(),
                "applied_config_revision": self.config_revision,
                "active_bot_games": active_bot_games, "engine_errors": self.engine_errors,
                "rungs": rungs, "participants": participants}

    def _load_config(self) -> None:
        from katrain.web.core.models_db import SystemConfigDB

        db = self.app.state.session_factory()
        try:
            row = db.get(SystemConfigDB, "pvp_lobby_bot_config")
            if row is not None:
                document = json.loads(row.value)
                self.apply_config(document["config"], revision=document["revision"])
        finally:
            db.close()

    def _publish_snapshot(self) -> None:
        from katrain.web.core.models_db import SystemConfigDB
        from sqlalchemy.exc import IntegrityError

        snapshot = self.build_snapshot()
        db = self.app.state.session_factory()
        try:
            for attempt in range(2):
                row = db.get(SystemConfigDB, "pvp_lobby_bot_runtime")
                if row is None:
                    row = SystemConfigDB(key="pvp_lobby_bot_runtime")
                    db.add(row)
                row.value = json.dumps(snapshot, ensure_ascii=False)
                try:
                    db.commit()
                    break
                except IntegrityError:
                    db.rollback()
                    if attempt:
                        raise
        finally:
            db.close()

    def _start_rotation_game(self) -> None:
        pair = self.reserve_rotation_pair(human_waiting=self.app.state.matchmaker.has_waiters())
        if pair is None:
            return
        rung, first, first_generation, second, second_generation = pair
        session = None
        try:
            session = self.app.state.session_manager.create_multiplayer_session(
                first, second, b_name=self._bot_username(first), w_name=self._bot_username(second),
                initial_game_type="free", skip_initial_analysis=True,
            )
            self._attach(session, rung, ((first, first_generation), (second, second_generation)), rotation=True)
        except Exception:
            if session is not None:
                self.app.state.session_manager.remove_session(session.session_id)
            self.release_rotation_pair(*pair)
            logging.getLogger("katrain_web").exception("PvP bot rotation game could not start")

    async def _poll_forever(self):
        try:
            while True:
                try:
                    await asyncio.to_thread(self._load_config)
                    if self.config["enabled"]:
                        self._start_rotation_game()
                    await asyncio.to_thread(self._publish_snapshot)
                except Exception:
                    logging.getLogger("katrain_web").exception("PvP bot runtime poll failed")
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass

    async def start(self):
        if self._poll_task is not None:
            raise RuntimeError("PvP bot runtime already started")
        if getattr(self.app.state, "pvp_lobby_bots", None) is not self:
            raise RuntimeError("PvP bot runtime must be the central app owner")
        self._poll_task = asyncio.create_task(self._poll_forever())

    async def stop(self):
        if self._poll_task is not None:
            self._poll_task.cancel()
            await self._poll_task
            self._poll_task = None
        for task in list(self._waiting_tasks.values()):
            task.cancel()
        self._waiting_tasks.clear()
        self._waiting_sockets.clear()
        for task in list(self._tasks.values()):
            task.cancel()
        for task in list(self._stall_tasks.values()):
            task.cancel()
        for sid in list(self._sessions):
            try:
                session = self.app.state.session_manager.get_session(sid)
            except KeyError:
                continue
            await self.finish(session, reason="shutdown", result="Void")
        self._move_executor.shutdown(wait=False, cancel_futures=True)
