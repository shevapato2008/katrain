# The base digest is the tested CUDA 12.4/cuDNN 9 runtime. The official KataGo
# binary itself is built for CUDA 12.1 and needs a compatible NVIDIA driver.
FROM docker.m.daocloud.io/nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04@sha256:2fcc4280646484290cc50dce5e65f388dd04352b07cbe89a635703bd1f9aedb6

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip libssl3 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY realtime_api/ /app/python/realtime_api/
COPY config.yaml /opt/katago/config.yaml
COPY engine/katago /opt/katago/katago
COPY engine/analysis_example.cfg /opt/katago/analysis_example.cfg
RUN chmod +x /opt/katago/katago && mkdir -p /opt/katago/models

ENV PYTHONPATH=/app/python \
    KATAGO_CONFIG_FILE=/opt/katago/config.yaml \
    APPIMAGE_EXTRACT_AND_RUN=1 \
    REALTIME_API_WARMUP_TIMEOUT=1800
EXPOSE 8000
CMD ["python3", "-m", "realtime_api.main"]
