# Lee Chang-ho 2010–2011 Korean Baduk League source research

Reviewer: `gpt-6-luna`. Reviewed 2026-10-02. Source research only; no database, SGF, code, or identity decision was made.

## Scope and result

Reviewed the 11 exact-slot candidates dated in the 2010 season and 13 dated in the 2011 season from the private exact-slot CSV. The specialist season match tables list 15 candidate tuples with matching date, opponent, and player color; mark those **approved for next identity review only**. Hold the other 9: 8 have a color conflict and 1 has a date conflict.

- 2010: 6 approved for next review; 5 holds. The listed results for the 6 matching entries are four wins and two losses for Lee.
- 2011: 9 approved for next review; 4 holds. The listed results for the 9 matching entries are seven wins and two losses for Lee.
- Combined: 15 approved for next review; 9 holds. No candidate is identity-approved by this memo.

Approved-for-next-review album IDs: 2010 `74958`, `84074`, `83412`, `50340`, `98013`, `98023`; 2011 `98039`, `28261`, `89846`, `98043`, `98050`, `27182`, `98054`, `87568`, `44125`.

Holds: `29478`, `98011`, `71164`, and `83424` conflict on player color; `98019` is dated 2010-09-10, while the season record lists Lee Chang-ho versus Mok Jin-seok on 2010-09-23; `30627`, `84098`, `98051`, and `84105` conflict on player color. For `98019`, the season table does not list the candidate date/pairing; its listed 2010-09-23 pairing has Lee as White.

The specialist tables provide game date, Black, White, result, and team matchup/event. They group games into first- and second-stage schedules but do not give numbered rounds for these games. Stage is recorded per slot in the restricted output. Result notation is preserved there and Lee's win/loss is derived from the listed color.

## Sources and capture hashes

- [2010 Korean Baduk League schedule, Go to Everyone!](https://gotoeveryone.k2ss.info/news/kr/kl/8/) — 11 captured passages; SHA-256 `748286fd1b72ce2fccb22d4a814dd4cda6912f93fe654cc9b34a635e344b0990`.
- [2011 Korean Baduk League schedule, Go to Everyone!](https://gotoeveryone.k2ss.info/news/kr/kl/9/) — 13 captured passages; SHA-256 `0c8a846668010453192f9376400ea65fbdd5c6e6cf6c2cc9d0f4f7f5b5137226`.

Each digest is SHA-256 over the UTF-8 captured record lines in the restricted output, joined with LF in candidate date/album-ID order. The pages were captured through web.open; direct HTTP retrieval returned 403, so a full response-body hash was unavailable. Each per-slot passage hash, result notation, and comparison is in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-link-prep/lee-143-korean-league-2010-2011-research.json` (mode 0600).
