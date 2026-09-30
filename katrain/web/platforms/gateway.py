"""Platform Command Gateway — intercepts game commands for platform-backed sessions.

For platform games: submit to remote platform -> wait for ACK -> apply locally.
For local games: pass through to KaTrain directly (existing behavior).
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Optional

from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import GamePhase, PlatformGameContext, PlatformMove, PlatformPass, PlatformResign

logger = logging.getLogger("katrain_web")

PLATFORM_ACK_TIMEOUT = 5.0  # seconds


class PlatformMoveRejectedError(Exception):
    """Raised when the platform rejects a submitted move.

    `reason` is a stable machine-readable code (Task 7 consumes it for UI copy):
    "illegal_move", "position_changed", "engine_error", "game_ended", "pending",
    or the default "move_rejected" for call sites that don't specialize it.
    """

    def __init__(self, message: str = "", reason: str = "move_rejected"):
        super().__init__(message)
        self.reason = reason


def _check_moves_legal_sequence(game, moves) -> None:
    """Raise IllegalMoveException if applying `moves` IN ORDER to game's CURRENT
    position would be illegal at any step, WITHOUT mutating the tree.

    KaTrain core (katrain/core/game.py) has no public non-mutating legality check —
    Game.play() commits the move as a side effect (creates/advances a GameNode).
    Reimplementing Go's chain/ko/suicide rules a second time here would be a
    correctness liability (two implementations to keep in sync); instead this
    reuses the real validator (Game._validate_move_and_update_chains) against a
    deep-copied snapshot of the board/chains state, then restores the originals
    unconditionally. That validator only touches game.board/chains/last_capture/
    prisoners (never the node tree), so the swap is confined to those four
    attributes and is invisible once this function returns.

    A sequence (rather than a single move) lets a caller validate move N against
    the position that would result from moves 1..N-1 already having landed — used
    to re-check the engine's genmove reply against the position AFTER the human's
    move, since the two are applied atomically as a pair.

    The swapped attributes (board/chains/last_capture/prisoners) are the ones
    `Game` itself normally guards with `game._lock`, not `session.lock` — this
    function does not take `game._lock`. It is safe anyway because callers MUST
    hold `session.lock` for the duration of this call (single-threaded per session
    by convention, for node-tree consistency), which also serializes out every
    other Game method call for this session, so no concurrent read can observe
    the transient swapped-in copies.
    """
    from katrain.core.game import IllegalMoveException

    board_size_x, board_size_y = game.board_size
    saved_board, saved_chains = game.board, game.chains
    saved_last_capture, saved_prisoners = list(game.last_capture), list(game.prisoners)
    game.board = copy.deepcopy(game.board)
    game.chains = copy.deepcopy(game.chains)
    try:
        for move in moves:
            if not move.is_pass and not (0 <= move.coords[0] < board_size_x and 0 <= move.coords[1] < board_size_y):
                raise IllegalMoveException(f"Move {move} outside of board coordinates")
            game._validate_move_and_update_chains(move, ignore_ko=False)
    finally:
        game.board, game.chains = saved_board, saved_chains
        game.last_capture, game.prisoners = saved_last_capture, saved_prisoners


def _check_move_legal(game, move) -> None:
    """Raise IllegalMoveException if `move` is illegal on game's CURRENT position,
    WITHOUT mutating the tree. See `_check_moves_legal_sequence` for the mechanics."""
    _check_moves_legal_sequence(game, [move])


def _submitted_position_status(session, game, node) -> str:
    """Return whether a tunnel reply still belongs to its submitted position.

    The caller must hold ``session.lock``. ``game`` and ``node`` are the actual
    objects captured before the tunnel request, keeping identity checks stable.
    """
    current = session.katrain.game
    if current is not game:
        return "game_replaced"
    if current.current_node is not node:
        return "position_changed"
    if current.end_result:
        return "ended"
    return "live"


def is_platform_engine_session(session) -> bool:
    """Return whether this session was created as a platform engine game.

    ``platform_engine_color`` survives removal of the active platform context
    and is cleared when a new game replaces this one. Only literal colours are
    accepted so mock objects and similarly shaped human games do not match.
    """
    return getattr(getattr(session, "katrain", None), "platform_engine_color", None) in ("B", "W")


class PlatformCommandGateway:
    """Intercepts game commands for platform-backed sessions.

    For platform games: submit to remote platform -> wait for ACK -> apply locally.
    For local games: pass through to KaTrain directly (existing behavior).
    """

    def __init__(self, platform_manager: PlatformManager, session_manager):
        self._pm = platform_manager
        self._sm = session_manager

    def is_platform_game(self, session_id: str) -> bool:
        return self._pm.is_platform_game(session_id)

    def is_engine_game(self, session_id: str) -> bool:
        """True for any engine-play (Golaxy 人机对弈 genmove-tunnel) session, pending or not.

        Used by /api/ai-move's unconditional guard: that endpoint bypasses the tunnel
        and triggers local KataGo directly, which is never valid for an engine game.
        """
        ctx = self._pm.get_game_context(session_id)
        return bool(ctx and ctx.is_engine)

    def get_game_id(self, session_id: str) -> Optional[str]:
        """Remote game id for a platform/engine-backed session, else None.

        Used as the engine_recovery episode key's game_id (Task 7) — the poller
        needs it to detect a game-id change (new game -> discard the old episode)
        without reaching into PlatformManager internals itself."""
        ctx = self._pm.get_game_context(session_id)
        return ctx.remote_game_id if ctx else None

    def is_engine_move_pending(self, session_id: str) -> bool:
        """True while an engine-play move is in flight (genmove tunnel, up to ~180s).

        Used by server.py's undo/redo/nav-family guards (409 while pending) — see the
        endpoint inventory in superpowers/tracks/kiosk-golaxy-physical-play/plan.md
        (基线记录) for the full set of tree-mutation entry points and which ones are
        (and are NOT) guarded this iteration.
        """
        ctx = self._pm.get_game_context(session_id)
        return bool(ctx and ctx.is_engine and ctx.is_pending)

    def _is_ended_engine_game(self, session_id: str) -> bool:
        """Detect an engine game whose terminal event removed its platform context."""
        try:
            session = self._sm.get_session(session_id)
        except KeyError:
            return False
        return is_platform_engine_session(session)

    def _is_unmapped_online_game(self, session_id: str) -> bool:
        try:
            return getattr(self._sm.get_session(session_id), "game_type", None) == "pvp_online"
        except KeyError:
            return False

    async def play_move(self, session_id: str, col: int, row: int, user_id: int) -> dict:
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            if self._is_ended_engine_game(session_id) or self._is_unmapped_online_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_play(session_id, col, row)

        if ctx.is_pending:
            raise PlatformMoveRejectedError("Previous move still pending", reason="pending")

        if ctx.is_engine:
            return await self._play_engine_move(session_id, ctx, col, row)
        if ctx.platform == "ogs":
            return await self._play_ogs_action(session_id, ctx, (col, row), user_id)

        # Platform game — remote first
        ctx.set_pending("move")
        self._broadcast_pending(session_id, col, row)

        adapter = self._pm.get_adapter(ctx.platform)
        try:
            success = await adapter.submit_move(ctx.remote_game_id, col, row)
        except Exception as e:
            logger.error(f"Platform move submission failed: {e}")
            ctx.clear_pending()
            self._broadcast_rejected(session_id, str(e))
            raise PlatformMoveRejectedError(str(e))

        if success:
            ctx.clear_pending()
            ctx.last_confirmed_move += 1
            result = self._local_play(session_id, col, row)
            self._broadcast_confirmed(session_id, col, row, ctx.last_confirmed_move)
            return result
        else:
            ctx.clear_pending()
            self._broadcast_rejected(session_id, "move_rejected")
            raise PlatformMoveRejectedError("Platform rejected the move")

    async def _play_ogs_action(
        self, session_id: str, ctx: PlatformGameContext, coords: Optional[tuple[int, int]], user_id: int
    ) -> dict:
        """Send once, then accept only an exact OGS echo or reconciled snapshot."""
        from katrain.core.game import IllegalMoveException
        from katrain.core.sgf_parser import Move

        session = self._sm.get_session(session_id)
        adapter = self._pm.get_adapter("ogs")
        if adapter is None or not getattr(adapter, "is_connected", True):
            raise PlatformMoveRejectedError("OGS connection unavailable", reason="engine_error")
        with session.lock:
            game = session.katrain.game
            if ctx.is_pending:
                raise PlatformMoveRejectedError("Previous move still pending", reason="pending")
            if ctx.needs_resync:
                raise PlatformMoveRejectedError("OGS position requires reconciliation", reason="position_changed")
            # KaTrain derives end_result after two passes even when OGS enters
            # stone removal and later resumes play. Only OGS's finished phase
            # or a committed remote terminal may close this online game.
            if ctx.game_phase != GamePhase.PLAYING or getattr(game, "terminal", None) is not None:
                raise PlatformMoveRejectedError("OGS game is not accepting moves", reason="game_ended")
            if user_id not in (0, session.user_id):
                raise PlatformMoveRejectedError("Not this game's owner", reason="move_rejected")
            if game.current_node.next_player != ctx.my_color:
                raise PlatformMoveRejectedError("Not your turn", reason="move_rejected")
            try:
                _check_move_legal(game, Move(coords=coords, player=ctx.my_color))
            except IllegalMoveException as exc:
                raise PlatformMoveRejectedError(str(exc), reason="illegal_move") from exc
            expected_number = ctx.last_confirmed_move + 1
            submitted_node = game.current_node
            ctx.set_pending("pass" if coords is None else "move")
            ctx.pending_coords = (-1, -1) if coords is None else coords

        if coords is not None:
            self._broadcast_pending(session_id, *coords)

        send_error = None
        try:
            if coords is None:
                sent = await adapter.submit_pass(ctx.remote_game_id)
            else:
                sent = await adapter.submit_move(ctx.remote_game_id, *coords)
            if not sent:
                send_error = "OGS move was not sent"
            else:
                try:
                    await asyncio.wait_for(ctx.pending_confirmation.wait(), timeout=PLATFORM_ACK_TIMEOUT)
                except asyncio.TimeoutError:
                    pass
        except Exception as exc:
            send_error = str(exc)

        def exact_remote_move() -> bool:
            try:
                snapshot = adapter.get_game_snapshot(ctx.remote_game_id)
            except (RuntimeError, AttributeError):
                return False
            if snapshot.game_id != ctx.remote_game_id or len(snapshot.moves) < expected_number:
                return False
            move = snapshot.moves[expected_number - 1]
            expected_coords = (-1, -1) if coords is None else coords
            return (
                move.game_id == ctx.remote_game_id
                and move.move_number == expected_number
                and move.color == ctx.my_color
                and (move.col, move.row) == expected_coords
            )

        def locally_confirmed() -> bool:
            with session.lock:
                return (
                    ctx.last_confirmed_move >= expected_number
                    and session.katrain.game.current_node is not submitted_node
                )

        confirmed = exact_remote_move() and locally_confirmed()
        if not confirmed:
            # A send failure can happen after bytes reached OGS. Reconcile once;
            # never issue a second game/move from this request.
            try:
                await adapter.fetch_game_snapshot(ctx.remote_game_id)
            except Exception as exc:
                logger.warning("OGS move reconciliation failed for %s: %s", ctx.remote_game_id, exc)
            confirmed = exact_remote_move() and locally_confirmed()

        if confirmed:
            if ctx.is_pending:
                ctx.clear_pending()
            return {"status": "ok"}

        # Keep uncertain sends pending. A delayed OGS echo may still arrive,
        # and a second physical detection must not silently send the move again.
        ctx.needs_resync = True
        reason = "position_changed" if ctx.last_confirmed_move >= expected_number else "engine_error"
        self._broadcast_rejected(session_id, reason)
        raise PlatformMoveRejectedError(send_error or "OGS did not confirm this move", reason=reason)

    async def _play_engine_move(self, session_id: str, ctx, col: int, row: int) -> dict:
        return await self._play_engine_turn(session_id, ctx, (col, row))

    async def _play_engine_pass(self, session_id: str, ctx) -> dict:
        return await self._play_engine_turn(session_id, ctx, None)

    async def _play_engine_turn(self, session_id: str, ctx, human_coords: Optional[tuple[int, int]]) -> dict:
        from katrain.core.game import IllegalMoveException
        from katrain.core.sgf_parser import Move
        from katrain.web.platforms.golaxy.adapter import GolaxyEngineTerminal

        session = self._sm.get_session(session_id)

        # B1: pre-validate the human's move locally (occupied/ko/suicide) BEFORE
        # spending a ~180s tunnel call on a move that can never land. Also record
        # the game and its current node as the submitted position. Both apply
        # paths re-check them so a mutation, new game, or resign that races the
        # tunnel wait cannot receive the late reply.
        with session.lock:
            game = session.katrain.game
            move = Move(coords=human_coords, player=session.katrain.next_player_info.player)
            try:
                _check_move_legal(game, move)
            except IllegalMoveException as e:
                self._broadcast_rejected(session_id, "illegal_move")
                raise PlatformMoveRejectedError(str(e), reason="illegal_move")
            submitted_game, submitted_node = game, game.current_node

            # B3/G4: resync the adapter's stateless move history to the CURRENT
            # node's path BEFORE spending a ~180s tunnel call -- an undo/branch
            # navigation since the last commit would otherwise send the AI a
            # stale or outright wrong history. Any encoding failure must reject
            # here, before pending state is set, so there is no half-commit.
            try:
                self._pm.rebuild_engine_context(session_id)
            except Exception as e:
                logger.error(f"Engine move history rebuild failed for session {session_id}: {e}")
                self._broadcast_rejected(session_id, "engine_error")
                raise PlatformMoveRejectedError(str(e), reason="engine_error")

        ctx.set_pending("pass" if human_coords is None else "move")
        if human_coords is not None:
            self._broadcast_pending(session_id, human_coords[0], human_coords[1])
        adapter = self._pm.get_adapter(ctx.platform)

        try:
            if human_coords is None:
                ai_reply = await adapter.submit_engine_pass(ctx.remote_game_id)
            else:
                ai_reply = await adapter.submit_engine_move(ctx.remote_game_id, human_coords[0], human_coords[1])
        except GolaxyEngineTerminal as e:
            # D7: the human's move is real and final (the adapter committed it on its
            # side before raising) — play it locally BEFORE the terminal/game_ended
            # broadcast, so the local record doesn't miss the actual last move. The
            # Known pass/resign values have typed replies; this branch is reserved
            # for an unknown sentinel, so the local game ends Void.
            try:
                with session.lock:
                    status = _submitted_position_status(session, submitted_game, submitted_node)
                    if status == "live":
                        session.katrain("play", coords=human_coords)
                        session.katrain("end_without_result")
                    else:
                        logger.warning(
                            f"Engine terminal for session {session_id}: game {status} during tunnel wait, "
                            "leaving the local game untouched"
                        )
            finally:
                ctx.clear_pending()
            if status == "game_replaced":
                await self._pm.end_platform_game(ctx.remote_game_id, "game_replaced")
            elif status == "live":
                await self._pm.end_platform_game(ctx.remote_game_id, "Void")
            if status in ("game_replaced", "position_changed"):
                self._broadcast_rejected(session_id, "position_changed")
                raise PlatformMoveRejectedError(
                    "Position changed while waiting for the engine reply", reason="position_changed"
                )
            self._broadcast_rejected(session_id, "game_ended")
            raise PlatformMoveRejectedError(str(e), reason="game_ended")
        except Exception as e:
            logger.error(f"Engine move failed: {e}")
            ctx.clear_pending()
            with session.lock:
                status = _submitted_position_status(session, submitted_game, submitted_node)
            if status == "ended":
                self._broadcast_rejected(session_id, "game_ended")
                raise PlatformMoveRejectedError("Game ended while waiting for the engine reply", reason="game_ended")
            if status == "game_replaced":
                await self._pm.end_platform_game(ctx.remote_game_id, "game_replaced")
            if status in ("game_replaced", "position_changed"):
                self._broadcast_rejected(session_id, "position_changed")
                raise PlatformMoveRejectedError(
                    "Position changed while waiting for the engine reply", reason="position_changed"
                )
            self._broadcast_rejected(session_id, "engine_error")
            raise PlatformMoveRejectedError(str(e), reason="engine_error")

        # Success: atomically apply the human action and the typed AI reply under a
        # single lock hold, gated on the submitted position.
        terminal_result = None
        try:
            with session.lock:
                status = _submitted_position_status(session, submitted_game, submitted_node)
                if status == "ended":
                    self._broadcast_rejected(session_id, "game_ended")
                    raise PlatformMoveRejectedError(
                        "Game ended while waiting for the engine reply", reason="game_ended"
                    )
                if status in ("game_replaced", "position_changed"):
                    self._broadcast_rejected(session_id, "position_changed")
                    raise PlatformMoveRejectedError(
                        "Position changed while waiting for the engine reply", reason="position_changed"
                    )

                if isinstance(ai_reply, PlatformMove):
                    # Revalidate the returned point against the position after the
                    # human action; WebKaTrain logs illegal plays instead of raising.
                    ai_move_obj = Move(coords=(ai_reply.col, ai_reply.row), player=ai_reply.color)
                    try:
                        _check_moves_legal_sequence(session.katrain.game, [move, ai_move_obj])
                    except IllegalMoveException as e:
                        logger.error(
                            f"Engine returned an illegal move ({ai_reply.col},{ai_reply.row}) for "
                            f"session {session_id}: {e}"
                        )
                        self._broadcast_rejected(session_id, "engine_error")
                        raise PlatformMoveRejectedError(
                            f"Engine returned an illegal move at ({ai_reply.col}, {ai_reply.row})",
                            reason="engine_error",
                        )

                session.katrain("play", coords=human_coords)
                if isinstance(ai_reply, PlatformMove):
                    human_move_number = ai_reply.move_number - 1
                    session.katrain("play", coords=(ai_reply.col, ai_reply.row))
                elif isinstance(ai_reply, PlatformPass):
                    human_move_number = ai_reply.move_number - 1
                    session.katrain("play", coords=None)
                    terminal_result = session.katrain.game.end_result
                elif isinstance(ai_reply, PlatformResign):
                    human_move_number = ai_reply.move_number
                    session.katrain("end_by_resignation", winner=ai_reply.winner)
                    terminal_result = session.katrain.game.end_result
                else:
                    raise PlatformMoveRejectedError("Unknown engine reply", reason="engine_error")
        except PlatformMoveRejectedError:
            if status == "game_replaced":
                await self._pm.end_platform_game(ctx.remote_game_id, "game_replaced")
            raise
        finally:
            ctx.clear_pending()

        if human_coords is not None:
            self._broadcast_confirmed(session_id, human_coords[0], human_coords[1], human_move_number)
        ctx.last_confirmed_move = ai_reply.move_number

        if isinstance(ai_reply, PlatformMove):
            self._broadcast_confirmed(session_id, ai_reply.col, ai_reply.row, ai_reply.move_number)
            return {
                "status": "ok",
                "ai_move": {"col": ai_reply.col, "row": ai_reply.row, "move_number": ai_reply.move_number},
            }

        if isinstance(ai_reply, PlatformPass) and not terminal_result:
            return {"status": "ok", "ai_move": {"pass": True, "move_number": ai_reply.move_number}}

        result = terminal_result or (f"{ai_reply.winner}+R" if isinstance(ai_reply, PlatformResign) else "game_end")
        await self._pm.end_platform_game(ctx.remote_game_id, result)
        self._broadcast_rejected(session_id, "game_ended")
        raise PlatformMoveRejectedError("Engine game ended", reason="game_ended")

    async def pass_move(self, session_id: str, user_id: int) -> dict:
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            if self._is_ended_engine_game(session_id) or self._is_unmapped_online_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_pass(session_id)

        if ctx.is_pending:
            raise PlatformMoveRejectedError("Previous action still pending", reason="pending")

        if ctx.is_engine:
            return await self._play_engine_pass(session_id, ctx)
        if ctx.platform == "ogs":
            return await self._play_ogs_action(session_id, ctx, None, user_id)

        ctx.set_pending("pass")
        adapter = self._pm.get_adapter(ctx.platform)
        try:
            success = await adapter.submit_pass(ctx.remote_game_id)
        except Exception as e:
            ctx.clear_pending()
            raise PlatformMoveRejectedError(str(e))

        if success:
            ctx.clear_pending()
            return self._local_pass(session_id)
        else:
            ctx.clear_pending()
            raise PlatformMoveRejectedError("Platform rejected pass")

    async def resign(self, session_id: str, user_id: int) -> dict:
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            if self._is_ended_engine_game(session_id) or self._is_unmapped_online_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_resign(session_id)

        if ctx.is_engine:
            adapter = self._pm.get_adapter(ctx.platform)
            await adapter.resign_engine_game(ctx.remote_game_id)
            return self._local_resign(session_id)

        if ctx.platform == "ogs":
            session = self._sm.get_session(session_id)
            if user_id != session.user_id or ctx.game_phase == GamePhase.FINISHED:
                raise PlatformMoveRejectedError("OGS game is not available", reason="game_ended")
            if ctx.is_pending:
                raise PlatformMoveRejectedError("Previous action still pending", reason="pending")
            adapter = self._pm.get_adapter("ogs")
            if adapter is None or not getattr(adapter, "is_connected", True):
                raise PlatformMoveRejectedError("OGS connection unavailable", reason="engine_error")
            ctx.set_pending("resign")
            try:
                await adapter.resign(ctx.remote_game_id)
            except Exception as exc:
                ctx.clear_pending()
                raise PlatformMoveRejectedError(str(exc), reason="engine_error") from exc
            return {"status": "pending"}

        ctx.set_pending("resign")
        adapter = self._pm.get_adapter(ctx.platform)
        try:
            await adapter.resign(ctx.remote_game_id)
        except Exception as e:
            ctx.clear_pending()
            raise PlatformMoveRejectedError(str(e))

        ctx.clear_pending()
        return self._local_resign(session_id)

    async def request_count(self, session_id: str, user_id: int) -> dict:
        """Route to platform scoring phase if supported."""
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            # Local game — use existing count logic
            return {"status": "local_count"}

        adapter = self._pm.get_adapter(ctx.platform)
        if adapter.supports_scoring:
            # Platform handles scoring; relay to adapter
            await adapter.submit_scoring_action(ctx.remote_game_id, {"action": "request_count"})
            return {"status": "platform_scoring_requested"}
        return {"status": "scoring_not_supported"}

    async def scoring_action(self, session_id: str, user_id: int, action: str, stones: str = "") -> dict:
        """Relay an OGS stone-removal decision; OGS alone supplies the result."""
        ctx = self._pm.get_game_context(session_id)
        if ctx is None or ctx.platform != "ogs" or ctx.game_phase != GamePhase.SCORING:
            raise PlatformMoveRejectedError("OGS is not in scoring phase", reason="move_rejected")
        session = self._sm.get_session(session_id)
        if user_id != session.user_id:
            raise PlatformMoveRejectedError("Not this game's owner", reason="move_rejected")
        if action not in ("accept", "reject") or ctx.is_pending:
            raise PlatformMoveRejectedError("Invalid or pending scoring action", reason="pending")
        adapter = self._pm.get_adapter("ogs")
        if adapter is None or not getattr(adapter, "is_connected", True):
            raise PlatformMoveRejectedError("OGS connection unavailable", reason="engine_error")
        payload = {"action": action}
        if action == "accept":
            payload["stones"] = stones
        ctx.set_pending(f"score_{action}")
        try:
            sent = await adapter.submit_scoring_action(ctx.remote_game_id, payload)
        except Exception as exc:
            ctx.clear_pending()
            raise PlatformMoveRejectedError(str(exc), reason="engine_error") from exc
        if not sent:
            ctx.clear_pending()
            raise PlatformMoveRejectedError("OGS scoring action was not sent", reason="engine_error")
        return {"status": "pending"}

    # --- Local passthrough ---

    def _local_play(self, session_id: str, col: int, row: int) -> dict:
        session = self._sm.get_session(session_id)
        session.katrain("play", coords=(col, row))
        return {"status": "ok"}

    def _local_pass(self, session_id: str) -> dict:
        session = self._sm.get_session(session_id)
        session.katrain("play", coords=None)
        return {"status": "ok"}

    def _local_resign(self, session_id: str) -> dict:
        session = self._sm.get_session(session_id)
        session.katrain("resign")
        return {"status": "ok"}

    # --- Broadcast helpers ---

    def _broadcast_pending(self, session_id: str, col: int, row: int) -> None:
        self._sm.broadcast_to_session(session_id, {"type": "platform_move_pending", "col": col, "row": row})

    def _broadcast_confirmed(self, session_id: str, col: int, row: int, move_number: int) -> None:
        self._sm.broadcast_to_session(
            session_id, {"type": "platform_move_confirmed", "col": col, "row": row, "move_number": move_number}
        )

    def _broadcast_rejected(self, session_id: str, reason: str) -> None:
        self._sm.broadcast_to_session(session_id, {"type": "platform_move_rejected", "reason": reason})
