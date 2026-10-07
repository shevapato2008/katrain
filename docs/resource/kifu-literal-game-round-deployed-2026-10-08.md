# SGF赛事局次／轮次校验发布

- 本地代码提交 `d56224ec`，独立Astra两轮审核最终PASS，主窗口实际152 tests通过。GitHub HTTPS及SSH443当前均超时，push尚未成功；不声称远端已有提交。
- TEST／PROD均实际构建不可变web镜像、按现有26／25层Compose配置持久发布，仅替换共享 `raw_event_translation.py`。健康、文件SHA、原env键／挂载／镜像及配置层核验通过。原发布 `develop-home/prod-4a911bb5` 作为回退保留；未重启GPU、数据库或RK3562。
- 新独立importer标签 `katrain-kifu-importer:literal-game-round-test/prod-20261008-r2` 已构建，四imports及新game阳性通过。与两端读端模块SHA一致：`e9122f7fe70260a97e813cb8be9529fe2759750a71311c437ae61474dcf19fc4`。旧mixed／normative标签和receipt没有覆盖。
- TEST web镜像ID `bb2ccc1ff043834e6f349755efc9f7a212737650fad14a6dabdf1eb9d841d0a3`；PROD web `67f3236aa3dad7c40755f0d1ae636fed455264075db82df7786a838c028ada5f`。
- 准备时一次env键检查因Config.Env未含容器运行时自动加入键而拒绝；仅补只读实际Python env键捕获，不读取／输出值。一次挂载比较因相同集合顺序不同拒绝，核对完全相同destination/type后改为顺序无关比较；都发生在部署之前。
- 完整发布、回退标签、模块差异、实际构建及部署收据见同名JSON.gz。新grammar首包145raw／211棋局仍在源冻结／owner准备，不计已翻译增量。
