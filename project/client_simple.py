"""
单次调用示例：不进入交互循环，发一条消息并打印回复。
"""
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.sessions.stdio import StdioConnection
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
with open(PROJECT_ROOT / "servers_config.json", "r", encoding="utf-8") as f:
    servers_cfg = json.load(f)
with open(PROJECT_ROOT / "agent_prompts.txt", "r", encoding="utf-8") as f:
    prompt_text = f.read().strip()


async def main():
    # 只连第一个 MCP 服务器做示例（可改为遍历全部）
    s = servers_cfg[0]
    cmd, cwd = s.get("command", ["python", "-m", "weather_server"]), s.get("cwd", str(PROJECT_ROOT))
    workdir = Path(cwd).resolve() if cwd and cwd != "." else PROJECT_ROOT
    connection = StdioConnection(
        transport="stdio",
        command=cmd[0],
        args=cmd[1:] if len(cmd) > 1 else [],
        cwd=workdir,
    )
    session = await create_session(connection)
    tools = await load_mcp_tools(session, server_name=s.get("name", "mcp"), tool_name_prefix=True)

    model = ChatTongyi(model=os.getenv("MODEL", "qwen-plus"))
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
        MessagesPlaceholder(variable_name="messages"),
    ])
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt_template,
        checkpointer=MemorySaver(),
    )

    user_msg = "北京现在天气怎么样？"
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_msg}]},
        config={"configurable": {"thread_id": "simple-1"}},
    )
    print("用户:", user_msg)
    print("AI:", result["messages"][-1].content)

    await session.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main())
