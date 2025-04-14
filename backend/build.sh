#!/bin/bash
set -e

# Script to build the Sphinx Voice Bot Docker image

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
echo "docker run \\"
echo "  --gpus all \\"
echo "  -e DAILY_API_KEY=\"your_daily_api_key\" \\"
echo "  -e OPENAI_API_KEY=\"your_openai_api_key\" \\"
echo "  -e HUME_API_KEY=\"your_hume_api_key\" \\"
echo "  -e SPHINX_WHISPER_DEVICE=\"cuda\" \\"
echo "  -e AWS_ACCESS_KEY_ID=\"your_aws_access_key\" \\"
echo "  -e AWS_SECRET_ACCESS_KEY=\"your_aws_secret_key\" \\"
echo "  -e AWS_REGION=\"us-east-1\" \\"
echo "  -e CLOUDWATCH_LOG_GROUP=\"/sphinx-voice-bot\" \\"
echo "  ${FULL_IMAGE_NAME}"
echo ""
echo "To run without GPU (slower performance):"
echo "docker run -p 8000:8000 \\"
echo "  -e DAILY_API_KEY=\"your_daily_api_key\" \\"
echo "  -e OPENAI_API_KEY=\"your_openai_api_key\" \\"
echo "  -e HUME_API_KEY=\"your_hume_api_key\" \\"
echo "  -e SPHINX_WHISPER_DEVICE=\"cpu\" \\"
echo "  ${FULL_IMAGE_NAME}"
echo ""
echo "To push to DockerHub (after docker login):"
echo "docker tag ${FULL_IMAGE_NAME} yourusername/${IMAGE_NAME}:${TAG}"
echo "docker push yourusername/${IMAGE_NAME}:${TAG}"
