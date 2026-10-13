# Source registry `.8` candidate

Producer: Luna, `/root/source_registry_08_luna`. This is a proposed registry snapshot, not independent approval of a source capture, name, identity, or import.

Created [kifu-name-source-registry-2026-10-02.8.json](kifu-name-source-registry-2026-10-02.8.json) from the independently reviewed immutable `.7` snapshot. It appends only two entries recommended by the 41–60 follow-up review:

| Source ID | Publisher and tier | Language and registration note |
| --- | --- | --- |
| `ttplus-go` | Tiyu+ / Tiyu Zhoubao / Tiyu Media Group; `reference` | `zh-Hans`; professional Go reportage, not an association or official player register. The reviewed article credits reporter Xie Rui, identifies his Go reporting role, and states the platform’s publisher affiliation. |
| `hk2-go` | Hong Kong Miu Sau Go Institute; `language_go` | `zh-Hant-HK`; specialist Go player reference, not an official register. The reviewed page lacks an HTML language declaration, clear author, and update date, and contains dated or repeated material. Its body must be decoded from original bytes as CP950/Big5 and checked person by person against independent professional records. |

The exact retained pages were opened and their hosts/content confirmed: [Tiyu+ article](https://www.ttplus.cn/publish/app/data/2022/01/03/407019/os_news.html) at `www.ttplus.cn` and [HK2 personages](https://hk2.com/personages.htm) plus the [HK2 home page](https://hk2.com/). Tiyu+’s article is visibly Simplified Chinese, while its HTML declares generic `zh`; HK2 declares no HTML language, and its original bytes identify Big5/CP950. Do not infer language from host alone.

All 49 `.7` source objects, language tags, and eleven language scopes are unchanged. The new entries do not alter required search scopes or any negative-claim completion flag. Existing `cyberoro` is reused; no duplicate FoxWQ or Cyberoro entry was added. Registry loading succeeded with 51 unique IDs.

## Hashes

| Artifact | SHA-256 |
| --- | --- |
| Input `.7` raw JSON | `e6ece1699371d54d719e8333cec2fa571c5fc6bb913f71815f0139399b2b591f` |
| Candidate `.8` raw JSON | `2cfd665b215d1e8651ec9313953504d7c9ac0536d02548bfb8b8f80210593911` |
| Candidate `.8` canonical registry content | `b1a43187a9694e8098697d0eb57ab97bcf0bea1042d16613d0361c36e9c54082` |

This candidate has not been independently approved. No database write, code change, or commit was made.
