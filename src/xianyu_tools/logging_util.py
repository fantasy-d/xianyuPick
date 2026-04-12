import logging
import sys
from pathlib import Path

def get_unified_logger(name: str, log_file: str = None):
    """
    创建一个统一格式的 Logger。
    如果提供了 log_file，则会同时输出到该文件（追加模式）。
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重复添加 Handler
    if logger.handlers:
        return logger

    # 统一的日志格式：时间 [等级] [模块名] 消息
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')

    # 控制台输出 (stderr 模式，不干扰 stdout 数据流)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出 (核心：全链路汇聚点)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
