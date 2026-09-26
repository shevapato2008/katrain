# 视觉实验室 · Mac 采集本地契约（2026-09-26）

状态：本地 Fixture 四图由独立 GPT-6 Astra max 裁定 APPROVE；以下冻结首个真实 API 切片的最小边界。尚未验证硬件、未连接测试机。本文件不授权任何远程操作。

## 进程与权限

- 所有 `/api/admin/vision/*` 都要求现有 admin Bearer，不能使用 Galaxy 令牌。只有 `KATRAIN_ADMIN_ENV=local`、`KATRAIN_ADMIN_VISION_LOCAL=1`、并且由专用 CLI 显式将 app 与进程绑定 `127.0.0.1` 时才开放硬件操作；直接调用无 bind_host 的 app 工厂、test/prod 均禁用。app 创建、读状态和读设备候选不打开摄像头/串口。
- 相机连接必须由 `POST /connect` 显式触发，`POST /disconnect` 和服务 shutdown 释放相机、LED、帧缓存与设备租约。设备占用返回 409，绝不抢占 kiosk。候选设备只表示“可尝试的本机编号”，不冒充已探测可用；初始为 `unknown`。
- 预览/采集文件留在受控 `~/.katrain/admin-vision` 下，接口不接受任意输出路径。预览响应 `Cache-Control: no-store`，图像通过带 Bearer 的 fetch 取得，令牌不进入图片 URL。任何异常/拒绝不改变已有已冻结版本。

## 首段 API

| 路由 | 请求/响应关键字段 | 失败语义 |
| --- | --- | --- |
| `GET /status` | `enabled`, `observed_at`, `camera:{state,device_id,error}`, `led:{state,error}`, `geometry:{state,revision,source,confidence}`, `sgf:{state,game_id,total_steps,next_step}`, `dataset:{state,id,count}`；状态来源均为该进程的真实 snapshot。 | 401 无效后台身份；非本机 `enabled=false`，不声称相机在线。 |
| `GET /devices` | `candidates:[{device_id,label,probed:false}]`；只列本机可尝试编号，实际可用性由 connect 确定。 | 非本机/未启用 403。 |
| `POST /connect` | `{device_id:0..8,mode:"stones2"|"led4"}`；成功返回 status。`led4` 的串口只能来自本机配置，缺失即拒绝。 | 409 已占用；422 非法编号/模式；503 硬件失败。 |
| `POST /disconnect` | 幂等返回 status；必须释放跨进程租约。 | 401/403。 |
| `GET /preview` | 一次 `grab_fresh()` 取得的 `frame_id`, `captured_at`（响应时 UTC 观测时间，`captured_at_source=runtime_observed_at`，不冒充传感器曝光时间）, `camera_seq`, `camera_monotonic_ts`, `geometry_revision`, `raw_jpeg_base64`, `warped_jpeg_base64`（几何未就绪时为 null）；最多 2 Hz、最长边 960 px，二者绝不取不同相机帧；超时返回的旧帧拒绝。 | 409 未连接；429 采样过频；503 帧不可用。 |
| `POST /calibrate` | `{empty_confirmed:true}`；真实 burst/空盘自检通过才锁定几何，返回 revision/confidence/source。无 LED 为 `opencv_empty_board`；LED 模式按其实际标定来源记录。 | 409 未连接/未确认空盘；422 非空、低置信度或检测失败。 |
| `POST /sgf` | `{sgf:string}`（UTF-8，最多 2 MiB）；复用 `build_steps_from_sgf`，并从原始 SGF 同时核对宽高，只接受 19×19；返回不可变的步骤摘要、pass/提子、`sgf_sha256` 及新采集会话 `game_id`。会话 ID 与 SGF 哈希独立，同谱可重复采不同模式/几何。 | 422 解析/路数错误；409 未标定。 |
| `POST /capture` | `{game_id,move_index,operator_confirmed:true,overwrite_existing:false}`；`-1` 为空盘初始帧，后续只接受下一有效步，pass/clear 按已有 SGF 真值跳过。返回 `frame_id,sha256,captured_at,geometry_revision,mode,idempotent`。 | 409 未准备好/乱序/LED 不可用；422 错误输入；507 磁盘失败。重拍须 `overwrite_existing:true`，不暗改其它帧。 |
| `GET /sessions/{game_id}` | 从受控目录读 manifest，返回帧清单与下一步，重启后可恢复。 | 404 不存在；坏 manifest 为 503，不伪称空草稿。 |
| `GET /sessions` | 有界的本机实际会话清单（已发布或已保存导谱草稿），不探测硬件。 | 401/403；坏记录需诚实指出，不伪造可恢复状态。 |
| `POST /sessions/{game_id}/resume` | 显式激活已验证的会话数据；不切换相机或采集模式。已发布会话恢复冻结几何为 `stale`，导谱草稿仍需当前标定。 | 404/503；相机或模式不匹配不得进入采集。 |
| `POST /verify-geometry` | `{game_id,frame_id,overlay_confirmed:true}`；操作员检查最近预览中的保存几何，当前相机编号/模式匹配后才把恢复几何置 ready。 | 409 无对应最近预览/硬件不匹配；422 输入错误。 |
| `GET /sessions/{game_id}/frames/{frame_id}/review` | 从真实文件与冻结几何生成叠框，返回 `boxes,class_names,overlay_jpeg_base64`、来源 SHA-256、几何/相机序号/SGF 步数；不修改样本。 | 404 缺记录；503 资产损坏；`no-store`。 |
| `POST /sessions/{game_id}/freeze` | `{}` 使用明确默认参数，或有界的 `val_fraction,stone_frac,led_frac,margin_cells`；返回实际不可变版本 manifest、路径、manifest SHA-256 与幂等标识。 | 422 参数或样本无效；507 发布失败。同步执行，不冒称大任务取消 UI 已完成。 |

上述 JSON 外包与确切字段类型以实现中的 Pydantic schema 为准，前后端聚焦测试必须基于同一契约。

重复非重拍请求在活动会话、明确摆谱确认及完整文件校验通过后，只读返回已存在的帧（`idempotent=true`）；断开相机或重新标定不使已保存响应消失。新帧与 `overwrite_existing=true` 仍检查实时相机、模式和几何，并禁止把新几何写入既有已采会话。

## 数据与样本模式

- `stones2`（Mac 无 LED）固定 `black=0,white=1`；`led4` 沿用 `katrain/vision/classes.py` 的现有四类顺序。captured frame 必须携带模式、SGF 步数/棋面 hash、采集时间/条件、原图 SHA-256、几何 revision/source。`stones2` 不出现红/绿 LED 标签或假 LED 标定。模式不可在一盘中途切换。
- 采集、导谱、标定和断开串行。每次采帧须证明相机序号和单调时间戳晚于操作者确认/LED 屏障；旧帧或超时不发布。`led4` 的旧 `run_capture` 仅可在一次性同卷暂存目录执行，首版 `fiducial_mode="off"`；不能对后台持久目录直接运行。`stones2` 直接采集真实新帧，空盘帧记 `frame_kind=initial_empty`、`led_point=null`，下一 SGF 手数另记进度，绝不伪作 LED 标签。
- 会话 manifest 含 `schema_version`、模式、按序类目、SGF 哈希、几何 revision/source 及几何文件哈希；保留旧标注器要用的 `sgf_path`、`geometry_path`、`frames[].file` 和 `applied_move_index`。每帧使用唯一不可变图片文件名，记录帧 ID、图像 SHA-256、真实采集时间、相机序号、board hash、几何 revision/source、采集条件及 `qa_status=operator_confirmed`。坏 manifest 返回 503；重拍仅替换指定条目，后续帧不变。新图像验证成功后才原子替换 manifest，失败时旧引用文件和 manifest 原样保留。
- 读取已保存 SGF 必须保留原始 UTF-8 字节与换行（包括 CRLF），不经默认文本换行转换后再算哈希。`game_id` 标识采集会话，SGF 来源权威为单独的 `sgf_sha256`。
- 导谱成功前先原子保存有界 `drafts/{game_id}.json`：原 SGF、哈希、模式、导入时几何来源/revision；写入失败不替换已有活动会话。已发布 manifest 优先于草稿，坏 manifest 不回退为空草稿。未拍首帧的恢复草稿仍需当前标定，首帧才永久固定几何。
- 服务端将实际选择的相机编号写入每帧采集条件；客户端不能冒充该来源。重启/重连后的已发布会话几何默认 stale；只有当前相机/模式匹配且操作员明确检查最近预览后可恢复采集。视角改变必须重新标定并另开会话，不暗改已采样本的几何。
- 复核/冻结只读真实采集文件；依据 manifest 的 SGF 顺序或整盘隔离防连续帧泄漏，不按重拍后的文件名排序。冻结目录包含训练/验证两侧非空的可读图像、类别 ID 合法且坐标有限/归一化的 YOLO 标签、与模式一致的 `data.yaml`、所有文件 SHA-256、参数与来源 manifest，验证完成后同卷原子发布。不能单靠旧 `validate_dataset()["valid"]`。失败保留草稿与上一版本。
- 测试机上传、训练和模型回拉是后续用户旅程；未获 Fan 当场 SSH/写入授权，不连接目标主机，UI 始终显示“待上传”。

## 上传本地核心（Task 6 Step 1；不含 SSH 适配器）

独立 Astra max 选择最小纯本地核心，而不是猜测远端目录或提前构建任务平台。`vision_transfer.py` 接受受控冻结 `dataset_id`，枚举 `assets`（不是 `source_assets`），加上原始 `manifest.json` 的字节哈希/大小；复用冻结校验，不重新序列化运行时返回值。上限为 2 GiB 总量、64 MiB 单文件、8192 个文件；清单/源文件改变即拒绝。

配置默认禁用，只允许 `home-ubuntu`，远端根目录默认为未核实 `None`。执行同时要求有效已核实的绝对目录、显式单次确认以及注入的传输对象。当前没有真实 SSH 传输对象、路由或启用配置，因此不会连接远端。传输对象仅约定三类能力：核实空间/暂存/最终版本、写单文件、核验并原子发布；未来适配器必须同卷、不覆盖已有最终版本。

暂存标识绑定数据集 ID 与 manifest SHA。按文件重新核对大小/哈希后恢复；空间按未完成字节加保留空间判断。取消/断线保留暂存，绝不标完成。完整文件集合和哈希核验后才能发布；发布后回执不匹配或丢失为“待核实”，重试看到完全一致最终版本才幂等返回“已上传”。本地 fake 测这些协议状态，不构成真实上传验收。实际适配器之前须逐次授权核实主机/账号、批准目录、权限配额/容量、同卷、工具和无覆盖发布能力。
