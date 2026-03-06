"""
MCP-Agent CLI 交互式客户端：连接多台 MCP 服务器，与 Agent 对话。
"""
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_mcp_adapters.sessions import create_session, StdioConnection
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# 项目根目录（与 servers_config.json、agent_prompts.txt 同层）
PROJECT_ROOT = Path(__file__).resolve().parent

# 加载 MCP 服务器配置
with open(PROJECT_ROOT / "servers_config.json", "r", encoding="utf-8") as f:
    servers_cfg = json.load(f)

# 加载 Agent 提示词
with open(PROJECT_ROOT / "agent_prompts.txt", "r", encoding="utf-8") as f:
    prompt = f.read().strip()

# 模型配置（.env 中 DASHSCOPE_API_KEY、MODEL）
cfg = type("Cfg", (), {"model": os.getenv("MODEL", "qwen-plus")})()


async def get_tools_from_servers():
    """根据 servers_config 启动各 MCP 服务器并汇总为 LangChain 工具列表。"""
    all_tools = []
    sessions = []
    for s in servers_cfg:
        name = s.get("name", "mcp")
        cmd = s.get("command", ["python", "-m", name])
        cwd = s.get("cwd", str(PROJECT_ROOT))
        workdir = Path(cwd).resolve() if cwd and cwd != "." else PROJECT_ROOT
        connection = StdioConnection(
            transport="stdio",
            command=cmd[0],
            args=cmd[1:] if len(cmd) > 1 else [],
            cwd=workdir,
        )
        try:
            session = await create_session(connection)
            sessions.append(session)
            tools = await load_mcp_tools(session, server_name=name, tool_name_prefix=True)
            all_tools.extend(tools)
        except Exception as e:
            print(f"[警告] 无法连接 MCP 服务器 {name}: {e}")
    return all_tools, sessions


async def run_chat_loop() -> None:
    """启动 MCP-Agent 聊天循环"""
    tools, sessions = await get_tools_from_servers()
    if not tools:
        print("未获取到任何 MCP 工具，请检查 servers_config.json 与服务器是否可启动。")
        return

    model = ChatTongyi(model=cfg.model)
    checkpointer = MemorySaver()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt_template,
        checkpointer=checkpointer,
    )

    print("输入 quit 退出。")
    try:
        while True:
            user_input = input("\n你: ").strip()
            if user_input.lower() == "quit":
                break
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config={"configurable": {"thread_id": "1"}},
            )
            print(f"\nAI: {result['messages'][-1].content}")
    finally:
        for s in sessions:
            try:
                await s.__aexit__(None, None, None)
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run_chat_loop())
