# demo-ci-cd

基于 **MCP（Model Context Protocol）** 的 Agent 练习项目，支持通过自然语言查询天气，并通过 **GitHub Actions** 实现 CI/CD：push 后自动构建镜像并部署到服务器。

## 项目说明

- **已实现**
  - **天气查询**：通过 MCP 工具调用 Open-Meteo 接口，可查询任意城市或经纬度的当前天气。
  - **Web 对话**：FastAPI 提供网页与 Agent 对话，支持多轮对话与工具调用。
  - **CI/CD**：Build workflow 构建镜像并推送到阿里云 ACR；Deploy workflow 通过 SSH 在服务器上拉取镜像并运行容器。
- **尚未实现（开发中）**
  - **文件管理**：将信息保存到本地文件（计划通过 MCP 写文件工具提供）。
  - **地图导航**：查询地点、规划路线（计划中）。

## 流程概览

- **Build**（`.github/workflows/build.yml`）：每次 push 到 `main`/`master` 时，构建镜像并推送到 **阿里云个人版镜像仓库**（`test017/test-cicid`）。
- **Deploy**（`.github/workflows/deploy.yml`）：可**手动触发**或在 Build 成功后自动触发；当前为 SSH 到服务器并 docker 部署（可改为部署到本地 Minikube，见 `docs/`）。



## Build workflow（推送到阿里云 ACR）

- **镜像仓库**：阿里云个人版，
  推送标签：`latest`、`sha-<7位commit>`
- **必须在 GitHub 配置 Secrets**（仓库 **Settings → Secrets and variables → Actions**）：
  - `ACR_USERNAME`：阿里云 ACR 登录用户名
  - `ACR_PASSWORD`：阿里云 ACR 登录密码

## Deploy workflow（与服务器联通）

Deploy 通过 **SSH** 连到服务器，在服务器上执行 `docker login`（阿里云 ACR）→ `docker pull` → `docker run`。拉镜像用的 ACR 账号由 workflow 传入，**服务器上无需预先 docker login**。

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

| Secret 名称         | 说明 | 示例 |
|---------------------|------|------|
| `DEPLOY_HOST`       | 服务器公网 IP 或域名 | `8.136.38.236` |
| `DEPLOY_USER`       | SSH 登录用户名 | `root` |
| `SSH_PASSWORD`      | 服务器 SSH 登录密码（与 root 密码一致即可） | （你的 root 密码） |
| `ACR_USERNAME`      | 阿里云 ACR 用户名（Build 已用） | 同 Build |
| `ACR_PASSWORD`      | 阿里云 ACR 密码（Build 已用） | 同 Build |
| `DASHSCOPE_API_KEY` | 通义千问 API Key（线上容器调用模型用） | 同 project/.env 中的值 |
| `MODEL`             | 可选，模型名称 | `qwen-plus` |

- 若用 **SSH 密钥** 而不是密码：可不填 `SSH_PASSWORD`，改填 `SSH_PRIVATE_KEY`（私钥全文）。  
- **不要**把密码或私钥提交到代码里，只放在 GitHub Secrets 中。

### 三、触发部署

- **手动**：Actions → 选 “Deploy” → “Run workflow”。
- **自动**：Build 成功后会触发 Deploy。

部署成功后访问：**`http://8.136.38.236`**（或你的公网 IP，80 端口）。

## 文件说明

- `project/`：MCP Agent 应用（FastAPI、天气 MCP、写文件 MCP 等）
- `Dockerfile`：构建 `project/` 下的 Python 应用并用于部署
- `k8s/`：Kubernetes 清单（供 Minikube 等使用）
- `scripts/minikube-deploy.sh`：本地 Minikube 一键部署脚本
- `.github/workflows/build.yml`：构建并推送镜像到阿里云 ACR
- `.github/workflows/deploy.yml`：部署到远程服务器（SSH + Docker）
