# Duplicate-GN import review, 2026-10-02

**PASS — no Critical or Important findings in `62757d7b` + `fe71e4fc`.**

The new import exception requires absent root `EV`, a path under `DATA_DIR/19x19`, exact root `SO[https://19x19.com]`, exactly two ordered root `GN` values, and exact first value `GNUGo3.8`. The second value must be nonempty and not classified as a program label or SGF fragment. Exactly one root `GC` must equal that value or continue it with ` | `. The three earlier counterexamples—another program label, a partial title prefix, and duplicate conflicting `GC` values—are now rejected. `SGF.parse_file` preserves duplicate `GN` values in order, and serialization retains them.

`parse_sgf_file` changes the chosen event for eligible new imports only. The import loop skips existing source paths and this patch does not update existing `kifu_albums.event` rows. The bounded existing-row remedy remains separate.

Verification: `python -m pytest -q tests/web_ui/test_import_kifu_history.py tests/web_ui/test_kifu_name_parse.py` passed (23 tests). The parent agent separately reported a read-only replay of all 1,160 audited clone SGFs with zero exclusions under the new guards; this review did not independently access those full SGFs.
