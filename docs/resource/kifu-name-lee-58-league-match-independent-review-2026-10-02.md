# Lee Chang-ho: independent review of 58 Korean Baduk League slots

Reviewed 2026-10-02 with the parent-specified model configuration **`gpt-6-sol`** (reasoning effort `high`); this subagent could not independently inspect its runtime model identifier. This is a read-only, exact `album_id/side` identity review of the 58 slots in the controlled `exact-slots.csv` (SHA-256 `5c36cdcedf3303310b05bf68b4ad3cc45c6e5368c76c1fbe373e3ab388844f11`). The producer reconciliation JSON is SHA-256 `0bb2b3f2059ca68f38ed15b2c89066425551b92cee2812036991bb1dcd9467e2`. No database, application, or source SGF was changed.

## Decision

**34 pass independent game identity review; 24 HOLD.** Of the passes, 33 agree with a full captured specialist schedule body on date, opponent, Lee's color, and result, and with the independently reread source SGF root. `98043/black` passes on the full original CyberOro game SGF, whose 192 move/color pairs exactly match the source SGF; the specialist schedule has the players and winner reversed in that row. This is approval of the finite game identity facts for a later link review, not a frozen import scope or authorization to write player IDs.

| Season | Pass exact slots | HOLD exact slots |
| --- | --- | --- |
| 2010 | `74958/black`, `84074/black`, `83412/black`, `50340/black`, `98013/black`, `98023/black` | `29478/white`, `98011/white`, `71164/black`, `98019/black`, `83424/black` |
| 2011 | `98039/black`, `28261/white`, `89846/white`, `98043/black`, `98050/black`, `27182/white`, `98054/white`, `87568/black`, `44125/black` | `30627/black`, `84098/black`, `98051/black`, `84105/black` |
| 2012 | `98065/white`, `98066/white`, `73619/white`, `70911/white`, `50488/white`, `27207/white`, `30702/white` | `98067/black`, `74995/black`, `73810/black`, `88405/black`, `98078/black` |
| 2013 | `34513/white`, `98098/white`, `98101/white`, `75033/white`, `83561/white` | `98114/white`, `98110/white`, `34531/white`, `98113/black` |
| 2014 | `98122/black`, `29575/black`, `98128/black`, `87595/black`, `92389/white`, `93288/white`, `90505/white` | `93283/white`, `44172/white`, `90647/white`, `98137/black`, `89540/black`, `98138/black` |

For 22 HOLDs, the schedule lists the same dated pairing but Lee's color opposes the exact slot. `98019/black` has candidate date 2010-09-10; the only Lee–Mok Jinseok schedule row found is 2010-09-23, with Lee white. `44172/white` has candidate date 2014-06-08; the only Lee–Jin Siyoung row is 2014-06-06, with Lee black. The source SGF roots agree with the controlled slots on player names and candidate dates, so the conflicts cannot be resolved by a schedule row alone. `98078/black` also differs on result: source SGF `B+1.5`, schedule `B+R`. Keep all 24 on HOLD until a full independent game record resolves each discrepancy. No inference was made from adjacent games or a majority of rows.

The producer labelled `98043/black` `MATCH` although its own cited schedule row gives Lee white. Directly rereading the [2011 specialist schedule](https://gotoeveryone.k2ss.info/news/kr/kl/9/) confirms the conflict. The [original CyberOro SGF](https://open.cyberoro.com/gibo/201107/110721-bl-lee.sd.sgf) gives `이창호` black, `이세돌` white, 2011-07-21, 192 moves, and a white resignation win. All 192 `(color, coordinate)` pairs equal the read-only source SGF at `data/kifu-album/19x19/41399505.sgf`, which names 李昌镐 black and 李世石 white and records `W+R`. A [contemporary CyberOro report](https://www.cyberoro.com/news/N_news_view.oro?cmt_n=&div_no=A1&num=515477&pageNo=) also names Lee Sedol as winner. The original game body SHA-256 is `6de744604394c38bf5dc893e170e29b3c11b3edad36a10aa4576c906d373ada7`; the report body is `81c119f3d4252f09afb58ad5fa44d0011edee3342bf6e4f2d1515ddd5163eb59`; the source SGF is `cce8e4dc616798cd02998b81d73257ee03336294f2e7ee1479e7cf92bed51629`. The [Korean Baduk Association profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001) identifies the nine-dan `이창호 (李昌鎬)`; its captured body SHA-256 is `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6`.

## Full source capture and limits

The five specialist HTML responses were retrieved directly with HTTP 200, retained as private mode-`0600` files, and parsed from complete table bodies. Thus the prior lack of response-body hashes is resolved for this review. Each source row also has a normalized line hash in the controlled reviewer artifact.

| Season source | Full HTML bytes | SHA-256 |
| --- | ---: | --- |
| [2010](https://gotoeveryone.k2ss.info/news/kr/kl/8/) | 106,558 | `df7c6756881f8ced7267f32d342b6521773408cb5a7527078edbdec832499268` |
| [2011](https://gotoeveryone.k2ss.info/news/kr/kl/9/) | 88,647 | `bad0660d0382050596b970ed9c415e8ce6afbe9e6d772a7b8ccc88ae7bf61ca7` |
| [2012](https://gotoeveryone.k2ss.info/news/kr/kl/10/) | 131,937 | `5e11756a5db948c2e9dfeb55ab4432e6d7f4cb878781f5e9e63b8bccd5ca66bf` |
| [2013](https://gotoeveryone.k2ss.info/news/kr/kl/11/) | 92,326 | `1a9b868358bbe0f6f922ea01b2873d73c260efc23665c91f4663b6b5c9bf089c` |
| [2014](https://gotoeveryone.k2ss.info/news/kr/kl/12/) | 84,142 | `dd5f9d8ed858f74d2ede28f9bf661760f4dd85ede0a65c584925656bfdfb1f11` |

All 58 source SGFs were fetched read-only from `home-ubuntu` in a single archive stream and checked for names, date, result, and raw SHA-256; their bodies were not saved locally. The prior 34 reviewed source SGF hashes were reproduced exactly. The controlled row-level review, all SGF hashes and roots, 58 row decisions, normalized schedule rows, page capture paths, and the CyberOro override are in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-link-prep/lee-58-independent-schedule-review-20261002.json` (mode `0600`, SHA-256 `0062e6c29ef0e12318de7e3c649f1b64ab9df5fee364035738519e477d1958b7`). The exact-slot CSV and SGF captures are different snapshots; any eventual production write still needs a newly frozen inventory, catalog, SGF hashes, old FK values, and final scope signature. The specialist schedules are independent secondary records, not organizer records. `89846/white` retains its source-SGF versus schedule opponent-rank difference (five versus six dan); its date, players, colors, and result match.
