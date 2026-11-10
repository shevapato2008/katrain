# 库内棋手最新段位回退与升段历史：只读调查

本轮只读调查与方案，未实施、未迁移、未回填、未部署。基线为实际fetch的develop `2e7640d892e311f3fc8ed70d4dc5a32e470d2ddf`。本文及邻接JSON写于独立本机调查目录，没有修改用户或其他agent的worktree。

用户最新授权的产品规则：原谱缺段位时，在TEST按已存在的可靠棋手身份取库内最新已知段位，记录来源/匹配时间，冻结后随同一包到PROD；不再以“不是历史当局段位”为由拒绝补充，但必须如实记录这是导入时资料回退。最终仍未知时，前端完全隐藏；前端改动由baipu负责人独占。

## 1. 实际表里有什么

TEST和PROD物理schema一致（证据：test-rank-schema.json、prod-rank-schema.json）。

| 表 | 实际保存 | 段位能力/限制 |
|---|---|---|
| kifu_players | id、canonical_name、created_at、authoritative_pages(JSON) | 没有current_rank、职业身份、updated_at、升段日期 |
| kifu_player_aliases | player_id、alias、normalized_alias、created_at | 唯一约束是(player_id,normalized_alias)，不是全局别名唯一 |
| kifu_player_names | 每实体五语display_name、status、reference、verified_at、revision、evidence_id | 是姓名/i18n审核结果，不是当前等级资料 |
| kifu_name_research_evidence | 按owner/lang/revision保存已审research_payload、原网页摘录/hash/来源与reviewed_at | 部分已包含等级证据，可复用捕获；名称获审不等于任意正文里的段位都获审 |
| player_translations | 名称、国家、五语、aliases、source、updated_at/llm_model | 没有rank；更新时间不能当作等级更新时间 |
| kifu_albums | black/white_player_id、black/white_rank、日期、原SGF等 | 已有的是每盘原始等级，未维护人物当前等级投影 |
| rating_history | users.id、old_rank/new_rank、user_games.id、changed_at | 本系统账号对局升降级；不属于kifu_players，不可混用 |

实际没有kifu_*rank/profile/history表。KifuPlayer的canonical_name本身也无唯一索引；归一化身份必须沿既有canonical/alias集合判定唯一性，不能用first()或五语展示名倒查。authoritative_pages目前只是从已审名称证据提取并追加的来源URL/证据ID；player_pages.sync_player_pages不会抓取并更新等级。

源码：models_db.py:744/805/829/909/1055；player_pages.py:180-268；catalog.py:319-355/524-572；name_parse.py:60-84。现小时prepare已有可靠身份查找，名字模型会拒绝把段位塞进名字，不是等级维护任务。

## 2. 六位真实棋手均有可用的库内最新已知等级

只查三盘对应六个人的已绑定实体及其关联元数据；未全库扫描SGF、未访问新个人profile、未启动任何采集job。两个环境各聚合这六人2701个非重复关联对局席位，其中1865个席位有非空rank；这不是全库覆盖率。对下表每人只再读一个准确已知album的SGF头，确认列值与库内保存SGF的BR/WR相符，双库同source SGF SHA一致。

| 人物 | TEST player_id | PROD player_id | 库内最近非空rank | 其比赛日期 | 凭据source ID | TEST/PROD凭据album |
|---|---:|---:|---|---|---|---|
| 藤泽里菜 | 30 | 30 | 七段 | 2026-10-19 | 91664767 | 179090 / 178754 |
| 上野梨纱 | 9 | 9 | 四段 | 2026-10-15 | 91284570 | 178825 / 178489 |
| 高星 | 503 | 502 | 五段 | 2026-09-16 | 89651576 | 173971 / 173951 |
| 王爽 | 575 | 574 | 五段 | 2026-09-05 | 88955900 | 176027 / 176007 |
| 唐奕 | 483 | 482 | 五段 | 2026-10-11 | 91116424 | 179009 / 178673 |
| 周泓余 | 196 | 195 | 七段 | 2026-10-01 | 90521040 | 176188 / 176168 |

三盘当前album的FK分别为：91694911→30/9；91638738→TEST503/575、PROD502/574；91637528→TEST483/196、PROD482/195。它们当前raw ranks都空。六个中文规范名各自唯一精确命中已绑定实体，查这些目标别名行为空；另有“藤沢里菜”“上野梨紗”独立实体，不能擅自按字形合并，也不从i18n展示名自动挑人。

因此用户建议的库内回退有实际数据可用，而不是必须先建设全库新爬虫。准确说法是“库内最近已知等级”，不是证明今天绝对未升段；尤其王爽/高星的最近非空依据已距查询日约50/39天，来源时间应保留。

### 职业/业余身份的证据

单独“七段/五段”不能自动解作7p/5p。现六人已审姓名research中保留了可复核的身份来源：

- 上野：TEST evidence1709/PROD1714含日本棋院人物页，明确“棋士段位 四段”，并有2024三段、2026四段文字。
- 藤泽：TEST742/PROD747的官方corroboration含日本棋院人物页“棋士段位 七段”；正文另有父亲/丈夫八段，不能正则取第一个或最大“段”。
- 唐奕：TEST1232/PROD1237的中国棋协捕获中有精确playerNo CWA000149、playerName唐奕、playerGrade Z05。
- 高星：TEST1574/PROD1579的中国棋协捕获中有CWA000548、playerName高星、playerGrade Z05。
- 周：TEST1177/PROD1182有职业七段与2023年4月升段文字及官方韩国棋院来源绑定。
- 王：TEST1942/PROD1947有职业棋手身份桥接与官方韩国棋院链接；当前结构尚未提取成独立rank fact。

另一个实际防守点：高星authoritative_pages还混有指向其他棋手“金彩瑛”的百科链接。因此不能把pages数组任一URL都当成该人物的等级权威；只选已经绑定准确人物/官方编号的资料。

这些是已有捕获的来源起点，不能把任意名称research的approved直接当成通用rank认证，也不能把整份中国棋协名单里邻近另一人的grade拿来用。实现时须对精确人物/官方ID/字段进行确定性提取与复核，形成typed rank fact；缺身份时保留未知，不能把“段”默认成业余d。不是再次让LLM猜等级。旧3002映射不参与方案。

## 3. 小时任务的最小接入点

1. derive_staged_record保留原SGF及source_metadata；derive_metadata读取源BR/WR/明确源rank/嵌名段位，不插人物当前资料。
2. prepare_staged_games:159-211已一次得到resolved.player[raw]的本地id、canonical_name、status，并隔离歧义及不便携身份。此处之后可按最多200名唯一player_id批量取rank cache/有限的最近非空原始rank，不做逐卡HTTP。
3. 先把每盘/两侧补充值和provenance原子固定在stage新rank-snapshots目录，键绑定sourceID、SGF SHA、canonical身份及policy版本。翻译/名称流程继续沿用原预算。冻结包生成后，任何重试都读相同rank snapshot，不能再查最新人物等级造成漂移。
4. 当前catalog._validate_manifest:255-296会把metadata与纯SGF/source derive严格比较，原生插入:1496会再次derive。因此只在producer的metadata塞rank会被拒绝或丢失，不能做这种单边补丁。建议将补充放入新版本rank_snapshots契约，原始metadata/SGF保持原样；TEST/PROD原生发布都验证并落相同快照。
5. PROD沿现有canonical逻辑身份重新解析当地id（上表已证明不能传TEST裸id），只接收同一TEST已验证包，不查外部profile、不重新翻译。API一次批量加载本页快照，display先原谱明确值、后冻结补充，最后null/空。原raw rank不改。
6. sync.py目前显式metadata验证只有姓名/赛事，必须给新契约增加五语rank/来源hash和公开列表验证；SGF全hash验证仍保留，checkpoint算法版本区分旧包，不能借旧五语成功记录跳过新增rank验证。

## 4. 当前等级与历史：建议的最小结构

为避免改变KifuPlayer字段形状而影响大量已有名称证据完整preimage与目录hash，建议保留已有实体表，仅新增两张业务表：

- kifu_player_rank_history：player_id、typed rank(value/system)、source_as_of、valid_from(确有准确升段日期才填)、observed_at、last_checked_at、source_kind、evidence/source_ref、content SHA、is_current。每人最多一个qualified current（部分唯一索引）；历史级别/证据不可静默改写。当前投影就是is_current行，不需要新的通用资料平台。
- kifu_album_rank_snapshots：album_id/side唯一、snapshot JSON/hash、原生publication/batch来源。保存导入时的选择、人物逻辑身份、来源证据、source_as_of/observed_at/matched_at与policy版本；不回写原SGF或raw rank。

有效时间和观察时间必须分开。例如一位假设人物官方确认2024-04-01七段、2026-03-15八段，本系统3月16日才看到：history保留7p/8p及各自valid_from，8p的observed_at是3月16日；当前查询返回8p。2024旧谱原BR=7p不动；2025缺rank但当时冻结补充为7p的谱也不随人物资料升段变8p。若来源只写“2026升段”，valid_from留空、证据保存年精度文字；不能伪造1月1日，更不能填本系统采集日。

从棋谱初始化当前资料时，source_as_of取该谱可靠比赛日期，observed_at取本次观察时间，valid_from未知。晚上传的旧比赛不会因为created_at新就覆盖更近期人物资料；不按MAX(rank)或MAX(observed_at)选当前。若来源同优先级/同有效日期冲突，隔离资料候选，不随便选一条；单个人物缺rank不堵整轮新谱。

【此段为早期只读建议，已被最终首切片“零外部profile请求”取代；不得据此实现爬虫。】更新：有效新谱明确rank可在TEST按已绑定人物追加观察；同时仅对本轮实际涉及且资料超过24h需复核的少量人物，使用已绑定官方URL/official playerNo的确定性适配器，最多10人、20HTTP、60秒、单响应2MiB，受全轮预算及按源退避约束。可复用已捕获官方证据初始化，不新增等级LLM。无安全定向接口时用已有缓存/最新已知rank并记录延期，不在小时任务遍历整个名录或棋谱库；另行有限人工资料更新。具体适配器与阈值应在实施前Astra审核，当前未访问或启动该刷新。

## 5. 已上架近期缺rank谱的独立修复

首批仅三个明确sourceID（91694911/91638738/91637528），后续可另批限100、近期窗口内明确选择。准备dry-run清单：sourceID+原SGF SHA+双侧原raw rank+当地已绑定身份+现有快照完整前像+选定rank事实hash。原谱已有rank则不补。

用新版本原生rank correction包，在TEST对已存在的exact SGF/同一album追加rank快照并完整验证，再把同一纠正包到PROD；新的correction key/receipt保留旧正式包与receipt，不能把旧冻结包原地改成另一个hash。沿用现有source/Stage/publication单写者边界和原生行日志，重放为already_applied。保持原album ID、源SGF、source links、翻译结果及prod_synced进度；不复位旧item或伪造重新导入。不在本调查阶段执行。

具体任务、文件、约束与测试见邻接Writing Plans文件。方案尚未由Astra审核，所有表/接口/命令均为候选设计，不是已上线状态。
