#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/envs/mytools/bin/python}"

cd "$ROOT_DIR"

"$PYTHON_BIN" -m pip install -e .

cat <<EOF

MCP server installed.

Use this config in OpenClaw, harness, or any MCP-compatible agent client:

{
  "mcpServers": {
    "xianyu-tools": {
      "command": "${PYTHON_BIN%/python}/xianyu-mcp",
      "cwd": "$ROOT_DIR",
      "env": {
        "PYTHONPATH": "$ROOT_DIR/src"
      }
    }
  }
}

Smoke test:
  PYTHON_BIN="$PYTHON_BIN" scripts/smoke_mcp.sh

EOF
