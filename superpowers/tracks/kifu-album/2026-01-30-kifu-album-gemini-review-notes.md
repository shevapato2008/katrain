# Code Review: Kifu Album Module

## Status: Approved with Required Changes

This is a solid, well-structured plan that follows the project's existing patterns. However, as a website development expert and Go professional, I have identified a few **critical data integrity** and **UX issues** that need to be addressed before implementation.

### 1. 🛑 Critical: Data Integrity & Encoding (The "Mojibake" Trap)
The plan proposes reading SGF files twice: once via `SGF.parse_file` (which has robust encoding detection) and once via `sgf_path.read_text(errors="ignore")`.
*   **The Risk:** `errors="ignore"` will silently strip characters from non-UTF-8 files (common in older SGF collections, e.g., GB2312, Shift-JIS). You will store corrupted game records.
*   **The Fix:** Since `SGF.parse_file` already successfully parses the game into an object, **use `root.sgf()` to generate a clean, standardized UTF-8 string** for the database. This ensures consistency and fixes encoding issues permanently.

### 2. ⚡ Performance: N+1 Bandwidth Issue
*   **The Issue:** `db.query(KifuAlbum).all()` fetches *all* columns, including the potentially massive `sgf_content` (which can contain huge variation trees), for every item in the list.
*   **The Fix:** In `list_kifu_albums`, use `defer`:
    ```python
    from sqlalchemy.orm import defer
    query = query.options(defer(KifuAlbum.sgf_content))
    ```

### 3. 🐛 Frontend Logic: Navigation & State
*   **Broken Back Button:** In `KifuLibraryPage.tsx`, you initialize state from URL params (`useState(searchParams.get('q'))`), but you don't update state *when* the URL changes (e.g., user clicks Back).
    *   **Fix:** Remove `page` and `query` state variables. Derive them directly from `searchParams` during render, or add a `useEffect` to sync state *from* params.
*   **Stuck State in ResearchPage:** If a user views Game A (`?kifu_id=1`), then navigates to Game B (`?kifu_id=2`), the `kifuLoaded` state will remain `true` (from Game A), and Game B won't load.
    *   **Fix:** You need to reset `kifuLoaded` when `kifuId` changes:
    ```typescript
    useEffect(() => { setKifuLoaded(false); }, [kifuId]);
    ```

### 4. 🎨 UX & Polish (Go Professional Perspective)
*   **Result Display:** "B+R", "W+2.5" are standard. Ensure the parser standardizes this. Historical games sometimes have "Draw" or "Void". The UI handles this well with the generic string type.
*   **Navigation:** When I click a game and go to `ResearchPage`, how do I get back?
    *   **Suggestion:** If `kifu_id` is present in the URL, `ResearchPage` should probably show a "Back to Library" button in the top left or within the right-hand panel.

---

### Revised Implementation Details

**A. Updated `scripts/import_kifu.py` (Encoding Fix)**
```python
# ... inside parse_sgf_file ...
root = SGF.parse_file(str(sgf_path))
# Standardize to UTF-8 using the parser's output instead of raw read
sgf_content = root.sgf() 

data = {
    # ... other fields ...
    "sgf_content": sgf_content,
    # ...
}
```

**B. Updated `kifu.py` (Performance Fix)**
```python
# ... inside list_kifu_albums ...
query = db.query(KifuAlbum).options(defer(KifuAlbum.sgf_content))
```

**C. Updated `KifuLibraryPage.tsx` (Back Button Fix)**
```typescript
// ... inside component ...
const [searchParams, setSearchParams] = useSearchParams();
// Derive state directly from URL, fallback to defaults
const page = Number(searchParams.get('page')) || 1;
const query = searchParams.get('q') || '';
// Local input state for the text field (debounced or on-enter)
const [searchInput, setSearchInput] = useState(query);

// Sync local input when URL changes (e.g. Back button)
useEffect(() => {
    setSearchInput(query);
}, [query]);

const fetchData = useCallback(async () => {
    // ... same logic, uses query/page vars ...
}, [query, page]);
```

**D. Updated `ResearchPage.tsx` (Loader Fix)**
```typescript
useEffect(() => {
    setKifuLoaded(false);
}, [kifuId]);

useEffect(() => {
    if (kifuId && sessionId && !kifuLoaded) {
        // ... load logic ...
    }
}, [kifuId, sessionId, kifuLoaded]);
```
