# Go Seigen pending evidence status

Capture date: 2026-10-02. Producer model: `gpt-6-luna` (requested `gpt-5.6-luna` was unavailable). All records now use existing owner `{"kind":"player","id":1}` after checking the pinned production inventory; the research records and their source-check owners agree. Candidate rows remain pending. No candidate approval, database write, or registry change was made.

The access-controlled JSONL is `/Users/fan/.local/share/kifu-name-audit/2026-10-02/wu-pending-evidence.jsonl` (mode `0600`). It contains 11 language records. `scripts/kifu_name_research.py validate` exited 0: **11 valid pending record formats**, with **4 record-level `found` scopes** (`cn`, `jp`, `ko`, `tr`) and **7 incomplete scopes**. The validator's format pass is not approval or a complete language research scope.

Found candidates and captured passages:

- `cn`: `吴清源`, China sports authority page. HTML omitted language metadata; the visible Simplified Chinese passage was reviewed and recorded as `zh-Hans` / `reviewed_text`.
- `jp`: `呉清源`, Nihon Ki-in player profile.
- `ko`: `우칭위안`, Korea Baduk Association player record (also displays `오청원`).
- `tr`: `Go Seigen`, Turkish Go School article directly states “Wu Qingyuan (Go Seigen)” in Turkish prose. A second Turkish reference passage is retained as supplementary evidence.

The pinned production inventory contains player ID 1, so this evidence attaches to that existing identity rather than proposing a duplicate symbolic player. Four pending conventional candidate rows for `cn`, `jp`, `ko`, and `tr` are stored in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/wu-pending-candidates.jsonl` (mode `0600`). Their `research_sha256` values bind to the updated records. `validate_candidate` passed for all four against production inventory SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`; no reviewer fields or approval status are present.

The Japanese original-name basis for `cn`, `jp`, `ko`, and `tr` is captured from the official Nihon Ki-in profile: `呉清源` and its reading are present in Japanese text, with direct-page body hash and fetch metadata stored in each record.

The remaining incomplete scopes are `en` (registered CWI Go archive did not contain the exact candidate); `tw` (PTS Taiwan has a found name passage, but the requested substantive Wikipedia passage and separate PTS corroboration pair was not captured); `de`, `es`, and `fr` (registered evidence pages are PDFs; HTML capture could not produce body text/hash); `ru` (registered Go Library request timed out); and `ua` (registered federation homepage did not expose an exact player passage). These remain incomplete, with no fabricated body hashes or observed language claims. Wiki evidence was not captured for any found scope; wiki-based checks require actual revision IDs and separately published identity evidence.

The registry's negative-claim scopes remain incomplete for every language. This pilot therefore makes no claim that any language lacks a conventional name and proposes no production names.
