# -*- coding: utf-8 -*-
"""
测试脚本：启动下位机模拟器
用于测试UDP示波器的功能
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from communication.simulator import MotorSimulator

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    print("=" * 50)
    print("UDP示波器 - 下位机模拟器测试")
    print("=" * 50)
    print()
    
    # 创建模拟器
    simulator = MotorSimulator(
        target_host='127.0.0.1',  # 本地测试
        target_port=8888
    )
    
    # 设置发送频率
    simulator.set_sample_rate(1000)  # 100Hz
    
    try:
        print("启动模拟器...")
        print("目标地址: 127.0.0.1:8888")
        print("发送频率: 100 Hz")
        print("按 Ctrl+C 停止模拟器")
        print()
        
        # 启动模拟器
        await simulator.start()
        
    except KeyboardInterrupt:
        print("\n用户中断，正在停止模拟器...")
    except Exception as e:
        print(f"模拟器运行出错: {e}")
    finally:
        await simulator.stop()
        print("模拟器已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
