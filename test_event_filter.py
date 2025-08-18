# -*- coding: utf-8 -*-
"""
测试事件过滤器修复
验证鼠标和键盘交互是否正常工作
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

def test_all_fixes():
    """测试所有修复"""
    from PyQt5 import QtWidgets, QtCore
    from ui.scope_view import ScopeView
    import numpy as np

    app = QtWidgets.QApplication(sys.argv)

    # 创建主窗口
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("完整功能测试 - 所有修复验证")
    main_window.resize(1400, 900)

    # 创建中央widget和布局
    central_widget = QtWidgets.QWidget()
    main_window.setCentralWidget(central_widget)
    layout = QtWidgets.QHBoxLayout(central_widget)

    # 创建示波器视图
    scope = ScopeView(n_channels=4, sample_rate=1000.0)
    layout.addWidget(scope, 3)  # 占3/4宽度

    # 创建控制面板
    control_panel = QtWidgets.QWidget()
    control_panel.setMaximumWidth(350)
    control_panel.setMinimumWidth(300)
    layout.addWidget(control_panel, 1)  # 占1/4宽度

    control_layout = QtWidgets.QVBoxLayout(control_panel)

    # 添加说明标签
    info_label = QtWidgets.QLabel("测试说明：")
    info_label.setStyleSheet("font-weight: bold; font-size: 14px;")
    control_layout.addWidget(info_label)

    # 添加测试步骤
    steps_text = """
1. 滚轮测试：
   - 在黑色区域滚动滚轮
   - 应该看到时基变化输出

2. Ctrl+滚轮测试：
   - 按住Ctrl滚动滚轮
   - 应该看到垂直缩放输出

3. 拖拽测试：
   - 在黑色区域拖拽鼠标
   - 应该看到水平偏移输出

4. Ctrl+拖拽测试：
   - 按住Ctrl拖拽鼠标
   - 应该看到垂直偏移输出

5. 滚动模式测试：
   - 点击下方按钮切换模式
   - 观察坐标轴变化
    """

    steps_label = QtWidgets.QLabel(steps_text)
    steps_label.setWordWrap(True)
    steps_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc;")
    control_layout.addWidget(steps_label)

    # 添加滚动模式切换按钮
    roll_button = QtWidgets.QPushButton("切换滚动模式")
    roll_button.setCheckable(True)
    roll_button.setChecked(True)
    roll_button.setText("滚动模式: 开启")

    def toggle_roll_mode():
        enabled = roll_button.isChecked()
        scope.set_auto_roll(enabled)
        roll_button.setText(f"滚动模式: {'开启' if enabled else '关闭'}")
        print(f"滚动模式切换为: {'开启' if enabled else '关闭'}")

    roll_button.clicked.connect(toggle_roll_mode)
    control_layout.addWidget(roll_button)

    # 添加通道选择
    channel_label = QtWidgets.QLabel("当前通道:")
    control_layout.addWidget(channel_label)

    channel_combo = QtWidgets.QComboBox()
    channel_combo.addItems([f"CH{i+1}" for i in range(4)])
    channel_combo.currentIndexChanged.connect(scope.set_current_channel)
    control_layout.addWidget(channel_combo)

    # 添加状态显示
    status_label = QtWidgets.QLabel("状态: 准备就绪")
    status_label.setStyleSheet("background-color: #e8f5e8; padding: 5px; border: 1px solid #4CAF50;")
    control_layout.addWidget(status_label)

    # 连接信号更新状态
    def update_status(text):
        status_label.setText(f"状态: {text}")

    scope.timeBaseChanged.connect(lambda v: update_status(f"时基: {v:.3f} ms/div"))
    scope.timeOffsetChanged.connect(lambda v: update_status(f"时间偏移: {v:.3f} s"))
    scope.verticalDivChanged.connect(lambda ch, v: update_status(f"CH{ch+1}垂直: {v:.3f} V/div"))
    scope.verticalOffsetChanged.connect(lambda ch, v: update_status(f"CH{ch+1}偏移: {v:.3f} V"))

    control_layout.addStretch()

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

    # 设置当前通道为CH1
    scope.set_current_channel(0)

    # 显示窗口
    main_window.show()

    print("=" * 80)
    print("完整功能测试启动 - 验证所有修复")
    print("=" * 80)
    print("1. 滚轮事件修复验证")
    print("2. UI布局滚动区域验证")
    print("3. 滚动模式坐标系修复验证")
    print("4. 所有交互功能验证")
    print()
    print("请按照右侧面板的说明进行测试")
    print("观察控制台输出和状态显示")
    print("=" * 80)

    # 添加键盘快捷键退出
    def keyPressEvent(event):
        if event.key() == QtCore.Qt.Key_Escape:
            app.quit()

    main_window.keyPressEvent = keyPressEvent

    # 运行应用
    app.exec_()

if __name__ == "__main__":
    test_all_fixes()
