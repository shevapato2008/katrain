# UCloud 新机基础环境安装结果

2026-10-27 01:04:44（Asia/Shanghai）完成。目标为新 `ucloud-v100`。新机基础环境已就绪，已明确向迁移统筹释放新机独占写入窗口。旧机未连接、未修改。

## 安装结果

| 组件 | 实际安装版本 / 状态 |
| --- | --- |
| OS | Ubuntu 24.04 LTS，未升级发行版 |
| Kernel | 6.8.0-138-generic，安装前后及重启后保持一致 |
| NVIDIA driver | Ubuntu 源 `nvidia-driver-580-server=580.178.04-0ubuntu0.24.04.1` |
| NVIDIA DKMS / kernel source | 同版 580.178.04，`nvidia-srv/580.178.04` 对现有内核 installed |
| 内核模块类型 | `modinfo -F license nvidia` 实测 `NVIDIA`，专有模块 |
| Docker CE / CLI | `5:29.5.2-1~ubuntu.24.04~noble`，API 1.54 |
| containerd.io | `2.2.4-1~ubuntu.24.04~noble`，运行时 v2.2.4 |
| runc | 1.3.5 |
| Docker Compose plugin | `5.1.4-1~ubuntu.24.04~noble` |
| NVIDIA Container Toolkit 四包 | `nvidia-container-toolkit`、`nvidia-container-toolkit-base`、`libnvidia-container-tools`、`libnvidia-container1` 均 1.20.1-1 |
| Docker GPU runtime | 已通过 `nvidia-ctk runtime configure --runtime=docker` 配置；`nvidia` runtime 存在 |
| Docker 默认 runtime / storage | runc；overlayfs，`io.containerd.snapshotter.v1`，保留默认 |

Docker、containerd、runc 和 Compose 均与统筹提供的旧机实测版本精确匹配。驱动 apt update 后的现场候选从准备阶段的 580.173.02 更新到同一授权分支的 580.178.04；没有安装 open 模块、590+ 驱动或宿主机 CUDA Toolkit。

驱动安装先模拟：9 个必要依赖补丁、97 个新包、0 删除，没有新增 kernel/headers 或发行版升级。运行时安装先模拟：8 个新包、0 升级、0 删除。使用 `--no-install-recommends`，未安装 buildx 等非本次迁移所需插件，未执行全系统 upgrade。

## 重启与验收证据

- 仅执行一次新机重启。重启前后 boot_id 已变化，kernel 未变。
- 重启后继续启用严格 SSH 主机密钥校验；ED25519 SHA256 指纹与安装前已验证指纹相同。
- `docker` 与 `containerd` 服务均 active；重启后 nvidia runtime 仍存在。
- 宿主机 `nvidia-smi` 识别单块 Tesla V100-PCIE-16GB，16384 MiB，驱动 580.178.04。
- 使用 Canonical 官方 `public.ecr.aws/ubuntu/ubuntu:24.04` 小镜像，通过 `docker run --rm --runtime=nvidia --gpus all` 执行真实 `nvidia-smi`。
- 容器与宿主机的 `name,driver_version,memory.total,pci.bus_id,uuid` CSV 用 `cmp` 比较，结果完全一致、退出码 0。
- 镜像 ID / digest：`sha256:e700eff42bffb30b0aa37029e5a9083745fbb1fa86420711b2c9639b51fc77f7`。inspect size 为 29,771,493 字节；Docker 记录的本地镜像占用 117.4 MB。
- 检查结束 0 容器、0 volume、0 build cache。只保留上述诊断镜像，没有复制模型或启动业务 writer。
- `dpkg --audit` 没有输出。

## 磁盘

| 时点 | 根分区可用 |
| --- | --- |
| 安装前 | 约 94 GiB |
| 驱动 / Docker 安装并清理 apt 下载缓存后 | 约 92 GiB |
| 重启及 Ubuntu 容器验收后 | 98,601,836,544 字节，约 91.8 GiB |

`/boot` 最终可用 724,037,632 字节，约 690.5 MiB。没有创建镜像归档或模型临时副本。

## 已处理的安装与网络情况

1. 极简新机不存在 `/etc/apt/sources.list.d`，首次官方源配置退出。创建该标准目录（0755）后重试成功；首次失败日志保留。
2. 重启期间第一次重连被服务端 reset，下一次严格主机密钥验证连接成功。没有关闭 host key 检查。
3. 首次 Docker Hub 拉取 Ubuntu 24.04 因 registry TCP 超时失败，退出码 125，未创建容器。保留失败日志。
4. 只执行一次替代下载：Canonical 官方 ECR Ubuntu 24.04，设置 28 秒 TERM / 2 秒 KILL 硬上限，限时内成功并完成 GPU 验收。未修改 registry mirror、Docker 镜像源或 TLS 配置。

未修改 SSH 账户、认证方式或云防火墙，未购买资源。Docker 包安装产生其标准网络转发规则；没有为迁移额外修改网络策略。

## 私有原始证据

远端目录 `/var/lib/ucloud-migration-20261027/foundation/` 为 root 700，全部文件检查为 600。长安装通过 systemd transient unit 执行并由实施者持续监看；原始完整日志保留在该目录，没有复制到此脱敏报告。

主要文件：

- `00-baseline.log`：安装前系统、内核、指纹、GPU、磁盘。
- `01-apt-update.log`、`02-driver-candidates.log`、`03-driver-simulation.log`。
- `04-driver-install.log`：实际驱动安装、DKMS、版本和结果。
- `05-official-sources-attempt1-failed.log`、`05-official-sources.log`。
- `06-runtime-candidates.log`、`07-runtime-simulation.log`、`08-runtime-install.log`。
- `09-before-reboot.log`、`10-reboot-request.log`、`10-reconnect-note.log`、`11-after-reboot.log`。
- `12-container-gpu-dockerhub-failed.log`、`14-ecr-pull.log`、`12-container-gpu-verification.log`。
- `13-host-gpu.csv`、`13-container-gpu.csv`：逐字段比较证据。

## 后续迁移边界

基础环境与容器设备注入已验证。后续仍需原样导入旧 KataGo 镜像，验证 image ID/digest、真实推理、单卡同时运行资源与业务服务健康。本次完成结果不代替真实 KataGo 推理验收。

官方参考：[Docker Ubuntu 安装](https://docs.docker.com/engine/install/ubuntu/)、[NVIDIA Toolkit 安装与运行时配置](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)、[Ubuntu 官方 OCI registries 使用说明](https://ubuntu.com/docs/oci-registries/oci-how-to/getting-started/)。Docker 与 NVIDIA 安装方式同时通过 Context7 官方文档核对；具体版本以新机现场 apt 候选和安装结果为准。
