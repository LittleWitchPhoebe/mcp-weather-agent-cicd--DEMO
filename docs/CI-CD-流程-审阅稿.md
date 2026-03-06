# CI/CD 流程变更 — 审阅稿

本文档描述将 **Build** 改为推送到阿里云镜像仓库，以及将 **Deploy** 改为部署到本地 Minikube 的流程设计。**请审阅确认后再实施代码修改。**

---

## 一、目标

| 项目 | 当前 | 变更后 |
|------|------|--------|
| **Build** | 构建镜像 → 推送到 GitHub GHCR | 构建镜像 → 推送到 **阿里云镜像仓库**（你已创建的 test-cicd，对应 GitHub 仓库 DEMO-CI-CD） |
| **Deploy** | SSH 到阿里云 ECS，在该机上 docker run | 从 **阿里云镜像仓库** 拉取镜像，部署到 **本地 Minikube** |

---

## 二、Build workflow 变更

### 2.1 行为

- **触发**：不变，仍为 push 到 `main` / `master`。
- **步骤**：
  1. Checkout 代码。
  2. 使用 **阿里云镜像仓库** 账号登录（在 workflow 里用 Secrets，不写死账号密码）。
  3. 构建镜像，打 tag 为阿里云镜像地址（见下）。
  4. Push 到阿里云镜像仓库。

### 2.2 镜像地址约定

阿里云 ACR 地址一般为：

```text
<registry>/<命名空间>/<仓库名>:<标签>
```

你已说明命名空间/仓库为 **test-cicd**，与 GitHub 仓库 DEMO-CI-CD 对应。建议约定：

- **Registry**：由你提供，例如 `registry.cn-hangzhou.aliyuncs.com`（以阿里云控制台实际显示为准）。
- **镜像名**：`<registry>/test-cicd/demo-ci-cd:latest`（及 `:<git-sha>` 等标签）。

最终以你在阿里云 ACR 里创建的「命名空间」和「仓库名」为准，可在审阅时确认。

### 2.3 需要你在 GitHub 配置的 Secrets（Build 用）

| Secret 名称     | 说明                     | 示例 |
|-----------------|--------------------------|------|
| `ACR_REGISTRY`  | 阿里云镜像仓库登录地址   | `registry.cn-hangzhou.aliyuncs.com` |
| `ACR_USERNAME`  | 阿里云 ACR 登录用户名    | 控制台「访问凭证」中的用户名 |
| `ACR_PASSWORD`  | 阿里云 ACR 登录密码      | 控制台设置的固定密码或临时密码 |

Build 将**只**推送到阿里云（不再推 GHCR）。若你希望同时保留推送到 GHCR，可说明，再增加双写逻辑。

---

## 三、Deploy workflow 变更（部署到本地 Minikube）

### 3.1 约束说明

- GitHub Actions 的 job 默认在 **GitHub 提供的云端 runner** 上执行。
- 云端 runner **无法**访问你本机的 Minikube（在你电脑上的 K8s）。
- 因此要实现「Deploy workflow 把镜像拉到本地并部署到本地 Minikube」，只能让 Deploy 在 **能访问你这台 Minikube 的机器** 上跑。

### 3.2 方案选择

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **A. Self-hosted Runner** | 在你本机（或一台固定机器）上安装 GitHub Actions **self-hosted runner**，该机已安装 Minikube。Deploy workflow 指定 `runs-on: self-hosted`，在 runner 上执行：登录 ACR、拉取镜像、`kubectl apply -f k8s/` 部署到本机 Minikube。 | 全流程在 GitHub 上可见、可追溯；Push 后自动/手动触发即可部署到本机 Minikube。 | 需要本机长期开着一个 runner 进程；本机需能访问外网（拉镜像）。 |
| **B. 本地脚本** | Deploy **不**在 workflow 里“部署到本机”，而是：workflow 只负责 Build 推 ACR；你本地需要部署时，在**本机**执行一个脚本（如 `./scripts/deploy-minikube-from-acr.sh`），脚本里：登录 ACR、拉镜像、部署到 Minikube。 | 无需配置 runner，不依赖本机常驻进程。 | “部署”不在 Actions 里体现，需自己记得在本地跑脚本。 |

建议：若你希望「在 GitHub Actions 里点一下或自动触发就完成部署到本机 Minikube」，选 **方案 A**；若可以接受「Build 推 ACR 后，需要时在本机手动跑脚本部署」，选 **方案 B**。

### 3.3 方案 A：Deploy workflow 在 Self-hosted Runner 上部署到 Minikube

- **触发**：与现有一致（手动触发 或 Build 成功后的 `workflow_run`）。
- **运行位置**：`runs-on: self-hosted`（或你给本机打的 label，如 `minikube`）。
- **步骤概要**：
  1. Checkout 代码（获取 `k8s/` 下的 YAML）。
  2. 使用 `ACR_REGISTRY` / `ACR_USERNAME` / `ACR_PASSWORD` 登录阿里云镜像仓库。
  3. 在 runner 所在机器上：
     - 为 Minikube 集群创建 ACR 的 `imagePullSecret`（若尚未存在）。
     - 将 `k8s/deployment.yaml` 中的镜像改为阿里云地址（如 `<ACR_REGISTRY>/test-cicd/demo-ci-cd:latest`），并引用该 `imagePullSecret`。
     - 执行 `kubectl apply -f k8s/`（或等价命令），使 Minikube 从 ACR 拉镜像并部署。
  4. 可选：输出 `kubectl get pods` 或 `minikube service demo-ci-cd --url`，便于你在本机浏览器访问。

**你需要做的**：在本机安装并配置 GitHub Actions self-hosted runner，并确保本机已安装 Minikube、kubectl、且 `kubectl` 当前上下文指向该 Minikube。

### 3.4 方案 B：仅提供本地部署脚本，Deploy workflow 不部署到本机

- **Deploy workflow**：可改为“仅做校验/占位”（例如检查 ACR 镜像是否存在），或暂时禁用/删除；实际部署不由 workflow 执行。
- **本地**：提供脚本（如 `scripts/deploy-minikube-from-acr.sh`），你在本机执行：
  - 使用 ACR 账号登录（或从环境变量/本机配置读取）。
  - 在 Minikube 中创建 ACR 的 imagePullSecret。
  - 使用 ACR 镜像地址更新 `k8s/deployment.yaml`（或通过环境变量传入镜像名），然后 `kubectl apply -f k8s/`。
- 访问方式：本机执行 `minikube service demo-ci-cd --url` 或 `http://$(minikube ip):30080`。

---

## 四、涉及的文件与配置（实施时将修改/新增）

| 类型 | 文件/位置 | 变更说明 |
|------|-----------|----------|
| Workflow | `.github/workflows/build.yml` | 登录阿里云 ACR；镜像 tag 改为 ACR 地址；push 到 ACR（不再推 GHCR，除非你要求双写）。 |
| Workflow | `.github/workflows/deploy.yml` | 若选方案 A：改为 `runs-on: self-hosted`，步骤改为登录 ACR、创建 imagePullSecret、kubectl apply；若选方案 B：可弱化或移除“部署到本机”的步骤，仅保留文档/脚本说明。 |
| K8s | `k8s/deployment.yaml` | 镜像改为阿里云地址（如 `<registry>/test-cicd/demo-ci-cd:latest`）；启用 `imagePullSecrets`（名称与 workflow/脚本中创建的 ACR secret 一致）。 |
| 脚本/文档 | `scripts/deploy-minikube-from-acr.sh`（方案 B 时） | 新增：本机从 ACR 拉镜像并部署到 Minikube 的脚本。 |
| 文档 | `README.md` | 更新：Build 推 ACR 的说明、所需 Secrets、Deploy 方案（A 或 B）及对应操作步骤。 |

---

## 五、需要你确认的信息

请逐项确认或补充，确认后再进行代码修改：

1. **阿里云镜像仓库信息**
   - Registry 完整地址（例如 `registry.cn-hangzhou.aliyuncs.com`）：  
     \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_  
   - 命名空间 + 仓库名（当前理解为 `test-cicd/demo-ci-cd`，是否一致？）：  
     \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

2. **Build**
   - 是否 **仅** 推送到阿里云 ACR？（是 / 否；若否，请说明是否同时推 GHCR。）

3. **Deploy 到本地 Minikube**
   - 选择 **方案 A（Self-hosted Runner）** 还是 **方案 B（本地脚本）**？

4. **Secrets**
   - 是否同意在 GitHub 仓库中配置 `ACR_REGISTRY`、`ACR_USERNAME`、`ACR_PASSWORD`？（Deploy 方案 A 也会复用这些 Secrets 在 runner 上登录 ACR。）

---

## 六、流程一览（确认后实施）

```text
开发者 push (main/master)
        ↓
  Build workflow 触发
        ↓
  构建镜像 → 推送到 阿里云 ACR (test-cicd/demo-ci-cd:latest 等)
        ↓
  Deploy 触发（手动 或 Build 成功后自动）
        ↓
  ┌─ 方案 A：在 self-hosted runner 上
  │   登录 ACR → 创建/更新 imagePullSecret → kubectl apply → 本机 Minikube 运行新镜像
  │
  └─ 方案 B：不在 workflow 里部署到本机
       你本机需要时执行脚本：登录 ACR → 创建 imagePullSecret → kubectl apply → 本机 Minikube 运行新镜像
```

请在上面「五、需要你确认的信息」中填写或勾选后回复，确认后我将按你的选择修改仓库中的 workflow、k8s 清单和文档。
