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


    @asyncSlot(SysREGsUpData)
    async def on_on_sys_regs_uploaded(self,sys_regs_up_data: SysREGsUpData):
        pass
