# -*- coding: utf-8 -*-
"""
测试垂直缩放功能
"""

import sys
import logging
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_vertical_scaling():
    """测试垂直缩放功能"""
    from PyQt5 import QtWidgets, QtCore
    from ui.scope_view import ScopeView
    import numpy as np
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("垂直缩放测试")
    main_window.resize(1200, 800)
    
    # 创建中央widget和布局
    central_widget = QtWidgets.QWidget()
    main_window.setCentralWidget(central_widget)
    layout = QtWidgets.QHBoxLayout(central_widget)
    
    # 创建示波器视图
    scope = ScopeView(n_channels=4, sample_rate=1000.0)
    layout.addWidget(scope, 3)
    
    # 创建控制面板
    control_panel = QtWidgets.QWidget()
    control_panel.setMaximumWidth(300)
    layout.addWidget(control_panel, 1)
    
    control_layout = QtWidgets.QVBoxLayout(control_panel)
    
    # 添加说明
    info_label = QtWidgets.QLabel("垂直缩放测试")
    info_label.setStyleSheet("font-weight: bold; font-size: 16px;")
    control_layout.addWidget(info_label)
    
    # 测试说明
    instructions = QtWidgets.QLabel("""
测试步骤：

1. 水平缩放测试：
   - 在示波器区域滚动鼠标滚轮
   - 应该看到: "Time base changed"

2. 垂直缩放测试：
   - 按住Ctrl键
   - 在示波器区域滚动鼠标滚轮
   - 应该看到: "Vertical scale changed"

3. 通道切换测试：
   - 点击下方按钮切换当前通道
   - 再测试垂直缩放

当前通道: CH1
    """)
    instructions.setWordWrap(True)
    instructions.setStyleSheet("background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc;")
    control_layout.addWidget(instructions)
    
    # 通道选择按钮
    channel_buttons = []
    for i in range(4):
        btn = QtWidgets.QPushButton(f"CH{i+1}")
        btn.setCheckable(True)
        btn.setChecked(i == 0)
        btn.clicked.connect(lambda checked, ch=i: scope.set_current_channel(ch))
        btn.clicked.connect(lambda checked, ch=i: update_current_channel(ch))
        channel_buttons.append(btn)
        control_layout.addWidget(btn)
    
    def update_current_channel(ch):
        for i, btn in enumerate(channel_buttons):
            btn.setChecked(i == ch)
        instructions.setText(instructions.text().replace(
            f"当前通道: CH{scope.current_channel+1}",
            f"当前通道: CH{ch+1}"
        ))
    
    # 状态显示
    status_label = QtWidgets.QLabel("状态: 准备测试")
    status_label.setStyleSheet("background-color: #e8f5e8; padding: 5px; border: 1px solid #4CAF50;")
    control_layout.addWidget(status_label)
    
    # 连接信号
    def on_time_base_changed(value):
        status_label.setText(f"水平缩放: {value:.3f} ms/div")
    
    def on_vertical_div_changed(channel, value):
        status_label.setText(f"垂直缩放: CH{channel+1} = {value:.3f} V/div")
    
    scope.timeBaseChanged.connect(on_time_base_changed)
    scope.verticalDivChanged.connect(on_vertical_div_changed)
    
    control_layout.addStretch()
    
    # 生成测试数据
    t = np.linspace(0, 1, 1000)
    test_data = [
        np.sin(2 * np.pi * 50 * t) + 0.1 * np.random.randn(1000),  # CH1
        np.cos(2 * np.pi * 100 * t) + 0.1 * np.random.randn(1000), # CH2
        np.sin(2 * np.pi * 25 * t) * 2 + 0.1 * np.random.randn(1000), # CH3
        np.random.randn(1000) * 0.5  # CH4
    ]
    
    scope.update_tail(test_data)
    scope.set_current_channel(0)
    
    # 显示窗口
    main_window.show()
    
    print("=" * 60)
    print("垂直缩放功能测试")
    print("=" * 60)
    print("请按照右侧说明进行测试")
    print("重点测试：按住Ctrl键滚动滚轮")
    print("应该看到垂直缩放的控制台输出")
    print("=" * 60)
    
    app.exec_()

if __name__ == "__main__":
    test_vertical_scaling()
