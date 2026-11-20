# Report card charging — 展示增量代码审核

**结论：Approved。** 本次展示增量符合用户确认的三项要求，没有阻塞合入的实质问题。

审核范围：`18d20c1ad..4861c6200`，产品提交 `4a1e63dff`、`4861c6200`。先按 `docs/superpowers/plans/2026-11-14-report-card-charging.md` 核对规格，再检查实现、相关状态模型与聚焦测试；此前已通过的访问引导弹窗未重复审核。

## 规格与实现

- 共享 `ReportProgressColumn` 从既有 `presentReportTier` 取值，仅保留 `running` 档位；单档只占一行，双档占两行，无运行返回 null。100% 不作为结束条件，直到任务状态变为 completed 才收起。
- Galaxy 与 Kiosk 均使用绿色横向充电填充、百分比和运行扫光，保留 reduced-motion。填充宽度、可见百分比及 aria 数值来自同一值；已删除圆环结构和专属 CSS。
- 两端外部行也使用同一 running 判定：运行时保留原 126px / 120px 进度列，无运行时改为 `minmax(0, 1fr)` 且 gap 为 0，避免组件返回空后仍留下空位。该判断不依赖选择卡片或打开菜单。
- pending 的进度列虽隐藏，卡片仍明确显示“排队中”；Kiosk 的运行与排队混合状态同时保留两种反馈。状态判断与 `rowState` 的活动任务优先级一致，没有被已完成档位遮盖。
- Galaxy 黑棋手在左、白棋手在右，中间为结果与总手数；来源/星阵、标题、日期、段位、选中样式和 Enter/空格选择均保留。长名字有截断和完整 title，卡片高度继续为 104px。
- Kiosk 继续使用 `RecordMatchLine`，仅历史卡传入可选 detail，在结果区显示手数并移除表头重复手数；74px 高度不变。棋谱库未传入 detail，其既有布局不变。
- 改动局限于展示组件、CSS 与对应测试，没有修改业务 hook、请求、轮询、进度计算、计费或后端。

## 验证

审核者独立运行：

```text
npm run test -- src/features/report/ReportProgressColumn.test.tsx src/galaxy/components/report/ReportGameCard.test.tsx src/galaxy/pages/report/ReportsPage.test.tsx src/kiosk/pages/ReportsPage.test.tsx src/kiosk/pages/ReportsPage.polling.test.tsx
Test Files  5 passed (5)
Tests       120 passed (120)
```

`git diff --check 18d20c1ad..4861c6200` 通过。测试覆盖非运行档位隐藏、单/双档运行、100% 保留、排队文字、两端卡片状态、棋手/手数结构、键盘选择及真实 hook 的轮询状态转换。

实现保持局部、直接，没有需要扩大本次展示范围处理的建议。两端构建与目标尺寸真实视觉预览由主代理执行，本审核不重复；未修改产品代码、连接设备、推送或部署。

主代理补充验证：Galaxy与严格Kiosk生产构建均通过；1920×1080 Galaxy真实卡片组件、1024×600 Kiosk复用卡片/实际新弹窗预览已检查。无运行卡片552/752px全宽，运行列126/120px，黑白棋手左右、结果和手数居中；弹窗文案与48px按钮可读。预览使用隔离fixture与既有页面背景，非真实任务运行验收；未为截图创建付费任务。参考截图与实现同尺寸检查仅关注本次三项变更，不改其它页面构图。fixture在发布前删除，截图保存在ignored output/playwright/。
