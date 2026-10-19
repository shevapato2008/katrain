# 双档 2D 教程视频测试交付 · 2026-10-17

## 入口与操作

- [第11页第1图](http://127.0.0.1:18012/admin?book=4&page=11&figure=1030&filter=all)
- [第11页第2图](http://127.0.0.1:18012/admin?book=4&page=11&figure=1031&filter=all)

沿用现有测试后台、账号和SSH隧道。在右栏「视频讲解 → 输出档位」选择「Galaxy · 4K」或「RK3562 · 7英寸」，播放当前保存版本。每档分别生成和人工审核；旧2D/3D文件只读保留。未代点新视频人工审核。

## 已部署版本

- TEST provider：`569120ae95b35a9f24c05429790bcf086b137e9c`，镜像 `smartbox-admin-go:tutorial-dual-profile-569120ae95b3`。
- TEST console：`03e967a14afd58dd9eef76debffba0b6be849232`，镜像 `smartbox-admin:tutorial-dual-profile-03e967a14afd`。
- 后端分档实现提交：`e6a67aa65ac97c89f86702cc21d9171ab93eba4b`；批准录制布局：`baf0e57ef`。
- 两个容器健康；环境、session密钥、端口、网络、挂载和资源限制保持。发布前任务队列为空，容器替换前后1030–1033数据指纹一致。
- 已核实TEST环境与DB system_identifier `7596941912817897507`、s3 `tutorial-assets`、`https://go.sailorvoyage.top/media`。未重启DB/MinIO/GPU/web/cron，未部署正式环境、ucloud或RK设备。
- 本阶段无develop/main合并或push。普通Galaxy/kiosk消费页面已在APP提交并构建，当前admin provider不承载这些页面，未声称已部署到设备/公网消费端。

## 实际测试环境产物

| figure_id | 输出档位 | 原生尺寸 | 时长 | 字节数 | 任务执行耗时 |
| --- | --- | --- | --- | --- | --- |
| 1030 | galaxy-4k-v1 | 3840×2160 | 42.24s | 4,658,160 | 235.72s |
| 1030 | kiosk-7-v1 | 1024×600 | 42.24s | 1,058,240 | 40.85s |
| 1031 | galaxy-4k-v1 | 3840×2160 | 25.44s | 2,853,942 | 48.87s |
| 1031 | kiosk-7-v1 | 1024×600 | 25.44s | 637,627 | 11.47s |

四段均为原生30fps、H.264/yuv420p/AAC。逐文件下载并核对artifact SHA256；视频/音轨时长差均约0.006667s，小于一帧。

1030为真实7手回放，沿用已保存初始局面、提子规则和已有时间轴。1031仍为静态讲解，落子时间待校准；没有为播放编造cue。两版共享对应的原音频SHA，不重新TTS或调用AI视频模型。棋图、文稿、audio_asset和board_review逐项比较未变。

四段新视频的人工审核状态均为false；Astra工程/视觉审查不等于管理员内容人工审核。

## 验证

- Python媒体任务/审核/渲染：80 passed、2 opt-in skipped；旧档真实Chrome+FFmpeg渲染另1 passed。
- Console聚焦：95 passed；APP聚焦：41 passed；两端构建、diff检查通过。原有讲解测试改为等待真实编辑状态，未变更产品编辑逻辑。
- 实际TEST后台：两图×两档浏览器播放均成功，切换档位与刷新读取各自artifact；无页面控制台错误。最后RK播放器实测1024×600、currentTime10.31426、error=null。
- 独立Astra Max：后端SPEC/CODE PASS；前端唯一P2（消费者缺少画外静态待校准说明）修复后SPEC/CODE PASS；两档实际成片解码帧视觉PASS。未见画内状态字、已移除范围框或灰遮挡；Galaxy原生白子天然纹路与光泽可辨。
- RK成片原生棋子约25px，细纹受屏幕像素限制。未进行RK硬解/实机验收。普通消费者临时只读本地代理的翻译响应壳不完整，实际外壳播放未验收；未把该测试工具问题当成产品通过。已有消费者选档、待校准说明、全视口层及返回行为聚焦测试通过，先前真实1024×600层几何验证通过。

## 文件校验

- `1030 / galaxy-4k-v1`：`7158df32283a012cdd00d66a65761912b6f155ee5ab8579c45f4d836a3d45881`
- `1030 / kiosk-7-v1`：`5d98a65f2866507373d5ecbc39ab5a1982e329848efa8961d8b8ead1d2e7c2a0`
- `1031 / galaxy-4k-v1`：`f733853e10fb224e89c45a9ee3381fda4cef7d600d2de355dbd17a9820c52488`
- `1031 / kiosk-7-v1`：`139d78ea9e7cee4f81a9712eea0ec798c7461816400b2d35cdfd752449e32000`

私有发布配置、回滚配置、原始probe/快照及下载视频保存在本机 `~/.local/share/smartbox-admin/tutorial-dual-profile-release-20261017/` 与home-ubuntu同名发布目录；密钥与令牌不入Git。
