"""Grafana dashboards the performance page may embed, read once from the operator's environment.

`KATRAIN_ADMIN_GRAFANA_DASHBOARDS` is a JSON list of `{"title", "url"}`. Every URL must share one
http(s) origin, which becomes the only `frame-src` the admin page allows. Nothing here contacts
Grafana: "configured" means an operator named it, not that it is online. Credentials never ride
in the URL (the admin token is never forwarded; Grafana keeps its own login).
"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import parse_qsl, urlparse

ENV_VAR = "KATRAIN_ADMIN_GRAFANA_DASHBOARDS"
MAX_DASHBOARDS = 12
MAX_TITLE = 40
_SECRET_KEY = re.compile(r"token|key|auth|pass|secret", re.IGNORECASE)


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("dashboard url must be an absolute http(s) url")
    if parsed.username or parsed.password or any(_SECRET_KEY.search(key) for key, _ in parse_qsl(parsed.query)):
        raise ValueError("dashboard url must not carry credentials")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"{parsed.scheme}://{host}{f':{parsed.port}' if parsed.port else ''}"


def _parse(raw: str) -> tuple[str, list[dict]]:
    entries = json.loads(raw)
    if not isinstance(entries, list) or not entries:
        raise ValueError("configure at least one dashboard")
    if len(entries) > MAX_DASHBOARDS:
        raise ValueError(f"configure at most {MAX_DASHBOARDS} dashboards")
    origins, dashboards = set(), []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"title", "url"}:
            raise ValueError("each dashboard needs exactly title and url")
        title, url = entry["title"], entry["url"]
        if not isinstance(title, str) or not 0 < len(title.strip()) <= MAX_TITLE:
            raise ValueError(f"dashboard title must be 1-{MAX_TITLE} characters")
        if not isinstance(url, str):
            raise ValueError("dashboard url must be an absolute http(s) url")
        origins.add(_origin(url))
        dashboards.append({"id": str(index), "title": title.strip(), "url": url})
    if len(origins) != 1:
        raise ValueError("all dashboards must share the same origin")
    return origins.pop(), dashboards


def load_grafana(raw: str | None = None) -> dict:
    raw = os.getenv(ENV_VAR) if raw is None else raw
    if raw is None or not raw.strip():
        return {"state": "unconfigured", "error": None, "origin": None, "dashboards": []}
    try:
        origin, dashboards = _parse(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return {"state": "invalid", "error": f"{ENV_VAR}: {exc}", "origin": None, "dashboards": []}
    return {"state": "configured", "error": None, "origin": origin, "dashboards": dashboards}
