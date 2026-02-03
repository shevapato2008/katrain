---
name: tsumego-data-sync
description: Update tsumego problem database and index from SGF files. Use when adding, replacing, or syncing tsumego/life-death problems.
---

# Tsumego Data Sync

## Overview

This skill documents the process for updating the tsumego (Go life-and-death problems) database and index in KaTrain.

## IMPORTANT: Do NOT List Files

The `data/life-n-death/` directory contains thousands of SGF files. **Never** use `ls`, `Glob`, `find`, or any other tool to list its contents — this will flood the context window and exhaust available tokens. The Python scripts handle file traversal internally and only output summary statistics.

## Data Structure

```
data/life-n-death/
├── index.json          # Generated index of all problems
├── 10K/                # Difficulty levels (10K-15K, 1K-9K, 1D-8D)
│   ├── 1163.sgf
│   └── ...
├── 3D/
│   └── ...
└── ...
```

## Update Process

### Step 1: Prepare SGF Files

Place SGF files in `data/life-n-death/{LEVEL}/` directories where `{LEVEL}` is the difficulty (e.g., `3D`, `5K`, `10K`).

SGF files should contain:
- `AB[]` / `AW[]` - Initial black/white stone positions
- `PL[B]` or `PL[W]` - Player to move
- `C[黑先]` or `C[白先]` - Problem description
- Solution tree with variations marked `✓ 正确` (correct) or `✗ 失败` (wrong)

### Step 2: Generate Index

Run the index generation script:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh && \
conda activate py311_katago && \
python scripts/generate_tsumego_index.py
```

This scans all SGF files and generates `data/life-n-death/index.json` with metadata:
- Problem ID (from filename)
- Level (from directory name)
- Category (life-death)
- Board size, initial stones, hints

### Step 3: Sync to Database

Run the database sync script:

```bash
source /opt/miniconda3/etc/profile.d/conda.sh && \
conda activate py311_katago && \
python scripts/sync_tsumego_db.py
```

This script:
- Reads `index.json` and all SGF files
- Inserts new problems into PostgreSQL
- Updates existing problems if changed
- Reports orphaned records (in DB but no SGF file)

**Output example:**
```
Found 574 SGF files
  INSERT: 1120 (3k/life-death)
  UPDATE: 1091 (level: 3d -> 3d)
  ...
Sync complete:
  Inserted: 417
  Updated: 157
  Unchanged: 0
  Orphaned: 839 (not auto-deleted)
```

### Step 4: Commit Changes

```bash
git add data/life-n-death/
git commit -m "data: update tsumego problems"
git push
```

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/generate_tsumego_index.py` | Generate `index.json` from SGF files |
| `scripts/sync_tsumego_db.py` | Sync index and SGFs to PostgreSQL database |

## Dependencies

Required Python packages (in `py311_katago` conda env):
- `sqlalchemy` - Database ORM
- `passlib` - Password hashing (required by web module imports)

## Troubleshooting

### Import errors when running sync script

If you see `ModuleNotFoundError`, ensure you're using the correct conda environment:
```bash
conda activate py311_katago
```

### Orphaned records

The sync script does NOT auto-delete orphaned records. To clean them up, manually delete from the database or update the script to handle deletions.

## Data Source

SGF files are typically scraped from `101weiqi.com`. The scraper is in a separate repository:
```
/Users/fan/Repositories/go-topic-collections/101weiqi/
```

To refresh all data:
1. Run scraper to download SGFs
2. Copy to `data/life-n-death/`
3. Follow steps 2-4 above
