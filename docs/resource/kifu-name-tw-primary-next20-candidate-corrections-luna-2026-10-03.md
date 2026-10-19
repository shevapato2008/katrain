# TW next20 source candidate replacement corrections

This is a separate replacement candidate packet for the earlier TW next20 work. The original candidate packet and its hashes remain unchanged. The replacement binds every row to its original row hash and to the corresponding independent review row hash.

## Corrections made

- All 15 rows with retained source pages now carry the literal rendered passage provided by the independent review; the five names without a qualifying source retain a null excerpt. Each excerpt was checked as a substring of the normalized rendered text from its retained raw body.
- **宋容慧:** removed the unsupported Haifong team attribution. The dated report says 海峰棋院女子隊 lost 0:3 to 深圳豪傑自行車隊 and separately lists 宋容慧五段 defeating 盧鈺樺五段; it does not establish Song’s team.
- **安冬旭:** corrected the 2023 result to 王元均九段持黑中盤負安冬旭六段. The original summary incorrectly said Wang had white and lost by 1¾ stones.
- **李鑫怡:** the 2016 Haifong passage’s `5段` is retained as written but is not characterized as professional fifth dan. A separately retained 2017 result article defines its `新` mark as new 初段 and lists 李鑫怡（新）.

The replacement carries forward the independent decisions without changing them: **11 PASS-CANDIDATE / 2,965 slots; 9 HOLD / 1,820 slots; 20 rows / 4,785 slots.** These remain source-name candidate decisions only.

## Packet and bindings

Protected replacement packet: `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/tw-primary-next20-replacement-luna/`.

- `candidates.replacement.jsonl` SHA-256: `a1401e8edd81864dc2b4e864f2b362248e6cc0e3bd85934edf82401c89f4b73c`
- `manifest.replacement.json` SHA-256: `23164396cd8167a1b9cad0a504e2b88000df76596272a7123ac3bd42feccd549`
- Replaced original candidate JSONL SHA-256: `45da4d6a43a1bc891e4b6901e83624a3f04563c19049d46c047b04681c503242`
- Independent reviewed rows SHA-256: `28d9f877e0a7000c0250e3be26a4ed202fa5868ccf6124bc28eb87ad3d1e2ab0`
- Independent review memo: [kifu-name-tw-primary-next20-independent-review-sol-2026-10-03.md](kifu-name-tw-primary-next20-independent-review-sol-2026-10-03.md)

Original Haifong raw bodies are copied unchanged into the new protected packet, with their prior URLs, timestamps, and hashes in its manifest. The added Sina Sports raw body `li-xinyi-2017-pro-name-context-sina.html` is 107,608 bytes, SHA-256 `e6c5d56b4213c233ebcafb4828be24b65b2793d8e4528d55bd2c40a498574d62`, captured `2026-10-02T21:18:31.594983Z`; its literal excerpt is `预赛对阵（2017年新初段标记为——新）： 李鑫怡（新） 胜 叶桂`.

The packet retains the registered Haifong source registry version `2026-10-02.5` (SHA-256 `2ebd1c462887632717f0b281ed983db41de7065d9e5f7c4332a4fef8a5624511`). No display write, entity/QID/FK/SGF/album approval, database write, code change, or commit is authorized or included.
