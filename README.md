# demo-ci-cd

静态页面 + GitHub Actions CI/CD：push 后自动**构建 Docker 镜像**并可选**部署到服务器**。

## 流程概览

- **Build**（`.github/workflows/build.yml`）：每次 push 到 `main`/`master` 时，构建镜像并推送到 [GHCR](https://ghcr.io)。
- **Deploy**（`.github/workflows/deploy.yml`）：独立 workflow，可**手动触发**，或在 Build 成功完成后**自动触发**；通过 SSH 登录服务器，拉取最新镜像并重启容器。

## 本地试跑

```bash
# 构建
docker build -t demo-ci-cd .

# 运行（本地访问 http://localhost:8080）
docker run -p 8080:80 demo-ci-cd
```

## Build workflow

- 无需额外配置，push 后自动运行。
- 镜像会推送到：
  - `ghcr.io/<你的用户名>/demo-ci-cd:latest`
  - `ghcr.io/<你的用户名>/demo-ci-cd:<git-sha>`

在仓库 **Settings → Actions → General** 里将 **Workflow permissions** 设为 “Read and write permissions”。

## Deploy workflow

需要一台已安装 Docker 的 Linux 服务器。在**服务器上**先登录 GHCR（拉取镜像用）：

```bash
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

在仓库 **Settings → Secrets and variables → Actions** 里配置：

| Secret 名称        | 说明             |
|--------------------|------------------|
| `DEPLOY_HOST`      | 服务器 IP 或域名   |
| `DEPLOY_USER`      | SSH 登录用户名     |
| `SSH_PRIVATE_KEY`  | 部署用 SSH 私钥    |

**触发方式：**

1. **手动**：Actions 页选择 “Deploy” workflow → “Run workflow”。
2. **自动**：Build workflow 成功完成后会自动触发 Deploy。

## 文件说明

- `index.html`：静态页面
- `Dockerfile`：基于 nginx 提供静态资源
- `.github/workflows/build.yml`：构建并推送镜像
- `.github/workflows/deploy.yml`：部署到服务器
