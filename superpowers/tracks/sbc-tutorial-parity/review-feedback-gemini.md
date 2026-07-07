# Gemini 对 Kiosk 教程模块开发计划的审核反馈

> Track: `sbc-tutorial-parity`
> Reviewer: Gemini
> Date: 2026-06-28

总的来说，这是一个非常出色和周密的开发计划（`plan.md`），与 PRD（`prd.md`）高度对齐。计划的阶段划分清晰、风险识别到位、验证步骤严谨，特别是对 kiosk 构建边界和回归测试的重视，为项目成功奠定了坚实基础。

以下是在肯定的基础上，提出的一些旨在进一步优化和规避潜在风险的建议。

---

## 1. 整体评价 (Overall Assessment)

**优点 (Strengths):**
- **结构化规划**: 7个 Phase 的划分逻辑清晰，每个阶段都有明确的目标和可验证的产出，降低了集成风险。
- **风险驱动**: 计划明确响应了 PRD 中识别的所有风险（R1-R5），并将缓解措施融入到具体的执行阶段。
- **严格验证**: 每个 Phase 都包含详尽的 `Verification` 步骤，特别是对双构建、`verify:kiosk-2d` 脚本和 E2E 测试的强调，确保了交付质量。
- **技术可行性**: "共享下沉"的架构决策正确且必要，解决了 kiosk 的构建约束。前端解析 `book slug` 的方案巧妙地避免了后端改动。

---

## 2. 存在的问题与优化建议 (Issues & Optimization Suggestions)

### 2.1. [中优先级] Phase 4 - 数据加载存在性能瀑布 (Data Fetching Waterfall)

- **问题**: `plan.md` 和 `prd.md` 都描述了在“章/节树页” (`TutorialBookDetailPage`) 需要先获取书籍信息（含章节列表），然后**对每一章**再单独调用 `getSections(chapterId)` 来获取节列表。这会产生一个 `1 + N` 的 API 请求瀑布，其中 N 是章节数。如果一本书章节很多，页面加载会很慢。
- **建议**:
    1. **短期优化 (并行化)**: 在前端，使用 `Promise.all(chapters.map(ch => getSections(ch.id)))` 来并行获取所有章节下的节列表，而不是串行循环。这能显著改善加载时间。请在 `Phase 4` 的任务描述中明确这一点。
    2. **长期建议 (后端优化)**: 虽然本次是纯前端任务，但建议为后端创建一个技术债 issue，提议在 `GET /api/v1/tutorials/books/{bookId}` 接口上增加一个查询参数，如 `?include=sections`，以便一次性返回完整的书-章-节三级树状结构，从根本上解决性能问题。

### 2.2. [中优先级] Phase 1 - 类型不一致引入技术债 (Type Inconsistency)

- **问题**: 计划中敏锐地指出了 `SGFBoard` 自带的 `SGFPayload` 接口与共享类型 `src/types/tutorial.ts` 中的 `BoardPayload` 存在定义重复。计划决定“本期不强行统一类型，保持迁移最小改动”，这是一个务实的短期决策。
- **建议**:
    - **明确跟进**: 同意此决策以控制本期范围。但为了避免技术债被遗忘，建议**立即创建一个 follow-up ticket/issue**，并将其 link 到本 track，计划在未来版本中将 `SGFPayload` 收敛到统一的 `BoardPayload` 类型。

### 2.3. [低优先级] Phase 5 - 页面状态在刷新后丢失 (State Loss on Refresh)

- **问题**: 计划建议在 `TutorialSectionPage` 中，为了面包屑导航，将书名和章名通过 `react-router` 的 `state` 从上一页传入。这在用户正常点击跳转时工作良好，但如果用户**刷新页面或直接通过 URL 访问**，`state` 会丢失，导致面包屑不完整。
- **分析**: 计划中已将此问题标注为“可接受的简化”，这在当前需求下是合理的。
- **建议**:
    - **增强鲁棒性**: 可以在 `TutorialSectionPage` 中增加一个逻辑：如果 `location.state` 不存在，可以考虑从 `section` 数据中向上追溯（如果 API 提供了 `section.chapter.book` 类似结构），或者退而求其次，仅显示当前节的标题，并隐藏不完整的面包屑，而不是显示 "undefined ▸ undefined ▸ 节标题"。这能让直接访问的用户体验更好。

### 2.4. [低优先级] Phase 4 & 5 - 组件抽象与复用 (Component Abstraction)

- **问题**: 计划将创建多个页面 (`TutorialCategoriesPage`, `TutorialBooksPage`) 和组件 (`FigureThumb`, `FigureDialog`)。这些组件和页面可能共享通用的布局和状态管理逻辑（如加载中、错误、空状态）。
- **建议**:
    - **鼓励抽象**: 在实施 `Phase 4` 时，可以考虑创建一个可复用的 `CardGridPage` 或 `ResourceList` 布局组件，用于统一处理 API 加载逻辑和卡片网格的展示。
    - **明确 `FigureThumb` 职责**: `FigureThumb.tsx` 的核心是渲染一个**非交互式**的缩略棋盘。建议其 `onClick` 事件直接由父组件 `TutorialSectionPage.tsx` 注入，自身不处理弹窗逻辑，保持组件的展示性（Presentational）。

### 2.5. [澄清点] "可选功能" 的实施决策 (Clarification on "Nice-to-have" Features)

- **问题**: PRD 和 Plan 都提到了一个可选功能：在 `FigureDialog.tsx` 中“可选展示 `figure.narration` 文本 (read-only)”。计划中没有明确是否要在本期实现。
- **建议**:
    - **做出决策**: 在正式开工前，需要团队明确此功能是否包含在本期交付范围内。
    - **同步更新验证**: 如果决定实现，`Phase 5` 的 `Verification` 步骤和 `Phase 7` 的 E2E 测试用例都需要补充对此功能的验证。如果决定不做，应从 `Phase 5` 的任务描述中移除。

---

## 3. 总结 (Conclusion)

此计划非常出色，上述建议旨在精益求精。实施团队可以按计划推进，只需在对应阶段开始前，针对上述建议点稍作澄清和微调即可。

**建议操作：**
1.  **接受计划**，采纳以上建议并对 `plan.md` 进行微调。
2.  在 `Phase 4` 明确使用 `Promise.all` 进行数据加载。
3.  为类型统一和后端 API 优化创建两个新的技术债 `issue`。
4.  明确 `narration` 的显示是否在本期范围内，并更新计划和测试用例。

做得很好！期待看到这个功能的上线。