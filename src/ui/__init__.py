# -*- coding: utf-8 -*-
"""
UI组件模块
"""

from .scope_view import ScopeWidget
from .channel_config_widget import ChannelConfigWidget, CursorControlWidget, ColorButton
from .register_integration import RegisterTabWidget
from .main_window_ui import Ui_MainWindow
__all__ = [
    'ScopeWidget',
    'ChannelConfigWidget', 
    'CursorControlWidget',
    'ColorButton',
    'RegisterTabWidget',
    'Ui_MainWindow'
]
