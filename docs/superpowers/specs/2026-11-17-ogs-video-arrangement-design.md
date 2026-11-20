# OGS 248 小节视频编排

用户已确认沿 OGS 现有七章、248 小节，采用“先视频讲解，再做本节 OGS 练习”。2026-11-17 本轮指令为开始逐节选编、排序和配置；沿用已验收的播放器，不重新设计课程 UI。

## 本轮结果

- 为每个稳定 lesson ID 给出有教学依据的有序片单、简短导读、练习衔接说明、来源和时长。
- 使用已生成的 1,931 幅清晰素材。15 个来源/校准/非实体排除项不参与选片。保留既有 14 节演示的选片与顺序作为基线。
- 根据具体练习说明区分同名小节；按照“概念/方法 → 例图/反例 → 进入练习”组织。通常选 1–4 段，优先相邻而连贯的书中例图；数量和时长服务于本节目标。
- 原视频有跨图引用时，补齐其前置例图或改选独立例图。不能仅按页码或关键词机械选片。不能把某片“存在”当成知识点已覆盖。
- 对既有提纲中需补充的终局操作、等待手、连续扑等目标，先检索当前全部成品。若仍只能覆盖原理，准确标注视频与 OGS 练习各自承担的内容，提供有原始 OGS 依据的文字导读；不伪称已有完全对应的视频。

## 数据与交付

1. 轻量素材索引：当前讲稿、原书描述、PDF 页码/图号、源指纹、时长、两档资产；只读 TEST 一次，不重复提取语音时间戳和识别历史。
2. 章节作者输出互不重叠的 JSON。每个小节含 `lesson_id/course_code/goal/intro/practice_bridge/clips/coverage_notes`；每个 clip 含 `figure_id/role/focus/rationale/source_unit`。时长和资产 URL 由统一索引计算，不由作者猜测。
3. 汇总形成 248 行 HTML/CSV/JSON 审查表，可按章/关键词查看，显示片序、用途、书名、PDF 页码、图号、Admin 原图链接、时长，并能预览 4K 或 7 英寸版本。
4. 生成版本化 TEST manifest；配置全部 248 个小节。使用现成不可变 TEST 资产 URL，不重新编码、不复制视频到盒子。
5. 复用现有播放器做隔离的 TEST 数据预览，视频与练习均指向 TEST。优先使用本机隔离预览服务和现有匿名只读 TEST API；不替换当前 Admin 静态文件、不改生产或 RK。

## 最小接入边界

已部署播放器的基线为 `43f5ef183`。当前默认固定 PROD manifest 且严格校验旧目录；本轮仅增加受信任的 TEST 构建配置，保留 PROD 默认约束。TEST 资产 URL 只允许配置的 TEST origin 和规范化 `/media/tutorial_assets/` 路径；不接受查询参数指定 origin、凭证、路径穿越或任意代理。TEST 海报可选，沿用现有海报或视频自身，不另造整套图片。

现有 Admin 没有片单编辑 API/UI，本轮使用版本化配置，不新建编辑器。现有播放器为 kiosk；审查表同时提供已生成的 Galaxy 4K 资产，但不把本轮称为 Galaxy 课程 UI 改造或已部署到设备。

## 验收

248 个 ID 与 OGS 目录精确一致、每节非空、片序内无重复；每个引用均来自当前完成索引且具备两档。既有 14 节基线不被静默改变，15 排除项不被引用。每节有具体选片理由和原书出处；不足有明确说明。只运行相关数据验证、已有播放器受影响的测试及代表性真实 TEST 预览。不生成新音视频、不调用 Astra 媒体审核、不写人工审核字段、不发布 PROD/RK。


## Verified implementation adjustments

The TEST image does not expose the public OGS reader found in current source code. The isolated preview therefore serves pinned exports of actual TEST book80 course/step data, with DB identity and SHA validation, and uses the existing pure kiosk board adapter. It does not impersonate an authenticated box or modify production guards. Only the preview entry bypasses the product shell, because its data is the public course contract; no Admin credential is exposed. The review table uses a fixed manifest allowlist streaming route for TEST video playback; this introduces no stored video copy or general-purpose URL proxy. Production/RK deployment is unchanged.
