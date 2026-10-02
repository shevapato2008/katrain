# 棋谱核名来源清单快照

来源清单在每个已审批次中按完整 JSON 哈希固定。增加专业来源时创建**新版本文件**，不要原地改写旧版本；研究、候选和导入命令使用同一个 `--registry` 路径。现有棋手 ID 的不同语言可以分批使用各自的版本；新增身份在一个批次中必须备齐基于同一版本的十一语言名称。

| 版本 | 文件 | 规范 JSON SHA-256 | 用途 |
|---|---|---|---|
| `2026-10-02.2` | `kifu-name-source-registry-2026-10-02.2.json` | `e2ed3cafa9b6f32d8ba30c78aecdf9667801df3cf34745227e5da588e98dd58e` | 与现有默认 `kifu-name-source-registry.json` 内容相同；保留先前吴清源等候选的证据哈希 |
| `2026-10-02.3` | `kifu-name-source-registry-2026-10-02.3.json` | `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61` | 新增英语 GoBase Articles 和西语 Godokoro，并纳入对应语言的必查来源 |
| `2026-10-02.4` | `kifu-name-source-registry-2026-10-02.4.json` | `b2d0b2fd65ce22b036e0160574301d954545450638edadf3981d1d53faf7a34c` | 按独立审定，仅增加智利围棋协会西语资料 `chile-go-federation`（`language_go`），并纳入西语必查来源 |
| `2026-10-02.5` | `kifu-name-source-registry-2026-10-02.5.json` | `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f` | 按[本因坊俄语来源独立裁决](kifu-name-honinbo-registry-decision-2026-10-02.md)，仅增加围棋资料馆 `nikoraido-ru`（`language_go`），并纳入俄语必查来源；土语沿用已登记的维基百科来源 |

新增来源依据分别见 [吴清源剩余语种研究](kifu-name-wu-remaining-sources.md)及 [西语/乌语疑难复核](kifu-name-wu-es-ua-sol-adjudication.md)。新版不自动升级旧候选签名。若把旧候选改为新版，其研究哈希、候选审核和负面闭环都要按新版重新核对；已捕获且仍有效的网页正文可以复用，不能复制旧审批签名。

默认路径暂保留 `.2`，以免后台研究工具无意改变已有受控工件的解析版本。新批次应显式传所需快照路径；朴廷桓西语候选使用 `.4`。智利来源的准入依据见[独立裁决](kifu-name-park-junghwan-es-registry-decision-2026-10-02.md)：仅准入来源，不自动批准具体译名或其他网页。
