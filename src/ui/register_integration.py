# -*- coding: utf-8 -*-
"""
寄存器管理界面集成模块
将寄存器管理界面集成到主程序中
"""

import logging
from pathlib import Path
from typing import Optional, Callable, List

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal

import qasync
from qasync import asyncSlot

from .register_manager import RegisterManagerWidget
from communication.protocol import SysREGsUpData

logger = logging.getLogger(__name__)


class RegisterIntegration(QObject):
    """寄存器管理集成器"""
    
    # 信号定义
    register_set_success = pyqtSignal(int, str, str)  # address, old_value, new_value
    register_set_failed = pyqtSignal(int)  # address
    
    def __init__(self, 
                 config_file_path: str,
                 device_reg_set_func: Callable[[int, List[int]], bool],
                 parent: Optional[QObject] = None):
        """
        初始化寄存器集成器
        
        Args:
            config_file_path: JSON配置文件路径
            device_reg_set_func: 设备寄存器设置函数
            parent: 父对象
        """
        super().__init__(parent)
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        
        # 创建寄存器管理界面
        self.register_widget = None
        self._create_register_widget()
        
        # 连接信号
        self._connect_signals()
    
    def _create_register_widget(self):
        """创建寄存器管理界面"""
        try:
            self.register_widget = RegisterManagerWidget(self.config_file_path)
            
            # 加载样式
            self._load_styles()
            
            logger.info("寄存器管理界面创建成功")
            
        except Exception as e:
            logger.error(f"创建寄存器管理界面失败: {e}")
            raise
    
    def _load_styles(self):
        """加载样式文件"""
        try:
            style_path = Path(__file__).parent / "styles" / "register_manager.qss"
            if style_path.exists():
                with open(style_path, 'r', encoding='utf-8') as f:
                    self.register_widget.setStyleSheet(f.read())
                logger.info("样式文件加载成功")
            else:
                logger.warning(f"样式文件不存在: {style_path}")
        except Exception as e:
            logger.warning(f"加载样式文件失败: {e}")
    
    def _connect_signals(self):
        """连接信号"""
        if self.register_widget:
            # 连接寄存器设置请求信号
            self.register_widget.register_set_requested.connect(
                self._on_register_set_requested
            )
            
            # 连接命令请求信号
            self.register_widget.command_requested.connect(
                self._on_command_requested
            )
            
            # 连接内部信号
            self.register_set_success.connect(
                self._on_register_set_success
            )
            self.register_set_failed.connect(
                self._on_register_set_failed
            )
    
    @asyncSlot(int, list)
    async def _on_register_set_requested(self, address: int, data_list: List[int]):
        """处理寄存器设置请求"""
        try:
            # 获取旧值用于显示
            old_value = ""
            if address in self.register_widget.register_widgets:
                widget = self.register_widget.register_widgets[address]
                old_value = widget.value_label.text()
            
            # 调用设备寄存器设置函数
            success = await self.device_reg_set_func(address, data_list)
            
            if success:
                # 计算新值用于显示
                new_value = ""
                if address in self.register_widget.register_widgets:
                    widget = self.register_widget.register_widgets[address]
                    config = widget.config
                    converter = widget.converter
                    new_value = converter.raw_to_display(data_list[0], config)
                
                self.register_set_success.emit(address, old_value, new_value)
            else:
                self.register_set_failed.emit(address)
                
        except Exception as e:
            logger.error(f"处理寄存器设置请求失败: {e}")
            self.register_set_failed.emit(address)
    
    @asyncSlot(int, int)
    async def _on_command_requested(self, address: int, command_value: int):
        """处理命令请求"""
        try:
            # 发送命令
            success = await self.device_reg_set_func(address, [command_value])
            
            if success:
                # 显示命令发送成功消息
                if address in self.register_widget.register_configs:
                    config = self.register_widget.register_configs[address]
                    name = config.alias or config.var_name
                    message = f"命令[{name}]发送成功"
                    self.register_widget._show_message(message, "success")
                else:
                    self.register_widget._show_message("命令发送成功", "success")
            else:
                # 显示命令发送失败消息
                if address in self.register_widget.register_configs:
                    config = self.register_widget.register_configs[address]
                    name = config.alias or config.var_name
                    message = f"命令[{name}]发送失败"
                    self.register_widget._show_message(message, "error")
                else:
                    self.register_widget._show_message("命令发送失败", "error")
                    
        except Exception as e:
            logger.error(f"处理命令请求失败: {e}")
            if address in self.register_widget.register_configs:
                config = self.register_widget.register_configs[address]
                name = config.alias or config.var_name
                message = f"命令[{name}]发送失败: {e}"
                self.register_widget._show_message(message, "error")
    
    def _on_register_set_success(self, address: int, old_value: str, new_value: str):
        """处理寄存器设置成功"""
        if self.register_widget:
            self.register_widget.show_register_set_result(
                address, True, old_value, new_value
            )
    
    def _on_register_set_failed(self, address: int):
        """处理寄存器设置失败"""
        if self.register_widget:
            self.register_widget.show_register_set_result(address, False)
    
    def get_widget(self) -> QWidget:
        """获取寄存器管理界面控件"""
        return self.register_widget
    
    def on_sys_regs_upload(self, sys_reg_upload: SysREGsUpData):
        """处理系统寄存器上传数据"""
        try:
            if self.register_widget and sys_reg_upload.reg:
                # 更新寄存器数据
                self.register_widget.update_registers_data(sys_reg_upload.reg)
                
                # 更新在线状态
                self.register_widget.set_online_status(True)
                
                logger.debug(f"更新了 {len(sys_reg_upload.reg)} 个寄存器数据")
                
        except Exception as e:
            logger.error(f"处理系统寄存器上传数据失败: {e}")
    
    def set_online_status(self, online: bool):
        """设置在线状态"""
        if self.register_widget:
            self.register_widget.set_online_status(online)
    
    def reload_config(self):
        """重新加载配置"""
        if self.register_widget:
            self.register_widget._reload_config()


class RegisterTabWidget(QWidget):
    """寄存器标签页控件"""
    
    def __init__(self, 
                 config_file_path: str,
                 device_reg_set_func: Callable[[int, List[int]], bool],
                 parent=None):
        """
        初始化寄存器标签页控件
        
        Args:
            config_file_path: JSON配置文件路径
            device_reg_set_func: 设备寄存器设置函数
            parent: 父控件
        """
        super().__init__(parent)
        
        # 创建集成器
        self.integration = RegisterIntegration(
            config_file_path, 
            device_reg_set_func,
            self
        )
        
        # 设置布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.integration.get_widget())
    
    def on_sys_regs_upload(self, sys_reg_upload: SysREGsUpData):
        """处理系统寄存器上传数据"""
        self.integration.on_sys_regs_upload(sys_reg_upload)
    
    def set_online_status(self, online: bool):
        """设置在线状态"""
        self.integration.set_online_status(online)
    
    def reload_config(self):
        """重新加载配置"""
        self.integration.reload_config()
