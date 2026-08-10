"""Small shared builder for the board's durable ranked-settlement outbox."""

from katrain.web.core.ai_ladder_catalog import result_for_user


GAME_RECORD_FIELDS = (
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
    "black_rank",
    "white_rank",
    "title",
    "event",
    "round_name",
    "game_date",
)


def build_settlement_payload(snapshot, raw_result, *, reservation_key, game_record, device_id, engine_stalled=False):
    strict_record = {field: game_record.get(field) for field in GAME_RECORD_FIELDS if field in game_record}
    return {
        "game_id": snapshot.game_id,
        "user_color": snapshot.user_color,
        "result": result_for_user(raw_result, snapshot.user_color),
        "game_type": snapshot.game_type,
        "opponent": {
            "rung": snapshot.opponent.rung,
            "rank_name": snapshot.opponent.rank_name,
            "config_snapshot": dict(snapshot.opponent.config_snapshot),
            "certification_status": snapshot.opponent.certification_status,
            "availability": snapshot.opponent.availability,
            "route": snapshot.opponent.route,
        },
        "engine_stalled": bool(engine_stalled),
        "device_id": device_id,
        "reservation_key": reservation_key,
        "game_record": strict_record,
    }

