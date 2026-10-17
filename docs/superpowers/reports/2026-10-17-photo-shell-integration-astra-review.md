# 照片蛤碁石素材接入 — Astra Max 聚焦审核

日期：2026-10-17。范围：用户已批准照片模型的 32 张白子 PNG 接入；原黑子、现有 SVG／录制消费者及媒体业务规则保持不变。

## 部署前结论

**SPEC／本地实际视觉 PASS；CODEQUALITY／来源一致性 PASS。无本范围内 P1/P2。** 可以按已批准计划继续 TEST 部署。

部署前审查的是 APP `fbe63727464ced79fb23312190e7df54638de32c`、console `92360f3de84594e6547ccc5b5acb2e68cd14071b` 之上的工作区改动。**现已完成 TEST 代表性实际编码帧收尾，结果见第 3 节；新视频继续待人工审核。**

## 1. SPEC 与实际视觉

实际查看 `output/photo-shell-integration-20261017/local-ui-wide-1030.png`（1719×905 工作台）及 `local-recorder-1030-final.png`（1280×800 录制帧）。照片材质的柔和天然纹路、固定 studio 高光及白子各自朝向保留，数字与末手圈独立正向；未出现黑底、照片文字或原图强反光块。现有棋形、细边界和字幕没有因资产替换改变。

小尺寸静态图及有数字覆盖的白子仍会减少可见纹理；本次判断是忠实接入已批准材质，不额外承诺所有显示尺寸都能清楚看到细纹，也不把集成效果再次称为已获用户确认。

实际浏览器记录 `static-browser-proof.json` 无 page errors，四个白子仍映射为：

| 全盘坐标 | 变体 | 新构建文件 |
| --- | --- | --- |
| 15,14 | 20 | `white-20-D2Q1kU4C.png` |
| 16,13 | 05 | `white-05-CjWIMtoV.png` |
| 15,12 | 21 | `white-21-DmxAjilH.png` |
| 16,8 | 14 | `white-14-DQhusnaz.png` |

这些图片来自当前 TEST 数据配合新本地构建，不充当已部署证明。

## 2. 代码与来源复核

已读照片预览导出 hook 和 `scripts/export-tutorial-stones.mjs` diff。导出 hook 固定调用 `sprite('photo', angle)`，不读取当前选中的 AI 模式；暂停／恢复同一 renderer 的动画循环，不改变 UV、几何、材质或 studio。脚本只写白图并读取现有黑图记录哈希，沿用既有镜像路径及消费者。

独立核对结果：

- `white-00.png` 与修改前捕获的 `approved-white-00.png` **逐字节一致**，SHA-256 为 `39e2723cf23e176e2eff396c6a1dba50b794e8f1f21a0a75845313fbc728d913`。
- 32 张白图具有 32 个不同哈希；黑图与 HEAD 逐字节一致；预览 JPEG 与厂商下载原图逐字节一致。
- 从当前 `preview.ts` 去掉新增导出 hook 后，哈希等于已批准 renderer 的 `ca249a7ff38ea2d5a704835f2cb3dbdf866ea75cdd1b970bda338e199db18f2b`，确认材质／UV／光照没有顺带调整。
- manifest 中全部素材、源文件、照片哈希有效；来源明确为原始照片裁取、近似几何非扫描，记录取样框、批准基线及 TEST 范围，未将图片称为开放许可素材。
- 独立运行 `sync-tutorial-stones.mjs --check`：两端 **36 个共享文件相同**。

已阅读实施日志：两端 sprite-selection 测试各 1 项通过，录制 bundle 与 console 构建通过。未重复运行这些测试或重审既有回放、音频、任务、CAS、人审逻辑，因为本次未修改其实现。照片预览及原始素材应随本次拥有的文件一并提交，以保留导出可复现性。

## 3. TEST 实际编码帧收尾 — PASS

部署方记录 provider 为 `f7b276b5d9c60c919d8333a2ff567a6d79c89908`，console 为 `68b6cedb7edf9eb6163d699695fc911f7c4d3e13`，两服务 healthy。此次只实际查看 `output/photo-shell-integration-20261017/actual-1030-2d.png`：从新任务 `6eed09035c5841ccad8466da73969c43` 的 MP4 解出的 9.4 s 帧，1280×800，按原始尺寸观看。

**代表性编码帧视觉 PASS，无本次资产替换引起的具体阻塞发现。** 编码后仍保持已批准照片材质的柔和亮暗与纹理方向，未见新增规则条纹、黑边或明显压缩破坏。数字、反色末手圈、细边界和字幕保持清楚。白子约 29 px，且数字覆盖中心，照片细纹仍较弱；不能按放大模型的细节清晰度理解，也不能承诺再次缩小到约 13 px 后仍清楚。

已读同目录 `samples.json`：

| 图 | 新任务 | 模式与审核状态 |
| --- | --- | --- |
| 1030 | `6eed09035c5841ccad8466da73969c43` | replay；视频人工审核 null |
| 1031 | `266f8296f5294d2eaae40f4b7fac4333` | cues pending，保持诚实 static；视频人工审核 null |

样片记录注明两段均复用原 audio SHA，棋图／讲稿／静态人审和历史 3D 保持不变。本轮未重复数据、代码或业务测试，未重新运行浏览器播放检查，也没有提交、部署、生成任务或人工批准视频；浏览器播放／跳转由部署方执行。此收尾限于约定的一张实际编码帧及样片记录，不扩展为全视频重新审核。

## 4. 实施方浏览器验收

单列样片页使用 `preload="none"`，真实浏览器仅加载第一段新视频：播放时间正常前进，成功跳转至 9.4 s，视频 1280×800、时长 42.266667 s，readyState 4，media error 为 null，page errors 为空。记录见 `output/photo-shell-integration-20261017/actual-browser-playback.json`，截图见同目录 `actual-gallery-1030.png`。两个实际下载 MP4 的 SHA-256 均与任务绑定的媒体元数据一致。
