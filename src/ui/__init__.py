# -*- coding: utf-8 -*-
"""
UI组件模块
"""

from .scope_view import ScopeWidget
from .channel_config_widget import ChannelConfigWidget, CursorControlWidget, ColorButton
from .main_window_ui import Ui_Form
from .ctrl_panel_ui import Ui_Form as Ctrl_Panel_Form
__all__ = [
    'ScopeWidget',
    'ChannelConfigWidget', 
    'CursorControlWidget',
    'ColorButton',
    'Ui_Form',
    'Ctrl_Panel_Form'
]
