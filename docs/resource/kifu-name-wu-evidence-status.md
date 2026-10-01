# Go Seigen pending evidence status

Capture date: 2026-10-02. Producer model: `gpt-6-luna` (requested `gpt-5.6-luna` was unavailable). All records use symbolic owner `{"kind":"player","ref":"wu_qingyuan"}` and remain pending. No candidate approval, database write, or registry change was made.

The access-controlled JSONL is `/Users/fan/.local/share/kifu-name-audit/2026-10-02/wu-pending-evidence.jsonl` (mode `0600`). It contains 11 language records. `scripts/kifu_name_research.py validate` exited 0: **11 valid pending record formats**, with **5 source checks capturing exact names** and **6 source checks incomplete**. A valid pending format is not an approval or a complete language research scope.

Captured exact target-language name passages:

- `cn`: `吴清源`, China sports authority page. HTML omitted language metadata; the visible Chinese passage was reviewed and recorded as `zh-Hans` / `reviewed_text`.
- `tw`: `吳清源`, PTS Taiwan.
- `jp`: `呉清源`, Nihon Ki-in.
- `ko`: `우칭위안`, Korea Baduk Association player record (also displays `오청원`).
- `tr`: `Go Seigen`, Asialogy Turkish biography.

Incomplete source checks: `en` (registered CWI Go archive did not contain the exact candidate); `de`, `es`, and `fr` (registered evidence pages are PDFs; HTML capture could not produce body text/hash); `ru` (registered Go Library request timed out); `ua` (registered federation homepage did not expose an exact player passage). These remain incomplete, with no fabricated body hashes or observed language claims. Wiki evidence and independent wiki identity corroboration were not captured in this pass; any future wiki-based checks need actual revision IDs and separately published identity evidence.

The registry's negative-claim scopes remain incomplete for every language. This pilot therefore makes no claim that any language lacks a conventional name and proposes no production names.
