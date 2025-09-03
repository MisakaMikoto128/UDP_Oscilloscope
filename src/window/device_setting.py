# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui
from qasync import asyncClose,asyncSlot
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from qfluentwidgets import InfoLevel

from src.communication.protocol import (
    SysREGsUpData,
)
from src.communication.udp_master import UDPMaster
from src.config.config_manager import ConfigManager
from src.ui import Device_Setting_From


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ctrl_panel_frame.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)
def uint32_to_int32(value: int) -> int:
    """将无符号32位整数转换为有符号32位整数"""
    if value >= 0x80000000:  # 2^31
        return value - 0x100000000  # 2^32
    return value

class DeviceSettingFrom(QtWidgets.QFrame, Device_Setting_From):
    """主窗口类"""

    def __init__(self, cfg: ConfigManager,
                 config_file_path: str,
                 device_reg_set_func: Callable[[int, List[int]], Awaitable[bool]],
                 parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)
        # 配置管理器
        self.cfg = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        self.setObjectName('DeviceSettingFrom')
        self.list_pid_param.setSelectRightClickedRow(True)


    @asyncSlot(SysREGsUpData)
    async def on_on_sys_regs_uploaded(self, sys_regs_up_data: SysREGsUpData):
        try:
            fixed_point_scale = 100000

            # 速度环（Speed Loop）PID参数
            PID_Speed_Kp = uint32_to_int32(sys_regs_up_data.reg[15]) / fixed_point_scale
            PID_Speed_Ki = uint32_to_int32(sys_regs_up_data.reg[16]) / fixed_point_scale
            PID_Speed_Kd = uint32_to_int32(sys_regs_up_data.reg[17]) / fixed_point_scale
            PID_Speed_Kd_Filter = uint32_to_int32(sys_regs_up_data.reg[18]) / fixed_point_scale

            # Id环（Id Loop）PID参数
            PID_Id_Kp = uint32_to_int32(sys_regs_up_data.reg[19]) / fixed_point_scale
            PID_Id_Ki = uint32_to_int32(sys_regs_up_data.reg[20]) / fixed_point_scale
            PID_Id_Kd = uint32_to_int32(sys_regs_up_data.reg[21]) / fixed_point_scale
            PID_Id_Kd_Filter = uint32_to_int32(sys_regs_up_data.reg[22]) / fixed_point_scale

            # Iq环（Iq Loop）PID参数
            PID_Iq_Kp = uint32_to_int32(sys_regs_up_data.reg[23]) / fixed_point_scale
            PID_Iq_Ki = uint32_to_int32(sys_regs_up_data.reg[24]) / fixed_point_scale
            PID_Iq_Kd = uint32_to_int32(sys_regs_up_data.reg[25]) / fixed_point_scale
            PID_Iq_Kd_Filter = uint32_to_int32(sys_regs_up_data.reg[26]) / fixed_point_scale
        
            
        
        except Exception as e:
            logger.info(f"解析数据错误{e}")
