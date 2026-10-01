# 管理后台访问与启用边界

本文说明访问机制，不是当前各环境的在线证明。教程/cron 的阶段性测试机部署记录见 [Codex 报告](../../superpowers/tracks/admin-console/codex-report.md)；后续视觉功能仍仅本地提交、未部署。测试机旧公开 `admin` 的撤权及口令重置是此前单独获批的安全操作，不等于生产后台专用账号上线。

- 管理后台是独立站点和进程，Compose 的 `admin` profile 才会启动它，宿主机默认只发布 `127.0.0.1:8010`；若该端口被占用，可通过 `KATRAIN_ADMIN_HOST_PORT` 调整宿主机端口，容器内仍用 8010，且始终只绑定 `127.0.0.1`。它不在公开 Galaxy 地址注册或登录。测试机的 8010 已由 `katago-calib` 使用，拟设宿主机端口 8012，本机隧道仍可映射到 8010：`ssh -N -L 8010:127.0.0.1:8012 home-ubuntu`。每次远程连接仍需当场批准。
- 首版唯一后台用户名为 `admin:fan`。部署环境只给 `katrain-admin` 容器注入 `KATRAIN_ADMIN_USERNAME`、bcrypt `KATRAIN_ADMIN_PASSWORD_HASH`（cost ≥ 12）、随机且至少 32 字符的 `KATRAIN_ADMIN_SESSION_SECRET`、`KATRAIN_ADMIN_ENV`（`local`/`test`/`prod`）。公开 web 不持有后台口令哈希或签名密钥；后台不查询公开 `users` 表。不要把明文密码、哈希或签名密钥写进仓库、日志或聊天。
- 后台和公开 web 读取同一环境的教程业务库与媒体存储。公开 web 的 schema 初始化需先建立 `admin_audit_log`；后台本身不建表，缺表时登录/写入返回不可用，不会静默跳过审计。
- 浏览器保存八小时后台 Bearer。点击“退出”只清掉浏览器令牌；已复制的令牌仍会持续到过期。变更后台口令时同时轮换后台签名密钥并重建后台服务，才能立即作废旧令牌。
- 上线教程管理前，必须处理现有全表替换式教程同步：先备份并核对差异，暂停或修改会覆盖后台在线编辑的路径。媒体若走对象存储，后台只允许配置中的公开媒体域名作为图片/音视频来源。
- 每次真实数据库写入、push、测试部署、生产部署和远程连接均是独立审批动作；设计稿或本地测试通过不代表这些动作已获准。

## 视觉训练：本地实现，测试机尚未启用

训练 API 已实现，但默认关闭。Mac/local 和 prod 永远不能开启本旅程；页面不会自动 SSH、探测远端 GPU 或上传。真实训练采用测试机独立 loopback admin 进程，Mac 通过**另经批准的隧道**访问不同 origin/端口并独立登录。现有 Docker 后台不因此自动获得 GPU 或训练依赖。

启用前必须逐次取得只读核实、远端部署/配置写入、单次真实训练授权，并核实 GPU/容器映射及 KataGo 预留。不能以显存当前空闲代替资源预留证明。首次只支持单卡，不支持 DDP。

服务端启用条件：Linux、`KATRAIN_ADMIN_ENV=test`、`KATRAIN_ADMIN_VISION_TRAINING=1`、明确 loopback bind、`KATRAIN_ADMIN_VISION_TRAINING_CONFIG` 指向已核实绝对 JSON 文件、Ultralytics **8.4.34**。入口 `python -m katrain.web.admin` 在训练 opt-in 时绑定127.0.0.1；仅启动服务不会开始训练。配置缺失/非法、权重哈希不符或版本不同均关闭能力。配置结构如下，以下占位不是可直接部署的实际值：

```json
{
  "schema_version": 1,
  "verified": true,
  "root": "/APPROVED/fixed-training-root",
  "gpu_ids": ["<核实并预留的GPU索引>"],
  "weights": {
    "yolo11m": {
      "path": "/APPROVED/fixed-training-root/weights/yolo11m.pt",
      "sha256": "<真实64位SHA256>"
    }
  }
}
```

根目录、配置路径及登记权重不允许 symlink；权重必须位于固定根 `weights/`，不存在时不下载回退。数据集放在同根 `datasets/dataset-<hash>`，只有冻结 manifest/schema/逐文件SHA校验通过才可用；上传适配器仍待独立完成。运行在 `runs/<UUID>`，只读模型在 `models/model-<hash>`；不写公开用户库。

同根只允许一个协调器、一次一个运行；API 创建/取消均要显式确认。取消必须确认原进程组退出才释放，重启遗留运行保持 interrupted/busy，不按持久化 PID 自动杀进程或重启。需要人工恢复时先另行核实，不能直接删除状态/锁文件绕过占用。日志归档最多8MiB，但仍展示最新16KiB尾部；完成仅接受可读 best.pt、类目、全部实际参数及哈希一致的原子版本。下载/激活模型属于下一旅程，当前按钮禁用。
