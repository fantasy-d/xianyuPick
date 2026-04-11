#!/bin/bash

# 获取项目根目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================="
echo "   🚢 正在启动 H5 选品决策系统..."
echo "=========================================="

# 配置 Python 环境
export PYTHONPATH=$PYTHONPATH:"$DIR/src"
PYTHON_BIN="/opt/anaconda3/envs/mytools/bin/python"
UVICORN_BIN="/opt/anaconda3/envs/mytools/bin/uvicorn"

# 自动打开浏览器
sleep 2 && open "http://localhost:8000" &

# 启动 FastAPI 后端
$UVICORN_BIN src.web_api.main:app --host 0.0.0.0 --port 8000 --reload
