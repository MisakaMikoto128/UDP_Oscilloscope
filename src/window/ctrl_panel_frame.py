# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui
from qasync import asyncClose, asyncSlot
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from qfluentwidgets import InfoLevel

from src.communication.protocol import (
    SysREGsUpData,
)
from src.communication.udp_master import UDPMaster
from src.config.config_manager import ConfigManager
from src.data.data_buffer import RingBuffer
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

        # 屏蔽spinbox的滚轮事件
        self.spinbox_speed.installEventFilter(self)
        self.spinbox_speed.setValue(0)  # 设置默认速度为0

        self.send_timer = QTimer(self)
        self.send_timer.setInterval(600)
        self.send_timer.timeout.connect(self.send_data)
        self.send_timer.start()

        self.btn_stop_dev.clicked.connect(self.stop_device)
        self.btn_launch_dev.clicked.connect(self.launch_device)
        self.badge_online_status.setLevel(InfoLevel.ERROR)

    
        self.parser = MotorControllerParser()
        # self.test_show()

    def test_show(self):
        sys_regs_up_data = SysREGsUpData(
            packet_type=1,
            reg_num=120,
            reg=[1023450 for _ in range(120)],
        )
        self.on_on_sys_regs_uploaded(sys_regs_up_data)

    @asyncSlot()
    async def send_data(self):
        speed_set = self.spinbox_speed.value()  # 获取速度设置值
        if speed_set > 3000:
            speed_set = 3000
        elif speed_set < -3000:
            speed_set = -3000

        speed_set = int(speed_set * 100000)
        target_addr = (self.cfg.target_host, self.cfg.target_port)
        ret = await self.device_reg_set_func(49, [speed_set], target_addr=target_addr)
        if not ret:
            logger.info("设置速度失败")
            pass

    @asyncSlot()
    async def stop_device(self):
        self.spinbox_speed.setValue(0)
        target_addr = (self.cfg.target_host, self.cfg.target_port)
        ret = await self.device_reg_set_func(49, [0], target_addr=target_addr)
        if not ret:
            logger.info("停止失败")
            pass

    @asyncSlot()
    async def launch_device(self):
        self.spinbox_speed.setValue(10)
        target_addr = (self.cfg.target_host, self.cfg.target_port)
        ret = await self.device_reg_set_func(49, [10 * 100000], target_addr=target_addr)
        if not ret:
            logger.info("启动失败")
            pass

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

            info = self.parser.get_display_info(temperature_u32, error_code_u32)

            self.label_vdc.setText(f"Vdc:     {Vbus:<7.2f}")
            self.label_vbus_in.setText(f"Vbus_in: {Vbus_in:<7.2f}")
            self.label_uq.setText(f"Uq:      {Uq:<7.2f}")
            self.label_id.setText(f"Id:      {Id:<7.2f}")
            self.label_iq.setText(f"Iq:      {Iq:<7.2f}")
            self.label_ud.setText(f"Ud:      {Ud:<7.2f}")
            self.label_ia.setText(f"Ia:      {MCV_Ia:<7.2f}")
            self.label_ib.setText(f"Ib:      {MCV_Ib:<7.2f}")
            self.label_ic.setText(f"Ic:      {MCV_Ic:<7.2f}")
            self.label_ibus.setText(f"Ibus:      {MCV_Ibus:<7.2f}")

            self.label_speed.setText(f"转速：    {MCV_mSpeed:<7.2f}")
            self.label_angle.setText(f"角度：    {MCV_angle:<7.2f}")
            self.label_duty_cycle.setText(f"占空比：{MCV_mDuty:<7.2f}")
            self.label_temperature.setText(f"逆变温度：A:{info['temp_d']} B:{info['temp_c']} C:{info['temp_b']}℃")
            self.label_sys_status.setText(f"状态：{info['state_en']}:{info['state_cn']}")
            self.label_dev_error.setText(f"报错：{info['error_text']}")
            self.label_motor_temp.setText(f"电机温度：{MCV_mPT1:<7.2f} {MCV_mPT2:<7.2f} {MCV_mPT3:<7.2f} {MCV_mPT4:<7.2f} {MCV_mPT5:<7.2f}℃")




            flag1_int32 = sys_regs_up_data.reg[90]
            flag1_uint32 = flag1_int32 & 0xFFFFFFFF
            # flag1_uint32 = 0xF00F001  # 示例值
            self.update_fault_status(flag1_uint32)

        except Exception as e:
            logger.info(f"解析数据错误{e}")

    @staticmethod
    def parse_flag1(flag1_uint32):
        # 定义状态位的掩码和中文描述
        ocflt_bits = [
            ("C相硬件过流", 1 << 24),
            ("B相硬件过流", 1 << 25),
            ("A相硬件过流", 1 << 26),
            ("母线硬件过流", 1 << 27),
            ("C相软件过流", 1 << 28),
            ("B相软件过流", 1 << 29),
            ("A相软件过流", 1 << 30),
            ("母线软件过流", 1 << 31),
        ]

        sysstatus_bits = [
            ("自检异常", 1 << 16),
            ("缺相", 1 << 17),
            ("电机过热", 1 << 18),
            ("逆变器过温", 1 << 19),
            ("功率器件保护", 1 << 20),
            ("母线欠压", 1 << 21),
            ("母线过压", 1 << 22),
            ("逆变器过流", 1 << 23),
        ]

        invstatus_bits = [
            ("Ib_Err", 1 << 8),
            ("Ia_Err", 1 << 9),
            ("Ibus_Err", 1 << 10),
            ("Vbus_Err", 1 << 11),
            ("NTC4_Err", 1 << 12),
            ("NTC3_Err", 1 << 13),
            ("NTC2_Err", 1 << 14),
            ("NTC1_Err", 1 << 15),
        ]

        motstatus_bits = [
            ("位置传感器异常", 1 << 0),
            ("内部超速", 1 << 1),
            ("CPLD_FLT", 1 << 2),
            ("FLT4_Flag", 1 << 3),
            ("FLT3_Flag", 1 << 4),
            ("FLT2_Flag", 1 << 5),
            ("FLT1_Flag", 1 << 6),
            ("Ic_Err", 1 << 7),
        ]

        # 提取每个状态位的值并生成描述字符串
        def extract_bits(bits, flag1):
            result = []
            for name, mask in bits:
                if flag1 & mask:
                    result.append(name)
            return result

        ocflt_status = extract_bits(ocflt_bits, flag1_uint32)
        sysstatus_status = extract_bits(sysstatus_bits, flag1_uint32)
        invstatus_status = extract_bits(invstatus_bits, flag1_uint32)
        motstatus_status = extract_bits(motstatus_bits, flag1_uint32)

        return {
            "OCFLT": ocflt_status,
            "SYSSTATUS": sysstatus_status,
            "INVSTATUS": invstatus_status,
            "MOTSTATUS": motstatus_status,
        }

    def update_fault_status(self, flag1_uint32):
        flag1 = self.parse_flag1(flag1_uint32)

        # 生成显示的文本
        fault_list = []
        for category, status in flag1.items():
            if status:
                fault_list.extend(status)

        # 设置 QLabel 的文本
        self.label_fault_status.setWordWrap(True)  # 允许自动换行
        if fault_list:
            self.label_fault_status.setText("故障状态：\t" + "\t".join(fault_list))
            self.badge_fault_status.setLevel(InfoLevel.ERROR)
        else:
            self.label_fault_status.setText("故障状态：\t无故障")
            self.badge_fault_status.setLevel(InfoLevel.SUCCESS)

    @asyncSlot(bool)
    async def on_net_online_status_changed(self, online_status: bool):
        if online_status:
            self.label_online_status.setText("以太网在线")
            self.badge_online_status.setLevel(InfoLevel.SUCCESS)
        else:
            self.label_online_status.setText("以太网离线")
            self.badge_online_status.setLevel(InfoLevel.ERROR)

    def eventFilter(self, obj, event):
        """事件过滤器，屏蔽spinbox的滚轮事件"""
        if obj == self.spinbox_speed and event.type() == QtCore.QEvent.Wheel:
            return True  # 拦截滚轮事件
        return super().eventFilter(obj, event)
