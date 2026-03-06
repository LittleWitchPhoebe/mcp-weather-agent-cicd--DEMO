#!/usr/bin/env bash
# 在本地用 Minikube 部署：构建镜像并 apply k8s 清单
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ">>> 使用 Minikube 的 Docker 环境构建镜像..."
eval "$(minikube docker-env)"
docker build -t demo-ci-cd:latest "$REPO_ROOT"

echo ">>> 部署到 Minikube..."
kubectl apply -f "$REPO_ROOT/k8s/"

echo ">>> 等待 Pod 就绪..."
kubectl rollout status deployment/demo-ci-cd --timeout=120s

echo ""
echo ">>> 访问方式："
echo "   NodePort: minikube service demo-ci-cd --url"
echo "   或直接:   http://$(minikube ip):30080"
echo ""
