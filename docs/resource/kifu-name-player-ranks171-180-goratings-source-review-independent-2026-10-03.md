# Independent source-only review: ranks 171–180 GoRatings v2

Date: 2026-10-03. Reviewer: Codex, based on GPT-6 (the exact serving-model variant is not exposed in this agent context). This review does not adopt the producer’s `gpt-6-luna` identity.

Decision: **28 PASS as GoRatings source evidence; 12 HOLD retained**. PASS is limited to the captured site rendering and same-ID profile linkage; it is not final localization, Wikipedia-name approval, import authorization, or production readiness.

I independently recomputed SHA-256 and byte lengths for all four listing bodies and ten profile bodies, parsed each actual HTML `lang`, found the exact candidate anchor under the same numeric player ID, and checked profile title, h1, language-switch ID, and Date of Birth against the recorded profile metadata. All checks matched. The 12 HOLD rows have zero matching ID anchors in their selected current pages, and null candidate names. This establishes absence only in these captured current listings.

Candidate file SHA-256: `4388585033346952946a496152e47953c7fd20234e62a9fa1ce50f585735b275`. Preserved index SHA-256: `d687c9c64b382851aa53fa6d4b569e0c863af5cbffce1a3de0557712b397b18c` (1,072,567 bytes); its bytes also equal the original local index. Index hash is computed by this review because the v2 manifest does not itself declare an index hash.

Identity support is bounded: titles and DOB values below corroborate the packet’s named GoRatings IDs. The numeric ID joins the four language listings to one English profile. DOB is evidence from that same source family, not independent biographical corroboration. Generic `zh` remains `zh`; no `cn` or `tw` split is inferred. No Wikipedia page or Wikipedia naming claim is made.

| Rank | Raw | ID | Profile title | Captured DOB |
|---:|---|---:|---|---|
| 171 | 上野爱咲美 | 1754 | Ueno Asami | 2001-10-26 |
| 172 | 陆敏全 | 1592 | Lu Minquan | 1999-04-26 |
| 173 | 王昊洋 | 379 | Wang Haoyang | 1989-12-24 |
| 174 | 唐奕 | 434 | Tang Yi | 1988-01-22 |
| 175 | 蔡丞韦 | 1693 | Cai Chengwei | 1998-03-21 |
| 176 | 志田达哉 | 1069 | Shida Tatsuya | 1990-12-06 |
| 177 | 本木克弥 | 1269 | Motoki Katsuya | 1995-08-02 |
| 178 | 范胤 | 1275 | Fan Yin | 1997-12-10 |
| 179 | 藤泽朋斋 | 854 | Fujisawa Hosai | 1919-03-09 |
| 180 | 林至涵 | 268 | Lin Zhihan | 1980-11-14 |

| Rank | Actual language | Exact candidate | Review |
|---:|---|---|---|
| 171 | zh | 上野愛咲美 | PASS |
| 171 | ja | 上野愛咲美 | PASS |
| 171 | ko | 우에노 아사미 | PASS |
| 171 | en | Ueno Asami | PASS |
| 172 | zh | 陆敏全 | PASS |
| 172 | ja | 陆敏全 | PASS |
| 172 | ko | 루민취안 | PASS |
| 172 | en | Lu Minquan | PASS |
| 173 | zh | 王昊洋 | PASS |
| 173 | ja | 王昊洋 | PASS |
| 173 | ko | 왕하오양 | PASS |
| 173 | en | Wang Haoyang | PASS |
| 174 | zh | 唐奕 | PASS |
| 174 | ja | 唐奕 | PASS |
| 174 | ko | 탕이 | PASS |
| 174 | en | Tang Yi | PASS |
| 175 | zh | — | HOLD |
| 175 | ja | — | HOLD |
| 175 | ko | — | HOLD |
| 175 | en | — | HOLD |
| 176 | zh | 志田達哉 | PASS |
| 176 | ja | 志田達哉 | PASS |
| 176 | ko | 시다 다쓰야 | PASS |
| 176 | en | Shida Tatsuya | PASS |
| 177 | zh | 本木克弥 | PASS |
| 177 | ja | 本木克弥 | PASS |
| 177 | ko | 모토키 가쓰야 | PASS |
| 177 | en | Motoki Katsuya | PASS |
| 178 | zh | 范胤 | PASS |
| 178 | ja | 范胤 | PASS |
| 178 | ko | 판인 | PASS |
| 178 | en | Fan Yin | PASS |
| 179 | zh | — | HOLD |
| 179 | ja | — | HOLD |
| 179 | ko | — | HOLD |
| 179 | en | — | HOLD |
| 180 | zh | — | HOLD |
| 180 | ja | — | HOLD |
| 180 | ko | — | HOLD |
| 180 | en | — | HOLD |

## Exact captured byte verification

| File | Bytes | SHA-256 |
|---|---:|---|
| sources/zh-current.html | 231853 | `c2abe95829a755aec356de732b622211f4b3a683d70254be78fab399bcb11393` |
| sources/en-current.html | 233262 | `98b3c2cafe03c7fb0af865edff629552b2cac8c0c4ffacf2ec18a51485e9cb9b` |
| sources/ja-current.html | 232106 | `8aecff238014ac38433dc9b7424e84b69dfcd8ebcaf3175c28b476f0e97506e6` |
| sources/ko-current.html | 234616 | `59ee45b164a9a814bd35397a064a908d0d65d97326e3c20ef04f462e91490bfe` |
| sources/profile-en-1754.html | 281406 | `d06a1933dfb036129a714d99bf7d0eb52d4f2e05e1f81c8c2e8514d2b546fa31` |
| sources/profile-en-1592.html | 201678 | `6ea38bd7ccb593b7dfe831f70d63572a9056bcfe8928cd89c501dc45e69d0440` |
| sources/profile-en-379.html | 243115 | `b31cb1d10d16bccbc7227185cbd25697d10112100bf2fa6e04c571a09c00559c` |
| sources/profile-en-434.html | 248932 | `5cd5fa3656510cc43371a5e78d51e03599053f666078a4b71e829c7de70c48d3` |
| sources/profile-en-1693.html | 43676 | `6628504c54ed6c6310a30f7d853390b3972066ebae431b2096cf7efbfcba823c` |
| sources/profile-en-1069.html | 209926 | `22543c7a2aa0f7170b85435dfe0d24b6fcee5e98ddeb5de79fbcb10c53240757` |
| sources/profile-en-1269.html | 205166 | `ce4011ebd80a74500c4100f2b8835e7b7020ae732a26589eb769fbf79f0c0a86` |
| sources/profile-en-1275.html | 231849 | `8648509b019e432924049be3a9fef10673f20438cf6ca0d6cbbeb4ecadaaf5b8` |
| sources/profile-en-854.html | 127250 | `09d57fb09a0b82658f28f36865a62cba4188821c022ec0197740e8421906eaa4` |
| sources/profile-en-268.html | 128880 | `b0071eaef8e7a36b9a2bca1758e4a1b49e34f9672e916e91c8e45eb9ddcfa627` |

The protected packet was read without mutation. This review created only this memo; no candidates were imported, no database or code was changed, and no commit or push was performed.
