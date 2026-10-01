"""Platform Manager — orchestrates all platform adapters and bridges them to KaTrain sessions."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
import logging
import math
from typing import Optional

from katrain.web.platforms.base import PlatformAdapter
from katrain.web.platforms.credentials import PlatformCredentialStore
from katrain.web.platforms.models import (
    ClockState,
    GamePhase,
    PlatformCredentials,
    PlatformGameContext,
    PlatformGameSession,
    PlatformGameSnapshot,
    PlatformMove,
    PlatformPass,
    PlatformResign,
)

logger = logging.getLogger("katrain_web")
ONLINE_RECORD_RETRY_DELAYS = (0.5, 1.0, 2.0)


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
        # Wired by server after its game-recording helper is available.
        self.on_online_game_finished = None
        self._record_retry_tasks: dict[str, asyncio.Task] = {}

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

    def active_game_for_owner(self, platform: str, user_id: int) -> Optional[str]:
        """Return only this box user's verified unfinished platform session."""
        adapter = self._adapters.get(platform)
        if not adapter or not adapter.is_connected or self._platform_user_ids.get(platform) != user_id:
            return None
        for ctx in self._active_games.values():
            if ctx.platform != platform:
                continue
            try:
                session = self._session_manager.get_session(ctx.session_id)
            except KeyError:
                continue
            if session.user_id == user_id:
                return ctx.session_id
        return None

    async def recover_active_game_for_owner(self, platform: str, user_id: int) -> Optional[str]:
        """Recreate an expired local OGS session from the current remote board."""
        active = self.active_game_for_owner(platform, user_id)
        if active is not None or platform != "ogs":
            return active
        adapter = self._adapters.get("ogs")
        if not adapter or not adapter.is_connected or self._platform_user_ids.get("ogs") != user_id:
            return None
        for ctx in list(self._active_games.values()):
            if ctx.platform != "ogs":
                continue
            try:
                self._session_manager.get_session(ctx.session_id)
            except KeyError:
                remote_session = await adapter.refresh_game_session(ctx.remote_game_id)
                return await self.start_platform_game("ogs", remote_session, user_id)
        return None

    # --- Bridge: platform game -> KaTrain session ---

    async def start_platform_game(self, platform: str, game_session: PlatformGameSession, user_id: int) -> str:
        """Create one local online session for a verified remote game identity.

        Board history is not reconstructed here: callers must restore an OGS
        snapshot before exposing an already-running game to the user.
        """
        if game_session.platform != platform or not game_session.game_id:
            raise ValueError("invalid platform game identity")
        if type(game_session.board_size) is not int or game_session.board_size not in (9, 13, 19):
            raise ValueError("unsupported platform board size")
        if game_session.my_color not in ("B", "W"):
            raise ValueError("invalid platform player color")
        if game_session.rules not in ("chinese", "japanese", "korean", "aga"):
            raise ValueError("unsupported platform rules")
        if type(game_session.handicap) is not int or not 0 <= game_session.handicap <= 9:
            raise ValueError("unsupported platform handicap")
        if type(game_session.komi) not in (int, float) or not math.isfinite(game_session.komi):
            raise ValueError("invalid platform komi")

        lock = self._locks.setdefault(f"game:{platform}:{game_session.game_id}", asyncio.Lock())
        async with lock:
            return await self._start_platform_game_locked(platform, game_session, user_id)

    async def _start_platform_game_locked(self, platform: str, game_session: PlatformGameSession, user_id: int) -> str:
        adapter = self._adapters.get(platform)
        snapshot = None
        if platform == "ogs" and adapter is not None:
            snapshot = adapter.get_game_snapshot(game_session.game_id)
            if snapshot.board_size != game_session.board_size:
                raise ValueError("OGS snapshot does not match game settings")

        existing = self._active_games.get(game_session.game_id)
        if existing is not None:
            if existing.platform != platform:
                raise ValueError("remote game id belongs to a different platform")
            try:
                existing_session = self._session_manager.get_session(existing.session_id)
            except KeyError as exc:
                if snapshot is None:
                    raise RuntimeError("remote game needs verified snapshot recovery") from exc
                # The web session may have expired while OGS kept the game.
                # Its verified snapshot can seed a new local session.
                self._active_games.pop(game_session.game_id, None)
                if self._session_to_game.get(existing.session_id) == game_session.game_id:
                    self._session_to_game.pop(existing.session_id, None)
                retry = self._record_retry_tasks.pop(game_session.game_id, None)
                if retry is not None:
                    retry.cancel()
                existing = None
        if existing is not None:
            if existing_session.user_id != user_id:
                raise ValueError("remote game belongs to a different local user")
            if snapshot is not None and (existing.needs_resync or existing.last_confirmed_move != snapshot.move_number):
                self._restore_ogs_snapshot(existing_session, snapshot, game_session)
                existing.last_confirmed_move = snapshot.move_number
                existing.game_phase = snapshot.phase
                existing.needs_resync = False
            return existing.session_id

        # Create a multiplayer session (local user vs virtual opponent)
        opponent_name = f"[{platform}] {game_session.opponent.username}"
        if game_session.my_color == "B":
            session = self._session_manager.create_multiplayer_session(
                player_b_id=user_id,
                player_w_id=-1,
                b_name="Me",
                w_name=opponent_name,
                initial_game_type="pvp_online",
                skip_initial_analysis=True,
            )
        else:
            session = self._session_manager.create_multiplayer_session(
                player_b_id=-1,
                player_w_id=user_id,
                b_name=opponent_name,
                w_name="Me",
                initial_game_type="pvp_online",
                skip_initial_analysis=True,
            )

        try:
            session.katrain(
                "edit_game",
                size=game_session.board_size,
                rules=game_session.rules,
                handicap=game_session.handicap,
                komi=game_session.komi,
            )
            if snapshot is not None:
                self._restore_ogs_snapshot(session, snapshot, game_session)
            session.katrain.platform_my_color = game_session.my_color
        except Exception:
            self._session_manager.remove_session(session.session_id)
            raise

        ctx = PlatformGameContext(
            session_id=session.session_id,
            platform=platform,
            remote_game_id=game_session.game_id,
            my_color=game_session.my_color,
            remote_session=game_session,
        )
        self._active_games[game_session.game_id] = ctx
        if snapshot is not None:
            ctx.last_confirmed_move = snapshot.move_number
            ctx.game_phase = snapshot.phase
            session.katrain.platform_phase = snapshot.phase.value
        self._session_to_game[session.session_id] = game_session.game_id

        if snapshot is not None and snapshot.phase == GamePhase.FINISHED:
            # A finished snapshot may have arrived before this context was
            # registered. Re-read its result now so the terminal callback has
            # a session to commit and save; the adapter schedules retries if
            # the REST result is still incomplete.
            try:
                await adapter.fetch_game_snapshot(game_session.game_id)
            except Exception:
                logger.exception("OGS finished game result not yet available for %s", game_session.game_id)

        logger.info(f"Platform game started: {platform} game {game_session.game_id} -> session {session.session_id}")
        return session.session_id

    @staticmethod
    def _restore_ogs_snapshot(session, snapshot: PlatformGameSnapshot, game_session: PlatformGameSession) -> None:
        """Replace the local tree from OGS history, including real setup stones."""
        from katrain.core.game import KaTrainSGF

        def sgf_point(col: int, row: int) -> str:
            return chr(97 + col) + chr(97 + snapshot.board_size - row - 1)

        root = [f"(;GM[1]FF[4]SZ[{snapshot.board_size}]KM[{game_session.komi}]RU[{game_session.rules}]",
                f"HA[{game_session.handicap}]", "PL[W]" if game_session.handicap else "PL[B]"]
        for color, property_name in (("B", "AB"), ("W", "AW")):
            stones = [sgf_point(col, row) for c, col, row in snapshot.setup if c == color]
            if stones:
                root.append(property_name + "".join(f"[{point}]" for point in stones))
        for move in snapshot.moves:
            point = "" if move.col == -1 else sgf_point(move.col, move.row)
            root.append(f";{move.color}[{point}]")
        root.append(")")
        move_tree = KaTrainSGF.parse_sgf("".join(root))
        session.katrain(
            "new_game", move_tree=move_tree, size=snapshot.board_size, handicap=0,
            komi=game_session.komi, rules=game_session.rules,
            game_type="pvp_online", skip_initial_analysis=True,
        )
        game = getattr(session.katrain, "game", None)
        if game is not None:
            node = game.root
            while node.children:
                node = node.children[0]
            game.set_current_node(node)
            session.katrain.update_state()
        session.katrain.platform_my_color = game_session.my_color

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
        retry = self._record_retry_tasks.pop(game_id, None)
        if retry is not None and retry is not asyncio.current_task():
            retry.cancel()
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
        adapter.on_game_snapshot(self._on_game_snapshot)
        adapter.on_clock_update(self._on_clock_update)
        adapter.on_game_started(self._on_game_started)
        adapter.on_automatch_found(self._on_game_started)
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
        if ctx.platform == "ogs":
            if move.move_number <= ctx.last_confirmed_move:
                return
            if move.move_number != ctx.last_confirmed_move + 1 or move.color not in ("B", "W"):
                ctx.needs_resync = True
                ctx.pending_confirmation.set()
                return
            if move.color == ctx.my_color:
                expected = (-1, -1) if ctx.pending_action == "pass" else ctx.pending_coords
                if not ctx.is_pending or expected != (move.col, move.row):
                    ctx.needs_resync = True
                    ctx.pending_confirmation.set()
                    return
        try:
            session = self._session_manager.get_session(ctx.session_id)
            with getattr(session, "lock", nullcontext()):
                if ctx.platform == "ogs" and move.move_number != ctx.last_confirmed_move + 1:
                    return
                coords = None if move.col == -1 and move.row == -1 else (move.col, move.row)
                session.katrain("play", coords=coords)
                ctx.last_confirmed_move = move.move_number
                if ctx.platform == "ogs" and move.color == ctx.my_color:
                    ctx.clear_pending()
                    # A timed-out send may receive its exact echo later. That
                    # echo reconciles the position and unlocks the next turn.
                    ctx.needs_resync = False
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
            if clock.game_id and game_id != clock.game_id:
                continue
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

    async def _on_game_snapshot(self, game_id: str, snapshot: PlatformGameSnapshot) -> None:
        ctx = self._active_games.get(game_id)
        if ctx is None:
            # Initial gamedata is retained by the adapter until start_platform_game.
            return
        if ctx.platform != "ogs" or ctx.remote_session is None:
            return
        if snapshot.game_id != game_id or snapshot.board_size != ctx.remote_session.board_size:
            ctx.needs_resync = True
            return
        if ctx.game_phase == GamePhase.FINISHED and snapshot.phase != GamePhase.FINISHED:
            logger.warning("Ignoring OGS snapshot phase rollback after finish for %s", game_id)
            return
        try:
            session = self._session_manager.get_session(ctx.session_id)
        except KeyError:
            ctx.needs_resync = True
            return
        terminal = getattr(getattr(session.katrain, "game", None), "terminal", None)
        if (
            terminal is not None and snapshot.phase == GamePhase.FINISHED
            and snapshot.move_number == ctx.last_confirmed_move
        ):
            # A retrying record may keep this context alive. Do not replace
            # its committed RE with an identical reconnect snapshot.
            ctx.needs_resync = False
            return
        if snapshot.move_number == ctx.last_confirmed_move and snapshot.phase == ctx.game_phase and not ctx.needs_resync:
            return
        try:
            with getattr(session, "lock", nullcontext()):
                if snapshot.move_number == ctx.last_confirmed_move and snapshot.phase == ctx.game_phase and not ctx.needs_resync:
                    return
                self._restore_ogs_snapshot(session, snapshot, ctx.remote_session)
                ctx.last_confirmed_move = snapshot.move_number
                ctx.game_phase = snapshot.phase
                ctx.clear_pending()
                ctx.needs_resync = False
                session.katrain.platform_phase = snapshot.phase.value
        except Exception:
            ctx.needs_resync = True
            logger.exception("OGS snapshot restore failed for game %s", game_id)
            return
        self._session_manager.broadcast_to_session(
            ctx.session_id, {"type": "platform_phase_changed", "phase": snapshot.phase.value}
        )

    async def _on_game_started(self, game_session: PlatformGameSession) -> None:
        if game_session.platform != "ogs":
            logger.info(f"Game started event from {game_session.platform}: {game_session.game_id}")
            return
        owner = self._pending_owner.get("ogs") or self._platform_user_ids.get("ogs")
        if owner is None:
            logger.warning("OGS game start before local owner is established")
            return
        try:
            await self.start_platform_game("ogs", game_session, owner)
        except Exception:
            logger.exception("Could not start OGS local session for %s", game_session.game_id)

    async def _on_game_ended(self, game_id: str, result: str, winner: str) -> None:
        ctx = self._active_games.get(game_id)
        if ctx is None:
            return
        if ctx.platform != "ogs":
            ctx.clear_pending()
            self._session_manager.broadcast_to_session(
                ctx.session_id, {"type": "platform_game_ended", "game_id": game_id, "result": result, "winner": winner}
            )
            await self.end_platform_game(game_id, result)
            return

        async with self._locks.setdefault(f"finish:{game_id}", asyncio.Lock()):
            ctx = self._active_games.get(game_id)
            if ctx is None:
                return
            adapter = self._adapters.get("ogs")
            get_snapshot = getattr(adapter, "get_game_snapshot", None)
            if get_snapshot is not None:
                snapshot = get_snapshot(game_id)
                if (
                    ctx.needs_resync or snapshot.phase != GamePhase.FINISHED
                    or ctx.last_confirmed_move != snapshot.move_number
                ):
                    raise RuntimeError("OGS final board has not been restored locally")
            try:
                session = self._session_manager.get_session(ctx.session_id)
            except KeyError:
                logger.error("OGS result for %s has no local session to settle", game_id)
                raise
            terminal = getattr(session.katrain.game, "terminal", None)
            if terminal is None:
                try:
                    session.katrain._commit_end_state(result)
                except Exception:
                    logger.exception("Could not commit OGS result for game %s", game_id)
                    raise
            elif terminal.result != result:
                raise ValueError(f"Conflicting OGS result for game {game_id}: {terminal.result} versus {result}")

            # A failed state update or broadcast can happen after the result
            # was committed. Retrying must finish the remaining steps rather
            # than skipping them because terminal is already populated.
            ctx.game_phase = GamePhase.FINISHED
            session.katrain.platform_phase = GamePhase.FINISHED.value
            session.katrain.update_state()
            session.last_state = session.katrain.get_state()
            session.game_ended = True
            winner_id = (
                getattr(session, "player_b_id", None) if winner == "B"
                else getattr(session, "player_w_id", None) if winner == "W" else None
            )
            if not ctx.game_end_emitted:
                self._session_manager.broadcast_to_session(
                    ctx.session_id,
                    {"type": "game_end", "data": {"reason": "platform", "winner_id": winner_id, "result": result}},
                )
                ctx.game_end_emitted = True
            if not ctx.platform_end_emitted:
                self._session_manager.broadcast_to_session(
                    ctx.session_id,
                    {"type": "platform_game_ended", "game_id": game_id, "result": result, "winner": winner},
                )
                ctx.platform_end_emitted = True

            ctx.clear_pending()
            record = self.on_online_game_finished
            try:
                saved = bool(await record(session, ctx, result)) if record is not None else False
            except Exception:
                logger.exception("Could not save OGS result for game %s", game_id)
                saved = False
            if saved:
                await self.end_platform_game(game_id, result)
            elif game_id not in self._record_retry_tasks or self._record_retry_tasks[game_id].done():
                self._record_retry_tasks[game_id] = asyncio.create_task(
                    self._retry_online_game_record(game_id, result, winner)
                )

    async def _retry_online_game_record(self, game_id: str, result: str, winner: str) -> None:
        for delay in ONLINE_RECORD_RETRY_DELAYS:
            await asyncio.sleep(delay)
            if game_id not in self._active_games:
                return
            await self._on_game_ended(game_id, result, winner)
            if game_id not in self._active_games:
                return
        logger.error("OGS game %s remains unsaved; waiting for a later terminal event", game_id)

    async def _on_game_phase_changed(self, game_id: str, phase: GamePhase) -> None:
        ctx = self._active_games.get(game_id)
        if ctx:
            if ctx.platform == "ogs" and ctx.game_phase == GamePhase.FINISHED and phase != GamePhase.FINISHED:
                logger.warning("Ignoring OGS phase rollback after finish for %s", game_id)
                return
            ctx.game_phase = phase
            if phase != GamePhase.SCORING and ctx.pending_action in ("score_accept", "score_reject"):
                ctx.clear_pending()
            try:
                session = self._session_manager.get_session(ctx.session_id)
                session.katrain.platform_phase = phase.value
            except KeyError:
                pass
            self._session_manager.broadcast_to_session(
                ctx.session_id, {"type": "platform_phase_changed", "phase": phase.value}
            )

    async def _on_connection_lost(self) -> None:
        logger.warning("Platform connection lost")
        for ctx in self._active_games.values():
            ctx.needs_resync = True
            ctx.pending_confirmation.set()

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
