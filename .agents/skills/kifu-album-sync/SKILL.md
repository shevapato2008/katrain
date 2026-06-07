---
name: kifu-album-sync
description: Import tournament game SGF files from local directories into the PostgreSQL kifu_albums table. Use when adding, replacing, or syncing kifu album data.
---

# Kifu Album Sync

## CRITICAL: Context Safety Rules

**NEVER list, glob, explore, or read files inside `data/kifu-album/`.** This directory contains ~24k+ SGF files. Any directory listing or file search will flood context and cause "Context limit reached" errors.

The ONLY correct approach is to run `scripts/import_kifu.py` — it handles everything internally.

## Quick Reference

**Import new SGFs (run in background due to large output):**
```bash
source /opt/miniconda3/etc/profile.d/conda.sh && conda activate py311_katago && python scripts/import_kifu.py
```

**Dry run preview (run in background):**
```bash
source /opt/miniconda3/etc/profile.d/conda.sh && conda activate py311_katago && python scripts/import_kifu.py --dry-run
```

**Verify DB count:**
```bash
source /opt/miniconda3/etc/profile.d/conda.sh && conda activate py311_katago && python -c "
from katrain.web.core.db import engine
from sqlalchemy.orm import Session
from katrain.web.core.models_db import KifuAlbum
with Session(engine) as db:
    print(f'Total kifu albums in DB: {db.query(KifuAlbum).count()}')
"
```

**IMPORTANT:** Always run import commands with `run_in_background: true` in the Bash tool and set a generous timeout (e.g., 600000ms). The script prints a progress line every 500 files. To check progress, use `tail -5` on the background task's output file.

## How It Works

1. Place SGF files under `data/kifu-album/{source_group}/` (e.g., `19x19/`, `Go_Seigen/`)
2. Run `scripts/import_kifu.py` — it recursively finds all `*.sgf` files, deduplicates by `source_path`, and inserts new records
3. Existing records (matched by `source_path` UNIQUE constraint) are automatically skipped

## Database Schema

**Table:** `kifu_albums` — see `scripts/import_kifu.py` for column mappings.

Key columns: `player_black`, `player_white`, `event`, `result`, `date_played`, `date_sort` (normalized for sorting), `sgf_content`, `source_path` (unique dedup key), `search_text`.

## Adding a New Source Directory

1. `mkdir data/kifu-album/{new_source}/`
2. Place SGF files in it
3. Run the import script (no code changes needed)

## Troubleshooting

- **ModuleNotFoundError**: Activate `conda activate py311_katago` first
- **Re-import a file**: Delete its row first: `DELETE FROM kifu_albums WHERE source_path = '...';`
- **Encoding issues**: The script auto-detects encoding and re-serializes to UTF-8
