# Traditional Chinese high-frequency 10 source discovery — 2026-10-03

Prepared a protected, unsigned source candidate packet for ten exact-name rows from frozen roster scope: `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/tw-high-frequency10-pending-luna/`. This is discovery evidence only; it does not approve localized displays, player identity, QID, SGF/album slots, foreign keys, or database changes.

## Findings

The captured [妙手棋院 (Miu Shou Go Academy) homepage](https://hk2.com/) identifies the Hong Kong publisher in its title and description and contains the titled **第九屆阿含桐山杯參賽棋手名單**, with the subsection **二、參加本選賽128人（預選優勝16人）**. It uses these exact Traditional forms in that professional tournament field: 黃奕中、方捷、汪洋、葉桂、黃晨、陶忻、黎春華、朱松力、丁烈. 王元 does not occur in that section or anywhere in the captured body.

Nine names are **PASS-CANDIDATE** for independent review as source-text leads, accounting for 1,779 frozen slots. **王元 is HOLD** (132 slots): no suitable Traditional professional Go context was found for that exact name in the captured regional source. These are pending candidates, not approvals. HK2’s page does not state the event year, does not print CWA or GoRatings IDs/ranks beside the entrant list, and has no HTML `lang`; its declared Big5 charset and reviewed body text support a Traditional Chinese reading, with Hong Kong provenance. HK2 also has no source ID in registry version `2026-10-02.5`; registry admission and independent review remain necessary before any approval.

The packet links each CWA roster row to its retained GoRatings Chinese profile through the already approved original-name anchor: exact Chinese name and full date of birth match, and the localized profile carries a stable GoRatings ID. Those anchor approvals cover original-name/reading correspondence only. They do not make the HK2 entrant-list occurrence a direct event-to-ID link. The packet records that limit per row rather than treating a bare string as identity proof.

| Original | Proposed Traditional form | CWA / GoRatings ID | Frozen slots | Candidate result |
|---|---|---:|---:|---|
| 黄奕中 | 黃奕中 | CWA000050 / 190 | 429 | PASS-CANDIDATE |
| 方捷 | 方捷 | CWA000109 / 171 | 218 | PASS-CANDIDATE |
| 汪洋 | 汪洋 | CWA000134 / 77 | 210 | PASS-CANDIDATE |
| 叶桂 | 葉桂 | CWA000245 / 307 | 199 | PASS-CANDIDATE |
| 黄晨 | 黃晨 | CWA000079 / 419 | 195 | PASS-CANDIDATE |
| 陶忻 | 陶忻 | CWA000054 / 411 | 161 | PASS-CANDIDATE |
| 黎春华 | 黎春華 | CWA000176 / 2 | 137 | PASS-CANDIDATE |
| 王元 | 王元 | CWA000153 / 226 | 132 | HOLD |
| 朱松力 | 朱松力 | CWA000093 / 130 | 116 | PASS-CANDIDATE |
| 丁烈 | 丁烈 | CWA000120 / 413 | 114 | PASS-CANDIDATE |

## Retained evidence and scope

- HK2 body URL: `https://hk2.com/`; fetched `2026-10-02T20:41:53Z`; 62,232 bytes; SHA-256 `6c4e8df8a1a06d165b64ac7140b072611f83c6b0a4570aef9ed1e0b44de43857`. Exact Big5/CP950 bytes and excerpts are retained in `hk2-homepage.html` and `candidates.pending.jsonl`.
- Frozen exact scope: `exact-candidate-scope.pending.json.gz`, 678 candidates; raw file SHA-256 `d6d10384211cfe6e21eb66271c5dd2abd83503367bef81e6a3f0de838c1728e2`. Ten targeted rows cover 1,911 slots. Per-row slot-set and context hashes are in the packet.
- Upstream source-name anchors: `secondary-six-remaining120-anchor-review-sol/anchors.approved.jsonl`, SHA-256 `fe2371a7ce47894bee17cf150a7eeae92f83191d1cd0ee701b75bd1a90fc8e71`.
- Fixed source registry inspected: `docs/resource/kifu-name-source-registry-2026-10-02.5.json`, version `2026-10-02.5`, raw SHA-256 `2ebd1c462887632717f0b281ed983db41de7065d9e5f7c4332a4fef8a5624511`; HK2 is not registered.
- Candidate JSONL SHA-256 `199bdeb8effc6d293388732786aa6bfac7b747396cf146e6317b12371e412438`.

No code, database, SGF, or album data was changed, and no commit was made.
