# 后续识别诊断：只读勘察记录（未开始设计/实现）

独立 Astra 只读核对现有生产链，供训练旅程闭合后的下一切片使用。不能把此文当诊断模块已完成或七格同帧已实现。

生产入口是 `katrain/vision/service.py` 的 `VisionService → InProcessAdapter`，不是较薄的 `DetectionPipeline`。

| 目标阶段 | 最小真实挂点与缺口 |
| --- | --- |
| 原图/标定叠图 | `worker_inprocess.py:_loop` 的本轮 raw frame + GeometryLock；不能拼接 admin.preview 另一次取帧 |
| 纯 warped | `_warp_frame` 返回后保存，只在帧平均/CLAHE 覆盖变量前观察；生产有 margin，要与 admin 的普通预览区分 |
| YOLO NMS 后、业务去重前框 | `stone_detector.py:detect` 中 backend_impl.detect 返回、dedup 之前；不是模型 tensor |
| 业务去重后框 | dedup 后再 `drop_shadow_boxes`；分 keep/sustain 档前后要标清，画框与参与棋盘赋值的框不是总相等 |
| 纠偏前棋盘 | 目前**没有**独立矩阵；`board_state.py:_positions/parallax_points` 有原始/视差坐标。`occupancy_aware=False` 仍经过视差修正，不能当完全纠偏前。下一设计须明确“纠偏前”含义及只读生成方式 |
| 纠偏后棋盘 | `detections_to_board/_assign_occupancy_aware` 后本轮 observed_board，已有视差/占位冲突/LED掩码/迟滞等修正；`raw_observation` 也是这个结果，不是纠偏前 |
| 最终稳定棋盘 | 两帧投票后还经过用户否认与 reference_check，取最终 `_publish_status` 的棋盘；`_last_stable_board` 尚不是最后发布结果 |

- 当前默认最多8帧平均再 CLAHE，因此 YOLO 真实输入不是当前 raw 的单张 warp；后续应显示同一处理批次及贡献帧范围/预处理来源，不能悄改识别配置来伪装同帧。
- `MoveDetector` 返回确认落子，不生成第八个稳定棋盘。旧 subprocess preview 会另读新帧叠旧框，不能用作同帧证据。
- WorkerStatus.observation_seq 不是 camera seq，现有 JPEG/board 分别读取缺统一模型哈希/几何版本/时间身份；最小快照需在同轮保存实际局部结果。不再次推理、不重复有状态赋值、平均或 MoveDetector，避免观察改变原算法状态。
- 当前只做勘察，未开始本切片 Artifact、Fixture、后端、设备或模型下载。先完成训练当前旅程；真实模型拉取/激活需独立授权和失败保留旧版本。

## 独立 GPT-6 Astra max 裁定

采用 `AdminVisionRuntime` 已持有的 CameraHub/GeometryLock → `VisionService/InProcessAdapter` 单次真实运行＋可选只读观察出口；不另拼简化 DetectionPipeline，不为七格重复推理或重复调用有状态逻辑。

- “同帧”应准确表述为**同一识别处理批次**。以当前原帧为锚点，帧/序号/单调时间从同一次加锁读取获得；保存实际平均的最多8条贡献帧身份。保留真实平均与 CLAHE，不为设计图关闭预处理。
- 第3/4格背景使用真实平均＋CLAHE推理输入；第3格是模型NMS后框，第4格是业务去重＋阴影剔除框，另标 keep/sustain 与实际赋值输入的区别。
- 第5格明确命名“原始定位投影·诊断派生”，不是生产中间结果：从本轮去重棋子框的原始连续网格坐标最近点落格、越界丢弃、同格最高置信度胜出；不做视差、sticky、spill、掩码或历史修正，不回灌状态。
- 第6格是单次真实 `detections_to_board()` 的返回值；第7格是逐格两帧投票→deny mask→reference check 后实际发布的棋盘。缺参考/未应用/历史刚初始化明确显示。MoveDetector不生成另一份稳定棋盘。
- Mac首版仅 viewer 模式，不绑定对局、不启 monitor、不提交棋步或控制 LED；没有对局基线时，MoveDetector与参考相关能力显示“未参与”。
- 采集、重标定、切换设备/模型前先停止诊断并确认旧线程退出；超时仍阻塞，不把旧平均/历史带入新代际。一个worker、一次在途推理，观察输出最多2Hz，不改变原识别采样配置。
- 只保留最新完整快照和生成中的一份；最多raw/纯warp/实际推理输入三个底图，长边≤960、每JPEG≤1MiB，框每阶段≤4096，总响应≤8MiB。超限报不可用；运动/断线/超时保留整份旧快照并标stale/error，不拼接新原图旧结果。
- 本地只加载受控登记且hash/schema核实的模型；保留当前/上一版。远程拉取仍disabled，不能隐式下载权重。真实下载/激活与设备验收不由此裁定授权。

以上是训练旅程闭合后下一切片的设计依据，不代表C已设计、实现或设备验收。

## 模型与停止边界补充裁定

- 可信登记固定 `model_id + manifest_sha256`，列表不加载torch，浏览器只传ID。将训练 `_artifact_info` 无self的规则抽成纯校验；训练继续提供冻结spec，本机登记用独立可信摘要固定manifest，内部一致性不冒称外部来源证明。实际激活的一次模型加载还须核对YOLO.names数量/顺序，不能只信checkpoint_readable旧声明。
- 旧诊断确认退出后才加载新模型。加载失败保留current/previous，但明确诊断已停；可手动重启旧版，不暗中启动。
- 通用VisionService.stop目前会丢掉join超时的worker引用。仅附加诊断专用 `stop_diagnostic() -> bool`：旧句柄仍alive则保留并阻塞采集/标定/断开/启动/换版本；确认退出才清除，不顺带改生产subprocess生命周期。
- imgsz目前在config→worker→detector→backend三处未贯通。C修通实际Ultralytics输入值并写快照，未指定仍960；不扩改ONNX/RKNN固定输入尺寸。已用Context7官方接口文档核对本地.pt、model.names及predict imgsz，实施时以本机已核实8.4.34源码为具体版本依据，不能套当前文档中的新型号下载示例。

独立Astra对C计划三个chunk均Approved；正式HTML、Fixture与后端仍按顺序分别完成，批准计划不等于视觉或设备通过。
