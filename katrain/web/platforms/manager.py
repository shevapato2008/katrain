"""Platform Manager — orchestrates all platform adapters and bridges them to KaTrain sessions."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from katrain.web.platforms.base import PlatformAdapter
from katrain.web.platforms.credentials import PlatformCredentialStore
from katrain.web.platforms.models import (
    ClockState,
    GamePhase,
    PlatformCredentials,
    PlatformGameContext,
    PlatformGameSession,
    PlatformMove,
    PlatformPass,
    PlatformResign,
)

logger = logging.getLogger("katrain_web")


class PlatformBusyError(Exception):
    """Raised by `connect_platform` when a DIFFERENT user tries to log into a
    platform that's currently connected and owned by someone else. The box
    has one adapter per platform, shared by whoever is using it — a silent
    takeover would disconnect the previous owner's live game without warning.
    The caller (endpoint layer) maps this to HTTP 409 with an actionable
    message: go disconnect the other account first."""

    def __init__(self, platform: str, owner_user_id: int):
        self.platform = platform
        self.owner_user_id = owner_user_id
        super().__init__(f"{platform} is connected by another user ({owner_user_id})")


class PlatformOwnershipError(Exception):
    """Raised by `disconnect_platform` when a user who doesn't own the
    connection tries to tear it down. The caller maps this to HTTP 403."""

    def __init__(self, platform: str):
        self.platform = platform
        super().__init__(f"{platform} is not owned by this user")


class PlatformManager:
    """Singleton managing all platform connections for a user.

    Bridges platform games to KaTrain sessions: opponent moves from the platform
    are injected into the local game, and vision/touch moves are submitted to the platform.
    """

    def __init__(self, session_manager, credential_store: Optional[PlatformCredentialStore] = None):
        self._session_manager = session_manager
        self._credential_store = credential_store or PlatformCredentialStore()
        self._adapters: dict[str, PlatformAdapter] = {}
        self._active_games: dict[str, PlatformGameContext] = {}  # game_id -> context
        self._session_to_game: dict[str, str] = {}  # session_id -> game_id
        self._platform_user_ids: dict[str, int] = {}  # platform -> owning user_id
        self._locks: dict[str, asyncio.Lock] = {}  # platform -> serializes connect/disconnect
        self._callbacks_wired: set[str] = set()  # platforms whose adapter callbacks are wired
        # platform -> user_id currently in the middle of connect(); lets
        # _on_token_refreshed attribute a mid-login refresh to the right
        # person even before `_platform_user_ids` is updated (see below).
        self._pending_owner: dict[str, int] = {}

    # --- Adapter registry ---

    def register_adapter(self, adapter: PlatformAdapter) -> None:
        """Register a platform adapter (call at startup for each supported platform)."""
        self._adapters[adapter.platform_name] = adapter

    def get_adapter(self, platform: str) -> Optional[PlatformAdapter]:
        return self._adapters.get(platform)

    def list_platforms(self, user_id: Optional[int] = None) -> list[dict]:
        """List all registered platforms with connection status.

        `user_id=None` (internal/legacy callers) returns the adapter's raw
        `is_connected` — unfiltered, for admin/diagnostic use only. The HTTP
        `/status` endpoint always passes the caller's `user_id`: on a shared
        box, "connected" must mean "connected AS YOU", not "connected as
        whoever is currently holding the one global adapter".
        """
        return [
            {
                "platform": name,
                "connected": (
                    adapter.is_connected
                    if user_id is None
                    else (adapter.is_connected and self._platform_user_ids.get(name) == user_id)
                ),
                "supports_live_play": adapter.supports_live_play,
                "supports_automatch": adapter.supports_automatch,
                "supports_rooms": adapter.supports_rooms,
                "supports_seek_graph": adapter.supports_seek_graph,
                "supports_engine_play": adapter.supports_engine_play,
            }
            for name, adapter in self._adapters.items()
        ]

    def owner_of(self, platform: str) -> Optional[int]:
        """The user_id currently holding this platform's connection, or None."""
        return self._platform_user_ids.get(platform)

    # --- Connection lifecycle ---

    async def connect_platform(self, platform: str, credentials: PlatformCredentials, user_id: int) -> bool:
        """Connect to a platform as `user_id`. Saves credentials on success.

        The box has ONE adapter per platform, shared by whoever is using it.
        Raises `PlatformBusyError` if a DIFFERENT user currently owns the
        connection — checked and raised BEFORE `adapter.connect()` is ever
        called, and while holding this platform's lock, so a concurrent
        second login can't interleave with this one and silently take over
        a previous owner's live session.
        """
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise ValueError(f"Unknown platform: {platform}")
        lock = self._locks.setdefault(platform, asyncio.Lock())
        async with lock:
            owner = self._platform_user_ids.get(platform)
            if owner is not None and owner != user_id and adapter.is_connected:
                raise PlatformBusyError(platform, owner)

            # Callbacks are wired exactly once per platform (not once per
            # connect) — otherwise every reconnect adds another copy of every
            # handler and a single token refresh gets persisted N times.
            if platform not in self._callbacks_wired:
                self._setup_callbacks(adapter)
                self._callbacks_wired.add(platform)

            # Pin the owner for THIS connection attempt before awaiting
            # adapter.connect(): a token_refreshed event fired mid-login must
            # be attributed to the user who is CURRENTLY logging in, not to
            # whatever `_platform_user_ids` happened to hold a moment ago
            # (which, in this same call, is the PREVIOUS owner).
            self._pending_owner[platform] = user_id
            try:
                success = await adapter.connect(credentials)
            finally:
                self._pending_owner.pop(platform, None)

            if success:
                self._platform_user_ids[platform] = user_id
                # Persist the RESULTING tokens, not the transient login secret. SMS/OAuth
                # login exchanges a one-time sms_code for access/refresh tokens that live
                # only in the adapter; saving the raw input credentials would store just the
                # (now-consumed) sms_code, forcing a fresh SMS login on every restart.
                # Adapters that expose get_auth_data() (Golaxy) get their tokens merged in;
                # others (OGS) fall back to the input credentials unchanged.
                auth_to_save = dict(credentials.auth_data)
                get_auth = getattr(adapter, "get_auth_data", None)
                if callable(get_auth):
                    auth_to_save.update({k: v for k, v in (get_auth() or {}).items() if v})
                self._credential_store.save_credentials(
                    user_id,
                    PlatformCredentials(platform=platform, username=credentials.username, auth_data=auth_to_save),
                )
                logger.info(f"Connected to {platform} as {credentials.username}")
            return success

    async def disconnect_platform(self, platform: str, user_id: int) -> None:
        """Disconnect `platform`, but only on behalf of the user who owns it.

        Raises `PlatformOwnershipError` if a different user currently owns
        the connection. A platform nobody owns (`owner is None`) is a no-op
        for any caller — that's the "already disconnected" case, not a
        permission question.
        """
        lock = self._locks.setdefault(platform, asyncio.Lock())
        async with lock:
            owner = self._platform_user_ids.get(platform)
            if owner not in (None, user_id):
                raise PlatformOwnershipError(platform)
            adapter = self._adapters.get(platform)
            if adapter and adapter.is_connected:
                await adapter.disconnect()
                logger.info(f"Disconnected from {platform}")
            self._platform_user_ids.pop(platform, None)
            # Releasing OWNERSHIP is not the same as releasing the GAME
            # CONTEXTS bridged through this connection. Leaving
            # `_active_games`/`_session_to_game` populated after the owner is
            # gone means the NEXT person to connect this platform inherits
            # someone else's game: `require_platform_owner` only checks "is
            # the platform yours", never "is this game yours", so the new
            # owner's engine-analysis calls would spend THEIR metered
            # allowance on the PREVIOUS owner's game, and the previous
            # owner's still-open game screen would keep submitting moves
            # through the NEW owner's token. Ending the game here closes both
            # directions.
            #
            # Trade-off, stated plainly: this ABANDONS any game that is still
            # in progress at the moment the platform changes hands (box
            # logout, box-SSO generation replaced, explicit disconnect).
            # There is no "hand the live game to the next local user" option
            # on a shared box — the remote platform sees the connection drop
            # and applies whatever it does for a disconnected opponent
            # (typically a timeout/forfeit on ITS side, outside our control).
            # We chose "always end" over "add a per-game user_id and only end
            # games the departing user doesn't still own" because a shared
            # box has exactly one adapter per platform: once the OWNER
            # changes, nobody left holding that adapter can safely keep
            # talking to the remote game on the old owner's behalf anyway.
            stale_game_ids = [gid for gid, ctx in self._active_games.items() if ctx.platform == platform]
            for game_id in stale_game_ids:
                await self.end_platform_game(game_id, "platform_released")

    async def release_user(self, user_id: int) -> None:
        """Release every platform this user currently owns, WITHOUT touching
        their saved credentials — this is the "box changed hands" path (a
        different local account logged in/out), not an explicit "forget my
        {platform} account" action. See `disconnect_platform` for the
        credential-deleting path (driven separately by the endpoint layer).

        Not clearing ownership here means: the next user to log into this box
        would hit `PlatformBusyError` trying to connect a platform the
        PREVIOUS box user was using, with no way to tell why — this closes
        that gap.
        """
        for platform, owner in list(self._platform_user_ids.items()):
            if owner == user_id:
                await self.disconnect_platform(platform, user_id)

    def list_connected_platforms(self) -> list[str]:
        return [name for name, a in self._adapters.items() if a.is_connected]

    # --- Game context ---

    def get_game_context(self, session_id: str) -> Optional[PlatformGameContext]:
        game_id = self._session_to_game.get(session_id)
        if game_id is None:
            return None
        return self._active_games.get(game_id)

    def is_platform_game(self, session_id: str) -> bool:
        return session_id in self._session_to_game

    # --- Bridge: platform game -> KaTrain session ---

    async def start_platform_game(self, platform: str, game_session: PlatformGameSession, user_id: int) -> str:
        """Creates a KaTrain session backed by a platform game. Returns session_id."""
        # Create a multiplayer session (local user vs virtual opponent)
        opponent_name = f"[{platform}] {game_session.opponent.username}"
        if game_session.my_color == "B":
            session = self._session_manager.create_multiplayer_session(
                player_b_id=user_id, player_w_id=-1, b_name="Me", w_name=opponent_name
            )
        else:
            session = self._session_manager.create_multiplayer_session(
                player_b_id=-1, player_w_id=user_id, b_name=opponent_name, w_name="Me"
            )

        ctx = PlatformGameContext(
            session_id=session.session_id,
            platform=platform,
            remote_game_id=game_session.game_id,
            my_color=game_session.my_color,
        )
        self._active_games[game_session.game_id] = ctx
        self._session_to_game[session.session_id] = game_session.game_id

        logger.info(f"Platform game started: {platform} game {game_session.game_id} -> session {session.session_id}")
        return session.session_id

    async def start_engine_game(self, platform: str, config, user_id: int) -> str:
        """Start a human-vs-engine game. Returns the local session_id.

        `config` is opaque here (an adapter-specific EngineGameConfig); the manager
        reads game parameters off the returned PlatformGameSession, not off config.
        """
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise ValueError(f"Unknown platform: {platform}")
        if not getattr(adapter, "supports_engine_play", False):
            raise ValueError(f"{platform} does not support engine play")

        start = await adapter.start_engine_game(config)
        gs = start.session
        bot_name = f"[{platform}] {gs.opponent.username}"
        if gs.my_color == "B":
            session = self._session_manager.create_multiplayer_session(
                player_b_id=user_id,
                player_w_id=-1,
                b_name="Me",
                w_name=bot_name,
                skip_initial_analysis=True,
            )
        else:
            session = self._session_manager.create_multiplayer_session(
                player_b_id=-1,
                player_w_id=user_id,
                b_name=bot_name,
                w_name="Me",
                skip_initial_analysis=True,
            )

        # Explicitly configure the local game to match the engine game parameters, and
        # mark which color is the remote engine (G1/G2 single source of truth): the
        # LED orchestrator and frontend read this off get_state() to know which side
        # is not physically playable by the human.
        ai_color = "W" if gs.my_color == "B" else "B"
        session.katrain(
            "edit_game",
            size=gs.board_size,
            handicap=gs.handicap,
            komi=gs.komi,
            rules=gs.rules,
            platform_engine_color=ai_color,
        )

        ctx = PlatformGameContext(
            session_id=session.session_id,
            platform=platform,
            remote_game_id=gs.game_id,
            my_color=gs.my_color,
            is_engine=True,
        )
        self._active_games[gs.game_id] = ctx
        self._session_to_game[session.session_id] = gs.game_id

        # If the AI was initially to move, mirror its typed reply locally.
        if start.first_ai_move is not None:
            m = start.first_ai_move
            ctx.last_confirmed_move = m.move_number
            if isinstance(m, PlatformMove):
                session.katrain("play", coords=(m.col, m.row))
                self._session_manager.broadcast_to_session(
                    session.session_id,
                    {"type": "platform_move_confirmed", "col": m.col, "row": m.row, "move_number": m.move_number},
                )
            elif isinstance(m, PlatformPass):
                session.katrain("play", coords=None)
            elif isinstance(m, PlatformResign):
                session.katrain("end_by_resignation", winner=m.winner)
                await self.end_platform_game(gs.game_id, "ai_resign")

        logger.info(f"Engine game started: {platform} {gs.game_id} -> session {session.session_id}")
        return session.session_id

    def rebuild_engine_context(self, session_id: str) -> list[Optional[tuple[int, int]]]:
        """Resync an engine-play adapter's stateless move history to the LOCAL
        game tree's CURRENT-NODE path (root -> current_node), NOT just the main
        line -- undo and branch navigation move `current_node` off whatever
        `ctx.moves` was last committed against, and the next genmove must see
        the history that matches where the tree actually is now (review B3/G4).

        Traversal mirrors hint.py's `_build_payload_from_game`: walk
        `game.current_node.nodes_from_root` and collect each node's `.moves`.
        Root-level handicap stones are ROOT SETUP placements (from
        `edit_game` -> `place_handicap_stones`), not move nodes, so they are
        NOT collected here -- the adapter re-derives the identical handicap
        prefix itself from `ctx.config.handicap` (see
        `GolaxyAdapter.rebuild_engine_moves`), matching how
        `start_engine_game` seeded `ctx.moves` in the first place.

        Pass nodes are encoded using Golaxy's live-captured -1 sentinel. Raises
        KeyError if session_id has no engine-play context.

        Returns the extracted (col, row)/None path (handicap-prefix-EXCLUSIVE)
        for callers/tests that want to inspect what was rebuilt.
        """
        ctx = self.get_game_context(session_id)
        if ctx is None or not ctx.is_engine:
            raise KeyError(session_id)
        session = self._session_manager.get_session(session_id)
        game = session.katrain.game
        nodes = game.current_node.nodes_from_root
        path: list[Optional[tuple[int, int]]] = []
        for node in nodes:
            for mv in node.moves:
                path.append(mv.coords)
        adapter = self._adapters.get(ctx.platform)
        if adapter is None:
            raise ValueError(f"Unknown platform: {ctx.platform}")
        adapter.rebuild_engine_moves(ctx.remote_game_id, path)
        return path

    async def engine_analysis(self, platform: str, session_id: str, kind: str):
        """Resolve the engine game behind session_id and run one analysis pull.

        Returns the adapter's AnalysisResult; QuotaExhausted/AuthExpired/etc.
        propagate to the caller unhandled (the endpoint layer decides how to
        map them to HTTP responses).

        Ownership is enforced at the ENDPOINT layer (`require_platform_owner`),
        not here. This used to be commented as needing no check because it's
        "read-only" — that reasoning doesn't hold: `session_id` resolves to a
        specific game inside `platform`'s connection, which on a shared box
        may belong to a DIFFERENT user than the caller. Read-only is not the
        same as no-owner; it still reads someone else's session.
        """
        game_id = self._session_to_game.get(session_id)
        if game_id is None:
            raise KeyError(session_id)
        ctx = self._active_games.get(game_id)
        if ctx is None or not getattr(ctx, "is_engine", False):
            raise KeyError(session_id)
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise ValueError(f"Unknown platform: {platform}")
        return await adapter.engine_analysis(game_id, kind)

    async def end_platform_game(self, game_id: str, result: str) -> None:
        """Clean up after a platform game ends."""
        ctx = self._active_games.pop(game_id, None)
        if ctx:
            # A late reply from an old game must not remove a newer game that has
            # already claimed the same local session.
            if self._session_to_game.get(ctx.session_id) == game_id:
                self._session_to_game.pop(ctx.session_id, None)
            if ctx.is_engine:
                adapter = self._adapters.get(ctx.platform)
                discard = getattr(adapter, "discard_engine_game", None)
                if discard is not None:
                    discard(game_id)
            ctx.game_phase = GamePhase.FINISHED
            logger.info(f"Platform game ended: {game_id} result={result}")

    # --- Callbacks ---

    def _setup_callbacks(self, adapter: PlatformAdapter) -> None:
        adapter.on_opponent_move(self._on_opponent_move)
        adapter.on_clock_update(self._on_clock_update)
        adapter.on_game_started(self._on_game_started)
        adapter.on_game_ended(self._on_game_ended)
        adapter.on_game_phase_changed(self._on_game_phase_changed)
        adapter.on_connection_lost(self._on_connection_lost)
        adapter.on_reconnected(self._on_reconnected)
        adapter.on_auth_expired(self._on_auth_expired)
        adapter.on_token_refreshed(lambda data, _p=adapter.platform_name: self._on_token_refreshed(_p, data))

    async def _on_opponent_move(self, move: PlatformMove) -> None:
        """Platform opponent played a move -> inject into the correct KaTrain game."""
        ctx = self._active_games.get(move.game_id)
        if ctx is None:
            logger.warning(f"Opponent move for unknown game_id={move.game_id!r}; dropping")
            return
        if ctx.game_phase != GamePhase.PLAYING:
            logger.warning(f"Opponent move for game {move.game_id} not in PLAYING phase; dropping")
            return
        try:
            session = self._session_manager.get_session(ctx.session_id)
            session.katrain("play", coords=(move.col, move.row))
            ctx.last_confirmed_move = move.move_number
            self._session_manager.broadcast_to_session(
                ctx.session_id,
                {
                    "type": "platform_move_confirmed",
                    "col": move.col,
                    "row": move.row,
                    "move_number": move.move_number,
                },
            )
        except KeyError:
            logger.warning(f"Session {ctx.session_id} not found for opponent move")

    async def _on_clock_update(self, clock: ClockState) -> None:
        for game_id, ctx in self._active_games.items():
            if ctx.game_phase in (GamePhase.PLAYING, GamePhase.PAUSED):
                ctx.remote_clock_version += 1
                self._session_manager.broadcast_to_session(
                    ctx.session_id,
                    {
                        "type": "clock_update",
                        "black_time": clock.black_time,
                        "white_time": clock.white_time,
                        "current_player": clock.current_player,
                        "paused": clock.paused,
                    },
                )
                break

    async def _on_game_started(self, game_session: PlatformGameSession) -> None:
        logger.info(f"Game started event from {game_session.platform}: {game_session.game_id}")

    async def _on_game_ended(self, game_id: str, result: str, winner: str) -> None:
        ctx = self._active_games.get(game_id)
        if ctx:
            self._session_manager.broadcast_to_session(
                ctx.session_id, {"type": "platform_game_ended", "game_id": game_id, "result": result, "winner": winner}
            )
            await self.end_platform_game(game_id, result)

    async def _on_game_phase_changed(self, game_id: str, phase: GamePhase) -> None:
        ctx = self._active_games.get(game_id)
        if ctx:
            ctx.game_phase = phase
            self._session_manager.broadcast_to_session(
                ctx.session_id, {"type": "platform_phase_changed", "phase": phase.value}
            )

    async def _on_connection_lost(self) -> None:
        logger.warning("Platform connection lost")

    async def _on_reconnected(self) -> None:
        logger.info("Platform reconnected")
        # Mark games that may have missed events
        for ctx in self._active_games.values():
            if ctx.game_phase == GamePhase.PLAYING:
                ctx.needs_resync = True

    async def _on_auth_expired(self) -> None:
        logger.warning("Platform auth expired")

    async def _on_token_refreshed(self, platform: str, new_auth_data: dict) -> None:
        # Mid-login (inside connect_platform's lock) the pending owner is the
        # user CURRENTLY logging in, not whatever `_platform_user_ids` holds
        # right now (which, during a takeover, is still the previous owner).
        # Once connect_platform finishes, `_pending_owner` is cleared and this
        # falls back to the settled owner for refreshes that happen later in
        # the session's lifetime.
        user_id = self._pending_owner.get(platform) or self._platform_user_ids.get(platform)
        if user_id is None:
            logger.debug(f"token_refreshed for {platform} but no known user; skipping persist")
            return
        existing = self._credential_store.load_credentials(user_id, platform)
        username = existing.username if existing else ""
        merged = dict(existing.auth_data) if existing else {}
        merged.update({k: v for k, v in new_auth_data.items() if v})
        self._credential_store.save_credentials(
            user_id, PlatformCredentials(platform=platform, username=username, auth_data=merged)
        )
        logger.debug(f"Persisted refreshed token for user {user_id} on {platform}")
