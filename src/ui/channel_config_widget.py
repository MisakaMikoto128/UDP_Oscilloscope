# -*- coding: utf-8 -*-
"""
通道配置组件
实现通道参数配置、颜色选择、光标控制等功能
"""

from PyQt5 import QtWidgets, QtCore, QtGui
from typing import Dict, Any, Callable, Optional
from src.ui.scope_view import ScopeWidget
import logging

logger = logging.getLogger(__name__)


class ColorButton(QtWidgets.QPushButton):
    """颜色选择按钮"""

    colorChanged = QtCore.pyqtSignal(str)  # 颜色改变信号

    def __init__(self, color: str = "#FFFFFF", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(40, 25)
        self.clicked.connect(self._choose_color)
        self._update_style()

    def _update_style(self):
        """更新按钮样式"""
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color};
                border: 2px solid #666666;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #AAAAAA;
            }}
        """)

    def _choose_color(self):
        """打开颜色选择对话框"""
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._color), self, "选择通道颜色"
        )

        if color.isValid():
            self.set_color(color.name())

    def set_color(self, color: str):
        """设置颜色"""
        self._color = color
        self._update_style()
        self.colorChanged.emit(color)

    def get_color(self) -> str:
        """获取颜色"""
        return self._color


class ChannelConfigWidget(QtWidgets.QWidget):
    """
    通道配置组件
    包含垂直挡位、偏移、单位、颜色等配置
    """

    # 配置改变信号
    configChanged = QtCore.pyqtSignal(int, dict)  # (channel_index, config)

    def __init__(self, channel_index: int, config: Dict[str, Any], parent=None):
        super().__init__(parent)

        self.channel_index = channel_index
        self.config = config.copy()

        self._setup_ui()
        self._load_config()
        self._connect_signals()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(8)

        # 通道启用复选框
        self.enabled_checkbox = QtWidgets.QCheckBox("启用通道")
        layout.addRow(self.enabled_checkbox)

        unit = self.config.get("unit", "V")
        # 垂直挡位
        self.vertical_div_spinbox = QtWidgets.QDoubleSpinBox()
        self.vertical_div_spinbox.setRange(0.001, 1000.0)
        self.vertical_div_spinbox.setDecimals(3)
        self.vertical_div_spinbox.setSingleStep(0.1)
        self.vertical_div_spinbox.setSuffix(f" {unit}/div")
        layout.addRow("垂直挡位:", self.vertical_div_spinbox)

        # 垂直偏移
        self.vertical_offset_spinbox = QtWidgets.QDoubleSpinBox()
        self.vertical_offset_spinbox.setRange(-1000.0, 1000.0)
        self.vertical_offset_spinbox.setDecimals(3)
        self.vertical_offset_spinbox.setSingleStep(0.1)
        self.vertical_offset_spinbox.setSuffix(f" {unit}")
        layout.addRow("垂直偏移:", self.vertical_offset_spinbox)

        # 单位选择
        self.unit_combobox = QtWidgets.QComboBox()
        self.unit_combobox.addItems(["V", "A", "W", "Hz", "rpm", "°C", "%", "bar"])
        self.unit_combobox.setEditable(True)
        layout.addRow("单位:", self.unit_combobox)

        # 缩放比例
        self.scale_factor_spinbox = QtWidgets.QDoubleSpinBox()
        self.scale_factor_spinbox.setRange(0.001, 1000.0)
        self.scale_factor_spinbox.setDecimals(6)
        self.scale_factor_spinbox.setSingleStep(0.1)
        self.scale_factor_spinbox.setValue(1.0)
        layout.addRow("缩放比例:", self.scale_factor_spinbox)

        # 通道颜色
        color_layout = QtWidgets.QHBoxLayout()
        self.color_button = ColorButton()
        self.color_label = QtWidgets.QLabel("通道颜色")
        color_layout.addWidget(self.color_button)
        color_layout.addWidget(self.color_label)
        color_layout.addStretch()
        layout.addRow(color_layout)

        # 可见性
        self.visible_checkbox = QtWidgets.QCheckBox("显示波形")
        layout.addRow(self.visible_checkbox)

        # 分隔线
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addRow(line)

        # 统计信息（只读）
        self.stats_group = QtWidgets.QGroupBox("统计信息")
        stats_layout = QtWidgets.QFormLayout(self.stats_group)

        self.min_label = QtWidgets.QLabel("--")
        self.max_label = QtWidgets.QLabel("--")
        self.mean_label = QtWidgets.QLabel("--")
        self.rms_label = QtWidgets.QLabel("--")

        stats_layout.addRow("最小值:", self.min_label)
        stats_layout.addRow("最大值:", self.max_label)
        stats_layout.addRow("平均值:", self.mean_label)
        stats_layout.addRow("有效值:", self.rms_label)

        layout.addRow(self.stats_group)

    def _load_config(self):
        """加载配置到UI"""
        self.enabled_checkbox.setChecked(self.config.get("enabled", True))
        self.vertical_div_spinbox.setValue(self.config.get("vertical_div", 1.0))
        self.vertical_offset_spinbox.setValue(self.config.get("vertical_offset", 0.0))

        unit = self.config.get("unit", "V")
        index = self.unit_combobox.findText(unit)
        if index >= 0:
            self.unit_combobox.setCurrentIndex(index)
        else:
            self.unit_combobox.setCurrentText(unit)

        self.scale_factor_spinbox.setValue(self.config.get("scale_factor", 1.0))
        self.color_button.set_color(self.config.get("color", "#FFFFFF"))
        self.visible_checkbox.setChecked(self.config.get("visible", True))

    def _connect_signals(self):
        """连接信号"""
        self.enabled_checkbox.toggled.connect(self._on_config_changed)
        self.vertical_div_spinbox.valueChanged.connect(self._on_config_changed)
        self.vertical_offset_spinbox.valueChanged.connect(self._on_config_changed)
        self.unit_combobox.currentTextChanged.connect(self._on_config_changed)
        self.scale_factor_spinbox.valueChanged.connect(self._on_config_changed)
        self.color_button.colorChanged.connect(self._on_config_changed)
        self.visible_checkbox.toggled.connect(self._on_config_changed)

    def _on_config_changed(self):
        """配置改变处理"""
        self.config.update(
            {
                "enabled": self.enabled_checkbox.isChecked(),
                "vertical_div": self.vertical_div_spinbox.value(),
                "vertical_offset": self.vertical_offset_spinbox.value(),
                "unit": self.unit_combobox.currentText(),
                "scale_factor": self.scale_factor_spinbox.value(),
                "color": self.color_button.get_color(),
                "visible": self.visible_checkbox.isChecked(),
            }
        )
        unit = self.unit_combobox.currentText()
        self.vertical_div_spinbox.setSuffix(f" {unit}/div")
        self.vertical_offset_spinbox.setSuffix(f" {unit}")
        self.configChanged.emit(self.channel_index, self.config.copy())

    def update_statistics(self, stats: Dict[str, float]):
        """
        更新统计信息显示

        Args:
            stats: 统计信息字典
        """
        unit = self.config.get("unit", "V")

        if stats.get("count", 0) > 0:
            self.min_label.setText(f"{stats['min']:.3f} {unit}")
            self.max_label.setText(f"{stats['max']:.3f} {unit}")
            self.mean_label.setText(f"{stats['mean']:.3f} {unit}")

            # 计算RMS值
            rms = (stats["mean"] ** 2 + stats["std"] ** 2) ** 0.5
            self.rms_label.setText(f"{rms:.3f} {unit}")
        else:
            self.min_label.setText("--")
            self.max_label.setText("--")
            self.mean_label.setText("--")
            self.rms_label.setText("--")

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self.config.copy()

    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        self.config.update(config)
        self._load_config()


class CursorControlWidget(QtWidgets.QWidget):
    """
    光标控制组件（带滚动区域）
    """

    # 光标改变信号
    cursorChanged = QtCore.pyqtSignal(str, float)  # (cursor_name, position)
    cursorEnabledChanged = QtCore.pyqtSignal(bool)  # enabled

    def __init__(self, ch_defs: Dict[str, Any], scope_widget: ScopeWidget, parent=None):
        super().__init__(parent)

        self.ch_defs = ch_defs
        self.scope_widget = scope_widget
        self.cursor_values = {"x1": 0.0, "x2": 1.0, "y1": 0.0, "y2": 1.0}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置UI布局"""
        # 主布局 - 只包含滚动区域
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距

        # 创建内容widget
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)

        # 设置内容widget的尺寸策略，确保宽度不会被压缩
        content_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        # 光标启用
        self.enable_checkbox = QtWidgets.QCheckBox("启用光标")
        content_layout.addWidget(self.enable_checkbox)

        # 光标控制组
        self.cursor_group = QtWidgets.QGroupBox("光标位置")
        cursor_layout = QtWidgets.QFormLayout(self.cursor_group)

        # X轴光标
        self.x1_spinbox = QtWidgets.QDoubleSpinBox()
        self.x1_spinbox.setRange(-1e6, 1e6)
        self.x1_spinbox.setDecimals(6)
        self.x1_spinbox.setSuffix(" s")
        self.x1_spinbox.setMinimumWidth(220)
        self.x1_spinbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        cursor_layout.addRow("X1:", self.x1_spinbox)

        self.x2_spinbox = QtWidgets.QDoubleSpinBox()
        self.x2_spinbox.setRange(-1e6, 1e6)
        self.x2_spinbox.setDecimals(6)
        self.x2_spinbox.setSuffix(" s")
        self.x2_spinbox.setMinimumWidth(220)
        self.x2_spinbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        cursor_layout.addRow("X2:", self.x2_spinbox)

        # Y轴光标
        self.y1_spinbox = QtWidgets.QDoubleSpinBox()
        self.y1_spinbox.setRange(-1e6, 1e6)
        self.y1_spinbox.setDecimals(3)
        self.y1_spinbox.setMinimumWidth(220)
        cursor_layout.addRow("Y1:", self.y1_spinbox)

        self.y2_spinbox = QtWidgets.QDoubleSpinBox()
        self.y2_spinbox.setRange(-1e6, 1e6)
        self.y2_spinbox.setDecimals(3)
        self.y2_spinbox.setMinimumWidth(220)
        cursor_layout.addRow("Y2:", self.y2_spinbox)

        content_layout.addWidget(self.cursor_group)

        # 测量结果组
        self.measurement_group = QtWidgets.QGroupBox("测量结果")
        measurement_layout = QtWidgets.QGridLayout(self.measurement_group)

        self.dx_label = QtWidgets.QLabel("--")
        self.dy_label = QtWidgets.QLabel("--")
        self.freq_label = QtWidgets.QLabel("--")

        # 设置标签的最小宽度和对齐方式
        for label in [self.dx_label, self.dy_label, self.freq_label]:
            label.setMinimumWidth(140)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        # 使用网格布局添加控件
        measurement_layout.addWidget(QtWidgets.QLabel("ΔX:"), 0, 0)
        measurement_layout.addWidget(self.dx_label, 0, 1)
        measurement_layout.addWidget(QtWidgets.QLabel("ΔY:"), 1, 0)
        measurement_layout.addWidget(self.dy_label, 1, 1)
        measurement_layout.addWidget(QtWidgets.QLabel("频率:"), 2, 0)
        measurement_layout.addWidget(self.freq_label, 2, 1)

        # 设置列的最小宽度
        measurement_layout.setColumnMinimumWidth(0, 50)  # 标签列
        measurement_layout.setColumnMinimumWidth(1, 120)  # 数值列

        content_layout.addWidget(self.measurement_group)

        # 添加弹性空间，使内容顶部对齐
        content_layout.addStretch()

        # 添加滚动区域到主布局
        main_layout.addWidget(content_widget)

        # 设置整个widget的最小尺寸
        self.setMinimumWidth(250)  # 确保有足够宽度显示所有控件
        self.setMinimumHeight(280)  # 设置合理的最小高度

        # 初始状态
        self.cursor_group.setEnabled(False)
        self.measurement_group.setEnabled(False)

    def _connect_signals(self):
        """连接信号"""
        self.enable_checkbox.toggled.connect(self._on_enable_changed)
        self.x1_spinbox.valueChanged.connect(lambda v: self._on_cursor_changed("x1", v))
        self.x2_spinbox.valueChanged.connect(lambda v: self._on_cursor_changed("x2", v))
        self.y1_spinbox.valueChanged.connect(lambda v: self._on_cursor_changed("y1", v))
        self.y2_spinbox.valueChanged.connect(lambda v: self._on_cursor_changed("y2", v))

    def _on_enable_changed(self, enabled: bool):
        """光标启用状态改变"""
        self.cursor_group.setEnabled(enabled)
        self.measurement_group.setEnabled(enabled)
        self.cursorEnabledChanged.emit(enabled)

        if enabled:
            self._update_measurements()

    def _on_cursor_changed(self, cursor_name: str, value: float):
        """光标位置改变"""
        self.cursor_values[cursor_name] = value
        self.cursorChanged.emit(cursor_name, value)
        self._update_measurements()

    def _update_measurements(self):
        """更新测量结果"""
        if not self.enable_checkbox.isChecked():
            return

        ch_config = self.ch_defs[self.scope_widget.current_channel]
        unit = ch_config.get("unit", "")

        dx = abs(self.cursor_values["x2"] - self.cursor_values["x1"])
        dy = abs(self.cursor_values["y2"] - self.cursor_values["y1"])
        freq = 1.0 / dx if dx > 0 else 0.0

        self.dx_label.setText(f"{dx:.6f} s")
        self.dy_label.setText(f"{dy:.3f} {unit}")
        self.freq_label.setText(f"{freq:.3f} Hz")

    def update_cursor_values(self, values: Dict[str, float]):
        """
        更新光标值（来自示波器视图）

        Args:
            values: 光标值字典
        """
        # 暂时断开信号连接，避免循环更新
        self.x1_spinbox.blockSignals(True)
        self.x2_spinbox.blockSignals(True)
        self.y1_spinbox.blockSignals(True)
        self.y2_spinbox.blockSignals(True)

        self.x1_spinbox.setValue(values.get("x1", 0.0))
        self.x2_spinbox.setValue(values.get("x2", 1.0))
        self.y1_spinbox.setValue(values.get("y1", 0.0))
        self.y2_spinbox.setValue(values.get("y2", 1.0))


        ch_config = self.ch_defs[self.scope_widget.current_channel]
        unit = " " + ch_config.get("unit", "")
        self.y1_spinbox.setSuffix(unit)
        self.y2_spinbox.setSuffix(unit)

        # 恢复信号连接
        self.x1_spinbox.blockSignals(False)
        self.x2_spinbox.blockSignals(False)
        self.y1_spinbox.blockSignals(False)
        self.y2_spinbox.blockSignals(False)

        self.cursor_values.update(values)
        self._update_measurements()

    def is_enabled(self) -> bool:
        """获取光标是否启用"""
        return self.enable_checkbox.isChecked()

    def set_enabled(self, enabled: bool):
        """设置光标是否启用"""
        self.enable_checkbox.setChecked(enabled)
