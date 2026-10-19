# Lee Chang-ho 58-slot Korean Baduk League source reconciliation

Reviewed 2026-10-02 by `gpt-6-luna`. This producer pass reconciles the 58 controlled exact-name slots from 2010–2014 against the Go to Everyone! specialist league season schedules. It is not an identity approval or an import authorization.

## Result

| Season | Slots | Schedule match | Hold |
|---|---:|---:|---:|
| 2010 | 11 | 6 | 5 |
| 2011 | 13 | 9 | 4 |
| 2012 | 12 | 7 | 5 |
| 2013 | 9 | 5 | 4 |
| 2014 | 13 | 7 | 6 |
| **Total** | **58** | **34** | **24** |

`MATCH` requires agreement on candidate date, opponent, and Lee color in a season schedule row. The schedule result is recorded where available. `HOLD` means an explicit mismatch or no schedule game matching that date/opponent. No decision relies on the event label or name alone.

## Holds

- **2010:** `29478/white`, `71164/black`, `83424/black`, `98011/white` have Lee-color conflicts; `98019/black` has no listed Lee–Mok Jinseok game on the candidate date (the cited schedule lists that pairing on another date and with Lee white).
- **2011:** `30627/black`, `84098/black`, `84105/black`, `98051/black` have Lee-color conflicts.
- **2012:** `73810/black`, `74995/black`, `88405/black`, `98067/black`, `98078/black` have Lee-color conflicts.
- **2013:** `34531/white`, `98110/white`, `98113/black`, `98114/white` have Lee-color conflicts.
- **2014:** `89540/black`, `90647/white`, `93283/white`, `98137/black`, `98138/black` have Lee-color conflicts; `44172/white` conflicts on both date and Lee color.

These are source reconciliation holds. A separate source or SGF investigation is needed before resolving them.

## Evidence and limits

The protected full record is `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-link-prep/lee-143-korean-league-2010-2014-source-reconciliation-20261002.json` (mode `0600`, SHA-256 `0bb2b3f2059ca68f38ed15b2c89066425551b92cee2812036991bb1dcd9467e2`). It binds all 58 rows to the exact-slot CSV SHA-256 `5c36cdcedf3303310b05bf68b4ad3cc45c6e5368c76c1fbe373e3ab388844f11` and records album ID/side, candidate fields, direct schedule URL, transcribed row, row excerpt hash, date, color, and result where present. Coverage was checked one-to-one against all 58 CSV rows; counts by season are included in the artifact.

The sources are specialist season schedules, not primary Korean Baduk Association/Hanguk Kiwon records. The rendered pages did not provide retrievable response-body hashes; the artifact preserves the available target-row excerpt SHA-256 values and notes missing hashes. `MATCH` therefore means only that the listed game attributes agree with the cited schedule. It does not establish a final player identity or authorize a player-ID link.

Season source pages: [2010](https://gotoeveryone.k2ss.info/news/kr/kl/8/), [2011](https://gotoeveryone.k2ss.info/news/kr/kl/9/), [2012](https://gotoeveryone.k2ss.info/news/kr/kl/10/), [2013](https://gotoeveryone.k2ss.info/news/kr/kl/11/), [2014](https://gotoeveryone.k2ss.info/news/kr/kl/12/).
