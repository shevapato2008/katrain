"""Transactional domain service for the independent ranked-AI ladder."""

from __future__ import annotations

import hashlib
import hmac
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from sqlalchemy.exc import IntegrityError

from katrain.core.sgf_parser import ParseError, SGF
from katrain.web.core import models_db

AI_LADDER_GAME_TYPE = "ai_ladder_ranked"
PLACEMENT_GAMES = 5

# 并发只靠一把占位锁:`uq_ai_ladder_active_user` 保证一个账号最多一行。
# 开新局 = 立即夺占位,没有门槛、没有窗口、没有倒计时 —— 曾经那一整套
# (心跳门槛/5 分钟接管窗口/30 分钟放弃窗口/两个 threshold + version)都在回答
# 「另一台设备是不是真的死了」,而那个问题不需要回答:这不是两个用户争抢,
# 是同一个人站在两台机器之间,他就在屏幕前,直接问他即可。
#
# 心跳保留,但用途降级:只让被夺占位的那台在下一次心跳时得知自己被顶掉、当场停手,
# 不再用来换取任何权限。


@dataclass(frozen=True)
class AiLadderOpponentSnapshot:
    rung: int
    rank_name: str
    config_snapshot: Mapping[str, Any]
    certification_status: str
    availability: str
    route: str

    def __post_init__(self) -> None:
        if type(self.rung) is not int or not 1 <= self.rung <= 41:
            raise ValueError("opponent rung must be an integer in 1..41")
        if not isinstance(self.rank_name, str) or not self.rank_name.strip():
            raise ValueError("opponent rank_name must be non-empty")
        if not isinstance(self.config_snapshot, Mapping):
            raise ValueError("opponent config_snapshot must be a mapping")
        config = deepcopy(dict(self.config_snapshot))
        digest = config.get("config_digest")
        identity = config.get("config_version") or config.get("recipe_identity")
        if not isinstance(digest, str) or not digest.strip() or not isinstance(identity, str) or not identity.strip():
            raise ValueError(
                "opponent config_snapshot requires nonempty config_digest and config_version or recipe_identity"
            )
        object.__setattr__(self, "config_snapshot", config)
        if self.route not in {"local", "server"}:
            raise ValueError("opponent route must be local or server")


@dataclass(frozen=True)
class AiLadderSettlementResult:
    counted: bool
    replayed: bool
    reason: Optional[str]
    ai_ladder_rung: Optional[int]
    placement_lo: Optional[int]
    placement_hi: Optional[int]
    placement_completed: Optional[int]
    net_score: Optional[int]


class AiLadderLifecycleError(ValueError):
    """Base class for account-level ranked game lifecycle failures."""


class AiLadderLifecycleNotFound(AiLadderLifecycleError):
    """The requested lifecycle does not exist for this account."""


class AiLadderLifecycleConflict(AiLadderLifecycleError):
    """The account already has a conflicting lifecycle or transition."""


class InvalidReservationKey(AiLadderLifecycleError):
    """An origin-only action did not prove possession of its reservation key."""


@dataclass(frozen=True)
class AiLadderBlockingGame:
    game_id: str
    user_id: int
    state: str
    origin_device_id: str
    origin_session_id: Optional[str]
    user_color: str
    opponent: AiLadderOpponentSnapshot
    ai_subtype: str
    execution_identity: str
    rules_snapshot: Mapping[str, Any]
    time_control_snapshot: Mapping[str, Any]


@dataclass(frozen=True)
class AiLadderReservationResult:
    created: bool
    game: AiLadderBlockingGame
    reservation_key: Optional[str] = field(repr=False, compare=False)


@dataclass(frozen=True)
class AiLadderLifecycleReceipt:
    state: str
    game_id: str
    result: str
    terminal_source: str
    counted: bool
    reason: Optional[str]
    replayed: bool
    ai_ladder_rung: Optional[int]
    placement_lo: Optional[int]
    placement_hi: Optional[int]
    placement_completed: Optional[int]
    net_score: Optional[int]


@dataclass(frozen=True)
class AiLadderCancelResult:
    cancelled: bool
    receipt: Optional[AiLadderLifecycleReceipt] = None


def initial_placement_window(legacy_rank: Optional[str]) -> tuple[int, int]:
    """Map a legacy rank to a 32-rung search window without granting a rung."""

    mapped = _legacy_rank_to_rung(legacy_rank)
    if mapped is None:
        return 1, 32
    start = max(1, min(mapped - 16, 10))
    return start, start + 31


def expected_opponent_rung(rung: Optional[int], placement_lo: int, placement_hi: int) -> int:
    """The rung a player faces next: their own once placed, else the window's midpoint.

    One definition, because the status endpoint and the settlement check both need the
    same answer; they used to inline the formula separately, and when two copies drift a
    legitimately seated game settles as `opponent_rung_mismatch`.

    NOT snapped onto a rung that has a recipe -- deliberately, for now. The raw midpoint
    lands on one of the ten recipe-less rungs in 12 of the 160 placement games reachable
    from the default 1..32 window, and those games cannot be seated at all. Snapping here
    changes the seating contract that `build_opponent_snapshot` and the mismatch check
    agree on, so it is an open question rather than a quiet fix. See
    superpowers/tracks/golaxy-ai-ladder-parity/2026-08-04-41-tier-rated-play-integration-design.md
    §6, which asks for the whole search to run over available rungs.
    """
    return rung if rung is not None else (placement_lo + placement_hi) // 2


def _legacy_rank_to_rung(legacy_rank: Optional[str]) -> Optional[int]:
    if not isinstance(legacy_rank, str):
        return None
    rank = legacy_rank.strip().lower()
    if len(rank) < 2 or not rank[:-1].isdigit():
        return None
    value = int(rank[:-1])
    if rank.endswith("k") and 1 <= value <= 20:
        return 21 - value
    if rank.endswith("d") and value >= 1:
        return min(20 + 2 * value, 38)
    return None


class AiLadderRankedRepository:
    """Own the complete lock/load/ledger/update/commit settlement boundary."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def reserve_game(
        self,
        *,
        user_id: int,
        game_id: str,
        user_color: str,
        opponent: AiLadderOpponentSnapshot,
        origin_device_id: str,
        ai_subtype: str,
        execution_identity: str,
        rules_snapshot: Mapping[str, Any],
        time_control_snapshot: Mapping[str, Any],
        reservation_key: str,
    ) -> AiLadderReservationResult:
        """Reserve the account's single ranked game with a caller-owned credential.

        Only the digest is durable. Replaying the same immutable request and raw key
        succeeds because the caller already owns that key; a different key conflicts.
        """

        self._validate_reservation_contract(
            game_id=game_id,
            user_color=user_color,
            origin_device_id=origin_device_id,
            ai_subtype=ai_subtype,
            execution_identity=execution_identity,
            rules_snapshot=rules_snapshot,
            time_control_snapshot=time_control_snapshot,
        )
        if not isinstance(reservation_key, str) or not reservation_key.strip() or len(reservation_key) > 128:
            raise ValueError("reservation_key must be a non-empty string of at most 128 characters")
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            self._lock_user(session, user_id=user_id)
            existing = (
                session.query(models_db.AiLadderActiveGame)
                .filter(models_db.AiLadderActiveGame.user_id == user_id)
                .with_for_update()
                .one_or_none()
            )
            if existing is not None:
                if self._is_stale_reserved(existing):
                    session.delete(existing)
                    session.flush()
                    existing = None
            if existing is not None:
                if self._reservation_matches(
                    existing,
                    game_id=game_id,
                    user_color=user_color,
                    opponent=opponent,
                    origin_device_id=origin_device_id,
                    ai_subtype=ai_subtype,
                    execution_identity=execution_identity,
                    rules_snapshot=rules_snapshot,
                    time_control_snapshot=time_control_snapshot,
                    reservation_key=reservation_key,
                ):
                    return AiLadderReservationResult(
                        created=False,
                        game=self._blocking_from_row(existing),
                        reservation_key=reservation_key,
                    )
                raise AiLadderLifecycleConflict("account already has an active ranked AI game")

            # A `game_id` that is already in the ledger cannot be reserved again -- by anyone.
            #
            # The id is minted by the box (`uuid4().hex`) and taken on trust here, so a box that
            # replays or fabricates one can hand this account a reservation whose every exit is
            # shut: `_find_ledger` raises NotFound the moment a ledger row for this `game_id`
            # belongs to someone else, and it is the FIRST statement in both the takeover path
            # and the release path. Waiting never helps, because nothing about that row changes.
            #
            # Refusing at the door rather than untangling it later, because there is nothing to
            # untangle: the state is unresolvable by construction, so the only cure is not
            # creating it. (`ai_ladder_game_ledger.game_id` is globally unique, so this reads
            # across accounts on purpose -- the collision is the hazard, not the ownership.)
            if self._find_ledger_by_game_id(session, game_id=game_id) is not None:
                raise AiLadderLifecycleConflict("game_id is already settled")
            # 同理,`user_games` 里已有这个 id 也不许预约 —— 而这一侧此前没人查。
            #
            # 已有的闸只挡一个方向:`user_game_repo.create` 会拒绝一个已被段位预约占用的
            # game_id。反过来先建 `user_games` 行、再拿同一个 id 预约,一路畅通;
            # 而 `_create_or_validate_user_game` 会把那行逐字段与结算比对、任一不同就抛
            # Conflict,且它挡在 finalize 的**每一条** terminal_source 前面 ⇒ 接管被拒、
            # 释放又要求 `pending_settlement`,账号在所有设备上锁死。
            #
            # game_id 由客户端给,所以这是**两次公开请求**就能走到的自锁。
            if session.query(models_db.UserGame.id).filter(models_db.UserGame.id == game_id).first() is not None:
                raise AiLadderLifecycleConflict("game_id already belongs to a recorded game")
            row = models_db.AiLadderActiveGame(
                game_id=game_id,
                user_id=user_id,
                origin_device_id=origin_device_id,
                origin_session_id=None,
                state="reserved",
                version=0,
                reservation_key_hash=self._hash_reservation_key(reservation_key),
                user_color=user_color,
                game_type=AI_LADDER_GAME_TYPE,
                opponent_rung=opponent.rung,
                opponent_rank_name=opponent.rank_name,
                opponent_config_snapshot=deepcopy(dict(opponent.config_snapshot)),
                opponent_certification_status=opponent.certification_status,
                opponent_availability=opponent.availability,
                opponent_route=opponent.route,
                ai_subtype=ai_subtype,
                execution_identity=execution_identity,
                rules_snapshot=deepcopy(dict(rules_snapshot)),
                time_control_snapshot=deepcopy(dict(time_control_snapshot)),
            )
            session.add(row)
            session.commit()
            return AiLadderReservationResult(
                created=True,
                game=self._blocking_from_row(row),
                reservation_key=reservation_key,
            )
        except IntegrityError as exc:
            session.rollback()
            existing = (
                session.query(models_db.AiLadderActiveGame)
                .filter(models_db.AiLadderActiveGame.user_id == user_id)
                .one_or_none()
            )
            if existing is not None and self._reservation_matches(
                existing,
                game_id=game_id,
                user_color=user_color,
                opponent=opponent,
                origin_device_id=origin_device_id,
                ai_subtype=ai_subtype,
                execution_identity=execution_identity,
                rules_snapshot=rules_snapshot,
                time_control_snapshot=time_control_snapshot,
                reservation_key=reservation_key,
            ):
                return AiLadderReservationResult(
                    created=False,
                    game=self._blocking_from_row(existing),
                    reservation_key=reservation_key,
                )
            raise AiLadderLifecycleConflict("account already has an active ranked AI game") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def activate_reservation(
        self,
        *,
        user_id: int,
        game_id: str,
        reservation_key: str,
        origin_device_id: str,
        origin_session_id: str,
    ) -> AiLadderBlockingGame:
        if not isinstance(origin_session_id, str) or not origin_session_id.strip():
            raise ValueError("origin_session_id must be non-empty")
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = self._lock_lifecycle(session, user_id=user_id, game_id=game_id)
            self._verify_origin(row, reservation_key=reservation_key, origin_device_id=origin_device_id)
            if row.state == "pending_settlement":
                raise AiLadderLifecycleConflict("pending settlement cannot be activated")
            if row.origin_session_id not in {None, origin_session_id}:
                raise AiLadderLifecycleConflict("reservation is already bound to another session")
            if row.state == "reserved":
                row.state = "active"
                row.origin_session_id = origin_session_id
                row.version += 1
            session.commit()
            return self._blocking_from_row(row)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def mark_pending_settlement(
        self, *, user_id: int, game_id: str, reservation_key: str, origin_device_id: str
    ) -> AiLadderBlockingGame:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = self._lock_lifecycle(session, user_id=user_id, game_id=game_id)
            self._verify_origin(row, reservation_key=reservation_key, origin_device_id=origin_device_id)
            if row.state == "reserved":
                raise AiLadderLifecycleConflict("reservation has not been activated")
            if row.state == "active":
                row.state = "pending_settlement"
                row.pending_settlement_since = datetime.now(timezone.utc)
                row.version += 1
            session.commit()
            return self._blocking_from_row(row)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def record_heartbeat(
        self, *, user_id: int, game_id: str, reservation_key: str, origin_device_id: str
    ) -> AiLadderBlockingGame:
        """Report that the box playing this game is still alive.

        Origin-only: the reservation key is the capability that says "I am the client running
        this game". Without that check any client could hold a game alive that it is not
        playing, which is precisely the state takeover exists to break out of.

        Only `active` games heartbeat. `reserved` has its own short reclaim and
        `pending_settlement` is already trying to hand over a result -- neither is waiting on a
        liveness signal, so a heartbeat there is a no-op rather than an error, and a box that
        keeps its timer running one tick past the end of a game does not get an error dialog
        for it.
        """

        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = self._lock_lifecycle(session, user_id=user_id, game_id=game_id)
            self._verify_origin(row, reservation_key=reservation_key, origin_device_id=origin_device_id)
            if row.state == "active":
                row.last_heartbeat_at = datetime.now(timezone.utc)
                row.heartbeat_generation = (row.heartbeat_generation or 0) + 1
            session.commit()
            return self._blocking_from_row(row)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def release_abandoned_settlement(
        self, *, user_id: int, game_id: str, deciding_device_id: str
    ) -> AiLadderCancelResult:
        """Stop waiting for a result that was announced but never delivered.

        **Writes no ledger row and moves no rating.** The ledger records verdicts, and "the box
        that played this game never came back" is not a verdict -- filing it as `inconclusive`
        would state that we know the game was undecided, when what we actually know is that we
        do not know. It would also void the real result permanently: the ledger is first-wins,
        so a box that syncs a week later would find its genuine outcome replayed away.

        Releasing only the reservation keeps both truths intact -- the account can play again
        now, and if that box ever does deliver, the game it really played still counts for
        exactly what it was.

        Not origin-only, deliberately: the whole point is that the origin is unreachable. The
        authenticated account plus the waiting window is the authority here.
        """

        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            self._lock_user(session, user_id=user_id)
            # Ledger first, before any state judgement: if the result did land, the honest
            # answer is that receipt, not a release. Ordering this after the state check is the
            # shape that makes a correct branch unreachable.
            existing = self._find_ledger(session, user_id=user_id, game_id=game_id)
            if existing is not None:
                return AiLadderCancelResult(cancelled=False, receipt=self._replay_lifecycle_receipt(session, existing))
            row = self._lock_lifecycle(session, user_id=user_id, game_id=game_id)
            if row.state != "pending_settlement":
                raise AiLadderLifecycleConflict("only a game awaiting settlement can be released")
            session.delete(row)
            session.commit()
            return AiLadderCancelResult(cancelled=True, receipt=None)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def cancel_reservation(
        self, *, user_id: int, game_id: str, reservation_key: str, origin_device_id: str
    ) -> AiLadderCancelResult:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            ledger = self._find_ledger(session, user_id=user_id, game_id=game_id)
            if ledger is not None:
                return AiLadderCancelResult(
                    cancelled=False,
                    receipt=self._lifecycle_receipt(session, ledger, replayed=True),
                )
            row = self._lock_lifecycle_or_none(session, user_id=user_id, game_id=game_id)
            if row is None:
                ledger = self._find_ledger(session, user_id=user_id, game_id=game_id)
                if ledger is not None:
                    return AiLadderCancelResult(
                        cancelled=False,
                        receipt=self._lifecycle_receipt(session, ledger, replayed=True),
                    )
                raise AiLadderLifecycleNotFound("ranked AI lifecycle not found")
            ledger = self._find_ledger(session, user_id=user_id, game_id=game_id)
            if ledger is not None:
                return AiLadderCancelResult(
                    cancelled=False,
                    receipt=self._lifecycle_receipt(session, ledger, replayed=True),
                )
            self._verify_origin(row, reservation_key=reservation_key, origin_device_id=origin_device_id)
            if row.state != "reserved":
                raise AiLadderLifecycleConflict("only an unactivated reservation may be cancelled")
            session.delete(row)
            session.commit()
            return AiLadderCancelResult(cancelled=True)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_blocking_game(self, user_id: int) -> Optional[AiLadderBlockingGame]:
        session = self.session_factory()
        try:
            row = (
                session.query(models_db.AiLadderActiveGame)
                .filter(models_db.AiLadderActiveGame.user_id == user_id)
                .one_or_none()
            )
            if row is not None and self._is_stale_reserved(row):
                session.delete(row)
                session.commit()
                return None
            return self._blocking_from_row(row) if row is not None else None
        finally:
            session.close()

    def get_game_lifecycle(
        self, *, user_id: int, game_id: str
    ) -> Optional[AiLadderBlockingGame | AiLadderLifecycleReceipt]:
        session = self.session_factory()
        try:
            row = (
                session.query(models_db.AiLadderActiveGame)
                .filter(
                    models_db.AiLadderActiveGame.user_id == user_id,
                    models_db.AiLadderActiveGame.game_id == game_id,
                )
                .one_or_none()
            )
            if row is not None:
                return self._blocking_from_row(row)
            ledger = self._find_ledger(session, user_id=user_id, game_id=game_id)
            return self._lifecycle_receipt(session, ledger, replayed=True) if ledger is not None else None
        finally:
            session.close()

    def recent_counted_results(self, user_id: int, *, limit: int = 5) -> list[str]:
        """Return newest valid win/loss decisions; excluded receipts never enter recent form."""

        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        session = self.session_factory()
        try:
            rows = (
                session.query(models_db.AiLadderGameLedger.result)
                .filter(
                    models_db.AiLadderGameLedger.user_id == user_id,
                    models_db.AiLadderGameLedger.counted.is_(True),
                    models_db.AiLadderGameLedger.result.in_(("win", "loss")),
                )
                .order_by(models_db.AiLadderGameLedger.settled_at.desc(), models_db.AiLadderGameLedger.id.desc())
                .limit(limit)
                .all()
            )
            return [row[0] for row in rows]
        finally:
            session.close()

    def has_ladder_rank(self, user_id: int) -> bool:
        """Whether placement has resolved into a rung -- the rated-PvP prerequisite.

        Replaces a count of finished `game_type == "rated"` games: nothing writes
        that value for an AI game, so the counter sat at 0 forever while the lobby
        told players to go and earn it on a page that could not move it.
        """
        session = self.session_factory()
        try:
            rung = (
                session.query(models_db.AiLadderProfile.ai_ladder_rung)
                .filter(models_db.AiLadderProfile.user_id == user_id)
                .scalar()
            )
            return rung is not None
        finally:
            session.close()

    def adopt_remote_profile(self, user_id: int, profile: Mapping[str, Any]) -> bool:
        """Overwrite this node's profile with the cloud's answer for the same account.

        A board settles its own games, but an account can play on more than one device,
        and only one of them can be right about the rank. The cloud is the merge point:
        it re-ran the settlement against everything it knows, so when it replies with a
        profile, that is the number to show. Returns whether anything changed.

        A settlement the cloud did not count carries no profile (all fields null), which
        is not an instruction to reset anyone -- those are ignored.
        """
        fields = ("ai_ladder_rung", "placement_lo", "placement_hi", "placement_completed", "net_score")
        if not isinstance(profile, Mapping):
            return False
        values = {name: profile.get(name) for name in fields}
        if any(values[name] is None for name in fields if name != "ai_ladder_rung"):
            return False
        if type(values["placement_lo"]) is not int or type(values["placement_hi"]) is not int:
            return False

        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = session.get(models_db.AiLadderProfile, user_id)
            if row is None:
                row = models_db.AiLadderProfile(user_id=user_id, version=0, **values)
                session.add(row)
                session.commit()
                return True
            if all(getattr(row, name) == values[name] for name in fields):
                return False
            for name in fields:
                setattr(row, name, values[name])
            row.version = (row.version or 0) + 1
            session.commit()
            return True
        finally:
            session.close()

    def create_pending_game(self, snapshot, *, reservation_key: Optional[str] = None) -> None:
        if reservation_key is None:
            reservation_key = getattr(snapshot, "reservation_key", None)
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            session.add(
                models_db.AiLadderPendingGame(
                    game_id=snapshot.game_id,
                    user_id=snapshot.user_id,
                    session_id=snapshot.session_id,
                    reservation_key=reservation_key,
                    user_color=snapshot.user_color,
                    game_type=snapshot.game_type,
                    opponent_rung=snapshot.opponent.rung,
                    opponent_rank_name=snapshot.opponent.rank_name,
                    opponent_config_snapshot=deepcopy(dict(snapshot.opponent.config_snapshot)),
                    opponent_certification_status=snapshot.opponent.certification_status,
                    opponent_availability=snapshot.opponent.availability,
                    opponent_route=snapshot.opponent.route,
                    ai_subtype=snapshot.ai_subtype,
                    execution_identity=snapshot.execution_identity,
                    game_saved=False,
                    saved_result=None,
                )
            )
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ValueError("user already has a pending ranked AI game") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_pending_game(self, user_id: int) -> Optional[dict[str, Any]]:
        session = self.session_factory()
        try:
            row = (
                session.query(models_db.AiLadderPendingGame)
                .filter(models_db.AiLadderPendingGame.user_id == user_id)
                .one_or_none()
            )
            if row is None:
                return None
            return {
                "game_id": row.game_id,
                "user_id": row.user_id,
                "session_id": row.session_id,
                "reservation_key": row.reservation_key,
                "user_color": row.user_color,
                "game_type": row.game_type,
                "opponent_rung": row.opponent_rung,
                "opponent_rank_name": row.opponent_rank_name,
                "opponent_config_snapshot": deepcopy(dict(row.opponent_config_snapshot)),
                "opponent_certification_status": row.opponent_certification_status,
                "opponent_availability": row.opponent_availability,
                "opponent_route": row.opponent_route,
                "ai_subtype": row.ai_subtype,
                "execution_identity": row.execution_identity,
                "game_saved": row.game_saved,
                "saved_result": row.saved_result,
            }
        finally:
            session.close()

    def get_settlement_receipt(self, *, user_id: int, game_id: str) -> Optional[dict[str, Any]]:
        """Return only this account's public lifecycle receipt for one ranked game."""

        session = self.session_factory()
        try:
            ledger = (
                session.query(models_db.AiLadderGameLedger)
                .filter(
                    models_db.AiLadderGameLedger.user_id == user_id,
                    models_db.AiLadderGameLedger.game_id == game_id,
                )
                .one_or_none()
            )
            if ledger is not None:
                return {
                    "state": "settled",
                    "game_id": ledger.game_id,
                    "counted": ledger.counted,
                    "reason": ledger.reason,
                }
            pending = (
                session.query(models_db.AiLadderPendingGame.game_id)
                .filter(
                    models_db.AiLadderPendingGame.user_id == user_id,
                    models_db.AiLadderPendingGame.game_id == game_id,
                )
                .one_or_none()
            )
            return {"state": "pending"} if pending is not None else None
        finally:
            session.close()

    def mark_pending_game_saved(self, *, user_id: int, game_id: str, result: str) -> None:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = (
                session.query(models_db.AiLadderPendingGame)
                .filter(
                    models_db.AiLadderPendingGame.user_id == user_id,
                    models_db.AiLadderPendingGame.game_id == game_id,
                )
                .with_for_update()
                .one_or_none()
            )
            if row is None:
                raise ValueError("pending ranked AI game not found")
            if row.game_saved and row.saved_result != result:
                raise ValueError("pending ranked AI saved result is immutable")
            row.game_saved = True
            row.saved_result = result
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def clear_pending_game(self, *, user_id: int, game_id: str) -> None:
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            row = (
                session.query(models_db.AiLadderPendingGame)
                .filter(
                    models_db.AiLadderPendingGame.user_id == user_id,
                    models_db.AiLadderPendingGame.game_id == game_id,
                )
                .with_for_update()
                .one_or_none()
            )
            if row is not None:
                session.delete(row)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def finalize_reserved_game(
        self,
        *,
        user_id: int,
        game_id: str,
        terminal_source: str,
        result: str,
        deciding_device_id: str,
        reservation_key: Optional[str] = None,
        game_record: Optional[Mapping[str, Any]] = None,
        engine_stalled: bool = False,
    ) -> AiLadderLifecycleReceipt:
        """Atomically record, rate, audit and release one account reservation."""

        if terminal_source not in {"played_result", "remote_resign", "recovery"}:
            raise ValueError("invalid terminal_source")
        if result not in {"win", "loss", "inconclusive"}:
            raise ValueError("invalid result")
        if terminal_source == "remote_resign" and result != "loss":
            raise ValueError("remote_resign must record a user loss")
        if not isinstance(deciding_device_id, str) or not deciding_device_id.strip():
            raise ValueError("deciding_device_id must be non-empty")
        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            self._lock_user(session, user_id=user_id)
            existing = self._find_ledger(session, user_id=user_id, game_id=game_id)
            if existing is not None:
                return self._replay_lifecycle_receipt(session, existing)

            row = self._lock_lifecycle_or_none(session, user_id=user_id, game_id=game_id)
            if row is None:
                existing = self._find_ledger(session, user_id=user_id, game_id=game_id)
                if existing is not None:
                    return self._replay_lifecycle_receipt(session, existing)
                raise AiLadderLifecycleNotFound("ranked AI lifecycle not found")
            existing = self._find_ledger(session, user_id=user_id, game_id=game_id)
            if existing is not None:
                return self._replay_lifecycle_receipt(session, existing)
            if terminal_source in {"played_result", "recovery"}:
                self._verify_origin(
                    row,
                    reservation_key=reservation_key,
                    origin_device_id=deciding_device_id,
                )
                if row.state not in {"active", "pending_settlement"}:
                    raise AiLadderLifecycleConflict("reservation must be activated before terminal submission")
            elif row.state == "pending_settlement":
                # 唯一还挡着的一格,而且挡的理由和「谁、等多久」无关:这一格**已经有结果了**,
                # 正在被送来。账本先到先得,所以在这里判负不是抢在真结果前面,是**永久替换**它
                # —— 记下一场用户没输的负,并把一份 0 手的记录当成他下过的那盘棋。
                # 这一格的出路是 `release_abandoned_settlement`(什么都不记,让真结果自己到),
                # 不是判负。
                raise AiLadderLifecycleConflict("a game awaiting settlement cannot be resigned from another device")

            opponent = self._opponent_from_row(row)
            record = self._validated_game_record(
                row=row,
                result=result,
                terminal_source=terminal_source,
                record=game_record,
            )
            self._create_or_validate_user_game(session, row=row, record=record)

            user = session.query(models_db.User).filter(models_db.User.id == user_id).with_for_update().one_or_none()
            if user is None:
                raise AiLadderLifecycleNotFound("account not found")
            ignored_reason, profile = self._prepare_profile(
                session,
                user=user,
                user_id=user_id,
                game_type=row.game_type,
                result=result,
                opponent=opponent,
                engine_stalled=engine_stalled,
            )
            ledger = self._new_ledger(
                user_id=user_id,
                # Same invariant as the other settlement path: every immutable ledger row
                # carries its own subject, frozen from the user row this transaction already
                # holds. A write path that skipped it would be a hole in exactly the guarantee
                # the column exists for -- "take the whole database away and leave only this
                # row: can you still tell whose it is?"
                account_subject=user.uuid,
                game_id=game_id,
                user_color=row.user_color,
                result=result,
                game_type=row.game_type,
                opponent=opponent,
                reason=ignored_reason,
            )
            ledger.origin_device_id = row.origin_device_id
            ledger.deciding_device_id = deciding_device_id
            ledger.terminal_source = terminal_source
            ledger.decided_at = datetime.now(timezone.utc)
            session.add(ledger)
            if ignored_reason is None:
                self._apply_result(profile, result)
                profile.version += 1
            session.delete(row)
            session.commit()
            return self._lifecycle_receipt(session, ledger, replayed=False)
        except IntegrityError:
            session.rollback()
            existing = self._find_ledger(session, user_id=user_id, game_id=game_id)
            if existing is None:
                raise
            return self._replay_lifecycle_receipt(session, existing)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def settle_game(
        self,
        *,
        user_id: int,
        game_id: str,
        user_color: str,
        result: str,
        game_type: str,
        opponent: Optional[AiLadderOpponentSnapshot],
        engine_stalled: bool = False,
    ) -> AiLadderSettlementResult:
        if user_color not in {"B", "W"}:
            raise ValueError("user_color must be B or W")
        if not isinstance(game_id, str) or not game_id.strip():
            raise ValueError("game_id must be non-empty")

        session = self.session_factory()
        try:
            self._begin_write_transaction(session)
            user = self._lock_user(session, user_id=user_id)
            existing = self._find_ledger_by_game_id(session, game_id=game_id)
            if existing is not None:
                return self._replay_result(session, existing, user_id)

            active = (
                session.query(models_db.AiLadderActiveGame)
                .filter(models_db.AiLadderActiveGame.game_id == game_id)
                .one_or_none()
            )
            if active is not None:
                if active.user_id != user_id:
                    raise AiLadderLifecycleNotFound("ranked AI lifecycle not found")
                raise AiLadderLifecycleConflict("active ranked AI game must use the lifecycle finalizer")

            ignored_reason = self._ignored_reason(
                game_type=game_type, result=result, opponent=opponent, engine_stalled=engine_stalled
            )
            profile = None
            if ignored_reason is None:
                assert opponent is not None
                profile = (
                    session.query(models_db.AiLadderProfile)
                    .filter(models_db.AiLadderProfile.user_id == user_id)
                    .with_for_update()
                    .one_or_none()
                )
                if profile is None:
                    lo, hi = initial_placement_window(user.rank)
                    expected = expected_opponent_rung(None, lo, hi)
                    if opponent.rung != expected:
                        ignored_reason = "opponent_rung_mismatch"
                    else:
                        profile = models_db.AiLadderProfile(
                            user_id=user_id,
                            ai_ladder_rung=None,
                            placement_lo=lo,
                            placement_hi=hi,
                            placement_completed=0,
                            net_score=0,
                            version=0,
                        )
                        session.add(profile)
                else:
                    expected = expected_opponent_rung(
                        profile.ai_ladder_rung, profile.placement_lo, profile.placement_hi
                    )
                    if opponent.rung != expected:
                        ignored_reason = "opponent_rung_mismatch"

            ledger = self._new_ledger(
                user_id=user_id,
                # Frozen here, from the row we already hold, at the moment of settlement.
                account_subject=user.uuid,
                game_id=game_id,
                user_color=user_color,
                result=result,
                game_type=game_type,
                opponent=opponent,
                reason=ignored_reason,
            )
            session.add(ledger)
            if ignored_reason is not None:
                session.commit()
                return self._ignored(ignored_reason)

            self._apply_result(profile, result)
            profile.version += 1

            session.commit()
            return self._counted_result(profile)
        except IntegrityError:
            session.rollback()
            existing = (
                session.query(models_db.AiLadderGameLedger)
                .filter(models_db.AiLadderGameLedger.game_id == game_id)
                .one_or_none()
            )
            if existing is None:
                raise
            return self._replay_result(session, existing, user_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _validate_reservation_contract(
        *,
        game_id: str,
        user_color: str,
        origin_device_id: str,
        ai_subtype: str,
        execution_identity: str,
        rules_snapshot: Mapping[str, Any],
        time_control_snapshot: Mapping[str, Any],
    ) -> None:
        if not isinstance(game_id, str) or not game_id.strip() or len(game_id) > 32:
            raise ValueError("game_id must be a non-empty string of at most 32 characters")
        if user_color not in {"B", "W"}:
            raise ValueError("user_color must be B or W")
        for name, value in {
            "origin_device_id": origin_device_id,
            "ai_subtype": ai_subtype,
            "execution_identity": execution_identity,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if not isinstance(rules_snapshot, Mapping) or not isinstance(time_control_snapshot, Mapping):
            raise ValueError("rules and time control snapshots must be mappings")
        if rules_snapshot.get("board_size") != 19:
            raise ValueError("ranked AI reservation requires a 19x19 board")

    @staticmethod
    def _hash_reservation_key(reservation_key: str) -> str:
        return hashlib.sha256(reservation_key.encode("utf-8")).hexdigest()

    @classmethod
    def _verify_origin(cls, row, *, reservation_key: Optional[str], origin_device_id: str) -> None:
        supplied_hash = cls._hash_reservation_key(reservation_key) if isinstance(reservation_key, str) else ""
        key_matches = hmac.compare_digest(row.reservation_key_hash, supplied_hash)
        # Device IDs are mutable provenance labels, never credentials. Ownership is
        # already scoped by authenticated user_id + game_id; the unguessable key is
        # the sole origin capability for origin-only transitions.
        if not key_matches:
            raise InvalidReservationKey("invalid reservation credential")

    @staticmethod
    def _opponent_from_row(row) -> AiLadderOpponentSnapshot:
        return AiLadderOpponentSnapshot(
            rung=row.opponent_rung,
            rank_name=row.opponent_rank_name,
            config_snapshot=deepcopy(dict(row.opponent_config_snapshot)),
            certification_status=row.opponent_certification_status,
            availability=row.opponent_availability,
            route=row.opponent_route,
        )

    @classmethod
    def _blocking_from_row(cls, row) -> AiLadderBlockingGame:
        return AiLadderBlockingGame(
            game_id=row.game_id,
            user_id=row.user_id,
            state=row.state,
            origin_device_id=row.origin_device_id,
            origin_session_id=row.origin_session_id,
            user_color=row.user_color,
            opponent=cls._opponent_from_row(row),
            ai_subtype=row.ai_subtype,
            execution_identity=row.execution_identity,
            rules_snapshot=deepcopy(dict(row.rules_snapshot)),
            time_control_snapshot=deepcopy(dict(row.time_control_snapshot)),
        )

    @staticmethod
    def _reservation_matches(
        row,
        *,
        game_id: str,
        user_color: str,
        opponent: AiLadderOpponentSnapshot,
        origin_device_id: str,
        ai_subtype: str,
        execution_identity: str,
        rules_snapshot: Mapping[str, Any],
        time_control_snapshot: Mapping[str, Any],
        reservation_key: str,
    ) -> bool:
        return all(
            (
                row.game_id == game_id,
                row.user_color == user_color,
                row.origin_device_id == origin_device_id,
                row.ai_subtype == ai_subtype,
                row.execution_identity == execution_identity,
                row.opponent_rung == opponent.rung,
                row.opponent_rank_name == opponent.rank_name,
                row.opponent_config_snapshot == dict(opponent.config_snapshot),
                row.opponent_certification_status == opponent.certification_status,
                row.opponent_availability == opponent.availability,
                row.opponent_route == opponent.route,
                row.rules_snapshot == dict(rules_snapshot),
                row.time_control_snapshot == dict(time_control_snapshot),
                hmac.compare_digest(
                    row.reservation_key_hash,
                    AiLadderRankedRepository._hash_reservation_key(reservation_key),
                ),
            )
        )

    @staticmethod
    def _is_stale_reserved(row) -> bool:
        if row.state != "reserved" or row.created_at is None:
            return False
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - created > timedelta(minutes=5)

    @staticmethod
    def _lock_lifecycle_or_none(session, *, user_id: int, game_id: str):
        return (
            session.query(models_db.AiLadderActiveGame)
            .filter(
                models_db.AiLadderActiveGame.user_id == user_id,
                models_db.AiLadderActiveGame.game_id == game_id,
            )
            .with_for_update()
            .one_or_none()
        )

    @classmethod
    def _lock_lifecycle(cls, session, *, user_id: int, game_id: str):
        row = cls._lock_lifecycle_or_none(session, user_id=user_id, game_id=game_id)
        if row is None:
            raise AiLadderLifecycleNotFound("ranked AI lifecycle not found")
        return row

    @staticmethod
    def _lock_user(session, *, user_id: int):
        user = session.query(models_db.User).filter(models_db.User.id == user_id).with_for_update().one_or_none()
        if user is None:
            raise AiLadderLifecycleNotFound("account not found")
        return user

    @staticmethod
    def _find_ledger_by_game_id(session, *, game_id: str):
        return session.query(models_db.AiLadderGameLedger).filter_by(game_id=game_id).one_or_none()

    @staticmethod
    def _find_ledger(session, *, user_id: int, game_id: str):
        ledger = AiLadderRankedRepository._find_ledger_by_game_id(session, game_id=game_id)
        if ledger is not None and ledger.user_id != user_id:
            raise AiLadderLifecycleNotFound("ranked AI lifecycle not found")
        return ledger

    def _prepare_profile(self, session, *, user, user_id, game_type, result, opponent, engine_stalled):
        ignored_reason = self._ignored_reason(
            game_type=game_type,
            result=result,
            opponent=opponent,
            engine_stalled=engine_stalled,
        )
        profile = None
        if ignored_reason is None:
            profile = (
                session.query(models_db.AiLadderProfile)
                .filter(models_db.AiLadderProfile.user_id == user_id)
                .with_for_update()
                .one_or_none()
            )
            if profile is None:
                lo, hi = initial_placement_window(user.rank)
                expected_opponent_rung = (lo + hi) // 2
                if opponent.rung != expected_opponent_rung:
                    ignored_reason = "opponent_rung_mismatch"
                else:
                    profile = models_db.AiLadderProfile(
                        user_id=user_id,
                        ai_ladder_rung=None,
                        placement_lo=lo,
                        placement_hi=hi,
                        placement_completed=0,
                        net_score=0,
                        version=0,
                    )
                    session.add(profile)
            else:
                expected_opponent_rung = (
                    profile.ai_ladder_rung
                    if profile.ai_ladder_rung is not None
                    else (profile.placement_lo + profile.placement_hi) // 2
                )
                if opponent.rung != expected_opponent_rung:
                    ignored_reason = "opponent_rung_mismatch"
        return ignored_reason, profile

    @staticmethod
    def _validated_game_record(*, row, result: str, terminal_source: str, record: Optional[Mapping[str, Any]]) -> dict:
        rules = deepcopy(dict(row.rules_snapshot))
        if terminal_source == "remote_resign":
            # `+F`(forfeit)而不是 `+R`(resign):云端手上一手棋都没有,
            # 写成认输等于声称这是一盘下过、并在某一手停下的棋。弃权才是真的。
            winner = "W" if row.user_color == "B" else "B"
            sgf_result = f"{winner}+F"
            return {
                "sgf_content": (
                    f"(;GM[1]FF[4]SZ[19]RU[{rules.get('rules', 'chinese')}]"
                    f"KM[{rules.get('komi', 7.5)}]PB[{'User' if row.user_color == 'B' else 'AI'}]"
                    f"PW[{'AI' if row.user_color == 'B' else 'User'}]RE[{sgf_result}])"
                ),
                "result": sgf_result,
                "board_size": 19,
                "rules": rules.get("rules", "chinese"),
                "komi": rules.get("komi", 7.5),
                "move_count": 0,
                "player_black": "User" if row.user_color == "B" else "AI",
                "player_white": "AI" if row.user_color == "B" else "User",
            }
        if not isinstance(record, Mapping):
            raise ValueError("played or recovered result requires a complete game_record")
        required = {
            "sgf_content",
            "result",
            "board_size",
            "rules",
            "komi",
            "move_count",
            "player_black",
            "player_white",
            "source",
            "category",
            "game_type",
        }
        if not required.issubset(record) or not isinstance(record.get("sgf_content"), str) or not record["sgf_content"]:
            raise ValueError("game_record is incomplete")
        normalized = dict(record)
        for name in ("player_black", "player_white", "result", "rules"):
            if not isinstance(normalized.get(name), str) or not normalized[name].strip():
                raise ValueError(f"game_record {name} must be non-empty")
        if normalized.get("source") != "play_ai":
            raise ValueError("game_record source must be play_ai")
        if normalized.get("category") != "game":
            raise ValueError("game_record category must be game")
        if normalized.get("game_type") != AI_LADDER_GAME_TYPE:
            raise ValueError(f"game_record game_type must be {AI_LADDER_GAME_TYPE}")
        if type(normalized.get("board_size")) is not int or normalized["board_size"] != 19:
            raise ValueError("game_record board_size must be 19")
        if type(normalized.get("move_count")) is not int or normalized["move_count"] < 0:
            raise ValueError("game_record move_count must be a non-negative integer")
        if isinstance(normalized.get("komi"), bool) or not isinstance(normalized.get("komi"), (int, float)):
            raise ValueError("game_record komi must be numeric")
        for name, frozen in {
            "board_size": rules.get("board_size", 19),
            "rules": rules.get("rules", "chinese"),
            "komi": rules.get("komi", 7.5),
        }.items():
            if normalized.get(name) != frozen:
                raise ValueError(f"game_record {name} does not match reservation")
        sgf_result = normalized["result"]
        winner = row.user_color if result == "win" else ("W" if row.user_color == "B" else "B")
        if result in {"win", "loss"} and (not isinstance(sgf_result, str) or not sgf_result.startswith(f"{winner}+")):
            raise ValueError("game_record result does not match user result")
        if result == "inconclusive" and sgf_result.upper().startswith(("B+", "W+")):
            raise ValueError("inconclusive result cannot carry a decisive SGF result")
        try:
            root = SGF.parse_sgf(normalized["sgf_content"])
        except (ParseError, TypeError, ValueError, IndexError) as exc:
            raise ValueError("game_record SGF is invalid") from exc
        parsed = {
            "board_size": root.get_property("SZ"),
            "result": root.get_property("RE"),
            "player_black": root.get_property("PB"),
            "player_white": root.get_property("PW"),
            "rules": root.get_property("RU"),
            "komi": root.get_property("KM"),
        }
        if str(parsed["board_size"]) != "19":
            raise ValueError("game_record SGF board_size does not match")
        for name in ("result", "player_black", "player_white"):
            if parsed[name] != normalized[name]:
                raise ValueError(f"game_record SGF {name} does not match")
        if AiLadderRankedRepository._normalize_rules(parsed["rules"]) != AiLadderRankedRepository._normalize_rules(
            normalized["rules"]
        ):
            raise ValueError("game_record SGF rules do not match")
        try:
            parsed_komi = float(parsed["komi"])
        except (TypeError, ValueError) as exc:
            raise ValueError("game_record SGF komi is invalid") from exc
        if parsed_komi != float(normalized["komi"]):
            raise ValueError("game_record SGF komi does not match")
        return normalized

    @staticmethod
    def _normalize_rules(value: Any) -> str:
        normalized = str(value or "").strip().casefold()
        return {"cn": "chinese", "jp": "japanese"}.get(normalized, normalized)

    @staticmethod
    def _create_or_validate_user_game(session, *, row, record: Mapping[str, Any]) -> None:
        existing = session.get(models_db.UserGame, row.game_id)
        expected = {
            "user_id": row.user_id,
            "sgf_content": record["sgf_content"],
            "source": "play_ai",
            "game_type": AI_LADDER_GAME_TYPE,
            "origin_device_id": row.origin_device_id,
            "result": record["result"],
            "board_size": record["board_size"],
            "rules": record["rules"],
            "komi": record["komi"],
            "move_count": record["move_count"],
        }
        if existing is not None:
            if any(getattr(existing, name) != value for name, value in expected.items()):
                raise AiLadderLifecycleConflict("existing user game does not match reserved result")
            return
        session.add(
            models_db.UserGame(
                id=row.game_id,
                user_id=row.user_id,
                sgf_content=record["sgf_content"],
                sgf_hash=hashlib.sha256(record["sgf_content"].encode("utf-8")).hexdigest(),
                source="play_ai",
                game_type=AI_LADDER_GAME_TYPE,
                origin_device_id=row.origin_device_id,
                result=record["result"],
                board_size=record["board_size"],
                rules=record["rules"],
                komi=record["komi"],
                move_count=record["move_count"],
                player_black=record.get("player_black"),
                player_white=record.get("player_white"),
                black_rank=record.get("black_rank"),
                white_rank=record.get("white_rank"),
                title=record.get("title"),
                category="game",
                event=record.get("event"),
                round_name=record.get("round_name"),
                game_date=record.get("game_date"),
            )
        )

    def _lifecycle_receipt(self, session, ledger, *, replayed: bool) -> AiLadderLifecycleReceipt:
        profile = session.get(models_db.AiLadderProfile, ledger.user_id) if ledger.counted else None
        return AiLadderLifecycleReceipt(
            state="settled",
            game_id=ledger.game_id,
            result=ledger.result,
            terminal_source=ledger.terminal_source or "recovery",
            counted=ledger.counted,
            reason=ledger.reason,
            replayed=replayed,
            ai_ladder_rung=profile.ai_ladder_rung if profile is not None else None,
            placement_lo=profile.placement_lo if profile is not None else None,
            placement_hi=profile.placement_hi if profile is not None else None,
            placement_completed=profile.placement_completed if profile is not None else None,
            net_score=profile.net_score if profile is not None else None,
        )

    def _replay_lifecycle_receipt(self, session, ledger) -> AiLadderLifecycleReceipt:
        """Replay terminal truth and remove an exact stale pre-fix active row."""

        receipt = self._lifecycle_receipt(session, ledger, replayed=True)
        stale = (
            session.query(models_db.AiLadderActiveGame)
            .filter(
                models_db.AiLadderActiveGame.user_id == ledger.user_id,
                models_db.AiLadderActiveGame.game_id == ledger.game_id,
            )
            .with_for_update()
            .one_or_none()
        )
        if stale is not None:
            session.delete(stale)
            session.commit()
        return receipt

    @staticmethod
    def _begin_write_transaction(session) -> None:
        """Serialize SQLite writers before any profile or idempotency reads.

        PostgreSQL uses the row locks below. SQLite ignores ``FOR UPDATE``, so
        BEGIN IMMEDIATE obtains its database write reservation up front and
        prevents two callbacks from reading the same profile version.
        """

        if session.get_bind().dialect.name == "sqlite":
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    @staticmethod
    def _ignored_reason(
        *,
        game_type: str,
        result: str,
        opponent: Optional[AiLadderOpponentSnapshot],
        engine_stalled: bool = False,
    ) -> Optional[str]:
        if game_type != AI_LADDER_GAME_TYPE:
            return "invalid_game_type"
        # The seated rung could not be played at its calibrated strength, so the AI
        # refused to move at all (interface._surface_ladder_unavailable). Whatever
        # ended the game after that -- the player giving up on a board that will
        # never answer, or the AI's own clock expiring -- is an artefact of our
        # engine, not a result. Checked before `result` so a conclusive-looking
        # B+T/W+R over a stalled board cannot bank a promotion for a game nobody
        # played. Observed on an RK3562 kiosk, 2026-08-05.
        if engine_stalled:
            return "engine_unavailable"
        if result not in {"win", "loss"}:
            return "inconclusive"
        if opponent is None:
            return "opponent_not_eligible"
        if opponent.certification_status != "certified" or opponent.availability != "available":
            # Deliberately NOT relaxed by KATRAIN_LADDER_ALLOW_PROVISIONAL. That switch
            # decides whether an uncertified rung may be SEATED; whether its result may
            # move a rank is not a per-node choice -- `ck_ai_ladder_ledger_decision`
            # refuses to store a counted row whose opponent is not certified+available,
            # because a rank earned against unmeasured strength does not mean anything.
            # So a provisional game is played, recorded, and openly not counted.
            return "opponent_not_eligible"
        return None

    @staticmethod
    def _apply_result(profile: models_db.AiLadderProfile, result: str) -> None:
        # Ten of the 41 rungs (准1段–准9段, 职业顶尖) have no fitted recipe. Every write to
        # `ai_ladder_rung` therefore goes through the ladder's playable-rung stepper: raw
        # +1 from 5段(30) lands on 准6段(31), a rung no opponent can ever be built for.
        from katrain.core import ladder

        if profile.ai_ladder_rung is None:
            mid = (profile.placement_lo + profile.placement_hi) // 2
            if result == "win":
                profile.placement_lo = mid + 1
            else:
                profile.placement_hi = mid
            profile.placement_completed += 1
            if profile.placement_completed == PLACEMENT_GAMES:
                # The window is still searched over raw rungs, so the landing can fall on a
                # recipe-less rung; snap it rather than seat the player somewhere unplayable.
                profile.ai_ladder_rung = ladder.nearest_playable_rung(profile.placement_lo)
                profile.net_score = 0
            return

        profile.net_score += 1 if result == "win" else -1
        if profile.net_score >= 3:
            profile.ai_ladder_rung = ladder.step_playable_rung(profile.ai_ladder_rung, 1)
            profile.net_score = 0
        elif profile.net_score <= -3:
            profile.ai_ladder_rung = ladder.step_playable_rung(profile.ai_ladder_rung, -1)
            profile.net_score = 0

    @staticmethod
    def _ignored(reason: str) -> AiLadderSettlementResult:
        return AiLadderSettlementResult(
            counted=False,
            replayed=False,
            reason=reason,
            ai_ladder_rung=None,
            placement_lo=None,
            placement_hi=None,
            placement_completed=None,
            net_score=None,
        )

    @staticmethod
    def _new_ledger(
        *,
        user_id: int,
        account_subject: Optional[str],
        game_id: str,
        user_color: str,
        result: str,
        game_type: str,
        opponent: Optional[AiLadderOpponentSnapshot],
        reason: Optional[str],
    ) -> models_db.AiLadderGameLedger:
        return models_db.AiLadderGameLedger(
            game_id=game_id,
            user_id=user_id,
            account_subject=account_subject,
            user_color=user_color,
            result=result,
            game_type=game_type,
            opponent_rung=opponent.rung if opponent is not None else None,
            opponent_rank_name=opponent.rank_name if opponent is not None else None,
            opponent_config_snapshot=(deepcopy(dict(opponent.config_snapshot)) if opponent is not None else None),
            opponent_certification_status=opponent.certification_status if opponent is not None else None,
            opponent_availability=opponent.availability if opponent is not None else None,
            opponent_route=opponent.route if opponent is not None else None,
            counted=reason is None,
            reason=reason,
        )

    @staticmethod
    def _counted_result(profile: models_db.AiLadderProfile, *, replayed: bool = False) -> AiLadderSettlementResult:
        return AiLadderSettlementResult(
            counted=True,
            replayed=replayed,
            reason=None,
            ai_ladder_rung=profile.ai_ladder_rung,
            placement_lo=profile.placement_lo,
            placement_hi=profile.placement_hi,
            placement_completed=profile.placement_completed,
            net_score=profile.net_score,
        )

    def _replay_result(self, session, ledger: models_db.AiLadderGameLedger, user_id: int) -> AiLadderSettlementResult:
        if ledger.user_id != user_id:
            raise ValueError("game_id belongs to another user")
        if not ledger.counted:
            return AiLadderSettlementResult(
                counted=False,
                replayed=True,
                reason=ledger.reason,
                ai_ladder_rung=None,
                placement_lo=None,
                placement_hi=None,
                placement_completed=None,
                net_score=None,
            )
        profile = session.get(models_db.AiLadderProfile, user_id)
        if profile is None:
            raise RuntimeError("settled game has no AI ladder profile")
        return self._counted_result(profile, replayed=True)
