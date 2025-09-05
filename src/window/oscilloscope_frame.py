# -*- coding: utf-8 -*-
import logging

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui

from ..config.scope_config_manager import ScopeConfigManager
from ..data.data_buffer import RingBuffer
from ..ui import Ui_Form
from ..ui.channel_config_widget import ChannelConfigWidget, CursorControlWidget
from ..ui.scope_view import ScopeWidget
from ..communication.scope_ipc import ScopeIPC

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("oscilloscope.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


class OscilloscopeFrame(QtWidgets.QFrame, Ui_Form):
    """示波器窗口类 - 仅支持IPC模式"""

    def __init__(self, scope_ipc, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        # 使用示波器专用配置
        self.cfg = ScopeConfigManager()
        self.scope_ipc = scope_ipc
        self.data_receiver = scope_ipc.get_receiver()

        logger.info("示波器启动 - IPC模式")

        # 设置窗口标题和图标
        self.setWindowTitle(f"{self.cfg.app_name} v{self.cfg.app_version}")

        # 初始化组件
        self._init_scope_view_ui()
        self._init_global_controls_ui()
        self._init_channel_controls_ui()
        self._init_data_storage()
        self._init_timers()

        # 连接信号
        self._connect_signals()

        # 加载配置
        self._load_configuration()

        # 信号就绪
        self.scope_ipc.signal_scope_ready()


    def _init_scope_view_ui(self):
        """初始化示波器视图"""
        ch_defs = self.cfg.channel_defs
        self.scope_widget = ScopeWidget(
            n_channels=len(ch_defs),
            sample_rate=self.cfg.sample_rate,
            cfg=self.cfg,
            parent=self,
        )

        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.scope_widget.sizePolicy().hasHeightForWidth())
        self.scope_widget.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Times New Roman")
        font.setPointSize(12)
        self.scope_widget.setFont(font)
        self.scope_widget.setObjectName("scope_widget")
        self.gridLayout_7.addWidget(self.scope_widget, 0, 0, 1, 1)

        # 应用配置
        self.scope_widget.max_points_window = self.cfg.max_points_window
        self.scope_widget.reset_time_offset(self.cfg.auto_roll)

        # 设置通道颜色和参数
        for i, ch_config in enumerate(ch_defs):
            color = ch_config.get("color", pg.intColor(i))
            self.scope_widget.set_channel_pen(i, color)
            self.scope_widget.set_channel_enabled(i, ch_config.get("enabled", True))

            # 设置垂直挡位和偏移
            self.scope_widget.set_vertical_scale(
                i,
                ch_config.get("vertical_div", 1.0),
            )
            self.scope_widget.set_vertical_offset(
                i, ch_config.get("vertical_offset", 0.0)
            )

    def _init_channel_controls_ui(self):
        """初始化通道控制界面"""
        # 填充通道列表
        ch_defs = self.cfg.channel_defs
        self.ch_setting_comboBox.addItems([c["name"] for c in ch_defs])

        # 创建通道配置组件
        self.channel_configs = []
        for i, ch_config in enumerate(ch_defs):
            config_widget = ChannelConfigWidget(i, ch_config)
            self.channel_configs.append(config_widget)

        # 创建光标控制组件
        self.cursor_control = CursorControlWidget(ch_defs, self.scope_widget)

        # 获取现有布局
        layout = self.ch_scroll_area_contents.layout()
        # 添加重新加载配置按钮
        layout.addWidget(self.reload_conf_btn)
        # 隐藏所有通道配置组件
        for config_widget in self.channel_configs:
            config_widget.setVisible(False)
            layout.addWidget(config_widget)
        # 添加光标控制
        layout.addWidget(self.cursor_control)
        # 显示当前CH的面板
        self._show_current_channel_config()

    def _create_channel_toggle_buttons(self):
        """创建通道显示开关按钮组"""
        # 在global_ctrl_widget中添加通道开关区域
        self.channel_toggle_frame = QtWidgets.QFrame(self.global_ctrl_widget)
        self.channel_toggle_frame.setFrameStyle(QtWidgets.QFrame.StyledPanel)

        # 创建布局
        toggle_layout = QtWidgets.QVBoxLayout(self.channel_toggle_frame)
        toggle_layout.setContentsMargins(4, 4, 4, 4)

        # 标题
        title_label = QtWidgets.QLabel("通道显示")
        title_label.setStyleSheet("font-weight: bold;")
        toggle_layout.addWidget(title_label)

        # 按钮网格布局
        button_grid = QtWidgets.QGridLayout()
        toggle_layout.addLayout(button_grid)

        # 创建通道开关按钮
        self.channel_toggle_buttons = []
        ch_defs = self.cfg.channel_defs

        for i, ch_config in enumerate(ch_defs):
            button = QtWidgets.QPushButton(ch_config["name"])
            button.setCheckable(True)
            button.setChecked(ch_config.get("enabled", True))
            button.setFixedSize(60, 30)

            # 设置按钮颜色
            color = ch_config.get("color", "#FFFFFF")
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: 2px solid #666666;
                    border-radius: 3px;
                    color: black;
                    font-weight: bold;
                }}
                QPushButton:checked {{
                    border: 2px solid #FFFFFF;
                }}
                QPushButton:!checked {{
                    background-color: #333333;
                    color: #666666;
                }}
            """)

            # 连接信号
            button.toggled.connect(
                lambda checked, ch=i: self.on_channel_toggle(ch, checked)
            )

            # 添加到网格布局（4列）
            row = i // 5
            col = i % 5
            button_grid.addWidget(button, row, col)

            self.channel_toggle_buttons.append(button)

        return self.channel_toggle_frame

    def on_channel_toggle(self, channel: int, enabled: bool):
        """通道显示开关处理"""
        # 更新示波器显示
        self.scope_widget.set_channel_enabled(channel, enabled)

        # 更新配置
        ch_config = self.cfg.get_channel_config(channel)
        ch_config["enabled"] = enabled
        self.cfg.set_channel_config(channel, ch_config)

        # 更新通道配置组件
        if 0 <= channel < len(self.channel_configs):
            config_widget = self.channel_configs[channel]
            config_widget.enabled_checkbox.blockSignals(True)
            config_widget.enabled_checkbox.setChecked(enabled)
            config_widget.enabled_checkbox.blockSignals(False)

    def _show_current_channel_config(self):
        """设置通道标签页布局"""
        # 隐藏所有通道配置组件
        for config in self.channel_configs:
            config.setVisible(False)

        # 显示当前选中通道的配置组件
        current_channel = self.ch_setting_comboBox.currentIndex()
        if 0 <= current_channel < len(self.channel_configs):
            config_widget = self.channel_configs[current_channel]
            config_widget.setVisible(True)

    def _init_global_controls_ui(self):
        """初始化全局控制"""
        global_ctrl_widget_layout = self.global_ctrl_widget.layout()
        # 确保自动滚动按钮存在
        self.radioButton = QtWidgets.QRadioButton(self.global_ctrl_widget)
        self.radioButton.setText("自动滚动")
        global_ctrl_widget_layout.addWidget(self.radioButton, 4, 0, 1, 1)

        # 创建通道显示开关按钮组
        channel_toggle_frame = self._create_channel_toggle_buttons()
        # 添加到主布局
        global_ctrl_widget_layout.addWidget(channel_toggle_frame, 5, 0, 1, 1)

        # 设置默认状态
        self.radioButton.setChecked(self.cfg.auto_roll)

        # 设置时基和偏移的默认值
        self.hori_div_spinbox.setValue(self.cfg.get("display.time_base_div", 1.0))
        self.hori_div_spinbox.setSuffix(
            f" {self.cfg.get('display.time_base_unit', 'ms')}/div"
        )

        self.hori_div_offset_spinbox.setValue(self.cfg.get("display.time_offset", 0.0))

    def _init_data_storage(self):
        """初始化数据存储"""
        ch_defs = self.cfg.channel_defs

        # 环形缓冲区
        self.buffer = RingBuffer(
            n_channels=len(ch_defs), max_bytes=self.cfg.storage_bytes
        )


    def _init_timers(self):
        """初始化定时器"""
        # 绘图刷新定时器
        refresh_interval = 1000 // self.cfg.refresh_rate  # 转换为毫秒
        self._plot_timer = QtCore.QTimer(self)
        self._plot_timer.setInterval(refresh_interval)
        self._plot_timer.timeout.connect(self.refresh_plot)

        # IPC数据接收定时器
        self._ipc_timer = QtCore.QTimer(self)
        self._ipc_timer.setInterval(1)  # 1ms高频接收
        self._ipc_timer.timeout.connect(self._receive_ipc_data)
        self._ipc_timer.start()
        logger.info("IPC数据接收定时器已启动")

        # 关闭信号检查定时器
        self._shutdown_timer = QtCore.QTimer(self)
        self._shutdown_timer.setInterval(100)  # 100ms检查一次
        self._shutdown_timer.timeout.connect(self._check_shutdown_signal)
        self._shutdown_timer.start()

        # 统计信息更新定时器
        self._stats_timer = QtCore.QTimer(self)
        self._stats_timer.setInterval(500)  # 每秒更新一次
        self._stats_timer.timeout.connect(self.update_statistics)
        self._stats_timer.start()

        # 启动绘图定时器
        self._plot_timer.start()

    def _receive_ipc_data(self):
        """接收IPC数据（高频调用）"""
        if not self.data_receiver:
            return

        try:
            # 批量接收数据以提高性能
            samples = self.data_receiver.receive_batch(max_count=50, timeout=0.001)

            for sample in samples:
                # 处理接收到的采样数据
                self.on_sample_received(sample.packet_type, sample.channels)

        except Exception as e:
            logger.error(f"接收IPC数据失败: {e}")

    def _check_shutdown_signal(self):
        """检查关闭信号"""
        if self.scope_ipc and self.scope_ipc.is_shutdown_requested():
            logger.info("收到关闭信号，示波器进程即将退出")
            self.close()

    def _connect_signals(self):
        """连接信号槽"""
        # 自动滚动切换
        self.radioButton.toggled.connect(self.on_auto_roll_toggled)

        # 通道选择改变
        self.ch_setting_comboBox.currentIndexChanged.connect(
            self.on_channel_selection_changed
        )

        # 通道配置改变
        for config_widget in self.channel_configs:
            config_widget.configChanged.connect(self.on_channel_config_changed)

        # 光标控制
        self.cursor_control.cursorEnabledChanged.connect(
            self.scope_widget.enable_cursors
        )
        self.cursor_control.cursorChanged.connect(self.scope_widget.set_cursor_position)

        # 示波器信号连接
        self.scope_widget.timeBaseChanged.connect(self.on_scope_time_base_changed)
        self.scope_widget.timeOffsetChanged.connect(self.on_scope_time_offset_changed)
        self.scope_widget.verticalDivChanged.connect(self.on_scope_vertical_div_changed)
        self.scope_widget.verticalOffsetChanged.connect(
            self.on_scope_vertical_offset_changed
        )

        # 重新加载配置
        self.reload_conf_btn.clicked.connect(self.reload_configuration)

        # 测试按钮
        self.test_btn.setText("显示寄存器管理")
        self.test_btn.clicked.connect(self.on_test_clicked_cb)

        # 时基控制
        self.hori_div_spinbox.valueChanged.connect(self.on_time_base_changed)
        self.hori_div_offset_spinbox.valueChanged.connect(self.on_time_offset_changed)

    def _load_configuration(self):
        """加载配置到UI"""
        # 设置示波器参数
        # self.scope_widget.set_time_base(
        #     self.cfg.get("display.time_base_div", 1.0),
        #     self.cfg.get("display.time_base_unit", "ms"),
        # )
        self.scope_widget.set_time_offset(self.cfg.get("display.time_offset", 0.0))

        # 设置光标
        cursor_config = self.cfg.get("cursors", {})
        if cursor_config.get("enabled", False):
            self.cursor_control.set_enabled(True)
            self.scope_widget.enable_cursors(True)

            # 设置光标位置
            for cursor_name in ["x1", "x2", "y1", "y2"]:
                if cursor_name in cursor_config:
                    self.scope_widget.set_cursor_position(
                        cursor_name, cursor_config[cursor_name]
                    )

    # 事件处理方法
    def on_auto_roll_toggled(self, enabled: bool):
        """自动滚动切换处理"""
        # 设置示波器滚动模式
        self.scope_widget.reset_time_offset(enabled)
        # 保存到配置
        self.cfg.set("display.auto_roll", enabled)

    def on_channel_selection_changed(self, index: int):
        """通道选择改变处理"""
        if 0 <= index < len(self.channel_configs):
            # 设置示波器当前通道
            self.scope_widget.set_current_channel(index)

            # 重新布局以显示选中通道的配置
            self._show_current_channel_config()

            # 更新tab标题
            ch_name = self.cfg.channel_defs[index]["name"]
            self.ch_ctrl_widget.setTabText(0, ch_name)

    def on_channel_config_changed(self, channel_index: int, config: dict):
        """通道配置改变处理"""
        # 更新配置管理器
        self.cfg.set_channel_config(channel_index, config)

        # 应用到示波器视图
        if config.get("color"):
            self.scope_widget.set_channel_pen(channel_index, config["color"])

        enabled = config.get("enabled", True)
        self.scope_widget.set_channel_enabled(channel_index, enabled)

        # 同步通道开关按钮
        if hasattr(self, "channel_toggle_buttons") and 0 <= channel_index < len(
            self.channel_toggle_buttons
        ):
            button = self.channel_toggle_buttons[channel_index]
            button.blockSignals(True)
            button.setChecked(enabled)
            button.blockSignals(False)

        if "vertical_div" in config:
            self.scope_widget.set_vertical_scale(channel_index, config["vertical_div"])

        if "vertical_offset" in config:
            self.scope_widget.set_vertical_offset(
                channel_index, config["vertical_offset"]
            )

        logger.debug(f"通道{channel_index + 1}配置已更新")

    def on_time_base_changed(self, value: float):
        """时基改变处理"""
        # unit = self.cfg.get("display.time_base_unit", "ms")
        # self.scope_widget.set_time_base(value, unit)
        self.cfg.set("display.time_base_div", value)

    def on_time_offset_changed(self, value: float):
        """时间偏移改变处理"""
        # self.scope_widget.set_time_offset(value)
        self.cfg.set("display.time_offset", value)

    def on_scope_time_base_changed(self, value: float):
        """示波器时基改变处理（来自鼠标滚轮）"""
        # 更新UI控件，避免循环调用
        if hasattr(self, "doubleSpinBox"):
            self.hori_div_spinbox.blockSignals(True)
            self.hori_div_spinbox.setValue(value)
            self.hori_div_spinbox.blockSignals(False)

        # 保存到配置
        self.cfg.set("display.time_base_div", value)

    def on_scope_time_offset_changed(self, value: float):
        """示波器时间偏移改变处理（来自鼠标拖拽）"""
        # 更新UI控件，避免循环调用
        if hasattr(self, "doubleSpinBox_2"):
            self.hori_div_offset_spinbox.blockSignals(True)
            self.hori_div_offset_spinbox.setValue(value)
            self.hori_div_offset_spinbox.blockSignals(False)

        # 保存到配置
        self.cfg.set("display.time_offset", value)

    def on_scope_vertical_div_changed(self, channel: int, value: float):
        """示波器垂直挡位改变处理（来自Ctrl+滚轮）"""
        # 更新通道配置
        if 0 <= channel < len(self.channel_configs):
            config_widget = self.channel_configs[channel]
            config_widget.vertical_div_spinbox.blockSignals(True)
            config_widget.vertical_div_spinbox.setValue(value)
            config_widget.vertical_div_spinbox.blockSignals(False)

        # 保存到配置
        ch_config = self.cfg.get_channel_config(channel)
        ch_config["vertical_div"] = value
        self.cfg.set_channel_config(channel, ch_config)

    def on_scope_vertical_offset_changed(self, channel: int, value: float):
        """示波器垂直偏移改变处理（来自Ctrl+拖拽）"""
        # 更新通道配置
        if 0 <= channel < len(self.channel_configs):
            config_widget = self.channel_configs[channel]
            config_widget.vertical_offset_spinbox.blockSignals(True)
            config_widget.vertical_offset_spinbox.setValue(value)
            config_widget.vertical_offset_spinbox.blockSignals(False)

        # 保存到配置
        ch_config = self.cfg.get_channel_config(channel)
        ch_config["vertical_offset"] = value
        self.cfg.set_channel_config(channel, ch_config)

    def on_sample_received(self, fmt: int, values: list):
        """接收到采样数据处理"""
        try:
            # fmt: 0xA1 for uint16, 0xA2 for float32 (当前都作为float处理)
            for ch in range(min(self.buffer.n_channels, len(values))):
                sample_value = float(values[ch])
                self.buffer.append(ch, (sample_value,))

        except Exception as e:
            logger.error(f"处理采样数据时出错: {e}")

    def refresh_plot(self):
        """刷新绘图"""
        try:
            # 获取每个通道的数据
            arrays = []
            for i in range(self.buffer.n_channels):
                data = self.buffer.view_tail(i, self.scope_widget.max_points_window)
                arrays.append(data)

            # 更新示波器显示
            self.scope_widget.update_tail(arrays)

            # 更新光标值显示
            if self.cursor_control.is_enabled():
                cursor_values = self.scope_widget.get_cursor_values()
                self.cursor_control.update_cursor_values(cursor_values)

        except Exception as e:
            logger.error(f"刷新绘图时出错: {e}")

    def update_statistics(self):
        """更新统计信息"""
        try:
            current_channel = self.ch_setting_comboBox.currentIndex()
            if 0 <= current_channel < len(self.channel_configs):
                stats = self.buffer.get_statistics(current_channel)
                self.channel_configs[current_channel].update_statistics(stats)
        except Exception as e:
            logger.error(f"更新统计信息时出错: {e}")

    def reload_configuration(self):
        """重新加载配置"""
        try:
            self.cfg.load()

            # 重新初始化相关组件
            self._load_configuration()

            # 更新通道列表
            self.ch_setting_comboBox.clear()
            ch_defs = self.cfg.channel_defs
            self.ch_setting_comboBox.addItems([c["name"] for c in ch_defs])

            # 更新通道颜色
            for i, ch_config in enumerate(ch_defs):
                color = ch_config.get("color", pg.intColor(i))
                self.scope_widget.set_channel_pen(i, color)

            logger.info("配置已重新加载")

        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")

    def on_test_clicked_cb(self):
        """显示/隐藏寄存器管理窗口"""
        # try:
        #     if hasattr(self, "register_tab_widget") and self.register_tab_widget:
        #         if self.register_tab_widget.isVisible():
        #             self.register_tab_widget.hide()
        #             self.test_btn.setText("显示寄存器管理")
        #             logger.info("隐藏寄存器管理窗口")
        #         else:
        #             self.register_tab_widget.show()
        #             self.register_tab_widget.raise_()  # 将窗口置于前台
        #             self.register_tab_widget.activateWindow()  # 激活窗口
        #             self.test_btn.setText("隐藏寄存器管理")
        #             logger.info("显示寄存器管理窗口")
        #     else:
        #         logger.warning("寄存器管理窗口未初始化")
        # except Exception as e:
        #     logger.error(f"切换寄存器管理窗口显示状态失败: {e}")
  

    def closeEvent(self, event: QtGui.QCloseEvent):
        """窗口关闭事件"""
        try:
            logger.info("示波器窗口开始关闭")

            # 停止定时器
            self._plot_timer.stop()
            self._stats_timer.stop()
            self._ipc_timer.stop()
            self._shutdown_timer.stop()

            # 保存配置
            self.cfg.save()

            logger.info("示波器窗口正常退出")
            event.accept()

        except Exception as e:
            logger.error(f"关闭示波器窗口时出错: {e}")
            event.accept()
