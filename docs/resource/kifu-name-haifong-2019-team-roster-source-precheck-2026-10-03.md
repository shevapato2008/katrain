# Haifong 2019 roster: 45 new candidate source review (pending)

Date: 2026-10-03. Reviewer model: GPT-6 Luna. Read-only review of retained article capture; no formal name, identity, FK, or database approval.

Inputs: `matches.pending.json` SHA-256 `3f3af06e9dc082253475069d88ad723e538d50b7c526e68f6b40a72698263bbd`; `source.html` SHA-256 `895a19db2bdc101a73e3a3883d620063c61d9e10bdaeb7a1abcc01639e0e1d47`; `source-lines.json` SHA-256 `a645775264d3529d9642aa89003b701114926cd028b0b211262c166a0b9f6d6f`. The pending candidate input SHA-256 is `3f3af06e9dc082253475069d88ad723e538d50b7c526e68f6b40a72698263bbd`. The article is [海峰棋院 2019 圍乙報導及隊名單](https://haifong.org/news/content/C95D148BBA79CCD1F15DA6B77FE4BF9D).

## Findings

Reviewed all 45 rows marked new against every exact captured article line and its adjacent lines. **45 have high confidence as complete printed personal names; 0 boundary-ambiguous.** Each TW candidate exactly matches the article spelling, with no substring-only or team-name acceptance. The packet records line numbers, exact context, neighboring lines, occurrence hashes, candidate flags, and source roles for each row.

Names with at least one competitor/result or numbered-board occurrence (40): 万恩泽, 严古韵琪, 仇丹云, 令狐嘉骏, 冯盛敬悦, 吴震宇, 周昱杉, 唐吟啸, 娄洛宁, 孔祥明, 孙冠群, 孟昭玉, 张浩伟, 张馨月, 朱剑舜, 李建宇, 杨宗煜, 杨智文, 毛彦新, 潘亭宇, 王昊天, 王竣啸, 王迦南, 秦佳林, 范蔚菁, 董天怡, 蔡文鑫, 薛宏哲, 袁亭昱, 贾欣怡, 贾罡璐, 赵中暄, 赵邦桥, 郑子健, 陈旭东, 陈笑天, 韦一博, 韩卓然, 马媛媛, 黄春棋.

Names appearing only in explicit team staff fields (5): 吴新宇, 常昊, 王冠军, 陈临新, 陈德龙. These are clearly bounded personal names in `領隊`/`教練` fields; that supports the article spelling as a staff name only, not as a competitor listing.

## Limits and artifact

The article establishes the printed name and article role. It does not establish that a same-name person in this repository's SGFs is the article person, approve name translation/formal name, or authorize any FK. The deterministic article line extraction and retained source are treated as the evidence boundary; candidate match counts remain leads.

Machine-readable packet: `evidence.pending.json`, SHA-256 `3a0d55fe86cdb38caa91274348bd51e3eebbc0190d4f06acf26eeb3a55bd836e`. It contains all 45 candidate records, source line citations and hashes; file mode 0600, containing directory 0700.
