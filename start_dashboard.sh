#!/bin/bash

# 获取脚本所在目录并切换过去，确保路径正确
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================="
echo "   🚀 闲鱼-1688 选品决策系统 正在启动..."
echo "=========================================="

# 配置 Python 模块搜索路径
export PYTHONPATH=$PYTHONPATH:"$DIR/src"

# 启动 Streamlit 可视化界面
/opt/anaconda3/envs/mytools/bin/streamlit run scripts/dashboard.py
