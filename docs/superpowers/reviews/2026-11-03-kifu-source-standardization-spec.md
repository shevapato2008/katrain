# 棋谱来源统一 — 独立规格复核

**结论：SPEC COMPLIANT。最终实现与双环境冻结 dry-run manifest 符合已批准计划；没有未关闭的规格阻塞项。此结论不表示生产数据已经应用或功能已经部署。**

复核依据为 [实施计划](../plans/2026-11-03-kifu-source-standardization.md)、[R2 批准意见](2026-11-03-kifu-source-standardization-plan-astra-r2.md)及结果、段位、去重三份独立调查。复核对象是 M1/M2/M3 稳定后的 metadata 工作树和最终修复包；物理摆谱与账户历史的独立功能不在本报告范围。未访问 `data/kifu-album/` 文件树，未查询远程数据库，未执行生产写入、设备操作、部署或提交；本复核仅新增本报告。

## 规格对应

- 结果展示共用 formatter：裸 `B+`/`W+` 只表达已知胜方，不补中盘或分差；数值必须完整匹配，保留 `?` 等未知后缀，正确处理已观察到的分数形式。Kiosk 原有中文中盘措辞保留，原始结果不改写。
- 来源段位以 `KifuAlbumSource`/`KifuSource` 的确切原始链接为权威。CWI 无限定 `d/dan` 变为系统未定，19x19 保留 typed `p/d/k`；明确业余、级位和不可解析值保留诚实语义。v2 覆盖绑定 album、side、原始 source-link ID/path、SGF SHA、raw rank、player 及已应用审计 journal；无效覆盖退回来源感知的未定展示。原始 SGF、BR/WR、v1 snapshots 和当前档案事实不被覆盖。
- 历史 `d→p` 需要完整操作、精确日期、有序身份、同段数及星阵明确职业证据。原始 SGF 的日期、段位和棋手身份必须与声称的证据一致；冲突拒绝。首轮 apply 冻结并重查整个相关 counterpart cohort，防止准备后新增冲突；应用后的历史值不随今天的档案重算。Yoda 例外只记录已审定的确切身份及当年七段/九段官方证据，没有通用音译推断。
- 去重先证明同局，再按原始星阵来源与稳定 ID 选择主记录。完整操作含尺寸、展开的 AB/AW/AE、PL、颜色、pass 和节点顺序；短谱、变图、原始日期/身份/显式元数据冲突及不完整输入保留为报告对象。冻结物理来源行 ID 和完整前像，只有经 journal 证明的 pointer 可通过；不产生自指、链或环，不删除棋谱或迁移分析任务。
- apply/retry/undo 使用现有审计设施、确定 manifest hash、事务锁及前后像检查。重复应用为 no-op；漂移拒绝整批，撤销不销毁后续独立改动。组合工具默认 dry-run，先持久化并校验可撤销前像，再允许受控应用；复用现有搜索维护。
- 旧导入/backfill 与真实 native publish/retry/replay 保留原始 source owner、ID、SGF 和 receipt。新发现来源在保留原 owner 的同时以 `reviewed_same_game` 聚合至主记录。隐藏旧卡只通过已验证 journal ancestry 接受；原始详情与公开主卡分别验证。raw stored-SGF SHA 和原有 canonical-SGF 校验分开，分析仍要求精确 SGF 相等。
- Kiosk/Galaxy 列表、详情、报告/回放标题及 Kiosk 导入对话框使用共享棋谱段位入口，中文职业段位显示汉字数字。普通用户强度和通用报告语义保留。

## 复核中发现的问题已关闭

本复核在隔离 SQLite 重现了「原始 DT 冲突被相同 scalar 日期遮蔽」及「原始 PB 指向另一已批准棋手，但 scalar/FK 未变」仍被合并的问题；最终逐项复跑均为 `groups=[]`。历史段位中的同类 raw identity 反例最终返回 `7段`，且无职业 counterpart proof。

另外确认 native 新来源向主记录聚合的缺口、报告/导入 rank 消费者遗漏均已由对应 owner 修复。ASTRA 独立复核关闭了历史 counterpart cohort 漂移及 raw/canonical HTTP 回放问题，并批准了最后的名称来源收紧：展示名必须同时为 `verified` 且有 `reference_url`。未引用来源的展示名产生的 **195 组旧产物已丢弃**，不作为本次修复包。详见 [最终 ASTRA 代码审核](2026-11-03-kifu-source-standardization-code-astra-r1.md)。

## 双环境最终修复包

独立读取并重新执行最终 JSON 的纯 manifest validation，验证 manifest hash、准备代码 hash、gzip 文件 hash、完整 census，以及 `25055→140858` 和两个 `7d/9d→7p/9p` 槽的精确绑定，均通过。没有额外远程查询或环境写入。

| 项目 | home-ubuntu | ucloud-v100 / PROD |
| --- | ---: | ---: |
| 全库 / 段位槽 | 176,949 / 353,898 | 176,949 / 353,898 |
| 可见 / 原有隐藏保留 | 176,690 / 259 | 176,690 / 259 |
| 完整操作候选组 | 1,885 | 1,885 |
| 合格去重 / 拟隐藏行 | 187 / 187 | 187 / 187 |
| 段位覆盖 | 5,571 | 5,571 |
| 未定 / 历史职业细化 | 5,550 / 21 | 5,550 / 21 |
| 原有 snapshots 保留 | 184 | 184 |

187 组准确对应原调查的 186 组合格集合加显式 Yoda 对；21 个职业槽为 19 个自动合格历史槽加目标 2 槽，没有为凑数放宽门槛。1,702 个包含未证明成员的候选组继续报告保留；完整操作组可同时包含合格子组与未证明成员，不能用简单相减解释该数。9 条原重复指针及 250 条其他隐藏记录均保留。

- [home manifest](../../../output/kifu-standardization/2026-11-03/home.manifest.json)：`db5d53d30689b6ae4bdc17b22d2b6028a025f51ece0a3f260f29b5000f59133f`
- [PROD manifest](../../../output/kifu-standardization/2026-11-03/prod.manifest.json)：`8af6346f74815843ff51294df90e53273eb39dfd433dfaec1f31354f54f984f6`
- [汇总、准备证据与兼容性状态](../../../output/kifu-standardization/2026-11-03/summary.json)。两个 manifest 均保留审计前像和撤销所需证据，且分别绑定各自数据库身份。

## 验证与交付边界

除上述独立反例回归与纯 manifest 复核外，核对了 owner/独立审核者记录的最终聚焦验证：M3 174 项、rank repair 35 项（含 disposable PostgreSQL），以及共享显示、报告和导入消费者的相关测试通过；ASTRA 独立验证另有 catalog 40 项、rank/native/API/CLI 83 项和 UI 51 项。测试范围相互重叠，不相加为总覆盖率。Root 的集成 28-suite 记录为 362 passed、2 个已知无新增因果关系的 baseline failure、1 skipped。

[真实运行时验收](2026-11-03-kifu-standardization-runtime.md)使用真实候选 API、生产 SGF 副本和隔离 SQLite，实际组合 apply 产生 5 个 rank 覆盖与 1 个去重。直接检查 Kiosk 1024×600 职业段位图及 Galaxy 1440×900 裸胜图：目标日期仅一张星阵卡，显示职业七段/职业九段；裸 `B+` 显示黑胜，棋盘预览正常。原 ID 25055 详情仍保留 raw `7d/9d` 并返回 `7p/9p` 与 journal proof。隔离环境 logo/硬件服务限制已在运行时记录中披露。

两环境在线 build 均为 `7f2ff0c65381250e41a9dc959d8cac9201c3a86b`，native original receipt、HTTP display duplicate、v2 reader 兼容检查均为 false；最终状态为 `dry-run-only`、`production_applied=false`。因此生产应用仍须等待兼容运行时发布及新鲜的前像/部署兼容性检查。本次经审核交付是候选代码、双环境冻结修复包与回滚证据，未声称在线 UI 或生产库已修复。
