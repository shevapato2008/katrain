# 双档 2D 教程视频实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox syntax. Astra Max 决策和独立审查；按用户 AGENTS 比例原则聚焦执行。

**Goal:** 输出能看清批准贝纹材质的 Galaxy 原生 4K 样片及适合 RK3562 7 英寸的左棋盘右字幕样片；用户确认后接入已有测试后台。

**Architecture:** 保留现有完整棋盘、批准 sprites、真实回放帧和音频边界；以两个固定输出 profile 调整录制视图。先只做真实快照前端及本地视频预览，不接新增后端、不更新 DB 媒体、不部署设备。后续复用现有媒体任务和 JSON 元数据，保持版本 CAS 与文件独立审核。

**Tech Stack:** Existing React/Three.js standalone recorder, Playwright screenshots, FFmpeg H.264/AAC; Python preview harness. No AI video model or new TTS/model call.

## 已确认的上下文及决策

- 当前实际链路：`media_render.py` 为 1280×800/15fps/CRF20；`TutorialMediaRecorder.tsx` 将 tm-static 状态烧进视频；固定字幕区116px和最大宽1100px不适合4K。
- Astra Max 已核实RK项目规格1024×600。推荐 Galaxy棋盘约1880px、底部240px字幕72px；RK左576px棋盘、24px间隔、右400px字幕28px/42px。
- Astra Max计划审核PASS；字幕沿用现有本地Noto Sans SC。若1030输出短段，记录来源start/end，画面／字幕／落子音与语音按同一绝对时间区间统一裁切；原source_audio_sha与样片文件SHA分开记录。
- 使用原生 viewport 与DPR1，不将1280成片上采样；棋子33个批准PNG保持字节不变（256px大于4K完整盘中约81px白子）。随机角度、黑白尺寸比例、数字正向、提子规则、360ms轻落子与低音量接触音保留。
- 4K:3840×2160/30fps/H.264/yuv420p/CRF16/medium；RK:1024×600/30fps/CRF18/medium。实测文件大小和耗时，保留有界超时，不声称4K必然很小或已通过RK硬解实测。
- 正式画面不含左上校准说明、已去掉的范围框及灰色遮挡；状态在播放器外说明/元数据中保留。
- 样片数据只用今日已授权并验收的1030/1031快照，保留哈希及来源时间；原音频核对哈希后复用。1030真回放，1031pending仍静态，不编造cue。

## Chunk 1：前端和可播放样片（当前阶段）

### Task 1: 录制视图

**Files:**
- Modify `katrain/web/ui/src/pages/TutorialMediaRecorder.tsx`
- Modify `katrain/web/ui/src/pages/tutorialMediaTimeline.ts` (optional fixed output_profile type)
- Modify `katrain/web/ui/src/pages/tutorial-media.css`
- Test `katrain/web/ui/src/pages/TutorialMediaRecorder.test.tsx`

- [x] 现有 RecordingData 可选 `output_profile: galaxy-4k-v1 | kiosk-7-v1`，默认既有布局兼容。有效profile明确映射CSS属性，不能由任意用户CSS/URL注入。
- [x] 新版2D画面删除tm-static烧录；绘制状态仍以snapshot/cues为准。RK固定横向左棋盘右字幕，边距、笔画随尺寸，30字字幕不裁切。Galaxy居中全盘、下方字幕。无新增页面导航或3D入口。
- [x] 聚焦检查两个profile布局语义、无状态叠字、pending最终静态图不变、既有真实时间线/标记及纹理等待保持；运行现有recorder/timeline聚焦测试与build:tutorial-media。

### Task 2: 本地渲染与视觉预览

**Files:**
- Create isolated `katrain/web/ui/preview/tutorial-video-profiles/` (preview index/README if needed)
- Local private snapshots/audio/results under `~/.local/share/smartbox-admin/tutorial-dual-video-preview-20261017/` (not Git)
- Preview harness can be `scripts/preview_tutorial_video_profiles.py` if a reusable script materially simplifies existing renderer use; otherwise local driver only.

- [x] 用真实快照驱动现有隔离录制器，所有图片/字体本地；先原生4K静态首样核对，再用1030落子样片核对WebGL drawingBuffer和截图分辨率。超时继续有界，失败不覆盖已有产物。
- [x] 输出1031两版完整25.44s样片，并为1030完成含轻落子/真实cue的短段验证；性能允许时输出1030两版完整42.24s，仍只一页图、不全书批量。
- [x] FFprobe核对分辨率/FPS/codec/时长/音轨；保留音频哈希、耗时、字节数和无API写证明。字幕跟原音频边界，不重新生成语音。
- [x] 提供原生4K截图、白子局部100%像素对照、RK1024×600截图与可播放页面，页面无需后台新登录，不冒充已部署媒体。
- [x] Astra Max先SPEC后CODE再视觉聚焦审核，修复实质阻塞；用户确认样片后才开始Chunk2。

## Chunk 2：现有测试后台接入（用户于 2026-10-17 明确确认样片）

### Task 3: 固定双profile任务与独立审核

**Files to confirm:** `katrain/web/admin/routers/tutorial_media.py`, `tutorials/media_tasks.py`, `media_render.py`, `manual_review.py`, existing models/output schemas, console workbench media cards/client/types; Galaxy/kiosk existing consumers.

- [ ] 保留render_mode=2d，output_profile进入任务快照、去重digest、artifact标识；现有workbench_media.videos JSON保存两版，video_2d_review JSON按profile保存文件绑定审核，兼容历史单文件记录，不新建表。
- [ ] 每版自己的asset/hash/配方版本/审核；重生成一版只撤销该版视频审核。图文编辑按现有依赖失效；完成任务核对内容版本，陈旧结果不绑定新内容。
- [ ] 后台可独立生成/播放/确认两版；Galaxy默认4K全屏实际原生、RK取设备版，播放器外显示pending原因。未知/不支持profile明确拒绝，不默默回退为低清。
- [ ] 聚焦CAS/去重/双版互不覆盖/审核失效/重试，真实测试环境一页生成验证；只部署必要TEST容器。生产和RK部署不在本阶段授权范围。

## 交付顺序

先交当前任务（已完成并记录62beebc7a）→ 原生双档可视样片 → 用户视觉确认 → 新后端集成。样片技术审核与管理员内容人工审核分别报告，不代为新增人工通过记录。


## Chunk 2 最小确定契约（Astra Max 决策）

- `workbench_media.videos["2d"]` 保留旧artifact字段，新增 `profiles` 映射；`video_2d_review` 同样保留旧record字段并新增profiles。两键固定：`galaxy-4k-v1`、`kiosk-7-v1`；旧读取/摘要必须剔除profiles，保证相互独立。3D只读历史保持。
- POST media-tasks增加可选output_profile，新video省略时归一Galaxy4K。存入snapshot/任务digest/输出/产物参数与recipe版本。旧snapshot无profile保持legacy，不冒称4K。audio不引入视频profile依赖。
- PUT approve-video显式profile选择精确artifact与review；旧请求省略仅按expected_asset精确匹配legacy或Galaxy，不隐式审核RK。review_validity保留video_2d legacy键，增加video_2d_profiles映射。单档审核摘要不含整个容器/另一档。
- 发布figure锁下合并最新JSON，只替换当前profile并清除该档review，保留另一档、历史审核与棋图审核。内容依赖不含其他视频，图文/音频/棋图审核依据变化仍stale。仅Galaxy发布改兼容video_asset/duration/size；RK不改。图文编辑/重生成音频继续按现有规则撤销依赖媒体。
- 公共section与figure响应加筛选的video_profiles（asset、尺寸、duration、playback/timing状态），及video_output_profile说明兼容video_asset是Galaxy还是legacy；不加DB列，不暴露审核人员。board proxy原样透传即可。
- Galaxy选择Galaxy档，kiosk选择RK档，缺少所需档显示尚未生成。旧文件明确历史，不冒称4K，不让RK自动加载Galaxy文件。
- kiosk点击看视频进入占满视口的播放层，复用现有video组件，有44px以上“返回棋图”按钮；保持原浏览布局与导航。避免成片再缩入原516宽棋盘槽导致字幕缩水。播放器外说明保留pending，不烧入视频。

### Task 3a：后端分档契约和原生renderer

**Files:** `katrain/web/tutorials/media_profiles.py`（最小固定配置与artifact/review选择）；`manual_review.py`、`media_tasks.py`、`media_render.py`、`admin/routers/tutorial_media.py`、`tutorials/models.py`、`api/v1/endpoints/tutorials.py`；仅必要处关联`db_queries.py`。不改DB表。

- [x] 针对profile去重/旧snapshot、两档独立发布/审核、legacy摘要兼容、内容变更stale写聚焦测试。保留CAS、错误与审计事务，非法/3D profile拒绝。
- [x] renderer按固定profile设置原生viewport/DPR1、FPS30、CRF16/18、medium；注入已确认output_profile，核对最终尺寸codec/时长，保留600s与进程组清理。有限编码线程，匹配已验证样片，不改素材/时序/音量。
- [x] 两个公共读接口输出安全摘要并注明实际profile；不足档位不静默伪装。profile版本进入artifact，清楚记录width/height/fps/renderer_recipe。
- [x] 独立Astra Max先SPEC后CODE聚焦通过，再交付前端对接固定契约。

### Task 3b：后台与消费者最小集成

**Files:** Console `admin/api/client.ts`、`tutorials/workbench/types.ts`、`WorkbenchContainer.tsx`、`TutorialWorkbench.tsx`（必要时抽现有媒体卡，仅为本需求）；APP `types/tutorial.ts`、`galaxy/pages/tutorials/TutorialFigurePage.tsx`、`kiosk/pages/TutorialSectionPage.tsx` 和现有共享video组件/样式。

- [ ] 后台沿用一张视频卡，固定档位选择“Galaxy · 4K”“RK3562 · 7英寸”；生成/任务状态恢复/播放/审核都对应当前档，旧2D/3D历史只读。各档审核状态不串用。
- [ ] Galaxy原生4K媒体选择与全屏controls；RK明确设备版且点击后全视口播放，有返回。无新registry/表/模拟业务数据。
- [ ] 聚焦前后端profile传递、切档状态、独立审核及消费者选择测试；代表性真实页面预览，Astra Max代码审查与实际视频/布局复核。

### Task 3c：TEST发布与真实一页验收

- [ ] 只更新home-ubuntu TEST provider+console；普通Galaxy/kiosk消费者前端只做本地构建与测试API验证，当前admin provider不承载其页面；守卫现有TEST标志、DB system_identifier7596941912817897507、s3/tutorial-assets及go.sailorvoyage.top/media。不重启DB/MinIO/GPU/web/cron或触碰ucloud/RK设备。
- [ ] 发布前无running/queued媒体任务；备份仅必要图/审核/媒体指纹与当前容器配置，保持原env/session密钥/ports/networks/mounts，保留回滚镜像。严禁打印秘密配置。
- [ ] 使用现有已登录浏览器与已有1030/1031棋图审核，生成四视频。原图/文稿/人工棋图审核不变，媒体新记录准确，视频人工审核待用户点，不代为登记。
- [ ] 每视频下载验证SHA、FFprobe、实际浏览器播放；真实后台切档/刷新仍保留。报告新提交/TEST容器版本、实际链接与明确未发布边界。
