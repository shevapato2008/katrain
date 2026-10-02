# Lee Chang-ho 2012–2014 Korean Baduk League source research

Reviewer: `gpt-6-luna`. Reviewed 2026-10-02. Source research only; no database, SGF, code, or identity decision was made.

## Scope and result

Reviewed all 34 exact `李昌镐` slots for the 2012–2014 Korean Baduk League cohort from the private exact-slot CSV: 2012: 12, 2013: 9, 2014: 13. A candidate matches only when date, opponent, and player color agree with the season schedule.

- 2012: 7 matched for next identity review; 5 holds.
- 2013: 5 matched for next identity review; 4 holds.
- 2014: 7 matched for next identity review; 6 holds.
- Combined: 19 matched for next identity review; 15 holds. None is identity-approved by this memo.

Matched-for-next-review album IDs: 2012 `98065`, `98066`, `73619`, `70911`, `50488`, `27207`, `30702`; 2013 `34513`, `98098`, `98101`, `75033`, `83561`; 2014 `98122`, `29575`, `98128`, `87595`, `92389`, `93288`, `90505`.

Holds: 2012 color conflicts are `98067`, `74995`, `73810`, `88405`, `98078`. 2013 color conflicts are `98114`, `98110`, `34531`, `98113`. 2014 color conflicts are `93283`, `90647`, `98137`, `89540`, `98138`; `44172` conflicts on both date (candidate 2014-06-08, schedule 2014-06-06) and color. Every hold remains per-slot; there is no majority inference.

The schedule’s win notation was used to record the result from Lee’s listed color. The 2012 and 2013 tables list stages but no numbered rounds for these games. The 2014 specialist page uses first/second-stage schedule sections; corresponding stage and source passage are recorded in the restricted JSON. The page is an independent specialist source, not an official organizer record.

## Sources and capture hashes

- [2012 Korean Baduk League season schedule, Go to Everyone!](https://gotoeveryone.k2ss.info/news/kr/kl/10/) — 12 passages; SHA-256 `f7031ca27c48effc044ceb039700aa41e4bca8e7d4321515e40d2d78ca5aa57c`.
- [2013 Korean Baduk League season schedule, Go to Everyone!](https://gotoeveryone.k2ss.info/news/kr/kl/11/) — 9 passages; SHA-256 `c4fb00b0d3921bfa2228ed453e243233323af830d3f09dbf28fc84276a1f02e8`.
- [2014 Korean Baduk League season schedule, Go to Everyone!](https://gotoeveryone.k2ss.info/news/kr/kl/12/) — 13 passages; SHA-256 `c2cb07da4b29c7a0e8bf90b34d55237bcbb9f36763e2423f60f02e738858ced3`.

Each digest is SHA-256 over the UTF-8 normalized schedule passages in candidate date/album-ID order, joined with LF. The site was captured through `web.open`; a full response-body hash was unavailable. Per-slot passage hashes, page line references, candidate tuples, stage, result, and precise comparison reasons are in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-link-prep/lee-143-korean-league-2012-2014-research.json` (mode `0600`). The file is source evidence for separate identity review only; it does not approve identity or authorize a database write.
