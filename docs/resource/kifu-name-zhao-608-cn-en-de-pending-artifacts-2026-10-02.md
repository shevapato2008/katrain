# Zhao/Cho Chikun CN, EN, and DE pending name artifacts

Created research-only pending records for existing player ID `608`, using registry `2026-10-02.3` (canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`). The controlled directory `/Users/fan/.local/share/kifu-name-audit/2026-10-02/` is mode `0700`; the two JSONL files below are mode `0600`.

## Pending files

- `zhao-chikun-cn-en-de-pending-research.jsonl` — three records (`cn`, `en`, `de`); SHA-256 `caa3c8a6b4226c9f82a29e233584736c37e6c5bad7acfdc9a143b8c2eaf59e02`. Each passes `validate_research_record` against registry `.3`.
- `zhao-chikun-cn-en-de-pending-candidates.jsonl` — three candidate rows, all `review_status: pending`, with no reviewer, preimage, or write binding; SHA-256 `78ba9aeb18bdb37926112e0df9ca92359854acad76e59b4e405aa07c23521ff6`. Each `research_sha256` equals the canonical SHA-256 of its matching research record: `cn` `7d746313d092e04400632a2ca8cbc69f713773d13e3b213a7d3d4a8a47605ae6`, `en` `e0e42fbc017a7f87c3d35efeb7b549c05615acfefec3fea73c7adf229f6130ef`, `de` `276add3d63984619b67c1d04b5f60b4d4335a005cf5465c0792356c303640956`.

Proposed source-attested names are `赵治勋` (`cn`), `Cho Chikun` (`en`), and `Cho Chikun` (`de`). The source checks bind to the exact previously captured bodies: `china-sport` article (HTTP 200, `zh-Hans`, `2026-10-01T21:38:52.096416Z`, body SHA-256 `b23cbf39ccb47465d5a27fa05d041546997cfc41963f51c5d1d67e520432b682`); CWI Go collection (`cwi-go`, HTTP 200, English text, `2026-10-01T21:38:52.358546Z`, `8ef933b0daf719a8382dddeadb1d56d9a51e52d7ee0deb02a4729e3f97a8ccd0`); and fixed German Wikipedia revision `250879659` (`wikipedia-de`, HTTP 200, `html lang=de`, `2026-10-01T22:00:23.510277Z`, `8f0944fb9032bc3ccfb4965722c5a8fe9799c133c511fa01525b9444ea6ddb86`). Their full bodies and capture metadata are in the controlled capture manifests named `zhao-cho-cn-en-source-captures-20261002.json` and `zhao-608-de-fr-ru-source-captures-20261002.json`.

All three records retain the same official identity anchors: Korea Baduk Association's Korean-original profile `조치훈 (趙治勳)`, with birth date `1956-06-20` and Japan affiliation (captured `2026-10-01T21:38:59.752516Z`, SHA-256 `0a17c1a56ece67066b4e79b5a54639b515dea63f4649947d5697e6bb3ac7039a`); and Nihon Ki-in's `趙　治勲`, official reading `チョウ　チクン / CHO, Chi Hun`, 9-dan, Busan origin, and Japan Ki-in affiliation (captured `2026-10-01T21:38:58.836580Z`, SHA-256 `665d169cbf6c893654c238083e7e2a8003d5911bae727561594a291c4c04ac3c`). The research records cite these bodies for the original-language and reading evidence.

## Limits

Candidate validation against the pinned production inventory was run for each pending row and rejected all three with `entity ID/ref absent from pinned inventory and approved links`. ID `608` is absent from that snapshot. These artifacts carry no album links and establish no identity decision for the 2,052 matching raw slots. CWI's page says Seoul as birthplace, while the official Nihon Ki-in profile says Busan; the pending record notes that source discrepancy and relies on the official identity anchors. No candidate is approved and no database write was made.
