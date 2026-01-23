# PostgreSQL Database Schema

This document outlines the current PostgreSQL tables and their fields, as defined in `katrain/postgres/init.sql`, `scripts/migrate_db.sql`, and `katrain/web/core/models_db.py`.

## Tables

### `users`

Stores user account information, ranking, and statistics.

| Field | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY`, `SERIAL` | Unique user identifier. |
| `uuid` | `VARCHAR` | `UNIQUE` | Globally unique identifier for the user. |
| `username` | `VARCHAR(255)` | `UNIQUE`, `NOT NULL` | User's login name. |
| `hashed_password` | `TEXT` | `NOT NULL` | Securely hashed password. |
| `rank` | `VARCHAR(10)` | `DEFAULT '20k'` | Current Go rank (e.g., '10k', '1d'). |
| `net_wins` | `INTEGER` | `DEFAULT 0` | Net wins tracking for rank progression. |
| `elo_points` | `INTEGER` | `DEFAULT 0` | Internal ELO rating points. |
| `credits` | `NUMERIC(15, 2)` | `DEFAULT 10000.00` | User's virtual currency balance. |
| `avatar_url` | `TEXT` | `NULLABLE` | URL to user's avatar image. |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` | Account creation timestamp. |
| `updated_at` | `TIMESTAMP` | `DEFAULT NOW()` | Last update timestamp. |

### `games`

Records game sessions, results, and SGF content.

| Field | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY`, `SERIAL` | Unique game identifier. |
| `black_player_id` | `INTEGER` | `FOREIGN KEY (users.id)` | ID of the player playing Black. |
| `white_player_id` | `INTEGER` | `FOREIGN KEY (users.id)` | ID of the player playing White. |
| `winner_id` | `INTEGER` | `FOREIGN KEY (users.id)`, `NULLABLE` | ID of the winning player. |
| `sgf_content` | `TEXT` | `NULLABLE` | Full SGF record of the game. |
| `result` | `VARCHAR(50)` | `NULLABLE` | Game result (e.g., "B+R", "W+0.5"). |
| `game_type` | `VARCHAR(20)` | `DEFAULT 'free'` | Type of game ('free', 'rated'). |
| `started_at` | `TIMESTAMP` | `DEFAULT NOW()` | Game start timestamp. |
| `ended_at` | `TIMESTAMP` | `NULLABLE` | Game end timestamp. |

### `relationships`

Manages social connections (followers/following) between users.

| Field | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `follower_id` | `INTEGER` | `PRIMARY KEY`, `FOREIGN KEY (users.id)` | User ID who is following. |
| `following_id` | `INTEGER` | `PRIMARY KEY`, `FOREIGN KEY (users.id)` | User ID being followed. |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` | Timestamp when the relationship started. |

### `rating_history`

Logs changes in user rank and ELO after rated games.

| Field | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY`, `SERIAL` | Unique history record identifier. |
| `user_id` | `INTEGER` | `FOREIGN KEY (users.id)` | User whose rank changed. |
| `old_rank` | `VARCHAR(10)` | - | Rank before the game. |
| `new_rank` | `VARCHAR(10)` | - | Rank after the game. |
| `elo_change` | `INTEGER` | `DEFAULT 0` | Change in ELO points. |
| `game_id` | `INTEGER` | `FOREIGN KEY (games.id)` | Associated game ID. |
| `changed_at` | `TIMESTAMP` | `DEFAULT NOW()` | Timestamp of the change. |

### `tsumego_problems`

Stores tsumego (life & death) problems.

| Field | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(32)` | `PRIMARY KEY` | Unique problem ID (e.g., "1014"). |
| `level` | `VARCHAR(8)` | `NOT NULL`, `INDEX` | Difficulty level (e.g., "3d"). |
| `category` | `VARCHAR(32)` | `NOT NULL`, `INDEX` | Problem category (e.g., "life-death"). |
| `hint` | `VARCHAR(16)` | `NOT NULL` | Hint text (e.g., "Black to play"). |
| `board_size` | `INTEGER` | `DEFAULT 19` | Board size (usually 19). |
| `initial_black` | `JSON` | - | List of initial black stone coordinates. |
| `initial_white` | `JSON` | - | List of initial white stone coordinates. |
| `sgf_content` | `TEXT` | - | Full SGF content for solving logic. |
| `source` | `VARCHAR(256)` | - | Source of the problem. |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` | Creation timestamp. |
| `updated_at` | `TIMESTAMP` | `DEFAULT NOW()` | Last update timestamp. |

### `user_tsumego_progress`

Tracks user progress and stats for specific tsumego problems.

| Field | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `user_id` | `INTEGER` | `PRIMARY KEY`, `FOREIGN KEY (users.id)` | User ID. |
| `problem_id` | `VARCHAR(32)` | `PRIMARY KEY`, `FOREIGN KEY (tsumego_problems.id)` | Problem ID. |
| `completed` | `BOOLEAN` | `DEFAULT FALSE` | Whether the problem has been solved. |
| `attempts` | `INTEGER` | `DEFAULT 0` | Number of attempts made. |
| `first_completed_at` | `TIMESTAMP` | `NULLABLE` | Timestamp of first successful completion. |
| `last_attempt_at` | `TIMESTAMP` | `NULLABLE` | Timestamp of the most recent attempt. |
| `last_duration` | `INTEGER` | `NULLABLE` | Time taken (in seconds) for the last attempt. |
