FROM python:3.12-slim

WORKDIR /app

ENV GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git
ENV PYTHONUNBUFFERED=1

# Install system dependencies + Node.js 20
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    build-essential \
    libssl-dev \
    curl \
    gnupg \
    cmake \
    g++ \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libpostproc-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy everything else
COPY . .

# Run the bot
CMD ["python3", "-m", "KHUSHI"]
