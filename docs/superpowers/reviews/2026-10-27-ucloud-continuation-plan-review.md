# UCloud continuation safety review

Reviewer: independent `gpt-6-astra`, reasoning `max`, no inherited conversation.

Decision: **Approved for the bounded continuation plan; actual proof and runtime checks remain required.**

The original final restore completed all 13 databases with exit 0. Its strict schema-dump comparison correctly retained a failed receipt when four schema hashes differed. Exact diagnosis identified 67 CHECK expressions and one partial unique-index predicate that PostgreSQL reparsed during logical restoration: varchar-array casts and associative AND grouping. Other DDL, literal bytes/order and previously compared data/ownership evidence matched. The failed receipt, original manifest and original fence must remain unchanged.

Required continuation checks:

- Fix the exact 68 database/schema/table/object identities and both original DDL hashes. Compare all remaining DDL strictly.
- Use read-only EXPLAIN without ANALYZE, in the same target type/typmod/collation/search-path context. Expression Output must actually exist. Check constraint and index metadata, including validity, uniqueness, keys, opclass, collation and NULL behavior.
- Acquire a new independent lock for at most 1800 seconds on the same file device/inode. Remove only the identified, naturally exited old pure-lock container after retaining its evidence. Do not change paused rows or start a scheduler.
- Bind the new receipt to the original window, manifest, transfer, failed-apply and fence hashes, the exact 13 successful restores, and the new window/ready/fence and current physical-writer evidence.
- Recheck source fingerprints against the original manifest; target differences are limited to the four documented raw schema hashes and fully proven expressions. Recheck password equivalence without retaining password material.
- Check fresh lock and physical fencing before continuation, receipt issuance and configuration copy. Expiry stops further actions. Authorization covers only verification of the existing import, normal target-PG shutdown and exact original configuration copying. Writers remain closed until restart validation.

This review does not claim that continuation, cutover, DNS or migration acceptance has completed.
