# Mandarin component rule：最终独立代码审核

**PASS。没有需要修复的阻塞项。**

审核人 `/root/durable_rule12_review_astra`；实际 UTC `2026-10-09T11:04:41Z`；配置 `gpt-6-astra / max`，依据 `source.parent_spawn`，不声明 serving variant。审核基线 `b0744bcc`，范围为下列五个文件；依据已批准范围修订 `77baaa2df091b7d3d73ae76bfeff1b4c504905dfd9247062cd2ec7aee0d172c5`。没有 DB/SSH/部署/Git 修改。

## 精确字节

| 文件 | SHA-256 |
|---|---|
| `katrain/web/kifu/name_zh_ko.py` | `a98dec4b66cae8cefc86950c0451b3bc31cbbbcb3d6ea301c985ac6543e7dc37` |
| `katrain/web/kifu/name_evidence.py` | `467bcd1ed905ead7567789ab76a586d5e9b9377678b7d8f7c41f8da770484a7f` |
| `tests/web_ui/test_kifu_name_candidates.py` | `b2a1e04624d0e4122fcdafac231ebb0b757f35df353503840b747bf829688553` |
| `tests/web_ui/test_kifu_name_batch.py` | `60cdf1619a0ef928c406bdf1b70aaeff8e465d90b39f29ef427aea7ee0ae050d` |
| `docs/superpowers/plans/2026-10-09-mandarin-component-rule.md` | `96b8ed2842aa11bd1cbc7a7d603aaaaa6045ac100142baa894ab21b724f36597` |

## 已核结论

1. 从真实 NIKL `fba7508fd4dfb60eee30561ff8e11c64493fb3f0bd9fecceacb1fcedd13c6731` HTML 行 1573 独立解析了 21 声母、38 韵母和 7 个方括号特殊音节，与代码逐项相等。没有依赖错误 no-www 标注或 GF0019 盲文文件。实际规范来源仍是 `www/fba7508…`，MOE ü 省点说明仍绑定真实 `184692fa…` 正文。
2. 对基线模块和当前模块直接比较：旧 30 个完整对象、旧18集合、两个精确 URL/body SHA pair、规则版本、source_basis 和 RULE_LOCATORS 均未改变。旧30 canonical SHA 为 `e303a74f8cfa26b440c29b8b8029748e2fd2171b41a32196790aaba82217fa1e`。历史条目优先返回原对象，新增 `method` 不进入旧 proof；旧 pair 仍只接受原18，新组件只能使用当前 exact pair。
3. 组件选择处理零声母、apical-i、声母后括号形、iou/iu、ui/un、jqx 省点 ü、n/l 显式 ü及规定的介音简化。Hangul 合成保留韵尾和后续韩文字，不把 ㅌ/ㅅ 套入 ㅈ/ㅉ/ㅊ 的简化。实际抽核 `qiu→추` 和 `lüe→뤠`；后者来自 NIKL yue/ue→웨，未加入无原文依据的覆盖值。未知或未覆盖形式走 ValueError。
4. `_normalized_phonetic_reading` 只对拼音新增保留 ê；ü 与 ê 不被通用去重音误折叠，日语路径未扩大字符接受范围。
5. 新 renderer 是**来源给定音节的转写函数，不是合法拼音或身份认证器**。代码及计划都明确这一点；未生成声母×韵母合法全集。现有 positive validator 的人物 owner/中文原名、现代普通话 scope、同人读音捕获、准确分节重现、contrary/conflict 和独立候选审批门槛未放宽。新的 rule entry 必须和当前规则重新生成的完整对象相等，不能自行改 method/locator/output。
6. 既有 ledger/reader 实现未改。新增合成协议夹具检查新组件候选进入原生 batch 后可被 qualified reader 读取，并在 batch 不再 applied 时失效；它明确是 synthetic，不是任何真实人物的新来源批准。

## 验证范围

已读实施者真实结果 `verification.md`：现有 positive_zh_ko 选择器 candidate **151 passed / 120 deselected**，batch **14 passed / 95 deselected**；diff whitespace check 通过。审核者未重复运行这两组或扩大回归；额外只做实际源表逐项比较、基线旧对象/常量一致性及上述两个有针对性的渲染核对。

本报告批准这组实际代码进入 root 既有发布流程；不宣称已经发布、完成任何新人物 source/candidate 审批，或证明完整合法拼音全集。
