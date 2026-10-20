# 实拍蛤碁石模型 — Astra Max 聚焦审核

日期：2026-10-17。范围：`katrain/web/ui/preview/photo-shell-stones/` 的独立本地预览；无生产／TEST 后台接入、数据库写入或视频生成。审核人未修改实现、未提交代码。

## 结论

**SPEC／实际视觉 PASS；CODEQUALITY PASS。未发现本范围内实质 P1/P2。** 可以将当前具体效果交给用户确认，**不代表用户已满意或已批准接入**。

这是把照片纹理贴到尺寸近似的闭合双凸几何上的模型，**不是实物三维扫描，也不是由照片测得的真实表面高度或材质参数**。照片版为默认，AI 衍生版只作显式对照。

## 实际视觉与来源

- 在独立浏览器实际打开 `http://127.0.0.1:9035/photo-model/site/`，查看俯视，并查看同轮斜视／侧视运行时截图。纹路的疏密、粗细和轻微弯曲来自照片，未见重新生成的规则程序条纹；没有黑底、字幕或两块强反光混入模型表面。
- `source-photo.jpg` 与下载的厂商 `snow-stripesample-01.jpg` **逐字节相同**。UV 的 offset/repeat 对应 2339×2356 原图中央 `x=700..1650, y=450..1400`，与页面取样框一致；没有图像补绘。该照片仍带自身亮暗，页面没有将其宣称为经测量的纯反射率贴图。
- 原图与模型并列，厂商来源可追溯：[黑木碁石店产品页](https://kurokigoishiten.com/en/products/clamshell-go-stones-premium-snow-grade)。页面明确标注照片贴图／近似几何、非扫描、本地预览及再分发许可未明确；此审核不授予素材商用许可。
- 在 1280×800、DPR 1 下读取并观看实际 **24／32／48 px** 样本，三组各五种朝向，尺寸声明真实。48 px 的天然纹路较易辨认；24 px 仍柔和，不能宣称细节十分清楚。数字和三角符号保持正向且可读。没有用放大模型的观感替代小尺寸判断。
- 实际点击 AI 对照后，按钮、三组样本标题和说明同步变为 AI 模式；说明明确“部分细节已重建，不等同原照片”。默认选中照片模式。

实际观看证据：

- `output/playwright/photo-shell-actual-size.png`、`photo-shell-samples.png`。
- `output/shell-stones-20261017/photo-model/model-photo-oblique.png`、`model-photo-side.png`。

## GLB 与代码

已检查预览 TypeScript、HTML/CSS、独立 Vite 配置及实际 `output/shell-stones-20261017/photo-model/clamshell-photo-preview.glb`。GLB 为 glTF 2，2,802,108 bytes；POSITION 边界为 X/Z ±1、Y 约 ±0.40182647，节点统一缩放 0.01095，故直径 **21.9 mm**、厚度 **8.8 mm**。Y 平移 0.0044 m 令下端接近零平面。实际导出包含原照片贴图及取样变换，metadata 记录来源、照片模式、尺寸和 local-preview 使用范围。

预览复用现有闭合几何与 studio；样本由同一 renderer/context 渲染，避免跨 WebGL context 共用 PMREM。不同朝向旋转模型，标记独立覆盖。素材从本地 bundle 加载，下载按钮仅导出本地 GLB；独立构建输出未接入后台或录制入口。

本轮未增加测试层、未重复既有媒体流程审核。加载、样本和模式切换正常；既有 PMREM 采样警告与本地 favicon 404 不阻塞预览。结论仅为当前本地模型的可审阅性、来源诚实性和实现正确性，最终外观选择保留给用户。
