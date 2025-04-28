#!/bin/bash
set -e

# 使用环境变量或默认值
IMAGE_NAME="awesome-epic"
TAG="${TAG:-llm}"
USERNAME="${USERNAME:-ech0sec}"
SKIP_PUSH="${SKIP_PUSH:-true}"

# 构建镜像
echo "Building Docker image ${IMAGE_NAME}:${TAG}..."
docker build -t ${IMAGE_NAME}:${TAG} -f docker/Dockerfile .

# 标记镜像
echo "Tagging image for Docker Hub..."
docker tag ${IMAGE_NAME}:${TAG} ${USERNAME}/${IMAGE_NAME}:${TAG}
docker tag ${IMAGE_NAME}:${TAG} ${USERNAME}/${IMAGE_NAME}:latest

# 如果不跳过推送，则推送镜像到Docker Hub
if [ "$SKIP_PUSH" != "true" ]; then
  echo "Pushing image to Docker Hub..."
  docker push ${USERNAME}/${IMAGE_NAME}:${TAG}
  docker push ${USERNAME}/${IMAGE_NAME}:latest
  echo "Publication completed successfully!"
else
  echo "Skipping push to Docker Hub (use --push to enable)"
fi

echo "Build completed successfully!"