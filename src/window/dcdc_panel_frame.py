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
from src.ui import Dcdc_Panel_Form

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("dcdc_panel_frame.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def uint32_to_int32(value: int) -> int:
    """将无符号32位整数转换为有符号32位整数"""
    if value >= 0x80000000:  # 2^31
        return value - 0x100000000  # 2^32
    return value


class DcdcPanelForm(QtWidgets.QFrame, Dcdc_Panel_Form):
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
        self.cfg = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        self.setObjectName("DcdcPanelForm")

        # 初始化DCDC参数监控组件
        self._init_dcdc_param_table()
        self._init_dcdc_fault_table()

    def _init_dcdc_param_table(self):
        """初始化DCDC参数显示表格"""
        # 设置右键选中
        self.table_dcdc_param.setSelectRightClickedRow(True)

        # 设置表格样式
        self.table_dcdc_param.setBorderVisible(True)
        self.table_dcdc_param.setBorderRadius(8)
        self.table_dcdc_param.setWordWrap(False)

        # 设置表格尺寸
        self.table_dcdc_param.setRowCount(4)
        self.table_dcdc_param.setColumnCount(2)

        # 设置表头
        headers = ["参数名称", "数值"]
        self.table_dcdc_param.setHorizontalHeaderLabels(headers)
        self.table_dcdc_param.verticalHeader().hide()

        # 设置行标题和初始化数据
        dcdc_params = [
            ["电压 (V)", "0.00"],
            ["电流 (A)", "0.00"],
            ["温度 (°C)", "0.00"],
            ["设置状态", "0"]
        ]
        
        for i, (param_name, initial_value) in enumerate(dcdc_params):
            # 参数名称
            name_item = QTableWidgetItem(param_name)
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            name_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_param.setItem(i, 0, name_item)
            
            # 参数值
            value_item = QTableWidgetItem(initial_value)
            value_item.setFlags(value_item.flags() & ~QtCore.Qt.ItemIsEditable)
            value_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_param.setItem(i, 1, value_item)

        # 自适应列宽
        self.table_dcdc_param.horizontalHeader().setStretchLastSection(True)
        self.table_dcdc_param.resizeColumnsToContents()

    def _init_dcdc_fault_table(self):
        """初始化DCDC故障显示表格"""
        # 设置右键选中
        self.table_dcdc_fault.setSelectRightClickedRow(True)

        # 设置表格样式
        self.table_dcdc_fault.setBorderVisible(True)
        self.table_dcdc_fault.setBorderRadius(8)
        self.table_dcdc_fault.setWordWrap(False)

        # 根据下位机故障位定义初始化故障表格
        fault_definitions = [
            # byte0
            ["VResCVolHOverRating", "储能电容高压过压"],
            ["VResCVolLOverRating", "储能电容低压过压"],
            ["VinOverRating", "输入电压过压"],
            ["VinUnderRating", "输入电压欠压"],
            ["Sps12VOverRating", "12V电源过压"],
            ["DCoutForbid", "直流输出禁止"],
            ["CanVoltOverLim", "CAN电压过限"],
            ["CanVoltCurrLim", "CAN电压电流限制"],
            # byte1
            ["VoutOverRating", "输出电压过压"],
            ["VoutUnderRating", "输出电压欠压"],
            ["VinMidOverRating", "输入中点电压过压"],
            ["VinMidUnderRatig", "输入中点电压欠压"],
            ["VinUnBalance", "输入电压不平衡"],
            ["Sps12VUnderRating", "12V电源欠压"],
            ["AirTempOver", "环境温度过高"],
            ["OVP_Vout_Fast", "输出过压快速保护"],
            # byte2
            ["IinOCPWarning", "输入过流警告"],
            ["IoutOcpWarning", "输出过流警告"],
            ["LLCOFP", "LLC开路故障"],
            ["Reserver15", "保留15"],
            ["Reserver16", "保留16"],
            ["Reserver17", "保留17"],
            ["Reserver18", "保留18"],
            ["Reserver19", "保留19"],
            # Unreserve
            ["ShortFlag", "短路标志"],
            ["IoutOcp", "输出过流"],
            ["IinOcp", "输入过流"],
            ["Reserved22", "保留22"],
            ["Reserved23", "保留23"],
            ["Reserved24", "保留24"],
            ["Reserved25", "保留25"],
            ["Reserved26", "保留26"],
        ]

        # 设置表格尺寸
        self.table_dcdc_fault.setRowCount(len(fault_definitions))
        self.table_dcdc_fault.setColumnCount(3)

        # 设置表头
        headers = ["故障位", "故障描述", "状态"]
        self.table_dcdc_fault.setHorizontalHeaderLabels(headers)
        self.table_dcdc_fault.verticalHeader().hide()

        # 初始化故障表格数据
        for i, (fault_name, fault_desc) in enumerate(fault_definitions):
            # 故障位名称
            name_item = QTableWidgetItem(fault_name)
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            name_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_fault.setItem(i, 0, name_item)

            # 故障描述
            desc_item = QTableWidgetItem(fault_desc)
            desc_item.setFlags(desc_item.flags() & ~QtCore.Qt.ItemIsEditable)
            desc_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_fault.setItem(i, 1, desc_item)

            # 故障状态
            status_item = QTableWidgetItem("正常")
            status_item.setFlags(status_item.flags() & ~QtCore.Qt.ItemIsEditable)
            status_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_fault.setItem(i, 2, status_item)

        # 自适应列宽
        self.table_dcdc_fault.horizontalHeader().setStretchLastSection(True)
        self.table_dcdc_fault.resizeColumnsToContents()

    def _update_dcdc_param_table(self, voltage: float, current: float, temperature: float, set_state: int):
        """更新DCDC参数表格显示"""
        try:
            # 更新电压
            voltage_item = QTableWidgetItem(f"{voltage:.2f}")
            voltage_item.setFlags(voltage_item.flags() & ~QtCore.Qt.ItemIsEditable)
            voltage_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_param.setItem(0, 1, voltage_item)

            # 更新电流
            current_item = QTableWidgetItem(f"{current:.2f}")
            current_item.setFlags(current_item.flags() & ~QtCore.Qt.ItemIsEditable)
            current_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_param.setItem(1, 1, current_item)

            # 更新温度
            temp_item = QTableWidgetItem(f"{temperature:.2f}")
            temp_item.setFlags(temp_item.flags() & ~QtCore.Qt.ItemIsEditable)
            temp_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_param.setItem(2, 1, temp_item)

            # 更新设置状态
            state_item = QTableWidgetItem(f"{set_state}")
            state_item.setFlags(state_item.flags() & ~QtCore.Qt.ItemIsEditable)
            state_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table_dcdc_param.setItem(3, 1, state_item)

        except Exception as e:
            logger.error(f"更新DCDC参数表格错误: {e}")

    def _update_dcdc_fault_table(self, fault_value: int):
        """更新DCDC故障表格显示"""
        try:
            # 故障位定义（按照下位机代码中的位顺序）
            fault_bits = []
            for i in range(32):
                fault_bits.append((fault_value >> i) & 1)

            # 更新故障状态显示
            for i, fault_bit in enumerate(fault_bits):
                if i < self.table_dcdc_fault.rowCount():
                    status_text = "故障" if fault_bit else "正常"
                    status_item = QTableWidgetItem(status_text)
                    status_item.setFlags(status_item.flags() & ~QtCore.Qt.ItemIsEditable)
                    status_item.setTextAlignment(QtCore.Qt.AlignCenter)

                    # 设置颜色：故障为红色，正常为绿色
                    if fault_bit:
                        status_item.setBackground(QtCore.Qt.red)
                        status_item.setForeground(QtCore.Qt.white)
                    else:
                        status_item.setBackground(QtCore.Qt.green)
                        status_item.setForeground(QtCore.Qt.white)

                    self.table_dcdc_fault.setItem(i, 2, status_item)

        except Exception as e:
            logger.error(f"更新DCDC故障表格错误: {e}")

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

    def infobar(
        self,
        ret,
        title: str,
        success_content: str,
        error_content: str,
        orient: Qt.Orientation = Qt.Horizontal,
        isClosable: bool = True,
        position: InfoBarPosition = InfoBarPosition.TOP,
        success_duration: int = 2000,
        error_duration: int = 2000,
    ):
        if ret:
            InfoBar.success(
                title=title,
                content=success_content,
                orient=orient,
                isClosable=isClosable,
                position=position,
                duration=success_duration,
                parent=self,
            )
            logger.info(success_content)
        else:
            InfoBar.error(
                title=title,
                content=error_content,
                orient=orient,
                isClosable=isClosable,
                position=position,
                duration=error_duration,
                parent=self,
            )
            logger.error(error_content)
