# Next bulk player-name cohort after CWA roster

Read-only count from the frozen production inventory (`kifu-name-inventory-prod-v2-20261002.json.gz`, SHA-256 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`). It has 173,025 albums and 346,050 black/white name slots. The 678 exact CWA candidate raw values account for 41,461 slots and are excluded here. `Unknown`, `Black`, `White`, and `?` are also excluded because they need sentinel/record-type review, not person-name translation.

| Next distinct raw names | Candidate slots | Share of all black/white slots |
| ---: | ---: | ---: |
| 10 | 16,468 | 4.76% |
| 20 | 29,026 | 8.39% |
| 50 | 59,788 | 17.28% |
| 100 | 96,849 | 27.99% |

The top 20 are 李昌镐、赵治勋、曹薰铉、林海峰、小林光一、朴廷桓、李世石、依田纪基、山下敬吾、古力、大竹英雄、刘昌赫、武宫正树、井山裕太、张栩、藤泽秀行、徐奉洙、王立诚、崔哲瀚、加藤正夫. `Go Seigen` ranks 46th among the filtered names with 949 slots; it deserves explicit inclusion because the user asked for historical-player coverage. These are **raw-string frequencies, not approved person IDs, translations, or FK links**.

Next research batch should first collect official Go association, Nihon Ki-in, Korea Baduk and established Go archive names for these 20 plus `Go Seigen`, resolve simplified/traditional/Japanese glyph and Korean spelling per person, then run the lighter six-language Roman/transcription rules against approved readings. Keep source-name proof separate from the exact album-slot applicability and identity decisions. The already implemented finite raw-display path can later use the same signed scope format. Read-only counts do not assert that every same-string game belongs to one person.
