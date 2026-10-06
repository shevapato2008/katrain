# 职业报告规则核验与报告界面发布 — 2026-10-07

状态：前后端已部署到home-ubuntu/ucloud-v100，视觉与代码审核通过。53局已在双3090重算并同步到两库，完整参数、逐手结果与原谱核验通过。11局规则仍未确证，保持“规则待核验 / 查看棋谱”，不猜测规则、不发布旧分析。

## 已确认的原因与边界

- 24171原谱 `KM[6.5]`、无`RU`。原职业分析路径沿用通用SGF解析器的`chinese`默认值；前端也把缺失规则显示成中国规则。旧结果未存储有效规则/贴目的核验快照，不能把当前补齐的参数摘要贴到旧分析行上。
- 贴目不能单独确定规则，`Chinese + 6.5`也不应一概改为7.5。24111/24112的规则错误另有直接赛事证据：第26届中环天元赛主办方简章§6(5)规定日本比目法、黑贴6.5，官方赛果匹配棋手、黑白和延期日期。这两局授权`RU: chinese → japanese`，保留原始SGF。另外24162/24163原谱缺RU，经官方赛规确认日本规则6.5；合计4局已证明旧参数的规则错误，不是统一贴目错误。
- 当前KataGo v1.18.2、fd0723把Japanese/Korean映射到同一preset；相同贴目下，两者名称差异不计为引擎分析规则错误。
- 两库各有173,025条棋谱记录，其中数据库`rules`为空35,943条。这是数据库字段统计，并非已逐一核验全部原谱或证明这些棋局都有错误报告。

## 参数准入与结果约束

职业分析需要单一根节点的受支持RU和显式KM，或绑定该原始SGF SHA256的已审核赛事/单局证据。证据保存来源URL、适用范围、审核人、时间；与原谱冲突时，还须逐字段记录原值、核验值与理由。

KM必须有限、在[-400,400]内、步长0.5；不舍入、不补默认贴目。任务存`analysis_parameters`，逐局面存`parameter_sha256`。工作进程、API、列表可用性与同步均核对同一快照。每次引擎请求有独立UUID，过期响应不会混入新参数任务。无核验快照的旧报告不再暴露逐手胜率/目差或标记有报告。

个人报告和直播的显式参数路径保持既有行为；此次准入约束针对职业棋谱。

## 核验与重算批次

- home已有64个任务，正式库已有61个；原数据已分别备份到各机`kifu-report-verified-20261007/backups`。
- 49条已审核证据加4条有效显式原谱，共53局、10,966个局面；冻结清单SHA256：`0dde96291687327222d5cf667b9bf6bb9fc6e8fb910f242a37af84a4ef006977`。
- 两个隔离SQLite工作库，GPU0分配5,521局面，GPU1分配5,445局面。使用`kata1-tf3-b11c768-s11003M-d5973M-7gres`、模型SHA`93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871`、每局面2000visits；已确认两路模型健康和实际初批root visits≥2000。
- 排除未确证的11局：24160、24161、24164–24169、24171、151913、168220。24160/61虽能确认赛事及主办方，现有来源未确证该届适用通则。24161原谱结果`B+R`与官方268手黑胜2.5目也有冲突，不能宣称原谱逐手完整一致。
- 全批原谱/目标身份只读预检通过：home53/53，prod53/53；正式库其中52局已有旧任务，85633尚无对应任务。新增两列已在两库完成，不补写旧结果。

## 发布保护

从当前运行镜像构造局部覆盖，保留同时部署的mixed150赛事标题/搜索代码。endpoint/library仅替换相关函数；web模型仅新增两列；home cron原`ReportTaskDB/LiveAnalysisDB`定义独立保留。保持现有compose配置、环境、媒体挂载；主cron职业批量开关为false。没有重启Postgres、MinIO或原在线引擎；GPU0批量模型为独立容器18002，GPU1使用已有8002。

独立Astra审核：23710048后端通过，cbbc5f81补足KM可执行边界；合并后的局部覆盖通过。设计稿已通过；真实组件初轮发现小窗口裁切、图例数字和盒端细节，修正后聚焦视觉复核通过。最终发布、同步、性能及截图证据见下方。

## 来源

- [天元赛官方简章](https://haifong.org/news/content/22EF19BA83B481381AF2AD202F19366E)、[官方初赛赛果](https://www.haifong.org/news/content/58AE566E6ED7F6175431B3A8BAB17BA0)
- [第2届烂柯杯官方报道](https://u-gen.nihonkiin.or.jp/topics/view.asp?tp_id=23420)
- [固定版本KataGo规则实现](https://github.com/lightvector/KataGo/blob/fd0723fdbc0e9d82cf269c9630af8c27c57c07c4/cpp/game/rules.cpp#L258)、[analysis API贴目边界](https://github.com/lightvector/KataGo/blob/fd0723fdbc0e9d82cf269c9630af8c27c57c07c4/cpp/command/analysis.cpp#L846)
- [51条证据及适用局限](kifu-rules-evidence-51-20261007.json)、[49条准入证据](kifu-rules-approved-49-20261007.json)

## 已完成的发布与真实验收

- 后端参数/职业API/传输回归：`94 passed`（test_kifu_parameters、test_kifu_analysis、test_sync_kifu_analysis、test_kifu_batch_transfer）。前端既有聚焦测试、typecheck、standard和kiosk2D构建通过；独立审核记录包含bbad3a45及1b094d98的APPROVED。
- home镜像：web `katrain-web:report-verified-home-20261007`、cron `katrain-cron:report-verified-home-20261007`；prod对应`report-verified-prod-20261007`。两库已完成两列迁移；主cron职业批量开关均为false。正式机没有职业批量引擎任务。
- 先同步7局新结果供真实验收：24139、24140、24145、24111、24112、24143、24156，共1,984个局面；完整同步保留这7局，仅替换其余46局旧结果。
- 公开测试/正式URL的24111报告：两库均返回277行、参数版本2、日本规则6.5、`parameters_verified=true`，最小`root_visits=2002`。`visits`是候选搜索量，不是局面总root visits，不能用它断言不足2000。
- Galaxy2048×1080/1440×900和kiosk1024×600真实报告截图已亲自查看；独立Astra对部署后的1440主页面、盒端发挥水准和详情给出APPROVED。盒端无3D。主rail不滚，详情参数可在模态面板内部滚动。
- 浏览器真实音频`play()`成功：首次加载0次、一次逐手点击后1次；静音不增加播放。图表切换不触发落子音。未做RK3562实体扬声器验收。
- 本轮浏览器进入棋谱库（应用资源已缓存）：home Galaxy0.900s/盒端0.916s；prod Galaxy0.881s/盒端0.672s。列表仅请求`page=1&page_size=20`并复用首局preview，无另取20份SGF。一次测试站网络瞬断重试后恢复；该测试不承诺任意网络或冷下载整个应用包也在1秒内。
- 原最新24171热身赛仍无确切规则证据；两端列表诚实显示“查看棋谱”，进入`/galaxy/kifu/24171/replay`。其analysis为`rules_unresolved`、`parameters_verified=false`、`moves=[]`。
- 截图位于`output/playwright/`的`home-report-v2-*`、`prod-report-v2-*`及`*-library-unresolved-*`。生产代码不含原型业务fixture。

- 盒端详情标签微调提交0b719e95：列宽88px，`SGF 规则/贴目`为单行，长标签自然换行；一次代表性预览、typecheck和双构建通过。最新前端压缩包SHA256 `90c2f74026120bf84d4db1ab0b029db3462336568cd3d9df384848818cca18cb`，两机standard index SHA256 `a07890c3685277a372bb0d9f685a355d0c392d97a5feb45db65243ec0b1b7618`，kiosk2D index `cd2c27f27e0986fd5a731353e163c25d67860625073f8f4d991b12667910fb20`。保留旧哈希资源，先复制新资源，再原子替换index，不重启服务。

- 双卡速度核查（只读，03:25）：GPU0/GPU1配置及SHA、CUDA/FP16/NHWC、8×4线程、batch16一致；GPU0三次采样90°C、SM1395–1455MHz且三次SW Thermal Slowdown激活，GPU1 80–83°C、1815–1890MHz且一次激活。记录为影响因素，不能把全部39%吞吐差异归因于温度；本批不改变显卡或引擎配置。

- 026b9e61补齐9局韩国赛事显示语义：通用赛事规则取核验证据`event_rules=korean`，实际分析预设及原谱仍是`japanese`。只允许相同或Japanese/Korean等价组合，未知/不等价字段不能覆盖分析参数。7项聚焦回归/typecheck/双构建/2D边界通过，独立代码审核APPROVED。最新发布包SHA `463719168d592c9242ba15f474ee5f8b2ebec6a61d47d9e09712d0c6151dcfc0`；两机最终standard index SHA `f540b4d847286a8682425867d34119b01251da797fa6d6a0d5d4850fbf5c51bd`，kiosk2D index SHA `10b5040194aa24603c2d02482248b5cdd012a88c791cd1c20cf331360ec1257c`。前一标签微调版本已被此同等布局版本替代。

- 最终发布后真实24156报告在home/prod均目视核对：赛事“韩国规则”、原谱`japanese`、实际分析“日本规则”、贴目6.5，字体LXGW WenKai。截屏`*-report-v2-korean-event-details-2048.png`；最终入口资源`index-Wh4cDTJ2.js`。

## 完整重算与同步结果

- 开始2026-10-07 02:20:37、结束05:28:03（北京时间）；53/53局、10,966/10,966局面，两个隔离工作进程均退出0。
- GPU0：26局、5,521局面，单局平均432.46秒（7.21分钟）；GPU1：27局、5,445局面，单局平均260.58秒（4.34分钟）。两卡均值344.90秒（5.75分钟），中位数305.74秒（5.10分钟），范围11.08–643.06秒；包含11手的12087短谱，均值不能视为统一长度比赛的耗时。整批墙时11,245.91秒（3小时7分26秒）。
- [逐局耗时表](kifu-verified-53-timings-20261007.csv)包含原谱标题、棋手、日期、手数、卡号、起止时间、实际root visits及报告链接；CSV SHA256 `7d0f7982f2a052e16cc138b10dee943c848a119ce59599f7ea143892c9ef4baa`。
- 严格核验两路完整结果后，先预检全部目标和46局重置计划，再逐局事务重置、全批dry run、全批事务导入。测试库先完成，再更新正式库；85633仅新增职业任务，不改原谱或个人报告表。
- 源计算结果、测试库导出、正式库导出的完整报告SHA256均为 `d8d146e33441a2560dbd738f89674676a5ce7b1c149e76ca49327ba9d1b510dc`。两库均核对53份报告、10,966个连续局面、全部参数快照一致、53份原始SGF未变化；最小实际root visits=2002（请求2000）。
- 两库这53局的候选/ownership JSON实存合计32,666,416字节；这是选中JSON字段的实存量，不包含行、索引和其他表，不是整库空间占用。表分配量包含其他棋局、索引及删除旧结果后未回收空间，不据此推算每局成本。
- 同步前的只读工具校验首次误选web镜像，旧SGF解析器无`invalid_moves`字段，校验失败且没有数据库写入。helper已修正为批量结果校验使用cron镜像；独立Astra复核12个home/prod镜像选择分支通过，随后完整同步成功。产品代码无需修改。
- 自建GPU0批量引擎18002已停止；原在线GPU引擎和既有GPU1服务保留，正式机没有本次职业批量容器运行。
- 同步后的公开API检查：24111、24112、24162、24163、24156、12087均completed/verified，参数、连续局面、>=2000深度、列表可用性正确，两端逐手响应SHA一致。全部11局未核实棋谱为rules_unresolved、parameters_verified=false、moves=[]、has_analysis=false。
- 第一页20条中11条有已核验报告，最新24171仍只显示“查看棋谱”。本轮API列表请求测试站0.432秒、正式站0.301秒；一次公网连接超时重试恢复，API耗时不等于任意网络的整页首次冷加载保证。
- 全批同步后再次亲自目视检查24163：两站Galaxy1440×900和kiosk1024×600真实页面，规则日本、分析贴目6.5、210个局面，棋盘/候选/走势/操作区正常，盒端3D按钮=0。截图 `output/playwright/{home,prod}-report-v2-final-24163-{galaxy-1440,kiosk-1024}.png`。截图脚本已按实际盒端路由`/kiosk/kifu/24163`及组合规则标签定位；生产业务路由与代码未更改。
- 可审核的实际入口：[正式桌面报告](https://modelstella.com/galaxy/kifu/24163/report)、[测试桌面报告](https://go.sailorvoyage.top/galaxy/kifu/24163/report)、[正式盒端报告](https://modelstella.com/kiosk/kifu/24163)、[测试盒端报告](https://go.sailorvoyage.top/kiosk/kifu/24163)。
