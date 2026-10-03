# Five Chinese-Origin Raw Player Names: Six Secondary Batches Pending

Producer packet only; no database writes and no independent approval claimed. The immutable protected bundle is at `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-v3-batch-producer-luna/` (manifest `manifest.pending.json`).

## Finite scope

The packet binds exactly 4,358 `(album_id, side, raw)` tuples: 唐韦星 (858), 杨鼎新 (864), 檀啸 (911), 胡耀宇 (868), 连笑 (857). All other raw values remain HOLD. It creates no alias and asserts no person foreign key. The five v3 source/reading anchors and RU/UA rules are copied from the independently signed packet; four Latin-language rules are reused from the previously signed raw-player packet. Six secondary batches contain 30 mechanical candidates.

## Fresh preimages

A fresh repeatable-read snapshot from the dedicated isolated clone verified `transaction_read_only=on`, inventory `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`, base `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`, and catalog `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`. The approved-name snapshot contains zero rows; all five target owner rows and target name preimages are absent. The dedicated container was stopped after capture. Snapshot and raw preimage files are frozen in the protected packet.

## Validation state

Repository validation is recorded in `producer-validation.actual.json`. It is not ready for approval yet. The current errors are expected producer/reviewer boundaries: five owner declarations need independent category review; pending batch records do not yet carry independent approval signatures; thus transliteration bindings/candidates cannot validate as approved. No signature was fabricated. The complete six batches and 30 pending candidate records are present for reviewer inspection. The validator also reports downstream membership errors because owner declarations are pending; resolving category review should allow revalidation.

Exact candidate output is mechanically recomputed from each signed anchor reading and signed language rule; no new transliteration token map was added. Candidate names and their source/rule/batch hashes are in `candidates.pending.json` and `transliteration-batches.pending.json`.
