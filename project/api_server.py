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
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from langchain_mcp_adapters.sessions import create_session, StdioConnection
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


@app.get("/")
async def root():
    """首页：欢迎语 + 对话框"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MCP-Agent</title>
    <style>
      * { box-sizing: border-box; }
      body { font-family: system-ui, sans-serif; max-width: 560px; margin: 0 auto; padding: 1.5rem; min-height: 100vh; display: flex; flex-direction: column; background: #f5f5f5; }
      .welcome { color: #333; margin-bottom: 1rem; font-size: 1.1rem; }
      #history { flex: 1; overflow-y: auto; background: #fff; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; min-height: 120px; }
      .msg { margin-bottom: 0.75rem; }
      .msg.user { color: #1a73e8; }
      .msg.agent { color: #333; white-space: pre-wrap; word-break: break-word; }
      .input-row { display: flex; gap: 8px; }
      #input { flex: 1; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 1rem; }
      #send { padding: 10px 20px; background: #1a73e8; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; }
      #send:hover { background: #1557b0; }
      #send:disabled { background: #ccc; cursor: not-allowed; }
      .error { color: #c00; margin-top: 0.5rem; }
    </style>
    </head>
    <body>
    <p class="welcome">欢迎使用 MCP-Agent，有什么可以帮您？</p>
    <div id="history"></div>
    <div class="input-row">
      <input id="input" type="text" placeholder="输入消息..." enterkeyhint="send" />
      <button id="send">发送</button>
    </div>
    <div id="error" class="error"></div>
    <script>
      const history = document.getElementById('history');
      const input = document.getElementById('input');
      const sendBtn = document.getElementById('send');
      const errEl = document.getElementById('error');
      const threadId = 'web-' + Math.random().toString(36).slice(2, 9);

      function addMsg(role, text) {
        const div = document.createElement('div');
        div.className = 'msg ' + role;
        div.textContent = (role === 'user' ? '你：' : 'Agent：') + text;
        history.appendChild(div);
        history.scrollTop = history.scrollHeight;
      }

      async function doSend() {
        const text = input.value.trim();
        if (!text) return;
        addMsg('user', text);
        input.value = '';
        sendBtn.disabled = true;
        errEl.textContent = '';
        try {
          const r = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: threadId })
          });
          const data = await r.json();
          if (!r.ok) throw new Error(data.detail || data.message || '请求失败');
          addMsg('agent', data.reply);
        } catch (e) {
          errEl.textContent = e.message || '发送失败';
        } finally {
          sendBtn.disabled = false;
        }
      }

      sendBtn.onclick = doSend;
      input.onkeydown = function(e) { if (e.key === 'Enter') doSend(); };
    </script>
    </body>
    </html>
    """)


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
