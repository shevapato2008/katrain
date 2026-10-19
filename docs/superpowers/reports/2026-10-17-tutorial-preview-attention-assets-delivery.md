# 教程编号预览、疑点标识及资产归档交付

日期：2026-10-17。范围：TEST；无生产、ucloud-v100、RK3562 发布，无 develop/main 合并。

## 本轮结果

- Console `e4a57c6139e62c28e08b1e224507be93fe67610e`：自动验证静态编号；符合连续、唯一、交替规则时直接开放逐手预览。无编号是合法 0 步；错误给出原因。真实 replay 继续使用规则回放；静态预览不生成缺失提子、不赋予完整手顺或媒体同步资格。
- Console `d2f58fe0a683e168c64e4a54dccb9ced9342b104`：本页、图签、原页图框及右栏显示历史识别疑点。可靠坐标可定位；来源不明时在原候选参考棋盘定位。旧快照具体原因和候选保留，坐标关系不明时保持图级说明。黑白不明不会误报为棋子假阳性或假阴性。
- APP `98a1e438f323e3157cbf3097c914f16332e3b064`：新 `tutorial-gpt-recognition` skill；用户已明确确认。当前 admin-console 工作树的文档提交为 `dc9d1fe5c`。
- APP `d234a16ee040a6288fca64ba53932e71f79e1f9e`：固定资产 `katrain/assets/board-equipment/go/stones/clamshell-slate/v1/`，包含黑白 GLB、来源照片、参数配方、33 张已批准图片、清单与哈希。白子 21.9×8.8 mm、黑子 22.2×9.1 mm；米制、自包含模型。后续样式按棋类／器具／样式／版本扩展。消费者使用单向镜像，不另建资产服务。

以上为本地 feature 分支提交，未声称远端发布或合并 develop。

## Astra Max 审核

- 自动编号预览：SPEC/CODE PASS；编辑模式预览保持只读，返回编辑恢复完整草稿。
- 疑点标识：SPEC/CODE PASS；唯一 P2（legacy 原因和候选遗漏）修复后复核通过。
- 真实 TEST 视觉：page 14 / page 13 两张 2048×1119 截图 PASS。沿用主题、导航、三栏；提示醒目；候选参考不误标当前图；人工审核与预览状态分离。未审新视频需求。
- 固定资产：SPEC/CODE PASS；批准照片、白 GLB 和 33 图片保持原字节，32 白子重新渲染一致；双方模型几何尺寸与封闭性通过。
- 新 skill：前后场景检验通过；明确严格 v2 契约和石田脚本适用边界后 PASS。用户已审核通过。

## 测试与真实页面

最终聚焦前端验证 6 文件 88 测试通过；生产构建成功。此前真实 replay 的 27 项规则测试通过。未为收尾扩大回归范围。

真实测试后台：

- 编号预览：<http://127.0.0.1:18012/admin?book=4&page=12&figure=1032&filter=all>。未点击校验按钮即自动可用；初始 10 子、下一手 11、步骤 3 共 13、末步 20。既有人工审核保留。
- 颜色不明：<http://127.0.0.1:18012/admin?book=4&page=14&figure=1044&filter=all>。原候选全盘坐标 13,2，候选 black/white，显示来源与完整原因。
- 编号推断：<http://127.0.0.1:18012/admin?book=4&page=13&figure=1038&filter=all>。原候选 15,2，推断值 1，依据 combined，保留来源说明。

实际检查：原页可访问、点位与原因双向选择、0 live writes、0 page errors。样例数据／文稿／审核／媒体前后指纹一致。

独立归档检查：33 张批准图片及 manifest 通过；Console 36 个消费镜像文件一致。

## 部署版本

2026-10-17 16:59 后再次只读确认：

- `smartbox-admin-admin-console-1`：running healthy，`smartbox-admin:tutorial-attention-d2f58fe0a683`。
- `katrain-admin`：running healthy，原 `smartbox-admin-go:tutorial-review-a2ee28a70f38`，本轮仅更新 Console。
- 现有 18012 页面返回 `index-CBF4XhR5.js`、`index-Yee6i2us.css`。沿用既有登录会话与入口。

本地私有截图与验证记录：`~/.local/share/smartbox-admin/tutorial-attention-release-20261017/` 和 `tutorial-number-preview-release-20261017/`；不提交会话、密码、部署配置或私有服务信息。

## 后续独立需求

用户要求本轮收尾后，再处理 Galaxy 4K／RK3562 左棋盘右字幕两种 2D 视频、提高贝纹清晰度及移除左上角状态叠字。本交付不声称这些新视频需求已完成。
