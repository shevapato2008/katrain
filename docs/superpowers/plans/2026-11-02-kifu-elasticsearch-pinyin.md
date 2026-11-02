# Kifu Elasticsearch Chinese Pinyin Search Implementation Plan (v2 - Revised)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Chinese Pinyin (full pinyin, initials/abbreviations, and spaced pinyin) search across player and event names in the KaTrain Kifu Elasticsearch library, while maintaining PostgreSQL as the authoritative store (0 DDL, 0 schema changes), sub-200ms production response times, zero regressions on existing exact Chinese/English/Japanese/Korean search, strict collision safety, and full SGF preview verification.

---

## 0. Architecture & Boundary Analysis

### 0.1 PostgreSQL Database Boundary
- **Authoritative Single Source of Truth:** PostgreSQL remains the sole source of truth for all game metadata, SGF files, player entities, event editions, ranks, and analysis records.
- **Database Schema Changes:** **Zero (0) changes required**.
  - No new PostgreSQL tables, columns, indexes, or triggers.
  - The previous release completely retired the legacy `kifu_search_prepared_*` tables and triggers, freeing ~3.51 GB disk space across TEST and PROD.
  - PostgreSQL continues to store standard canonical Chinese characters (e.g. `王星昊`, `吴清源`, `柯洁`, `朴文垚`).
  - Search reads and ranking take place entirely in Elasticsearch; PostgreSQL is queried only to batch-enrich the paginated 20 items (`_enrich_elasticsearch_page`) by `album_id`.

### 0.2 Elasticsearch 9.5.5 & Plugin Architecture
- **Plugin Requirement:** Add `analysis-pinyin` plugin for Elasticsearch 9.5.5.
  - Pinned release: `https://release.infinilabs.com/analysis-pinyin/stable/elasticsearch-analysis-pinyin-9.5.5.zip`
  - Platform: `linux/amd64`
  - Checksum (SHA512): `b39c1bc05544b44a5dcee493c2072bde456a790a1745cd022a8f57d466a90607940ede5ccbd482c89efae8c3969ffeaeeee6a8a93a776b76fec3bd45d52116b9`
  - Pinned in `deploy/elasticsearch/versions.lock.json` alongside `analysis-ik`, `analysis-kuromoji`, and `analysis-nori`.
  - Built via `deploy/elasticsearch/Dockerfile` with explicit checksum validation and installation.
- **Python Dependencies:**
  - Add `pypinyin>=0.50.0` to `requirements-web.txt`, `requirements-cron.txt`, and `pyproject.toml` (under `[project.optional-dependencies] web`).
  - Used strictly during offline index projection (`search_projection.py`), not on the critical search query path.

### 0.3 Analysis Configuration (`INDEX_SETTINGS`)
- **`pinyin_filter`**:
  - `type: "pinyin"`
  - `keep_first_letter: true` (generates initials, e.g. `wxh` for `王星昊`, `wqy` for `吴清源`)
  - `keep_separate_first_letter: false`
  - `keep_full_pinyin: true` (generates `wang`, `xing`, `hao`)
  - `keep_joined_full_pinyin: true` (generates joined full pinyin, e.g. `wangxinghao`)
  - `keep_none_chinese: true`
  - `keep_none_chinese_together: true`
  - `keep_original: true` (retains original Hanzi characters)
  - `limit_first_letter_length: 16`
  - `lowercase: true`
  - `trim_whitespace: true`
  - `remove_duplicated_term: true`
- **Analyzers:**
  - **`player_pinyin_analyzer`** (Index Analyzer for player names):
    - `tokenizer: "keyword"`, `filter: ["pinyin_filter", "lowercase"]`
    - Using `keyword` tokenizer ensures `pinyin_filter` receives the complete, untokenized player name so `keep_joined_full_pinyin` (`wangxinghao`) and `keep_first_letter` (`wxh`) are generated intact.
  - **`text_pinyin_analyzer`** (Index Analyzer for events and full text):
    - `tokenizer: "ik_smart"`, `filter: ["pinyin_filter", "lowercase"]`
  - **`pinyin_search_analyzer`** (Query Analyzer):
    - `tokenizer: "standard"`, `filter: ["lowercase"]`

### 0.4 Mapping Configuration (`INDEX_MAPPING`) & Multi-Fields
To satisfy the strict **< 2 GiB index store budget** (~800MB target across 17.7k albums) without ballooning document `_source` size:
- Use Elasticsearch **multi-fields** (`fields`) on existing text fields rather than duplicating large strings in `_source`:
  - `display.cn.player_black`: `type: "keyword"`, `fields: {"pinyin": {"type": "text", "analyzer": "player_pinyin_analyzer", "search_analyzer": "pinyin_search_analyzer"}}`
  - `display.cn.player_white`: `type: "keyword"`, `fields: {"pinyin": {"type": "text", "analyzer": "player_pinyin_analyzer", "search_analyzer": "pinyin_search_analyzer"}}`
  - `display.cn.event`: `type: "text"`, `fields: {"raw": {"type": "keyword"}, "pinyin": {"type": "text", "analyzer": "text_pinyin_analyzer", "search_analyzer": "pinyin_search_analyzer"}}`
  - `search_text`: `type: "text"`, `fields: {"pinyin": {"type": "text", "analyzer": "text_pinyin_analyzer", "search_analyzer": "pinyin_search_analyzer"}}`

### 0.5 Dual-Tier Pinyin Search Model & Collision Safety
1. **Tier 1: O(1) Exact Term Document Projection (`search_projection.py`)**:
   - In addition to Hanzi terms (`王星昊`), pre-generate phonetic terms for canonical Chinese players and high-frequency events:
     - Full pinyin (e.g. `wangxinghao`, `wuqingyuan`, `kejie`)
     - Initials / abbreviations (e.g. `wxh`, `wqy`, `kj`)
   - **Baduk Surname Polyphone Dictionary:**
     - Polyphone map: `BADUK_SURNAME_POLYPHONES = {"朴": ["piao", "pu"], "仇": ["qiu"], "单": ["shan"], "解": ["xie"], "查": ["zha"]}`.
     - Generates projections for both standard and Go-specific readings (e.g. `piaowenyao` / `pwy` and `puwenyao` for `朴文垚`).
   - **Collision Safety via Clustering:**
     - Pinyin terms are merged into the `groups` / `aliases` aggregation dictionary alongside Hanzi and English names.
     - Passed through `classify_qualified_names` to detect multiple owner collisions.
     - Unambiguous terms become `exact_player` (`{"terms": {"black_player_id": [id], "white_player_id": [id]}}`).
     - Colliding terms (e.g. identical initials across multiple players) safely fall into `shared_players` or `generic` without overwriting document keys.
2. **Tier 2: Query Preprocessing & Multi-Field Search (`search_terms.py`)**:
   - **Spaced Pinyin Normalization**:
     - Normalize query `q`: detect English/space strings and generate condensed variant `q_condensed = re.sub(r"\s+", "", q).lower()`.
     - In `read_album_page_elasticsearch`: `mget` probes both `term_document_id(q)` and `term_document_id(q_condensed)`.
     - Queries like `"wang xing hao"` or `"WangXingHao"` hit `wangxinghao` in O(1) time (<20ms).
   - **Generic Pinyin Fallback**:
     - When query does not match a term document, compile `bool` query across `search_text.pinyin` (boost 1.0), `display.cn.event.pinyin` (boost 2.0), and `display.cn.player_*.pinyin` (boost 5.0).
     - Retains full ranking priorities: player matches > event matches > full text matches.

---

## 1. Implementation Chunks & Tasks

### Chunk 1: Dependencies, Plugin Pinning & Docker Packaging

#### Task 1: Declare Dependencies & Update ES Manifest & Dockerfile
**Files:**
- Modify: `deploy/elasticsearch/versions.lock.json`
- Modify: `deploy/elasticsearch/Dockerfile`
- Modify: `deploy/elasticsearch/prepare_plugins.py`
- Modify: `requirements-web.txt`
- Modify: `requirements-cron.txt`
- Modify: `pyproject.toml`
- Modify: `tests/web_ui/test_kifu_search_es.py`

- [ ] **1.1** In `deploy/elasticsearch/versions.lock.json`, add the `analysis-pinyin` plugin configuration (name, filename, download URL, and SHA512 hash).
- [ ] **1.2** In `deploy/elasticsearch/Dockerfile`, add the plugin install command:
  ```dockerfile
  && /usr/share/elasticsearch/bin/elasticsearch-plugin install --batch file:///tmp/kifu-es-plugins/elasticsearch-analysis-pinyin-9.5.5.zip \
  ```
- [ ] **1.3** In `requirements-web.txt`, `requirements-cron.txt`, and `pyproject.toml`, add `pypinyin>=0.50.0`.
- [ ] **1.4** Verify `prepare_plugins.py` validates `analysis-pinyin-9.5.5.zip` descriptor and checksum.
- [ ] **1.5** In `tests/web_ui/test_kifu_search_es.py`, assert that `analysis-pinyin` is part of the required plugin set and lockfile.
- [ ] **1.6** Commit: `feat(kifu-es): declare pypinyin dependency and pin analysis-pinyin in elasticsearch manifest`.

---

### Chunk 2: ES Analyzers, Multi-Field Mappings & Projection Logic

#### Task 2: Pinyin Analyzers and Multi-Field Mapping Definition
**Files:**
- Modify: `katrain/web/kifu/search_es.py`
- Modify: `tests/web_ui/test_kifu_search_documents.py`

- [ ] **2.1** In `katrain/web/kifu/search_es.py` (`INDEX_SETTINGS`):
  - Add `pinyin_filter` configuration with full pinyin, joined full pinyin, and first letter options.
  - Define `player_pinyin_analyzer` (`keyword` tokenizer + `pinyin_filter` + `lowercase`).
  - Define `text_pinyin_analyzer` (`ik_smart` tokenizer + `pinyin_filter` + `lowercase`).
  - Define `pinyin_search_analyzer` (`standard` tokenizer + `lowercase`).
- [ ] **2.2** In `INDEX_MAPPING`:
  - Add `.pinyin` multi-fields to `search_text`, `display.cn.event`, and player name fields.
  - Verify mapping does not add redundant top-level storage fields to avoid store bloat.
- [ ] **2.3** In `tests/web_ui/test_kifu_search_documents.py`, assert settings and mapping structure, analyzer definitions, and schema compatibility.
- [ ] **2.4** Commit: `feat(kifu-es): configure pinyin analyzers and multi-field mappings`.

#### Task 3: Pinyin Term Projection, Polyphones & Query Normalization
**Files:**
- Modify: `katrain/web/kifu/search_projection.py`
- Modify: `katrain/web/kifu/search_terms.py`
- Modify: `katrain/web/kifu/library_search.py`
- Modify: `tests/web_ui/test_kifu_search_es.py`

- [ ] **3.1** In `katrain/web/kifu/search_projection.py`:
  - Implement `_chinese_pinyin_variants(name)` with `pypinyin` and `BADUK_SURNAME_POLYPHONES` support (`朴` -> `piao`/`pu`, `仇` -> `qiu`, `单` -> `shan`, `解` -> `xie`, `查` -> `zha`).
  - Generate full pinyin and initials variants for canonical Chinese player names.
  - Merge phonetic terms into the `groups` / `aliases` aggregation dictionary in `_classification_documents`, preserving collision safety via `classify_qualified_names`.
- [ ] **3.2** In `katrain/web/kifu/search_terms.py` & `katrain/web/kifu/library_search.py`:
  - In `read_album_page_elasticsearch`: implement spaced pinyin normalization (`re.sub(r"\s+", "", q)`).
  - In `mget`: probe both raw `q` and normalized `q_condensed` so queries like `"wang xing hao"` or `"WangXingHao"` hit `wangxinghao` in O(1) time.
  - In `compile_query`: add fallback clauses targeting `.pinyin` multi-fields with boosted player scores.
- [ ] **3.3** Add comprehensive unit and regression tests in `tests/web_ui/test_kifu_search_es.py`:
  - Full pinyin exact match: `wangxinghao` -> 506 items of 王星昊.
  - Initials match: `wxh` -> 506 items of 王星昊.
  - Spaced pinyin: `wang xing hao` -> 506 items of 王星昊.
  - Case insensitivity: `WangXingHao`, `WxH`, `WuQingYuan`.
  - Polyphone match: `piaowenyao` and `pwy` -> returns albums of 朴文垚.
  - Event pinyin: `chunlan` / `clb` -> returns albums of 春兰杯.
  - SGF preview verification: verify first item returns non-empty `sgf_content` and valid metadata preview.
  - Zero regression assertion on Chinese (`王星昊`), English, Japanese, and Korean queries.
- [ ] **3.4** Format code with `black -l 120 katrain tests scripts deploy`.
- [ ] **3.5** Commit: `feat(kifu-es): implement pinyin term projection, polyphone mapping, and spaced query normalization`.

---

### Chunk 3: Local Integration Verification & Index Rebuilding

#### Task 4: Local Test Suite & Index Rebuild Verification
**Files:**
- Modify: `tests/web_ui/test_kifu_es_contract.py`
- Modify: `scripts/kifu_search_index.py`

- [ ] **4.1** Run full local test suite: `pytest tests/web_ui/test_kifu_*.py -v` (100% pass required).
- [ ] **4.2** Verify candidate index creation in `scripts/kifu_search_index.py` with pinyin mappings and check that index size remains well under the 2 GiB limit.
- [ ] **4.3** Commit: `test(kifu-es): verify complete pinyin test suite and index sizing`.

---

### Chunk 4: Multi-Environment Deployment & Acceptance Testing

#### Task 5: Staging Deployment on TEST (`home-ubuntu`)
**Host:** `home-ubuntu` (`go.sailorvoyage.top`)
- [ ] **5.1** Rebuild Docker image `katrain-elasticsearch:9.5.5-plugins` with `analysis-pinyin` on `home-ubuntu`.
- [ ] **5.2** Restart Elasticsearch container and verify `elasticsearch-plugin list` reports:
  - `analysis-ik`
  - `analysis-kuromoji`
  - `analysis-nori`
  - `analysis-pinyin`
- [ ] **5.3** Build candidate index with pinyin support, verify stats (doc count, size < 2 GiB), switch alias `kifu-search`.
- [ ] **5.4** Deploy updated `katrain-web` and `katrain-cron` containers.
- [ ] **5.5** Verify TEST public queries:
  - `https://go.sailorvoyage.top/api/v1/kifu/albums?q=wangxinghao` -> HTTP 200, 506 items, valid SGF preview.
  - `https://go.sailorvoyage.top/api/v1/kifu/albums?q=wxh` -> HTTP 200, 506 items.
  - `https://go.sailorvoyage.top/api/v1/kifu/albums?q=wang+xing+hao` -> HTTP 200, 506 items.
  - `https://go.sailorvoyage.top/api/v1/kifu/albums?q=piaowenyao` -> HTTP 200, valid SGF preview.

#### Task 6: Production Deployment on PROD (`ucloud-v100`)
**Host:** `ucloud-v100` (`modelstella.com` / `117.50.177.254`)
- [ ] **6.1** Build and verify `katrain-elasticsearch:9.5.5-plugins` with `analysis-pinyin` on `ucloud-v100`.
- [ ] **6.2** Restart PROD ES container, verify plugins.
- [ ] **6.3** Run `scripts/kifu_search_index.py` to build candidate index `kifu-search-<timestamp>-<hash>` in quiescent window.
- [ ] **6.4** Verify candidate index docs (176,949), store size (< 2 GiB, target ~800MB), analyzers, and atomic alias switch.
- [ ] **6.5** Deploy updated `katrain-web` container with atomic swap script.
- [ ] **6.6** PROD Acceptance & Benchmark Verification:
  - Query `wangxinghao` and `wxh`: HTTP 200, latency < 100ms, 506 items, valid SGF preview.
  - Query `wang xing hao`: HTTP 200, latency < 100ms, 506 items.
  - Query `wuqingyuan` and `wqy`: HTTP 200, valid SGF preview.
  - Query `piaowenyao` and `pwy`: HTTP 200, valid SGF preview.
  - Sustained load test: 30 QPS x 10s (P50 < 30ms, P95 < 50ms, 0 errors, 0 diffs).
  - Verify public HTTPS at `https://modelstella.com/`.

---

## 2. Review & Quality Gates
- **Plan Review:** Argon (high effort) independent agent review (Round 2 final confirmation).
- **Implementation:** Subagent-driven development (Gemini 3.8 Flash for code modifications).
- **Final Code Audit:** Argon (high effort) independent agent audit prior to release.
- **Git Release Workflow:** Strict 4-step workflow per Repository Guidelines:
  1. Fetch latest `develop`, merge into feature branch, verify locally, commit and push feature branch.
  2. Merge feature branch into `develop` and push `origin/develop`.
  3. Update `smartbox-software/vendor/katrain` submodule pointer to the new `develop` commit, commit and push parent repository.
  4. Deploy integrated release to both `home-ubuntu` and `ucloud-v100`; verify service health and representative actual pages.
