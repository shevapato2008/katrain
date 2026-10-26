# UCloud 新 staging GPU 真实验收

日期：2026-10-27（Asia/Shanghai）。只操作新 staging；旧生产 GPU、DNS、Docker daemon、数据库和对象存储均未改动。验收完成时间为 UTC 2026-10-26 18:06:41，即北京时间 2026-10-27 02:06:41。

## 结论

**通过。原样迁入的两份 GPU 镜像在新驱动上已同时运行并完成真实推理，无需修复或容器停启。**

| 服务 | 实际版本 | 健康与模型状态 | 空 19 路真实推理 |
| --- | --- | --- | --- |
| Web 引擎，loopback 8000 | KataGo v1.16.4，TensorRT | HTTP 200；b28、b18 均 running / warm / ready；error_code=null | 唯一一次 POST /analyze 返回 200，约 6 ms，最终 rootInfo.visits=1 |
| TF 引擎，loopback 8002 | KataGo v1.18.2，CUDA 12.1.105 | HTTP 200；tf3-b11c768 running / warm / ready；error_code=null | 唯一一次 POST /analyze 返回 200，约 22 ms，最终 rootInfo.visits=1 |

两容器最终 Docker health 均 healthy、restartCount=0、OOMKilled=false。V100 总显存 16384 MiB，所有模型同时 warm 后占用 1880 MiB、GPU 利用率 0%。探针期间以 200 ms 间隔采到 2 个样本，观察峰值 1880 MiB；请求很短，此采样不能代表首次 TensorRT 构建峰值。

## 早先 503 的定位

接手后的第一份实际健康采样已经 HTTP 200：b28 已 ready，b18 仍 warming_normal；随后 b18 也自然完成。未取得历史 503 的原始 body，因此不声称实测到其具体历史 phase/error 值。

实际镜像源码确认：/health 的顶层 ready 与 HTTP 503 由默认模型的 warmup 状态门控，次模型在后台 warmup。私有日志的分类时序显示，Web 引擎在 UTC 17:49:26 开始 TensorRT 构建流程；timing cache 在 17:56:33、17:57:33、18:04:21 和 18:04:36 写入；b28 在 18:04:21.939、b18 在 18:04:36.835 完成 warmup。相对启动约 14 分 57 秒、15 分 12 秒。

这支持“首次 TensorRT 调优与缓存生成耗时”的判断。未发现 OOM、权限拒绝或缺失文件的日志证据，随后所有模型自然 ready 且真实推理成功。没有执行建议中的临时停止 TF 引擎，也没有变更运行 payload、配置或模型。

## 请求范围与验收语义

先分别读取两个运行服务的 /openapi.json，再读取原镜像中的请求处理源码，核实协议。请求为无落子、无初始子、19×19、Chinese、komi=7.5、analyzeTurns=[0]、maxVisits=1、includePolicy=false、includeOwnership=false；没有 gameId/userId。只请求两个默认模型，各一次，read timeout 为 90 秒，顺序执行。

每次推理前确认全部模型 warm/ready、GPU 利用率 0%，且没有连接到模型 API 的已建立 TCP 调用者。统筹另确认新 staging 的业务 cron / Pitch worker 未创建，receiver 的 active authorized_keys 为空，公网 nginx / VPN masked，无真实用户 GPU 任务。

响应均为 isDuringSearch=false、turnNumber=0、rootInfo.visits=1，winrate / scoreLead / utility 为有限数值，无 error。maxVisits=1 时 moveInfos=[] 仍有实际根节点评估；初版检查中过强的“moveInfos 必须非空”断言已按实际响应纠正，只离线重验已有响应，没有重复发送 Web 请求。

此验收覆盖两服务默认模型的各一次推理，以及三个模型同时 warm / ready。未追加 b18 或 human override 推理，未测试业务调用链、并发容量或长期稳定性。

## 原始身份与模型校验

| 对象 | SHA-256 |
| --- | --- |
| Web 原镜像 | efdeb9de4f64faf68072d236a3f73ff5c1f38af9566d78a52af78ec03f3026f3 |
| TF 原镜像 | b242fd2a379b28b7dda5cf965e41230324bc825e7d23cd4aa1c0c81f7a16798e |
| b28 | 798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0 |
| b18 | 9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d |
| humanv0 | 637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5 |
| tf3-b11c768 | 93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871 |

健康响应的 model_sha256_verified 均为 true；Web 的 human_model_sha256_verified 也为 true。宿主 NVIDIA driver 为 580.178.04。

## 证据保管

原始日志、原始 inspect、源码、OpenAPI、健康响应与合成空棋盘请求/响应只保存在新机 root 私有目录 `/var/lib/ucloud-migration-20261027/gpu-preflight/`。目录权限已检查为 0700，30 个证据文件均为 0600。没有把原始日志或 Env 复制到本地公开报告，没有上传用户棋局，也没有访问公网 LLM。

唯一运行性操作是上述两个有界推理请求；其余为只读检查和私有验收证据落盘。

## Final 重建前的当前 TensorRT 缓存保全

本节为后续追加。仅只读检查、导出已验证运行容器的当前必要缓存，没有停启容器、提交新 image、改 payload / 模型或追加推理。

Web 容器没有持久化挂载。实际日志引用且 docker diff 标记为本次新增的缓存只有以下 3 个；TF 容器的 `/root/.nv/ComputeCache` 经检查为空，不导出。没有扫描或搬运其他历史缓存。

全部文件原路径前缀为 `/root/.katago/trtcache/`，owner 为 **0:0**、mode 为 **0644**。原 `/root/.katago/` 和 `trtcache/` 目录均为 owner 0:0、mode 0755。

| 文件名 | 字节数 | SHA-256 |
| --- | --- | --- |
| trt-8503_gpu-e623a2f6_tune-04e4d48f9167_max19x19_batch64_fp16 | 247831 | 3690a1138b0a6c78d4f99e0a5879b87b690e112229e0e34cc8c2b52a4500f7d8 |
| trt-8503_gpu-e623a2f6_tune-63eb38c37b0b_max19x19_batch64_fp16 | 260935 | 143a2e48b5c11eea0cb1b486ff24ae57ef89d222f8d86b63c6750cb74fcda902 |
| trt-8503_gpu-e623a2f6_tune-d32769ca7234_max19x19_batch64_fp16 | 306279 | 9bb753a499749b71e665c066cc3eed3dc4e69e505ddbf032a7041964b3d196d8 |

总计 **815045 bytes**。读取 `/proc/*/fd` 与对应 flags 确认没有缓存写句柄；源文件在导出前后哈希一致。逐个使用 `docker cp -a` 只读源导出，未复制任何模型或运行程序。

新机 root 私有导出目录为 `/var/lib/ucloud-migration-20261027/gpu-preflight/current-cache/`，目录与 `files/` 为 0700，所有导出文件为 0600：

- `files/<上表文件名>`：三个独立文件，内容哈希见上表。
- `manifest.json`：源 stat、原始权限、哈希、精确 image、模型校验值、运行配置校验值及 GPU / driver 绑定信息。GPU UUID 只保留于此私有清单。
- `restore-web-trtcache.tar`：**829440 bytes**，SHA-256 **0c6b1b3169818ea37e488a17d38925e09bc6761e46bba8c8cec023d04b34eb49**。归档内仅两个相对目录 `.katago/`、`.katago/trtcache/` 和上述三个普通文件，已离线逐项验证权限与内容哈希。

复用条件为同一新机物理 V100、同一 driver 580.178.04、同一 Web image `sha256:efdeb9de4f64faf68072d236a3f73ff5c1f38af9566d78a52af78ec03f3026f3`、本报告所列 b28 / b18 / human 模型内容，以及运行中的 `/app/cpp/configs/server_analysis.cfg` 内容保持不变。该配置为 22783 bytes，SHA-256 `162a19384d768680cd47d43b1f9e89cc3f8d6a5e7295e646a936b28130d0b69e`。只恢复给新建的 **Created Web GPU 容器，且必须在首次 start 前**；不恢复到 TF 容器。仅 VPN 端口绑定与 restart 策略恢复不改变这些绑定条件。

统筹可在新机 root Python 中用以下核心操作恢复，`created_web_name` 为已经核实 image 相同且 State.Status 为 `created` 的新 Web 容器名称：

```python
archive = "/var/lib/ucloud-migration-20261027/gpu-preflight/current-cache/restore-web-trtcache.tar"
with open(archive, "rb") as cache_input:
    subprocess.run(
        ["docker", "cp", "-a", "-", created_web_name + ":/root/"],
        stdin=cache_input,
        check=True,
    )
```

归档相对 `/root/` 展开，所以最终文件路径与上表源路径完全相同；`-a` 保留包内 uid / gid。[Docker 官方 cp 文档](https://docs.docker.com/reference/cli/docker/container/cp/)明确支持向运行或停止的容器复制，并支持从 stdin 解包 tar 到已有目录。

这些是 **timing / tuning cache**，没有发现需要导出的单独 serialized engine cache。复用可能减少重复 tactic 调优，但不保证完全跳过 TensorRT 构建或零冷启动。重建、恢复、启动和最终健康复验由统筹执行，本任务没有提前对运行容器导入任何内容。
