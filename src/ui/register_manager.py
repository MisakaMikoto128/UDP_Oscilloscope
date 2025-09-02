# -*- coding: utf-8 -*-
"""
寄存器管理界面模块
基于JSON配置文件自动生成寄存器管理界面
"""

import json
import logging
import struct
import socket
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QLineEdit,
    QGroupBox, QMessageBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QKeySequence

import qasync
from qasync import asyncSlot

logger = logging.getLogger(__name__)


@dataclass
class RegisterConfig:
    """寄存器配置数据类"""
    var_name: str
    alias: str
    permission: str  # "r", "rw", "w"
    address: int
    data_type: str
    range: List[float] = None  
    unit: str = ""
    confirm_dialog: bool = False
    step_size: float = 1.0
    scale_factor: int = 100000
    command_value: Optional[int] = None
    hotkey: Optional[str] = None
    qss_file_path: Optional[str] = None


class RegisterDataConverter:
    """寄存器数据转换器"""
    
    @staticmethod
    def raw_to_display(raw_value: int, config: RegisterConfig) -> str:
        """将原始寄存器值转换为显示值"""
        try:
            if config.data_type == "fixed_point":
                # 定点数转换
                float_val = (raw_value if raw_value < 2**31 else raw_value - 2**32) / config.scale_factor
                return f"{float_val:.5f}"
            elif config.data_type == "ipv4":
                # IPv4地址转换 - 按照下位机的字节序
                # 下位机使用: IPV4_TO_UINT32(ip1, ip2, ip3, ip4) = (ip1<<24)|(ip2<<16)|(ip3<<8)|ip4
                ip1 = (raw_value >> 24) & 0xFF
                ip2 = (raw_value >> 16) & 0xFF
                ip3 = (raw_value >> 8) & 0xFF
                ip4 = raw_value & 0xFF
                return f"{ip1}.{ip2}.{ip3}.{ip4}"
            elif config.data_type == "dual_uint16":
                # 双uint16转换
                high = (raw_value >> 16) & 0xFFFF
                low = raw_value & 0xFFFF
                return f"{high}:{low}"
            elif config.data_type in ["uint32_t", "int32_t", "uint16_t", "int16_t"]:
                # 整数类型
                if config.data_type.startswith("int") and raw_value >= 2**31:
                    # 有符号数处理
                    return str(raw_value - 2**32)
                return str(raw_value)
            else:
                return str(raw_value)
        except Exception as e:
            logger.error(f"数据转换错误: {e}")
            return str(raw_value)
    
    @staticmethod
    def display_to_raw(display_value: str, config: RegisterConfig) -> int:
        """将显示值转换为原始寄存器值"""
        try:
            if config.data_type == "fixed_point":
                # 定点数转换
                float_val = float(display_value)
                int_val = int(float_val * config.scale_factor)
                return int_val & 0xFFFFFFFF
            elif config.data_type == "ipv4":
                # IPv4地址转换 - 按照下位机的字节序
                # 下位机使用: IPV4_TO_UINT32(ip1, ip2, ip3, ip4) = (ip1<<24)|(ip2<<16)|(ip3<<8)|ip4
                parts = display_value.split('.')
                if len(parts) != 4:
                    raise ValueError("IPv4格式应为 xxx.xxx.xxx.xxx")
                ip1, ip2, ip3, ip4 = [int(part) for part in parts]
                if not all(0 <= ip <= 255 for ip in [ip1, ip2, ip3, ip4]):
                    raise ValueError("IPv4地址每段应在0-255范围内")
                return ((ip1 & 0xFF) << 24) | ((ip2 & 0xFF) << 16) | ((ip3 & 0xFF) << 8) | (ip4 & 0xFF)
            elif config.data_type == "dual_uint16":
                # 双uint16转换
                parts = display_value.split(':')
                if len(parts) != 2:
                    raise ValueError("格式应为 high:low")
                high = int(parts[0]) & 0xFFFF
                low = int(parts[1]) & 0xFFFF
                return (high << 16) | low
            elif config.data_type in ["uint32_t", "int32_t", "uint16_t", "int16_t"]:
                # 整数类型
                val = int(display_value)
                if config.data_type.startswith("int") and val < 0:
                    # 有符号数处理
                    return (val + 2**32) & 0xFFFFFFFF
                return val & 0xFFFFFFFF
            else:
                return int(display_value) & 0xFFFFFFFF
        except Exception as e:
            logger.error(f"数据转换错误: {e}")
            raise ValueError(f"无效的输入值: {display_value}")


class RegisterWidget(QWidget):
    """单个寄存器控件"""
    
    value_changed = pyqtSignal(int, int)  # address, new_raw_value
    command_triggered = pyqtSignal(int, int)  # address, command_value
    
    def __init__(self, config: RegisterConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_raw_value = 0
        self.converter = RegisterDataConverter()
        
        self._setup_ui()
        self._load_custom_style()
    
    def _setup_ui(self):
        """设置界面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # 寄存器名称标签
        name_label = QLabel(self.config.alias or self.config.var_name)
        name_label.setMinimumWidth(150)
        name_label.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(name_label)
        
        # 地址标签
        addr_label = QLabel(f"[{self.config.address}]")
        addr_label.setMinimumWidth(40)
        addr_label.setStyleSheet("color: #666; font-size: 8pt;")
        addr_label.setObjectName("addr_label")
        layout.addWidget(addr_label)
        
        # 当前值显示
        self.value_label = QLabel("--")
        self.value_label.setMinimumWidth(100)
        self.value_label.setStyleSheet("background: #f0f0f0; padding: 2px; border: 1px solid #ccc;")
        self.value_label.setObjectName("value_label")
        self.value_label.mousePressEvent = self._on_value_double_click
        layout.addWidget(self.value_label)

        # 单位标签
        if self.config.unit:
            unit_label = QLabel(self.config.unit)
            unit_label.setMinimumWidth(30)
            unit_label.setStyleSheet("color: #666;")
            unit_label.setObjectName("unit_label")
            layout.addWidget(unit_label)
        
        # 根据权限添加控件
        if self.config.permission == "rw":
            self._add_config_controls(layout)
        elif self.config.permission == "w":
            self._add_command_controls(layout)
        
        layout.addStretch()
    
    def _add_config_controls(self, layout):
        """添加配置寄存器控件"""
        # 输入框
        if self.config.data_type == "fixed_point":
            self.input_widget = QDoubleSpinBox()
            self.input_widget.setDecimals(5)
            self.input_widget.setRange(self.config.range[0], self.config.range[1])
            self.input_widget.setSingleStep(self.config.step_size)
            self.input_widget.setMinimumWidth(120)
        elif self.config.data_type == "ipv4":
            self.input_widget = QLineEdit()
            self.input_widget.setPlaceholderText("192.168.1.1")
            self.input_widget.setMinimumWidth(100)  # 减小IPv4输入框宽度
        elif self.config.data_type == "dual_uint16":
            self.input_widget = QLineEdit()
            self.input_widget.setPlaceholderText("high:low")
            self.input_widget.setMinimumWidth(100)
        else:
            self.input_widget = QSpinBox()
            self.input_widget.setRange(int(self.config.range[0]), int(self.config.range[1]))
            self.input_widget.setSingleStep(int(self.config.step_size))
            self.input_widget.setMinimumWidth(120)

        layout.addWidget(self.input_widget)

        # 设置按钮
        set_btn = QPushButton("设置")
        set_btn.setMinimumWidth(50)  # 确保按钮文字完全显示
        set_btn.setMaximumWidth(70)
        set_btn.clicked.connect(self._on_set_clicked)
        layout.addWidget(set_btn)
    
    def _add_command_controls(self, layout):
        """添加命令寄存器控件"""
        if self.config.command_value is not None:
            # 显示命令值（16进制）
            cmd_text = f"{self.config.alias or self.config.var_name}\n(0x{self.config.command_value:X})"
            cmd_btn = QPushButton(cmd_text)
            cmd_btn.setMaximumWidth(200)
            cmd_btn.clicked.connect(self._on_command_clicked)

            # 设置快捷键
            if self.config.hotkey:
                cmd_btn.setShortcut(QKeySequence(self.config.hotkey))
                cmd_btn.setToolTip(f"快捷键: {self.config.hotkey}\n命令值: 0x{self.config.command_value:X}")
            else:
                cmd_btn.setToolTip(f"命令值: 0x{self.config.command_value:X}")

            layout.addWidget(cmd_btn)
    
    def _load_custom_style(self):
        """加载自定义样式"""
        if self.config.qss_file_path:
            try:
                qss_path = Path(self.config.qss_file_path)
                if qss_path.exists():
                    with open(qss_path, 'r', encoding='utf-8') as f:
                        self.setStyleSheet(f.read())
            except Exception as e:
                logger.warning(f"加载样式文件失败: {e}")
    
    def _on_value_double_click(self, event):
        """双击当前值同步到输入框"""
        if self.config.permission == "rw" and hasattr(self, 'input_widget'):
            try:
                display_value = self.value_label.text()
                if display_value != "--":
                    if isinstance(self.input_widget, (QSpinBox, QDoubleSpinBox)):
                        self.input_widget.setValue(float(display_value))
                    else:
                        self.input_widget.setText(display_value)
            except Exception as e:
                logger.error(f"同步值到输入框失败: {e}")
    
    def _on_set_clicked(self):
        """设置按钮点击"""
        try:
            # 获取输入值
            if isinstance(self.input_widget, (QSpinBox, QDoubleSpinBox)):
                display_value = str(self.input_widget.value())
            else:
                display_value = self.input_widget.text().strip()
            
            if not display_value:
                QMessageBox.warning(self, "警告", "请输入有效值")
                return
            
            # 转换为原始值
            new_raw_value = self.converter.display_to_raw(display_value, self.config)
            
            # 二次确认
            if self.config.confirm_dialog:
                old_display = self.value_label.text()
                msg = f"将寄存器[{self.config.alias or self.config.var_name}]从[{old_display}]设置为[{display_value}]？"
                reply = QMessageBox.question(self, "确认设置", msg, 
                                           QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
            
            # 发射信号
            self.value_changed.emit(self.config.address, new_raw_value)
            
        except ValueError as e:
            QMessageBox.warning(self, "输入错误", str(e))
        except Exception as e:
            logger.error(f"设置寄存器失败: {e}")
            QMessageBox.critical(self, "错误", f"设置失败: {e}")
    
    def _on_command_clicked(self):
        """命令按钮点击"""
        try:
            # 二次确认
            if self.config.confirm_dialog:
                msg = f"确认发送命令[{self.config.alias or self.config.var_name}]？"
                reply = QMessageBox.question(self, "确认命令", msg,
                                           QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
            
            # 发射命令信号
            self.command_triggered.emit(self.config.address, self.config.command_value)
            
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            QMessageBox.critical(self, "错误", f"命令发送失败: {e}")
    
    def update_value(self, raw_value: int):
        """更新显示值"""
        self.current_raw_value = raw_value
        display_value = self.converter.raw_to_display(raw_value, self.config)
        self.value_label.setText(display_value)


class RegisterManagerWidget(QWidget):
    """寄存器管理主界面"""

    register_set_requested = pyqtSignal(int, list)  # address, data_list
    command_requested = pyqtSignal(int, int)  # address, command_value

    def __init__(self, config_file_path: str, parent=None):
        super().__init__(parent)
        self.config_file_path = config_file_path
        self.register_widgets: Dict[int, RegisterWidget] = {}
        self.register_configs: Dict[int, RegisterConfig] = {}

        # 状态指示器
        self.online_status = False

        # 消息提示定时器
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self._clear_message)

        self._load_config()
        self._setup_ui()
        self._connect_signals()

    def _load_config(self):
        """加载JSON配置文件"""
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 加载配置寄存器
            for reg_data in config_data.get('registers', []):
                config = RegisterConfig(**reg_data)
                self.register_configs[config.address] = config

            # 加载状态寄存器
            for reg_data in config_data.get('status_registers', []):
                config = RegisterConfig(**reg_data)
                self.register_configs[config.address] = config

            # 加载命令寄存器 - 支持相同地址的多个命令
            self.command_configs = []  # 单独存储命令配置
            for cmd_data in config_data.get('commands', []):
                config = RegisterConfig(**cmd_data)
                self.command_configs.append(config)
                # 不再使用地址作为key，避免覆盖

            logger.info(f"成功加载 {len(self.register_configs)} 个寄存器配置和 {len(self.command_configs)} 个命令配置")

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            QMessageBox.critical(self, "配置错误", f"无法加载配置文件: {e}")

    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)

        # 状态栏
        self._setup_status_bar(layout)

        # 主内容区域 - 三列并排布局
        main_content = QHBoxLayout()
        layout.addLayout(main_content)

        # 配置寄存器列
        self._setup_config_registers_column(main_content)

        # 状态寄存器列
        self._setup_status_registers_column(main_content)

        # 命令寄存器列
        self._setup_command_registers_column(main_content)

        # 消息显示区域
        self.message_label = QLabel()
        self.message_label.setStyleSheet("""
            QLabel {
                background: #e8f5e8;
                border: 1px solid #4caf50;
                border-radius: 4px;
                padding: 8px;
                color: #2e7d32;
            }
        """)
        self.message_label.setObjectName("message_label")
        self.message_label.hide()
        layout.addWidget(self.message_label)

    def _setup_status_bar(self, layout):
        """设置状态栏"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.StyledPanel)
        status_frame.setFixedHeight(50)  # 固定高度，确保显示完整
        status_frame.setObjectName("status_frame")

        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 5, 10, 5)  # 增加边距

        # 标题
        title_label = QLabel("寄存器管理界面")
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title_label.setStyleSheet("color: #333; padding: 5px;")
        status_layout.addWidget(title_label)

        status_layout.addStretch()

        # 在线状态指示器
        self.status_indicator = QLabel("离线")
        self.status_indicator.setFixedSize(80, 30)  # 固定大小确保显示完整
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self._update_status_indicator()
        status_layout.addWidget(self.status_indicator)

        # 刷新按钮
        refresh_btn = QPushButton("刷新配置")
        refresh_btn.setFixedSize(150, 30)  # 固定大小确保显示完整
        refresh_btn.clicked.connect(self._reload_config)
        status_layout.addWidget(refresh_btn)

        layout.addWidget(status_frame)

    def _setup_config_registers_column(self, main_layout):
        """设置配置寄存器列"""
        # 配置寄存器滚动区域
        config_scroll = QScrollArea()
        config_scroll.setWidgetResizable(True)
        config_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        config_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        config_scroll.setMinimumWidth(350)

        config_content = QWidget()
        config_layout = QVBoxLayout(config_content)

        # 配置寄存器组
        config_group = QGroupBox("配置寄存器 (可读写)")
        config_group_layout = QVBoxLayout(config_group)
        # 设置组框内边距，避免贴边
        config_group_layout.setContentsMargins(10, 20, 10, 10)

        config_registers = [config for config in self.register_configs.values()
                          if config.permission == "rw"]
        config_registers.sort(key=lambda x: x.address)

        for config in config_registers:
            widget = RegisterWidget(config)
            self.register_widgets[config.address] = widget
            config_group_layout.addWidget(widget)

        config_layout.addWidget(config_group)
        config_layout.addStretch()

        config_scroll.setWidget(config_content)
        main_layout.addWidget(config_scroll)

    def _setup_status_registers_column(self, main_layout):
        """设置状态寄存器列"""
        # 状态寄存器滚动区域
        status_scroll = QScrollArea()
        status_scroll.setWidgetResizable(True)
        status_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        status_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        status_scroll.setMinimumWidth(300)

        status_content = QWidget()
        status_layout = QVBoxLayout(status_content)

        # 状态寄存器组
        status_group = QGroupBox("状态寄存器 (只读)")
        status_group_layout = QVBoxLayout(status_group)
        # 设置组框内边距，避免贴边
        status_group_layout.setContentsMargins(10, 20, 10, 10)

        status_registers = [config for config in self.register_configs.values()
                          if config.permission == "r"]
        status_registers.sort(key=lambda x: x.address)

        for config in status_registers:
            widget = RegisterWidget(config)
            self.register_widgets[config.address] = widget
            status_group_layout.addWidget(widget)

        status_layout.addWidget(status_group)
        status_layout.addStretch()

        status_scroll.setWidget(status_content)
        main_layout.addWidget(status_scroll)

    def _setup_command_registers_column(self, main_layout):
        """设置命令寄存器列"""
        # 命令寄存器滚动区域
        command_scroll = QScrollArea()
        command_scroll.setWidgetResizable(True)
        command_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        command_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        command_scroll.setMinimumWidth(250)

        command_content = QWidget()
        command_layout = QVBoxLayout(command_content)

        # 命令寄存器组
        command_group = QGroupBox("命令寄存器 (只写)")
        command_group_layout = QVBoxLayout(command_group)
        # 设置组框内边距，避免贴边
        command_group_layout.setContentsMargins(10, 20, 10, 10)

        # 使用单独的命令配置列表，支持相同地址的多个命令
        if hasattr(self, 'command_configs'):
            command_configs = sorted(self.command_configs, key=lambda x: (x.address, x.var_name))

            for i, config in enumerate(command_configs):
                widget = RegisterWidget(config)
                # 使用唯一标识符而不是地址作为key
                unique_key = f"cmd_{config.address}_{i}"
                self.register_widgets[unique_key] = widget
                command_group_layout.addWidget(widget)

        command_layout.addWidget(command_group)
        command_layout.addStretch()

        command_scroll.setWidget(command_content)
        main_layout.addWidget(command_scroll)

    def _connect_signals(self):
        """连接信号"""
        for widget in self.register_widgets.values():
            widget.value_changed.connect(self._on_register_set_requested)
            widget.command_triggered.connect(self._on_command_requested)

    def _update_status_indicator(self):
        """更新状态指示器"""
        if self.online_status:
            self.status_indicator.setText("在线")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    background: #4caf50;
                    color: white;
                    border: 2px solid #388e3c;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
        else:
            self.status_indicator.setText("离线")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    background: #f44336;
                    color: white;
                    border: 2px solid #d32f2f;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)

    def _reload_config(self):
        """重新加载配置"""
        try:
            # 清除现有配置
            old_register_configs = self.register_configs.copy()
            old_register_widgets = self.register_widgets.copy()
            old_command_configs = getattr(self, 'command_configs', []).copy()

            self.register_configs.clear()
            self.register_widgets.clear()
            if hasattr(self, 'command_configs'):
                self.command_configs.clear()

            # 重新加载配置
            self._load_config()

            # 重新创建界面 - 更安全的方式
            self._recreate_interface()

            self._show_message("配置重新加载成功", "success")

        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            # 恢复旧配置
            self.register_configs = old_register_configs
            self.register_widgets = old_register_widgets
            if hasattr(self, 'command_configs'):
                self.command_configs = old_command_configs
            QMessageBox.critical(self, "错误", f"重新加载配置失败: {e}")

    def _recreate_interface(self):
        """重新创建界面"""
        try:
            # 找到主内容布局
            main_layout = self.layout()
            if not main_layout:
                return

            # 找到并清除主内容区域（跳过状态栏和消息标签）
            items_to_remove = []
            for i in range(main_layout.count()):
                item = main_layout.itemAt(i)
                if item and item.layout() and isinstance(item.layout(), QHBoxLayout):
                    # 这是主内容的三列布局
                    items_to_remove.append(i)

            # 从后往前删除，避免索引变化
            for i in reversed(items_to_remove):
                item = main_layout.takeAt(i)
                if item and item.layout():
                    self._clear_layout(item.layout())

            # 重新创建主内容区域
            main_content = QHBoxLayout()

            # 重新创建三列
            self._setup_config_registers_column(main_content)
            self._setup_status_registers_column(main_content)
            self._setup_command_registers_column(main_content)

            # 插入到正确位置（状态栏之后，消息标签之前）
            main_layout.insertLayout(1, main_content)

            # 重新连接信号
            self._connect_signals()

        except Exception as e:
            logger.error(f"重新创建界面失败: {e}")
            raise

    def _clear_layout(self, layout):
        """递归清除布局"""
        if layout is None:
            return

        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout(child.layout())

    def _on_register_set_requested(self, address: int, raw_value: int):
        """寄存器设置请求"""
        self.register_set_requested.emit(address, [raw_value])

    def _on_command_requested(self, address: int, command_value: int):
        """命令请求"""
        self.command_requested.emit(address, command_value)

    def _show_message(self, message: str, msg_type: str = "info"):
        """显示消息"""
        self.message_label.setText(message)

        if msg_type == "success":
            self.message_label.setStyleSheet("""
                QLabel {
                    background: #e8f5e8;
                    border: 1px solid #4caf50;
                    border-radius: 4px;
                    padding: 8px;
                    color: #2e7d32;
                }
            """)
        elif msg_type == "error":
            self.message_label.setStyleSheet("""
                QLabel {
                    background: #ffebee;
                    border: 1px solid #f44336;
                    border-radius: 4px;
                    padding: 8px;
                    color: #c62828;
                }
            """)
        else:
            self.message_label.setStyleSheet("""
                QLabel {
                    background: #e3f2fd;
                    border: 1px solid #2196f3;
                    border-radius: 4px;
                    padding: 8px;
                    color: #1565c0;
                }
            """)

        self.message_label.show()
        self.message_timer.start(3000)  # 3秒后自动隐藏

    def _clear_message(self):
        """清除消息"""
        self.message_label.hide()
        self.message_timer.stop()

    def set_online_status(self, online: bool):
        """设置在线状态"""
        self.online_status = online
        self._update_status_indicator()

    def update_registers_data(self, registers_data: List[int]):
        """更新寄存器数据"""
        try:
            for address, raw_value in enumerate(registers_data):
                if address in self.register_widgets:
                    self.register_widgets[address].update_value(raw_value)
        except Exception as e:
            logger.error(f"更新寄存器数据失败: {e}")

    def show_register_set_result(self, address: int, success: bool, old_value: str = "", new_value: str = ""):
        """显示寄存器设置结果"""
        if address in self.register_configs:
            config = self.register_configs[address]
            name = config.alias or config.var_name

            if success:
                if old_value and new_value:
                    message = f"寄存器[{name}]从[{old_value}]设置为[{new_value}]成功"
                else:
                    message = f"寄存器[{name}]设置成功"
                self._show_message(message, "success")
            else:
                message = f"寄存器[{name}]设置失败"
                self._show_message(message, "error")
