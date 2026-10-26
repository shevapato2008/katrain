# UCloud 旧→新运行与容量只读盘点（2026-10-27）

仅连接 `ucloud-v100-old`，确认 hostname `10-60-219-118`、eth0 `10.60.219.118`、WireGuard `10.8.0.3`；旧公网为任务指定 `117.50.183.169`。未连接或修改新的 `ucloud-v100`，未修改服务、锁、调度、DNS、数据库内容，未发起 dump、采集、导入、全表查询或 SGF 文件读取。

权威容器来源：`/Users/fan/.local/share/ucloud-migration/2026-10-26/docker-containers.private.json`（20 个实际 inspect，含秘密，仅限私有使用）。补充原始输出均保存在同目录下 `runtime-inventory/`（目录 0700，文件 0600）：`old-runtime.private.json`、`old-detail.private.json`、`old-metadata.private.json`、`old-scoped-diff.private.json`、`old-versions.private.json`。本报告不包含密码、secret、角色 hash 或完整环境变量。

## 结论与容量

- 20 个容器：17 running、3 exited；共 18 个不可变 image ID，17 个仍存在。已退出 importer 的 `sha256:7bac8e07808c542ba361aa8dfb2011500aa09f0ae8d726d3608b7608337e108b` 已不在 image store，不能用当前同名 tag 冒充。
- 现存17个唯一镜像（含停止态mc）的 content 合计上界 **18,182,118,872 B（18.182 GB）**；371 个按 RootFS diffID 去重的解包层 **21,769,580,544 B（21.770 GB）**。当前 Docker 使用 `overlayfs / io.containerd.snapshotter.v1`，保留 content 与 snapshot 的物理容量保守上界 **39.952 GB**。content 尚未按 compressed digest 去重，实际会更小。
- 在线迁移集合为 **17 running容器 / 16个唯一image ID**：content上界 **18,152,515,126 B** + 366个去重解包层 **21,708,210,176 B** = **39.861 GB**。**三个exited容器（minio-setup、kifu-init、kifu-importer）全部excluded，不迁移启动、不执行初始化/导入**；mc镜像也不属于在线必要镜像集。
- `docker system df -v` 的每镜像 SIZE 在此引擎上包含 content 与解包层；17 个 ID 的 SIZE 简单相加约 42.35 GB，不能再额外叠加 content，也不能将全局 UNIQUE SIZE 约 3.31 GB 当作迁移需求。
- 八个现用持久卷约 **12.417 GB**（Docker df 四舍五入）；必要 bind 约 **278.873 MB**；TLS 目录仅 199,108 B。在线必要镜像 + 全部现用卷 + bind 约 **52.56 GB**，无需整盘复制旧机约 110.09 GB 已用空间。
- 原 GPU 为单张 Tesla V100-PCIE-16GB-LS / 16,384 MiB，驱动 535.288.01。web 与 cron 两引擎都申请同一主机 `nvidia Count=1 / NVIDIA_VISIBLE_DEVICES=all`；应保持单卡双 engine，勿额外开启采集。
- PROD cron 的实际值为 `CRON_KIFU_ANALYZE_ENABLED=false`、`CRON_REPORT_ANALYZE_ENABLED=true`、`CRON_REPORT_CONCURRENCY=3`，这三个显式值不能代表其它默认任务关闭；实际运行配置补核证实直播采集、翻译、备份等默认开启，但无原生小时 kifu_ingest 注册。仅 TEST 保留原生小时采集。

| 100 GB 目标盘预算项 | 保守预算（十进制 GB） | 说明 |
| --- | --- | --- |
| 必要 image content + snapshot | 40 | 16个在线必要ID；流式save/load，目标不落全量tar |
| 八个现用数据卷 | 13 | 包括主PG所有preview/baseline库、MinIO、kifu_work、审计 |
| bind、TLS与少量运行配置 | 0.5 | 保留owner/mode与目录结构 |
| 新机OS、Docker/NVIDIA工具与基础日志 | 10 | 预算值；需以新机df现状替换 |
| 数据传输/恢复工作空间 | 8 | 只保留单批数据库归档；主库dump仍partial，不可恢复 |
| 增长与恢复余量 | 15 | WAL、索引恢复、日志等 |
| 总预算 | 86.5 | 约80.6GiB；100GB盘约93.1GiB，仍留约13.5GB未分配预算 |

上述为规划预算，不是新机剩余空间实测。应逐批流式传 image，恢复完成一批再释放其目标临时归档；不要在目标同时放整套 docker save、全量数据副本与第二份完整PG目录。PG逻辑恢复可能产生临时索引/WAL，8 GB工作区与15 GB余量应持续监测。旧机 `/dev/vda1`：207,929,917,440 B，总已用 110,091,218,944 B，可用 97,821,921,280 B。

## 旧运行时版本

- OS：Ubuntu 22.04.4 LTS（jammy），kernel 5.15.0-113-generic，amd64。
- Docker Engine Community：client/server均 **29.5.2**；API **1.54**，server最低API1.40；Engine git 568f755 / client git 79eb04c。
- containerd.io **v2.2.4**，runc **1.3.5**，docker-init **0.19.0**，Compose插件 **v5.1.4**。
- Docker store：overlayfs / `io.containerd.snapshotter.v1`，root `/var/lib/docker`。新机依现有Docker官方source安装同29 major（可用时同patch），不需要Ubuntu发行版升级。

## 20 容器实际运行表

| 容器 | image ID前12位 | 状态 | Config.User | restart | runtime | host端口 | 网络 | mount源/卷 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| katrain-ucloud-katrain-web-1 | f90b1526e8ec | running | 10001:10001 | unless-stopped | runc | 10.8.0.3:8001→8001/tcp; 127.0.0.1:8001→8001/tcp | katrain-ucloud_app,katrain-ucloud_backend | katrain-ucloud_katrain-state-production |
| smartbox-admin-admin-console-1 | cf96fe9e7432 | running | 10001:10001 | unless-stopped | runc | 127.0.0.1:8010→8011/tcp | katrain-ucloud_app,lobby-net,smartbox-admin_default | smartbox-admin_admin-audit |
| smartbox-platform | 485903bb2ae8 | running | 未设（镜像默认） | unless-stopped | runc | 127.0.0.1:8090→8090/tcp | lobby-net | /home/ubuntu/smartbox-platform/ui/lobby,/home/ubuntu/smartbox-platform/ui/shared |
| katrain-ucloud-katrain-admin-1 | 86f9abb4fcec | running | 10001:10001 | unless-stopped | runc | 127.0.0.1:18010→8010/tcp | katrain-ucloud_app,katrain-ucloud_backend | — |
| katrain-ucloud-katrain-cron-1 | 9b28e8be9b77 | running | 未设（镜像默认） | unless-stopped | runc | 无host发布 | katrain-ucloud_app,katrain-ucloud_backend | — |
| katrain-ucloud-katago-cron-1 | b242fd2a379b | running | 未设（镜像默认） | unless-stopped | nvidia | 10.8.0.3:8002→8000/tcp; 127.0.0.1:8002→8000/tcp | katrain-ucloud_app | /home/ubuntu/katrain-transformer/models/kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz |
| katrain-ucloud-minio-setup-1 | aead63c77f9d | exited | 未设（镜像默认） | no | runc | 无host发布 | katrain-ucloud_backend | /opt/katrain/releases/42c40275/deploy/ucloud/minio/bootstrap.sh |
| pitch-booking-caddy-1 | 4c6e91c6ed0e | running | 未设（镜像默认） | no | runc | 127.0.0.1:8080→8080/tcp | pitch-booking_default | /opt/pitch-booking/releases/3010f042179fd8ecef5c1eab0e17457552a9019b/deploy/Caddyfile |
| pitch-booking-worker-1 | 471818775e47 | running | pitch | no | runc | 无host发布 | pitch-booking_default | — |
| pitch-booking-api-1 | 28f423c069fc | running | pitch | no | runc | 无host发布 | pitch-booking_default | — |
| katrain-ucloud-katago-web-1 | efdeb9de4f64 | running | 未设（镜像默认） | unless-stopped | nvidia | 10.8.0.3:8000→8000/tcp; 127.0.0.1:8000→8000/tcp | katrain-ucloud_app | — |
| platform-postgres | fe0737ba566a | running | 未设（镜像默认） | unless-stopped | runc | 127.0.0.1:5433→5432/tcp | bridge,lobby-net | lobby-pgdata |
| pitch-booking-postgres-1 | d4bb0a8c1b7b | running | 未设（镜像默认） | no | runc | 无host发布 | pitch-booking_default | pitch-booking_postgres_data |
| katrain-ucloud-minio-1 | a1ea29fa2835 | running | 未设（镜像默认） | unless-stopped | runc | 无host发布 | katrain-ucloud_backend | katrain-ucloud_minio-data |
| smartbox-kifu-api-1 | 9760261da8ff | running | 未设（镜像默认） | unless-stopped | runc | 10.8.0.3:8013→8013/tcp; 127.0.0.1:8013→8013/tcp; 127.0.0.1:9013→9013/tcp | smartbox-kifu_default | smartbox-kifu_kifu_work |
| smartbox-kifu-api-b-1 | 9760261da8ff | running | 未设（镜像默认） | unless-stopped | runc | 10.8.0.3:8014→8013/tcp; 127.0.0.1:8014→8013/tcp; 127.0.0.1:9014→9014/tcp | smartbox-kifu_default | smartbox-kifu_kifu_work |
| smartbox-kifu-init-1 | 9760261da8ff | exited | 未设（镜像默认） | no | runc | 无host发布 | smartbox-kifu_default | smartbox-kifu_kifu_work |
| smartbox-kifu-importer-1 | 7bac8e07808c | exited | 未设（镜像默认） | no | runc | 无host发布 | smartbox-kifu_default | smartbox-kifu_kifu_work |
| smartbox-kifu-postgres-1 | 57c72fd2a128 | running | 未设（镜像默认） | unless-stopped | runc | 无host发布 | smartbox-kifu_default | smartbox-kifu_kifu_db |
| katrain-ucloud-postgres-1 | 3d0f7584ed7d | running | 未设（镜像默认） | unless-stopped | runc | 无host发布 | katrain-ucloud_backend | katrain-ucloud_postgres-data |

Config.User 是启动配置；PostgreSQL entrypoint 会切换至数据库用户。仅容器暴露但未 host publish 的端口未逐项列入 host 列；完整端口与 GPU DeviceRequests 均在权威 inspect。所有容器 host publish 都限定 loopback 或 VPN，没有容器直接绑定公网 0.0.0.0。

## 启动命令与依赖

| 容器 | 脱敏命令 | 依赖与启动语义 |
| --- | --- | --- |
| katrain-ucloud-katrain-web-1 | python3 -m katrain --ui web --host 0.0.0.0 --port 8001 | PG15主库 / minio:9000 / katago-web:8000 |
| smartbox-admin-admin-console-1 | smartbox-admin --host 0.0.0.0 --port 8011 --static-dir /app/ui/dist | katrain-admin:8010 / smartbox-platform:8090；/data/audit.sqlite |
| smartbox-platform | /usr/local/bin/entrypoint.sh | platform-postgres:5432/lobby；两处lobby/shared静态bind；SSO密钥来自私有inspect |
| katrain-ucloud-katrain-admin-1 | python3 -m katrain.web.admin | PG15主库 / minio:9000；统一admin provider |
| katrain-ucloud-katrain-cron-1 | python -m katrain.cron | PG15主库 / minio:9000 / katago-cron:8000；旧分析/直播采集/翻译任务，无原生小时 kifu_ingest |
| katrain-ucloud-katago-cron-1 | /opt/nvidia/nvidia_entrypoint.sh → python3 -m realtime_api.main | /opt/katago/config.yaml；外部模型只读bind；nvidia单卡共享 |
| katrain-ucloud-minio-setup-1 | /bin/sh /bootstrap.sh | 已退出0；会写入bucket/权限；bind源已缺失，不自动运行 |
| pitch-booking-caddy-1 | caddy run --config /etc/caddy/Caddyfile --adapter caddyfile | api:8000；内部HTTP层，没有TLS持久卷 |
| pitch-booking-worker-1 | uv run python -m backend.app.worker | PG17 postgres:5432/pitch；APP_ENV=staging；payment/notification disabled |
| pitch-booking-api-1 | /bin/sh -c [uv run alembic upgrade head && exec uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000] | PG17 postgres:5432/pitch；启动自动执行alembic迁移；外部OSS/WeChat配置来自私有inspect |
| katrain-ucloud-katago-web-1 | /opt/nvidia/nvidia_entrypoint.sh → python3 -m realtime_api.main | /app/config.yaml；模型在image；nvidia单卡共享 |
| platform-postgres | docker-entrypoint.sh → postgres | lobby-pgdata / PG15.19 |
| pitch-booking-postgres-1 | docker-entrypoint.sh → postgres | pitch-booking_postgres_data / PG17.11 |
| katrain-ucloud-minio-1 | /usr/bin/docker-entrypoint.sh → server /data --console-address :9001 | katrain-ucloud_minio-data；bucket tutorial-assets |
| smartbox-kifu-api-1 | uvicorn kifu_api.main:app --host 0.0.0.0 --port 8013 | PG16 postgres:5432/kifu；generation2；共享kifu_work |
| smartbox-kifu-api-b-1 | uvicorn kifu_api.main:app --host 0.0.0.0 --port 8013 | 同上；第二API副本，非第二采集 |
| smartbox-kifu-init-1 | python -m kifu_api.prestart | 已退出0；初始化/迁移任务，不自动运行 |
| smartbox-kifu-importer-1 | sh -c → python -m kifu_api.ingest <source> --workdir /var/lib/kifu --generation 2 [参数由env决定] | 已退出0；image已缺失；会采集/导入，不自动运行 |
| smartbox-kifu-postgres-1 | docker-entrypoint.sh → postgres | smartbox-kifu_kifu_db / PG16.14 |
| katrain-ucloud-postgres-1 | docker-entrypoint.sh → postgres | katrain-ucloud_postgres-data / PG15.18 |

## 不可变镜像清单

| 实际image ID（完整） | 使用者 | image content bytes（单image） | 解包history bytes（单image） |
| --- | --- | --- | --- |
| sha256:28f423c069fc439faa2b486eeb88d0a4c8297a221bdc407518661347acdf3ac0 | pitch-booking-api-1 | 177,839,454 | 584,929,280 |
| sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f | katrain-ucloud-postgres-1 | 115,217,815 | 300,732,416 |
| sha256:471818775e4743ea00dd07f95a77ac6782c9e4d0ede399b46d460093b0e16c29 | pitch-booking-worker-1 | 177,839,457 | 584,929,280 |
| sha256:485903bb2ae878287de244f90b8dac457cdbb37564f3ff0005dcf0b4a0c606df | smartbox-platform | 236,982,712 | 431,267,840 |
| sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d | pitch-booking-caddy-1 | 22,520,098 | 60,338,176 |
| sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777 | smartbox-kifu-postgres-1 | 116,039,394 | 302,907,392 |
| sha256:7bac8e07808c542ba361aa8dfb2011500aa09f0ae8d726d3608b7608337e108b | smartbox-kifu-importer-1 | 旧机已缺失 | 未知 |
| sha256:86f9abb4fcec71c920ab7885bae39011292f776089cd24c24346095579ea19d9 | katrain-ucloud-katrain-admin-1 | 1,110,224,811 | 2,047,737,856 |
| sha256:9760261da8ffebc648abb630f63f9f73d436ee26fe594b440f1a22f35f7c4d10 | smartbox-kifu-api-1, smartbox-kifu-api-b-1, smartbox-kifu-init-1 | 71,617,418 | 237,846,528 |
| sha256:9b28e8be9b77deb63f99cac2b076aac9df584a521f9b00989d6cc2bc920adb79 | katrain-ucloud-katrain-cron-1 | 69,977,796 | 217,022,464 |
| sha256:a1ea29fa28355559ef137d71fc570e508a214ec84ff8083e39bc5428980b015e | katrain-ucloud-minio-1 | 64,009,196 | 186,040,320 |
| sha256:aead63c77f9db9107f1696fb08ecb0faeda23729cde94b0f663edf4fe09728e3 | katrain-ucloud-minio-setup-1 | 29,603,746 | 86,683,648 |
| sha256:b242fd2a379b28b7dda5cf965e41230324bc825e7d23cd4aa1c0c81f7a16798e | katrain-ucloud-katago-cron-1 | 2,211,029,953 | 3,463,581,696 |
| sha256:cf96fe9e743263206e8aad91ecc8d554ef885d42d735a42fdf2e9ebcefa64602 | smartbox-admin-admin-console-1 | 196,475,062 | 211,841,024 |
| sha256:d4bb0a8c1b7bb2e29f976d099e7bfb9a5d8858cffe9e46b35cd302cd1f1f8168 | pitch-booking-postgres-1 | 117,204,007 | 305,963,008 |
| sha256:efdeb9de4f64faf68072d236a3f73ff5c1f38af9566d78a52af78ec03f3026f3 | katrain-ucloud-katago-web-1 | 10,442,340,455 | 10,519,334,912 |
| sha256:f90b1526e8ec9375e3f0021a478b7a546fbf3026f6268b2b331adf97289b5355 | katrain-ucloud-katrain-web-1 | 2,907,946,938 | 4,277,620,736 |
| sha256:fe0737ba566a2c5b2a28f34433c0a423261900ec17b9bf7ad115e1aae7e57f1b | platform-postgres | 115,250,560 | 300,785,664 |

单image解包列存在共享层，勿相加当去重需求。重建应 pin 上述实际 ID/digest；`postgres:15-alpine` 在两服务实际为不同 ID（15.18 vs 15.19），`latest` 也不能作为精确版本依据。

## 持久卷与外部绑定

| 卷名 | 精确旧机源路径 | 容器目标 | 使用量约 | UID:GID / mode |
| --- | --- | --- | --- | --- |
| katrain-ucloud_katrain-state-production | /var/lib/docker/volumes/katrain-ucloud_katrain-state-production/_data | /home/katrain/.katrain | 24.6 kB | 10001:10001 / 755 |
| smartbox-admin_admin-audit | /var/lib/docker/volumes/smartbox-admin_admin-audit/_data | /data | 16.38 kB | 10001:10001 / 755 |
| lobby-pgdata | /var/lib/docker/volumes/lobby-pgdata/_data | /var/lib/postgresql/data | 49.16 MB | 70:70 / 700 |
| pitch-booking_postgres_data | /var/lib/docker/volumes/pitch-booking_postgres_data/_data | /var/lib/postgresql/data | 69.24 MB | 70:70 / 700 |
| katrain-ucloud_minio-data | /var/lib/docker/volumes/katrain-ucloud_minio-data/_data | /data | 2.768 GB | 0:0 / 755 |
| smartbox-kifu_kifu_work | /var/lib/docker/volumes/smartbox-kifu_kifu_work/_data | /var/lib/kifu | 704.6 MB | 0:0 / 755 |
| smartbox-kifu_kifu_db | /var/lib/docker/volumes/smartbox-kifu_kifu_db/_data | /var/lib/postgresql/data | 1.223 GB | 70:70 / 700 |
| katrain-ucloud_postgres-data | /var/lib/docker/volumes/katrain-ucloud_postgres-data/_data | /var/lib/postgresql/data | 7.603 GB | 70:70 / 700 |

| 精确bind源路径 | 容器目标 | 使用量 | UID:GID / mode |
| --- | --- | --- | --- |
| /home/ubuntu/smartbox-platform/ui/lobby | /usr/local/lib/python3.12/site-packages/lobby_api/static/lobby | 4,369,079 B | 1000:1000 / 755 |
| /home/ubuntu/smartbox-platform/ui/shared | /usr/local/lib/python3.12/site-packages/lobby_api/static/shared | 12,464,283 B | 1000:1000 / 755 |
| /home/ubuntu/katrain-transformer/models/kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz | /opt/katago/models/kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz | 262,039,869 B | 1000:1000 / 664 |
| /opt/katrain/releases/42c40275/deploy/ucloud/minio/bootstrap.sh | /bootstrap.sh | 已不存在 | 缺失 |
| /opt/pitch-booking/releases/3010f042179fd8ecef5c1eab0e17457552a9019b/deploy/Caddyfile | /etc/caddy/Caddyfile | 125 B | 0:0 / 664 |

MinIO volume 要包含对象和 `.minio.sys` 等自身元数据。kifu_work 仅按卷用量盘点，未列举/读取其SGF内容；迁移时应保留现用工作卷及manifest/provenance，不基于“cache”字样擅自排除。所有PG卷 owner 为70:70 / 0700；不得在线直接拷贝正在运行的PG目录作为一致备份，需由统筹选定停机物理复制或版本匹配的逻辑备份/恢复方案。

## 全部 PostgreSQL 数据库（非template）

| 容器 | 实际版本 | 数据库 | pg_database_size bytes |
| --- | --- | --- | --- |
| platform-postgres | 15.19 | lobby | 8,854,887 |
| platform-postgres | 15.19 | postgres | 7,667,047 |
| pitch-booking-postgres-1 | 17.11 | pitch | 12,023,475 |
| pitch-booking-postgres-1 | 17.11 | postgres | 7,698,099 |
| smartbox-kifu-postgres-1 | 16.14 | kifu | 729,889,815 |
| smartbox-kifu-postgres-1 | 16.14 | postgres | 7,699,479 |
| katrain-ucloud-postgres-1 | 15.18 | katrain_db | 9,608,551 |
| katrain-ucloud-postgres-1 | 15.18 | katrain_import_preview | 628,931,943 |
| katrain-ucloud-postgres-1 | 15.18 | katrain_prod_20260725 | 4,950,195,559 |
| katrain-ucloud-postgres-1 | 15.18 | katrain_slice1_20260725_baseline | 634,871,143 |
| katrain-ucloud-postgres-1 | 15.18 | katrain_slice1c_20260725 | 628,809,063 |
| katrain-ucloud-postgres-1 | 15.18 | katrain_slice1c_20260725_baseline | 628,800,871 |
| katrain-ucloud-postgres-1 | 15.18 | postgres | 7,667,047 |

查询仅 `SHOW server_version` 与 `pg_database / pg_database_size`，未访问应用表、角色密码或hash。主应用、admin、cron共同使用 `katrain_prod_20260725`；其它preview/baseline库仍属于同一现用PG15卷，完整迁移时保留，不在本盘点中删除或截断。现有Mac `katrain-prod.pgcustom.partial` 仍为partial，未检查完整性、未恢复、未追加第二个dump。

## 网络、入口、TLS与VPN

| 网络 | Driver | Internal | IPv4子网 | 迁移注意 |
| --- | --- | --- | --- | --- |
| bridge | bridge | False | 172.17.0.0/16 | 保留服务alias与连接关系 |
| katrain-ucloud_app | bridge | False | 172.20.0.0/16 | 保留服务alias与连接关系 |
| katrain-ucloud_backend | bridge | True | 172.19.0.0/16 | 保留服务alias与连接关系 |
| lobby-net | bridge | False | 172.23.0.0/16 | 保留服务alias与连接关系 |
| smartbox-admin_default | bridge | False | 172.24.0.0/16 | 保留服务alias与连接关系 |
| pitch-booking_default | bridge | False | 172.22.0.0/16 | 保留服务alias与连接关系 |
| smartbox-kifu_default | bridge | False | 172.21.0.0/16 | 保留服务alias与连接关系 |

四个核心容器（GPU web/cron、KaTrain web、platform）的只读 `docker diff` 未发现 `.py/.yaml/.yml/.sh/.toml/.ini` 源码或配置文件改动；两个GPU指定config路径也未出现在diff中。变动主要是解释器缓存和NVIDIA运行时注入，不迁移这些可写层。未对其它容器开展全量diff审计。

旧机公网listener：TCP22/80/443，UDP36353（WireGuard）；容器服务仅loopback/VPN，PG15 lobby另发布127.0.0.1:5433。Nginx systemd启用且运行；不存在host Caddy service或 `/etc/caddy/Caddyfile`。以下为旧机实际已加载入口：

| 域名 | 旧机配置源（sites-enabled均为指向这些源的symlink） | 路由 | TLS目录 |
| --- | --- | --- | --- |
| `_`（默认站点） | /etc/nginx/sites-enabled/default | HTTP80默认站点，root /var/www/html | 无TLS |
| modelstella.com / www.modelstella.com | /etc/nginx/sites-available/modelstella.com | /api/v1/kifu/ 与 / →127.0.0.1:8001 | /etc/letsencrypt/live/modelstella.com/ |
| pitch-api-staging.modelstella.com | /etc/nginx/sites-available/pitch-api-staging.modelstella.com | / →127.0.0.1:8080；内层Caddy只放行/api/*及/platform-admin*→api:8000 | /etc/letsencrypt/live/pitch-api-staging.modelstella.com/ |
| lobby.modelstella.com | /etc/nginx/sites-available/smartbox-platform | users/games/lobby/auth/health/ws/lobby/static/shared→127.0.0.1:8090，其余404 | /etc/letsencrypt/live/smartbox-platform/ |
| ranked.modelstella.com | /etc/nginx/sites-available/smartbox-platform | ranked/auth/health→127.0.0.1:8090，其余404 | /etc/letsencrypt/live/smartbox-platform/ |

还需保留 `/etc/nginx/nginx.conf`、`/etc/nginx/snippets/katrain-frontend-gzip.conf`、`/etc/nginx/snippets/smartbox-platform-proxy.conf`、`/etc/nginx/snippets/smartbox-platform-ws.conf` 及其已加载include依赖。TLS使用 `fullchain.pem`、`privkey.pem` symlink；复制时保留整个 `/etc/letsencrypt/` 的live/archive/renewal关系与权限（live/archive 0700 root:root，目录总199,108 B），并保留 `/var/www/letsencrypt` ACME webroot配置。私钥内容未读取。

应用inspect的公共媒体URL为 `https://v100-preview.sailorvoyage.top/media`，但此域名未出现在旧机加载的Nginx配置中；其外层gateway/Caddy/DNS入口不属于这份旧机已证实路线，不应误认迁完本机Nginx即已迁完该入口。旧机inspect没有admin-console公网域名，实际127.0.0.1:8010入口的外部代理亦应由统筹在gateway侧对接。

VPN为root拥有的 `wg-quick@wg0`，active/exited、enabled，配置 `/etc/wireguard/wg0.conf` 0600 root:root，目录0700；监听UDP36353、1个peer。接口10.8.0.3/24，路由10.8.0.0/24；旧机默认网关10.60.0.1。未读取WireGuard私钥，不在报告显示peer key。容器host绑定依赖10.8.0.3已存在；新旧不可同时使用同一VPN身份/地址，实际切换须由统筹控制。

## 调度归属与保留运行语义

- root、ubuntu 均无crontab；ubuntu无user timer和运行中的user service。`/etc/cron.hourly` 只有placeholder；daily/weekly/monthly只有OS包维护。`/etc/cron.d` 只有certbot、e2scrub及placeholder。
- 系统timer：certbot、motd-news、systemd-tmpfiles-clean、dpkg-db-backup、logrotate、man-db、e2scrub_all、fstrim；未发现KataGo/Kifu/Golaxy/Smartbox/Pitch的host timer或unit文件。`atq`命令不可用，未据此声称无所有可能队列。
- 实际业务循环由 `katrain-ucloud-katrain-cron-1` 的 `python -m katrain.cron` 承担。保留仅分析env，不能因为容器名cron而启动新的同步器。
- exited的minio-setup、kifu-init、kifu-importer维持停止语义；Pitch API实际启动命令含alembic upgrade，应在迁移计划中作为明确写入边界处理。Pitch三个应用容器及PG实际restart=no，不应未经判断改成新的自动调度。

## 精选可迁移清单与可排除项

必要迁移：上表运行态16个唯一不可变镜像（明确排除三个exited容器/任务及mc镜像）、八个现用volume、四个仍存在的bind源、Nginx及所有已加载include、Let’s Encrypt目录和ACME配置、WireGuard私有配置/身份（受控切换），以及权威inspect中的环境变量/HostConfig/network alias等私有参数。统一admin、Go admin、platform SSO的session/service/bridge/ranked等密钥只能从私有来源恢复，不重新生成后声称会话可无损延续。

可不复制到新盘（不删除旧机）：未被这20个容器使用的历史image/tag/build cache、未被现用bind引用的旧releases/source/checkouts、旧日志/apt cache、无链接的匿名volume约784.8MB、无链接的preview-state/old-state小volume。主PG内preview/baseline数据库不在该排除列表中。原始compose labels含大量历史overlay和/tmp路径，部分已失效；新运行定义应仅以17 running容器的实际inspect和以上必要路径为准，不能直接重跑旧overlay串。

**明确excluded：`katrain-ucloud-minio-setup-1`、`smartbox-kifu-init-1`、`smartbox-kifu-importer-1`。** 这些任务均未运行，不属于新机在线恢复启动集合。

缺口：停止态importer的原image已缺失、停止态minio-setup的bootstrap bind源已缺失；若必须复刻这两个历史批处理，需要另找归档/源码并单独复核，不能作为恢复在线服务的先决条件，也不能启动替代采集。


## Bounded follow-up: writable layers of all 17 online containers

Collection UTC: 2026-10-26T19:12:52.694877+00:00. Old hostname was verified. All 17 docker diff calls succeeded; 768 changed-path markers, zero deleted-path markers. Only metadata was inspected. No data/kifu-album, SGF, or model directory was traversed or read; no DB/role/capacity queries or old/new container writes or jobs were performed.

| Container | Diff path markers | Extra application source/static files required |
| --- | --- | --- |
| katrain-ucloud-katrain-web-1 | 193 | 0 |
| smartbox-admin-admin-console-1 | 0 | 0 |
| smartbox-platform | 98 | 0 |
| katrain-ucloud-katrain-admin-1 | 17 | 0 |
| katrain-ucloud-katrain-cron-1 | 87 | 0 |
| katrain-ucloud-katago-cron-1 | 160 | 0 |
| pitch-booking-caddy-1 | 8 | 0 |
| pitch-booking-worker-1 | 12 | 0 |
| pitch-booking-api-1 | 12 | 0 |
| katrain-ucloud-katago-web-1 | 141 | 0 |
| platform-postgres | 4 | 0 |
| pitch-booking-postgres-1 | 4 | 0 |
| katrain-ucloud-minio-1 | 5 | 0 |
| smartbox-kifu-api-1 | 2 | 0 |
| smartbox-kifu-api-b-1 | 4 | 0 |
| smartbox-kifu-postgres-1 | 6 | 0 |
| katrain-ucloud-postgres-1 | 15 | 0 |

Application directories and source/UI/config candidates included .py/.js/.css/.html/.svg/.map/.wasm/.woff/.env/.json/.yaml/.yml/.ini/.toml/.sh. Directory parent markers do not imply changes to their application files. No extra business source, UI static files, runtime .env files, or unmounted business progress files were found beyond the migrated images, eight volumes, four binds, and the cron backups already checked by another agent.

- Go admin: generated /home/katrain/.kivy/config.ini (1,371 bytes, seven sections, 60 keys) and nine Kivy framework icons. These are framework user files, not the admin UI build. The actual INI was exported privately; the generated icons need not be restored for the Web admin.
- Pitch Caddy: /config/caddy/autosave.json (479 bytes), instance UUID, cleanup timestamp, and locks directory. The actual autosave has only :8080, /api/* and /platform-admin* forwarding to api:8000, and the 404 fallback, matching the migrated bind Caddyfile routes. No additional TLS or business routes were found. Autosave was exported privately; UUID/cleanup/locks are housekeeping state.
- Cron: /app/data/tutorial_backups contains the 14 backups (about 16 MB) already checked by another agent; this task did not re-read or export them. Temporary deployment manifests and credentials were skipped.
- GPU caches, NVIDIA injected files, analysis_logs, .cache, __pycache__, other logs and temporary paths were excluded. MinIO only added empty certificate-directory markers, with no unmounted certificate-file changes.

Private metadata: old-online17-diff.private.json and old-online17-diff-classified.private.json in runtime-inventory. Fixed-path exports from the actual running old containers:

| Old container source file | Private archive basename | File SHA-256 |
| --- | --- | --- |
| katrain-ucloud-katrain-admin-1:/home/katrain/.kivy/config.ini | admin-kivy-config.private.tar | 0d43d56e6e9b189844d70303964470b1b43acd244e077e5cfff62f0fad1880e7 |
| pitch-booking-caddy-1:/config/caddy/autosave.json | pitch-caddy-autosave.private.tar | 9273e5641e264ce9f6ac9504afe621c556cc4d83fcf0ea70e50334634a3db29b |

Archive SHA-256, member mode/uid/gid and byte counts are in runtime-fixed-config-exports.private.json. All archives were written only on the Mac under the private runtime-inventory directory. The controller can restore a confirmed-needed configuration file from these actual-container exports; image defaults were not substituted.
