# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable
import asyncio
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui
from qasync import asyncClose, asyncSlot
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from qfluentwidgets import InfoLevel, TeachingTip, InfoBarIcon, TeachingTipTailPosition
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout

from qfluentwidgets import (
    InfoBarIcon,
    InfoBar,
    PushButton,
    setTheme,
    Theme,
    FluentIcon,
    InfoBarPosition,
    InfoBarManager,
)

from src.communication.protocol import (
    SysREGsUpData,
)
from src.config.config_manager import ConfigManager
from src.ui import Ctrl_Panel_Form
from .motor_controller_parser import MotorControllerParser

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


class CtrlPanelForm(QtWidgets.QFrame, Ctrl_Panel_Form):
    """主窗口类"""

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
        self.cfg: ConfigManager = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        self.setObjectName("CtrlPanelForm")
        self.speed_set = 0
        self.speed_set_step = 10
        self.speed_max = 3000
        self.speed_min = -3000

        self.spinbox_speed.setValue(0)  # 设置默认速度为0

        self.send_timer = QTimer(self)
        self.send_timer.setInterval(600)
        self.send_timer.timeout.connect(self.send_data)
        self.send_timer.start()

        self.btn_stop_dev.clicked.connect(self.stop_device)
        self.btn_launch_dev.clicked.connect(self.launch_device)
        self.badge_online_status.setLevel(InfoLevel.ERROR)

        self.parser = MotorControllerParser()

        self.btn_speed_set.clicked.connect(self.set_speed)
        self.radio_btn_speed_1.clicked.connect(lambda: self.set_speed_step(1))
        self.radio_btn_speed_10.clicked.connect(lambda: self.set_speed_step(10))
        self.radio_btn_speed_100.clicked.connect(lambda: self.set_speed_step(100))

        self.period_send_sw = True
        self.sw_btn_host_computer.setChecked(True)
        self.sw_btn_host_computer.checkedChanged.connect(
            self.on_sw_btn_host_computer_checked_changed
        )

        # 初始化 ListWidget
        self.init_list_widgets()
        # self.test_show()
        QApplication.instance().installEventFilter(self)

    def init_list_widgets(self):
        """初始化列表控件"""
        # 设置右键点击选中行为
        self.list_dev_error.setSelectRightClickedRow(True)
        self.list_fault_status.setSelectRightClickedRow(True)

        # 初始状态显示无错误
        self.update_dev_error_list([])
        self.update_fault_status_list([])

    def test_show(self):
        sys_regs_up_data = SysREGsUpData(
            packet_type=1,
            reg_num=120,
            reg=[1023450 for _ in range(120)],
        )
        self.on_on_sys_regs_uploaded(sys_regs_up_data)

    def set_speed(self):
        self.speed_set = self.spinbox_speed.value()

    def set_speed_step(self, step: int):
        """设置速度步进值并更新 spinbox 的步进值"""
        self.speed_set_step = step
        self.spinbox_speed.setSingleStep(step)

    def on_sw_btn_host_computer_checked_changed(self, checked: bool):
        self.period_send_sw = checked

    async def send_speed_set_cmd(self):
        self.speed_set = min(max(self.speed_set, self.speed_min), self.speed_max)
        speed_set_int = int(self.speed_set * 100000)
        target_addr = (self.cfg.target_host, self.cfg.target_port)
        ret = await self.device_reg_set_func(
            49, [speed_set_int], target_addr=target_addr
        )
        return ret

    def update_btn_check_state(self):
        launched = self.speed_set != 0
        self.btn_launch_dev.setChecked(launched)
        self.btn_stop_dev.setChecked(not launched)

    @asyncSlot()
    async def send_data(self):
        self.update_btn_check_state()
        if self.period_send_sw:
            ret = await self.send_speed_set_cmd()
            if not ret:
                logger.info("设置速度失败")
                pass

    @asyncSlot()
    async def stop_device(self):
        self.speed_set = 0
        self.update_btn_check_state()
        self.spinbox_speed.setValue(self.speed_set)
        ret = await self.send_speed_set_cmd()
        if ret:
            InfoBar.success(
                title="电机停止结果",
                content="停止成功，收到回复！",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self,
            )
        else:
            logger.info("停止失败")
            InfoBar.error(
                title="电机停止结果",
                content="停止命令发送超时！",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    @asyncSlot()
    async def launch_device(self):
        if self.speed_set == 0:
            self.speed_set = 10
            self.update_btn_check_state()
            self.spinbox_speed.setValue(self.speed_set)

        ret = await self.send_speed_set_cmd()
        if ret:
            InfoBar.success(
                title="电机启动结果",
                content="启动成功，收到回复！",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self,
            )
        else:
            logger.info("启动失败")
            InfoBar.error(
                title="电机启动结果",
                content="启动命令发送超时！",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    def update_dev_error_list(self, error_list: List[str]):
        """更新设备错误列表"""
        self.list_dev_error.clear()

        if not error_list:
            # 没有错误时显示"无报错"
            item = QListWidgetItem("无报错")
            # 可以设置图标，如果有合适的图标的话
            # item.setIcon(QIcon(':/path/to/success_icon.png'))
            self.list_dev_error.addItem(item)
        else:
            # 添加错误信息
            for error in error_list:
                item = QListWidgetItem(error)
                # 可以设置错误图标
                # item.setIcon(QIcon(':/path/to/error_icon.png'))
                self.list_dev_error.addItem(item)

    def update_fault_status_list(self, fault_list: List[str]):
        """更新故障状态列表"""
        self.list_fault_status.clear()

        if not fault_list:
            # 没有故障时显示"无故障"
            item = QListWidgetItem("无故障")
            # 可以设置图标
            # item.setIcon(QIcon(':/path/to/success_icon.png'))
            self.list_fault_status.addItem(item)
        else:
            # 添加故障信息
            for fault in fault_list:
                item = QListWidgetItem(fault)
                # 可以设置故障图标
                # item.setIcon(QIcon(':/path/to/fault_icon.png'))
                self.list_fault_status.addItem(item)

    @asyncSlot(SysREGsUpData)
    async def on_on_sys_regs_uploaded(self, sys_regs_up_data: SysREGsUpData):
        try:
            fixed_point_scale = 100000

            MCV_mSpeed = -uint32_to_int32(sys_regs_up_data.reg[83]) / fixed_point_scale
            MCV_angle = sys_regs_up_data.reg[62] / fixed_point_scale
            Vbus = uint32_to_int32(sys_regs_up_data.reg[76]) / fixed_point_scale
            Vbus_in = uint32_to_int32(sys_regs_up_data.reg[77]) / fixed_point_scale
            Id = uint32_to_int32(sys_regs_up_data.reg[56]) / fixed_point_scale
            Iq = uint32_to_int32(sys_regs_up_data.reg[59]) / fixed_point_scale
            Ud = uint32_to_int32(sys_regs_up_data.reg[60]) / fixed_point_scale
            Uq = uint32_to_int32(sys_regs_up_data.reg[61]) / fixed_point_scale
            temperature_u32 = sys_regs_up_data.reg[55]
            error_code_u32 = sys_regs_up_data.reg[63]
            MCV_mDuty = uint32_to_int32(sys_regs_up_data.reg[64]) / fixed_point_scale
            MCV_mPT1 = uint32_to_int32(sys_regs_up_data.reg[65]) / fixed_point_scale
            MCV_mPT2 = uint32_to_int32(sys_regs_up_data.reg[66]) / fixed_point_scale
            MCV_mPT3 = uint32_to_int32(sys_regs_up_data.reg[67]) / fixed_point_scale
            MCV_mPT4 = uint32_to_int32(sys_regs_up_data.reg[68]) / fixed_point_scale
            MCV_mPT5 = uint32_to_int32(sys_regs_up_data.reg[69]) / fixed_point_scale
            MCV_Ia = uint32_to_int32(sys_regs_up_data.reg[73]) / fixed_point_scale
            MCV_Ib = uint32_to_int32(sys_regs_up_data.reg[74]) / fixed_point_scale
            MCV_Ic = uint32_to_int32(sys_regs_up_data.reg[75]) / fixed_point_scale
            MCV_Ibus = uint32_to_int32(sys_regs_up_data.reg[79]) / fixed_point_scale

            self.label_vdc.setText(f"{Vbus:<7.2f}")
            self.label_vbus_in.setText(f"{Vbus_in:<7.2f}")
            self.label_uq.setText(f"{Uq:<7.2f}")
            self.label_id.setText(f"{Id:<7.2f}")
            self.label_iq.setText(f"{Iq:<7.2f}")
            self.label_ud.setText(f"{Ud:<7.2f}")
            self.label_ia.setText(f"{MCV_Ia:<7.2f}")
            self.label_ib.setText(f"{MCV_Ib:<7.2f}")
            self.label_ic.setText(f"{MCV_Ic:<7.2f}")
            self.label_ibus.setText(f"{MCV_Ibus:<7.2f}")

            info = self.parser.get_display_info(temperature_u32, error_code_u32)
            self.label_speed.setText(f"转速：    {MCV_mSpeed:<7.2f}")
            self.label_angle.setText(f"角度：    {MCV_angle:<7.2f}")
            self.label_duty_cycle.setText(f"占空比：{MCV_mDuty:<7.2f}")
            self.label_temperature.setText(
                f"逆变温度：A:{info['temp_d']} B:{info['temp_c']} C:{info['temp_b']}℃"
            )
            self.label_motor_temp.setText(
                f"电机温度：{MCV_mPT1:<7.2f} {MCV_mPT2:<7.2f} {MCV_mPT3:<7.2f} {MCV_mPT4:<7.2f} {MCV_mPT5:<7.2f}℃"
            )
            self.label_sys_status.setText(
                f"状态：{info['state_en']}:{info['state_cn']}"
            )
            error_d = (error_code_u32 >> 24) & 0xFF
            error_c = (error_code_u32 >> 16) & 0xFF
            error_b = (error_code_u32 >> 8) & 0xFF
            self.label_fault_status.setText(
                f"故障状态：A:0x{error_d:02X} B:0x{error_c:02X} C:0x{error_b:02X}"
            )
            all_errors = info.get("all_errors", [])
            self.update_dev_error_list(all_errors)

            flag1_int32 = sys_regs_up_data.reg[90]
            flag1_uint32 = flag1_int32 & 0xFFFFFFFF
            # flag1_uint32 = 0xF00F001  # 示例值
            self.update_fault_status(flag1_uint32)

        except Exception as e:
            logger.info(f"解析数据错误{e}")

    def update_fault_status(self, flag1_uint32):
        """更新故障状态"""
        fault_info = self.parser.parse_fault_flags(flag1_uint32)

        # 收集所有故障信息
        fault_list = []
        for category, status in fault_info.items():
            if status:
                fault_list.extend(status)

        # 更新故障状态列表
        self.update_fault_status_list(fault_list)

    @asyncSlot(bool)
    async def on_net_online_status_changed(self, online_status: bool):
        if online_status:
            self.label_online_status.setText("以太网在线")
            self.badge_online_status.setLevel(InfoLevel.SUCCESS)
        else:
            self.label_online_status.setText("以太网离线")
            self.badge_online_status.setLevel(InfoLevel.ERROR)

    def increase_speed(self):
        self.speed_set = min(self.speed_set + self.speed_set_step, self.speed_max)
        self.spinbox_speed.setValue(self.speed_set)
        logger.info("Key_Up (global)")

    def decrease_speed(self):
        self.speed_set = max(self.speed_set - self.speed_set_step, self.speed_min)
        self.spinbox_speed.setValue(self.speed_set)
        logger.info("Key_Down (global)")

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key == QtCore.Qt.Key_Up:
                self.increase_speed()
                return True  # 拦截事件，防止继续传递
            elif key == QtCore.Qt.Key_Down:
                self.decrease_speed()
                return True
            elif key == QtCore.Qt.Key_Return or key == QtCore.Qt.Key_Enter:
                asyncio.ensure_future(self.launch_device())
                return True
            elif key == QtCore.Qt.Key_Space:
                asyncio.ensure_future(self.stop_device())
                return True
        return super().eventFilter(source, event)
