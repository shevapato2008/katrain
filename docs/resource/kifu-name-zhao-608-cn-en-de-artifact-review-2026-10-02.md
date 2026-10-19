# Independent artifact review: Zhao/Cho Chikun CN, EN, DE

**Result: source/research artifacts PASS; identity attachment remains PENDING.** This is an artifact review only. It does not approve any candidate or any of the 2,052 raw-name slots.

## Integrity and validation

The controlled research JSONL and candidate JSONL are mode `0600`; their SHA-256 values match the producer memo: `caa3c8a6b4226c9f82a29e233584736c37e6c5bad7acfdc9a143b8c2eaf59e02` and `78ba9aeb18bdb37926112e0df9ca92359854acad76e59b4e405aa07c23521ff6`. Registry `2026-10-02.3` at `kifu-name-source-registry-2026-10-02.3.json` hashes canonically to `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. All three records pass `validate_research_record`; all three candidates are `pending`, have no reviewer or write binding, and each `research_sha256` matches its canonical research record: `cn` `7d746313d092e04400632a2ca8cbc69f713773d13e3b213a7d3d4a8a47605ae6`, `en` `e0e42fbc017a7f87c3d35efeb7b549c05615acfefec3fea73c7adf229f6130ef`, `de` `276add3d63984619b67c1d04b5f60b4d4335a005cf5465c0792356c303640956`.

`validate_candidate` rejects each row with the same error: `entity ID/ref absent from pinned inventory and approved links`. The pinned inventory is the production snapshot `kifu-name-inventory-prod-v2-20261002.json.gz`, file SHA-256 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`, internal SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`, database `katrain_prod_20260725`. Its candidate gate derives player IDs from album associations: this failure establishes that ID 608 is not present in the snapshot's associated IDs, not that the production player row is absent or belongs to someone else. The parent task separately confirms production ID 608 is Zhao; the test database's ID mapping is a different environment. No test-database identity was used here.

## Source checks

- `cn`: official China Sport Administration report, HTTP 200, observed `zh-Hans`, fetched `2026-10-01T21:38:52.096416Z`, body SHA-256 `b23cbf39ccb47465d5a27fa05d041546997cfc41963f51c5d1d67e520432b682`. The captured Chinese passage names `赵治勋` among first-round entrants, without a rank suffix.
- `en`: CWI Go collection, HTTP 200, observed `en`, fetched `2026-10-01T21:38:52.358546Z`, body SHA-256 `8ef933b0daf719a8382dddeadb1d56d9a51e52d7ee0deb02a4729e3f97a8ccd0`. The body identifies `Cho Chikun` and cross-lists `Cho Chi Hun, 趙治勲, 조치훈`; its rank progression is separate from the name.
- `de`: fixed German Wikipedia revision `250879659`, HTTP 200, `html lang=de`, fetched `2026-10-01T22:00:23.510277Z`, body SHA-256 `8f0944fb9032bc3ccfb4965722c5a8fe9799c133c511fa01525b9444ea6ddb86`. The German text uses `Cho Chikun` and says he is a Japanese Go player; the candidate contains only the name, without rank.

The raw response bodies and capture manifests are in the controlled mode-`0600` directory named by the producer memo. Identity anchors also match their captured bodies: Korea Baduk Association gives `조치훈 (趙治勳)`, born 1956-06-20, affiliated with Japan (SHA-256 `0a17c1a56ece67066b4e79b5a54639b515dea63f4649947d5697e6bb3ac7039a`); Nihon Ki-in gives `趙　治勲`, reading `チョウ　チクン / CHO, Chi Hun`, 9-dan and Busan origin (SHA-256 `665d169cbf6c893654c238083e7e2a8003d5911bae727561594a291c4c04ac3c`). The CWI page's Seoul birthplace statement conflicts with Nihon Ki-in's Busan statement; the records disclose this, and identity relies on the official association/profile anchors rather than silently merging birthplace claims.

No controlled artifact or database row was changed in this review. The artifacts support the three proposed language names, but the inventory association gate and separate raw-slot identity review remain unresolved.
