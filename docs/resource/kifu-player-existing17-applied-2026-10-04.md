# Existing-owner 17-name exact player links: applied on 2026-10-04

The [independent identity and slot decision](kifu-player-existing17-independent-decision-astra-2026-10-04.json) approved 3,576 exact NULL player FK slots for 14 of the 17 reviewed raw names. It held 807 slots: 661 across three unresolved identities and 146 per-game context exceptions. No new player ID, alias, translation, or raw-staging status was created by this batch.

The executor [player_existing17.py](../../katrain/web/kifu/player_existing17.py) pinned both TEST/PROD frozen captures and both six-league applied plans, allowing only the 137 reviewed `event_id` postimages in its 4,318-album scope. Final independently reviewed module SHA-256: `890a68f883f914ad5dee7a0f9278086720a099c6654059be84dcb4e062555346`; focused tests: 7 passed. Both environments captured 4,383 currently NULL slots, then passed real transaction dry updates, rollback recaptures, ordered TEST→PROD commits and independent post-commit full-scope verification.

| Environment | Applied plan SHA-256 | New exact player FKs | Held | Total linked player slots / 346,050 | Fully linked games / 173,025 |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `5beb594584af5a0d59065c25181e5b662ad43937e521e5f7292c54b947ec7bab` | 3,576 | 807 | 303,530 | 78,660 |
| PROD | `2fae3a90b9a68d14475fb7c83ea935726b775d9e1e6cbd10fdb38445bf88b07f` | 3,576 | 807 | 305,135 | 79,815 |

Durable exact applied plans: [TEST](kifu-player-existing17-TEST-applied-plan-2026-10-04.json.gz) and [PROD](kifu-player-existing17-PROD-applied-plan-2026-10-04.json.gz). PROD event links remained 99,371/173,025. All 807 held player FKs remained NULL; raw names, SGFs, source associations, event IDs and catalog rows were not written in this batch. Full preprocessing and five-language translation remain outstanding.
