# Lee player 143: producer addendum for the 34-link unsigned bundle

Read-only producer verification of the controlled artifact at `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-34-current-prod/bundle-34-current-bound-unsigned-pending-review.json`.

## Artifact and producer-side checks

- Bundle file SHA-256: `815566ad7a1cc10033e29fbd500b0a322a220c04ace059774b04a363bc928d68`.
- Canonical bundle SHA-256: `4abfde85df59c6871ced05650d72c738292f6af5818fecb1d2aa6ee80647124d`.
- Link-set SHA-256: `fbeef9dbe59e095589aa2a74611580ff81aa18f6bbdca99e2614a341cc807e7e`.
- Shared identity-scope SHA-256: `1f4e29a2d0892c37153ea747f479fce46366b69a64ab10f509e1e0521f418e67`.
- Bound context: format 2, base inventory SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`, catalog SHA-256 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`, and raw-scope SHA-256 `43b19733404467dbe5300258627767d32ecd13138de7ac81d26a5a720acac9ec`.
- Scope is exactly 34 album links and 11 language candidates. Every candidate has a producer preimage binding from the same production capture, including explicit null preimages for languages with no current row. Bindings record the producer actor/model, capture time/hash, bind time, and the source candidate row hash.
- All 34 links share the same pending identity scope. Each has 36 checks. The Russian candidate retains the approved `conflict_adjudication` and `excluded_candidates` fields.
- For `98043/black`, the CyberOro original-game SGF excerpt is present and bound to body SHA-256 `6de744604394c38bf5dc893e170e29b3c11b3edad36a10aa4576c906d373ada7`; the Korean Baduk Association profile excerpt is present and bound to body SHA-256 `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6`.

The validator command was run offline with the controlled format-2 inventory, registry `2026-10-02.3`, and the reviewed research JSONL:

```text
uv run python scripts/kifu_name_batch.py validate --bundle <controlled unsigned bundle> --registry docs/resource/kifu-name-source-registry-2026-10-02.3.json --inventory <reviewed format-2 inventory> --evidence <reviewed research.jsonl>
```

It returned exit code 1, `ready=false`, `write_ready=false`, `approved=0`, `missing=0`, and `write_errors=[]`. The 34 link errors are exclusively pending identity reviews. The 11 member-outside-scope and 11 candidate-outside-finite-member errors cascade from those unapproved links; the 11 candidates themselves remain pending independent review. This is the expected HOLD state and does not indicate an input-format, hash, excerpt, or name-preimage error.

## Remaining review gates

An independent reviewer must verify and sign the frozen 34-link identity scope and each of the 11 candidate preimage bindings. The validator must then be rerun against the frozen reviewed artifacts. No reviewer signature, dry-run, approval, import, or database write is present or implied by this producer addendum. The controlled JSON and addendum sidecar remain outside the repository; detailed source bodies and production row captures remain in the private mode-0600 capture directory.
