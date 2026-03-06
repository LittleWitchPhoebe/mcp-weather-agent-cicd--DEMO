# demo-ci-cd

静态页面 + GitHub Actions CI/CD：push 后自动**构建 Docker 镜像**并可选**部署到服务器**。

## 流程概览

- **Build**（`.github/workflows/build.yml`）：每次 push 到 `main`/`master` 时，构建镜像并推送到 **阿里云个人版镜像仓库**（`test017/test-cicid`）。
- **Deploy**（`.github/workflows/deploy.yml`）：可**手动触发**或在 Build 成功后自动触发；当前为 SSH 到服务器并 docker 部署（可改为部署到本地 Minikube，见 `docs/`）。

## 本地试跑（Docker）

```bash
# 构建
docker build -t demo-ci-cd .

# 运行（本地访问 http://localhost:8080）
docker run -p 8080:80 demo-ci-cd
```

## 本地用 Minikube 部署

需要已安装 [Minikube](https://minikube.sigs.k8s.io/docs/start/) 和 kubectl。

**一键部署（在项目根目录执行）：**

```bash
minikube start   # 若未启动
./scripts/minikube-deploy.sh
```

脚本会：用 Minikube 内置 Docker 构建镜像 → 部署到集群 → 输出访问地址。

**访问页面：**

```bash
minikube service demo-ci-cd --url
# 或浏览器打开: http://$(minikube ip):30080
```

**手动步骤（可选）：**

```bash
eval $(minikube docker-env)
docker build -t demo-ci-cd:latest .
kubectl apply -f k8s/
kubectl rollout status deployment/demo-ci-cd
```

若要用 **GHCR 上的镜像** 而不是本地构建：在 `k8s/deployment.yaml` 里把 `image` 改成 `ghcr.io/<你的用户名>/demo-ci-cd:latest`，并创建拉取密钥后取消注释 `imagePullSecrets`：

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=你的GitHub用户名 \
  --docker-password=你的PAT
```

## Build workflow（推送到阿里云 ACR）

- **镜像仓库**：阿里云个人版，公网地址  
  `crpi-tdt2zc9s3n24ef5b.cn-hangzhou.personal.cr.aliyuncs.com/test017/test-cicid`  
  推送标签：`latest`、`sha-<7位commit>`
- **必须在 GitHub 配置 Secrets**（仓库 **Settings → Secrets and variables → Actions**）：
  - `ACR_USERNAME`：阿里云 ACR 登录用户名
  - `ACR_PASSWORD`：阿里云 ACR 登录密码
- **安全提醒**：请勿在代码或聊天中提交密码。若密码曾泄露，请在阿里云控制台修改 ACR 密码后，将新密码填入 `ACR_PASSWORD`。

## Deploy workflow（与服务器联通）

Deploy 通过 **SSH** 连到你的服务器，在服务器上执行 `docker login`（阿里云 ACR）→ `docker pull` → `docker run`。拉镜像用的 ACR 账号由 workflow 传入，**服务器上无需预先 docker login**。

### 一、服务器上需要做的（阿里云 ECS）

1. **安全组放行**：22（SSH）、80（HTTP）。
2. **安装 Docker**（SSH 登录后执行）：
   ```bash
   curl -fsSL https://get.docker.com | sh
   systemctl enable docker && systemctl start docker
   ```
3. **允许 root 用密码 SSH 登录**（若当前已是密码登录，可跳过）：  
   确认 `/etc/ssh/sshd_config` 中 `PasswordAuthentication yes`，然后 `systemctl restart sshd`。

### 二、GitHub 仓库里配置的 Secrets

仓库 **Settings → Secrets and variables → Actions** 中需有：

| Secret 名称       | 说明 | 示例 |
|------------------|------|------|
| `DEPLOY_HOST`    | 服务器公网 IP 或域名 | `8.136.38.236` |
| `DEPLOY_USER`    | SSH 登录用户名 | `root` |
| `SSH_PASSWORD`   | 服务器 SSH 登录密码（与 root 密码一致即可） | （你的 root 密码） |
| `ACR_USERNAME`   | 阿里云 ACR 用户名（Build 已用） | 同 Build |
| `ACR_PASSWORD`   | 阿里云 ACR 密码（Build 已用） | 同 Build |

- 若用 **SSH 密钥** 而不是密码：可不填 `SSH_PASSWORD`，改填 `SSH_PRIVATE_KEY`（私钥全文）。  
- **不要**把密码或私钥提交到代码里，只放在 GitHub Secrets 中。

### 三、触发部署

- **手动**：Actions → 选 “Deploy” → “Run workflow”。
- **自动**：Build 成功后会触发 Deploy。

部署成功后访问：**`http://8.136.38.236`**（或你的公网 IP，80 端口）。

## 文件说明

- `index.html`：静态页面
- `Dockerfile`：基于 nginx 提供静态资源
- `k8s/deployment.yaml`、`k8s/service.yaml`：Kubernetes 清单（供 Minikube 等使用）
- `scripts/minikube-deploy.sh`：本地 Minikube 一键部署脚本
- `.github/workflows/build.yml`：构建并推送镜像
- `.github/workflows/deploy.yml`：部署到远程服务器（SSH + Docker）
