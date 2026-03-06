"""
FastAPI HTTP API：对外提供与 Agent 对话的接口。
"""
import asyncio
import json
import os
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
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

# 全局 Agent 与 sessions（启动时初始化）
agent = None
mcp_sessions = []


async def init_agent():
    global agent, mcp_sessions
    all_tools = []
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
            mcp_sessions.append(session)
            tools = await load_mcp_tools(session, server_name=name, tool_name_prefix=True)
            all_tools.extend(tools)
        except Exception:
            pass
    if not all_tools:
        return
    model = ChatTongyi(model=os.getenv("MODEL", "qwen-plus"))
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
        MessagesPlaceholder(variable_name="messages"),
    ])
    agent = create_react_agent(
        model=model,
        tools=all_tools,
        prompt=prompt_template,
        checkpointer=MemorySaver(),
    )


async def close_sessions():
    for s in mcp_sessions:
        try:
            await s.__aexit__(None, None, None)
        except Exception:
            pass
    mcp_sessions.clear()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_agent()
    yield
    await close_sessions()


app = FastAPI(title="MCP-Agent API", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent 未就绪（无可用 MCP 工具）")
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": req.message}]},
        config={"configurable": {"thread_id": req.thread_id}},
    )
    reply = result["messages"][-1].content
    return ChatResponse(reply=reply)


@app.get("/health")
async def health():
    return {"status": "ok", "agent_ready": agent is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
