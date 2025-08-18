# -*- coding: utf-8 -*-
"""
测试脚本：启动UDP示波器应用
用于测试应用程序的功能
"""

import sys
import logging
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """主函数"""
    print("=" * 50)
    print("UDP示波器 - 应用程序测试")
    print("=" * 50)
    print()
    
    try:
        # 导入主程序
        from main import main as app_main
        
        print("启动UDP示波器应用...")
        print("请确保已启动下位机模拟器 (运行 test_simulator.py)")
        print()
        
        # 启动应用
        app_main()
        
    except KeyboardInterrupt:
        print("\n用户中断程序")
    except Exception as e:
        print(f"应用程序运行出错: {e}")
        logger.exception("详细错误信息:")


if __name__ == "__main__":
    main()
