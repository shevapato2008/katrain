# Traditional Chinese high-frequency 10 — Haifong context augmentation

This packet supplements the earlier HK2 discovery without altering it: `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/tw-high-frequency10-pending-luna/`. The earlier HK2 page was an undated entrant list and did not identify players by rank or roster ID. This augmentation captures dated Traditional Chinese Haifong pages with team, tournament, visit, opponent, or rank context where found.

Status remains **pending independent review**. Five records are **PASS-CANDIDATE** for that review; five are **HOLD**. This is not a localized display approval or entity/album identity decision.

## Contextual candidates

| Name | Traditional source text | Haifong context | CWA / GoRatings | Slots |
|---|---|---|---|---:|
| 黄奕中 | 黃奕中七段 | 2019-02-01 Haifong visit; page calls him a national youth team coach and records him teaching students. | CWA000050 / GR 190; CWA grade Z07; DOB 1981-08-24 | 429 |
| 叶桂 | 葉　桂（五段） | 2017 men's Division C / women's Division B league report; Hubei team roster and opponent in a professional result. Fullwidth spacing is retained as source typography. | CWA000245 / GR 307; CWA grade Z05; DOB 1974-08-05 | 199 |
| 黄晨 | 黃 晨 五段 | 2016 Chinese league report; listed on Hangzhou Heibai Fang team roster. Source contains a non-breaking layout space between the characters. | CWA000079 / GR 419; CWA grade Z05; DOB 1988-08-17 | 195 |
| 黎春华 | 黎春華（四段） | 2017 league report; Hubei team roster alongside 叶桂. | CWA000176 / GR 2; CWA grade Z04; DOB 1973-04-18 | 137 |
| 丁烈 | 丁 烈 六段 | 2015 men's Division C league, named opponent and first-board result for China Coal Go Academy; team roster also gives six dan. Source spacing is retained. | CWA000120 / GR 413; CWA grade Z06; DOB 1986-08-29 | 114 |

For each candidate, the approved original-name anchor ties the official CWA Chinese name and full DOB to the same-name GoRatings Chinese profile and stable profile ID. The Haifong rank also agrees with the official CWA grade in the retained anchor row. These are independent correspondence facts supporting a candidate review; the source anchor itself does not approve the `tw` display. See the per-record identity fields, locators, and hashes in the packet.

## Holds

方捷 (218 slots), 汪洋 (210), 陶忻 (161), 朱松力 (116), and 王元 (132) remain **HOLD**. The only Traditional professional page located for these names in the earlier pass was HK2’s undated 128-player event list; it carries no per-player rank, team, or person ID. Targeted Haifong searches did not surface a suitable contextual page for these four list hits. 王元 was absent from HK2’s field as well. None advances from a same-string hit alone.

## Captures and scope

The five raw Haifong HTML bodies, fetched `2026-10-02T20:47:25Z`, are retained in `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/tw-high-frequency10-haifong-augmentation-luna/`. All returned HTTP 200, declare `lang="zh-tw"` and UTF-8, and are listed with byte lengths, exact excerpts, URLs, and SHA-256 in `manifest.pending.json` and `candidates.pending.jsonl`.

- [Huang Yizhong 2019 visit](https://www.haifong.org/news/content/A4DCDDA762BDB5CFF06142B2C02C75AF) — `6a10fedff453b3a7f06f7ff57f20308a382d774704597cbdb87bb5f2fc3dee94`
- [Ye Gui and Li Chunhua 2017 league](https://haifong.org/news/content/948201B616FE67AF49D822019A2C02C5) — `9ccf67cdac0fd98249349a007644650a26b1c5e9c4bfc5f88c9ccdb7ba17e938`
- [Huang Chen 2016 league](https://www.haifong.org/news/content/88EB8085ED12AB42FAB0BF73242617C5) — `9f43e502adb57613f1140d6c7b8e66fe34f01beaf11f3def6977a51b4ba69ed0`
- [Ding Lie 2015 league result](https://www.haifong.org/news/content/3E8165ECA3D3EB80DA36C4E8B0AAB986) — `30aae92a45287e9d625b0f71e64c6d38897d852aacbd2cee038475527fefdd0f`

Haifong is source `haifong` (official, `zh-Hant`) in fixed registry `2026-10-02.5`. The frozen exact scope file SHA-256 is `d6d10384211cfe6e21eb66271c5dd2abd83503367bef81e6a3f0de838c1728e2`; these ten rows cover 1,911 slots: 1,074 PASS-CANDIDATE and 837 HOLD. Upstream anchor file SHA-256: `fe2371a7ce47894bee17cf150a7eeae92f83191d1cd0ee701b75bd1a90fc8e71`.

No code, database, SGF, or album data changed, and no commit was made.
