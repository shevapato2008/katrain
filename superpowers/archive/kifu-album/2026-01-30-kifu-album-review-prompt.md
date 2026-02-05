# Code Review Request: Kifu Album (大赛棋谱) Module Plan

## Context

KaTrain is a Go/Baduk/Weiqi teaching application with dual UIs (Kivy desktop + FastAPI/React web). We're adding a **tournament game records library** module ("棋谱库 > 大赛棋谱"). The implementation plan is attached below.

## What This Module Does

1. **Data**: ~891 SGF (Smart Game Format) files in `data/kifu-album/` containing historical Go tournament games (currently Go Seigen's collection, 1926–1970s)
2. **Import**: A Python script parses SGF files using an existing parser, extracts metadata (players, event, date, result, etc.), and bulk-inserts into a SQLite/PostgreSQL table
3. **API**: Two FastAPI REST endpoints — paginated list with `ILIKE` search on a concatenated `search_text` column, and single-record detail returning full SGF content
4. **Frontend**: React + MUI page at `/galaxy/kifu` with search bar, game record list, pagination. Clicking a record navigates to the existing Research page (`/galaxy/research?kifu_id=N`) which fetches the SGF and loads it into the analysis board

## Existing Codebase Conventions

- **DB**: SQLAlchemy `declarative_base()`, no Alembic, `create_all()` on startup. Models in `models_db.py`. No ORM relationships for this module.
- **API**: FastAPI routers in `katrain/web/api/v1/endpoints/`, Pydantic response models defined per-file, `Depends(get_db)` for DB sessions. Registered in `api.py`.
- **Frontend**: React 18 + react-router-dom v6 + MUI v5/6. Pages in `galaxy/pages/`. API clients in `galaxy/api/`. Types in `galaxy/types/`. Dark theme. `useTranslation()` hook for i18n with `t('namespace:key', 'default')`.
- **SGF Parser**: `katrain/core/sgf_parser.py` — `SGF.parse_file(path)` returns an `SGFNode` root. `root.get_property("PB")` extracts metadata. Handles encoding detection, `.gib`/`.ngf` formats.

## What I Want Reviewed

Please review the implementation plan below for:

1. **Bugs / Logic Errors**: Anything that would break at runtime — wrong API paths, incorrect SQLAlchemy usage, React hook dependency issues, race conditions in the SGF loading flow
2. **Security**: SQL injection via the `ILIKE` search query, path traversal in `source_path`, any XSS vectors in rendering user-searchable content
3. **Performance**: Is the `search_text ILIKE '%query%'` approach adequate for ~1000 records on SQLite? Any N+1 query issues? Should pagination use cursor-based instead of offset?
4. **Data Integrity**: The import script's duplicate detection via `source_path`, the `count_moves()` traversal logic, encoding handling when reading SGF files twice (once via parser, once via `read_text`)
5. **Frontend Patterns**: React state management — is the dual `searchInput`/`query` pattern correct? Could `useSearchParams` sync cause infinite re-render loops? Is the `kifuLoaded` flag in ResearchPage robust enough?
6. **API Design**: Is the response schema well-structured? Should `KifuAlbumSummary` use `model_config = ConfigDict(from_attributes=True)` for ORM mode instead of manual field mapping? Should there be a `lang` param for player name translation (like the live module)?
7. **Missing Pieces**: Error boundaries, loading states, empty states, accessibility, keyboard navigation, mobile responsiveness
8. **Codebase Consistency**: Does this follow the established patterns from `LiveMatchDB`/`live.py`/`LivePage.tsx` closely enough, or are there unnecessary deviations?

---

## The Full Plan

# Kifu Album (大赛棋谱) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a public tournament game record library that lets users browse, search, and open historical Go game records for analysis in the Research page.

**Architecture:** SGF files in `data/kifu-album/` are imported into a `kifu_albums` database table via a script following the existing `sync_tsumego_db.py` pattern. A new FastAPI endpoint (`/api/v1/kifu/albums`) serves paginated, searchable listings. A new React page (`/galaxy/kifu`) displays the list with search and pagination, and clicking a record navigates to the Research page to load the SGF.

**Tech Stack:** SQLAlchemy model, FastAPI REST endpoints, React + MUI frontend, existing `SGF.parse_file()` parser.

---

### Task 1: Database Model — `KifuAlbum`

**Files:**
- Modify: `katrain/web/core/models_db.py` (insert before `UpcomingMatchDB` class at line 284)

**Step 1: Add the `KifuAlbum` model**

Add this class in `katrain/web/core/models_db.py` directly before the `class UpcomingMatchDB(Base):` line:

```python
class KifuAlbum(Base):
    """Database model for tournament game records (大赛棋谱)."""
    __tablename__ = "kifu_albums"

    id = Column(Integer, primary_key=True, index=True)
    player_black = Column(String(128), nullable=False, index=True)
    player_white = Column(String(128), nullable=False, index=True)
    black_rank = Column(String(16), nullable=True)
    white_rank = Column(String(16), nullable=True)
    event = Column(String(256), nullable=True, index=True)
    result = Column(String(64), nullable=True)
    date_played = Column(String(32), nullable=True, index=True)  # Raw SGF date string (can be partial: "1926", "1928-09-04,05")
    place = Column(String(256), nullable=True)
    komi = Column(Float, nullable=True)
    handicap = Column(Integer, default=0)
    board_size = Column(Integer, default=19)
    rules = Column(String(32), nullable=True)
    round_name = Column(String(128), nullable=True)
    source = Column(String(256), nullable=True)
    move_count = Column(Integer, default=0)
    sgf_content = Column(Text, nullable=False)
    source_path = Column(String(512), unique=True, nullable=False, index=True)  # Prevents duplicate imports
    search_text = Column(Text, nullable=True)  # Concatenated searchable fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

Design decisions:
- `date_played` is `String`, not `DateTime` — SGF dates can be partial ("1926") or multi-day ("1928-09-04,05")
- `source_path` has a unique constraint to prevent re-importing the same file
- `search_text` concatenates player names, event, date, etc. for simple `LIKE` queries (sufficient for ~1000 records, no full-text search engine needed)
- Follows `LiveMatchDB` column naming and typing conventions exactly

**Step 2: Verify the model loads on app startup**

Run: `CI=true uv run pytest tests/test_version.py -v`
Expected: PASS (model is auto-discovered by `create_all` since it's in `models_db.py`)

**Step 3: Commit**

```bash
git add katrain/web/core/models_db.py
git commit -m "feat(kifu): add KifuAlbum database model for tournament game records"
```

---

### Task 2: SGF Import Script

**Files:**
- Create: `scripts/import_kifu.py`
- Test: manual run with `--dry-run`

This follows the exact pattern of `scripts/sync_tsumego_db.py`.

**Step 1: Create the import script**

Create `scripts/import_kifu.py`:

```python
#!/usr/bin/env python3
"""
Import SGF files from data/kifu-album/ into the kifu_albums table.

Usage:
  python scripts/import_kifu.py --dry-run  # Preview changes
  python scripts/import_kifu.py            # Apply changes
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from katrain.web.core.db import engine, Base
from katrain.web.core.models_db import KifuAlbum
from katrain.core.sgf_parser import SGF


DATA_DIR = Path("data/kifu-album")


def count_moves(root) -> int:
    """Count total moves by traversing the main line."""
    count = 0
    node = root
    while node.children:
        node = node.children[0]
        if node.move:
            count += 1
    return count


def build_search_text(data: dict) -> str:
    """Concatenate searchable fields into a single string."""
    parts = [
        data.get("player_black", ""),
        data.get("player_white", ""),
        data.get("black_rank", "") or "",
        data.get("white_rank", "") or "",
        data.get("event", "") or "",
        data.get("result", "") or "",
        data.get("date_played", "") or "",
        data.get("place", "") or "",
        data.get("round_name", "") or "",
        data.get("source", "") or "",
    ]
    return " ".join(p for p in parts if p)


def parse_sgf_file(sgf_path: Path) -> dict:
    """Parse SGF file and return kifu album data."""
    root = SGF.parse_file(str(sgf_path))
    sgf_content = sgf_path.read_text(encoding="utf-8", errors="ignore")

    data = {
        "player_black": root.get_property("PB", "Unknown"),
        "player_white": root.get_property("PW", "Unknown"),
        "black_rank": root.get_property("BR"),
        "white_rank": root.get_property("WR"),
        "event": root.get_property("EV"),
        "result": root.get_property("RE"),
        "date_played": root.get_property("DT"),
        "place": root.get_property("PC"),
        "komi": root.komi if "KM" in root.properties else None,
        "handicap": root.handicap,
        "board_size": root.board_size[0],
        "rules": root.get_property("RU"),
        "round_name": root.get_property("RO"),
        "source": root.get_property("SO") or root.get_property("US"),
        "move_count": count_moves(root),
        "sgf_content": sgf_content,
        "source_path": str(sgf_path.relative_to(DATA_DIR.parent.parent)),
    }
    data["search_text"] = build_search_text(data)
    return data


def import_kifu(dry_run: bool = False):
    """Import all SGF files from DATA_DIR into database."""
    if not DATA_DIR.exists():
        print(f"ERROR: Data directory not found: {DATA_DIR}")
        sys.exit(1)

    # Collect all SGF files
    sgf_files = sorted(DATA_DIR.rglob("*.sgf"))
    print(f"Found {len(sgf_files)} SGF files in {DATA_DIR}")

    # Ensure tables exist
    Base.metadata.create_all(engine)

    stats = {"inserted": 0, "skipped": 0, "errors": 0}

    with Session(engine) as db:
        existing_paths = {
            r.source_path for r in db.query(KifuAlbum.source_path).all()
        }

        for sgf_path in sgf_files:
            rel_path = str(sgf_path.relative_to(DATA_DIR.parent.parent))
            if rel_path in existing_paths:
                stats["skipped"] += 1
                continue

            try:
                data = parse_sgf_file(sgf_path)
                if not dry_run:
                    db.add(KifuAlbum(**data))
                stats["inserted"] += 1
                print(f"  INSERT: {data['player_black']} vs {data['player_white']} ({data['date_played']})")
            except Exception as e:
                stats["errors"] += 1
                print(f"  ERROR: {sgf_path.name}: {e}")

        if not dry_run:
            db.commit()

    print(f"\nImport {'(DRY RUN) ' if dry_run else ''}complete:")
    print(f"  Inserted: {stats['inserted']}")
    print(f"  Skipped (already exists): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import kifu album SGF files into database")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    args = parser.parse_args()
    import_kifu(dry_run=args.dry_run)
```

**Step 2: Run dry-run to verify parsing works**

Run: `uv run python scripts/import_kifu.py --dry-run`
Expected: "Found 891 SGF files" + INSERT lines, 0 errors, no DB writes

**Step 3: Run actual import**

Run: `uv run python scripts/import_kifu.py`
Expected: ~891 records inserted

**Step 4: Commit**

```bash
git add scripts/import_kifu.py
git commit -m "feat(kifu): add SGF import script for tournament game records"
```

---

### Task 3: REST API Endpoint

**Files:**
- Create: `katrain/web/api/v1/endpoints/kifu.py`
- Modify: `katrain/web/api/v1/api.py` (add router registration)

**Step 1: Create the kifu endpoint file**

Create `katrain/web/api/v1/endpoints/kifu.py`:

```python
"""REST API endpoints for the kifu album (tournament game records) module."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from katrain.web.core.db import get_db
from katrain.web.core.models_db import KifuAlbum

router = APIRouter()


class KifuAlbumSummary(BaseModel):
    """Summary response for kifu album listing (excludes sgf_content)."""
    id: int
    player_black: str
    player_white: str
    black_rank: Optional[str]
    white_rank: Optional[str]
    event: Optional[str]
    result: Optional[str]
    date_played: Optional[str]
    komi: Optional[float]
    handicap: int
    board_size: int
    round_name: Optional[str]
    move_count: int


class KifuAlbumDetail(KifuAlbumSummary):
    """Full response including SGF content."""
    place: Optional[str]
    rules: Optional[str]
    source: Optional[str]
    sgf_content: str


class KifuAlbumListResponse(BaseModel):
    """Paginated list response."""
    items: List[KifuAlbumSummary]
    total: int
    page: int
    page_size: int


@router.get("/albums", response_model=KifuAlbumListResponse)
def list_kifu_albums(
    q: Optional[str] = Query(None, description="Search query (fuzzy match on player names, event, date)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List tournament game records with optional search and pagination."""
    query = db.query(KifuAlbum)

    if q:
        query = query.filter(KifuAlbum.search_text.ilike(f"%{q}%"))

    # Sort by date descending (newest first), with nulls last
    query = query.order_by(KifuAlbum.date_played.desc())

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    items = [
        KifuAlbumSummary(
            id=r.id,
            player_black=r.player_black,
            player_white=r.player_white,
            black_rank=r.black_rank,
            white_rank=r.white_rank,
            event=r.event,
            result=r.result,
            date_played=r.date_played,
            komi=r.komi,
            handicap=r.handicap,
            board_size=r.board_size,
            round_name=r.round_name,
            move_count=r.move_count,
        )
        for r in records
    ]

    return KifuAlbumListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/albums/{album_id}", response_model=KifuAlbumDetail)
def get_kifu_album(album_id: int, db: Session = Depends(get_db)):
    """Get a single kifu album record with full SGF content."""
    record = db.query(KifuAlbum).filter(KifuAlbum.id == album_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Kifu album {album_id} not found")

    return KifuAlbumDetail(
        id=record.id,
        player_black=record.player_black,
        player_white=record.player_white,
        black_rank=record.black_rank,
        white_rank=record.white_rank,
        event=record.event,
        result=record.result,
        date_played=record.date_played,
        place=record.place,
        komi=record.komi,
        handicap=record.handicap,
        board_size=record.board_size,
        rules=record.rules,
        round_name=record.round_name,
        source=record.source,
        move_count=record.move_count,
        sgf_content=record.sgf_content,
    )
```

**Step 2: Register the router**

In `katrain/web/api/v1/api.py`, add the import and registration. The file currently has:

```python
from katrain.web.api.v1.endpoints import health, auth, analysis, games, users, live, tsumego
```

Change to:

```python
from katrain.web.api.v1.endpoints import health, auth, analysis, games, users, live, tsumego, kifu
```

And add after the tsumego line:

```python
api_router.include_router(kifu.router, prefix="/kifu", tags=["kifu"])
```

**Step 3: Test the API manually**

Run: `python -m katrain --ui web`
Then: `curl http://localhost:8001/api/v1/kifu/albums?page=1&page_size=3`
Expected: JSON with `items`, `total`, `page`, `page_size` fields

Then: `curl "http://localhost:8001/api/v1/kifu/albums?q=Sakata"`
Expected: Filtered results containing "Sakata"

Then: `curl http://localhost:8001/api/v1/kifu/albums/1`
Expected: Full record with `sgf_content`

**Step 4: Commit**

```bash
git add katrain/web/api/v1/endpoints/kifu.py katrain/web/api/v1/api.py
git commit -m "feat(kifu): add REST API endpoints for kifu album listing and detail"
```

---

### Task 4: Frontend Types & API Client

**Files:**
- Create: `katrain/web/ui/src/galaxy/types/kifu.ts`
- Create: `katrain/web/ui/src/galaxy/api/kifuApi.ts`

**Step 1: Create TypeScript types**

Create `katrain/web/ui/src/galaxy/types/kifu.ts`:

```typescript
// Types for kifu album (tournament game records) module

export interface KifuAlbumSummary {
  id: number;
  player_black: string;
  player_white: string;
  black_rank: string | null;
  white_rank: string | null;
  event: string | null;
  result: string | null;
  date_played: string | null;
  komi: number | null;
  handicap: number;
  board_size: number;
  round_name: string | null;
  move_count: number;
}

export interface KifuAlbumDetail extends KifuAlbumSummary {
  place: string | null;
  rules: string | null;
  source: string | null;
  sgf_content: string;
}

export interface KifuAlbumListResponse {
  items: KifuAlbumSummary[];
  total: number;
  page: number;
  page_size: number;
}
```

**Step 2: Create API client**

Create `katrain/web/ui/src/galaxy/api/kifuApi.ts`:

```typescript
// API functions for kifu album (tournament game records) module

import type { KifuAlbumListResponse, KifuAlbumDetail } from '../types/kifu';

const API_BASE = '/api/v1/kifu';

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

export const KifuAPI = {
  getAlbums: (options?: { q?: string; page?: number; page_size?: number }): Promise<KifuAlbumListResponse> => {
    const params = new URLSearchParams();
    if (options?.q) params.set('q', options.q);
    if (options?.page) params.set('page', String(options.page));
    if (options?.page_size) params.set('page_size', String(options.page_size));
    const query = params.toString();
    return apiGet(`/albums${query ? `?${query}` : ''}`);
  },

  getAlbum: (id: number): Promise<KifuAlbumDetail> => {
    return apiGet(`/albums/${id}`);
  },
};
```

**Step 3: Commit**

```bash
git add katrain/web/ui/src/galaxy/types/kifu.ts katrain/web/ui/src/galaxy/api/kifuApi.ts
git commit -m "feat(kifu): add frontend types and API client for kifu albums"
```

---

### Task 5: Kifu Library Page

**Files:**
- Create: `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx`

This page follows the `LivePage.tsx` and `TsumegoLevelsPage.tsx` patterns: fetch data on mount, display as a list, support search and pagination.

**Step 1: Create the page component**

Create `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx`:

```tsx
import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Typography,
  TextField,
  Pagination,
  CircularProgress,
  InputAdornment,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { KifuAPI } from '../api/kifuApi';
import type { KifuAlbumSummary } from '../types/kifu';
import { useTranslation } from '../../hooks/useTranslation';

const PAGE_SIZE = 20;

export default function KifuLibraryPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  const [items, setItems] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState(searchParams.get('q') || '');
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await KifuAPI.getAlbums({ q: query || undefined, page, page_size: PAGE_SIZE });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to fetch kifu albums:', err);
    } finally {
      setLoading(false);
    }
  }, [query, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Sync state to URL search params
  useEffect(() => {
    const params: Record<string, string> = {};
    if (query) params.q = query;
    if (page > 1) params.page = String(page);
    setSearchParams(params, { replace: true });
  }, [query, page, setSearchParams]);

  const handleSearch = () => {
    setPage(1);
    setQuery(searchInput);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleClick = (album: KifuAlbumSummary) => {
    navigate(`/galaxy/research?kifu_id=${album.id}`);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header + Search */}
      <Box sx={{ p: 3, pb: 2 }}>
        <Typography variant="h4" fontWeight="bold" sx={{ mb: 2 }}>
          {t('kifu:library', '棋谱库')}
        </Typography>
        <TextField
          fullWidth
          size="small"
          placeholder={t('kifu:search_placeholder', 'Search by player, event, date...')}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={handleKeyDown}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
          }}
          sx={{ maxWidth: 600 }}
        />
        {!loading && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {total} {t('kifu:records', 'records')}{query ? ` · "${query}"` : ''}
          </Typography>
        )}
      </Box>

      {/* List */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 3 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
            <CircularProgress />
          </Box>
        ) : items.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
            <Typography color="text.secondary">{t('kifu:no_results', 'No records found')}</Typography>
          </Box>
        ) : (
          items.map((album) => (
            <Box
              key={album.id}
              onClick={() => handleClick(album)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                py: 1.5,
                px: 2,
                mb: 1,
                borderRadius: 1,
                cursor: 'pointer',
                bgcolor: 'rgba(255,255,255,0.03)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' },
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              {/* Left: event + players */}
              <Box sx={{ minWidth: 0, flex: 1 }}>
                {/* Event line */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  {album.event && (
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {album.event}
                    </Typography>
                  )}
                  {album.round_name && (
                    <Typography variant="caption" color="text.secondary" noWrap>
                      · {album.round_name}
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary">
                    · {album.move_count}{t('kifu:moves', '手')}
                  </Typography>
                  {album.board_size !== 19 && (
                    <Typography variant="caption" color="text.secondary">
                      · {album.board_size}×{album.board_size}
                    </Typography>
                  )}
                </Box>
                {/* Players line */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" fontWeight={600} noWrap>
                    {album.player_black}
                  </Typography>
                  {album.black_rank && (
                    <Typography variant="caption" color="text.secondary">
                      {album.black_rank}
                    </Typography>
                  )}
                  <Typography
                    variant="caption"
                    sx={{
                      px: 0.8,
                      py: 0.1,
                      borderRadius: 0.5,
                      bgcolor: album.result?.startsWith('B') ? 'rgba(0,0,0,0.6)' : album.result?.startsWith('W') ? 'rgba(255,255,255,0.15)' : 'rgba(128,128,128,0.3)',
                      color: album.result?.startsWith('B') ? '#fff' : 'text.primary',
                      fontWeight: 600,
                      border: '1px solid rgba(255,255,255,0.1)',
                    }}
                  >
                    {album.result || '?'}
                  </Typography>
                  <Typography variant="body2" fontWeight={600} noWrap>
                    {album.player_white}
                  </Typography>
                  {album.white_rank && (
                    <Typography variant="caption" color="text.secondary">
                      {album.white_rank}
                    </Typography>
                  )}
                </Box>
              </Box>

              {/* Right: date */}
              <Typography variant="caption" color="text.secondary" sx={{ ml: 2, whiteSpace: 'nowrap' }}>
                {album.date_played || ''}
              </Typography>
            </Box>
          ))
        )}
      </Box>

      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(_, v) => setPage(v)}
            color="primary"
            shape="rounded"
          />
        </Box>
      )}
    </Box>
  );
}
```

**Step 2: Commit**

```bash
git add katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx
git commit -m "feat(kifu): add KifuLibraryPage with search and pagination"
```

---

### Task 6: Route & Sidebar Integration

**Files:**
- Modify: `katrain/web/ui/src/GalaxyApp.tsx` (add import + route)
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx` (add nav item)

**Step 1: Add route in GalaxyApp.tsx**

Add import at top of `GalaxyApp.tsx` (after the existing page imports):

```typescript
import KifuLibraryPage from './galaxy/pages/KifuLibraryPage';
```

Add route inside `<Route element={<MainLayout />}>`, after the `research` route and before `live`:

```tsx
<Route path="kifu" element={<KifuLibraryPage />} />
```

**Step 2: Add sidebar nav item in GalaxySidebar.tsx**

Add MUI icon import at top of file:

```typescript
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
```

Add new entry in the `menuItems` array, after the "Live" entry (at the end, before the closing `]`):

```typescript
{ text: t('kifu:library', '棋谱库'), icon: <LibraryBooksIcon />, path: '/galaxy/kifu', disabled: false },
```

**Step 3: Verify in browser**

Run: `cd katrain/web/ui && npm run dev`
Open: `http://localhost:5173/galaxy`
Expected: "棋谱库" appears in sidebar, clicking it loads the kifu page

**Step 4: Commit**

```bash
git add katrain/web/ui/src/GalaxyApp.tsx katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx
git commit -m "feat(kifu): add kifu library route and sidebar navigation"
```

---

### Task 7: Research Page — Load SGF from kifu_id

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/ResearchPage.tsx`

This enables clicking a record in the kifu library to open it in the Research page for analysis.

**Step 1: Add kifu_id URL param handling**

In `ResearchPage.tsx`, add these imports at the top:

```typescript
import { useSearchParams } from 'react-router-dom';
```

And import the API:

```typescript
import { KifuAPI } from '../api/kifuApi';
import { API } from '../../api';
```

Inside the `ResearchPage` component, after the existing `useGameSession` call, add:

```typescript
const [searchParams] = useSearchParams();
const kifuId = searchParams.get('kifu_id');
const [kifuLoaded, setKifuLoaded] = useState(false);
```

Add a new `useEffect` after the existing session init effect:

```typescript
useEffect(() => {
    if (kifuId && sessionId && !kifuLoaded) {
        KifuAPI.getAlbum(Number(kifuId)).then((album) => {
            API.loadSGF(sessionId, album.sgf_content).then(() => {
                setKifuLoaded(true);
            });
        }).catch((err) => {
            console.error('Failed to load kifu:', err);
        });
    }
}, [kifuId, sessionId, kifuLoaded]);
```

**Step 2: Verify end-to-end flow**

1. Open `/galaxy/kifu`
2. Click any record
3. Expected: Navigates to `/galaxy/research?kifu_id=N` and the game loads on the board

**Step 3: Commit**

```bash
git add katrain/web/ui/src/galaxy/pages/ResearchPage.tsx
git commit -m "feat(kifu): load tournament game SGF from kifu_id in Research page"
```

---

### Task 8: Run Existing Tests

**Files:** None (verification only)

**Step 1: Run the full test suite**

Run: `CI=true uv run pytest tests -v`
Expected: All existing tests PASS (no regressions from our changes)

**Step 2: Manual end-to-end verification**

1. Import data: `uv run python scripts/import_kifu.py`
2. Start server: `python -m katrain --ui web`
3. Test API: `curl http://localhost:8001/api/v1/kifu/albums?page=1&page_size=5`
4. Test search: `curl "http://localhost:8001/api/v1/kifu/albums?q=Sakata"`
5. Test detail: `curl http://localhost:8001/api/v1/kifu/albums/1`
6. Open browser: `/galaxy/kifu` — verify list displays with pagination
7. Click a record — verify it navigates to Research page and loads the game
8. Use search — verify filtering works

---

### Files Summary

| Action | File | Task |
|--------|------|------|
| Modify | `katrain/web/core/models_db.py` | 1 |
| Create | `scripts/import_kifu.py` | 2 |
| Create | `katrain/web/api/v1/endpoints/kifu.py` | 3 |
| Modify | `katrain/web/api/v1/api.py` | 3 |
| Create | `katrain/web/ui/src/galaxy/types/kifu.ts` | 4 |
| Create | `katrain/web/ui/src/galaxy/api/kifuApi.ts` | 4 |
| Create | `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.tsx` | 5 |
| Modify | `katrain/web/ui/src/GalaxyApp.tsx` | 6 |
| Modify | `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx` | 6 |
| Modify | `katrain/web/ui/src/galaxy/pages/ResearchPage.tsx` | 7 |
