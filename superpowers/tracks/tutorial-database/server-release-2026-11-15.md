# OGS 视频 Demo：服务器与盒端交接

## 本次边界

本 session 仅将已完成的视频选编投放到正式媒体服务。RK3562 的教程入口、安装及设备验收由另一个 session 处理。本轮不恢复批量制作，不修改正式教材数据库，不重启应用或数据库。

## 固定读取契约

- 发布版本：`ogs-intro-20261115`
- 正式清单：`https://modelstella.com/media/tutorial_demos/ogs-intro-20261115/manifest.json`
- 正式课程：`https://modelstella.com/api/v1/tutorials/ogs-course?lang=zh-cn`
- 同一版本目录中的文件只新增，不覆盖。清单在所有媒体上传并核对 SHA-256 后最后发布。
- `schema_version` 为 `1`。`chapters` / `lessons` 提供前 3 章 54 小节的目录；`playlists` 为稳定 OGS `lesson_id` 到片段 ID 数组的映射。
- `clips` 提供片段标题、来源书、PDF 页码、时长、封面和两档视频。数字片段 ID 仅标识选编内容，不是正式数据库外键。
- 盒端使用 `profiles["kiosk-7-v1"].url`；Galaxy 使用 `profiles["galaxy-4k-v1"].url`。每档带 `bytes`、`sha256`、`width`、`height` 和编码信息。
- `poster_url` 是实际视频帧封面。`source_url` 仅供追溯，客户端播放必须使用正式 `url`，不能回退到 TEST。

## 盒端接入约定

1. 获取正式 OGS 课程，再读取上述清单；按 `lesson.id` 查询 `playlists`。
2. 选中有视频的小节时，按数组顺序播放对应片段；允许重看、返回和继续 OGS 练习。无映射的小节继续保留原有练习入口。
3. 盒端仅点播 1024×600 的 H.264 / AAC 档，不预下载 4K。服务端支持 HTTP Range，播放器应支持拖动和续播。
4. 清单失败时保留 OGS 练习，提供重试；不要将没有视频的小节显示为已有视频。
5. 如需离线演示兜底，可仅缓存 4278、4310、4341 三段，约 2.04 MiB；完整 16 段 kiosk 档为 18.79 MiB。

## 选编范围

16 段不同视频，约 13.2 分钟，覆盖 14 小节。Galaxy 档 77.54 MiB，kiosk 档 18.79 MiB；媒体总计约 96.3 MiB，另有 16 张封面及清单。

精确映射见 [投放计划](demo-deployment-2026-11-15.md) 中的“精确小节和来源清单”。OGS 的全部章节及练习仍以正式课程 API 为准；此次没有声称前 3 章的全部 54 小节都已配置视频。

## 发布验收

服务器媒体投放已于 2026-11-15 完成。

- 正式目标：`ucloud-v100` 的 `tutorial-assets` 桶，公网入口为 `https://modelstella.com/media`。
- 32 份 MP4、16 张封面、1 份清单，共 49 个对象；均以条件创建方式写入，逐项回读核对 SHA-256。未覆盖旧对象。
- 全部 49 个公网地址返回 200，长度和 Content-Type 正确；全部 32 份 MP4 的 Range 请求返回 206。
- 公网清单与本地冻结版本一致。清单允许本机预览 Origin `http://127.0.0.1:18950` 读取。
- 浏览器实际播放并拖动了 kiosk 1024×600 和 Galaxy 3840×2160 两档样例，均可解码；本次短时播放检查未见丢帧。这不替代 RK3562 实机验收。
- 正式健康接口返回 200，原 OGS 课程仍为 7 章、248 小节。服务器 19 个运行容器的 ID、镜像、启动时间和重启次数均保持一致。
- 临时上传目录已清理。批量音视频制作继续暂停。

可直接交给 RK3562 session 的清单本地副本：[production-manifest.json](demo-7inch-2026-11-15/production-manifest.json)。

详细执行回执及公网验证保存在 `output/tutorial-demo-release-20261115/`。本次仅发布服务器媒体与映射清单；课程 API 没有新增字段，Galaxy 页面和 RK3562 的视频入口尚需各自客户端读取清单。盒端接入与设备验收由另一个 session 继续。

## 盒端接入代码交接（后续补齐）

- 分支：`feature/ogs-lesson-videos-20261115`
- 接入提交：`3923a2b5a`；最终 develop：`43f5ef183`（另含构建输出忽略修复）。SmartBox 远端 main：`7605cada`。
- 从章节中的“视频讲解 · N段”进入播放器，支持选段、顺序续播、全屏及原有OGS练习入口；没有视频的小节仍可直接练习。盒端只加载7英寸档。
- 聚焦测试33项、功能文件ESLint及strict Box kiosk构建检查通过；本机1024×600实际播放、全屏显示和进入原练习后落子判定通过。
- 已按用户授权完成同步功能分支、推送 develop、更新并推送 SmartBox main 的子模块指针。RK3562 本次仅发布围棋 kiosk 前端，不更新其他棋类或 Python 后端；不重复上传媒体或导入教材数据库。
- 本机预览：`http://127.0.0.1:18951/output/ogs-video-preview.html#/kiosk/tutorial/chapter/ogs-learning%3AFundamentals`。
- 接入说明位于该分支的`docs/operations/ogs-lesson-video-integration-20261115.md`。本轮隔离worktree为`/Users/fan/.config/superpowers/worktrees/katrain-admin-console/ogs-lesson-videos-20261115`。

## RK3562 实机投放结果

2026-11-15 用户确认只需围棋模块后，停止了尚未进入维护的整应用暂存传输，改为定向发布约44MiB的围棋 kiosk 前端。399个文件全部逐一核对SHA-256，保留旧静态目录用于回退；未覆盖整机版本记录，避免把前端发布误标为整平台升级。

- 设备实际加载新视频入口：第一章“围棋”3段、“棋盘”2段。
- 实际观察到“气”小节第二段4289从正式服务器在线播放，原生1024×600，readyState=4，已解码688帧、音轨337013字节，完整屏幕显示1024×600。当前页面由现场用户选择，检查后未再切换模式或页面。
- 仅发布前端；其他棋类和后端源码未更新。进入原有练习的衔接由此前33项聚焦测试及Mac真实课程运行检查确认。
- 取消的整包临时目录已清理，设备剩余约2.18GiB；视频没有整批下载到设备。
- 回退目录：`/var/lib/smartbox/deployments/ogs-videos-20261115T011408Z-go-frontend/previous-static-kiosk-2d`。
- 本机执行回执、设备截图与最终结果：`output/rk3562-ogs-rollout-20261115/`。最初整包流程的退出码20表示主动取消暂存，不是最终前端投放结果；最终以`final-result.json`的`verified`为准。
