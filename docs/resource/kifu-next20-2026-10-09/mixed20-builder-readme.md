# Next mixed 20 unsigned assembly

`mixed20-source-review.json` is the compact source review sheet: nine exact Japanese-source TW displays, seven Chinese-source TW orthographic displays, one exact KBA Hanja TW display, and three Japanese-to-Korean generated displays. It pins the actual source creation hashes, current target status and hashes, and the retained file bytes. The full source rows and HTML remain in the referenced captures.

Root first reviews and signs the 17 TW anchors per environment and the three finite orthographic rules. The seven Chinese TW targets and the KBA TW target are existing REVIEW rows. The separate reviewed implementation must accept the exact complete REVIEW target image through `preimage_binding.target_name_preimage`; approved/evidence-bearing targets remain ineligible. The three Korean research records need root source and NIKL review, environment-specific owner binding, and independent candidate approval.

The actual TW source/rule review is recorded in `root-source-rule-review.json`; approved anchors are `ENV-tw-anchors.approved.json.gz`, and approved rules are `tw-rules.approved.json`. After root confirms both native importer images load the reviewed module and batch-590 pages are synchronized, run `capture-mixed20-fresh-readonly.py` with `--root-confirms-deployed-and-pages-synced`, `--prod-image`, and `--test-image` set to the two pinned image IDs. It writes separate `ENV-mixed20-fresh-post590-pages.json.gz` files and preserves the signed source captures. Then run `prepare-mixed20-bound-requests.py TEST` and `PROD`; its output is pending root review, with no approval fields invented.

After batch 590 and page synchronization, supply one `TEST` or `PROD` JSON/JSON.gz input to `assemble-mixed20-unsigned.py` with:

- `status: "root_approved_fresh_post590_pages"`, `environment`, `context_refreshed_at`, `preceding_batch_applied >= 590`, and `pages_synchronized: true`;
- fresh `inventory`, `catalog_sha256`, `approved_name_snapshot`, `registry`, all 20 complete `fresh_targets` keyed by environment owner ID, and all 20 format-2 `owners` declarations;
- the 17 approved `tw_anchors`, three approved `orthographic_rules`, and three approved `orthographic_batches` for JP9, CN7, and KBA1;
- all 20 approved, freshly bound `candidates`, three approved environment-specific `ko_research` records, and `ko_prod_to_owner` mapping for PROD IDs `5396`, `4276`, and `4782`.

The builder compares approvals to the retained unsigned source/rule bytes, checks exact names and fresh target preimages, then runs native `validate_bundle`. It writes `ENV-mixed20-unsigned-bundle.json.gz`, `ENV-mixed20-unsigned-evidence.json.gz`, and a summary only when all 20 are ready and write ready. The output remains unsigned for outer execution. It does not capture, sign, change SQL, or overwrite an existing bundle.

Run from the repository root: `python docs/resource/kifu-next20-2026-10-09/assemble-mixed20-unsigned.py TEST path/to/TEST-approved-input.json.gz` (and then `PROD` after TEST verification).
