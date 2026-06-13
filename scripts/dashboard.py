import streamlit as st
import json
import asyncio
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
import subprocess

from scripts.run_full_pipeline import get_active_ali1688_state_file, sanitize_dir_name

st.set_page_config(page_title="闲鱼-1688 选品决策系统", layout="wide")

st.title("🚀 闲鱼-1688 选品决策系统")
st.markdown("通过闲鱼热度分析与 1688 API 劫持技术，自动化挖掘高毛利货源。")

# 侧边栏配置
st.sidebar.header("⚙️ 任务配置")
keyword = st.sidebar.text_input("搜索关键词", value="人体工学椅")
scan_depth = st.sidebar.slider("每个商品匹配货源数", 1, 20, 10)
run_button = st.sidebar.button("开始执行全量流水线", type="primary")

# 初始化状态
if 'logs' not in st.session_state:
    st.session_state.logs = []

def add_log(msg):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# 核心执行逻辑
if run_button:
    st.session_state.logs = []
    add_log(f"任务启动: {keyword}")
    
    # 创建目录
    date_str = datetime.now().strftime("%Y%m%d")
    root_dir = Path(f"outputs/{keyword}_{date_str}")
    root_dir.mkdir(parents=True, exist_ok=True)
    
    with st.status("正在执行自动化流水线...", expanded=True) as status:
        # Step 1: 闲鱼扫描
        st.write("🔍 正在扫描闲鱼热品...")
        add_log("Phase 1: Xianyu Scanning...")
        cmd_xianyu = f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && /opt/anaconda3/envs/mytools/bin/python scripts/run_xianyu_hot_items.py --keyword '{keyword}' --state-file xianyu_state.json --max-pages 1 --top-n 10"
        result = subprocess.run(cmd_xianyu, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            xianyu_data = json.loads(result.stdout)
            (root_dir / "xianyu_hot_items.json").write_text(result.stdout)
            hot_items = xianyu_data.get("hot_items", [])
            st.success(f"找到 {len(hot_items)} 个闲鱼热品")
            
            # 展示预览
            cols = st.columns(5)
            for idx, item in enumerate(hot_items[:5]):
                with cols[idx]:
                    st.image(item.get("image_url"), caption=f"Rank {idx+1}")
                    st.caption(f"想要: {item.get('want_count')}")
        else:
            st.error("闲鱼扫描失败")
            st.stop()

        # Step 2: 1688 深度验证
        st.write("📦 正在 1688 匹配货源并提取 SKU...")
        progress_bar = st.progress(0)
        
        for i, item in enumerate(hot_items, start=1):
            add_log(f"Processing Item {i}: {item.get('title')[:20]}...")
            st.write(f"正在处理 Rank {i}: {item.get('title')[:30]}...")
            
            # 使用之前的全自动脚本逻辑
            safe_title = sanitize_dir_name(item.get("title", "item"))
            item_dir = root_dir / f"Rank_{i}_{safe_title}"
            item_dir.mkdir(parents=True, exist_ok=True)
            ali1688_state_file = get_active_ali1688_state_file()
            
            cmd_1688 = (
                f"export PYTHONPATH=$PYTHONPATH:$(pwd)/src && /opt/anaconda3/envs/mytools/bin/python scripts/run_ali1688_slow_flow.py "
                f"--image-url '{item.get('image_url')}' "
                f"--state-file '{ali1688_state_file}' "
                f"--output-dir '{item_dir}' "
                f"--detail-top-n {scan_depth}"
            )
            subprocess.run(cmd_1688, shell=True)
            progress_bar.progress(i / len(hot_items))

        # Step 3: 生成标准报表
        st.write("📊 正在汇总数据并生成 Excel...")
        cmd_report = f"/opt/anaconda3/envs/mytools/bin/python scripts/export_final_excel_v3.py"
        subprocess.run(cmd_report, shell=True)
        status.update(label="✅ 全量流水线执行完毕!", state="complete", expanded=False)

# 展示结果
date_str = datetime.now().strftime("%Y%m%d")
root_dir = Path(f"outputs/{keyword}_{date_str}")
report_file = root_dir / f"{keyword}_深度分析报表_标准多Sheet版.xlsx"

if report_file.exists():
    st.divider()
    st.subheader("📊 最终分析结果")
    
    # 尝试读取 CSV 进行展示
    summary_csv = root_dir / f"{keyword}_最终结论分析表.csv"
    if summary_csv.exists():
        df = pd.read_csv(summary_csv)
        st.dataframe(df, use_container_width=True)
    
    with open(report_file, "rb") as f:
        st.download_button(
            label="📥 下载完整多Sheet Excel 报表",
            data=f,
            file_name=report_file.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# 日志区域
if st.session_state.logs:
    with st.expander("📝 详细执行日志"):
        for log in st.session_state.logs:
            st.text(log)
