# Builder Stage: Compile CTranslate2 with CUDA 11.8 support
FROM nvidia/cuda:11.8.0-devel-ubuntu22.04 AS builder

# Install basic dependencies and tools for adding Intel oneAPI repository
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add Intel oneAPI repository for OpenMP
RUN wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list && \
    apt-get update

# Install build dependencies including Intel OpenMP
RUN apt-get install -y --no-install-recommends \
    git \
    cmake \
    g++ \
    python3.10 \
    python3.10-dev \
    python3-pip \
    intel-oneapi-openmp \
    && rm -rf /var/lib/apt/lists/*

# Install Python build tools
RUN pip3 install --no-cache-dir setuptools wheel

# Clone CTranslate2 with submodules
RUN git clone --recursive https://github.com/OpenNMT/CTranslate2.git /ctranslate2

WORKDIR /ctranslate2

# Build CTranslate2 with CUDA support
RUN mkdir build && cd build && \
    cmake .. -DWITH_CUDA=ON -DCUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda && \
    make -j$(nproc)

# Create a Python wheel for CTranslate2
RUN python3 setup.py bdist_wheel

# Runtime Stage: Create the final lightweight image
FROM nvidia/cuda:11.8.0-base-ubuntu22.04

# Set working directory
WORKDIR /app

# Install basic dependencies and tools for adding Intel oneAPI repository
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add Intel oneAPI repository for OpenMP runtime
RUN wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list && \
    apt-get update

# Install runtime dependencies including Intel OpenMP runtime
RUN apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    ffmpeg \
    libsndfile1 \
    libsm6 \
    libxext6 \
    intel-oneapi-runtime-openmp \
    && rm -rf /var/lib/apt/lists/*

# Copy the CTranslate2 wheel from the builder
COPY --from=builder /ctranslate2/dist/*.whl /tmp/

# Copy requirements.txt
COPY requirements.txt .

# Install CTranslate2, faster-whisper, and other Python dependencies
RUN pip3 install --no-cache-dir /tmp/*.whl faster-whisper -r requirements.txt && \
    rm /tmp/*.whl

# Create directories for whisper models
RUN mkdir -p /root/.cache/whisper

# Download and cache the Whisper medium model
RUN wget -q https://openaipublic.azureedge.net/main/whisper/models/345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1/medium.pt -O /root/.cache/whisper/medium.pt

# Verify model is properly downloaded and can be loaded with faster-whisper
RUN python3 -c "from faster_whisper import WhisperModel; model = WhisperModel('medium'); print('Successfully loaded faster-whisper medium model')"

# Copy application code
COPY . .

# Create an entry point script that accepts environment variables
RUN echo '#!/bin/bash\n\
python3 -m sphinx_bot \
    -u "${DAILY_ROOM_URL}" \
    -t "${DAILY_TOKEN}" \
    -i "${IDENTIFIER}" \
    ${TTS_CONFIG:+-d "${TTS_CONFIG}"}\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Command to run when container starts
ENTRYPOINT ["/app/entrypoint.sh"]