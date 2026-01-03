FROM nvcr.io/nvidia/tensorrt:23.03-py3

# Install dependencies and setup mirrors
RUN sed -i "s|http://archive.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g" /etc/apt/sources.list && \
    sed -i "s|http://security.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g" /etc/apt/sources.list
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy source
COPY . /app

# Install Python dependencies using the same mirror and flags as KataGo Dockerfile
RUN python3 -m pip install --trusted-host pypi.tuna.tsinghua.edu.cn -i https://pypi.tuna.tsinghua.edu.cn/simple --default-timeout=100 --no-cache-dir --upgrade pip && \
    python3 -m pip install --trusted-host pypi.tuna.tsinghua.edu.cn -i https://pypi.tuna.tsinghua.edu.cn/simple --default-timeout=100 --no-cache-dir -r /app/requirements.txt

# Set headless environment for Kivy
ENV KIVY_NO_WINDOW=1
ENV PYTHONPATH=/app

# Expose KaTrain Web UI port
EXPOSE 8001

# Start the Web UI by default, binding to all interfaces for Docker access
CMD ["python3", "-m", "katrain", "--host", "0.0.0.0", "--port", "8001"]
