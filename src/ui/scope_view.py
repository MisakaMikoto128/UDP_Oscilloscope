# -*- coding: utf-8 -*-
"""
示波器显示组件
使用pyqtgraph实现高性能波形显示
直接继承GraphicsLayoutWidget优化设计
"""

import pyqtgraph as pg
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
from typing import List, Optional, Tuple, Callable
import logging
import time
from src.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class ScopeWidget(pg.GraphicsLayoutWidget):
    """
    示波器显示组件
    支持多通道波形显示、网格、光标等功能
    直接继承GraphicsLayoutWidget
    """

    # 信号定义
    timeBaseChanged = QtCore.pyqtSignal(float)  # 时基改变信号
    verticalScaleChanged = QtCore.pyqtSignal(
        int, float
    )  # 垂直挡位改变信号 (channel, div)
    verticalOffsetChanged = QtCore.pyqtSignal(
        int, float
    )  # 垂直偏移改变信号 (channel, offset)

    # 新增的键盘滚轮组合信号
    ctrlWheelEvent = QtCore.pyqtSignal(int)  # CTRL+滚轮事件 (delta)
    shiftWheelEvent = QtCore.pyqtSignal(int)  # SHIFT+滚轮事件 (delta)
    normalWheelEvent = QtCore.pyqtSignal(int)  # SHIFT+滚轮事件 (delta)

    def __init__(
        self,
        n_channels: int = 10,
        sample_rate: float = 1000.0,
        cfg: ConfigManager = None,
        parent=None,
    ):
        """
        初始化示波器视图

        Args:
            n_channels: 通道数量
            sample_rate: 采样频率 (Hz)
            parent: 父组件
        """
        super().__init__(parent)

        self.cfg: ConfigManager = cfg
        self.n_channels = n_channels
        self.sample_rate = sample_rate  # 采样频率
        logger.info(f"ScopeWidget 设置采样频率为：{sample_rate:.2f}Hz")
        self.max_points_window = 60000
        self.max_points_preview = 60000

        # 通道数据和曲线
        self.curves = []
        self.channel_data = [np.array([], dtype=np.float32) for _ in range(n_channels)]
        self.channel_enabled = [True] * n_channels

        # 光标相关
        self.cursors_enabled = False
        self.cursor_lines = {"x1": None, "x2": None, "y1": None, "y2": None}
        self.cursor_values = {"x1": 0.0, "x2": -0.1, "y1": 0.0, "y2": -0.1}

        # 显示参数
        self.x_spin = 0.1  # 0.1s
        self.x_offset = 0.0  # 0s
        self.vertical_scale_factors = [1.0] * n_channels  # 1unit/div for each channel
        self.vertical_offsets = [0.0] * n_channels
        self._dt_cache = 1.0 / self.sample_rate  # 缓存采样间隔
        self._time_axis_cache = np.array([], dtype=np.float32)  # 时间轴缓存
        self._last_time_axis_len = 0  # 上次时间轴长度

        # 当前选中的通道
        self.current_channel = 0
        # 滚动模式
        self.auto_roll = True

        # 键盘状态跟踪
        self.ctrl_pressed = False
        self.shift_pressed = False

        # 创建图形布局
        self._setup_ui()
        # 创建通道曲线
        self._create_curves()
        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        logger.info(f"示波器视图已初始化: {n_channels}通道, 采样率: {sample_rate}Hz")

    # 当采样率或垂直挡位改变时更新缓存的方法：
    def _update_dt_cache(self):
        """更新采样间隔缓存"""
        self._dt_cache = 1.0 / self.sample_rate
  
    def wheelEvent(self, event):
        """重写滚轮事件处理"""
        delta = event.angleDelta().y()

        if self.ctrl_pressed:
            # CTRL + 滚轮：发射信号给外部处理
            self.ctrlWheelEvent.emit(delta)
            self.handle_ctrl_wheel(delta)
            event.accept()
            return
        elif self.shift_pressed:
            # SHIFT + 滚轮：发射信号给外部处理
            self.shiftWheelEvent.emit(delta)
            self.handle_shift_wheel(delta)
            event.accept()
            return
        else:
            # 普通滚轮：默认行为或自定义处理
            self.normalWheelEvent.emit(delta)
            # self._handle_normal_wheel(delta)
            event.accept()
            return

    def _handle_normal_wheel(self, delta):
        """处理普通滚轮事件（水平缩放时基）"""
        step = 0.01
        offset_delta = step if delta > 0 else -step
        new_x_spin = self.x_spin + offset_delta

        self.x_spin = max(0, self.x_spin)
        if new_x_spin != self.x_spin:
            self.x_spin = new_x_spin
            self.timeBaseChanged.emit(new_x_spin)
            self.plot_item.setXRange(-self.x_spin, self.x_offset)

            print(f"X axis range changed to {new_x_spin:.3f}s")

    def handle_ctrl_wheel(self, delta):
        curr_ch = self.current_channel
        step = 0.001
        offset_delta = step if delta > 0 else -step
        current_vertical_scale_factor = self.vertical_scale_factors[curr_ch]
        new_vertical_scale_factor = current_vertical_scale_factor + offset_delta
        # 限制缩放范围
        new_vertical_scale_factor = max(0.0001, min(2000.0, new_vertical_scale_factor))

        if new_vertical_scale_factor != current_vertical_scale_factor:
            self.vertical_scale_factors[curr_ch] = new_vertical_scale_factor
            self.verticalScaleChanged.emit(curr_ch, self.vertical_scale_factors[curr_ch])

    def handle_shift_wheel(self, delta):
        offset_delta = 0.1 if delta > 0 else -0.1
        current_offset = self.vertical_offsets[self.current_channel]
        new_offset = current_offset + offset_delta

        self.vertical_offsets[self.current_channel] = new_offset
        self.verticalOffsetChanged.emit(self.current_channel, new_offset)
        print(
            f"Vertical offset changed: CH{self.current_channel + 1} = {new_offset:.3f} V"
        )

    def keyPressEvent(self, event):
        """重写键盘按下事件"""
        if event.key() == QtCore.Qt.Key_Control:
            self.ctrl_pressed = True
        elif event.key() == QtCore.Qt.Key_Shift:
            self.shift_pressed = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """重写键盘释放事件"""
        if event.key() == QtCore.Qt.Key_Control:
            self.ctrl_pressed = False
        elif event.key() == QtCore.Qt.Key_Shift:
            self.shift_pressed = False
        super().keyReleaseEvent(event)

    def set_sample_rate(self, sample_rate: float):
        """设置采样频率"""
        self.sample_rate = sample_rate
        self._update_dt_cache()
        print(f"Sample rate changed: {sample_rate} Hz")

    def get_sample_rate(self) -> float:
        """获取采样频率"""
        return self.sample_rate

    def set_current_channel(self, channel: int):
        """设置当前选中的通道"""
        if 0 <= channel < self.n_channels:
            self.current_channel = channel

    def reset_time_offset(self, enabled: bool):
        """设置自动滚动模式"""
        # 进入滚动模式，重置偏移
        self.x_offset = 0.0
        logger.info(f"Auto roll set to {enabled}, time_offset reset to {self.x_offset}")

    def _setup_ui(self):
        """设置UI布局"""
        # 创建绘图区域
        self.plot_item: pg.ViewBox = self.addPlot()

        # 设置标签和网格
        self.plot_item.setLabel("left", "幅值")
        self.plot_item.setLabel("bottom", "时间", units="s")
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        # 设置背景颜色（示波器风格）
        self.plot_item.getViewBox().setBackgroundColor("#001122")

        # 设置坐标轴颜色
        axis_pen = pg.mkPen(color="#00FF00", width=1)
        self.plot_item.getAxis("left").setPen(axis_pen)
        self.plot_item.getAxis("bottom").setPen(axis_pen)

        # 禁用默认的鼠标交互
        self.plot_item.setMouseEnabled(x=True, y=True)
        self.plot_item.enableAutoRange(False)
        # 6. 性能优化设置
        self.plot_item.setDownsampling(auto=True, mode='peak')  # 启用峰值下采样
        self.plot_item.setClipToView(True)  # 只渲染可见区域

        # 设置固定的Y轴范围（专业示波器风格）
        self.plot_item.setXRange(-self.x_spin, 0)

    def _create_curves(self):
        """创建通道曲线"""
        # 预定义颜色
        colors = [
            "#FF6B6B",
            "#4ECDC4",
            "#45B7D1",
            "#FFA07A",
            "#98D8C8",
            "#F7DC6F",
            "#BB8FCE",
            "#85C1E9",
            "#F8C471",
            "#82E0AA",
        ]

        plot_item: pg.ViewBox = self.plot_item
        for i in range(self.n_channels):
            color = colors[i % len(colors)]
            pen = pg.mkPen(color=color, width=1)

            curve = plot_item.plot(
                pen=pen,
                skipFiniteCheck=True,  # 跳过有限值检查 - 重要优化！
                antialias=False,
                name=f"CH{i + 1}",
            )
            self.curves.append(curve)

    def set_channel_pen(self, channel: int, color_or_pen):
        """
        设置通道画笔颜色

        Args:
            channel: 通道索引
            color_or_pen: 颜色字符串或画笔对象
        """
        if 0 <= channel < len(self.curves):
            if isinstance(color_or_pen, str):
                pen = pg.mkPen(color=color_or_pen, width=2)
            else:
                pen = color_or_pen
            self.curves[channel].setPen(pen)

    def set_channel_enabled(self, channel: int, enabled: bool):
        """
        设置通道是否启用

        Args:
            channel: 通道索引
            enabled: 是否启用
        """
        if 0 <= channel < self.n_channels:
            self.channel_enabled[channel] = enabled
            if enabled:
                self.curves[channel].show()
            else:
                self.curves[channel].hide()

    def update_tail(self, data_arrays: List[np.ndarray], realtime_mode:bool = True):
        """
        更新波形显示 - 优化版本

        Args:
            data_arrays: 每个通道的数据数组列表
            _max_points_preview: 预览模式的最大显示点数，默认使用 self.max_points_window
        """
        if not data_arrays:
            return

        try:
            n_points = len(data_arrays[0])
            n = min(n_points, self.max_points_window if realtime_mode else self.max_points_preview)
            if n == 0:
                return

            # 1) 时间轴（只算一次）
            if n != self._last_time_axis_len:
                self._time_axis_cache = np.linspace(
                    -(n - 1) * self._dt_cache, 0, n, dtype=np.float32
                )
                self._last_time_axis_len = n
            t = self._time_axis_cache

            # 2) 叠成 (n_channels, n) 连续数组
            stacked = np.vstack([d[-n:] for d in data_arrays]).astype(np.float32)

            # 3) 垂直变换（广播）
            scale  = np.array(self.vertical_scale_factors,  dtype=np.float32)[:, None]
            offset = np.array(self.vertical_offsets,       dtype=np.float32)[:, None]
            stacked *= scale
            stacked += offset

            start = time.perf_counter_ns()
            # 4) 逐通道更新（仍保留 self.curves 列表，对外 API 不变）
            for ch, curve in enumerate(self.curves):
                curve.setData_A(t, stacked[ch],
                            _callSync="off",
                            skipFiniteCheck=True)

            # curve = self.curves[0]
            # curve.informViewBoundsChanged()
            # curve.sigPlotChanged.emit(curve)

            # elapsed_ns = time.perf_counter_ns() - start
            # print(f"[update_tail] 耗时: {elapsed_ns / 1e6:.3f} ms")

        except Exception as e:
            logger.error(f"更新波形显示时出错: {e}")

    def set_time_offset(self, offset: float):
        """
        设置时间偏移

        Args:
            offset: 时间偏移值（秒）
        """
        self.x_offset = offset

    def set_vertical_scale(self, channel: int, div_value: float):
        """
        设置垂直缩放

        Args:
            channel: 通道索引
            div_value: 垂直挡位值
            offset: 垂直偏移值（可选）
        """
        if 0 <= channel < self.n_channels:
            self.vertical_scale_factors[channel] = div_value

    def set_vertical_offset(self, channel: int, offset: float):
        """
        设置垂直偏移

        Args:
            channel: 通道索引
            offset: 垂直偏移值
        """
        if 0 <= channel < self.n_channels:
            self.vertical_offsets[channel] = offset

    def enable_cursors(self, enabled: bool):
        """
        启用/禁用光标

        Args:
            enabled: 是否启用光标
        """
        self.cursors_enabled = enabled

        if enabled:
            self._create_cursors()
        else:
            self._remove_cursors()

    def _create_cursors(self):
        """创建光标线"""
        if not self.cursors_enabled:
            return

        # X轴光标（垂直线）
        if self.cursor_lines["x1"] is None:
            self.cursor_lines["x1"] = pg.InfiniteLine(
                pos=self.cursor_values["x1"],
                angle=90,
                pen=pg.mkPen("#FFFF00", width=2, style=QtCore.Qt.DashLine),
                movable=True,
                label="X1",
            )
            self.plot_item.addItem(self.cursor_lines["x1"])

        if self.cursor_lines["x2"] is None:
            self.cursor_lines["x2"] = pg.InfiniteLine(
                pos=self.cursor_values["x2"],
                angle=90,
                pen=pg.mkPen("#FFFF00", width=2, style=QtCore.Qt.DashLine),
                movable=True,
                label="X2",
            )
            self.plot_item.addItem(self.cursor_lines["x2"])

        # Y轴光标（水平线）
        if self.cursor_lines["y1"] is None:
            self.cursor_lines["y1"] = pg.InfiniteLine(
                pos=self.cursor_values["y1"],
                angle=0,
                pen=pg.mkPen("#FF00FF", width=2, style=QtCore.Qt.DashLine),
                movable=True,
                label="Y1",
            )
            self.plot_item.addItem(self.cursor_lines["y1"])

        if self.cursor_lines["y2"] is None:
            self.cursor_lines["y2"] = pg.InfiniteLine(
                pos=self.cursor_values["y2"],
                angle=0,
                pen=pg.mkPen("#FF00FF", width=2, style=QtCore.Qt.DashLine),
                movable=True,
                label="Y2",
            )
            self.plot_item.addItem(self.cursor_lines["y2"])

    def _remove_cursors(self):
        """移除光标线"""
        for cursor_name, cursor_line in self.cursor_lines.items():
            if cursor_line is not None:
                self.plot_item.removeItem(cursor_line)
                self.cursor_lines[cursor_name] = None

    def set_cursor_position(self, cursor: str, position: float):
        """
        设置光标位置

        Args:
            cursor: 光标名称 ('x1', 'x2', 'y1', 'y2')
            position: 位置值
        """
        if cursor in self.cursor_values:
            self.cursor_values[cursor] = position

            if self.cursors_enabled and self.cursor_lines[cursor] is not None:
                self.cursor_lines[cursor].setPos(position)

    def get_cursor_values(self) -> dict:
        """
        获取光标值和差值

        Returns:
            光标值字典
        """
        if not self.cursors_enabled:
            return {}

        # 更新光标值（如果用户拖动了光标）
        for cursor_name, cursor_line in self.cursor_lines.items():
            if cursor_line is not None:
                self.cursor_values[cursor_name] = cursor_line.pos()[
                    0 if "x" in cursor_name else 1
                ]

        curr_vertical_offset = self.vertical_offsets[self.current_channel]

        return {
            "x1": self.cursor_values["x1"],
            "x2": self.cursor_values["x2"],
            "y1": (self.cursor_values["y1"] - curr_vertical_offset),
            "y2": (self.cursor_values["y2"] - curr_vertical_offset),
            "dx": (self.cursor_values["x2"] - self.cursor_values["x1"]),
            "dy": (self.cursor_values["y2"] - self.cursor_values["y1"]),
            "frequency": 1.0 / abs(self.cursor_values["x2"] - self.cursor_values["x1"])
            if abs(self.cursor_values["x2"] - self.cursor_values["x1"]) > 0
            else 0.0,
        }

    def clear_display(self):
        """清空显示"""
        for curve in self.curves:
            curve.clear()

        for i in range(self.n_channels):
            self.channel_data[i] = np.array([], dtype=np.float32)

    def export_image(self, file_path: str, width: int = 1920, height: int = 1080):
        """
        导出图像

        Args:
            file_path: 文件路径
            width: 图像宽度
            height: 图像高度
        """
        try:
            exporter = pg.exporters.ImageExporter(self.plot_item)
            exporter.parameters()["width"] = width
            exporter.parameters()["height"] = height
            exporter.export(file_path)
            logger.info(f"图像已导出: {file_path}")
        except Exception as e:
            logger.error(f"导出图像失败: {e}")

    def get_display_info(self) -> dict:
        """
        获取显示信息

        Returns:
            显示信息字典
        """
        return {
            "n_channels": self.n_channels,
            "max_points_window": self.max_points_window,
            "time_base": self.time_div,
            "time_offset": self.x_offset,
            "vertical_scales": self.vertical_scale_factors.copy(),
            "vertical_offsets": self.vertical_offsets.copy(),
            "cursors_enabled": self.cursors_enabled,
            "cursor_values": self.cursor_values.copy() if self.cursors_enabled else {},
            "channel_enabled": self.channel_enabled.copy(),
        }
