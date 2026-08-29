# 生产 KataGo 能力载荷镜像（modelstella.com / ucloud-v100）

2026-08-30 用它把生产上「升降级对弈 AI 永远不落子」修好。背景与判据见
[`../../superpowers/specs/2026-08-25-ladder-engine-capability-contract.md`](../../superpowers/specs/2026-08-25-ladder-engine-capability-contract.md)。

**为什么是叠一层而不是重建。** ucloud 外网时通时断，一次真正的 KataGo 重建很可能中途停死；
而现役镜像一旦被覆盖就没有退路（`katago-trt:latest` 是多个容器共用的标签）。这里只在现役镜像上
`COPY` 三样东西，不重编、不拉基础镜像，几秒钟出结果，旧镜像原封不动。

## 三样东西分别是什么、从哪来

| 放进去的 | 来源 | 为什么 |
|---|---|---|
| `realtime_api/` | 测试机 `home-ubuntu:/home/fan/Repositories/KataGo` 的**工作树**（`develop 74d7e7fe` + 7 个未提交的本地适配） | 生产镜像是 **Python 3.8.10**，`X \| None` 必须靠 `from __future__ import annotations` 才解析得了 —— 那些「本地适配」不是可选项。另外它带了 `REALTIME_API_WARMUP_TIMEOUT` 这个逃生阀。 |
| `config.yaml` | 本目录 | 多模型格式（`models:` 列表 + `default_model`）。旧的单 `model:` 格式产生的 `/health` 没有 `capability_schema`，`require_ladder_capability` 第一句就拒。 |
| `kata1-b18c384nbt-s9996604416-d4316597426.bin.gz` | **生产机上早就有**（旧 release 目录），sha256 与 config 一致 | 阶梯 35/37/38/39/40/41 六档的 `main_model` 是 `b18`；没有这个别名，那六档会报 `HTTP ladder model 'b18' is not advertised`。b28 与 humanv0 镜像里本来就有。**权重不进仓库**，98MB。 |

`ENV REALTIME_API_WARMUP_TIMEOUT=1800` 写在镜像里而不是 compose：compose 归 release 管，
手改会被下一次部署覆盖掉。V100 上两个模型各建一次 TensorRT plan，冷启动要十几分钟。

## 构建与切换

构建上下文在生产机的 `/opt/katrain/katago-capability/`（**不要放 `/tmp`**，会被清）。

```bash
# 现役镜像先给个名字：buildkit 不认裸 sha256:，会当成 Docker Hub 引用去 HEAD 一下然后 403
docker tag 6516aaa7e10a katago-realtime:base-20260331

cd /opt/katrain/katago-capability
DOCKER_BUILDKIT=0 docker build --build-arg BASE=katago-realtime:base-20260331 \
    -t katago-realtime:capability-schema-20260830 .

# 换镜像 = 改一个变量
sudo cp -a /etc/katrain/ucloud.env /etc/katrain/ucloud.env.bak-$(date +%Y%m%d)
sudo sed -i 's|^KATAGO_IMAGE=.*|KATAGO_IMAGE=katago-realtime:capability-schema-20260830|' /etc/katrain/ucloud.env

cd /opt/katrain/current/deploy/ucloud
sudo docker compose --project-name katrain-ucloud --env-file /etc/katrain/ucloud.env \
    -f compose.yml --profile production up -d --no-deps katago-web
```

先跑一次 `--dry-run`：它必须只说 `katago-web Recreate`，多一个服务就停手
（容器标签里记的 compose 工作目录是个**已经被删掉的** release，别让它顺手去调和别的服务）。

## 验收

不要只看 `/health` 的形状（那只证明这一层贴上去了）。端到端一条：

1. `curl -s localhost:8000/health` → `capability_schema: 1`、`ready: true`、
   `models` 里 b28/b18 各自 `running/model_sha256_verified/human_model_sha256_verified` 全 true；
2. 开一局升降级、落一手，`player_to_move` 要从 W 回到 B；
3. 服务端日志里**不应**再有 `[ladder] engine unavailable at certified strength`。

## 回滚

```bash
sudo cp -a /etc/katrain/ucloud.env.bak-20260830-ladder /etc/katrain/ucloud.env
cd /opt/katrain/current/deploy/ucloud
sudo docker compose --project-name katrain-ucloud --env-file /etc/katrain/ucloud.env \
    -f compose.yml --profile production up -d --no-deps katago-web
```

旧镜像仍在，另打了 `katago-realtime:base-20260331` 这个名字，没有被覆盖。
