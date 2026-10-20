# 黑白碁石模型预览：Astra 独立审核

日期：2026-10-17。范围仅 `katrain/web/ui/preview/shell-stones/` 五个隔离文件及本地预览产物。

## 结论

**SPEC / 视觉 PASS → CODEQUALITY PASS。发现的一项 P2 已修复并完成窄复核，无未关闭的 P1/P2。** 本报告不代表用户已经确认完整模型，也不授权应用到后台。

## 实际视觉与规格检查

已用独立浏览器在 1280×800 检查当前预览，并实际查看截图及厂家 / 模型 / 50% 叠加对照。

| 检查项 | 结论与证据 |
| --- | --- |
| 配套比例与几何 | PASS。白 21.9×8.8mm、黑 22.2×9.1mm；俯视呈圆形，侧视为上下对称双凸，边缘圆润。物理比例按厂家说明保留。 |
| 白石材质 | PASS。珍珠白、克制的斜向近似平行贝纹，有明暗与曲率；没有浓黄或年轮纹。材质为原创程序纹理。 |
| 黑石材质 | PASS。黑色保留柔和宽高光，没有金属感或繁杂镜面倒影。最新版本阴影已柔化。 |
| 小尺寸可读性 | PASS。浏览器实测各组直径分别为 24 / 32 / 48 CSS px；两行互换黑白的双位数字、字母、三角、方形、叉号、末手圈均可辨。此等径样张用于可读性检查，不改变模型的黑白实物比例。 |
| 交互与页面 | PASS。俯视 / 斜视 / 侧视、拖动旋转、深浅背景与重播均可操作；目标视口无横向或纵向溢出。落子示例为 360ms 单调收束，无回弹。 |
| 参考和范围 | PASS。已查看用户星阵截图及厂家参考；修正后的对照页页脚正确显示白石贝纹与黑子剪图。素面白石对照使用相同新几何及普通材质，不是旧 UI 的完整复制。 |
| 隔离与后续方向 | PASS。正式入口没有导入预览模块；浏览器只请求本地 JS / CSS / favicon，无 API 或外网请求。页面明确等待视觉确认，后续用于静态棋盘及俯视 2D 视频。 |

## CODEQUALITY：已关闭的 P2

首轮 `preview.ts:118-124` 创建第二个 `WebGLRenderer`，却把首个 renderer 在第 31 行生成的 PMREM render-target texture 用作其环境纹理。GPU render-target texture 不能跨 WebGL context 共用。本地 Three 源码确认每个 renderer 的 `WebGLProperties` 独立，`WebGLTextures.setTexture2D` 对 render-target texture 不重新上传，因此第二上下文没有该环境纹理。

原影响：小尺寸样张及导出的 sprites 缺少主模型的环境照明，不能作为与主模型相同灯光条件下的 2D 材质基准。

修复：当前 `preview.ts:117-176` 使用同一个 renderer，在动画循环启动前临时设为 DPR=1、256×256 输出 sprites，再恢复原 DPR 和主视口。主模型灯光、材质参数及其他交互没有改变。

独立窄复核：重新加载实际 `index-122UBzpN.js`，查看更新后的 1280×800 页面及小尺寸棋子，确认页面仍无溢出、无 WebGL 错误；核对同一 renderer 的源码路径。重新导出的 `stone-*.png`、`sprites.json` 已更新，再加载并实际查看材质对照页，当前白石和黑石表现通过。没有重复已通过的三视图和背景全状态检查。

其余五文件审查没有发现需要修复的 P1/P2。固定种子、平面 UV、非金属且不透明的材质、独立 Vite 输出目录均与计划一致。

## 证据与限制

- 预览：`http://127.0.0.1:9035/site/`；对照：`http://127.0.0.1:9035/materials-comparison.html`。
- 独立截图位于 `output/shell-stones-20261017/`：最终主视图 `astra-top-final.png`、最终对照页 `astra-comparison-final.png`；首轮三视图证据另有 `astra-top.png`、`astra-side-dark.png`、`astra-oblique-light.png`。
- 首轮实际加载 `index-BgSmOUPd.js`，关闭 P2 后实际加载 `index-122UBzpN.js`。浏览器没有 WebGL 错误；PMREM blur samples 的 clipping warning 及首轮 favicon 404 不阻止当前本地预览，不据此扩张实现范围。
- 未运行全量测试；没有部署、生成视频、写库或变更生产入口。
