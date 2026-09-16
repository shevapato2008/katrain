"""Platform Command Gateway — intercepts game commands for platform-backed sessions.

For platform games: submit to remote platform -> wait for ACK -> apply locally.
For local games: pass through to KaTrain directly (existing behavior).
"""

from __future__ import annotations

import copy
import logging
import time
from typing import Optional

from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import PlatformGameContext

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

    async def play_move(self, session_id: str, col: int, row: int, user_id: int) -> dict:
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            if self._is_ended_engine_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_play(session_id, col, row)

        if ctx.is_pending:
            raise PlatformMoveRejectedError("Previous move still pending", reason="pending")

        if ctx.is_engine:
            return await self._play_engine_move(session_id, ctx, col, row)

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

    async def _play_engine_move(self, session_id: str, ctx, col: int, row: int) -> dict:
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
            move = Move(coords=(col, row), player=session.katrain.next_player_info.player)
            try:
                _check_move_legal(game, move)
            except IllegalMoveException as e:
                self._broadcast_rejected(session_id, "illegal_move")
                raise PlatformMoveRejectedError(str(e), reason="illegal_move")
            submitted_game, submitted_node = game, game.current_node

            # B3/G4: resync the adapter's stateless move history to the CURRENT
            # node's path BEFORE spending a ~180s tunnel call -- an undo/branch
            # navigation since the last commit would otherwise send the AI a
            # stale or outright wrong history. Failure (e.g. a pass found on the
            # path) must reject loudly here, before any pending state is set, so
            # there is no half-commit to unwind.
            try:
                self._pm.rebuild_engine_context(session_id)
            except Exception as e:
                logger.error(f"Engine move history rebuild failed for session {session_id}: {e}")
                self._broadcast_rejected(session_id, "engine_error")
                raise PlatformMoveRejectedError(str(e), reason="engine_error")

        ctx.set_pending("move")
        self._broadcast_pending(session_id, col, row)
        adapter = self._pm.get_adapter(ctx.platform)

        try:
            ai_move = await adapter.submit_engine_move(ctx.remote_game_id, col, row)
        except GolaxyEngineTerminal as e:
            # D7: the human's move is real and final (the adapter committed it on its
            # side before raising) — play it locally BEFORE the terminal/game_ended
            # broadcast, so the local record doesn't miss the actual last move. The
            # AI terminal is ambiguous (pass or resign), so the local game ends Void.
            try:
                with session.lock:
                    status = _submitted_position_status(session, submitted_game, submitted_node)
                    if status == "live":
                        self._local_play(session_id, col, row)
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

        # Success: atomic apply of [human, AI] under a single lock hold, gated on the
        # submitted position. Discard both moves when the position was replaced, and
        # preserve an existing result when the user resigned during the wait.
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

                # G6: re-validate the AI's OWN returned coordinate before committing
                # anything. `submit_engine_move` already committed it into the
                # stateless tunnel's ctx.moves unconditionally once genmove returned
                # an on-board coord, so an illegal reply (e.g. an already-occupied
                # point) can't be un-sent to the tunnel -- but it must not be allowed
                # to land locally: `WebKaTrain._do_play` (interface.py) only logs
                # IllegalMoveException instead of raising, so without this check the
                # human's move would silently commit while the AI's reply vanished,
                # desyncing the tunnel history from the local board with no signal
                # to the recovery machinery. Check the AI's move against the
                # position that results from the human move landing first (the
                # order they're about to be applied in).
                game = session.katrain.game
                ai_move_obj = Move(coords=(ai_move.col, ai_move.row), player=ai_move.color)
                try:
                    _check_moves_legal_sequence(game, [move, ai_move_obj])
                except IllegalMoveException as e:
                    logger.error(
                        f"Engine returned an illegal move ({ai_move.col},{ai_move.row}) for "
                        f"session {session_id}: {e}"
                    )
                    self._broadcast_rejected(session_id, "engine_error")
                    raise PlatformMoveRejectedError(
                        f"Engine returned an illegal move at ({ai_move.col}, {ai_move.row})",
                        reason="engine_error",
                    )

                self._local_play(session_id, col, row)
                human_move_number = ai_move.move_number - 1
                self._local_play(session_id, ai_move.col, ai_move.row)
        except PlatformMoveRejectedError:
            if status == "game_replaced":
                await self._pm.end_platform_game(ctx.remote_game_id, "game_replaced")
            raise
        finally:
            ctx.clear_pending()

        self._broadcast_confirmed(session_id, col, row, human_move_number)
        ctx.last_confirmed_move = ai_move.move_number
        self._broadcast_confirmed(session_id, ai_move.col, ai_move.row, ai_move.move_number)
        return {"status": "ok", "ai_move": {"col": ai_move.col, "row": ai_move.row, "move_number": ai_move.move_number}}

    async def pass_move(self, session_id: str, user_id: int) -> dict:
        ctx = self._pm.get_game_context(session_id)
        if ctx is None:
            if self._is_ended_engine_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_pass(session_id)

        if ctx.is_engine:
            raise PlatformMoveRejectedError("pass_not_supported")

        if ctx.is_pending:
            raise PlatformMoveRejectedError("Previous action still pending")

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
            if self._is_ended_engine_game(session_id):
                raise PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
            return self._local_resign(session_id)

        if ctx.is_engine:
            adapter = self._pm.get_adapter(ctx.platform)
            await adapter.resign_engine_game(ctx.remote_game_id)
            return self._local_resign(session_id)

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
