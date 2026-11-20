"""Fixed Go cloud business contract, copied verbatim into KaTrain.

No remote bearer credentials, headers, hostnames, or caller-selected routes cross this boundary.
Names track RemoteAPIClient methods; the extra settlement operation serves its
durable sync queue. Authentication belongs exclusively to the identity service.
Only standard-library imports are used so the two runtimes share this module.
"""

from __future__ import annotations

import json as _json
import math
import re


def _string(maximum=512, minimum=0, *, multiline=False, pattern=None):
    return ("string", minimum, maximum, multiline, pattern)


def _integer(minimum=0, maximum=2147483647):
    return ("integer", minimum, maximum)


def _enum(*values):
    return ("enum", values)


def _nullable(schema):
    return ("nullable", schema)


def _object(fields, required=()):
    return ("object", fields, frozenset(required))


_BOOL = ("boolean",)
_NUMBER = ("number", -1000000, 1000000)
_TEXT = _string()
_TOKEN = _string(128, 1)
_SEGMENT = _string(128, 1, pattern=r"[\w.~-]+")
_HEX64 = _string(64, 64, pattern=r"[0-9a-f]{64}")
_ID = _integer(1)
_SGF = _string(1048576, 1, multiline=True)
_BILLING_SGF = _nullable(_string(262144, multiline=True))
_QUOTE_TOKEN = _nullable(_string(8192))
_PAGE = _integer(1, 1000000)
_NO_FIELDS = _object({})

_POSITION_INPUT = {
    "profile": _enum("normal", "advanced"), "sgf": _BILLING_SGF,
    "game_id": _nullable(_string(64)), "session_id": _nullable(_string(128)),
    "expected_position_key": _nullable(_string(64)),
}
_REPORT_PAYMENT = {"quote_token": _QUOTE_TOKEN, "idempotency_key": _nullable(_TOKEN)}
_GAME_FIELDS = {
    "id": _nullable(_SEGMENT), "sgf_content": _SGF, "source": _string(64, 1),
    **{key: _nullable(_TEXT) for key in (
        "title", "player_black", "player_white", "black_rank", "white_rank",
        "result", "game_type", "event", "round_name", "game_date",
    )},
    "board_size": _integer(1, 52), "rules": _string(64), "komi": _NUMBER,
    "move_count": _integer(0, 1000000), "category": _string(64),
    "platform": _nullable(_enum("golaxy", "ogs", "fox")),
    "user_color": _nullable(_enum("B", "W")), "origin_device_id": _nullable(_string(128)),
}
_PHONE_CODE = {
    "challenge_id": _string(128, 16), "code": _string(6, 6, pattern=r"[0-9]{6}"),
    "flow_id": _string(128, 22, pattern=r"[A-Za-z0-9_-]+"),
}
_CLOCK = {
    "color": _enum("black", "white"), "time_enabled": _BOOL,
    "main_time": _integer(0, 86400), "byo_length": _integer(0, 3600),
    "byo_periods": _integer(0, 100),
}
_KEY_FIELDS = {"reservation_key": _TOKEN}
_LADDER_RECIPE = _object({
    "rung": _integer(1, 41),
    **{key: _nullable(_TEXT) for key in ("golaxy_level_name", "human_sl_profile")},
    "golaxy_api_level": _nullable(_integer()), "display_elo": _nullable(_integer()),
    **{key: _TEXT for key in ("ref_rank", "rank_name", "net", "mechanism", "backend_hint")},
    "max_visits": _integer(0, 100000000), "root_policy_temperature": _NUMBER,
    "human_policy_temperature": _nullable(_NUMBER), "selection": _nullable(_TEXT),
    "human_sl_params": _object({
        **{key: _NUMBER for key in (
            "humanSLChosenMoveProp", "humanSLChosenMovePiklLambda", "humanSLRootExploreProbWeightless",
            "humanSLCpuctPermanent", "subtreeValueBiasFactor",
        )},
        "useUncertainty": _BOOL, "useNoisePruning": _BOOL,
    }),
})
_OPPONENT = _object({
    "rung": _integer(1, 41), "rank_name": _string(512, 1),
    "config_snapshot": _object({
        "config_digest": _TOKEN, "config_version": _TOKEN,
        "recipe_identity": _TOKEN, "recipe": _LADDER_RECIPE,
    }),
    "certification_status": _string(64, 1), "availability": _string(64, 1),
    "route": _enum("local", "server"),
}, ("rung", "rank_name", "config_snapshot", "certification_status", "availability", "route"))
_LADDER_RECORD = _object({
    **{key: value for key, value in _GAME_FIELDS.items() if key in {
        "sgf_content", "result", "board_size", "rules", "komi", "move_count", "player_black", "player_white",
        "black_rank", "white_rank", "title", "event", "round_name", "game_date",
    }},
    "source": _enum("play_ai"), "category": _enum("game"), "game_type": _enum("ai_ladder_ranked"),
}, ("sgf_content", "result", "board_size", "rules", "komi", "move_count", "player_black", "player_white", "source", "category", "game_type"))


def _spec(method, path, arguments=None, body=None, params=None, *, optional_body=False):
    return {
        "method": method, "path": "/api/v1/" + path,
        "arguments": _object(arguments or {}, (arguments or {}).keys()),
        "json": body, "params": params or _NO_FIELDS, "optional_body": optional_body,
    }


# This is the complete allowlist. Additions require an explicit endpoint schema.
OPERATIONS = {
    "phone_challenge": _spec("POST", "auth/phone/challenges", body=_object({
        "phone": _string(32, 1), "purpose": _enum("bind"),
        "flow_id": _string(128, 22, pattern=r"[A-Za-z0-9_-]+"),
    }, ("phone", "purpose", "flow_id"))),
    "phone_status": _spec("GET", "auth/phone/status"),
    "phone_bind": _spec("POST", "auth/phone/bind", body=_object({
        **_PHONE_CODE, "current_password": _nullable(("secret",)),
    }, _PHONE_CODE.keys())),
    "phone_password": _spec("POST", "auth/phone/password", body=_object({
        **_PHONE_CODE, "new_password": ("secret",),
    }, (*_PHONE_CODE.keys(), "new_password"))),
    "billing_catalog": _spec("GET", "billing/catalog"),
    "billing_usage": _spec("GET", "billing/usage"),
    "billing_quote": _spec("POST", "billing/quotes", body=_object({
        **_POSITION_INPUT, "kind": _enum("report", "position"),
    }, ("kind", "profile"))),
    "billing_create_order": _spec("POST", "billing/orders", body=_object({
        "sku": _enum("membership_plus", "membership_pro", "membership_max", "topup_10", "topup_30", "topup_100"),
        "provider": _nullable(_enum("mock", "live", "wechat")), "idempotency_key": _TOKEN,
    }, ("sku", "idempotency_key"))),
    "billing_list_orders": _spec("GET", "billing/orders"),
    "billing_get_order": _spec("GET", "billing/orders/{order_id}", {"order_id": _SEGMENT}),
    "billing_cancel_order": _spec("POST", "billing/orders/{order_id}/cancel", {"order_id": _SEGMENT}),
    "paid_position": _spec("POST", "analysis/positions", body=_object({
        **_POSITION_INPUT, "quote_token": _string(8192), "idempotency_key": _TOKEN,
    }, ("profile", "quote_token", "idempotency_key"))),
    "paid_position_get": _spec("GET", "analysis/positions/{position_id}", {"position_id": _ID}),
    "baipu_history_list": _spec("GET", "baipu/history", params=_object({"limit": _integer(1, 100)})),
    "baipu_history_get": _spec("GET", "baipu/history/{record_id}", {"record_id": _HEX64}),
    "baipu_history_sync": _spec("PUT", "baipu/history/{record_id}/sync", {"record_id": _HEX64}, body=_object({
        "sgf_content": _SGF, "source_id": _string(128), "name": _TEXT, "sgf_sha256": _HEX64,
        "replay_version": _integer(1), "total": _integer(1), "k": _integer(),
        "writer_id": _TOKEN, "writer_seq": _integer(), "expected_revision": _integer(),
    }, ("sgf_content", "sgf_sha256", "replay_version", "total", "k", "writer_id", "writer_seq", "expected_revision"))),
    "get_levels": _spec("GET", "tsumego/levels"),
    "get_problems": _spec("GET", "tsumego/levels/{level}/categories/{category}", {"level": _SEGMENT, "category": _SEGMENT}, params=_object({
        "offset": _integer(), "limit": _integer(1, 1000),
    })),
    "get_all_problems": _spec("GET", "tsumego/levels/{level}/problems", {"level": _SEGMENT}, params=_object({"page": _PAGE, "page_size": _integer(1, 200)})),
    "get_problem": _spec("GET", "tsumego/problems/{problem_id}", {"problem_id": _SEGMENT}),
    "get_progress": _spec("GET", "tsumego/progress"),
    "update_progress": _spec("POST", "tsumego/progress/{problem_id}", {"problem_id": _SEGMENT}, body=_object({
        "completed": _BOOL, "attempts": _integer(), "lastDuration": _nullable(_integer()),
    }, ("completed", "attempts"))),
    "search_kifu": _spec("GET", "kifu/albums", params=_object({
        "q": _nullable(_TEXT), "player_id": _nullable(_ID), "page": _PAGE,
        "page_size": _integer(1, 100), "lang": _string(32),
    })),
    "get_kifu": _spec("GET", "kifu/albums/{album_id}", {"album_id": _ID}, params=_object({"lang": _string(32)})),
    "get_kifu_analysis": _spec("GET", "kifu/albums/{album_id}/analysis", {"album_id": _ID}),
    "list_user_games": _spec("GET", "user-games/", params=_object({
        "page": _PAGE, "page_size": _integer(1, 1000),
        **{key: _nullable(_TEXT) for key in ("category", "source", "q")}, "sort": _string(64),
    })),
    "create_user_game": _spec("POST", "user-games/", body=_object(_GAME_FIELDS, ("sgf_content", "source"))),
    "get_user_game": _spec("GET", "user-games/{game_id}", {"game_id": _SEGMENT}),
    "delete_user_game": _spec("DELETE", "user-games/{game_id}", {"game_id": _SEGMENT}),
    "get_ai_ladder_status": _spec("GET", "ai-ladder/status"),
    "reserve_ai_ladder_game": _spec("POST", "ai-ladder/games/reserve", body=_object({
        **_CLOCK, **_KEY_FIELDS, "game_id": _string(32, 1, pattern=r"[\w.~-]+"),
    }, ("game_id", "reservation_key"))),
    "activate_ai_ladder_game": _spec("POST", "ai-ladder/games/{game_id}/activate", {"game_id": _SEGMENT}, body=_object({**_KEY_FIELDS, "session_id": _TOKEN}, ("reservation_key", "session_id"))),
    "mark_ai_ladder_game_pending": _spec("POST", "ai-ladder/games/{game_id}/pending-settlement", {"game_id": _SEGMENT}, body=_object(_KEY_FIELDS, ("reservation_key",))),
    "send_ai_ladder_heartbeat": _spec("POST", "ai-ladder/games/{game_id}/heartbeat", {"game_id": _SEGMENT}, body=_object(_KEY_FIELDS, ("reservation_key",))),
    "cancel_ai_ladder_reservation": _spec("DELETE", "ai-ladder/games/{game_id}/reservation", {"game_id": _SEGMENT}, body=_object(_KEY_FIELDS, ("reservation_key",))),
    "get_ai_ladder_game_status": _spec("GET", "ai-ladder/games/{game_id}/status", {"game_id": _SEGMENT}),
    "end_ai_ladder_game": _spec("POST", "ai-ladder/games/{game_id}/end", {"game_id": _SEGMENT}, body=_object({"reason": _enum("user_resigned")}, ("reason",))),
    "count_ai_ladder_game": _spec("POST", "ai-ladder/games/{game_id}/count", {"game_id": _SEGMENT}, body=_object({
        **_KEY_FIELDS, "sgf_content": _string(100000, 1, multiline=True), "trigger": _enum("manual", "double_pass"),
    }, ("reservation_key", "sgf_content", "trigger"))),
    "get_ai_ladder_territory": _spec("GET", "ai-ladder/games/{game_id}/territory", {"game_id": _SEGMENT}),
    "request_ai_ladder_territory": _spec("POST", "ai-ladder/games/{game_id}/territory", {"game_id": _SEGMENT}, body=_object({
        **_KEY_FIELDS, "sgf_content": _string(100000, 1, multiline=True), "request_id": _string(64, 1),
    }, ("reservation_key", "sgf_content", "request_id"))),
    "settle_ai_ladder_ranked": _spec("POST", "ai-ladder/settlements", body=_object({
        "game_id": _string(64, 1, pattern=r"[\w.~-]+"), "user_color": _enum("B", "W"),
        "result": _enum("win", "loss", "inconclusive"), "game_type": _string(64, 1),
        "opponent": _nullable(_OPPONENT), "engine_stalled": _BOOL,
        "device_id": _nullable(_string(64)), "reservation_key": _nullable(_TOKEN),
        "game_record": _nullable(_LADDER_RECORD),
    }, ("game_id", "user_color", "result", "game_type"))),
    "get_growth_summary": _spec("GET", "growth/summary", params=_object({"days": _integer(1, 365)})),
    "get_growth_diagnosis": _spec("GET", "growth/diagnosis", params=_object({"days": _integer(1, 365), "reports": _integer(1, 50)})),
    "get_growth_activity": _spec("GET", "growth/activity", params=_object({"days": _integer(1, 365), "tz_offset": _integer(-720, 840)})),
    "list_reports": _spec("GET", "reports/"),
    "get_report_summary": _spec("GET", "reports/summary"),
    "get_report": _spec("GET", "reports/{task_id}", {"task_id": _ID}),
    "create_report": _spec("POST", "reports/", body=_object({
        **_REPORT_PAYMENT, "user_game_id": _SEGMENT, "report_type": _string(64), "force": _BOOL,
    }, ("user_game_id",))),
    "retry_report": _spec("POST", "reports/{task_id}/retry", {"task_id": _ID}, body=_object(_REPORT_PAYMENT), optional_body=True),
    "get_report_moves": _spec("GET", "reports/{task_id}/moves", {"task_id": _ID}),
}


# These exact cloud reads are public at their owning endpoints. The broker must
# allow guest access without fetching a bearer or requiring a real-user lease.
PUBLIC_OPERATIONS = frozenset({
    "get_levels", "get_problems", "get_all_problems", "get_problem",
    "search_kifu", "get_kifu", "get_kifu_analysis",
})


def _bounded_tree(value, depth=0, budget=None):
    """Reject cycles, container explosions and non-JSON values before serialization."""
    budget = [10000] if budget is None else budget
    budget[0] -= 1
    if depth > 10 or budget[0] < 0:
        raise ValueError("Go operation data is too deeply nested or too large")
    if type(value) is dict:
        if len(value) > 128 or any(type(key) is not str or len(key) > 128 for key in value):
            raise ValueError("Invalid Go object fields")
        for item in value.values():
            _bounded_tree(item, depth + 1, budget)
    elif type(value) is list:
        if len(value) > 4096:
            raise ValueError("Go list is too large")
        for item in value:
            _bounded_tree(item, depth + 1, budget)
    elif type(value) is str:
        if len(value) > 1048576 or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("Invalid or oversized Go string")
    elif value is not None and type(value) not in (bool, int, float):
        raise ValueError("Go operation accepts JSON data only")
    elif type(value) is float and not math.isfinite(value):
        raise ValueError("Go numbers must be finite")
    elif type(value) is int and abs(value) > 9007199254740991:
        raise ValueError("Go integer is too large")


def _validate(value, schema):
    kind = schema[0]
    if kind == "nullable":
        return None if value is None else _validate(value, schema[1])
    if kind == "object":
        if type(value) is not dict or set(value) - schema[1].keys() or not schema[2] <= value.keys():
            raise ValueError("Missing or unknown Go operation fields")
        return {key: _validate(item, schema[1][key]) for key, item in value.items()}
    if kind == "string":
        if type(value) is not str or not schema[1] <= len(value) <= schema[2]:
            raise ValueError("Invalid Go string length")
        if any((ord(char) < 32 and not (schema[3] and char in "\n\r\t")) or ord(char) == 127 for char in value):
            raise ValueError("Invalid Go string characters")
        if schema[4] and (not re.fullmatch(schema[4], value) or value in (".", "..")):
            raise ValueError("Invalid Go path segment or identifier")
    elif kind == "secret":
        if type(value) is not str or len(value) > 1024 or "\x00" in value:
            raise ValueError("Invalid Go credential field")
    elif kind == "integer":
        if type(value) is not int or not schema[1] <= value <= schema[2]:
            raise ValueError("Invalid Go integer")
    elif kind == "number":
        if type(value) not in (int, float) or not math.isfinite(value) or not schema[1] <= value <= schema[2]:
            raise ValueError("Invalid Go number")
    elif kind == "boolean":
        if type(value) is not bool:
            raise ValueError("Invalid Go boolean")
    elif kind == "enum":
        if type(value) is not str or value not in schema[1]:
            raise ValueError("Invalid Go choice")
    else:
        raise ValueError("Unknown Go field schema")
    return value


def describe(operation, arguments, json=None, params=None):
    """Return a fixed method/path and validated copies of body and query data."""
    if type(operation) is not str or operation not in OPERATIONS:
        raise ValueError("Unknown Go operation")
    _bounded_tree({"arguments": arguments, "json": json, "params": params})
    spec = OPERATIONS[operation]
    arguments = _validate(arguments, spec["arguments"])
    if spec["json"] is None:
        if json is not None:
            raise ValueError("This Go operation has no JSON body")
        body = None
    elif json is None and spec["optional_body"]:
        body = None
    else:
        body = _validate(json, spec["json"])
    query = None if params is None else _validate(params, spec["params"])
    # SGF/history support 1 MiB of characters, including multibyte text and JSON
    # escaping. This envelope bound intentionally leaves room for those payloads.
    if len(_json.dumps([body, query], ensure_ascii=False, allow_nan=False).encode("utf-8")) > 8 * 1048576:
        raise ValueError("Go operation payload is too large")
    return spec["method"], spec["path"].format(**arguments), body, query


def classify(method, path, json=None, params=None):
    """Map an existing RemoteClient request to one validated named operation."""
    if type(method) is not str or type(path) is not str or len(path) > 1024:
        raise ValueError("Invalid Go method or path")
    if not path.startswith("/api/v1/") or any(char in path for char in "%?#\\"):
        raise ValueError("Go target must be a fixed API path")
    for operation, spec in OPERATIONS.items():
        if method != spec["method"]:
            continue
        names = re.findall(r"\{(\w+)\}", spec["path"])
        pattern = re.escape(spec["path"])
        for name in names:
            pattern = pattern.replace(re.escape("{" + name + "}"), r"([^/]+)")
        match = re.fullmatch(pattern, path)
        if match is None:
            continue
        arguments = dict(zip(names, match.groups()))
        for name, value in arguments.items():
            if spec["arguments"][1][name][0] == "integer":
                if not re.fullmatch(r"[1-9][0-9]{0,9}", value):
                    raise ValueError("Invalid Go integer path identifier")
                arguments[name] = int(value)
        describe(operation, arguments, json=json, params=params)
        return operation, arguments
    raise ValueError("Go method/path is not an allowed business operation")
