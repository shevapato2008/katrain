"""Bounded hourly overlap observation; historical traversal remains explicit.

There is no reliable source updated_at or upload-time filter. playTime is
interpreted in Asia/Shanghai by product convention, not by an API zone claim.
The caller holds staging_writer_lock across Stage construction and this call.
"""

import asyncio
from datetime import datetime, timedelta
import hashlib
import inspect
import json
import logging
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.source_19x19 import SourceBudgetExceeded, SourceError, SourceRateLimited
from katrain.kifu_ingest.staging import Stage, _id

SOURCE_TIMEZONE = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)
# Only identity, match, result and length fields; no mutable engagement counters.
METADATA_FIELDS = (
    "id",
    "pb",
    "pw",
    "blackName",
    "whiteName",
    "player_black",
    "player_white",
    "blackLevel",
    "whiteLevel",
    "black_rank",
    "white_rank",
    "br",
    "wr",
    "gamename",
    "event",
    "playTime",
    "date_played",
    "datePlayed",
    "gameRound",
    "round_name",
    "ro",
    "place",
    "pc",
    "boardSize",
    "board_size",
    "sz",
    "rule",
    "rules",
    "ru",
    "komi",
    "km",
    "handicap",
    "ha",
    "gameResult",
    "result",
    "re",
    "moveNum",
    "moveCount",
    "gameLength",
)


def metadata_sha256(metadata):
    stable = {key: metadata[key] for key in METADATA_FIELDS if key in metadata}
    return hashlib.sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def match_time(metadata):
    """Require the supplied complete date/time; never infer missing midnight."""
    try:
        play = metadata["playTime"]
        date, clock = play["date"], play["time"]
        values = [date[k] for k in ("year", "month", "day")] + [clock[k] for k in ("hour", "minute", "second")]
        if any(type(v) is not int for v in values):
            return None
        nano = clock.get("nano", 0)
        if type(nano) is not int or not 0 <= nano < 1_000_000_000:
            return None
        return datetime(*values, microsecond=nano // 1000, tzinfo=SOURCE_TIMEZONE)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _validate_sgf(raw):
    if not isinstance(raw, str) or not raw.lstrip().startswith("(;") or not raw.rstrip().endswith(")"):
        raise ValueError("invalid SGF structure")
    if len(raw.encode("utf-8")) > 16 * 1024 * 1024:
        raise ValueError("SGF exceeds 16 MiB limit")
    try:
        SGF.parse_sgf(raw)
    except (ValueError, IndexError, AttributeError, TypeError) as exc:
        raise ValueError("invalid SGF") from exc
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _quarantine_change(stage, item, before, metadata, raw, digest, observed_at):
    """One bounded variant per ID until an operator explicitly restores it."""
    directory = stage._directory("source-changes")
    external_id = item["external_id"]
    raw_path = None
    if raw is not None:
        raw_path = directory / f"{external_id}-{digest}.sgf"
        stage._atomic(raw_path, raw.encode("utf-8"))
    record_path = directory / f"{external_id}-{uuid4().hex}.json"
    record = {
        "external_id": external_id,
        "observed_at": observed_at,
        "before": before,
        "after": {
            "metadata": metadata,
            "metadata_sha256": metadata_sha256(metadata),
            "raw_sha256": digest,
            "raw_sgf_path": str(raw_path.relative_to(stage.root)) if raw_path is not None else None,
            "raw_status": "fetched" if raw is not None else "not_fetched",
        },
    }
    stage._atomic(record_path, json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    item["recent"].update(
        terminal=True, classification="source_changed", change_evidence=str(record_path.relative_to(stage.root))
    )
    # A published item's successful status and originals must survive isolation.
    stage._persist()


def _before_observation(item):
    observation = item["recent"]
    metadata = observation.get("metadata", item["metadata"])
    return {
        "metadata": metadata,
        "metadata_sha256": observation.get("metadata_sha256") or metadata_sha256(metadata),
        "raw_sha256": observation.get("raw_sha256") or item.get("raw_sha256"),
        "raw_sgf_path": item.get("raw_sgf_path"),
    }


async def discover_recent(
    source,
    stage: Stage,
    known_ids=(),
    *,
    published_ids=(),
    published_lookup=None,
    excluded_ids=(),
    max_head_pages=5,
    max_downloads=100,
    max_rechecks=20,
    max_requests=160,
    window_days=7,
    deadline=None,
    clock=None,
    wall_clock=None,
):
    """Observe finite head pages, then window-scoped SGFs, without rolling work.

    known_ids and published_ids mean catalog/native-receipt publication only.
    StateStore discovered/downloaded membership is deliberately not publication.
    eligible_ids are downloaded, unchanged, unpublished window candidates and
    include previously prepared-but-unpublished items deferred by other budgets.
    published_lookup receives only the finite candidate ID set after the scan.
    """
    for name, value, maximum in (
        ("max_head_pages", max_head_pages, 10),
        ("max_downloads", max_downloads, 100),
        ("max_rechecks", max_rechecks, 20),
        ("max_requests", max_requests, 240),
    ):
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError(f"{name} must be between 0 and {maximum}")
    if type(window_days) is not int or not 1 <= window_days <= 14:
        raise ValueError("window_days must be between 1 and 14")
    clock, wall_clock = clock or time.monotonic, wall_clock or time.time
    deadline = min(deadline, clock() + 600) if deadline is not None else clock() + 600
    if hasattr(source, "deadline"):
        source.deadline = min(source.deadline, deadline) if source.deadline is not None else deadline
    request_start = getattr(source, "requests", 0)
    if hasattr(source, "max_requests"):
        source.max_requests = min(source.max_requests, request_start + max_requests)
    now = datetime.fromtimestamp(wall_clock(), SOURCE_TIMEZONE)
    lower = now - timedelta(days=window_days)
    published = {_id(i) for i in (*known_ids, *published_ids)}
    excluded = {_id(i) for i in excluded_ids}
    errors, changed, quarantined = [], [], []
    candidates, head_ids = {}, set()
    checked_ids = set()
    downloaded = 0
    coverage = dict(
        head_pages=0,
        head_unique_ids=0,
        unknown_match_time=0,
        out_of_window=0,
        excluded=0,
        head_page_cap=False,
        boundary_in_window=False,
        sgf_attempts=0,
        sgf_attempt_cap=False,
        source_budget_exhausted=False,
        time_budget_exhausted=False,
        recheck_selected=0,
        recheck_deferred=0,
        oldest_recheck_age_seconds=None,
        source_http_attempts=0,
        terminal_count=0,
    )
    head = dict(stage.manifest.get("recent_head", {}))
    head.update(started_at=wall_clock(), complete=False, window_start=lower.isoformat(), window_end=now.isoformat())
    source_stopped = False

    def save_head():
        stage.manifest["recent_head"] = head
        stage.manifest["head"] = head
        stage._persist()

    def error(exc, **context):
        errors.append(
            {
                **context,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "code": getattr(exc, "code", None),
                "source_message": getattr(exc, "source_message", None),
            }
        )

    def budget(exc):
        coverage["source_budget_exhausted"] = True
        coverage["time_budget_exhausted"] = clock() >= deadline or "time" in str(exc)

    async def request(method, *args):
        remaining = deadline - clock()
        if remaining <= 0:
            raise SourceBudgetExceeded("source time budget exhausted")
        try:
            return await asyncio.wait_for(method(*args), remaining)
        except asyncio.TimeoutError as exc:
            raise SourceBudgetExceeded("source time budget exhausted") from exc

    def rate_limit(exc):
        nonlocal source_stopped
        stage.manifest["source_next_retry_at"] = wall_clock() + exc.retry_after
        source_stopped = True
        stage._persist()

    def result():
        eligible = []
        for external_id in candidates:
            item = stage.manifest["items"].get(external_id)
            if (
                item
                and external_id not in published
                and item.get("raw_sgf_path")
                and item.get("recent", {}).get("raw_sha256")
                and item.get("recent", {}).get("metadata_sha256") == metadata_sha256(candidates[external_id])
                and not item.get("recent", {}).get("terminal")
                and not item.get("recent", {}).get("retry_pending")
            ):
                eligible.append(external_id)
        coverage["source_http_attempts"] = getattr(source, "requests", request_start) - request_start
        coverage["terminal_count"] = sum(bool(i.get("recent", {}).get("terminal")) for i in stage.items())
        coverage["last_observed_at"] = stage.manifest.get("recent_last_observed_at")
        head["coverage"] = dict(coverage)
        save_head()
        logger.info("recent source overlap coverage %s", json.dumps(coverage, sort_keys=True))
        return {
            "status": (
                "partial"
                if (
                    errors
                    or source_stopped
                    or coverage["head_page_cap"]
                    or coverage["sgf_attempt_cap"]
                    or coverage["source_budget_exhausted"]
                )
                else "head_complete"
            ),
            "items": stage.items(),
            "downloaded": downloaded,
            "failures": len(errors),
            "errors": errors,
            "last_error": errors[-1]["error"] if errors else None,
            "head": head,
            "rolling": stage.manifest.get("rolling", {}),
            "deferred_until": stage.manifest.get("source_next_retry_at"),
            "candidate_ids": list(candidates),
            "eligible_ids": eligible,
            "changed_ids": changed,
            "quarantined_ids": sorted(
                set(quarantined)
                | {
                    external_id
                    for external_id in candidates
                    if stage.manifest["items"].get(external_id, {}).get("recent", {}).get("terminal")
                }
            ),
            "checked_ids": sorted(checked_ids),
            "coverage": coverage,
        }

    if (stage.manifest.get("source_next_retry_at") or 0) > wall_clock():
        source_stopped = True
        return result()
    stage.manifest["source_next_retry_at"] = None

    # Collect all bounded head candidates before any SGF can fail or consume time.
    for page in range(max_head_pages):
        try:
            games = await request(source.fetch_page, page)
        except SourceBudgetExceeded as exc:
            budget(exc)
            break
        except SourceRateLimited as exc:
            error(exc, phase="head", page=page)
            rate_limit(exc)
            break
        except SourceError as exc:
            error(exc, phase="head", page=page)
            break
        coverage["head_pages"] += 1
        boundary_in_window = False
        for metadata in games:
            external_id = _id(metadata.get("id"))
            played = match_time(metadata)
            boundary_in_window |= played is not None and lower <= played <= now
            if external_id in head_ids:
                continue
            head_ids.add(external_id)
            if external_id in excluded:
                coverage["excluded"] += 1
                continue
            played = match_time(metadata)
            if played is None:
                coverage["unknown_match_time"] += 1
            elif not lower <= played <= now:
                coverage["out_of_window"] += 1
            else:
                boundary_in_window = True
                candidates[external_id] = metadata
        coverage["boundary_in_window"] = boundary_in_window
        head.update(last_page=page, games=len(games))
        if not games:
            head.update(complete=True, completed_at=wall_clock())
            break
    else:
        coverage["head_page_cap"] = bool(max_head_pages)
        head.update(complete=bool(max_head_pages), completed_at=wall_clock() if max_head_pages else None)
    coverage["head_unique_ids"] = len(head_ids)
    save_head()

    absent = []
    for item in stage.items():
        observation = item.get("recent", {})
        external_id = item["external_id"]
        if external_id in head_ids or external_id in excluded or not observation or observation.get("terminal"):
            continue
        metadata = observation.get("metadata", item["metadata"])
        played = match_time(metadata)
        if played is not None and lower <= played <= now:
            absent.append(item)
    absent.sort(key=lambda i: (i["recent"].get("last_checked_at") or 0, i["external_id"]))
    for item in absent[:max_rechecks]:
        candidates[item["external_id"]] = item["recent"].get("metadata", item["metadata"])
    coverage["recheck_selected"] = min(len(absent), max_rechecks)
    coverage["recheck_deferred"] = max(0, len(absent) - max_rechecks)
    if absent:
        coverage["oldest_recheck_age_seconds"] = max(
            0, wall_clock() - (absent[0]["recent"].get("last_checked_at") or wall_clock())
        )

    if published_lookup is not None and candidates and not source_stopped:
        found = published_lookup(set(candidates))
        if inspect.isawaitable(found):
            found = await request(lambda: found)
        published.update(_id(i) for i in found)

    for external_id, metadata in candidates.items():
        item = stage.manifest["items"].get(external_id)
        if item is None:
            item = stage.remember(metadata)
        if "recent" not in item:
            item["recent"] = {"scope": "hourly", "last_checked_at": None, "terminal": False}
        if item.get("status") == "failed" and item.get("next_retry_at") is None:
            item["recent"].update(
                terminal=True, classification=item["recent"].get("classification", "preparation_quarantine")
            )
        # Metadata observation is durable before SGF attempts or their budgets.
        # Keep its stable baseline separate from this round's full source values.
        observation = item["recent"]
        before = _before_observation(item)
        observation.setdefault("metadata", before["metadata"])
        observation.setdefault("metadata_sha256", before["metadata_sha256"])
        observation.update(
            seen_metadata=metadata, seen_metadata_sha256=metadata_sha256(metadata), last_seen_at=wall_clock()
        )
        if not observation.get("terminal") and before["metadata_sha256"] != observation["seen_metadata_sha256"]:
            # Metadata alone proves a source revision. Never spend a request or
            # bypass Retry-After to obtain optional SGF evidence for it.
            _quarantine_change(stage, item, before, metadata, None, None, wall_clock())
            changed.append(external_id)
            quarantined.append(external_id)
    stage._persist()

    def priority(external_id):
        item = stage.manifest["items"][external_id]
        observation = item["recent"]
        unobserved = not observation.get("raw_sha256")
        return (
            0 if unobserved and external_id not in published else 1,
            observation.get("last_checked_at") or 0,
            external_id,
        )

    for external_id in sorted(candidates, key=priority):
        if source_stopped or coverage["source_budget_exhausted"]:
            break
        item = stage.manifest["items"][external_id]
        observation = item["recent"]
        if observation.get("terminal"):
            quarantined.append(external_id)
            continue
        if (item.get("next_retry_at") or 0) > wall_clock():
            continue
        if coverage["sgf_attempts"] >= max_downloads:
            coverage["sgf_attempt_cap"] = True
            break
        metadata = candidates[external_id]
        coverage["sgf_attempts"] += 1
        try:
            raw = await request(source.fetch_sgf, external_id)
            digest = _validate_sgf(raw)
        except SourceBudgetExceeded as exc:
            budget(exc)
            break
        except SourceRateLimited as exc:
            error(exc, phase="sgf", external_id=external_id)
            rate_limit(exc)
            break
        except (SourceError, ValueError) as exc:
            error(exc, phase="sgf", external_id=external_id)
            observation["last_checked_at"] = wall_clock()
            observation["retry_pending"] = True
            item["attempts"] += 1
            observation["failure_attempts"] = observation.get("failure_attempts", 0) + 1
            terminal = (
                isinstance(exc, ValueError)
                or not getattr(exc, "retryable", True)
                or observation["failure_attempts"] >= 3
            )
            observation.update(
                terminal=terminal,
                classification="terminal_source_error" if terminal else "transient_source_error",
                error_code=getattr(exc, "code", None),
                source_message=getattr(exc, "source_message", None),
            )
            # Do not erase a published successful status; failures remain observable here.
            if external_id not in published:
                item["status"] = "failed"
            item["last_error"] = str(exc)
            item["next_retry_at"] = (
                None if terminal else wall_clock() + min(21600, 300 * 2 ** (observation["failure_attempts"] - 1))
            )
            if terminal:
                quarantined.append(external_id)
            stage._persist()
            continue
        checked_ids.add(external_id)
        stamp = wall_clock()
        observation["last_checked_at"] = stamp
        stage.manifest["recent_last_observed_at"] = stamp
        before = _before_observation(item)
        new_meta_hash = metadata_sha256(metadata)
        if before["raw_sha256"] is not None and before["raw_sha256"] != digest:
            _quarantine_change(stage, item, before, metadata, raw, digest, stamp)
            changed.append(external_id)
            quarantined.append(external_id)
            continue
        observation.update(metadata=metadata, metadata_sha256=new_meta_hash, raw_sha256=digest, retry_pending=False)
        # Published items with no original are observations only; no prepare artifact.
        if external_id not in published and not item.get("raw_sgf_path"):
            stage.save_sgf(external_id, raw)
            downloaded += 1
        elif external_id not in published:
            item.update(status="downloaded", next_retry_at=None)
        stage._persist()
    return result()
