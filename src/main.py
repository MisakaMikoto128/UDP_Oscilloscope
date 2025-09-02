# -*- coding: utf-8 -*-
"""
UDP示波器主程序
电机控制板上位机软件
"""

import asyncio
import sys
import logging
from pathlib import Path
import winloop
from qasync import asyncClose, asyncSlot
import traceback
import threading
import time
from communication.protocol import (
    ProtocolParser,
    MotorSampleData,
    SysREGsUpData,
    SysREGsSetResp,
)
from ui.register_integration import RegisterTabWidget

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

# 导入PyQt5和相关模块
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

# 导入项目模块
from main_window.main_window import Ui_MainWindow
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout
from ui.scope_view import ScopeWidget
from ui.channel_config_widget import ChannelConfigWidget, CursorControlWidget
from config.config_manager import ConfigManager
from data.data_buffer import RingBuffer
from data.storage import PersistentStorage
from communication.udp_master import UDPMaster


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    """主窗口类"""

    def __init__(self, cfg: ConfigManager):
        super().__init__()
        self.setupUi(self)

        # 配置管理器
        self.cfg = cfg

        # 设置窗口标题和图标
        self.setWindowTitle(f"{cfg.app_name} v{cfg.app_version}")

        # 初始化组件
        self._init_scope_view_ui()
        self._init_global_controls_ui()
        self._init_channel_controls_ui()
        self._init_register_controls_ui()
        self._init_data_storage()
        self._init_communication()
        self._init_timers()

        # 连接信号
        self._connect_signals()

        # 加载配置
        self._load_configuration()

        logger.info("主窗口初始化完成")

    def _init_scope_view_ui(self):
        """初始化示波器视图"""
        ch_defs = self.cfg.channel_defs
        self.scope_widget = ScopeWidget(
            n_channels=len(ch_defs),
            sample_rate=self.cfg.sample_rate,
            cfg=self.cfg,
            parent=self.centralwidget,
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
        self.gridLayout_4.addWidget(self.scope_widget, 0, 0, 1, 1)

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

    def _init_register_controls_ui(self):
        """初始化寄存器控制界面"""
        try:
            # 寄存器配置文件路径
            config_file_path = "config/registers_config.json"

            # 创建寄存器管理标签页
            self.register_tab_widget = RegisterTabWidget(
                config_file_path=config_file_path,
                device_reg_set_func=self.device_reg_set,
            )

            # 设置窗口属性
            # self.register_tab_widget.setWindowTitle("寄存器管理界面")
            # self.register_tab_widget.setGeometry(100, 100, 1000, 700)  # 设置窗口大小和位置

            # 默认隐藏，通过按钮控制显示
            self.register_tab_widget.show()

            logger.info("寄存器控制界面初始化完成")

        except Exception as e:
            logger.error(f"初始化寄存器控制界面失败: {e}")
            # 创建错误提示标签
            error_label = QtWidgets.QLabel(f"寄存器管理界面加载失败: {e}")
            error_label.setStyleSheet("color: red; padding: 20px;")
            if not hasattr(self.tab_ctrl, 'layout') or self.tab_ctrl.layout() is None:
                layout = QtWidgets.QVBoxLayout(self.tab_ctrl)
            else:
                layout = self.tab_ctrl.layout()
            layout.addWidget(error_label)

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

        # 永久存储
        self.persistent_storage = PersistentStorage(
            file_path=self.cfg.persistent_path,
            n_channels=len(ch_defs),
            enabled=self.cfg.enable_persistent_storage,
        )

    def _init_communication(self):
        """初始化通信"""
        self.receiver = UDPMaster(
            host=self.cfg.udp_host,
            port=self.cfg.udp_port,
            on_sample=self.on_sample_received,
            on_sys_regs_upload=self.on_sys_regs_upload,
        )

        # 连接在线状态信号
        self.receiver.client_online_status_changed.connect(
            self.register_tab_widget.set_online_status
        )

    def _init_timers(self):
        """初始化定时器"""
        # 绘图刷新定时器
        refresh_interval = 1000 // self.cfg.refresh_rate  # 转换为毫秒
        self._plot_timer = QtCore.QTimer(self)
        self._plot_timer.setInterval(refresh_interval)
        self._plot_timer.timeout.connect(self.refresh_plot)

        # 统计信息更新定时器
        self._stats_timer = QtCore.QTimer(self)
        self._stats_timer.setInterval(500)  # 每秒更新一次
        self._stats_timer.timeout.connect(self.update_statistics)
        self._stats_timer.start()

        # 启动绘图定时器
        self._plot_timer.start()

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
            # 添加到缓冲区
            for ch in range(min(self.buffer.n_channels, len(values))):
                sample_value = float(values[ch])
                self.buffer.append(ch, (sample_value,))

                # 永久存储
                if self.persistent_storage.enabled:
                    self.persistent_storage.store_data(ch, [sample_value])

        except Exception as e:
            logger.error(f"处理采样数据时出错: {e}")

    def on_sys_regs_upload(self, sys_reg_upload: SysREGsUpData):
        """接收到配置数据处理"""
        try:
            # 将寄存器数据传递给寄存器管理界面
            if hasattr(self, 'register_tab_widget') and self.register_tab_widget:
                self.register_tab_widget.on_sys_regs_upload(sys_reg_upload)

            logger.debug(f"收到 {sys_reg_upload.reg_num} 个寄存器数据")

        except Exception as e:
            logger.error(f"处理寄存器上传数据时出错: {e}")

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
        try:
            if hasattr(self, 'register_tab_widget') and self.register_tab_widget:
                if self.register_tab_widget.isVisible():
                    self.register_tab_widget.hide()
                    self.test_btn.setText("显示寄存器管理")
                    logger.info("隐藏寄存器管理窗口")
                else:
                    self.register_tab_widget.show()
                    self.register_tab_widget.raise_()  # 将窗口置于前台
                    self.register_tab_widget.activateWindow()  # 激活窗口
                    self.test_btn.setText("隐藏寄存器管理")
                    logger.info("显示寄存器管理窗口")
            else:
                logger.warning("寄存器管理窗口未初始化")
        except Exception as e:
            logger.error(f"切换寄存器管理窗口显示状态失败: {e}")

    async def device_reg_set(self, regAddrStart: int, datas: list[int]) -> bool:
        """发送配置到下位机

        Returns:
            bool: 配置是否成功
        """
        try:
            target_addr = (self.cfg.target_host, self.cfg.target_port)
            success = await self.receiver.reg_set(
                regAddrStart=regAddrStart, datas=datas, target_addr=target_addr
            )
            if success:
                logger.info("配置已成功发送到下位机")
            else:
                logger.warning("配置发送失败")
            return success
        except TimeoutError:
            logger.error("发送配置到下位机超时")
            return False
        except Exception as e:
            logger.error(f"发送配置到下位机失败: {e}")
            return False

    @asyncClose
    async def closeEvent(self, event: QtGui.QCloseEvent):
        """窗口关闭事件"""
        try:
            # 停止定时器
            if hasattr(self, "_plot_timer"):
                self._plot_timer.stop()
            if hasattr(self, "_stats_timer"):
                self._stats_timer.stop()

            # 保存配置
            self.cfg.save()

            # 停止永久存储
            if hasattr(self, "persistent_storage"):
                self.persistent_storage.stop()

            logger.info("应用程序正常退出")
            event.accept()

        except Exception as e:
            logger.error(f"关闭应用程序时出错: {e}")
            event.accept()


async def main_async(app, window):
    """异步主函数"""
    await window.receiver.start()
    logger.info("应用程序启动完成")
    # 等待 Qt 退出信号
    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)
    await app_close_event.wait()
    await window.receiver.stop()


def main():
    """主入口函数"""
    try:
        # 启用OpenGL加速
        pg.setConfigOptions(
            useOpenGL=True,  # 启用OpenGL加速
            # enableExperimental=True,  # 启用实验性功能
            antialias=False,  # 关闭抗锯齿（性能提升明显）
            crashWarning=False,  # 关闭崩溃警告
        )

        try:
            winloop.install()  # 必须在任何 asyncio/qasync 调用之前
            logger.info("winloop 已启用")
        except Exception as e:
            logger.warning("winloop 不可用，回退到默认事件循环: %s", e)

        print(type(asyncio.get_event_loop()))
        # # 在Windows上设置事件循环策略
        # if sys.platform == "win32":
        #     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        #     # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # 创建Qt应用
        app = QtWidgets.QApplication(sys.argv)
        app.setApplicationName("UDP示波器")
        app.setApplicationVersion("1.0.0")

        # 加载配置
        cfg = ConfigManager()

        # 创建主窗口
        window = MainWindow(cfg)
        window.show()

        # 设置异步事件循环
        # 3. 让qasync基于当前事件循环（winloop）创建QEventLoop
        from qasync import QEventLoop

        event_loop = QEventLoop(app)
        asyncio.set_event_loop(event_loop)

        app_close_event = asyncio.Event()
        app.aboutToQuit.connect(app_close_event.set)

        print(type(asyncio.get_event_loop()))

        with event_loop:
            event_loop.run_until_complete(main_async(app, window))
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
