# Three-player exact FK batch: applied on 2026-10-04

The independent frozen player reviews and the two independent rebase decisions approved only 1,529 exact NULL player slots per environment for 周鹤洋、赵善津、工藤纪夫. The 580 held player slots remained NULL. The executor accepted 83 previously committed background changes in its 2,105-game scope: 56 event IDs and 27 opponent player IDs, all from SHA-pinned prior batches; it did not write those fields.

The final reviewed executor module SHA-256 was `8263e6665edc69d13951645f1c7d3e1ea77d6359d75591a9b593692f0bb94fd1`. Focused tests: 19 passed. The TEST Python 3.10 source timestamp formatting difference was checked for equal instants; 198 TEST and 139 PROD source-association rows differed only in zero padding, with no semantic difference. Both live read-only captures and real transaction dry runs passed; the dry runs rolled back and recaptured the same plan.

| Environment | Frozen plan SHA-256 | Committed exact player FKs | Held | Independent post-commit verification | Total linked player slots |
| --- | --- | ---: | ---: | --- | ---: |
| TEST | `e44001325ed009340b1d575d19ba28310025d7a5eb7b1829a19349b5672d53ab` | 1,529 | 580 | Passed | 299,954 / 346,050 |
| PROD | `eec2244f7f5ec10fb2a123f344f638bb7961bf2a72a1f779ca0d267f94349cef` | 1,529 | 580 | Passed | 301,559 / 346,050 |

Read-only post-commit complete-game counts (both players and event linked): TEST 70,482 / 173,025; PROD 71,514 / 173,025. Raw names, SGFs, sources, event IDs, catalogs, existing associations and held slots were unchanged by this batch. The five-language translation phase has not begun because full preprocessing remains incomplete.
