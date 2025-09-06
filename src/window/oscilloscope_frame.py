# -*- coding: utf-8 -*-
import logging
from pathlib import Path
from typing import List

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

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.scope_widget.sizePolicy().hasHeightForWidth())
        self.scope_widget.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Times New Roman")
        font.setPointSize(12)
        self.scope_widget.setFont(font)
        self.scope_widget.setObjectName("scope_widget")
        self.gridLayout.addWidget(self.scope_widget, 0, 0, 1, 1)

        # 应用配置
        self.scope_widget.max_points_window = self.cfg.max_points_window
        self.scope_widget.max_points_preview = self.cfg.max_points_preview
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
        layout:QtWidgets.QVBoxLayout = self.ch_scroll_area_contents_layout
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
        global_ctrl_widget_layout:QtWidgets.QVBoxLayout = self.global_ctrl_widget_layout
        # 创建通道显示开关按钮组
        channel_toggle_frame = self._create_channel_toggle_buttons()
        # 添加到主布局
        global_ctrl_widget_layout.addWidget(channel_toggle_frame)

        # 设置默认状态
        self.radioButton.setChecked(self.cfg.auto_roll)

        # 设置时基和偏移的默认值
        self.hori_div_spinbox.setValue(self.cfg.get("display.time_base_div", 1.0))
        self.hori_div_spinbox.setSuffix(
            f" {self.cfg.get('display.time_base_unit', 'ms')}/div"
        )

    def _init_data_storage(self):
        """初始化数据存储"""
        ch_defs = self.cfg.channel_defs

        # 环形缓冲区
        self.buffer = RingBuffer(
            n_channels=len(ch_defs), max_bytes=self.cfg.storage_bytes
        )

        # 数据显示模式状态
        self._is_preview_mode = False  # False: 实时模式, True: 预览模式
        self._preview_buffer = None    # 独立的预览数据缓冲区


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

        # HDF5录制和预览功能
        self.radiobtn_recording_wave_enable.toggled.connect(self.on_recording_wave_toggled)
        self.sw_mode.checkedChanged.connect(self.on_mode_switch_changed)
        self.btn_recording_preview.clicked.connect(self.on_recording_preview_clicked)

        # 数据导出功能
        # self._create_export_buttons()
        # self._connect_export_signals()

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

    def on_recording_wave_toggled(self, checked: bool):
        """录制波形单选按钮切换处理"""
        try:
            if checked:
                # 开始录制
                file_path = self.buffer.start_recording(self.cfg.channel_defs, self.cfg.sample_rate)
                logger.info(f"开始录制波形数据到: {file_path}")
            else:
                # 停止录制
                self.buffer.stop_recording()
                logger.info("停止录制波形数据")
        except Exception as e:
            logger.error(f"录制波形切换失败: {e}")
            # 恢复按钮状态
            self.radiobtn_recording_wave_enable.blockSignals(True)
            self.radiobtn_recording_wave_enable.setChecked(not checked)
            self.radiobtn_recording_wave_enable.blockSignals(False)

    def on_mode_switch_changed(self, checked: bool):
        """模式切换按钮处理"""
        try:
            self._is_preview_mode = checked
            if checked:
                logger.info("切换到录波预览模式")
                # 如果有预览数据，刷新预览显示
                if self._preview_buffer is not None:
                    self._refresh_preview_plot()
            else:
                logger.info("切换到实时波形显示模式")
                # 清除预览buffer，释放内存
                self._preview_buffer = None
        except Exception as e:
            logger.error(f"模式切换失败: {e}")

    def on_recording_preview_clicked(self):
        """录制预览按钮点击处理"""
        try:
            from PyQt5.QtWidgets import QFileDialog

            # 打开文件选择对话框
            data_dir = Path("data")
            if not data_dir.exists():
                data_dir.mkdir(parents=True, exist_ok=True)

            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择波形数据文件",
                str(data_dir),
                "HDF5文件 (*.h5);;所有文件 (*)"
            )

            if file_path:
                file_path = Path(file_path)
                logger.info(f"加载波形数据文件: {file_path}")

                # 使用静态方法创建独立的预览buffer
                self._preview_buffer = RingBuffer.create_from_file(file_path)

                # 自动切换到预览模式
                self.sw_mode.blockSignals(True)
                self.sw_mode.setChecked(True)
                self.sw_mode.blockSignals(False)
                self._is_preview_mode = True

                # 刷新预览显示
                self._refresh_preview_plot()

                logger.info("波形数据加载完成，已切换到预览模式")

        except Exception as e:
            logger.error(f"加载波形数据失败: {e}")

    def on_sample_received(self, fmt: int, values: list):
        """接收到采样数据处理"""
        try:
            # fmt: 0xA1 for uint16, 0xA2 for float32 (当前都作为float处理)
            self.buffer.append_batch(values)
        except Exception as e:
            logger.error(f"处理采样数据时出错: {e}")

    def refresh_plot(self):
        """刷新绘图"""
        try:
            # 根据当前模式决定数据源和显示点数
            if not self._is_preview_mode:
                # 实时模式：使用实时buffer的数据
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

    def _refresh_preview_plot(self):
        """刷新预览模式的绘图"""
        try:
            if self._preview_buffer is not None:
                # 预览模式：显示预览buffer中的数据
                arrays = []
                for i in range(self._preview_buffer.n_channels):
                    data = self._preview_buffer.view_tail(i, self.scope_widget.max_points_preview)
                    arrays.append(data)

                # 更新示波器显示
                self.scope_widget.update_tail(arrays, realtime_mode=False)

                # 更新光标值显示
                if self.cursor_control.is_enabled():
                    cursor_values = self.scope_widget.get_cursor_values()
                    self.cursor_control.update_cursor_values(cursor_values)

        except Exception as e:
            logger.error(f"刷新预览绘图时出错: {e}")

    def update_display_points_config(self):
        """更新显示点数配置"""
        try:
            # 更新实时模式显示点数
            self.scope_widget.max_points_window = self.cfg.max_points_window

            # 更新预览模式显示点数
            self._max_points_preview = self.cfg.max_points_preview

            logger.info(f"显示点数配置已更新: 实时模式={self.scope_widget.max_points_window}, 预览模式={self._max_points_preview}")

        except Exception as e:
            logger.error(f"更新显示点数配置失败: {e}")

    def get_current_max_points(self) -> int:
        """获取当前模式的最大显示点数"""
        if self._is_preview_mode:
            return self._max_points_preview
        else:
            return self.scope_widget.max_points_window

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

    def _create_export_buttons(self):
        """创建数据导出按钮"""
        try:
            # 在全局控制区域添加导出按钮组
            export_group = QtWidgets.QGroupBox("数据导出")
            export_layout = QtWidgets.QVBoxLayout(export_group)

            # 导出当前数据按钮
            self.btn_export_current = QtWidgets.QPushButton("导出当前数据")
            self.btn_export_current.setToolTip("导出当前缓冲区中的数据")
            export_layout.addWidget(self.btn_export_current)

            # 导出录制文件按钮
            self.btn_export_file = QtWidgets.QPushButton("导出录制文件")
            self.btn_export_file.setToolTip("选择并导出已录制的HDF5文件")
            export_layout.addWidget(self.btn_export_file)

            # 批量导出按钮
            self.btn_batch_export = QtWidgets.QPushButton("批量导出")
            self.btn_batch_export.setToolTip("批量导出多种格式")
            export_layout.addWidget(self.btn_batch_export)

            # 添加到主布局
            self.global_ctrl_widget_layout.addWidget(export_group)

        except Exception as e:
            logger.error(f"创建导出按钮失败: {e}")

    def _connect_export_signals(self):
        """连接导出功能信号"""
        try:
            self.btn_export_current.clicked.connect(self.on_export_current_data)
            self.btn_export_file.clicked.connect(self.on_export_file)
            self.btn_batch_export.clicked.connect(self.on_batch_export)
        except Exception as e:
            logger.error(f"连接导出信号失败: {e}")

    def _show_format_selection_dialog(self, title: str) -> List[str]:
        """显示格式选择对话框"""
        try:
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(title)
            dialog.setModal(True)
            dialog.resize(300, 200)

            layout = QtWidgets.QVBoxLayout(dialog)

            # 添加说明
            label = QtWidgets.QLabel("请选择要导出的格式:")
            layout.addWidget(label)

            # 格式选择复选框
            self.format_checkboxes = {}
            formats = [
                ('csv', 'CSV格式 (Excel兼容)'),
                ('excel', 'Excel格式 (.xlsx)'),
                ('matlab', 'MATLAB格式 (.mat)'),
                ('hdf5', 'HDF5格式 (原始)')
            ]

            for fmt_key, fmt_name in formats:
                checkbox = QtWidgets.QCheckBox(fmt_name)
                if fmt_key == 'csv':  # 默认选择CSV
                    checkbox.setChecked(True)
                self.format_checkboxes[fmt_key] = checkbox
                layout.addWidget(checkbox)

            # 按钮
            button_layout = QtWidgets.QHBoxLayout()
            ok_button = QtWidgets.QPushButton("确定")
            cancel_button = QtWidgets.QPushButton("取消")

            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)

            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)

            # 显示对话框
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                selected_formats = []
                for fmt_key, checkbox in self.format_checkboxes.items():
                    if checkbox.isChecked():
                        selected_formats.append(fmt_key)
                return selected_formats
            else:
                return []

        except Exception as e:
            logger.error(f"显示格式选择对话框失败: {e}")
            return ['csv']  # 默认返回CSV格式

    def on_export_current_data(self):
        """导出当前缓冲区数据"""
        try:
            # 显示格式选择对话框
            formats = self._show_format_selection_dialog("导出当前数据")
            if not formats:
                return

            # 显示文件保存对话框
            output_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self, "选择导出目录", "data"
            )
            if not output_dir:
                return

            # 显示进度对话框
            progress = QtWidgets.QProgressDialog("正在导出数据...", "取消", 0, 100, self)
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()

            # 执行导出
            QtCore.QTimer.singleShot(100, lambda: self._do_export_current(
                formats, Path(output_dir), progress
            ))

        except Exception as e:
            logger.error(f"导出当前数据失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _do_export_current(self, formats: List[str], output_dir: Path, progress: QtWidgets.QProgressDialog):
        """执行当前数据导出"""
        try:
            progress.setValue(10)
            if progress.wasCanceled():
                return

            # 使用当前buffer导出数据
            results = self.buffer.export_data(formats, output_dir, "current_data")

            progress.setValue(90)
            if progress.wasCanceled():
                return

            # 显示结果
            self._show_export_results(results, "当前数据导出完成")
            progress.setValue(100)

        except Exception as e:
            logger.error(f"执行当前数据导出失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"导出失败: {e}")
        finally:
            progress.close()

    def on_export_file(self):
        """导出录制文件"""
        try:
            # 选择HDF5文件
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "选择HDF5文件", "data", "HDF5 Files (*.h5 *.hdf5)"
            )
            if not file_path:
                return

            # 显示格式选择对话框
            formats = self._show_format_selection_dialog("导出录制文件")
            if not formats:
                return

            # 显示进度对话框
            progress = QtWidgets.QProgressDialog("正在导出文件...", "取消", 0, 100, self)
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()

            # 执行导出
            QtCore.QTimer.singleShot(100, lambda: self._do_export_file(
                Path(file_path), formats, progress
            ))

        except Exception as e:
            logger.error(f"导出文件失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _do_export_file(self, file_path: Path, formats: List[str], progress: QtWidgets.QProgressDialog):
        """执行文件导出"""
        try:
            progress.setValue(10)
            if progress.wasCanceled():
                return

            # 使用persistence_manager导出
            results = self.buffer.persistence_manager.export_batch(file_path, formats)

            progress.setValue(90)
            if progress.wasCanceled():
                return

            # 显示结果
            self._show_export_results(results, f"文件 {file_path.name} 导出完成")
            progress.setValue(100)

        except Exception as e:
            logger.error(f"执行文件导出失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"导出失败: {e}")
        finally:
            progress.close()

    def on_batch_export(self):
        """批量导出"""
        try:
            # 选择多个HDF5文件
            file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self, "选择HDF5文件", "data", "HDF5 Files (*.h5 *.hdf5)"
            )
            if not file_paths:
                return

            # 显示格式选择对话框
            formats = self._show_format_selection_dialog("批量导出")
            if not formats:
                return

            # 选择输出目录
            output_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self, "选择导出目录", "data"
            )
            if not output_dir:
                return

            # 显示进度对话框
            progress = QtWidgets.QProgressDialog("正在批量导出...", "取消", 0, len(file_paths), self)
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()

            # 执行批量导出
            QtCore.QTimer.singleShot(100, lambda: self._do_batch_export(
                [Path(p) for p in file_paths], formats, Path(output_dir), progress
            ))

        except Exception as e:
            logger.error(f"批量导出失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"批量导出失败: {e}")

    def _do_batch_export(self, file_paths: List[Path], formats: List[str],
                        output_dir: Path, progress: QtWidgets.QProgressDialog):
        """执行批量导出"""
        try:
            all_results = {}

            for i, file_path in enumerate(file_paths):
                if progress.wasCanceled():
                    break

                progress.setLabelText(f"正在导出: {file_path.name}")
                progress.setValue(i)

                try:
                    # 为每个文件创建子目录
                    file_output_dir = output_dir / file_path.stem
                    file_output_dir.mkdir(exist_ok=True)

                    # 导出文件
                    results = self.buffer.persistence_manager.export_batch(
                        file_path, formats, file_output_dir
                    )
                    all_results[file_path.name] = results

                except Exception as e:
                    logger.error(f"导出文件 {file_path.name} 失败: {e}")
                    all_results[file_path.name] = {"error": str(e)}

            progress.setValue(len(file_paths))

            # 显示批量导出结果
            self._show_batch_export_results(all_results)

        except Exception as e:
            logger.error(f"执行批量导出失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"批量导出失败: {e}")
        finally:
            progress.close()

    def _show_export_results(self, results: dict, title: str):
        """显示导出结果"""
        try:
            if not results:
                QtWidgets.QMessageBox.warning(self, "警告", "没有成功导出任何文件")
                return

            message = f"{title}\n\n导出的文件:\n"
            for fmt, file_path in results.items():
                message += f"• {fmt.upper()}: {file_path}\n"

            QtWidgets.QMessageBox.information(self, "导出完成", message)

        except Exception as e:
            logger.error(f"显示导出结果失败: {e}")

    def _show_batch_export_results(self, all_results: dict):
        """显示批量导出结果"""
        try:
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("批量导出结果")
            dialog.setModal(True)
            dialog.resize(500, 400)

            layout = QtWidgets.QVBoxLayout(dialog)

            # 创建文本显示区域
            text_edit = QtWidgets.QTextEdit()
            text_edit.setReadOnly(True)

            # 构建结果文本
            result_text = "批量导出结果:\n\n"
            success_count = 0
            error_count = 0

            for file_name, results in all_results.items():
                result_text += f"文件: {file_name}\n"

                if "error" in results:
                    result_text += f"  ❌ 错误: {results['error']}\n"
                    error_count += 1
                else:
                    result_text += "  ✅ 成功导出:\n"
                    for fmt, file_path in results.items():
                        result_text += f"    • {fmt.upper()}: {file_path}\n"
                    success_count += 1

                result_text += "\n"

            result_text += f"总结: 成功 {success_count} 个, 失败 {error_count} 个"

            text_edit.setPlainText(result_text)
            layout.addWidget(text_edit)

            # 关闭按钮
            close_button = QtWidgets.QPushButton("关闭")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)

            dialog.exec_()

        except Exception as e:
            logger.error(f"显示批量导出结果失败: {e}")
