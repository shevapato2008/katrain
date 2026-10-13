# 本次决定：复用 translated，有限支持原文赛事直译

批准扩展现有 `translated_from_original → translated` 路径到 **已有 `raw_event` ID**，用于完整原文描述的五语言显示。无需再向用户确认。本决定允许实施协议扩展，不代替每份真实候选的独立批准；我本次只读代码并写此文，未改代码、DB 或部署。

已核对 `name_evidence.validate_research_record`、`scripts/kifu_name_research.py`、`name_candidates._validate_candidate/validate_bundle/render_event_components`、`name_batch._check_raw_owner/_apply_candidate`、`identity._approved_names/_approved_raw_event_names/_raw_event_map`、`legacy_raw_events.py` 及旧运行时打包器。阻塞点明确：研究仅接受 event；strict reader 仅对实体赛事接受 translated；legacy helper 只读三个旧 raw。批处理写名称与证据的主体已能复用。

1. **扩展直译验证，保留真实证据。** 仅加 existing raw_event ID 和 cn/tw/jp/ko/en；沿用 `decision_kind=translated`、`translation_method=literal_event_title`，raw 分支用明确的 `raw-event-title-translation-v1`，原 event 规则继续有效。candidate.raw_value 必须精确绑定 DB owner 与库存原文；source check 保留真实 URL、正文摘要、SHA、抓取时间、原文语言。研究记录始终 pending，由实际 root 独立签候选；不把中文网页改称英语证据，也不把直译宣称为目标语言惯用名。只允许本批可读原文类别，旧 generic/archive、损坏值及玩家不借此放行。

2. **核心复用在离线生成时完成，DB 存完整标题。** 复用 `structure_event` 和 `render_event_components`，每个 raw 绑定无损 parts、原文核心和明确 year/edition/round/game；源证据可复用同一个准确核心，`original_name` 是来源中实际出现的核心，完整 raw 另行精确保存，不能声称网页含完整赛事轮次。每语言最终 display 由已审核核心译文和这些部分生成并逐项绑定。仅补当前实际遇到的汉字/全角序号归一化，保留原始片段，不猜缺失部分。友情杯 7 raw、招商杯 17 raw 都存五种完整译名；不启用 Honinbo 的 34×11 composition，不要求新增六语言模板，不把只译核心记为整条完成。

3. **直接走现有入库管线，保留数据界线。** 使用 `bundle_format=2 + inventory_format=4 + album_links=[]`，固定 owner/preimage/member/inventory，复用 dry-run、apply 与撤销账本；format 4 的强制 selected_event link 不适用。该分支仅写名字、证据与账本，不改 alias、赛事 FK、原始 EV/SGF。先核对 raw owner 已存在且 approved；此有限决定不批准伪造 ID 或新赛事身份。第1届/第一届等 raw 可产生相同完整直译：仅给两端均已审核的 translated raw_event 描述增加同名豁免，批内与跨批门禁一致，不伪填 `distinct_people_confirmed`，不把同名当身份归并。

4. **strict 与 PROD 旧运行时增加同一窄读取分支。** 新分支核对 signed candidate、research hash、owner ID、精确 raw、lang/display、rule、revision、实际 producer/reviewer 和 approved 状态；复用一个无 ORM 依赖的小资格校验，旧 helper 仍用 SQL，打包器仅带所需纯规则。现有三个 raw 的模板/档案门禁继续原样工作；新 raw 资格来自已批准 DB 记录，无需每批改静态白名单。页面读取按当前页 exact raw 集合限定，显示和搜索均只作用于当前 `event_id IS NULL` 且无 selected_event 的原始 EV。相同译名的已批准 raw 搜索应 OR 全部精确成员，不能继续要求唯一 raw_event_id。六种次语言直接读已批准英文，五种主语言缺译仍算缺口。

5. **最低充分验证并立即继续入库。** 聚焦现有赛事翻译/legacy 测试：一组完整五语言 raw 经 dry-run/apply 后在 strict 和打包旧 reader 的显示、精确搜索一致；覆盖全角/汉字轮次、同名 raw、多语言 English fallback，以及错误原文/hash/独立签名或撤销后不放行；确认 alias/FK/SGF 未改即可，不追加全库逐赛事考证或全量回归。当前可直译的 493 局与待用现有身份匹配的 606 局分开统计；Nihon Ki-in #1 的 354 局继续 hold。只有最终五语言译文实际入库且读取得到的字段计完成，pending、缺译和 fallback 不冒充新增翻译。
