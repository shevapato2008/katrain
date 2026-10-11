# Source packet corrections and current-591 gate

The immutable `source20-v2.json` packet and both exact-20 current-591 captures remain paired by its SHA-256. These clarifications do not silently change that captured packet.

- 3844 Traditional Chinese Wikipedia markdown displays `亞歷山大·迪納斯塔因` in **two** Go event table rows. The v2 source packet described that variant as appearing once. It also displays the proposed `亞歷山大·迪那斯塔因` in three table rows and shorter `迪那斯塔因` in one. The choice between published spellings remains a reviewer decision. Source: `3844-zhtw-wiki.md` at its retained file hash in `source20-v2.json`.
- 3771, 6642, 6635 and 4568 have previously verified generated Korean display rows in both environments, but all four remain **strictly unqualified for Korean** in the current-591 read-only capture. Their older evidence uses `not_found_in_scope`, contains no `positive_generation`, and the persisted evidence has no `normative_ja_ko` batch proof. Keep these owners in this batch as positive-proof repair candidates, with full existing 13-field target preimages from `current591-four-positive-proof-gap.json`.
- 368 and 339 have different existing unqualified REVIEW Korean names. The retained actual canonical names and other four qualified languages match the newly researched people; replacement still needs the root's full-preimage compare-and-swap approval.

The v2 sources remain research, not write approval. Baduk TV's individual profile is an actual POST with preserved form fields and body hash; its same-code Cyberoro GET is the same underlying profile data.
