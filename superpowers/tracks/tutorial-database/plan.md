# 教程数据库：当前执行说明与进度

更新：2026-10-18T02:01:55+08:00

本文件已替换早期媒体存储迁移计划，以本轮实际任务为准。完整书单、教学模块与78本制作阶段见 [go-curriculum.html](go-curriculum.html#progress)；状态数据保存在 [progress.json](progress.json)。

## 当前范围

- 当前连续执行目标为23本核心教材、5827个PDF页，直到识别、校验和TEST增量接入完成；完成一本即接下一核心书。其他层级后置；intro-fast作为此前已启动的补充任务单独记录，不计入23本。人工审核及媒体独立记录，不自动完成。
- 78本真实书源按核心教材 → 练习/专项/纠错 → 提高/棋风比较 → 模块内补充 → 独立补充专题推进；每层按模块轮转、每轮每模块一本，多卷分轮，跨模块重复书只识别一次。
- 已完成和正在识别的书籍见下表；空闲任务接续队列中的下一本核心教材。模块13首选《简明形势判断》，石田书复用完成结果，不替代主教材。
- 使用 `.agents/skills/tutorial-gpt-recognition`：GPT-6.1-Sol / high，整页定位、完整棋图转录、严格契约校验、dry-run及TEST增量候选入库。
- 每位子智能体负责一本书，全局最多3个实际模型请求并行；每书每10个PDF页识别及校验完成后在session报告，尾批单独报告。
- 复用已完成final与原页、文字、缓存；不重跑OCR，不覆盖人工校准、审核或音视频。识别/机器检查与管理员人工审核分开。
- 仅TEST环境授权：home-ubuntu，DB system_identifier `7596941912817897507`，`katrain_db`，s3 `tutorial-assets`，媒体地址 `https://go.sailorvoyage.top/media`。不写生产或全表同步。
- 本轮不自动批量生成语音/视频；两阶段在HTML表中独立跟踪。

## 当前已核实进度

| 书名 | 棋图识别 | 验证 / 入库 |
| --- | --- | --- |
| 曹薰铉和李昌镐围棋教室：入门篇·上卷 | 已识别 · 314/314页 · 549图 | 已入TEST·549图；复跑0新增；SGF549份已验证 |
| 曹薰铉和李昌镐围棋教室：入门篇·下卷 | 识别中 · 300/313页 · 731图 | 机器校验 300/313页；失败0；模型疑点0图；待整书TEST入库 |
| 围棋入门速成 | 已识别 · 160/160页 · 132图 | 已入TEST·132图；复跑0新增；SGF132份已验证 |
| 围棋的筋和形 | 识别中 · 50/190页 · 150图 | 机器校验 50/190页；失败0；模型疑点6图；待整书TEST入库 |
| 李昌镐精讲围棋死活：第1卷 | 识别中 · 40/255页 · 65图 | 机器校验 40/255页；失败0；模型疑点0图；待整书TEST入库 |
| 布局基础 | 来源已准备 · 0/197页 · 待识别 | 待机器验证 / 本轮未入库 |
| 曹薰铉布局技巧：上册 | 已有前50页 / 80图结果，待核验复用 | 待核验既有结果 / 本轮未入库 |
| 围棋形势判断基础 | 已识别 · 195/195页 · 468图 | 已入TEST · 468图；人工成果保留 |

“待开始”只代表本轮未开展；旧媒体未核对时不会写成不存在。石田书已完成195页/468图；已保留前100页最终266图及第92页修正。新自动结果不得标成人工审核通过。

## 现有可操作后台

- [测试教程后台](http://127.0.0.1:18012/admin?book=4&page=11&figure=1030&filter=all)，沿用现有SSH隧道和后台登录。
- 最新双档样例：第11页两图，各有Galaxy原生4K与RK1024×600版；新视频待人工审核。TEST provider `f671f20f6`，console `03e967a1`。普通消费者/RK实机未在本阶段部署。

## 当前工具与写入边界

识别使用包含最新实现的APP工作树：`/Users/fan/.config/superpowers/worktrees/katrain-tutorial-module/tutorial-workbench-2026-10-14`：

- `scripts/recognize_tutorial_book.py`：单书与10页检查点；数据输出在书籍仓库 `curriculum/recognition-comparison/curriculum-gpt61sol-v1/<catalog-id>/`。
- `scripts/import_tutorial_book_recognition.py`：通用整书TEST导入，先dry-run；旧石田专用CLI继续保留冻结守卫。
- 缺源PNG页只有确认无图、无来源引用的补渲染页可仅进入覆盖ledger；有图/有引用的页必须核对来源页注册与哈希后才入库。
- 每本交付覆盖/疑点/异常清单、来源到数据库ID映射、真实后台入口和独立SGF导出；顺序未知的静态图不编造replay。

## 更新方式

在本仓库运行 `python3 superpowers/tracks/tutorial-database/update_progress.py --refresh` 从识别输出刷新表格及本说明。每本识别完成必须执行一次；语音/视频阶段变化可用 `--book <catalog-id> --voice '<阶段>' --video '<阶段>'` 更新。原始书目来源：`/Users/fan/Repositories/go-topic-collections/docs/go-curriculum.html`；此仓库副本保留原模块、路径和书目内容。
