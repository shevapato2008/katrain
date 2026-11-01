"""Finite paid position requests and the shared private-analysis delivery boundary."""

from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException

from katrain.web.core.config import settings


def legacy_analysis_allowed(*, runtime=None, user=None, app=None):
    """Legacy is available only before activation; startup enforces its durable marker.

    A live runtime stays guarded if configuration is changed back without restarting.
    Paid results are delivered from owner-scoped receipts, never from the live node cache.
    """
    active = settings.MEMBERSHIP_MODE != "legacy"
    if active and runtime is not None:
        runtime.membership_guard_active = True
    if active and app is not None:
        app.state.membership_guard_active = True
    return not (
        active
        or (app is not None and getattr(app.state, "membership_guard_active", False))
        or getattr(runtime, "membership_guard_active", False)
        or getattr(user, "membership_migrated_at", None)
    )


def require_legacy_analysis(*, runtime=None, user=None, app=None):
    if not legacy_analysis_allowed(runtime=runtime, user=user, app=app):
        raise HTTPException(
            503 if settings.MEMBERSHIP_MODE == "paused" else 409,
            detail={"code": "paid_position_required", "message": "Use a quoted position analysis"},
            headers={"Cache-Control": "no-store"},
        )


def strip_private_analysis(state):
    """Copy and remove both raw engine output and its derived presentation fields."""
    clean = dict(state)
    clean.update(analysis=None, commentary="", note="", ghost_stones=[], analysis_delivered=False)
    clean["history"] = [{**h, "score": None, "winrate": None} for h in state.get("history", [])]
    clean["stones"] = [[row[0], row[1], None, row[3]] for row in state.get("stones", [])]
    for key in ("ownership", "policy", "pv", "moveInfos", "rootInfo", "score_loss", "analysis_progress", "report"):
        clean.pop(key, None)
    # An estimated score is private analysis; authoritative terminal results survive.
    if isinstance(clean.get("end_result"), str) and clean["end_result"].endswith("?"):
        clean["end_result"] = None
    return clean


def session_position_sgf(session, user):
    from katrain.web.core.ranked_session_guard import guard_ai_ladder_ranked_session

    with session.lock:
        owners = {getattr(session, key, None) for key in ("owner_user_id", "user_id", "player_b_id", "player_w_id")}
        if user is None or user.id not in owners:
            raise HTTPException(403, detail="Position analysis is restricted to a session participant")
        guard_ai_ladder_ranked_session(session, "paid-position")
        runtime = session.katrain
        if (
            not runtime.analysis_allowed
            or getattr(runtime, "game_type", "free") != "free"
            or getattr(session, "bot_game", False) is True
            or getattr(runtime, "pvp_bot_session", False) is True
        ):
            raise HTTPException(403, detail="Position analysis is unavailable in this game")
        # Serialize only the full path to the cursor; sibling branches and future moves
        # must not change the scope or leak saved analysis properties.
        nodes = runtime.game.current_node.nodes_from_root
        if len(nodes) > 501:
            raise ValueError("Analysis supports at most 500 moves")
        allowed = {"GM", "FF", "CA", "SZ", "RU", "KM", "HA", "PL", "AB", "AW", "AE", "B", "W"}
        chunks = []
        for node in nodes:
            chunks.append(
                ";"
                + "".join(
                    key + "".join("[" + node._escape_value(v) + "]" for v in values)
                    for key, values in node.properties.items()
                    if key in allowed and values
                )
            )
            if sum(len(chunk.encode("utf-8")) for chunk in chunks) > 262142:
                raise ValueError("SGF exceeds 256 KiB")
        return "(" + "".join(chunks) + ")"


def paid_engine_client():
    from katrain.cron.clients.katago import KataGoClient

    raw = settings.CLOUD_KATAGO_URL.strip()
    if not raw:
        raise RuntimeError("Paid analysis engine is not configured")
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
        raise RuntimeError("Invalid paid analysis engine URL")
    # Existing deployments configure either a base URL or the complete /analyze URL.
    path = parsed.path.rstrip("/")
    if path.endswith("/analyze"):
        base = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        return KataGoClient(base_url=base, analyze_path=path, timeout=80)
    return KataGoClient(base_url=raw.rstrip("/"), timeout=80)


def operation_receipt(db, op, *, now=None):
    from katrain.web.core import membership, models_db as m

    now = now or datetime.now(timezone.utc)
    expired = op.status == "committed" and op.result_expires_at and membership.utc(op.result_expires_at) <= now
    state = "result_expired" if expired else ("succeeded" if op.status == "committed" else op.status)
    user = db.get(m.User, op.user_id)
    payload = {
        "operation_id": str(op.id),
        "state": state,
        "source": op.source,
        "profile": op.profile,
        "units": op.units,
        "wallet_credits": op.units if op.source == "wallet" else 0,
        "catalog_version": op.catalog_version,
        "revision": int(user.membership_revision or 0),
    }
    if state == "succeeded" and op.result is not None:
        payload["result"] = op.result
    if state in ("refunded", "failed", "result_expired"):
        payload["error"] = {
            "code": state,
            "message": "Analysis result expired" if expired else "Analysis did not complete",
        }
    return payload
