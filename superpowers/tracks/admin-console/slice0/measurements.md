# 切片 0：教程页只读右栏承重实测

- 日期：2026-09-24；真实 Chromium，目标 viewport 1440×900；本地 Vite 127.0.0.1:5183，API 用 Playwright 路由 Fixture。
- 测量脚本按计划为一次性脚本；为避免误拦 Vite 的 `/src/api/live.ts`，兜底匹配从 `**/api/**` 收窄为 `**/api/v1/**`。三态全部通过，因此按计划删除临时脚本。
- 证据：[非管理员＋溢出](nonadmin-overflow-1440x900.png)、[非管理员＋最空](nonadmin-minimal-1440x900.png)、[管理员对照](admin-overflow-1440x900.png)。截图仅供 Fan 确认，不代表视觉验收通过。
- 本地未启动后端，顶部 logo 图片与翻译接口回退/加载失败；三张截图里可见的破图属于预览环境限制，不影响右栏几何与滚动判定。

| 状态 | shell top/bottom | rail top/bottom | module bottom | scroll top/bottom | scrollHeight/clientHeight | actions top/height |
| --- | --- | --- | --- | --- | --- | --- |
| 非管理员＋溢出 | 52 / 900 | 52 / 900 | 111.46875 | 111.46875 / 900 | 6048 / 789 | 900 / 0 |
| 非管理员＋最空 | 52 / 900 | 52 / 900 | 111.46875 | 111.46875 / 900 | 789 / 789 | 900 / 0 |
| 管理员对照 | 52 / 900 | 52 / 900 | 111.46875 | 111.46875 / 775 | 6069 / 664 | 775 / 125 |

- R1（三态）：rail 与 shell 的上、下边缘差均为 0 px，≤1 px，通过。
- R2（两种非管理员态）：actions 高度 0 px；scroll 下边缘＝rail 下边缘、上边缘＝module 下边缘，差均为 0 px，通过。
- R3（非管理员＋溢出）：6048＞789；将 scrollTop 写为 1e6 后读回＞0，重置后滚轮滚动读回＞0，通过。
- R4（管理员）：actions 高度 125 px＞0；scroll 下边缘＝actions 上边缘（775 px），通过。

结论：本次测量的几何关系与滚动行为均符合计划。等待 Fan 检视三张截图与结果，明确确认后才能进入 Task 6。
