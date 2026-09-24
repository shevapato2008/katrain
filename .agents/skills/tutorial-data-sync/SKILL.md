---
name: tutorial-data-sync
description: Sync tutorial database tables and page assets from local Macbook to remote server fan@home-ubuntu. Use when deploying updated tutorial data (books, figures, narrations, board_payload, training samples) to the production server after local edits.
---

# Tutorial Data Sync (Local -> Remote)

> 🛑 **停用旧数据库同步流程（管理后台启用前置条件）**：以下 Step 0–4 是历史参考，不得照做。旧 Step 3 会清空生产教程表，再用本机数据覆盖后台编辑；旧备份漏掉棋图历史，计数核对也不能发现同数量内容被覆盖。上线后以目标环境数据库为已有内容的权威；新增教材导入须另定按范围核差、冲突拒绝、完整可恢复备份与恢复演练的流程。任何远程连接、写库或部署仍须 Fan 对具体步骤当场批准。**本技能目前不提供可执行的数据库同步命令。**

> **WARNING: This sync does TRUNCATE CASCADE on all tutorial tables.**
> Any human-verified `board_payload` corrections on the server that are NOT in
> your local database WILL BE PERMANENTLY LOST. **Always run Step 0 first.**
> The `board_payload` data involves extensive manual annotation work and is
> the most valuable and hardest-to-reproduce data in the system.

## Overview

Full sync of tutorial module data from the local Macbook (PostgreSQL via Docker) to the remote server `fan@home-ubuntu` (same Docker PostgreSQL setup). Syncs both database records (5 tables) and asset files (page images, debug images, audio).

## Environment

| | Local (Macbook) | Remote (home-ubuntu) |
|--|--|--|
| **SSH** | - | `home-ubuntu` (see `~/.ssh/config`) |
| **Repo** | `/Users/fan/Repositories/katrain-tutorials` | `/home/fan/Repositories/katrain` |
| **Branch** | `feature/tutorials` | `develop` |
| **DB** | Docker `katrain-postgres`, user `katrain_user`, db `katrain_db` | Same |
| **Assets** | `data/tutorial_assets/` | `data/tutorial_assets/` (volume-mounted into `katrain-web` at `/app/data/tutorial_assets:ro`) |

## Sync Process

### Step 0: MANDATORY — Backup server data before sync

```bash
# Export verified board payloads to git-tracked JSON (preserves manual corrections)
ssh home-ubuntu "cd ~/Repositories/katrain && \
  KATRAIN_DATABASE_URL='postgresql://katrain_user:katrain_secure_password_CHANGE_ME@localhost:5432/katrain_db' \
  python scripts/export_verified_payloads.py"

# Full database backup (all 5 tables as compressed JSON)
ssh home-ubuntu "cd ~/Repositories/katrain && \
  docker exec katrain-postgres pg_dump -U katrain_user -d katrain_db \
    --data-only --column-inserts \
    -t tutorial_books -t tutorial_chapters -t tutorial_sections \
    -t tutorial_figures -t training_samples \
    | gzip > data/tutorial_backups/pre_sync_$(date +%Y%m%d_%H%M%S).sql.gz"
```

Verify the backup exists before proceeding:
```bash
ssh home-ubuntu "ls -la ~/Repositories/katrain/data/tutorial_backups/ | tail -3"
```

### Step 0.5: Compare verified counts (recommended)

```bash
# Check how many verified figures exist on the server
ssh home-ubuntu "docker exec katrain-postgres psql -U katrain_user -d katrain_db -c \
  \"SELECT COUNT(*) as verified FROM tutorial_figures WHERE recognition_debug::text LIKE '%human_verified%true%'\""

# Compare with local
docker exec katrain-postgres psql -U katrain_user -d katrain_db -c \
  "SELECT COUNT(*) as verified FROM tutorial_figures WHERE recognition_debug::text LIKE '%human_verified%true%'"
```

If the server has MORE verified figures than local, the sync will lose those corrections. Consider syncing the server's verified data back to local first.

### Step 1: Export local DB (with column names for schema safety)

```bash
docker exec katrain-postgres pg_dump -U katrain_user -d katrain_db \
  --data-only --column-inserts \
  -t tutorial_books -t tutorial_chapters -t tutorial_sections \
  -t tutorial_figures -t training_samples \
  > tutorial_data.sql
```

### Step 2: Rsync assets (run in background, incremental)

```bash
rsync -avz data/tutorial_assets/ home-ubuntu:~/Repositories/katrain/data/tutorial_assets/
```

### Step 3: Upload SQL and import on remote

🛑 已停用。不得上传后执行全表 `TRUNCATE`／导入；先制定不会覆盖目标环境后台编辑的逐项迁移与冲突处理方案，并取得每条真实写库命令的当场批准。

### Step 4: Verify counts match

```bash
# Run on both local and remote, compare output
docker exec katrain-postgres psql -U katrain_user -d katrain_db -c \
  "SELECT 'books', COUNT(*) FROM tutorial_books UNION ALL \
   SELECT 'chapters', COUNT(*) FROM tutorial_chapters UNION ALL \
   SELECT 'sections', COUNT(*) FROM tutorial_sections UNION ALL \
   SELECT 'figures', COUNT(*) FROM tutorial_figures UNION ALL \
   SELECT 'training_samples', COUNT(*) FROM training_samples;"
```

## Tables Synced

| Table | Content |
|-------|---------|
| `tutorial_books` | Book metadata (title, author, slug, category) |
| `tutorial_chapters` | Chapter hierarchy |
| `tutorial_sections` | Section hierarchy |
| `tutorial_figures` | Figures with board_payload, narration, audio_asset, bbox, recognition_debug |
| `training_samples` | ML training patches from human-verified figures |

## Important Notes

- Use `--column-inserts` (not `--inserts`) because local and remote schemas may have different column order (e.g., `recognition_debug` column position differs between branches).
- `pg_dump` automatically appends `setval` calls to reset sequences, preventing ID conflicts on future inserts.
- rsync is incremental; only changed files are transferred. First sync ~387MB, subsequent syncs much faster.
- The remote `katrain-web` Docker container must have `./data/tutorial_assets:/app/data/tutorial_assets:ro` volume mount in `docker-compose.yml`. If images don't load after sync, check this mount.
- Clean up temp files after sync: `rm tutorial_data.sql; ssh home-ubuntu "rm ~/tutorial_data.sql"`

## Troubleshooting

### Images not loading on remote web UI
The `katrain-web` container needs the volume mount. Add to `docker-compose.yml` under `katrain-web`:
```yaml
volumes:
  - ./data/tutorial_assets:/app/data/tutorial_assets:ro
```
Then `docker compose up -d katrain-web` to recreate the container.

### Schema mismatch errors during import
If you see `invalid input syntax` errors, the column order differs. Ensure export uses `--column-inserts`. Minor type differences (`jsonb` vs `json`) are compatible.

### SSH connection refused
The remote host `home-ubuntu` is configured via `~/.ssh/config` (port forwarding). Do not use `fan@ubuntu` directly.
