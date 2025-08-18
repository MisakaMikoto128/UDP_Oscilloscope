# -*- coding: utf-8 -*-
"""
示波器显示组件
使用pyqtgraph实现高性能波形显示
"""

import pyqtgraph as pg
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
from typing import List, Optional, Tuple, Callable
import logging

logger = logging.getLogger(__name__)

# 启用OpenGL加速
pg.setConfigOptions(useOpenGL=True)


class ScopeView(QtWidgets.QWidget):
    """
    示波器显示组件
    支持多通道波形显示、网格、光标等功能
    """

    # 信号定义
    timeBaseChanged = QtCore.pyqtSignal(float)  # 时基改变信号
    timeOffsetChanged = QtCore.pyqtSignal(float)  # 时间偏移改变信号
    verticalDivChanged = QtCore.pyqtSignal(int, float)  # 垂直挡位改变信号 (channel, div)
    verticalOffsetChanged = QtCore.pyqtSignal(int, float)  # 垂直偏移改变信号 (channel, offset)

    def __init__(self, n_channels: int = 10, sample_rate: float = 1000.0, parent=None):
        """
        初始化示波器视图

        Args:
            n_channels: 通道数量
            sample_rate: 采样频率 (Hz)
            parent: 父组件
        """
        super().__init__(parent)

        self.n_channels = n_channels
        self.sample_rate = sample_rate  # 采样频率
        self.max_points_window = 10000  # 窗口最大显示点数

        # 创建图形布局
        self._setup_ui()

        # 通道数据和曲线
        self.curves = []
        self.channel_data = [np.array([], dtype=np.float32) for _ in range(n_channels)]
        self.channel_enabled = [True] * n_channels

        # 创建通道曲线
        self._create_curves()

        # 光标相关
        self.cursors_enabled = False
        self.cursor_lines = {'x1': None, 'x2': None, 'y1': None, 'y2': None}
        self.cursor_values = {'x1': 0.0, 'x2': 1.0, 'y1': 0.0, 'y2': 1.0}

        # 显示参数
        self.time_base = 1.0  # ms/div
        self.time_offset = 0.0
        self.vertical_divs = [1.0] * n_channels  # V/div for each channel
        self.vertical_offsets = [0.0] * n_channels

        # 当前选中的通道
        self.current_channel = 0

        # 滚动模式
        self.auto_roll = True

        # 设置鼠标和键盘交互
        self._setup_interactions()

        logger.info(f"示波器视图已初始化: {n_channels}通道, 采样率: {sample_rate}Hz")

    def _setup_interactions(self):
        """设置鼠标和键盘交互"""
        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.graphics_widget.setFocusPolicy(QtCore.Qt.StrongFocus)

        # 安装事件过滤器到正确的widget
        self.graphics_widget.installEventFilter(self)
        self.installEventFilter(self)

        # 启用鼠标跟踪
        self.graphics_widget.setMouseTracking(True)
        self.setMouseTracking(True)

        # 记录鼠标状态
        self._mouse_pressed = False
        self._last_mouse_pos = None
        self._ctrl_pressed = False

    def eventFilter(self, obj, event):
        """事件过滤器，处理自定义鼠标和键盘交互"""
        # 调试：打印事件类型
        if hasattr(event, 'type'):
            event_type = event.type()
            # 只处理我们关心的事件类型
            if event_type in [QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease,
                             QtCore.QEvent.Wheel, QtCore.QEvent.MouseButtonPress,
                             QtCore.QEvent.MouseMove, QtCore.QEvent.MouseButtonRelease]:
                print(f"Event type: {event_type}, obj: {type(obj).__name__}")

        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Control:
                self._ctrl_pressed = True
                print("Ctrl pressed")
                return True
        elif event.type() == QtCore.QEvent.KeyRelease:
            if event.key() == QtCore.Qt.Key_Control:
                self._ctrl_pressed = False
                print("Ctrl released")
                return True
        elif event.type() == QtCore.QEvent.Wheel:
            print("Wheel event detected")
            return self._handle_wheel_event(event)
        elif event.type() == QtCore.QEvent.MouseButtonPress:
            print("Mouse press detected")
            return self._handle_mouse_press(event)
        elif event.type() == QtCore.QEvent.MouseMove:
            if self._mouse_pressed:
                print("Mouse move detected")
                return self._handle_mouse_move(event)
        elif event.type() == QtCore.QEvent.MouseButtonRelease:
            print("Mouse release detected")
            return self._handle_mouse_release(event)

        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        """重写滚轮事件处理"""
        print(f"Wheel event in wheelEvent: delta={event.angleDelta().y()}, ctrl={self._ctrl_pressed}")

        if self._ctrl_pressed:
            # Ctrl + 滚轮：垂直缩放当前通道
            delta = event.angleDelta().y()
            scale_factor = 1.1 if delta > 0 else 1.0 / 1.1

            current_div = self.vertical_divs[self.current_channel]
            new_div = current_div * scale_factor

            # 限制缩放范围
            new_div = max(0.001, min(1000.0, new_div))

            if new_div != current_div:
                self.vertical_divs[self.current_channel] = new_div
                self.verticalDivChanged.emit(self.current_channel, new_div)
                self._update_display()
                print(f"Vertical scale changed: CH{self.current_channel+1} = {new_div}")
        else:
            # 普通滚轮：水平缩放（时基）
            delta = event.angleDelta().y()
            scale_factor = 1.1 if delta > 0 else 1.0 / 1.1

            new_time_base = self.time_base * scale_factor

            # 限制时基范围
            new_time_base = max(0.001, min(1000.0, new_time_base))

            if new_time_base != self.time_base:
                self.time_base = new_time_base
                self.timeBaseChanged.emit(new_time_base)
                self._update_time_axis()
                print(f"Time base changed: {new_time_base} ms/div")

        event.accept()

    def keyPressEvent(self, event):
        """重写键盘按下事件"""
        if event.key() == QtCore.Qt.Key_Control:
            self._ctrl_pressed = True
            print("Ctrl pressed in keyPressEvent")
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """重写键盘释放事件"""
        if event.key() == QtCore.Qt.Key_Control:
            self._ctrl_pressed = False
            print("Ctrl released in keyReleaseEvent")
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        """重写鼠标按下事件"""
        if event.button() == QtCore.Qt.LeftButton:
            self._mouse_pressed = True
            self._last_mouse_pos = event.pos()
            print(f"Mouse pressed at {event.pos()}")
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """重写鼠标移动事件"""
        if self._mouse_pressed and self._last_mouse_pos is not None:
            current_pos = event.pos()
            delta_x = current_pos.x() - self._last_mouse_pos.x()
            delta_y = current_pos.y() - self._last_mouse_pos.y()

            if self._ctrl_pressed:
                # Ctrl + 拖拽：垂直偏移当前通道
                sensitivity = 0.01
                y_delta = delta_y * sensitivity

                current_offset = self.vertical_offsets[self.current_channel]
                new_offset = current_offset - y_delta

                self.vertical_offsets[self.current_channel] = new_offset
                self.verticalOffsetChanged.emit(self.current_channel, new_offset)
                self._update_display()
                print(f"Vertical offset changed: CH{self.current_channel+1} = {new_offset}")
            else:
                # 普通拖拽：水平偏移
                sensitivity = 0.001
                x_delta = delta_x * sensitivity

                new_offset = self.time_offset - x_delta
                self.time_offset = new_offset
                self.timeOffsetChanged.emit(new_offset)
                self._update_time_axis()
                print(f"Time offset changed: {new_offset}")

            self._last_mouse_pos = current_pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """重写鼠标释放事件"""
        if event.button() == QtCore.Qt.LeftButton:
            self._mouse_pressed = False
            self._last_mouse_pos = None
            print("Mouse released")
        super().mouseReleaseEvent(event)

    def _handle_wheel_event(self, event):
        """处理鼠标滚轮事件"""
        if self._ctrl_pressed:
            # Ctrl + 滚轮：垂直缩放当前通道
            delta = event.angleDelta().y()
            scale_factor = 1.1 if delta > 0 else 1.0 / 1.1

            current_div = self.vertical_divs[self.current_channel]
            new_div = current_div * scale_factor

            # 限制缩放范围
            new_div = max(0.001, min(1000.0, new_div))

            if new_div != current_div:
                self.vertical_divs[self.current_channel] = new_div
                self.verticalDivChanged.emit(self.current_channel, new_div)
                self._update_display()
        else:
            # 普通滚轮：水平缩放（时基）
            delta = event.angleDelta().y()
            scale_factor = 1.1 if delta > 0 else 1.0 / 1.1

            new_time_base = self.time_base * scale_factor

            # 限制时基范围
            new_time_base = max(0.001, min(1000.0, new_time_base))

            if new_time_base != self.time_base:
                self.time_base = new_time_base
                self.timeBaseChanged.emit(new_time_base)
                self._update_time_axis()

        return True  # 事件已处理

    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        if event.button() == QtCore.Qt.LeftButton:
            self._mouse_pressed = True
            self._last_mouse_pos = event.pos()
        return True

    def _handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        if self._mouse_pressed and self._last_mouse_pos is not None:
            current_pos = event.pos()
            delta_x = current_pos.x() - self._last_mouse_pos.x()
            delta_y = current_pos.y() - self._last_mouse_pos.y()

            if self._ctrl_pressed:
                # Ctrl + 拖拽：垂直偏移当前通道
                # 简化的像素到数据单位转换
                sensitivity = 0.01  # 调整灵敏度
                y_delta = delta_y * sensitivity

                current_offset = self.vertical_offsets[self.current_channel]
                new_offset = current_offset - y_delta  # 反向，符合直觉

                self.vertical_offsets[self.current_channel] = new_offset
                self.verticalOffsetChanged.emit(self.current_channel, new_offset)
                self._update_display()
            else:
                # 普通拖拽：水平偏移（只允许水平方向）
                # 简化的像素到时间单位转换
                sensitivity = 0.001  # 调整灵敏度
                x_delta = delta_x * sensitivity

                new_offset = self.time_offset - x_delta  # 反向，符合直觉
                self.time_offset = new_offset
                self.timeOffsetChanged.emit(new_offset)
                self._update_time_axis()

            self._last_mouse_pos = current_pos

        return True

    def _handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        if event.button() == QtCore.Qt.LeftButton:
            self._mouse_pressed = False
            self._last_mouse_pos = None
        return True

    def _update_display(self):
        """更新显示（重新绘制所有曲线）"""
        # 这里会触发update_tail方法重新绘制
        pass

    def _update_time_axis(self):
        """更新时间轴显示"""
        # 计算X轴范围
        if self.auto_roll:
            # 滚动模式：X轴原点在最右侧，显示最近的数据
            x_span = 10 * (self.time_base / 1000.0)  # 10个时基格，转换为秒
            x_max = 0  # 最新数据在X=0位置
            x_min = -x_span
        else:
            # 非滚动模式：X轴原点保持在0，可以偏移观察
            x_span = 10 * (self.time_base / 1000.0)  # 10个时基格，转换为秒
            x_center = self.time_offset  # 使用偏移值
            x_min = x_center - x_span / 2
            x_max = x_center + x_span / 2

        self.plot_item.setXRange(x_min, x_max, padding=0)
        print(f"Time axis updated: [{x_min:.3f}, {x_max:.3f}], auto_roll={self.auto_roll}")

    def set_sample_rate(self, rate: float):
        """设置采样频率"""
        self.sample_rate = rate
        self._update_time_axis()

    def set_current_channel(self, channel: int):
        """设置当前选中的通道"""
        if 0 <= channel < self.n_channels:
            self.current_channel = channel

    def set_auto_roll(self, enabled: bool):
        """设置自动滚动模式"""
        self.auto_roll = enabled

        # 切换模式时重置偏移
        if enabled:
            # 进入滚动模式，重置偏移
            self.time_offset = 0.0
        else:
            # 退出滚动模式，保持当前位置为中心
            self.time_offset = 0.0

        self._update_time_axis()
        print(f"Auto roll set to {enabled}, time_offset reset to {self.time_offset}")
    
    def _setup_ui(self):
        """设置UI布局"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建图形窗口
        self.graphics_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics_widget)
        
        # 创建绘图区域
        self.plot_item = self.graphics_widget.addPlot()
        
        # 设置标签和网格
        self.plot_item.setLabel('left', '幅值')
        self.plot_item.setLabel('bottom', '时间', units='s')
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        
        # 设置背景颜色（示波器风格）
        self.plot_item.getViewBox().setBackgroundColor('#001122')
        
        # 设置坐标轴颜色
        axis_pen = pg.mkPen(color='#00FF00', width=1)
        self.plot_item.getAxis('left').setPen(axis_pen)
        self.plot_item.getAxis('bottom').setPen(axis_pen)
        
        # 禁用默认的鼠标交互，我们将自定义
        self.plot_item.setMouseEnabled(x=False, y=False)
        self.plot_item.enableAutoRange(False)

        # 设置固定的Y轴范围（专业示波器风格）
        self.plot_item.setYRange(-4, 4)  # 8个垂直格，每格1单位
    
    def _create_curves(self):
        """创建通道曲线"""
        # 预定义颜色
        colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
            '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8C471', '#82E0AA'
        ]
        
        for i in range(self.n_channels):
            color = colors[i % len(colors)]
            pen = pg.mkPen(color=color, width=2)
            
            curve = self.plot_item.plot(
                pen=pen,
                name=f'CH{i+1}',
                antialias=True
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
    
    def update_tail(self, data_arrays: List[np.ndarray]):
        """
        更新波形显示

        Args:
            data_arrays: 每个通道的数据数组列表
        """
        if not data_arrays:
            return

        try:
            for channel, data in enumerate(data_arrays):
                if channel >= self.n_channels or not self.channel_enabled[channel]:
                    continue

                if len(data) == 0:
                    continue

                # 限制显示点数
                if len(data) > self.max_points_window:
                    data = data[-self.max_points_window:]

                # 生成时间轴
                if self.auto_roll:
                    # 滚动模式：最新数据在X=0，向左延伸
                    dt = 1.0 / self.sample_rate  # 采样间隔（秒）
                    time_axis = np.arange(len(data)) * (-dt)  # 负时间轴
                    time_axis = time_axis[::-1]  # 反转，使最新数据在右侧
                else:
                    # 非滚动模式：根据时基和偏移计算
                    dt = 1.0 / self.sample_rate
                    time_axis = np.arange(len(data)) * dt + self.time_offset

                # 应用垂直缩放和偏移（作用于曲线显示，不是坐标）
                # 注意：这里是对数据进行变换，而不是坐标变换
                scaled_data = (data / self.vertical_divs[channel] +
                              self.vertical_offsets[channel])

                # 更新曲线
                self.curves[channel].setData(time_axis, scaled_data)

        except Exception as e:
            logger.error(f"更新波形显示时出错: {e}")
    
    def set_time_base(self, time_base: float, unit: str = 'ms'):
        """
        设置时基

        Args:
            time_base: 时基值
            unit: 时基单位 ('ms', 's', 'us')
        """
        # 转换为毫秒
        if unit == 's':
            self.time_base = time_base * 1000
        elif unit == 'us':
            self.time_base = time_base / 1000
        else:  # ms
            self.time_base = time_base

        self._update_time_axis()
    
    def set_time_offset(self, offset: float):
        """
        设置时间偏移

        Args:
            offset: 时间偏移值（秒）
        """
        self.time_offset = offset
        self._update_time_axis()
    
    def set_vertical_scale(self, channel: int, div_value: float, offset: float = None):
        """
        设置垂直缩放

        Args:
            channel: 通道索引
            div_value: 垂直挡位值
            offset: 垂直偏移值（可选）
        """
        if 0 <= channel < self.n_channels:
            self.vertical_divs[channel] = div_value
            if offset is not None:
                self.vertical_offsets[channel] = offset
            self._update_display()

    def set_vertical_offset(self, channel: int, offset: float):
        """
        设置垂直偏移

        Args:
            channel: 通道索引
            offset: 垂直偏移值
        """
        if 0 <= channel < self.n_channels:
            self.vertical_offsets[channel] = offset
            self._update_display()
    
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
        if self.cursor_lines['x1'] is None:
            self.cursor_lines['x1'] = pg.InfiniteLine(
                pos=self.cursor_values['x1'],
                angle=90,
                pen=pg.mkPen('#FFFF00', width=1, style=QtCore.Qt.DashLine),
                movable=True,
                label='X1'
            )
            self.plot_item.addItem(self.cursor_lines['x1'])
        
        if self.cursor_lines['x2'] is None:
            self.cursor_lines['x2'] = pg.InfiniteLine(
                pos=self.cursor_values['x2'],
                angle=90,
                pen=pg.mkPen('#FFFF00', width=1, style=QtCore.Qt.DashLine),
                movable=True,
                label='X2'
            )
            self.plot_item.addItem(self.cursor_lines['x2'])
        
        # Y轴光标（水平线）
        if self.cursor_lines['y1'] is None:
            self.cursor_lines['y1'] = pg.InfiniteLine(
                pos=self.cursor_values['y1'],
                angle=0,
                pen=pg.mkPen('#FF00FF', width=1, style=QtCore.Qt.DashLine),
                movable=True,
                label='Y1'
            )
            self.plot_item.addItem(self.cursor_lines['y1'])
        
        if self.cursor_lines['y2'] is None:
            self.cursor_lines['y2'] = pg.InfiniteLine(
                pos=self.cursor_values['y2'],
                angle=0,
                pen=pg.mkPen('#FF00FF', width=1, style=QtCore.Qt.DashLine),
                movable=True,
                label='Y2'
            )
            self.plot_item.addItem(self.cursor_lines['y2'])
    
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
                self.cursor_values[cursor_name] = cursor_line.pos()[0 if 'x' in cursor_name else 1]
        
        return {
            'x1': self.cursor_values['x1'],
            'x2': self.cursor_values['x2'],
            'y1': self.cursor_values['y1'],
            'y2': self.cursor_values['y2'],
            'dx': abs(self.cursor_values['x2'] - self.cursor_values['x1']),
            'dy': abs(self.cursor_values['y2'] - self.cursor_values['y1']),
            'frequency': 1.0 / abs(self.cursor_values['x2'] - self.cursor_values['x1']) 
                        if abs(self.cursor_values['x2'] - self.cursor_values['x1']) > 0 else 0.0
        }
    
    def auto_scale(self, channel: Optional[int] = None):
        """
        自动缩放
        
        Args:
            channel: 指定通道，None表示所有通道
        """
        if channel is not None:
            # 单通道自动缩放
            if 0 <= channel < self.n_channels and len(self.channel_data[channel]) > 0:
                data = self.channel_data[channel]
                if len(data) > 0:
                    data_range = np.max(data) - np.min(data)
                    if data_range > 0:
                        self.vertical_divs[channel] = data_range / 8  # 8个垂直格
                        self.vertical_offsets[channel] = -np.mean(data)
        else:
            # 全部通道自动缩放
            self.plot_item.enableAutoRange()
    
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
            exporter.parameters()['width'] = width
            exporter.parameters()['height'] = height
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
            'n_channels': self.n_channels,
            'max_points_window': self.max_points_window,
            'time_base': self.time_base,
            'time_offset': self.time_offset,
            'vertical_divs': self.vertical_divs.copy(),
            'vertical_offsets': self.vertical_offsets.copy(),
            'cursors_enabled': self.cursors_enabled,
            'cursor_values': self.cursor_values.copy() if self.cursors_enabled else {},
            'channel_enabled': self.channel_enabled.copy()
        }
