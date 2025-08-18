# -*- coding: utf-8 -*-
"""
测试示波器交互功能
验证缩放偏移功能是否正常工作
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

def test_scope_view():
    """测试示波器视图组件"""
    from PyQt5 import QtWidgets
    from ui.scope_view import ScopeView
    import numpy as np
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建示波器视图
    scope = ScopeView(n_channels=4, sample_rate=1000.0)
    scope.show()
    
    # 生成测试数据
    t = np.linspace(0, 1, 1000)
    test_data = [
        np.sin(2 * np.pi * 50 * t) + 0.1 * np.random.randn(1000),  # CH1: 50Hz正弦波
        np.cos(2 * np.pi * 100 * t) + 0.1 * np.random.randn(1000), # CH2: 100Hz余弦波
        np.sin(2 * np.pi * 25 * t) * 2 + 0.1 * np.random.randn(1000), # CH3: 25Hz正弦波，幅值2倍
        np.random.randn(1000) * 0.5  # CH4: 随机噪声
    ]
    
    # 更新显示
    scope.update_tail(test_data)
    
    print("=" * 50)
    print("示波器交互测试")
    print("=" * 50)
    print("测试功能:")
    print("1. 鼠标滚轮 - 水平缩放（时基）")
    print("2. Ctrl + 鼠标滚轮 - 垂直缩放（当前通道）")
    print("3. 鼠标左键拖拽 - 水平偏移")
    print("4. Ctrl + 鼠标左键拖拽 - 垂直偏移（当前通道）")
    print("5. 通道选择：使用set_current_channel()方法")
    print()
    print("当前通道: CH1")
    print("按ESC键退出")
    
    # 设置当前通道为CH1
    scope.set_current_channel(0)
    
    app.exec_()

def test_config_manager():
    """测试配置管理器"""
    from config.config_manager import ConfigManager
    
    print("=" * 50)
    print("配置管理器测试")
    print("=" * 50)
    
    cfg = ConfigManager()
    
    print(f"应用名称: {cfg.app_name}")
    print(f"采样频率: {cfg.sample_rate} Hz")
    print(f"时基挡位: {cfg.get('display.time_base_div')} ms/div")
    print(f"自动滚动: {cfg.auto_roll}")
    print(f"通道数量: {len(cfg.channel_defs)}")
    
    # 测试通道配置
    for i, ch_config in enumerate(cfg.channel_defs[:3]):  # 只显示前3个
        print(f"  {ch_config['name']}: {ch_config['color']}, "
              f"{ch_config['vertical_div']}V/div, "
              f"偏移{ch_config['vertical_offset']}V")

def main():
    """主函数"""
    print("选择测试项目:")
    print("1. 示波器视图交互测试")
    print("2. 配置管理器测试")
    print("3. 退出")
    
    choice = input("请输入选择 (1-3): ").strip()
    
    if choice == "1":
        test_scope_view()
    elif choice == "2":
        test_config_manager()
    elif choice == "3":
        print("退出测试")
    else:
        print("无效选择")

if __name__ == "__main__":
    main()
