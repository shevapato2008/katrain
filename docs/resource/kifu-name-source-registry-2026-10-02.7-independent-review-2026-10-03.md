# `.7` 来源 registry 独立审核

2026-10-03。结论：**PASS（仅候选 registry 元数据）**。`kifu-name-source-registry-2026-10-02.7.json` 可作为下一批研究的固定来源清单；此结论不批准任何网页抓取、译名、人物身份、负面检索结论或数据库导入。下面的证据风险继续 **HOLD**。

## 保留性和可加载性

独立读入 `.6`、`.7` 与仓库默认 registry：`.6` 的原 39 条来源与 `.7` 前 39 条**逐对象相等**，11 个 `language_tags`、11 个 `language_scopes` 和按 `source_plan` 算出的 11 个搜索计划均相等；所有 `complete_for_negative_claims` 仍为 false。只有版本、说明和末尾 10 个新增来源有变化。默认 registry 原始 SHA-256 为 `9a3b3bd517e85f6822d2edd55bc06816bd202919c72214d91a8b7f8a1fd7b7f5`，`.6` 为 `7b857caa5a8058d198cf46ca6fb92eb07a664b0491aa6fe06a83130eaa6393a2`，均与候选作者记录一致；`.7` 原始文件为 `e6ece1699371d54d719e8333cec2fa571c5fc6bb913f71815f0139399b2b591f`，规范内容 hash 为 `e7470d52d26b006a3eb7e799cf649857214e10eb35e565ecf5c269a8987b669a`。`load_registry` 实际载入 49 个不同 ID，无异常。

| 新 ID | 元数据复核 | 审核结论 |
| --- | --- | --- |
| `goratings-zh`、`goratings-ja`、`goratings-ko`、`goratings-en` | 四个 HTTPS `/zh/`、`/ja/`、`/ko/`、`/en/` 起点与留存同 ID 多语 profile 页面相符；`language_go` 合理。四条属于**同一 GoRatings 出版方**。[其 `zh` 页](https://www.goratings.org/zh/players/30.html)有兼容汉字及混合字形，登记 `zh` 准确。 | 4 条 PASS；`zh` 不能充当自动 `zh-Hans` 或 `zh-Hant` 证据。 |
| `nihon-kiin-archive-jp`、`nihon-kiin-archive-en` | 共同 host 为 `archive.nihonkiin.or.jp`，属日本棋院；留存 Oza 日文首页和 `061-e.html` 英文页均为 HTTP 200，英文页原文 SHA-256 `2c39164e6afa456dab7ad057c1c966aefe367b0333d2bfbddee971e963678606`。两条 `official` 符合出版方，分别记页面语言。 | 2 条 PASS；一个协会、不能算两家独立来源。 |
| `weiqi-association-culture` | `wqwh.weiqi.org.cn` 留存正文标题、页脚均标中国围棋协会；[规则页](https://wqwh.weiqi.org.cn/rules/)也以该协会名发布。`official` 是出版方级别；`zh-Hans` 与留存正文语言相符。 | PASS；三份既有 `tls_verified=false` 抓取 **HOLD 传输验证**，不能因注册而视为已验证。被转载正文仍须看署名。 |
| `foxwq-cn` | `foxwq.com` 是[野狐围棋](https://www.foxwq.com/home/)专业平台，`language_go` 符合商业围棋出版方，`www.foxwq.com` 是受现有子域匹配覆盖的引用 host。 | PASS；转载文章不能算原作者之外的独立来源，具体页语言另查。 |
| `cna-tw` | `www.cna.com.tw` 为中央社繁中新闻页面；`reference` 而非棋院 `official` 正确。 | PASS；每篇报道的姓名和身份仍需正文核对。 |
| `sina-sports-cn` | `sports.sina.com.cn` 对应留存新浪体育简中原文，`reference` 正确；既有 `sports.sina.cn` 属另一 host，非此条覆盖。 | PASS；其他新浪子域需另登记或不用此 ID。 |

## 仍为 HOLD 的证据边界

直接读代码确认 `_source_url_matches` 只核 HTTPS 与**主机名/子域名**，忽略 URL 路径；实测 `goratings-ja` 也接受 `/ko/players/30.html`。因此表中的 `/ja/` 等只是研究起点和审阅约束，**不是验证器强制路径**。`_validate_check` 会核目标语的 `observed_lang` 和正文候选，却不要求它等于 registry 的 `source.language`；资料记录必须保存并独立审阅精确 URL、实际语言、同一 profile ID、响应体哈希与原文。代码的 `_matches_target('zh','zh-Hans')` 和 `('zh','zh-Hant')` 均为 false；不能把 GoRatings `zh` H1 自动当繁简显示。英文/日文日本棋院 archive 同 host、GoRatings 四语同出版方，也都不能做独立出版方数量膨胀。

运行现有聚焦测试：

```text
.venv/bin/python -m pytest -q tests/web_ui/test_kifu_name_evidence.py -k 'repository_source_registry or product_language_mapping or source_plan or record_is_bound_to_exact_registry_contents or a_found_name_requires_url_real_body_and_actual_target_language or capture_rejects_page_language_fallback or found_record_stays_pending'
17 passed, 88 deselected in 0.04s
```

未改 `.7`、`.6`、默认 registry、受控原文、代码或数据库；无 Git 提交。
