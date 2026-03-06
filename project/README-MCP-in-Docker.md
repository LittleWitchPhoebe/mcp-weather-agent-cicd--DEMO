# 为什么在容器里会出现「Agent 未就绪（无可用 MCP 工具）」？

API 服务启动时会按 `servers_config.json` **在进程内再起子进程**（`python weather_server.py`、`python write_server.py`），通过 **stdio** 和这些 MCP 服务通信、拉取工具。在 Docker 里这类子进程经常起不来，所以拿不到任何工具，就会报「Agent 未就绪」。

## 常见原因

1. **子进程在容器里启动失败**
   - 镜像里可能只有 `python3`，没有 `python`，命令写成 `python weather_server.py` 会找不到解释器。
   - 工作目录 `cwd` 在容器里和本地不一致，MCP 脚本或依赖找不到路径。
   - 缺少依赖：例如 `fastmcp`、`httpx` 等没打进镜像，子进程一 import 就崩。

2. **stdio 在 Web 进程下的限制**
   - API 跑在 uvicorn 里，本身没有「真实终端」；再 spawn 子进程用 stdin/stdout 通信，部分库或 MCP 实现在这种环境下会超时、卡住或直接失败。
   - 子进程若往 stderr 打很多日志，或缓冲没关，也可能影响和父进程的 stdio 协议通信。

3. **启动顺序 / 超时**
   - 容器冷启动时，同时起两个 MCP 子进程，若有一个慢或卡住，适配器那边可能等不到「就绪」就超时，认为连接失败。

4. **环境变量 / 权限**
   - 子进程继承的环境和主进程一致；若容器里没设好 `DASHSCOPE_API_KEY` 等，只影响主进程调模型，一般不会直接导致 MCP 起不来。但若 MCP 脚本里自己读 env 并校验，也可能在子进程里报错退出。

## 当前行为

- 若 **任一 MCP 工具加载成功**：Agent 会带工具正常对话（如天气、写文件）。
- 若 **全部失败**：我们会退化为「仅用模型、无工具」的 Agent，对话仍可用，只是没有查天气、写文件等能力；同时会在 **容器日志** 里打印 `[MCP] xxx 未就绪: ...`，便于排查。

## 如何排查

在服务器上查看容器标准错误，能看到具体是哪个 MCP、什么错：

```bash
docker logs demo-ci-cd 2>&1 | head -80
```

若看到例如 `ModuleNotFoundError`、`FileNotFoundError`、`TimeoutError` 等，就按报错修（缺依赖加依赖、命令改成 `python3`、调大超时等）。

## 若希望容器里也用上 MCP 工具

- 确认镜像里 **有** `weather_server.py`、`write_server.py` 以及它们依赖的包（如 `fastmcp`、`httpx`）。
- 在 `servers_config.json` 里把 `python` 改成 **`python3`**（若镜像里只有 `python3`）。
- 若仍失败，看 `docker logs` 里 `[MCP] ... 未就绪:` 后面的异常信息，再针对该错误改启动方式或环境。
