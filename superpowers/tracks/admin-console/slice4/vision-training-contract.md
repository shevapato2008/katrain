# 训练契约（2026-09-26 本地冻结）

HTML 与四态 Fixture 同尺寸四图已由独立 GPT-6 Astra max APPROVE；另一独立 Astra 规格/质量 APPROVE，根代理16项聚焦前端测试通过。本契约允许进入本地后端，不授权外部操作。

## 最小部署边界

首版训练由测试机独立 admin 服务内的单协调器管理一个独立子进程/进程组，不在 ASGI 内执行 CUDA/增强。默认禁用，实际目标根目录、权重、GPU 预留未知；独立 Astra 已批准只有 `test` 环境＋显式开关＋已核实配置可启用。Mac local 始终 disabled/unknown，不暗中 SSH 或代理远端令牌。操作者在 Mac 经当次授权隧道访问测试机 loopback admin，用不同浏览器 origin/端口独立登录；隧道授权不等于训练授权。无效身份一律 401，能力未启用 403，资源未核实/忙 409，完整性失败 503；这些不能变成“在线/完成”。

## 页面所需读取与操作

前缀 `/api/admin/vision-training`，不复用只限 Mac 本机设备的相机路由闸。

| 请求 | 所需字段与用途 |
| --- | --- |
| `GET /status` | `enabled`, `state`, `reason`, `observed_at`, `active_run_id`, 经核实的单 GPU allowlist；禁用时 GPU/实际运行未知，不列假设备 |
| `GET /datasets` | 不可变 `id`, `manifest_sha256`, `mode`, `class_names`, train/val 样本数；只列测试机受控根中已完整校验版本 |
| `GET /presets` | 已登记本地权重 ID/哈希、与 class mode 兼容的增强 preset、允许 epochs/batch/imgsz/seed 范围；没有客户端路径/命令 |
| `GET /runs` / `GET /runs/<UUID>` | 有界历史、当前 run；`id`, `state`, 创建/开始/结束/观测时间, dataset ID/hash, 实际参数, GPU, `epoch`/total, 同 run metrics/null, 有界日志tail及error, model ID或null |
| `GET /models` | 不可变 model ID, run ID, dataset/hash/mode/classes, 权重SHA/大小, manifest SHA, 创建时间与实际参数；不暴露任意文件读取 |
| `POST /runs` | 仅 frozen dataset ID + manifest SHA、registered weights ID、augmentation preset ID、单 GPU ID、epochs/batch/imgsz/seed、幂等 request UUID、显式确认；一次一 run，第二run busy |
| `POST /runs/<UUID>/cancel` | 显式确认，取消只针对本 run，实际退出前仍 cancelling/busy；不按请求中的 pid 或任意进程组杀进程 |

模型下载/激活属于下一旅程，本页先禁用“下载 · 待授权”，不把源码中的示意参数作为训练输入。不会写公共用户库。

## 权威、完整性、资源与错误

- 数据真值来自已冻结清单及逐文件哈希；复用当前数据集验证规则，两类 `black/white` 与 LED 四类分别固定 class order。字段/数据集未核实时为空，不用0补指标。
- 权重必须检查最终解析的实际本地文件哈希；现有 CLI 同名 `models/` 优先机制不能覆盖服务端已校验路径。缺失或不符立即拒绝，不降级为网络下载。
- 一次最多一个训练进程；GPU 必须预先有经核实的资源预留策略，不能凭当前显存空闲就抢 KataGo。无 GPU/null 不是 CPU/MPS 自动回退，不支持多卡 DDP。
- 运行目录固定 `root/runs/<UUID>`，独立 worker 固定输出子目录；无 shell，无任意客户端字符串参数/URL。日志尾部16KiB，保存上限8MiB，读取历史最多100条；预留磁盘至少1GiB、模型文件最多1GiB。参数 epochs 1–300、batch 4/8、imgsz 640/960、seed 0–2147483647（拒绝布尔值与自动 batch）；真实配置只能缩小这些范围，不能扩大。缺容量/资源证明不启动。
- 冻结输入只读取固定 datasets 根中 `dataset-<64hex>` 的完整最终版本；沿用现有 transfer 的有界路径、逐文件哈希与 dataset schema/YAML/label 验证。验证器提取为纯函数供两个实际消费者复用，不构造虚假相机 coordinator。已冻结目录不得在运行中重写；worker 启动前再次校验清单/文件/权重。
- 每次观察都带 run ID/观测时间，前端串行轮询最多每2秒，选中 run/代际改变后丢弃旧响应。401 回登录；错误有重试读取出口；取消意图不等于已退出。
- 重启不盲目重启训练；未能确认旧进程组退出时保留 interrupted/unknown 与 busy。不能只凭重用 PID 杀进程。协调器仅接受内部 adapter 的本 run 句柄；新进程 `start_new_session=True`，监控线程持有原 Popen，取消只对其仍存活的自建组执行，确认整个组退出才释放。进程身份/存活无法证明时不杀、不释放；重启后不接管孤儿组，需另行人工核实恢复。fake adapter 只能证明本地测试，不代真实验收。
- 完成须成功退出 + 可读 best.pt + 实际 schema + SHA-256 + 训练 manifest 全部实际参数一致，原子发布不可变模型目录；failed/cancelled 保留旧模型，不用 last.pt 或打印文本冒充完成。
- 本机源码核对 Ultralytics **8.4.34**：AMP 检查会加载其他模型、dataset 检查可能下载字体、integration callbacks 含外部平台。独立 Astra 已批准仅 worker 内最小兼容处理：导入前设置 `YOLO_CONFIG_DIR` 到受控 run、`YOLO_OFFLINE=true`、`YOLO_AUTOINSTALL=false`；显式 `amp=False/plots=False`；仅禁用外部 `add_integration_callbacks`，保留默认训练回调；无图模式跳过 dataset `check_font`。不改 ASGI 或用户全局配置，不引入字体 registry。最终本地权重验哈希；固定生成的 YAML 必须拒绝 URL、download 脚本等字段。
- 这些兼容符号限定已核实版本；真实机器版本不同则禁用等待核对。OFFLINE 不是系统级网络隔离保证，不能笼统声称绝无外部网络。关闭 AMP 增加显存需求，Batch 须在真实机器授权验证；实际 amp/plots/workers 等参数纳入 manifest。
- 已实施的额外边界：固定root flock排除第二协调器；GPU ID在导入训练库/torch前锁到`CUDA_VISIBLE_DEVICES`，要求仅一张可见卡，物理/容器映射仍须授权实机核实。8MiB归档满后继续drain并保留最新16KiB尾部；首次取消/终态持久化失败仍可重试，不伪造完成或释放占用。

## Fixture 删除与验收

Fixture 仅演示 unknown/running/failed/completed/cancelled，样例集中在控制器，正式入口不构建；真实 Dashboard 接入并验证诚实空态后删除入口/样例/控制器，纯页面留用。真实 GPU、输入数据回执、取消与模型产物验收均需 Fan 当场授权，fake-worker 不能代表测试机训练完成。
