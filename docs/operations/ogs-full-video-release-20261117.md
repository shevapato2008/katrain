# OGS 248小节视频正式片单

用户已验收本机编排预览，授权按四步流程整合并发布到RK3562。正式客户端读取 `https://modelstella.com/media/tutorial_demos/ogs-full-20261117/manifest.json`，稳定 lesson ID 与正式已有248节课程一致；不导入TEST教材数据库、数字外键或测试快照。

本轮编排来自12本书、316段现有普通话视频，共721次顺序引用；双档632份MP4约1327MiB，全部位于服务器。盒端仅按需读取1024×600档，不打包视频、不预下载4K。片单允许无封面；如提供封面，其地址仍严格限制在当前正式版本目录。生产与TEST的构建配置分离，TEST快照/预览入口没有进入正式入口或设备鉴权。

正式冻结数据位于 `superpowers/tracks/tutorial-database/releases/ogs-full-20261117/`：manifest、release-index以及逐章内容决策。完整审查表为相邻的 `ogs-video-arrangement-2026-11-17.html`。素材支持程度不等于每一道原题的精确手顺均在视频中演示；各节覆盖说明保留具体边界，原OGS练习及答案树不改。

发布程序 `scripts/tutorials/publish_ogs_release.py` 默认只读预检；显式 `--publish` 才条件创建固定版本目录的对象。它校验固定PROD数据库身份、目标bucket/public base、633个唯一键、源SHA及回读SHA，632份视频全部成功后最后写manifest。旧 `ogs-intro-20261115` 对象不覆盖、不删除。回退客户端版本即可恢复原14节片单。

集成顺序：功能分支追最新develop并测试、提交推送；合入并推送develop；在干净的SmartBox发布checkout中更新vendor/katrain并推送main；定向部署正式前端/媒体清单和RK3562围棋前端。SmartBox本地未推送的其他语音提交及其他工作区保留，不夹带发布。不重建引擎/数据库或改动其他棋类。

验证基线：编排约束23项、相关前端57项通过，真实TEST快照预览的7英寸播放→原练习→落子判定、4K播放已经验证。发布前独立代码检查通过。正式构建、实际服务器和RK3562发布结果以部署回执为准，代码提交本身不表示已部署。
