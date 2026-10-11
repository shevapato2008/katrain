# Bounded native patch and capture preparation review

Reviewed and finally rechecked 2026-10-09: `backport_mixed_game.py`, `build_source.py`, `selection.json`, `source-packet.json`, `capture.py`, `run_capture.py`, `bind_unsigned.py`, the two focused check scripts, and README. The reviewer used the actual locally fetched TEST/PROD r5 modules. No database, Docker build, cloud, deployment or Git mutation was performed by this review.

## Native compatibility patch — PASS

Both fetched modules have identical SHA-256 `d97e8e88a4e484b684106e0b06296b372066645961b79647425154b5c5102499`. Applying the source transform in memory independently reproduces `0aab89aa5a93541dde26381254d3e9ff1a1a1dc6707b6089ba6fd6f473506b1f`.

The complete diff contains only the finite positive-number/game expression and mixed-only `game` allowance/validation in the two existing parts/research gates. No parser, ORM, other module, or unrelated round rule is copied. The transform checks the exact input hash and each replacement count, refuses an existing output file, and leaves the input untouched.

Independent checks reproduced **2/250** C76+Han records accepted by old r5 and **250/250** by the patch. Invalid game-number examples, non-mixed `game`, and altered native input bytes reject. The new source packet and 150-title selection also reproduce exactly from their pinned source bytes:

- Selection: `f06a6a87d600f3fa6d710ce35914f65534b0a11d257c749941c7dedcd48d43eb`.
- Packet: `eacd589a90178e806c7b76239d7d9444cbfc7d3d46f628b683e16eced6a928bb`.

This PASS permits proceeding with the narrow administrative-image preparation; it is not approval for owner/name SQL or production data changes.

## Capture and unsigned binding — PASS

**Both reported Important findings are closed. No remaining Essential or Important blockers in this bounded read-only preparation review.**

1. **Post-owner scope drift — closed.** `frozen_post_owner_scope` loads the same environment's actual pre-owner capture and verifies its file hash through the unsigned matrix, the exact owner-manifest hash, source packet and selection hashes, and the manifest's original inventory/catalog binding. The actual post-owner capture compares owner ID, album IDs, scope rows/hash, original SGF references and full physical album hash to that frozen capture and manifest. Differences become rejection reasons and prevent readiness. Expected owner-review/catalog changes are not confused with album drift.

2. **Source packet drift after collision capture — closed.** `source_records` returns the hash of the same packet object used to create the captured proposals. Each capture stores that hash. Before binding, `verify_source_binding` checks both captures against the current frozen selection and packet hashes, exact 150-record membership, and the complete raw/profile/source/hint/parts/core/names projection. Binding and matrix assembly use the same loaded packet. Post-owner capture also checks the packet identity across the frozen capture, manifest and matrix.

Fresh independent verification after the repairs:

- `PYTHONPATH=. python docs/resource/kifu-event-chinese-next150-20261009/check_postowner_scope.py` — passed: pristine scope accepted; ID, rank/scope, SGF and physical image drift rejected.
- `PYTHONPATH=. python docs/resource/kifu-event-chinese-next150-20261009/check_source_binding.py` — passed: matching source accepted; stale packet and altered captured proposal rejected.

The final call sites were also inspected: these checks execute in the real capture/binding path before its readiness/output decisions. The native compatibility patch was not changed or redundantly retested in this repair recheck.

## Other inspected boundaries

The capture opens a single `REPEATABLE READ, READ ONLY` transaction. It resolves owners by unique exact raw text and treats archived IDs as hints; checks owner state, parser parts, empty name/evidence preimages, first GN, EV, formal-event/edition NULL state, duplicates, hidden rows and existing selections; and stores a full physical `SELECT *` album hash with the SGF represented by its full-content hash. Empty current album scopes have rejection reasons. Saved counts are clearly labelled prioritization hints, and the unsigned binder excludes captured row failures, cross-environment count disagreements and normalized external name collisions.

An independent SGF helper smoke check covered escaped brackets, first-GN ordering, a present EV, full-content SHA-256, and unchanged input data. These passed.

The current runner correction is appropriate: it checks the supplied administrative image ID and exact patched module hash separately from the pinned existing web images, takes DB/network context from the web container, uses no network for the hash read, mounts the preparation read-only, and does not require a web restart. Credentials are supplied through stdin and error URLs are redacted.

The 593/594 owner/name execution helpers are outside this approval. Their profile, counts, hashes, image pins, source references and provenance still need rebinding to the actual accepted captures before any separate SQL review. No current live eligibility, approval signature, applied count or deployed state is asserted here.
