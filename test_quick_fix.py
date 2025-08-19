# -*- coding: utf-8 -*-
"""
快速修复测试
"""

import sys
import logging
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_scope_only():
    """只测试示波器组件"""
    from PyQt5 import QtWidgets, QtCore
    from ui.scope_view import ScopeWidget
    import numpy as np
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建示波器视图
    scope = ScopeWidget(n_channels=2, sample_rate=1000.0)
    scope.setWindowTitle("示波器交互测试")
    scope.resize(800, 600)
    scope.show()
    
    # 生成简单测试数据
    t = np.linspace(0, 1, 100)
    test_data = [
        np.sin(2 * np.pi * 10 * t),  # CH1: 10Hz正弦波
        np.cos(2 * np.pi * 20 * t),  # CH2: 20Hz余弦波
    ]
    
    # 更新显示
    scope.update_tail(test_data)
    scope.set_current_channel(0)
    
    print("=" * 50)
    print("快速测试启动")
    print("=" * 50)
    print("测试项目:")
    print("1. 滚轮 -> 时基缩放")
    print("2. Ctrl+滚轮 -> 垂直缩放")
    print("3. 拖拽 -> 水平偏移")
    print("4. Ctrl+拖拽 -> 垂直偏移")
    print("观察控制台输出...")
    print("=" * 50)
    
    app.exec_()

if __name__ == "__main__":
    test_scope_only()
