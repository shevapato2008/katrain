# 朴廷桓 ID 54：原文捕获补记

日期：2026-10-02。研究者 `/root/park_11lang_luna`，实际模型 `gpt-6`。更新首轮[来源研究](kifu-name-park-junghwan-11lang-research-2026-10-02.md)：下列记录有实际页面正文哈希，并通过 `name_evidence` 当前注册表校验。它们仍是 pending 候选，不是审批或数据库写入授权。

## 受控归档与捕获

全部原文位于 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-player-54/`：目录权限 `0700`，正文、清单、JSONL 文件权限 `0600`。每项 URL、采集时间、HTTP 状态、字节数、语种和 SHA-256 保存在 `capture-manifest.json`（SHA-256 `6eac5bf66455943661c7dd9e62287f4511c995c44796224b91ee5b0a06879fa2`）。七份源语正面正文、一份无姓名的西语维基正文，以及一份西语补充来源正文均存档。韩文身份资料从五源索引受控归档复用，未重抓；其 Firecrawl Markdown 正文 SHA-256 `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e`。

| 语码 | 捕获结果及来源 | 采集时间 UTC | 正文 SHA-256 |
|---|---|---|---|
| `cn` | 找到 `朴廷桓`；中国体育总局[应氏杯报道](https://www.sport.gov.cn/n20001280/n20745751/n20767274/c22049225/content.html)，正文称“韩国棋手朴廷桓”。页面无可用 HTML 语种标签，人工核对可见正文为简体中文后记为 `zh-Hans / reviewed_text`。 | `2026-10-02T04:12:53.977464+00:00` | `08c46249a67cd7083ba8c3e3b46b4a446d60320b53928915fd072e5d88e7cdda` |
| `tw` | 找到 `朴廷桓`；海峰棋院[人物报道](https://www.haifong.org/news/content/FB0057DC471A9DDB5CFD2DA6895572F9)将繁体姓名与 `박정환`、1993-01-11 生日相连。 | `2026-10-02T04:12:54.289214+00:00` | `fd7c3e3c89cd7c60cdda5125a3172cb09202650859bb67efb81ac19111bcbc28` |
| `jp` | 找到 `朴廷桓`；日本棋院[赛事报道](https://www.nihonkiin.or.jp/match_news/match_result/2019_1.html)称其为九段并记载其赢得世界棋战。 | `2026-10-02T04:12:56.958016+00:00` | `694f367c09d4ed690806e814214f85f93e55b22b9c60a16029c4b2179f7fa5cc` |
| `en` | 找到 `Park Junghwan`；英文维基修订 `1370095338`，[正文](https://en.wikipedia.org/w/index.php?title=Park_Junghwan&oldid=1370095338)写明 1993-01-11、韩国职业棋手、九段。KBA 身份正文作为不同站点交叉佐证。 | `2026-10-02T04:12:58.771199+00:00` | `83cd41a252ac218d50776c2a1c47d2c2d15f2ee28dc940bd1cad2f6e9cb86fc4` |
| `de` | 找到 `Park Junghwan`；德语维基修订 `269555081` 的[围棋条目](https://de.wikipedia.org/w/index.php?title=Go_%28Spiel%29&oldid=269555081)称其为韩国九段并附韩文、汉字。KBA 身份正文独立佐证。 | `2026-10-02T04:13:00.622778+00:00` | `a4468b89faeaf54776845e70831d02551d622521ec119bcf3b75c4ede57a481b` |
| `fr` | 找到 `Park Junghwan`；法语维基修订 `235624730` 的[人物条目](https://fr.wikipedia.org/w/index.php?title=Park_Junghwan&oldid=235624730)称其为韩国职业围棋棋手并附韩文、汉字、生日。KBA 身份正文独立佐证。 | `2026-10-02T04:13:08.536354+00:00` | `a33d8eeab00409d3107db6dacf91814b5090ccb04a79dcbda6937329851f619b` |
| `ko` | 找到 `박정환`；复用韩国棋院[官方棋士资料](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000457)，将姓名与 `朴廷桓`、生日、九段及韩国所属配对。 | `2026-10-02T03:54:12.904147Z` | `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e` |
| `es` | 西语维基[围棋条目](https://es.wikipedia.org/wiki/Go)正文不含棋手名，记录为 `incomplete`，正文哈希 `ee1947947968f13de4105b6e6fb69b594e52539a43314aefa96f712ab6d71603`。另实际捕获西语 Kifubara[职业棋手页](https://kifubara.app/es/players/a42b2257-fad2-4fc5-b978-b76b607239ee)，显示 `Park Junghwan (9p) - KR jugador pro de Go`，语种 `es`，SHA-256 `597f7dbba7b38a35574c8021600c8d982282d180b69c15dcfa08ead40326c00e`。该主机不在当前来源注册表，因此尚不能成为 registry-bound `source_check` 或候选行；保留为正面补充线索，待注册表纳入后再校验。 | `2026-10-02T04:13:06.288233+00:00`（维基）；`2026-10-02T04:22:25.204021+00:00`（Kifubara） | 如左列所示 |

## 工件和校验

- 原始注册表版本 `2026-10-02.3`；规范哈希 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`。
- `research.jsonl`：8 条（7 条 `found`、1 条西语维基 `incomplete`），SHA-256 `9aa60cd246a38b895eba39d787b80b1f0bfce74251eaa1ac5bfd8bf00fddbac6`。命令 `python scripts/kifu_name_research.py --registry docs/resource/kifu-name-source-registry-2026-10-02.3.json validate --input …/research.jsonl --output …/research.validated.jsonl` 退出码 0。Kifubara 是额外捕获，未进入这八条注册表绑定记录。
- `candidates.jsonl`：7 条逐语 `conventional` pending 候选，SHA-256 `de4240a9e20bb8b48ff1e538389fc51b2d0a8c4d6fd3cef76fed628d4c7349f5`。每条的 `research_sha256` 都绑定上述 JSONL 中对应的已校验记录；没有 reviewer 字段或批准签名。
- 没有生成候选 bundle。固定生产清单虽包含棋手目录 ID 54，但该 ID 不出现在任何棋局黑白方 FK 中；根代理确认当前 album FK 数为 0。名称来源完成不构成棋局身份范围批准，也不能作为可直接写入的 name-only bundle。
- 本补记未查询或修改数据库，未写入服务，也未运行测试。当前语种状态为七语 registry-bound 正面 pending；`es` 有正面西语用例但来源尚未登记，故没有 current-registry 候选；`ru` 有冲突转写待 Sol；`tr`、`ua` 未完成来源闭环。没有“十一语已完成”的结论。
