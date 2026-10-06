# 历史日本棋手韩文名：规范生成决策

2026-10-06；决策者 `/root/historical_ko_policy_astra`，`gpt-6-astra`。本次仅核查政策、来源与部署代码；没有修改代码、签署姓名候选或写入数据库。

**决定：允许继续使用既有 `generated` 路径补齐韩文。官方日文原名及本人假名读音已确认、既定有限可靠来源检索未取得可采纳韩文名时，可按国立国语院规则生成，并独立审核每个完整输出。无需等待网上出现已发表韩文名，也无需新代码、迁移或新的转写框架。** 这项决定沿用用户此前对有来源规范转写的授权；不改变主五语言的现有证据门槛。

国立国语院明确规定，日本历史与现代人名均按日语表记法处理；假名表区分词首与词中，日语细则规定促音及长音处理。[假名与韩文对照表](https://www.korean.go.kr/front/page/pageView.do?page_id=P000108&mn_id=97)、[现行完整规则，第2章表4、第3章第6节、第4章第2节第3项](https://korean.go.kr/kornorms/regltn/regltnView.do?regltn_code=0003)。两页已于本次联网查得，HTTP 200；检索及页面内容保存在 `/tmp/kifu-ko-policy-normative-search.json`。

立即按以下最小流程执行：

1. 复用已经捕获的同人官方页面，记录原名、精确假名、姓与名的边界、来源 URL、正文与哈希。汉字读音、生日及身份对应存在歧义者仍 HOLD；不得从汉字字典猜读音。
2. 使用当前 registry 的韩文必需来源 `korea-baduk`、`wikipedia-ko`、`wikidata`，补齐 **v1 有限负面闭环**。前两者执行明确的姓名及已知变体查询，并实际完成所声明结果的分页；Wikidata 查询已确认同人的精确 Q 项之 `ko` labels、aliases、sitelinks，关闭语言回退。复用已有真实抓取，列出查了什么、何时查、返回什么及已知线索如何处理。闭环只说明这个有限范围未取得可采纳用名，不宣称穷尽网络。
3. 原有 GoWiki、Namu、新闻及其他已知线索不得丢弃。出现可靠且同人韩文用例即按 `conventional` 审核；不合格线索保留正文、实际来源角色和明确拒绝原因。现有 `rejected_leads` 验证器要求实际独立 `gpt-6-sol` 审核，不能冒写模型名称或挪用别人的签名。
4. 为日文→韩文使用明确版本，例如 `nikl-ja-ko-personal-name-v1`。在研究载荷内绑定规则 URL/正文哈希与逐名转换说明，区分词首、词中、促音和长音；全部内容由 `research_sha256` 绑定。无需开发通用音译器。研究保持 `scope_status=not_found_in_scope`、`candidate_name=""`、真实 `reading/reading_basis_url`；候选使用 `decision_kind=generated`，精确输出放在 `display_name`。
5. 独立审核先完成 `negative_closure.version=1`，再完成 `generated_review`，后者时间须晚于闭环，明确批准同一 owner、语言、原名、读音、输出、规则和研究哈希。此政策决定本身不等于这些具体姓名已获批准。
6. 沿根线程既有步骤交付：每5位完整五语形成精确25项 pending → 根线程审核 → TEST dry-run/apply/verify → PROD → 来源页面追加 → 实际覆盖统计。若一位暂缺完整证据，可换入下一位五语齐备者；其他已完成者不必等待它。

已只读检查本地 `name_candidates.py/name_evidence.py/name_batch.py/name_transliteration.py`，并直接读取 TEST `katrain-web` 及 PROD 当前导入镜像 `katrain-kifu-importer:five-gate-978491a2` 的相关函数。两处均已有上述 `generated`、v1 闭环及精确 `generated_review` 校验，导入器将完整 candidate/research、decision_kind 和 generation_rule_version 持久化，因此数据可以如实表示“规范生成名”。各部署源码哈希不同，不作全树一致声明；本结论限于已读取的相关分支。

**硬边界：** KO 不能借用仅供六种次要语言的 `transliterated` 或 `negative_closure.version=2`。不能把生成名写成 `conventional`，不能将空正文、超时、验证码、未完成分页写成成功负面检索，也不能为当前人删减必需来源来取得放行。实际不能满足 v1 的名字暂留 HOLD，继续其他完整名字；不为缺少已发表韩文名而放宽校验。姓名显示决定不授权合并人物、修改 FK 或自动增加跨人物别名。

**附加决定：許育祺（PROD 5899）的个人博客用例。** 根线程捕获的 `472 쉬위치(Xu Yuqi)` 可保留为已发表候选线索，但单凭该转载排名表不足以批准 `conventional`。具体可靠性问题已核实：[博客](https://qkrrhkdfo1.tistory.com/640)第3行把指向 [GoRatings 1090](https://www.goratings.org/en/players/1090.html) 的 Park Junghwan 写成 `박중환`，而该页面指向的[韩国棋院本人档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000457)明确写 `박정환(朴廷桓)`。这是对该表姓名准确性的直接反证；不是把所有个人博客一律排除。

该博客如实登记为个人围棋博客/参考线索，不能升级为官方或机构专业来源。原有 Badukworld URL 目前 HTTP 200 但无正文，也不能补足正面证据。許育祺可以在真实闭环后按已核实的汉语本人读音及[国立国语院中文表记规则](https://korean.go.kr/kornorms/regltn/regltnView.do?regltn_code=0003)独立生成；必须记录并处置 `쉬위치` 这一已知线索，不声称网上无该字串。日文转写规则不适用于这位台湾棋手。其具体输出本次尚未批准；retired12 其他4位可换入下一位完整棋手后继续原25项流程。
