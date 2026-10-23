# 两云大厅领地 API 后端覆盖部署回执

2026-10-23；source develop：`0ac3190d8a114403f35d37ffd76c34caaa31825b`；Smartbox gitlink：`a87024e2`。

两台 API 均已 ready。此次各自基于现役本地镜像，仅覆盖 `server.py` 与 `core/pvp_territory.py`。镜像标签和 manifest 明确 `backend-overlay`、source SHA、原 base image ID 和两文件实际 SHA256。**云端 static UI 保持原版；不是整棵新 release 的部署。**

| 主机 | 项目 / web 容器 | 新 image ID | 切换完成（UTC） |
| --- | --- | --- | --- |
| home-ubuntu | `katrain` / `katrain-web` | `sha256:cf26206cf6d51560ccd276ae0af9f42d99c8b8d76f0f7ca01559c3cbed0f31c2` | 2026-10-23T13:08:28.019701+00:00 |
| ucloud-v100 | `katrain-ucloud` / `katrain-ucloud-katrain-web-1` | `sha256:b4f36e32127420656266e1cd53417375075bd3d1bacd3a7ada8a7ddaf3c5d4ae` | 2026-10-23T13:10:47.611378+00:00 |

两站均通过候选镜像真实 Python import、OpenAPI POST 和隔离 ASGI 认证检查；候选禁止网络、根只读、内存 SQLite，未启动 lifespan。切换命令仅 `up -d --no-deps --no-build --pull never katrain-web`。

部署后确认：

- 本机及公网 health 200，`status=ok`、local engine reachable，语义版本仍 `1.17.1`；版本号不是 source SHA。
- 本机及公网 OpenAPI 有 `POST /api/pvp/territory`；未认证 POST 均为 401，已从原 404 正确切换。
- 容器实际两文件 SHA256 与固定 source 完全一致；运行 image ID、build SHA、overlay manifest 一致。
- 环境仅 `KATRAIN_BUILD_SHA` 变更；挂载完全一致；原三份 compose 配置未修改；GPU、cron、DB、MinIO、admin 及其他容器 ID/start time 均未变化。
- 两种 static index 的部署前后 hash 完全相同，frontend SHA 仍 `2aa81b37d659ccd47410ece88ab4f92a778a5ae5`。
- 独立未登录 Chrome 实际读取下列四页：Galaxy 模式选择、kiosk 在线大厅登录门均正常渲染。仅预期的 `/api/v1/auth/me` 401；无登录、账户创建、对局创建或真实领地/GPU 请求。

实际公开页面：

- https://go.sailorvoyage.top/galaxy/play
- https://go.sailorvoyage.top/kiosk/play/pvp/lobby
- https://modelstella.com/galaxy/play
- https://modelstella.com/kiosk/play/pvp/lobby

固定源文件 SHA256：

```text
server.py       d7525ae106b1fc1347565231902fe4340b28572065135a5fbfd8a06575c2315a
pvp_territory.py 8bdc390ac039b23b4b09f325e4ade41e1595f2d1dfd65ebc598d69a257b5ba52
```

独立核对示例（不输出 secret）：

```sh
ssh home-ubuntu 'docker exec katrain-web sha256sum /app/katrain/web/server.py /app/katrain/web/core/pvp_territory.py'
ssh ucloud-v100 'docker exec katrain-ucloud-katrain-web-1 sha256sum /app/katrain/web/server.py /app/katrain/web/core/pvp_territory.py'
ssh home-ubuntu 'curl -fsS http://127.0.0.1:8001/api/v1/health'
ssh ucloud-v100 'curl -fsS http://127.0.0.1:8001/api/v1/health'
curl -fsS https://go.sailorvoyage.top/api/v1/health
curl -fsS https://modelstella.com/api/v1/health
```

完整 base image ID/RepoDigests、新 image ID、实际 manifest/hash、所有保留服务身份、环境/挂载指纹及更多可执行复核命令见同目录 JSON 回执。Home 原 base 无 RepoDigest；PROD 原 RepoDigest 已按本地 inspect 原样记录，未声称存在可拉取的远端 registry 发布。

发布目录：home `/mnt/disk1/fan/lobby-backend-overlay-0ac3190d8-20261023`；PROD `/home/ubuntu/lobby-backend-overlay-0ac3190d8-20261023`。每台目录都有 baseline、候选与部署回执、两源文件、Dockerfile、构建日志、manifest 和仅 image/build SHA 的尾部 override。原三份快照与 rollback 镜像 tag 均保留；若回滚，使用原 project/directory/三文件并省略新 override，仅 web `up -d --no-deps --no-build --pull never katrain-web`。

未执行 Git push、导入/同步、数据迁移或其他主机操作。未验收登录后真实棋局/领地结果；RK 激活和设备验收由 controller 负责。
