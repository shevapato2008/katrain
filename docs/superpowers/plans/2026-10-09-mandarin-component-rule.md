# 有来源普通话读音的 NIKL 有界转写

本实现采用 2026-10-09 已批准的范围修订：对来源已给定、人工确认同一人物、现代普通话且音节切分明确的姓名补齐 NIKL 组件转写。取消 GF0015 扫描表 1110 条转录及完整合法拼音全集作为前置条件。渲染结果仅证明规范输出可复现；身份、读音合法性、普通话范围与候选审批仍由现有正面证据路径判断。

## 已核来源

- NIKL `https://www.korean.go.kr/kornorms/m/m_regltn.do?regltn_code=0003`，捕获正文 SHA-256 `fba7508fd4dfb60eee30561ff8e11c64493fb3f0bd9fecceacb1fcedd13c6731`。第 2 章表 5 原始 HTML 行 1573、注记行 1578；第 3 章中文条款行 6666、6707；第 4 章人名范围行 13706。
- MOE 拼写说明请求 `https://www.moe.gov.cn/s78/A18/A18_ztzl/jnhypyfa/201805/t20180517_336341.html`，实际最终 HTTP 同路径；正文 SHA-256 `184692fa2fd97dc8b356c5cef1c0e56fec58995de076a1e82fa8c4070a3d484d`。原始 HTML 行 206 支持 jqxy 后 ü 省点，韩文输出来自 NIKL。
- GF0019 是盲文方案，排除。GF0015 仅保留为参考，不声称其音节表已转录或已证明完整合法拼音集合。

## 实现

1. `name_zh_ko.py` 保留旧 30 个 `{hangul, kind, locator}` 完整对象，优先原样查表。`SOURCE_BASIS`、`RULE_VERSION`、旧 18 项 `LEGACY_RULE_SYLLABLES` 不变。
2. 同模块存放实际 21 声母、38 韵母行，数据方法版本 `nikl-table5-components-v1`。仅针对给定音节选择明确组件，不生成声母×韵母合法全集，不从汉字推音，不自动切词。
3. 有限分支覆盖零声母 y/w、七个 apical-i、括号前接形式、表内 iou/iu 与 ui/un、省点 jqx u、n/l 显式 ü、ㅈ/ㅉ/ㅊ 后规定的 ㅑ/ㅖ/ㅛ/ㅠ 简化。表中 yue/ue 是 웨，n/l üe 按该行组合为 눼/뤠。独立 er 可用，附加儿化 r 不在本范围。未知、未覆盖或无法确定的拼法 HOLD。
4. 新 `used_entries` 带稳定方法版本与实际规范 locator。旧证据的 no-www URL + `92977a7c4e2d255aa62d91011372bea1a198f5c3ee6f92db5b02fa6366fb9d9b` pair 仍只支持旧 18；www + `fba7508…` pair 支持本次组件输出。错配 URL/hash 仍拒绝。
5. `name_evidence.py` 只增加拼音 ê 的保留，以及 current pair 对已由规则重现条目的支持。读音捕获、身份、现代范围、精确分节、contrary checks、独立审批、完整 proof 与 ledger 资格不放宽。

## 最低充分验证与交付

- 旧 30 完整对象 SHA 回归及已有全部旧姓名输出；各有限规则分支的确切韩文预期；ü/ê 正规化与未覆盖拼法拒绝。
- 一个明确标注为合成协议夹具的新组件姓名，经 native candidate 校验和 batch 导入进入合格 ledger；旧 capture 及篡改方法/范围/冲突/分节拒绝。夹具不作为真实人物的来源证据。
- `.venv/bin/python -m pytest tests/web_ui/test_kifu_name_candidates.py -k positive_zh_ko -q`
- `.venv/bin/python -m pytest tests/web_ui/test_kifu_name_batch.py -k positive_zh_ko -q`

本范围仅上述两个模块、两份聚焦测试和本方案文件。实现后一次最终代码审核；本实现任务不 commit/push，不接触生产 DB、SSH 或部署。
