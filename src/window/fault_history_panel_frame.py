# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QTableWidgetItem
from qasync import asyncSlot
from qfluentwidgets import InfoBar, InfoBarPosition
from PyQt5.QtCore import Qt

from src.communication.protocol import SysREGsUpData
from src.config.config_manager import ConfigManager
from src.ui import History_Panel_Form

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("fault_history_panel_frame.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def uint32_to_int32(value: int) -> int:
    """将无符号32位整数转换为有符号32位整数"""
    if value >= 0x80000000:  # 2^31
        return value - 0x100000000  # 2^32
    return value


class FaultHistoryPanelForm(QtWidgets.QFrame, History_Panel_Form):
    """DCDC状态监控窗口类"""

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
        self.cfg:ConfigManager = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        self.setObjectName("FaultHistoryPanelForm")

        # 初始化combo_box_devices
        
    @asyncSlot(SysREGsUpData)
    async def on_on_sys_regs_uploaded(self, sys_regs_up_data: SysREGsUpData):
        """处理系统寄存器上传数据"""
        try:
            fixed_point_scale = 100000

            # 根据下位机代码解析DCDC数据
            # APP_Net_WriteReg(addr++, g_dcdc_info.u32_fault); // 93
            # APP_Net_WriteReg(addr++, FLOAT_TO_U32_FIXED_POINT(g_dcdc_info.f32_volt_V)); // 94
            # APP_Net_WriteReg(addr++, FLOAT_TO_U32_FIXED_POINT(g_dcdc_info.f32_curr_A)); // 95
            # APP_Net_WriteReg(addr++, FLOAT_TO_U32_FIXED_POINT(g_dcdc_info.f32_temperature)); // 96
            # APP_Net_WriteReg(addr++, (uint32_t)dcdc_set_state); // 97

            if len(sys_regs_up_data.reg) > 97:
                # 解析DCDC参数
                dcdc_fault = sys_regs_up_data.reg[93]  # 故障信息
                dcdc_voltage = uint32_to_int32(sys_regs_up_data.reg[94]) / fixed_point_scale  # 电压
                dcdc_current = uint32_to_int32(sys_regs_up_data.reg[95]) / fixed_point_scale  # 电流
                dcdc_temperature = uint32_to_int32(sys_regs_up_data.reg[96]) / fixed_point_scale  # 温度
                dcdc_set_state = sys_regs_up_data.reg[97]  # 设置状态

                # 更新DCDC参数表格
                self._update_dcdc_param_table(dcdc_voltage, dcdc_current, dcdc_temperature, dcdc_set_state)

                # 更新DCDC故障表格
                self._update_dcdc_fault_table(dcdc_fault)

        except Exception as e:
            logger.error(f"解析数据错误: {e}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            logger.info("DcdcPanelForm正常退出")
            event.accept()
        except Exception as e:
            logger.error(f"关闭DcdcPanelForm时出错: {e}")
            event.accept()

    