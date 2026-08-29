# 只在现役镜像上叠一层:新的 realtime_api(能力载荷 schema-1 + 多模型路由 + 预热后才 ready)、
# 多模型 config.yaml、以及 b18 权重。**不重编 katago、不拉基础镜像** —— ucloud 上外网时通
# 时断,一次真正的重建很可能中途停死,而现役镜像一旦被覆盖就没有退路。
ARG BASE
FROM ${BASE}
COPY realtime_api/ /app/python/realtime_api/
COPY config.yaml /app/config.yaml
COPY kata1-b18c384nbt-s9996604416-d4316597426.bin.gz /app/models/
ENV REALTIME_API_WARMUP_TIMEOUT=1800
