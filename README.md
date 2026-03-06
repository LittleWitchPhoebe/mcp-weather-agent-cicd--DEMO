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

Deploy 通过 **SSH** 连到你的服务器，在服务器上执行 `docker pull` + `docker run`，无需在 GitHub 里存服务器密码，只需配好 SSH 密钥和主机信息即可“自己和服务器联通”。

### 阿里云服务器配置步骤

#### 1. 安全组放行端口

在 阿里云控制台 → ECS → 安全组 → 配置规则 中放行：

- **22**（SSH）：供 GitHub Actions 登录。
- **80**（HTTP）：供浏览器访问页面。

#### 2. 在服务器上安装 Docker

SSH 登录到阿里云（用控制台 VNC 或本地 `ssh root@你的公网IP`），执行：

```bash
# 以 root 或 sudo 执行
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker
```

#### 3. 服务器上登录 GHCR（拉取镜像用）

若仓库或镜像是私有的，在服务器上执行一次（PAT 需勾选 `read:packages`）：

```bash
echo "你的GitHub_PAT" | docker login ghcr.io -u 你的GitHub用户名 --password-stdin
```

公开镜像可跳过本步。

#### 4. 生成 SSH 密钥并配置到服务器

在**你本机**执行（不要设密码，直接回车两次，便于 CI 使用）：

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deploy_demo_ci_cd -N ""
```

- 把**公钥**写入服务器（将下面 `你的公网IP` 换成实际 IP）：

```bash
ssh-copy-id -i ~/.ssh/deploy_demo_ci_cd.pub root@你的公网IP
```

- 若没有 `ssh-copy-id`，可手动在服务器上执行：

```bash
# 在服务器上
mkdir -p ~/.ssh
echo "这里粘贴 deploy_demo_ci_cd.pub 的内容" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### 5. 在 GitHub 仓库配置 Secrets

仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：

| Secret 名称        | 值 |
|--------------------|----|
| `DEPLOY_HOST`      | 阿里云 ECS 的**公网 IP**（或已解析到该机的域名） |
| `DEPLOY_USER`      | SSH 登录用户名（阿里云一般为 `root`） |
| `SSH_PRIVATE_KEY`  | 本机 `~/.ssh/deploy_demo_ci_cd` 文件的**全部内容**（含 `-----BEGIN ... KEY-----` 和 `-----END ... KEY-----`） |

保存后，Deploy workflow 会用这些信息**自己**和服务器联通并部署。

#### 6. 触发部署

- **手动**：Actions → 选择 “Deploy” → “Run workflow”。
- **自动**：Build 成功后会触发 Deploy。

部署成功后访问：**`http://你的公网IP`**（80 端口）。

## 文件说明

- `index.html`：静态页面
- `Dockerfile`：基于 nginx 提供静态资源
- `k8s/deployment.yaml`、`k8s/service.yaml`：Kubernetes 清单（供 Minikube 等使用）
- `scripts/minikube-deploy.sh`：本地 Minikube 一键部署脚本
- `.github/workflows/build.yml`：构建并推送镜像
- `.github/workflows/deploy.yml`：部署到远程服务器（SSH + Docker）
