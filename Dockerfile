FROM nvcr.io/nvidia/tensorrt:24.02-py3

# Install dependencies and setup mirrors
RUN sed -i "s|http://archive.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g" /etc/apt/sources.list && \
    sed -i "s|http://security.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g" /etc/apt/sources.list
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    git \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libavcodec-dev \
    libavformat-dev \
    libglib2.0-0 \
    libgl1-mesa-dev \
    libgl1-mesa-glx \
    libgstreamer1.0-0 \
    libmtdev1 \
    libportmidi-dev \
    libpulse0 \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libswscale-dev \
    libzip-dev \
    ocl-icd-opencl-dev \
    opencl-headers \
    pkg-config \
    python3-dev \
    python3-pip \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy source
COPY . /app

# Install Python dependencies using the same mirror and flags as KataGo Dockerfile
RUN python3 -m pip install --trusted-host pypi.tuna.tsinghua.edu.cn -i https://pypi.tuna.tsinghua.edu.cn/simple --default-timeout=100 --no-cache-dir --upgrade pip && \
    python3 -m pip install --trusted-host pypi.tuna.tsinghua.edu.cn -i https://pypi.tuna.tsinghua.edu.cn/simple --default-timeout=100 --no-cache-dir \
    -r /app/requirements-web.txt \
    -r /app/requirements-desktop.txt

ENV PYTHONPATH=/app
ENV KATRAIN_UI=web
ENV KATRAIN_HOST=0.0.0.0
ENV KATRAIN_PORT=8001

# Expose KaTrain Web UI port
EXPOSE 8001

# Start the Web UI by default, binding to all interfaces for Docker access
CMD ["/bin/bash", "-lc", "if [ \"$KATRAIN_UI\" = \"desktop\" ]; then exec python3 -m katrain --ui desktop; else exec python3 -m katrain --host \"${KATRAIN_HOST}\" --port \"${KATRAIN_PORT}\"; fi"]
