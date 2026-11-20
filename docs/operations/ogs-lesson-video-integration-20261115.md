# OGS 小节视频入口接入

分支：`feature/ogs-lesson-videos-20261115`，基于 `develop` 的 `f16869c9e`。本轮补前端接入，不操作 RK3562，不恢复音视频生产。用户确认预览后，由负责整合发布的 session 合入 develop、更新 SmartBox 子模块并上板；代码提交不表示已经合入或部署。

正式清单：`https://modelstella.com/media/tutorial_demos/ogs-intro-20261115/manifest.json`

16 段视频覆盖 14 个 OGS 小节；盒端只使用 `kiosk-7-v1` 的 1024×600 MP4，不下载 4K。课程和题目判定树没有改写。

## 用户路径

- `/kiosk/tutorial/chapter/:chapterId` 中，有视频的小节显示“视频讲解 · N段”，进入 `/kiosk/tutorial/lesson/:lessonId/videos`；无视频仍直接进入原练习。
- 播放页支持选段、顺序续播、全屏、重试和进入练习，显示原书/PDF页及普通话音轨说明。离开页面暂停播放器。
- “全屏播放”配合屏内兼容显示，原生 API 不可用时仍显示完整 1024×600；可退出，全段结束后返回普通布局。
- 清单失败或12秒超时可重试，仍可做练习；播放失败也能直接进入练习。
- 视频按需读取且 `preload=metadata`。不在盒端打包或预下载整套媒体，不读取 TEST 视频地址。

## 验证

- 聚焦 Vitest 33 项通过：有/无视频、错误恢复、原练习判定衔接、切段、兼容全屏和只读契约。
- 功能文件 ESLint、TypeScript 及 `build:smartbox-kiosk-2d` 通过；strict Box SSO / 无 Galaxy及Three.js构建边界检查通过。
- 1024×600 浏览器实际读取正式课程、清单、MP4，完成播放与拖动；展开播放器实测为1024×600。视频进入原练习后，实际棋盘落子判定正确，播放器已卸载。
- 同尺寸截图与RK原目录对照：保留左248px章节栏和右侧两列课目，只新增视频数量标识。预览顶栏为隔离容器，正式构建仍使用原外壳。
- 截图、并排图及叠加图：本worktree `output/ogs-video-integration-20261115/`。临时预览在`katrain/web/ui/output/`，未进入生产构建。

本机预览：`http://127.0.0.1:18951/output/ogs-video-preview.html#/kiosk/tutorial/chapter/ogs-learning%3AFundamentals`

尚待完成：用户视觉验收、合入 develop、SmartBox 子模块更新、RK3562安装和实机解码/声音验收。不能将代码完成说成已经上板。
