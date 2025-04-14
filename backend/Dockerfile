# Use CUDA 12.1 base image for runtime
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Set working directory
WORKDIR /app

# Install basic dependencies and tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    python3.10 \
    python3-pip \
    ffmpeg \
    libsndfile1 \
    libsm6 \
    libxext6 \
    libcudnn9-cuda-12 \
    libcublas-12-1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt
COPY requirements.txt .

# Install CTranslate2, faster-whisper, and other Python dependencies
RUN pip3 install --no-cache-dir ctranslate2 faster-whisper -r requirements.txt

# Create directories for whisper models
RUN mkdir -p /root/.cache/whisper

# Download and cache the Whisper medium model
RUN wget -q https://openaipublic.azureedge.net/main/whisper/models/345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1/medium.pt -O /root/.cache/whisper/medium.pt

# Verify model is properly downloaded and can be loaded with faster-whisper
RUN python3 -c "from faster_whisper import WhisperModel; model = WhisperModel('medium'); print('Successfully loaded faster-whisper medium model')"

# Copy application code from the sphinx-bot directory
COPY src/sphinx-bot/ /app/

# Copy the pod termination script
COPY scripts/terminate_pod.sh /app/
# Make the termination script executable
RUN chmod +x /app/terminate_pod.sh

# Create an entry point script that accepts environment variables
RUN echo '#!/bin/bash\n\
python3 -m sphinx_bot \
    -u "${DAILY_ROOM_URL}" \
    -t "${DAILY_TOKEN}" \
    -i "${IDENTIFIER}" \
    ${TTS_CONFIG:+-d "${TTS_CONFIG}"}\n\
# Shut down the RunPod container when the process exits\n\
/app/terminate_pod.sh\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Command to run when container starts
ENTRYPOINT ["/app/entrypoint.sh"]