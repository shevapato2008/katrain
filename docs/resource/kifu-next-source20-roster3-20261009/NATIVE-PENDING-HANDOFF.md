# Roster 3 native pending handoff

The source packet is `next20-source-only-firstpass-proposal.json`; `astra-pragmatic-identity-decision.md` accepts all 20 at the **source level**. The bounded saved post-591 mapping is `next20-current-scoped-request.json` (PROD IDs and independently matched TEST IDs). Root must read the current owners after batch 592 or later before any binding. No cloud capture or SQL write has been run by this worker.

The current native conventional-name gate requires a target display in an `official`, `language_go`, `wikipedia_article`, or `encyclopedia` source. Thirteen Korean names have actual KBA GET pages; 5034 has Japanese Kifudepot; 5036 has English u-go.net; 5296 has a Taiwanese Go roster. The four community-only Korean names 4071, 6329, 5495, and 4331 remain **native gate holds**. Daum is proposed at honest `reference` tier and serves as the complete bilingual identity bridge for the first 13 Korean records. KBA and TVBaduk share stable codes/content and are not counted as independent identity publications. The 5036 Go4Go HTTP 500 page is excluded.

Root may run the bounded read-only capture once PROD and TEST are stable, with its pinned native image IDs:

```sh
python docs/resource/kifu-next-source20-roster3-20261009/capture-next20-scoped-readonly.py --root-confirms-current-state --prod-image 'sha256:...' --test-image 'sha256:...'
```

That script reads exactly 20 owner IDs in each environment, their 13-field name preimages, all owner evidence/aliases, four qualified languages, current catalog SHA, latest batch/registry, and only their linked SGF metadata plus UTF-8 content hash. It does not call the global inventory or 64k-name snapshot. Then prepare each environment's 16 native-ready pending records locally:

```sh
python docs/resource/kifu-next-source20-roster3-20261009/build-next20-native-pending.py --env PROD
python docs/resource/kifu-next-source20-roster3-20261009/build-next20-native-pending.py --env TEST
```

The builder validates the actual captured source bodies and native pending records against the saved post-591 inventory **only provisionally**. It proposes a new `reference` registry row for Daum and marks the four community-only names held. Root must bind a fresh inventory, review the exact registry/source/CAS packet, and provide a reviewed fresh input before optional unsigned assembly via `assemble-next20-after-root-review.py`. That assembler creates a 16-name conventional bundle without a global approved-name snapshot, and it does not sign or apply it. If four replacement players arrive, amend the source packet, recapture the expanded scope, and rebuild rather than silently treating community reference as a qualifying primary name source.

## Focused 16-name path for the next player batch

`next16-current-scoped-request.json` excludes the four reference-only names. Root can run `capture-next16-scoped-readonly.py` after its preceding batch is applied, passing the exact expected latest batch ID and pinned PROD/TEST importer image IDs. It reads 16 owners, all name preimages with 13 physical fields, their aliases and evidence, current catalog hash and registry, plus one parameterized physical `SELECT *` over associated `kifu_albums`. The SGF content is represented by its UTF-8 SHA-256. The actual unique album count and owner slots are recorded from that capture; the scripts do not assume 609/614 or any other earlier batch scope.

```sh
python docs/resource/kifu-next-source20-roster3-20261009/capture-next16-scoped-readonly.py --root-confirms-current-state --expected-latest-batch 594 --prod-image 'sha256:...' --test-image 'sha256:...'
python docs/resource/kifu-next-source20-roster3-20261009/build-next16-native-pending.py --env PROD
python docs/resource/kifu-next-source20-roster3-20261009/build-next16-native-pending.py --env TEST
```

The `594` argument is an example of the intended preceding batch, not a claim that batch 594 is already applied. The 16-name builder keeps the complete source packet for review, uses KBA GET as primary for 13 KO names, Kifudepot for JP, u-go.net for EN, and the actual Taiwan Go roster URL for TW. Daum is registered as a reference and cannot itself qualify a conventional name. The target breakdown is KO 13, JP 1, TW 1, EN 1; all 16 decisions are conventional.

After root creates per-environment `ENV-root-reviewed-fresh.json.gz` with `status: root_approved_fresh_context`, matching draft SHA, registry/owners/catalog/latest-batch, reviewed candidates, and fresh native inventory, use `assemble-next16-after-root-review.py --env ENV --root-reviewed-fresh PATH`. Then `prepare-next16-execution.py --prod-image IMAGE --test-image IMAGE` creates a small unsigned transport and manifest. The required `root-next16-execution-approval.json` is deliberately absent: root must create it with `reviewer_id: "/root"`, `allow_apply: true`, the exact proposed manifest file SHA, both canonical bundle SHA values, and matching pinned image IDs. Once staged, `next16-run.py ENV baseline|dry-run|apply|verify` performs the protected native CLI phases. Baseline and verify compare all non-target name rows, 64→80 strict qualified names, 0→16 five-language owners, and the captured complete physical game scope. Root alone signs, invokes apply, and handles receipts.
