# PostgreSQL Database Schema

> Auto-generated from live database on 2025-02-09.
> Source of truth: `katrain/web/core/models_db.py` (web) and `katrain/cron/models.py` (cron).
> Initial DDL: `katrain/postgres/init.sql`, migrations: `scripts/migrate_db.sql`, `scripts/migrate_upcoming.sql`.

## Overview

| # | Table | Rows | Size | Description |
|---|-------|------|------|-------------|
| 1 | `users` | 1 | 16 kB | User accounts, ranking and credits |
| 2 | `relationships` | 0 | 0 B | Social follow relationships between users |
| 3 | `rating_history` | 0 | 8 kB | ELO/rank change log per rated game |
| 4 | `user_games` | 18 | 64 kB | Personal game library (play, import, research) |
| 5 | `user_game_analysis` | 3,332 | 2.1 MB | Move-by-move KataGo analysis for user games |
| 6 | `live_matches` | 71 | 312 kB | Live/historical pro matches from external sources |
| 7 | `live_analysis` | 14,796 | 53 MB | Move-by-move KataGo analysis for live matches |
| 8 | `live_comments` | 0 | 8 kB | User comments on live matches |
| 9 | `live_upcoming` | 16 | 56 kB | Upcoming scheduled match events |
| 10 | `player_translations` | 123 | 72 kB | Player name i18n translations |
| 11 | `tournament_translations` | 101 | 88 kB | Tournament name i18n translations |
| 12 | `tsumego_problems` | 21,076 | 19 MB | Tsumego (life & death) problem bank |
| 13 | `user_tsumego_progress` | 0 | 0 B | Per-user tsumego solving progress |
| 14 | `kifu_albums` | 25,062 | 41 MB | Historical tournament game records |
| 15 | `system_config` | 0 | 8 kB | Runtime key-value configuration store |

---

## Entity-Relationship Diagram

```
users ─────────┬──────────────── relationships (follower/following)
  │            │
  │            ├──── rating_history ──── user_games
  │            │                              │
  │            ├──── user_games ──────── user_game_analysis
  │            │
  │            ├──── user_tsumego_progress ──── tsumego_problems
  │            │
  │            └──── live_comments ──── live_matches
  │                                         │
  │                                         ├──── live_analysis
  │                                         └──── live_comments
  │
  └── (standalone tables: kifu_albums, player_translations,
       tournament_translations, live_upcoming, system_config)
```

---

## Tables

### 1. `users`

User accounts, ranking, and virtual currency.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `uuid` | `VARCHAR` | YES | — | Globally unique ID (hex), used for KataGo requests |
| `username` | `VARCHAR` | NOT NULL | — | Login name |
| `hashed_password` | `VARCHAR` | NOT NULL | — | bcrypt-hashed password |
| `rank` | `VARCHAR(10)` | YES | `'20k'` | Current Go rank (e.g. `'10k'`, `'1d'`) |
| `net_wins` | `INTEGER` | YES | `0` | Net wins for rank progression |
| `elo_points` | `INTEGER` | YES | `0` | Internal ELO rating |
| `credits` | `NUMERIC(10,2)` | YES | `10000.00` | Virtual currency balance |
| `avatar_url` | `VARCHAR(255)` | YES | — | Avatar image URL |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Account creation time |
| `updated_at` | `TIMESTAMPTZ` | YES | `CURRENT_TIMESTAMP` | Last update time |

**Indexes:**
- `users_pkey` — PRIMARY KEY (`id`)
- `ix_users_id` — btree (`id`)
- `ix_users_username` — UNIQUE (`username`)
- `users_uuid_key` — UNIQUE CONSTRAINT (`uuid`)
- `ix_users_uuid` — btree (`uuid`)

**Referenced by:** `relationships`, `rating_history`, `user_games`, `user_tsumego_progress`, `live_comments`

---

### 2. `relationships`

Social follow connections between users (many-to-many self-join).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `follower_id` | `INTEGER` | NOT NULL | — | FK → `users.id`, the follower |
| `following_id` | `INTEGER` | NOT NULL | — | FK → `users.id`, the user being followed |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | When the follow was created |

**Indexes:**
- `relationships_pkey` — PRIMARY KEY (`follower_id`, `following_id`)

**Foreign Keys:**
- `follower_id` → `users.id`
- `following_id` → `users.id`

---

### 3. `rating_history`

Logs rank/ELO changes after rated games.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `user_id` | `INTEGER` | YES | — | FK → `users.id` |
| `old_rank` | `VARCHAR` | YES | — | Rank before game |
| `new_rank` | `VARCHAR` | YES | — | Rank after game |
| `elo_change` | `INTEGER` | YES | — | ELO delta |
| `game_id` | `VARCHAR(32)` | YES | — | FK → `user_games.id` |
| `changed_at` | `TIMESTAMPTZ` | YES | `now()` | Timestamp of change |

**Indexes:**
- `rating_history_pkey` — PRIMARY KEY (`id`)
- `ix_rating_history_id` — btree (`id`)

**Foreign Keys:**
- `user_id` → `users.id`
- `game_id` → `user_games.id`

---

### 4. `user_games`

Personal game library: AI play records, imported SGFs, research positions.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `VARCHAR(32)` | NOT NULL | uuid4 hex | Primary key |
| `user_id` | `INTEGER` | NOT NULL | — | FK → `users.id` |
| `title` | `VARCHAR(255)` | YES | — | Game title |
| `sgf_content` | `TEXT` | YES | — | Full SGF record |
| `player_black` | `VARCHAR(100)` | YES | — | Black player name |
| `player_white` | `VARCHAR(100)` | YES | — | White player name |
| `result` | `VARCHAR(50)` | YES | — | Game result (e.g. `"B+R"`) |
| `board_size` | `INTEGER` | YES | — | Board size (9, 13, 19) |
| `rules` | `VARCHAR(64)` | YES | — | Rule set (`chinese`, `japanese`, etc.) |
| `komi` | `FLOAT` | YES | — | Komi value |
| `move_count` | `INTEGER` | YES | — | Total moves played |
| `source` | `VARCHAR(50)` | NOT NULL | — | Origin: `play_ai` / `play_human` / `import` / `research` |
| `category` | `VARCHAR(50)` | YES | — | `game` / `position` |
| `game_type` | `VARCHAR(50)` | YES | — | `free` / `rated` / null |
| `sgf_hash` | `VARCHAR(64)` | YES | — | SHA hash for deduplication |
| `event` | `VARCHAR(255)` | YES | — | Event/tournament name |
| `game_date` | `VARCHAR(32)` | YES | — | Date string from SGF |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | Last update time |

**Indexes:**
- `user_games_pkey` — PRIMARY KEY (`id`)
- `ix_user_games_user_id` — btree (`user_id`)
- `ix_user_games_user_category` — btree (`user_id`, `category`)
- `ix_user_games_user_source` — btree (`user_id`, `source`)
- `ix_user_games_created` — btree (`created_at`)
- `ix_user_games_sgf_hash` — btree (`sgf_hash`)

**Foreign Keys:**
- `user_id` → `users.id`

**Referenced by:** `user_game_analysis`, `rating_history`

---

### 5. `user_game_analysis`

Move-by-move KataGo analysis data for user games (research module).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `game_id` | `VARCHAR(32)` | NOT NULL | — | FK → `user_games.id` |
| `move_number` | `INTEGER` | NOT NULL | — | Move index (0 = empty board) |
| `status` | `VARCHAR(16)` | YES | — | `pending` / `running` / `success` / `failed` |
| `priority` | `INTEGER` | YES | — | Higher = more urgent |
| `winrate` | `FLOAT` | YES | — | Black's winrate (0–1) |
| `score_lead` | `FLOAT` | YES | — | Black's point lead |
| `visits` | `INTEGER` | YES | — | KataGo visit count |
| `top_moves` | `JSON` | YES | — | `[{move, visits, winrate, score_lead, prior, pv}, ...]` |
| `ownership` | `JSON` | YES | — | 2D ownership grid (−1 to 1, positive = Black) |
| `move` | `VARCHAR(8)` | YES | — | Actual move played (e.g. `"Q16"`) |
| `actual_player` | `VARCHAR(1)` | YES | — | `'B'` or `'W'` |
| `delta_score` | `FLOAT` | YES | — | Score change from previous position |
| `delta_winrate` | `FLOAT` | YES | — | Winrate change from previous position |
| `is_brilliant` | `BOOLEAN` | YES | — | Brilliant move flag |
| `is_mistake` | `BOOLEAN` | YES | — | Mistake flag |
| `is_questionable` | `BOOLEAN` | YES | — | Questionable move flag |
| `error_message` | `TEXT` | YES | — | Error detail if analysis failed |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | Last update time |

**Indexes:**
- `user_game_analysis_pkey` — PRIMARY KEY (`id`)
- `ix_user_game_analysis_id` — btree (`id`)
- `ix_user_game_analysis_game_id` — btree (`game_id`)
- `ix_user_game_analysis_status` — btree (`status`, `priority`)
- `uq_user_game_analysis_move` — UNIQUE (`game_id`, `move_number`)

**Foreign Keys:**
- `game_id` → `user_games.id`

---

### 6. `live_matches`

Live and historical pro matches fetched from external sources (XingZhen, WeiqiOrg).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `match_id` | `VARCHAR(64)` | NOT NULL | — | Unique ID: `{source}_{source_id}` |
| `source` | `VARCHAR(20)` | NOT NULL | — | Data source (`xingzhen`, `weiqi_org`) |
| `source_id` | `VARCHAR(64)` | NOT NULL | — | Original ID from source |
| `tournament` | `VARCHAR(256)` | NOT NULL | — | Tournament/event name |
| `round_name` | `VARCHAR(128)` | YES | — | Round info (e.g. `"Final"`) |
| `match_date` | `TIMESTAMPTZ` | YES | — | Match date |
| `player_black` | `VARCHAR(128)` | NOT NULL | — | Black player name |
| `player_white` | `VARCHAR(128)` | NOT NULL | — | White player name |
| `black_rank` | `VARCHAR(16)` | YES | — | Black rank (e.g. `"9p"`) |
| `white_rank` | `VARCHAR(16)` | YES | — | White rank |
| `status` | `VARCHAR(16)` | NOT NULL | — | `live` / `finished` |
| `result` | `VARCHAR(64)` | YES | — | Game result (e.g. `"B+R"`, `"W+3.5"`) |
| `move_count` | `INTEGER` | YES | — | Total moves played |
| `sgf_content` | `TEXT` | YES | — | Full SGF record |
| `moves` | `JSONB` | YES | — | Move list `["Q16", "D4", ...]` |
| `current_winrate` | `FLOAT` | YES | — | Black winrate from source API |
| `current_score` | `FLOAT` | YES | — | Black score lead from source API |
| `katago_winrate` | `FLOAT` | YES | — | Black winrate from local KataGo |
| `katago_score` | `FLOAT` | YES | — | Black score lead from local KataGo |
| `board_size` | `INTEGER` | YES | `19` | Board size |
| `komi` | `FLOAT` | YES | `7.5` | Komi |
| `rules` | `VARCHAR(32)` | YES | `'chinese'` | Rule set |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | Last update time |

**Indexes:**
- `live_matches_pkey` — PRIMARY KEY (`id`)
- `ix_live_matches_id` — btree (`id`)
- `ix_live_matches_match_id` — UNIQUE (`match_id`)

**Referenced by:** `live_analysis`, `live_comments`

---

### 7. `live_analysis`

Move-by-move KataGo analysis for live matches (populated by katrain-cron).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `match_id` | `VARCHAR(64)` | NOT NULL | — | FK → `live_matches.match_id` |
| `move_number` | `INTEGER` | NOT NULL | — | Move index (0 = empty board) |
| `status` | `VARCHAR(16)` | NOT NULL | — | `pending` / `running` / `success` / `failed` |
| `priority` | `INTEGER` | YES | — | Higher = more urgent |
| `winrate` | `FLOAT` | YES | — | Black's winrate (0–1) |
| `score_lead` | `FLOAT` | YES | — | Black's point lead |
| `top_moves` | `JSONB` | YES | — | `[{move, visits, winrate, score_lead, prior, pv}, ...]` |
| `ownership` | `JSONB` | YES | — | 2D ownership grid (−1 to 1, positive = Black) |
| `actual_move` | `VARCHAR(8)` | YES | — | The move that was played |
| `actual_player` | `VARCHAR(1)` | YES | — | `'B'` or `'W'` |
| `delta_score` | `FLOAT` | YES | — | Score change from previous position |
| `delta_winrate` | `FLOAT` | YES | — | Winrate change from previous position |
| `is_brilliant` | `BOOLEAN` | YES | — | Brilliant move flag (妙手) |
| `is_mistake` | `BOOLEAN` | YES | — | Mistake flag (问题手) |
| `is_questionable` | `BOOLEAN` | YES | — | Questionable move flag (疑问手) |
| `error_message` | `TEXT` | YES | — | Error detail if analysis failed |
| `retry_count` | `INTEGER` | YES | — | Number of retries |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |
| `analyzed_at` | `TIMESTAMPTZ` | YES | — | When analysis completed |

**Indexes:**
- `live_analysis_pkey` — PRIMARY KEY (`id`)
- `ix_live_analysis_id` — btree (`id`)
- `ix_live_analysis_match_id` — btree (`match_id`)
- `uq_match_move` — UNIQUE (`match_id`, `move_number`)
- `idx_analysis_pending_priority` — partial btree (`priority` DESC, `created_at`) WHERE `status = 'pending'`

**Foreign Keys:**
- `match_id` → `live_matches.match_id`

---

### 8. `live_comments`

User comments on live match broadcasts.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `match_id` | `VARCHAR(64)` | NOT NULL | — | FK → `live_matches.match_id` |
| `user_id` | `INTEGER` | NOT NULL | — | FK → `users.id` |
| `content` | `TEXT` | NOT NULL | — | Comment text |
| `is_deleted` | `BOOLEAN` | YES | — | Soft-delete flag |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |

**Indexes:**
- `live_comments_pkey` — PRIMARY KEY (`id`)
- `ix_live_comments_id` — btree (`id`)
- `ix_live_comments_match_id` — btree (`match_id`)
- `ix_live_comments_user_id` — btree (`user_id`)

**Foreign Keys:**
- `match_id` → `live_matches.match_id`
- `user_id` → `users.id`

---

### 9. `live_upcoming`

Upcoming/scheduled match events (populated by katrain-cron).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `event_id` | `VARCHAR(128)` | NOT NULL | — | Unique event identifier |
| `tournament` | `VARCHAR(256)` | NOT NULL | — | Tournament name |
| `round_name` | `VARCHAR(128)` | YES | — | Round info |
| `scheduled_time` | `TIMESTAMPTZ` | NOT NULL | — | Scheduled start time |
| `player_black` | `VARCHAR(128)` | YES | — | Black player (may be TBD) |
| `player_white` | `VARCHAR(128)` | YES | — | White player (may be TBD) |
| `source` | `VARCHAR(32)` | NOT NULL | — | Source: `foxwq`, `nihonkiin`, etc. |
| `source_url` | `VARCHAR(512)` | YES | — | Link to more info |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | Last update time |

**Indexes:**
- `live_upcoming_pkey` — PRIMARY KEY (`id`)
- `live_upcoming_event_id_key` — UNIQUE CONSTRAINT (`event_id`)
- `idx_upcoming_event_id` — btree (`event_id`)
- `idx_upcoming_scheduled_time` — btree (`scheduled_time`)

---

### 10. `player_translations`

Multilingual translations for player names (populated by LLM or manual entry).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `canonical_name` | `VARCHAR(128)` | NOT NULL | — | Original/canonical name (e.g. `"王立诚"`) |
| `country` | `VARCHAR(4)` | YES | — | Country code: `CN`, `JP`, `KR`, `TW` |
| `en` | `VARCHAR(128)` | YES | — | English name |
| `cn` | `VARCHAR(128)` | YES | — | Simplified Chinese |
| `tw` | `VARCHAR(128)` | YES | — | Traditional Chinese |
| `jp` | `VARCHAR(128)` | YES | — | Japanese (kanji/katakana) |
| `ko` | `VARCHAR(128)` | YES | — | Korean (hangul) |
| `aliases` | `JSON` | YES | — | Alternative name list |
| `source` | `VARCHAR(16)` | NOT NULL | — | `static` / `manual` / `llm` / `search+llm` / `wikipedia` / `fuzzy_match` |
| `llm_model` | `VARCHAR(64)` | YES | — | LLM model used for translation |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | Last update time |

**Indexes:**
- `player_translations_pkey` — PRIMARY KEY (`id`)
- `ix_player_translations_id` — btree (`id`)
- `ix_player_translations_canonical_name` — UNIQUE (`canonical_name`)

---

### 11. `tournament_translations`

Multilingual translations for tournament names.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `original` | `VARCHAR(256)` | NOT NULL | — | Original tournament name |
| `en` | `VARCHAR(256)` | YES | — | English |
| `cn` | `VARCHAR(256)` | YES | — | Simplified Chinese |
| `tw` | `VARCHAR(256)` | YES | — | Traditional Chinese |
| `jp` | `VARCHAR(256)` | YES | — | Japanese |
| `ko` | `VARCHAR(256)` | YES | — | Korean |
| `source` | `VARCHAR(16)` | NOT NULL | — | `static` / `manual` / `llm` / `search+llm` / `wikipedia` |
| `llm_model` | `VARCHAR(64)` | YES | — | LLM model used for translation |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | Last update time |

**Indexes:**
- `tournament_translations_pkey` — PRIMARY KEY (`id`)
- `ix_tournament_translations_id` — btree (`id`)
- `ix_tournament_translations_original` — UNIQUE (`original`)

---

### 12. `tsumego_problems`

Tsumego (life & death / tesuji) problem bank.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `VARCHAR(32)` | NOT NULL | — | Problem number (e.g. `"1014"`) |
| `level` | `VARCHAR(8)` | NOT NULL | — | Difficulty level (e.g. `"3d"`, `"5k"`) |
| `category` | `VARCHAR(32)` | NOT NULL | — | Problem type: `life-death`, `tesuji` |
| `hint` | `VARCHAR(16)` | NOT NULL | — | Hint text (e.g. `"黑先"`, `"白先"`) |
| `board_size` | `INTEGER` | YES | — | Board size (usually 19) |
| `initial_black` | `JSON` | YES | — | Initial black stone coordinates |
| `initial_white` | `JSON` | YES | — | Initial white stone coordinates |
| `sgf_content` | `TEXT` | YES | — | Full SGF for solving logic |
| `source` | `VARCHAR(256)` | YES | — | Problem source |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Creation time |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | Last update time |

**Indexes:**
- `tsumego_problems_pkey` — PRIMARY KEY (`id`)
- `ix_tsumego_problems_level` — btree (`level`)
- `ix_tsumego_problems_category` — btree (`category`)
- `ix_tsumego_level_category` — composite btree (`level`, `category`)

**Referenced by:** `user_tsumego_progress`

---

### 13. `user_tsumego_progress`

Per-user solving progress and stats for tsumego problems.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `user_id` | `INTEGER` | NOT NULL | — | FK → `users.id` |
| `problem_id` | `VARCHAR(32)` | NOT NULL | — | FK → `tsumego_problems.id` |
| `completed` | `BOOLEAN` | YES | — | Whether the problem was solved |
| `attempts` | `INTEGER` | YES | — | Number of attempts |
| `first_completed_at` | `TIMESTAMPTZ` | YES | — | First successful completion |
| `last_attempt_at` | `TIMESTAMPTZ` | YES | — | Most recent attempt |
| `last_duration` | `INTEGER` | YES | — | Time taken in seconds (last attempt) |

**Indexes:**
- `user_tsumego_progress_pkey` — PRIMARY KEY (`user_id`, `problem_id`)

**Foreign Keys:**
- `user_id` → `users.id`
- `problem_id` → `tsumego_problems.id`

---

### 14. `kifu_albums`

Historical tournament game records (大赛棋谱), imported from SGF file collections.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `SERIAL` | NOT NULL | auto-increment | Primary key |
| `player_black` | `VARCHAR(512)` | NOT NULL | — | Black player name |
| `player_white` | `VARCHAR(512)` | NOT NULL | — | White player name |
| `black_rank` | `VARCHAR(64)` | YES | — | Black player rank |
| `white_rank` | `VARCHAR(64)` | YES | — | White player rank |
| `event` | `VARCHAR(256)` | YES | — | Tournament/event name |
| `result` | `VARCHAR(64)` | YES | — | Game result |
| `date_played` | `VARCHAR(32)` | YES | — | Raw SGF date for display (e.g. `"1926"`, `"1928-09-04,05"`) |
| `date_sort` | `VARCHAR(10)` | YES | — | Normalized ISO prefix for sorting (e.g. `"1926-00-00"`) |
| `place` | `VARCHAR(256)` | YES | — | Game location |
| `komi` | `FLOAT` | YES | — | Komi value |
| `handicap` | `INTEGER` | YES | — | Handicap stones |
| `board_size` | `INTEGER` | YES | — | Board size |
| `rules` | `VARCHAR(32)` | YES | — | Rule set |
| `round_name` | `VARCHAR(128)` | YES | — | Round name |
| `source` | `VARCHAR(256)` | YES | — | SGF source attribution |
| `move_count` | `INTEGER` | YES | — | Total moves |
| `sgf_content` | `TEXT` | NOT NULL | — | Full SGF content |
| `source_path` | `VARCHAR(512)` | NOT NULL | — | Original file path (dedup key) |
| `search_text` | `TEXT` | YES | — | Lowercased concatenation for full-text search |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | Import time |

**Indexes:**
- `kifu_albums_pkey` — PRIMARY KEY (`id`)
- `ix_kifu_albums_id` — btree (`id`)
- `ix_kifu_albums_player_black` — btree (`player_black`)
- `ix_kifu_albums_player_white` — btree (`player_white`)
- `ix_kifu_albums_event` — btree (`event`)
- `ix_kifu_albums_date_sort` — btree (`date_sort`)
- `ix_kifu_albums_source_path` — UNIQUE (`source_path`)

---

### 15. `system_config`

Runtime key-value configuration store for system settings.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `key` | `VARCHAR(64)` | NOT NULL | — | Config key (primary key) |
| `value` | `TEXT` | YES | — | Config value |
| `description` | `TEXT` | YES | — | Human-readable description |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | Last update time |

**Indexes:**
- `system_config_pkey` — PRIMARY KEY (`key`)
- `ix_system_config_key` — btree (`key`)

---

## Notes

### Legacy `games` table

The `init.sql` defines a `games` table (PvP matchmaking), but it has been superseded by `user_games` which serves as the personal game library. The `rating_history.game_id` column now references `user_games.id` instead of the original `games.id`.

### Dual model definitions

Both `katrain/web/core/models_db.py` and `katrain/cron/models.py` define ORM models for shared tables (`live_matches`, `live_analysis`, `player_translations`, `tournament_translations`, `live_upcoming`). They map to the same PostgreSQL tables but are maintained independently to avoid cross-service imports.

### Schema management

There is no Alembic migration setup. Schema changes are applied via:
1. SQLAlchemy's `Base.metadata.create_all()` on app startup (creates missing tables)
2. Manual migration scripts in `scripts/` for column additions on existing tables
