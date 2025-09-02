# -*- coding: utf-8 -*-
import logging
from typing import Callable, List

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui
from qasync import asyncClose,asyncSlot

from src.communication.protocol import (
    SysREGsUpData,
)
from src.communication.udp_master import UDPMaster
from src.config.config_manager import ConfigManager
from src.data.data_buffer import RingBuffer
from src.ui import Ctrl_Panel_Form


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


class CtrlPanelForm(QtWidgets.QFrame, Ctrl_Panel_Form):
    """主窗口类"""

    def __init__(self, cfg: ConfigManager,
                 config_file_path: str,
                 device_reg_set_func: Callable[[int, List[int]], bool],
                 parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)
        # 配置管理器
        self.cfg = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func

        self.test_show()

    def test_show(self):
        sys_regs_up_data = SysREGsUpData(
            packet_type=1,
            reg_num=200,
            reg=[1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450, 1023450,
                 ]
        )
        self.on_on_sys_regs_uploaded(sys_regs_up_data)

    # @asyncSlot
    def on_on_sys_regs_uploaded(self,sys_regs_up_data: SysREGsUpData):
        try:
            fixed_point_scale = 100000
            MCV_mSpeed = sys_regs_up_data.reg[83] / fixed_point_scale
            MCV_angle = sys_regs_up_data.reg[83] / fixed_point_scale
            MCV_duty_cycle = sys_regs_up_data.reg[83] / fixed_point_scale
            MCV_temperature = sys_regs_up_data.reg[83] / fixed_point_scale
            self.label_speed.setText(f"速度：    {MCV_mSpeed:>7.1f}")
            self.label_angle.setText(f"角度：    {MCV_angle:>7.1f}")
            self.label_duty_cycle.setText(f"占空比：  {MCV_duty_cycle:>7.2f}")
            self.label_temperature.setText(f"温度：    {MCV_temperature:>7.2f}")
            flag1_int32 = sys_regs_up_data.reg[90]
            flag1_uint32 = flag1_int32 & 0xFFFFFFFF
            flag1_uint32 = 0x80000001  # 示例值
            self.update_fault_status(flag1_uint32)

        except Exception as e:
            logger.info(f"解析数据错误{e}")

    @staticmethod
    def parse_flag1(flag1_uint32):
        # 定义状态位的掩码和描述
        ocflt_bits = [
            ("OC_PhaseC_Hard", 1 << 24),  # C相硬件过流
            ("OC_PhaseB_Hard", 1 << 25),  # B相硬件过流
            ("OC_PhaseA_Hard", 1 << 26),  # A相硬件过流
            ("OC_IBus_Hard", 1 << 27),  # 母线硬件过流
            ("OC_PhaseC_Soft", 1 << 28),  # C相软件过流
            ("OC_PhaseB_Soft", 1 << 29),  # B相软件过流
            ("OC_PhaseA_Soft", 1 << 30),  # A相软件过流
            ("OC_IBus_Soft", 1 << 31),  # 母线软件过流
        ]

        sysstatus_bits = [
            ("SelfCheck_FLT", 1 << 16),  # 自检异常
            ("Phase_FLT", 1 << 17),  # 缺相
            ("MOT_OT", 1 << 18),  # 电机过热
            ("INV_OT", 1 << 19),  # 逆变器过温
            ("IGBT_FLT", 1 << 20),  # 功率器件保护
            ("Bus_UV", 1 << 21),  # 母线欠压
            ("Bus_OV", 1 << 22),  # 母线过压
            ("INV_OC", 1 << 23),  # 逆变器过流
        ]

        invstatus_bits = [
            ("Ib_Err", 1 << 8),  # Ib_Err
            ("Ia_Err", 1 << 9),  # Ia_Err
            ("Ibus_Err", 1 << 10),  # Ibus_Err
            ("Vbus_Err", 1 << 11),  # Vbus_Err
            ("NTC4_Err", 1 << 12),  # NTC4_Err
            ("NTC3_Err", 1 << 13),  # NTC3_Err
            ("NTC2_Err", 1 << 14),  # NTC2_Err
            ("NTC1_Err", 1 << 15),  # NTC1_Err
        ]

        motstatus_bits = [
            ("Sensor_FLT", 1 << 0),  # 位置传感器异常
            ("OVSpeed", 1 << 1),  # 内部超速
            ("CPLD_FLT", 1 << 2),  # CPLD_FLT
            ("FLT4_Flag", 1 << 3),  # FLT4_Flag
            ("FLT3_Flag", 1 << 4),  # FLT3_Flag
            ("FLT2_Flag", 1 << 5),  # FLT2_Flag
            ("FLT1_Flag", 1 << 6),  # FLT1_Flag
            ("Ic_Err", 1 << 7),  # Ic_Err
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
        lines = []
        for category, status in flag1.items():
            if status:
                lines.append(f"{category}: {', '.join(status)}")
            else:
                lines.append(f"{category}: 无故障")

        # 设置 QLabel 的文本
        self.label_fault_status.setText("\n".join(lines))
