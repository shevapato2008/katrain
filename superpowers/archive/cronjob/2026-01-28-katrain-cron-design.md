# katrain-cron: Independent Scheduled Task Service

**Date:** 2026-01-28
**Status:** Design

## 1. Problem Statement

Current pain points in katrain-web's live broadcasting module:

1. **Translation blocking**: LLM translation is triggered on-demand when users open the live page or switch languages. All text is sent to the LLM in one batch, causing page freezes and frequent failures.
2. **Analysis bottleneck**: The analyzer sends requests to KataGo serially (`limit=1`), meaning KataGo processes one position at a time. GPU utilization oscillates between 0% and 100% — batch inference never activates.
3. **Coupling**: Polling, translation, and analysis all run inside the web process. A failure in any of these affects user-facing API responsiveness.

## 2. Solution Overview

Introduce `katrain-cron`, an independent Python service that handles all background tasks: match fetching, translation, and KataGo analysis. It shares only the PostgreSQL database with `katrain-web` — no code imports between the two.

```
┌─────────────────────────────────────────────────────────┐
│                     PostgreSQL                          │
│  (matches, analysis, translations)                      │
└──────────┬──────────────────────┬───────────────────────┘
           │                      │
     ┌─────┴──────┐        ┌──────┴───────┐
     │ katrain-web│        │ katrain-cron │
     │  (FastAPI) │        │ (Scheduler)  │
     └─────┬──────┘        └──┬───────┬───┘
           │                  │       │
      KataGo 8000         ┌──┴──┐ ┌──┴──────┐
      (user play)         │Jobs │ │AnalyzeJob│
                          └──┬──┘ └──┬───────┘
                             │       │
                   ┌─────────┴───┐ ┌─┴──────────┐
                   │ Qwen LLM    │ │ KataGo 8002│
                   │ (translate) │ │ (analysis)  │
                   └─────────────┘ └─────────────┘
```

## 3. Service Responsibilities

| Service | Responsibilities | Does NOT do |
|---------|-----------------|-------------|
| **katrain-web** | HTTP API, WebSocket, frontend, user gameplay (KataGo 8000), read DB + memory cache | No polling, no LLM calls, no batch analysis |
| **katrain-cron** | Match fetching, move polling, LLM translation, KataGo analysis (8002) | No HTTP API |
| **katago-web** | User gameplay analysis (port 8000, GPU 0) | - |
| **katago-cron** | Batch match analysis (port 8002, GPU 1) | - |

## 4. katrain-cron Project Structure

```
katrain/cron/
├── __init__.py
├── __main__.py              # Entry: python -m katrain.cron
├── scheduler.py             # APScheduler wrapper
├── config.py                # DB URL, job intervals, KataGo URL, LLM keys
├── db.py                    # Independent SQLAlchemy engine + session
├── models.py                # Independent DB model definitions (same tables)
├── clients/
│   ├── __init__.py
│   ├── xingzhen.py          # XingZhen API client (match list + moves)
│   └── katago.py            # KataGo HTTP client (send analysis requests)
├── translator.py            # Translation logic (DB lookup + LLM calls)
├── analysis_repo.py         # Analysis task DB operations
└── jobs/
    ├── __init__.py
    ├── base.py              # BaseJob class
    ├── fetch_list.py        # FetchListJob: pull match list from APIs
    ├── poll_moves.py        # PollMovesJob: poll live game moves
    ├── translate.py         # TranslateJob: pre-translate all names
    └── analyze.py           # AnalyzeJob: flight-window KataGo analysis
```

### Key Principles

- `katrain/cron/` does NOT import anything from `katrain/web/`
- DB models map to the same PostgreSQL tables, but code is independently maintained
- Schema changes require updating both sides — mitigated by unified Alembic migrations
- Adding a new job: create file in `jobs/`, inherit `BaseJob`, implement `run()`, add interval in `config.py`
- SQLAlchemy connection pool size ≥ 20 (AnalyzeJob alone uses up to 16 concurrent DB connections)

## 5. Job Scheduling

### BaseJob Interface

```python
class BaseJob:
    name: str               # Log identifier
    interval_seconds: int   # Schedule interval
    enabled: bool           # Config toggle

    async def run(self):    # Subclass implements
        raise NotImplementedError
```

### Job Registry

| Job | Interval | Description |
|-----|----------|-------------|
| `FetchListJob` | 60s | Pull match list from XingZhen API, write to DB |
| `PollMovesJob` | 3s | Poll live games for new moves, create pending analysis tasks |
| `TranslateJob` | 120s | Scan missing translations, call LLM one-by-one |
| `AnalyzeJob` | Persistent loop | Flight-window KataGo analysis (see Section 7) |

## 6. Translation Job Design

### Current Problem
- User request triggers LLM synchronously -> page freezes
- All names sent to LLM in one batch -> easy to fail
- Direct LLM translation of player names is unreliable (wrong romanization, wrong characters)

### Translation Strategy: Players vs Tournaments

Player names require **authoritative sources** (Wikipedia, national Go associations). Tournament names can use direct LLM translation.

| Type | Strategy | Source Priority |
|------|----------|----------------|
| **Player names** | Search-first: Wikipedia + Go association → LLM-assisted extraction | `manual > search+llm > llm > fuzzy_match` |
| **Tournament names** | Direct LLM translation (acceptable quality) | `manual > llm` |

### Source Priority Rules

- `manual`: User-submitted via `POST /api/v1/live/translations/learn`. **Never overwritten** by automated jobs.
- `search+llm`: Search results verified by LLM. High quality.
- `llm`: Direct LLM translation. Acceptable for tournaments, fallback for players.
- `fuzzy_match`: Fuzzy string match from existing DB. Lowest confidence.

TranslateJob **skips** any record where `source = 'manual'`.

### Player Name Translation Flow

```
TranslateJob — Player Names
│
├─ 1. Query DB: players from live/finished matches
│     WHERE source != 'manual' AND (any language is NULL)
│
├─ 2. For each untranslated player:
│
│   ├─ Step A: Search Wikipedia
│   │   Search: "{name} Go player" / "{name} 棋士" / "{name} 기사"
│   │   Extract: multilingual names from Wikipedia infobox / interwiki links
│   │   Example: "柯洁" → Wikipedia pages in zh/en/ja/ko all have the name
│   │
│   ├─ Step B: Search national Go association (by country)
│   │   CN → qipai.org.cn / weiqi.cc
│   │   JP → nihonkiin.or.jp / kansaikiin.jp
│   │   KR → baduk.or.kr
│   │   TW → weiqi.org.tw
│   │   Extract: official romanization, local name variants
│   │
│   ├─ Step C: LLM-assisted extraction
│   │   Feed search results to LLM as context
│   │   Prompt: "Based on these search results, provide the name
│   │            in en/cn/tw/jp/ko. Return JSON."
│   │   This is NOT blind translation — LLM extracts from real data
│   │
│   └─ Step D: Fallback — direct LLM translation
│       If search returns nothing (rare/amateur player)
│       Direct LLM translation as last resort, source="llm"
│
├─ 3. Write to DB with source="search+llm" or "llm"
│     Store llm_model version for auditing
│
└─ 4. Concurrency: asyncio.Semaphore(3) + rate limiting
```

### Tournament Name Translation Flow

```
TranslateJob — Tournament Names
│
├─ 1. Query DB: tournaments from live/finished matches
│     WHERE source != 'manual' AND (any language is NULL)
│
├─ 2. For each untranslated tournament:
│     Call LLM once, requesting all 5 languages
│     Input:  "第52期日本天元战预选A组"
│     Output: {"en": "52nd Japan Tengen Preliminary A", ...}
│
└─ 3. Write to DB, source="llm", store llm_model version
```

### Languages (5, extensible)
- `en` (English), `cn` (Simplified Chinese), `tw` (Traditional Chinese), `jp` (Japanese), `ko` (Korean)

### Efficiency

- **Players:** 1 search + 1 LLM call per name (search may involve 2-3 web requests)
- **Tournaments:** 1 LLM call per name
- **Concurrency:** Up to 3 names in parallel via Semaphore
- 100 new players: ~2-3 minutes (search + LLM, 3 concurrent)
- 20 new tournaments: ~15 seconds

### Failure Handling

- Search returns no results → fall back to direct LLM (Step D)
- LLM returns invalid JSON → entire name retried next cycle (2 min later)
- LLM returns partial results → save what we got, retry remaining next cycle
- LLM service down → circuit breaker (3 consecutive failures → 5 min cooldown)
- Rate limited (429) → exponential backoff

### User Manual Corrections

- Users submit corrections via `POST /api/v1/live/translations/learn` → stored with `source="manual"`
- TranslateJob skips `source="manual"` records — manual corrections are never overwritten
- Manual corrections propagate to TranslationCache on next 60s refresh cycle

### Result
- User opens page → translations already in DB → instant load
- New player appears → searched + translated within ~2-3 minutes
- Translation quality: based on authoritative sources, not blind LLM guessing
- User corrections: permanent, never overwritten by automation

## 7. Analysis Task Queue

### Required Database Setup

**Partial index** to prevent query degradation (10k+ historical tasks):

```sql
CREATE INDEX idx_analysis_pending_priority
ON live_analysis (priority DESC, created_at ASC)
WHERE status = 'pending';
```

**Unique constraint** for idempotent task insertion:

```sql
ALTER TABLE live_analysis
ADD CONSTRAINT uq_analysis_match_move UNIQUE (match_id, move_number);
```

**Task fetching query** uses `FOR UPDATE SKIP LOCKED` to prevent duplicate pickup (safe for future multi-instance):

```sql
SELECT * FROM live_analysis
WHERE status = 'pending'
ORDER BY priority DESC, created_at ASC
LIMIT :window_slots
FOR UPDATE SKIP LOCKED;

-- Immediately followed by:
UPDATE live_analysis SET status = 'running', started_at = NOW()
WHERE id IN (:selected_ids);
```

This ensures:
- Constant-time query regardless of table size (partial index)
- No duplicate task assignment even under concurrent access (row locking)
- Idempotent inserts (unique constraint prevents duplicate tasks per move)

### Priority System

| Priority | Value | Scenario |
|----------|-------|----------|
| `PRIORITY_LIVE_NEW` | 1000 | Live game, newly played move |
| `PRIORITY_LIVE_BACKFILL` | 100 | Live game, backfill historical moves |
| `PRIORITY_FINISHED` | 10 | Finished match from live list |
| `PRIORITY_HISTORICAL` | 1 | Historical game batch analysis |

### Flight-Window Design

The current analyzer sends requests serially (`limit=1`), wasting GPU capacity. The new design maintains N concurrent requests to KataGo at all times, with **preemption** for high-priority tasks.

```
AnalyzeJob (persistent async loop)
│
├─ Config: window_size = 16 (= KataGo numAnalysisThreads)
│
├─ Startup:
│   1. Reset stale 'running' tasks to 'pending' (crash recovery)
│   2. Fetch 16 pending tasks from DB, mark running
│   3. Send 16 HTTP requests to KataGo 8002 concurrently
│
├─ Main loop:
│   ├─ Wait for any request to complete (asyncio.FIRST_COMPLETED)
│   ├─ Write result to DB (mark success or failed)
│   ├─ Fetch new pending tasks to refill window
│   └─ Window stays at ≤16 in-flight requests
│
└─ Preemption check (every refill cycle):
    ├─ Peek highest pending priority in DB
    ├─ Compare with lowest in-flight priority
    ├─ If pending.priority >> in_flight.min_priority:
    │   cancel lowest in-flight task, mark back to 'pending'
    └─ Send high-priority task immediately
```

### Preemption Mechanism

When all 16 slots are occupied by low-priority tasks and a high-priority task arrives:

```python
PREEMPT_THRESHOLD = 500  # Only preempt if priority gap >= this

async def _maybe_preempt(self, in_flight):
    """Cancel lowest-priority in-flight task if a much higher one is waiting."""
    highest_pending = self._peek_highest_pending_priority()
    if highest_pending is None:
        return

    # Find lowest priority in current window
    lowest_key, lowest_priority = min(
        self._priorities.items(), key=lambda x: x[1]
    )

    if highest_pending - lowest_priority >= PREEMPT_THRESHOLD:
        # Cancel the low-priority task
        in_flight[lowest_key].cancel()
        del in_flight[lowest_key]
        # Mark cancelled task back to pending (will be retried later)
        self._mark_pending(lowest_key)
        logger.info(f"Preempted {lowest_key} (pri={lowest_priority}) "
                    f"for pending task (pri={highest_pending})")
```

This ensures:
- Live new moves (1000) preempt historical analysis (1) — gap=999 > threshold=500
- Live backfill (100) does NOT preempt finished matches (10) — gap=90 < threshold
- GPU utilization stays near 100% (no reserved slots)

### Pseudocode

```python
class AnalyzeJob(BaseJob):
    name = "analyze"
    window_size = 16        # = numAnalysisThreads
    request_timeout = 60.0  # Per-request timeout in seconds

    async def run(self):
        in_flight: dict[str, asyncio.Task] = {}
        priorities: dict[str, int] = {}  # key -> priority for preemption

        # Crash recovery: reset stale running tasks
        self._reset_stale_running_tasks()

        # Fill window (uses FOR UPDATE SKIP LOCKED)
        pending = self._fetch_pending(limit=self.window_size)
        for record in pending:
            task = asyncio.create_task(self._send_with_timeout(record))
            in_flight[record.key] = task
            priorities[record.key] = record.priority

        while self._running:
            if not in_flight:
                await asyncio.sleep(5)
                pending = self._fetch_pending(limit=self.window_size)
                for record in pending:
                    task = asyncio.create_task(self._send_with_timeout(record))
                    in_flight[record.key] = task
                    priorities[record.key] = record.priority
                continue

            done, _ = await asyncio.wait(
                in_flight.values(),
                return_when=asyncio.FIRST_COMPLETED,
            )

            for completed_task in done:
                key = self._find_key(in_flight, completed_task)
                del in_flight[key]
                del priorities[key]
                try:
                    result = completed_task.result()
                    self._save_result(result)
                except asyncio.CancelledError:
                    pass  # Preempted, already marked pending
                except asyncio.TimeoutError:
                    self._mark_failed(key, "KataGo request timeout")
                except Exception as e:
                    self._mark_failed(key, e)

            # Check for preemption before refilling
            await self._maybe_preempt(in_flight, priorities)

            # Refill window
            slots = self.window_size - len(in_flight)
            if slots > 0:
                new_pending = self._fetch_pending(limit=slots)
                for record in new_pending:
                    task = asyncio.create_task(self._send_with_timeout(record))
                    in_flight[record.key] = task
                    priorities[record.key] = record.priority

    async def _send_with_timeout(self, record):
        """Send analysis request with per-request timeout."""
        return await asyncio.wait_for(
            self._send_analysis(record),
            timeout=self.request_timeout,
        )
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| No pending tasks in DB | Window drains, sleep 5s, re-check |
| KataGo request timeout (60s) | Single task times out, mark failed, refill slot immediately |
| KataGo service down | All tasks fail/timeout, all marked failed, sleep then retry |
| KataGo slow but alive | Requests complete within 60s timeout, normal flow continues |
| High-priority task inserted | Preemption check cancels lowest in-flight task if gap >= 500 |
| Cron crashes while tasks running | Startup resets all 'running' → 'pending' |
| All slots filled with low priority | Live move (1000) preempts historical (1) within one loop cycle |

### Relationship to KataGo Config

```
katrain-cron AnalyzeJob          KataGo analysis_config_cron.cfg
───────────────────────          ────────────────────────────────
window_size = 16             ←→  numAnalysisThreads = 16
maxVisits = 500 (per request)    numSearchThreadsPerAnalysisThread = 4
                                 nnMaxBatchSize = 64  (≥ 16 × 4)
```

`window_size` must equal `numAnalysisThreads`. Smaller wastes GPU threads; larger just queues inside KataGo without throughput gain.

## 8. KataGo Dual-Instance Configuration

Two KataGo instances, each on a dedicated RTX 3090 GPU, optimized for different workloads.

### katago-web (Port 8000, GPU 0) — User Gameplay

```cfg
# analysis_config_web.cfg
numAnalysisThreads = 4
numSearchThreadsPerAnalysisThread = 16
nnMaxBatchSize = 64
```

- Few concurrent games, deep search per position
- Low latency for interactive play

### katago-cron (Port 8002, GPU 1) — Batch Analysis

```cfg
# analysis_config_cron.cfg
numAnalysisThreads = 16
numSearchThreadsPerAnalysisThread = 4
nnMaxBatchSize = 64
```

- Many concurrent positions, GPU continuously saturated
- Each request uses `maxVisits = 500` for professional-grade analysis
- Throughput-optimized: GPU utilization approaches 100%

### Why GPU Was Underutilized Before

The old `LiveAnalyzer._analysis_loop()` fetches `limit=1` and `await`s the result before fetching the next. KataGo only ever has 1 request — its `numAnalysisThreads=8` goes unused, batch inference never activates, and GPU idles between requests.

## 9. katrain-web Changes

### Removed

| Component | File | Action |
|-----------|------|--------|
| `LivePoller` polling loops | `poller.py` | Delete entire class |
| `LiveAnalyzer` analysis loop | `analyzer.py` | Delete entire class |
| `LiveService._analysis_cron_loop()` | `service.py` | Delete |
| `LiveService.start()` poller/analyzer startup | `service.py` | Delete |
| `LiveTranslator._call_llm/qwen/anthropic` | `translator.py` | Remove LLM call paths |

### Retained (unchanged)

| Component | Reason |
|-----------|--------|
| All REST API endpoints | Pure DB reads, unchanged |
| `LiveTranslator` DB lookup + fuzzy match | Still used for on-demand query fallback |
| `LiveCache` | Frontend fast reads still need memory cache |
| `analysis_repo.py` | API reads analysis results from DB |
| Gameplay module -> KataGo 8000 | User real-time interaction, must stay in web process |

### Added

**TranslationCache** — load all translations into memory at startup, refresh every 60s:

```python
class TranslationCache:
    _players: dict[str, dict[str, str]]     # name -> {lang: translation}
    _tournaments: dict[str, dict[str, str]]

    async def load(self):
        """Load all translations from DB. Called at startup."""

    async def refresh_loop(self, interval=60):
        """Incremental refresh (WHERE updated_at > last_refresh)."""

    def get_player(self, name: str, lang: str) -> Optional[str]:
        """Pure memory lookup, microsecond latency."""
```

**LiveCache refresh loop** — since poller is removed, LiveCache needs a DB polling loop:

```python
# Every 5s, read latest match data from DB -> populate LiveCache
# (cron writes DB -> web reads DB -> fills memory cache)
```

katrain-web becomes a pure **read service**: DB -> memory cache -> API response. All writes are done by katrain-cron.

## 10. API Endpoints Reference

### 10.1 katrain-web Endpoints

#### Session & Gameplay (prefix: `/api`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/session` | Create new game session |
| GET | `/api/state` | Get current session state |
| POST | `/api/move` | Play a move |
| POST | `/api/undo` | Undo move(s) |
| POST | `/api/redo` | Redo move(s) |
| GET | `/api/sgf/save` | Export game as SGF |
| POST | `/api/sgf/load` | Import SGF file |
| POST | `/api/new-game` | Start new game |
| POST | `/api/game/setup` | Setup game with settings |
| POST | `/api/edit-game` | Edit game settings |
| POST | `/api/nav` | Navigate game tree |
| POST | `/api/ai-move` | Request AI move (-> KataGo 8000) |
| GET | `/api/config` | Get configuration value |
| POST | `/api/config` | Update configuration |
| POST | `/api/config/bulk` | Bulk update configuration |
| POST | `/api/player` | Update player info |
| POST | `/api/player/swap` | Swap black/white players |
| POST | `/api/analysis/continuous` | Toggle continuous analysis |
| POST | `/api/analysis/extra` | Run extra analysis on position |
| POST | `/api/analysis/show-pv` | Show principal variation |
| POST | `/api/analysis/clear-pv` | Clear principal variation |
| POST | `/api/mode` | Set play/analyze mode |
| POST | `/api/nav/mistake` | Navigate to next mistake |
| POST | `/api/nav/branch` | Switch game tree branch |
| POST | `/api/analysis/tsumego` | Create tsumego frame |
| POST | `/api/analysis/selfplay` | Setup AI selfplay |
| POST | `/api/analysis/region` | Select region for analysis |
| POST | `/api/resign` | Resign game |
| POST | `/api/timeout` | Timeout player |
| POST | `/api/multiplayer/leave` | Leave multiplayer game |
| POST | `/api/timer/pause` | Pause game timer |
| POST | `/api/rotate` | Rotate board view |
| POST | `/api/node/delete` | Delete game tree node |
| POST | `/api/node/prune` | Prune game tree branch |
| POST | `/api/node/make-main` | Make branch the main line |
| POST | `/api/node/toggle-collapse` | Toggle node collapse |
| POST | `/api/ui/toggle` | Toggle UI element visibility |
| POST | `/api/language` | Switch display language |
| GET | `/api/translations` | Get UI translations |
| GET | `/api/ai-constants` | Get AI strategy constants |
| POST | `/api/ai/estimate-rank` | Estimate rank for AI settings |
| POST | `/api/theme` | Switch UI theme |
| POST | `/api/analysis/game` | Analyze full game |
| POST | `/api/analysis/report` | Generate game report |
| POST | `/api/mode/insert` | Set insert mode |
| WS | `/ws/lobby` | Lobby websocket (matchmaking, invites) |
| WS | `/ws/{session_id}` | Game websocket (spectating, chat) |

#### Health (prefix: `/api/v1/health`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check with engine status |
| GET | `/health` | Simple health check |

#### Auth (prefix: `/api/v1/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Login, returns JWT |
| POST | `/api/v1/auth/register` | Register new user |
| GET | `/api/v1/auth/me` | Get current user info |
| POST | `/api/v1/auth/logout` | Logout and cleanup |

#### Analysis Routing (prefix: `/api/v1/analysis`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/analysis/analyze` | Route analysis to local/cloud engine |

#### Games (prefix: `/api/v1/games`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/games/` | List user's games (paginated) |
| POST | `/api/v1/games/` | Create game record |
| GET | `/api/v1/games/{game_id}` | Get game details |
| POST | `/api/v1/games/{game_id}/result` | Update game result |
| GET | `/api/v1/games/active/multiplayer` | List active multiplayer games |

#### Users (prefix: `/api/v1/users`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/users/follow/{username}` | Follow user |
| DELETE | `/api/v1/users/follow/{username}` | Unfollow user |
| GET | `/api/v1/users/followers` | List followers |
| GET | `/api/v1/users/following` | List following |
| GET | `/api/v1/users/online` | List online users |

#### Live Broadcasting (prefix: `/api/v1/live`)

| Method | Path | Description | After Migration |
|--------|------|-------------|-----------------|
| GET | `/api/v1/live/matches` | List live + finished matches | Read from DB + TranslationCache |
| GET | `/api/v1/live/matches/featured` | Get featured match | Read from LiveCache |
| GET | `/api/v1/live/matches/{id}` | Match detail with SGF | Read from DB |
| GET | `/api/v1/live/upcoming` | Upcoming tournament matches | Read from DB |
| GET | `/api/v1/live/matches/{id}/analysis` | KataGo analysis for match | Read from DB |
| GET | `/api/v1/live/matches/{id}/analysis/preload` | Preload analysis data | Read from DB |
| POST | `/api/v1/live/matches/{id}/analyze` | Queue analysis for moves | Write pending tasks to DB |
| POST | `/api/v1/live/refresh` | Force refresh match data | **Removed** (cron handles) |
| GET | `/api/v1/live/analysis/stats` | Analysis queue statistics | Read from DB |
| POST | `/api/v1/live/cleanup` | Clean up stale data | **Removed** (cron handles) |
| POST | `/api/v1/live/matches/{id}/recover` | Recover match moves | **Removed** (cron handles) |
| GET | `/api/v1/live/admin/stats` | Admin dashboard stats | Read from DB |
| POST | `/api/v1/live/admin/recover-all` | Recover all matches | **Removed** (cron handles) |
| GET | `/api/v1/live/stats` | Live service statistics | Read from DB |
| GET | `/api/v1/live/translations` | All translations for frontend | Read from TranslationCache |
| GET | `/api/v1/live/translate/player` | Translate player name | Read from TranslationCache, fallback DB |
| GET | `/api/v1/live/translate/tournament` | Translate tournament name | Read from TranslationCache, fallback DB |
| GET | `/api/v1/live/translate/round` | Translate round name | Read from TranslationCache, fallback DB |
| POST | `/api/v1/live/translations/learn` | Manually store translation | Write to DB |
| GET | `/api/v1/live/translations/missing` | List untranslated names | Read from DB |
| GET | `/api/v1/live/matches/{id}/comments` | Get match comments | Read from DB |
| POST | `/api/v1/live/matches/{id}/comments` | Create comment | Write to DB |
| DELETE | `/api/v1/live/comments/{id}` | Delete comment | Write to DB |
| GET | `/api/v1/live/matches/{id}/comments/poll` | Poll new comments | Read from DB |

#### Tsumego (prefix: `/api/v1/tsumego`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tsumego/levels` | List difficulty levels |
| GET | `/api/v1/tsumego/levels/{level}/categories` | Categories for level |
| GET | `/api/v1/tsumego/levels/{level}/categories/{cat}` | Problems list (paginated) |
| GET | `/api/v1/tsumego/problems/{id}` | Full problem details |
| GET | `/api/v1/tsumego/progress` | User's progress |
| POST | `/api/v1/tsumego/progress/{id}` | Update problem progress |

#### Static & SPA

| Method | Path | Description |
|--------|------|-------------|
| GET | `/galaxy` | Galaxy UI SPA entry |
| GET | `/galaxy/{path}` | SPA catch-all routing |
| GET | `/` | Static files and assets |

### 10.2 katrain-cron Jobs (No HTTP API)

katrain-cron does not expose HTTP endpoints. All work is done via scheduled jobs writing directly to the database.

| Job | Interval | External Calls | DB Writes |
|-----|----------|----------------|-----------|
| `FetchListJob` | 60s | XingZhen API `/all`, `/history` | `live_matches` |
| `PollMovesJob` | 3s | XingZhen API `/situation/{id}` | `live_matches` (moves), `live_analysis` (pending) |
| `TranslateJob` | 120s | Qwen/Claude LLM API | `player_translations`, `tournament_translations` |
| `AnalyzeJob` | Persistent | KataGo HTTP 8002 `/analyze` | `live_analysis` (results), `live_matches` (katago stats) |

## 11. Docker Deployment

### docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:15-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: katrain
      POSTGRES_USER: katrain
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"

  katrain-web:
    build:
      context: .
      dockerfile: Dockerfile.web
    ports:
      - "8080:8080"
    environment:
      - KATRAIN_DATABASE_URL=postgresql://katrain:${POSTGRES_PASSWORD}@postgres:5432/katrain
      - KATAGO_URL=http://katago-web:8000
    depends_on:
      - postgres
      - katago-web

  katrain-cron:
    build:
      context: .
      dockerfile: Dockerfile.cron
    restart: unless-stopped
    environment:
      - KATRAIN_DATABASE_URL=postgresql://katrain:${POSTGRES_PASSWORD}@postgres:5432/katrain
      - KATAGO_URL=http://katago-cron:8002
      - DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
    depends_on:
      - postgres
      - katago-cron

  katago-web:
    image: katago:tensorrt
    volumes:
      - ./katago-configs/analysis_config_web.cfg:/config.cfg
      - ./katago-models:/models
    command: analysis -config /config.cfg -model /models/kata1.bin.gz
    ports:
      - "8000:8000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["0"]
              capabilities: [gpu]

  katago-cron:
    image: katago:tensorrt
    volumes:
      - ./katago-configs/analysis_config_cron.cfg:/config.cfg
      - ./katago-models:/models
    command: analysis -config /config.cfg -model /models/kata1.bin.gz
    ports:
      - "8002:8002"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["1"]
              capabilities: [gpu]

volumes:
  pgdata:
```

### Dockerfiles

**Dockerfile.web** — includes Node.js frontend build:

```dockerfile
FROM node:20-alpine AS frontend
WORKDIR /app/katrain/web/ui
COPY katrain/web/ui/package*.json ./
RUN npm ci
COPY katrain/web/ui/ ./
RUN npm run build

FROM python:3.11-slim
COPY --from=frontend /app/katrain/web/static /app/katrain/web/static
COPY . /app
RUN pip install -r requirements-web.txt
CMD ["python", "-m", "katrain", "--ui", "web"]
```

**Dockerfile.cron** — lightweight, Python only:

```dockerfile
FROM python:3.11-slim
COPY katrain/cron/ /app/katrain/cron/
COPY requirements-cron.txt /app/
RUN pip install -r /app/requirements-cron.txt
CMD ["python", "-m", "katrain.cron"]
```

**requirements-cron.txt** (minimal):

```
sqlalchemy>=2.0
psycopg2-binary
httpx
apscheduler>=3.10
```

### Local Development (no Docker)

```bash
# Terminal 1: web service
python -m katrain --ui web

# Terminal 2: cron service
python -m katrain.cron

# KataGo already running or use remote HTTP
```

## 12. Data Flow Summary

```
1. FetchListJob (60s)
   XingZhen API → match list → DB (live_matches)

2. PollMovesJob (3s)
   XingZhen API → new moves detected → DB (live_matches.moves)
   → create pending analysis tasks (priority=1000)

3. TranslateJob (120s)
   Scan DB for untranslated names (skip source=manual)
   → Players: search Wikipedia/Go associations → LLM-assisted extraction
   → Tournaments: direct LLM (1 name → 5 languages)
   → DB (player_translations, tournament_translations)

4. AnalyzeJob (persistent, window_size=16)
   DB pending tasks → 16 concurrent requests to KataGo 8002
   → results written to DB (live_analysis)
   → GPU batch inference, near 100% utilization

5. katrain-web
   DB → TranslationCache (refresh 60s) + LiveCache (refresh 5s)
   → API responses to users (microsecond memory lookups)
```

## 13. Migration Checklist

### Phase 1: Build katrain-cron
- [ ] Create `katrain/cron/` package structure
- [ ] Implement `config.py`, `db.py`, `models.py` (independent DB models)
- [ ] Add Alembic migration: partial index + unique constraint on `live_analysis`
- [ ] Implement `scheduler.py` with APScheduler
- [ ] Implement `BaseJob`
- [ ] Port `FetchListJob` from `LivePoller._list_poll_loop()`
- [ ] Port `PollMovesJob` from `LivePoller._live_poll_loop()`
- [ ] Implement `TranslateJob` — players: search+LLM; tournaments: direct LLM batch
- [ ] Implement `AnalyzeJob` with flight-window + preemption + per-request timeout
- [ ] Implement `clients/xingzhen.py` and `clients/katago.py`
- [ ] Create `requirements-cron.txt`
- [ ] Create `Dockerfile.cron`
- [ ] Test locally: `python -m katrain.cron`

### Phase 2: Modify katrain-web
- [ ] Delete `LivePoller` class
- [ ] Delete `LiveAnalyzer` class
- [ ] Strip `LiveTranslator` of LLM call paths
- [ ] Remove `LiveService._analysis_cron_loop()`
- [ ] Simplify `LiveService.start()` (no poller/analyzer startup)
- [ ] Add `TranslationCache` with startup load + 60s refresh
- [ ] Add `LiveCache` DB refresh loop (5s)
- [ ] Remove admin endpoints that trigger write operations (refresh, cleanup, recover)
- [ ] Update translation endpoints to read from `TranslationCache`

### Phase 3: Deploy
- [ ] Create `analysis_config_web.cfg` and `analysis_config_cron.cfg`
- [ ] Update `docker-compose.yml` with all 4+1 services (+ restart policies)
- [ ] Create `Dockerfile.web` (if not exists)
- [ ] Test full stack with Docker Compose
- [ ] Verify GPU utilization on katago-cron approaches 100%
- [ ] Monitor DB connection pool usage under load

---

## 14. Architecture Review Log

### Review by Gemini 3 Pro (2026-01-28)

**Verdict:** Conditional Approval

**Adopted recommendations:**

| # | Recommendation | Action Taken |
|---|---------------|--------------|
| A | Add partial index on analysis queue | Added to Section 7 + Migration Phase 1 |
| B | Priority starvation in flight window | Implemented preemption mechanism (cancel lowest, re-queue) — Section 7 |
| 6 | Single cron instance crash recovery | `restart: unless-stopped` + startup stale task reset |
| 7 | Translation efficiency: batch per name | 1 LLM call per name → 5 languages — Section 6 |
| 9a | Stuck job rescuer | Startup resets `running → pending` (ported from existing code) |
| 9b | DB connection pooling | Pool size ≥ 20 in config — Section 4 |

**Rejected recommendations:**

| # | Recommendation | Reason |
|---|---------------|--------|
| C/5 | Share models.py via common package | User decision: zero shared code for future repo separation. Schema consistency ensured by shared Alembic migrations + CI tests. |

**Design choices that differ from Gemini's suggestions:**

- **Preemption over slot reservation:** Gemini suggested reserving 4 of 16 slots for high-priority tasks (75% GPU utilization). We chose timeout-cancel + preemption instead (near 100% GPU utilization). Trade-off: more implementation complexity, but no wasted GPU capacity.
- **Translation failure handling:** Gemini suggested batching. We adopted batching but with full-name retry on failure (not per-language fallback), keeping the DB record as the atomic unit.

### Review by Codex (2026-01-28)

**Verdict:** Approval with suggested hardening

**Adopted recommendations:**

| # | Recommendation | Action Taken |
|---|---------------|--------------|
| 1 | `FOR UPDATE SKIP LOCKED` for queue | Added to Section 7 DB setup — prevents duplicate task pickup |
| 2 | Per-request timeout on KataGo calls | Added `_send_with_timeout()` with 60s deadline — Section 7 pseudocode |
| 3 | Unique constraint `(match_id, move_number)` | Added to Section 7 DB setup — idempotent task insertion |
| 4 | Translation concurrency (Semaphore) | Added `asyncio.Semaphore(3)` — Section 6 player translation flow |
| 5 | Store LLM model/version in translation records | Added `llm_model` field — Section 6 |
| 6 | Basic observability (queue depth, task rates, latency) | Phase 1: structured logging + DB stats queries |

**Rejected recommendations:**

| # | Recommendation | Reason |
|---|---------------|--------|
| Multi-instance cron with leader election | Over-engineering for current scale. Single instance + `restart: unless-stopped` + crash recovery is sufficient. Revisit when scaling demands it. |
| Backlog fairness / age bumping | Historical tasks being starved by live tasks is **by design**. Historical analysis can be postponed indefinitely (confirmed requirement). |
| Schema sharing via common package | User decision: zero shared code. Already rejected in Gemini review. |
| Shadow mode / dry-run deployment | Good idea in principle, but Phase 1 can mitigate via incremental rollout: run cron first, verify outputs, then disable web-side equivalents. |
| Adaptive window sizing | Fixed window + per-request timeout + preemption already covers degraded GPU scenarios without the complexity of dynamic sizing. |

**Open questions resolved:**

| Question | Answer |
|----------|--------|
| Live analysis latency target | ≤ 5 seconds. window_size=16 + preemption handles this. |
| Historical backfill SLO | None. Can be postponed indefinitely during live events. |
| User-editable translations | Yes. `source=manual` records are never overwritten by automation. Player names use search-first strategy (Wikipedia, Go associations) for quality. |
