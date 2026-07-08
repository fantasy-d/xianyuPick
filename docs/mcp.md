# MCP Server

This project exposes selected management capabilities through an MCP stdio server.

## Install

```bash
cd /Users/mac/PycharmProjects/mytools/xianyu-tools
/opt/anaconda3/envs/mytools/bin/python -m pip install -e .
```

Or use the helper script:

```bash
cd /Users/mac/PycharmProjects/mytools/xianyu-tools
scripts/install_mcp.sh
```

## Run

```bash
cd /Users/mac/PycharmProjects/mytools/xianyu-tools
PYTHONPATH="$PWD/src:$PYTHONPATH" /opt/anaconda3/envs/mytools/bin/python -m xianyu_tools.mcp_server
```

Or, after `pip install -e .`:

```bash
cd /Users/mac/PycharmProjects/mytools/xianyu-tools
PYTHONPATH="$PWD/src:$PYTHONPATH" /opt/anaconda3/envs/mytools/bin/xianyu-mcp
```

## Example MCP Client Config

Ready-to-copy config templates are available in:

- `mcp/xianyu-tools.mcp.json`
- `mcp/xianyu-tools.python-module.mcp.json`
- `mcp/openclaw.example.json`
- `mcp/harness.example.json`

For OpenClaw, harness, or any other MCP-compatible agent client, use the config shape below unless the client documents a different wrapper key.

```json
{
  "mcpServers": {
    "xianyu-tools": {
      "command": "/opt/anaconda3/envs/mytools/bin/python",
      "args": ["-m", "xianyu_tools.mcp_server"],
      "cwd": "/Users/mac/PycharmProjects/mytools/xianyu-tools",
      "env": {
        "PYTHONPATH": "/Users/mac/PycharmProjects/mytools/xianyu-tools/src"
      }
    }
  }
}
```

If the console script is installed, this equivalent config can be used:

```json
{
  "mcpServers": {
    "xianyu-tools": {
      "command": "/opt/anaconda3/envs/mytools/bin/xianyu-mcp",
      "cwd": "/Users/mac/PycharmProjects/mytools/xianyu-tools",
      "env": {
        "PYTHONPATH": "/Users/mac/PycharmProjects/mytools/xianyu-tools/src"
      }
    }
  }
}
```

## Smoke Test

After installation:

```bash
cd /Users/mac/PycharmProjects/mytools/xianyu-tools
scripts/smoke_mcp.sh
```

Expected result: JSON output with `status: "success"` and the available MCP tool names.

## Tools

- `xianyu_system_status`: read system status.
- `xianyu_list_tasks`: list scan tasks.
- `xianyu_get_task_detail`: read one scan task detail.
- `xianyu_start_scan_task`: start a scan task with optional per-task crawl config.
- `xianyu_list_selection_items`: list selected/published candidates.
- `xianyu_list_orders`: list XianGuanJia orders.
- `xianyu_get_order_detail`: read one XianGuanJia order detail.
- `xianyu_token_stats`: read LLM token usage summary.

### Start Scan Task Config

`xianyu_start_scan_task` accepts:

```json
{
  "keyword": "蚊帐",
  "crawl_config": {
    "source_limit_1688": 20,
    "gross_profit_rate": 0.3,
    "source_filter_models": [],
    "source_channel_selection_mode": "custom_selected",
    "enabled_source_channels": [
      {
        "channel_id": "ali1688",
        "enabled": true,
        "account_ids": ["ali1688-account-1"]
      }
    ],
    "channel_search_filters": [
      {
        "channel_id": "ali1688",
        "filters": {
          "rapid_invoice": true,
          "free_shipping": true
        }
      }
    ]
  }
}
```

If `crawl_config` is omitted, the task uses the current system default crawl config. If provided, it is normalized and stored as the task snapshot only; system defaults are not changed.

## Current Scope

The MCP server exposes mostly read-only tools plus scan-task creation. Operations that mutate external marketplace state, such as order shipping or price modification, are intentionally not exposed in the first version.
