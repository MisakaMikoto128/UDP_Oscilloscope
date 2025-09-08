# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable

from PyQt5 import QtWidgets
from qfluentwidgets import Theme, setTheme
from src.config.config_manager import ConfigManager
from src.ui import Setting_Form

logger = logging.getLogger(__name__)


class SettingForm(QtWidgets.QFrame, Setting_Form):
    """设置窗口类"""

    def __init__(
        self,
        cfg: ConfigManager,
        config_file_path: str,
        device_reg_set_func: Callable[[int, List[int]], Awaitable[bool]],
        parent=None,
    ):
        super().__init__(parent=parent)
        self.setupUi(self)

        # 配置管理器
        self.cfg = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        self.setObjectName("Setting_Form")

        # 连接按钮信号
        self._connect_network_buttons()

    def _connect_network_buttons(self):
        self.sw_theme.checkedChanged.connect(
            lambda checked: self._switch_theme(checked)
        )

    def _switch_theme(self, is_dark: bool):
        setTheme(Theme.DARK if is_dark else Theme.LIGHT)