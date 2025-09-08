# -*- coding: utf-8 -*-
"""
UI组件模块
"""

from .scope_view import ScopeWidget
from .channel_config_widget import ChannelConfigWidget, CursorControlWidget, ColorButton
from .main_window_ui import Ui_Form
from .ctrl_panel_ui import Ui_Form as Ctrl_Panel_Form
from .device_setting_ui import Ui_Form as Device_Setting_From
from .network_setting_ui import Ui_Form as Network_Setting_From
from .setting_ui import Ui_Form as Setting_Form

__all__ = [
    'ScopeWidget',
    'ChannelConfigWidget', 
    'CursorControlWidget',
    'ColorButton',
    'Ui_Form',
    'Ctrl_Panel_Form',
    'Device_Setting_From',
    'Network_Setting_From',
    'Setting_From',
]
