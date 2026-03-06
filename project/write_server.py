"""
文件写入 MCP 服务器：提供安全范围内的写文件能力。
"""
import os
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("write-server")

# 仅允许写入此目录下的文件（可改为环境变量 WRITE_BASE_DIR）
WRITE_BASE = Path(os.environ.get("WRITE_BASE_DIR", ".")).resolve()


def _safe_path(relative_path: str) -> Path:
    p = (WRITE_BASE / relative_path).resolve()
    if not str(p).startswith(str(WRITE_BASE)):
        raise PermissionError(f"不允许写入该路径: {relative_path}")
    return p


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """在项目允许的目录下写入或覆盖一个文本文件。path 为相对路径，如 'output/hello.txt'。"""
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"已写入: {p}"
    except Exception as e:
        return f"写入失败: {e}"


@mcp.tool()
def read_file(path: str) -> str:
    """读取项目允许目录下的文本文件内容。path 为相对路径。"""
    try:
        p = _safe_path(path)
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"读取失败: {e}"


if __name__ == "__main__":
    mcp.run()
