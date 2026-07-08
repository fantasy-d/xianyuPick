#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/envs/mytools/bin/python}"

cd "$ROOT_DIR"

PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}" "$PYTHON_BIN" - <<'PY'
import asyncio
import json
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main() -> None:
    root_dir = os.getcwd()
    params = StdioServerParameters(
        command=os.path.join(os.path.dirname(sys.executable), "xianyu-mcp"),
        cwd=root_dir,
        env={**os.environ, "PYTHONPATH": os.path.join(root_dir, "src")},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(json.dumps(
                {
                    "status": "success",
                    "tool_count": len(tools.tools),
                    "tools": [tool.name for tool in tools.tools],
                },
                ensure_ascii=False,
                indent=2,
            ))


asyncio.run(main())
PY
