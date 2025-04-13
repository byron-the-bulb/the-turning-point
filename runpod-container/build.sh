#!/bin/bash
set -e

# Script to build the Sphinx Voice Bot Docker image for RunPod

# Configuration
IMAGE_NAME="sphinx-voice-bot"
TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

echo "Building ${FULL_IMAGE_NAME}..."

# Build the Docker image
docker build -t ${FULL_IMAGE_NAME} .

echo "Build complete!"
echo ""
echo "You can test it locally with:"
echo "docker run -p 8000:8000 \\"
echo "  -e DAILY_ROOM_URL=\"https://your-domain.daily.co/room-name\" \\"
echo "  -e DAILY_TOKEN=\"your-daily-token\" \\"
echo "  -e HUME_API_KEY=\"your-hume-api-key\" \\"
echo "  ${FULL_IMAGE_NAME}"
echo ""
echo "To push to DockerHub (after docker login):"
echo "docker tag ${FULL_IMAGE_NAME} yourusername/${IMAGE_NAME}:${TAG}"
echo "docker push yourusername/${IMAGE_NAME}:${TAG}"
