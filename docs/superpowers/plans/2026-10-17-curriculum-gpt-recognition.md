# 课程书单 GPT 棋图识别实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Use fixed per-book agents and independent Astra Max plan/code review. Steps use checkbox syntax.

**Goal:** 按已确认15模块及补充专题书目重要度，对78本去重书逐书做GPT整页定位、整图识别、规则验证与TEST候选导入；每本每10个PDF页报告真实进度。

**Architecture:** 复用现有GPT6.1Sol/high请求、schema、完整上下文、缓存与保守坐标转换。增加最小通用book runner和导入入口，石田专用流程和冻结守卫保留。每书独有输出/进程锁，最多3个实际Codex请求并行；共用DB写入由根代理串行处理。

**Tech Stack:** Existing Python/Codex CLI/PIL/PyMuPDF, StrictBoardPayload, source registry, immutable recognition candidate transactions.

## Chunk 1：来源和共享最小工具

### Task 1：清单与队列

**Files:** 本计划；书籍仓库 `curriculum/recognition-comparison/curriculum-gpt61sol-v1/queue.json`；各书 `inventory.json`。

- [x] 读新skill、AGENTS、HTML嵌入JSON和catalog。HTML与catalog78个同ID，78个book.json realpath独立；主模块65本，补充13本。HTML旧state不代表解析状态。
- [x] 最新Astra决策（用户明确先覆盖各模块最高优先级后修订）：核心教材23本 → 练习/专项/纠错16本 → 提高/棋风比较8本 → 模块内补充18本 → 独立补充专题13本。同层按模块轮转，每轮每模块一本；多卷分轮，组内保留书序，全局按realpath去重、保留全部模块角色。intro-up/down/fast继续；下一批新增shape、life-1、opening。模块4共享intro-down不重复；模块13首选simple-judgement，石田只复用final。
- [x] 首批intro-up/down清点，分别PDF314/313页、549/779图引用；没有电子图final可复用。原页缺封面版权页只渲染缺页，不重新OCR。
- [x] 队列逐书保存catalog ID、sourcebook/book ID映射、PDF/JSON哈希、总页、所有模块角色。78本实际PDF共20,875页；21本使用config.py明确的已有转换PDF或双副本中的指定文件，不执行配置代码或重建PDF。石田195页最终结果复用，不重新模型；曹布局final前50页/80图已只读冻结哈希，整页覆盖仍需核验后复用。

### Task 2：通用识别runner（子agent实现）

**Files:** Create `scripts/recognize_tutorial_book.py`; Test `tests/web_ui/test_tutorial_book_recognition.py`。复用 `scripts/recognize_ishida_remaining.py` 的纯识别辅助，不修改石田冻结文件或195/468专用流程。

- [x] CLI固定catalog id，按真实源PDF总页范围准备page map；复用已有PNG，仅在独有输出assets/pages渲染缺页。物理引用排除commentary_refs，递归章首/小节全部支持；pointer与现有source registry一致。
- [x] 每10个PDF页流水线：detect→查漏recheck→完整图+全页context转录→契约校验→累积results/index/coverage/audit→checkpoint事件。无图页有明确outcome，错误保留并继续，尾批报告。已完成final不重新调用。
- [x] 复用模型gpt-6.1-sol/high、有限600s/2attempts、输入模型/提示/schema/图hash缓存、token/耗时事件。所有真实launch拿同一路径3槽flock；每书独有writer锁；每书workers默认1。
- [x] 一旦完成检测分配物理ID即冻结，首次导入后不能通过新dataset重新几何排序复用旧ID。
- [x] 新输出明确schema2、unknown_stones、source_region confirmed=false、replay needs_calibration，不编造初始局面/被提手数。模型inferences/uncertainties原样保留，坐标转换一次。
- [x] 聚焦测试：异形嵌套、commentary引用排除、缺页渲染不改源、10页结果累积、缓存resume无调用、跨进程请求限额、来源变更拒绝。无需全量回归。
- [x] Astra先SPEC再CODE审核到通过；先首批10页烟测再全书续跑。

### Task 3：通用TEST增量导入（根代理）

**Files:** Modify `katrain/web/tutorials/recognition_catalog_import.py`；Create `scripts/import_tutorial_book_recognition.py`；Test现有 `tests/web_ui/test_tutorial_recognition_catalog_import.py`。

- [x] 保留旧load_recognition以及石田CLI195/468、前266、P92哨兵；generic入口按catalog/source/hash绑定并使用排除commentary的物理pointer。不能让其他书p092-f03误触石田特例。
- [x] generic最终结果必须含完整PDF页outcome、匹配PDF/JSON/image/index hashes、catalog id与总页/引用数。仅部分进行结果不冒充全书完成。
- [x] 缺原PNG而本轮补渲染的PDF页，仅在检测完成、无图、无canonical引用、无识别图时作为coverage-only ledger保留，仍校验图hash；有图/有引用的未注册页严格阻断该书导入，按受控资产/来源页流程补齐，不弱化原注册守卫。expected-pdf-pages必须来自独立PDF清点。
- [x] dry-run只读，apply使用既有TEST身份守卫及事务/audit，按现有保护条件保留棋图/人工校准/审核/音视频。重复dataset/recognitionID一致跳过，变化不得覆盖不可变候选。
- [ ] 使用已核实的本地工具环境和现有TEST数据库隧道执行专用CLI，无需服务部署或重启DB/MinIO/GPU；不访问生产，不运行force/全表同步。每书根代理串行dry-run/apply，复跑确认幂等，生成来源→数据库映射、异常和链接。

## Chunk 2：逐书执行和交付

- [ ] 三位book agent每人一本书；识别验证可并行，请求总并发3。当前首先intro-up、intro-down，下一位按已确定队列intro-fast。完成再领下一本。
- [ ] 每本每10个PDF页（最后不足10页也报）发送：范围、累计已识别校验页/全书页、独立图数、疑点/失败、入库状态。仅定位完成不能计识别完成；失败/待处理另列。
- [ ] 整书coverage覆盖所有页，图引用与独立图数差异有理由；普通编号规则核验不升级真实replay或人工审核。逐图SGF、整书导出及来源索引复用已有后台接口。
- [ ] 独立技术验证与管理员内容审核分开。模型不确定点标识沿用现有后台。无自动批量音视频、不代点人工审核。
- [ ] 持续队列状态与book报告落盘，保留失败断点。遇配额/请求限流有界重试并明确报告，不能无限重试、悄悄换模型或宣称78本已完成。

## 计划审核

Astra Max第二轮PASS，来源页补漏采用coverage-only ledger方案，其余注册页守卫保留。

工具阶段实际验证：通用识别runner17项 + 原/通用导入器40项，共57 passed。Astra Max计划两轮PASS，runner/导入器SPEC/CODE PASS；目标绑定和21本配置PDF适配均窄CODE PASS，实际78/78来源路径与已核实清点一致。已启动intro-up、intro-down、intro-fast三书识别，未宣称整书完成。书单副本/阶段表与当前计划入口在主仓库 superpowers/tracks/tutorial-database/。
