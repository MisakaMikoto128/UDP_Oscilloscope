# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QTableWidgetItem
from qasync import asyncSlot
from qfluentwidgets import MessageBox
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
from PyQt5.QtCore import QPoint, Qt

from src.communication.protocol import (
    SysREGsUpData,
)
from src.config.config_manager import ConfigManager
from src.ui import Device_Setting_From

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


class DeviceSettingFrom(QtWidgets.QFrame, Device_Setting_From):
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
        self.cfg = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        self.setObjectName("DeviceSettingFrom")


        # 设置按钮图标
        # self.btn_id_pid_i.setIcon(QIcon("./img/save2.svg"))

        # 初始化PID参数表格
        self._init_pid_table()

        # 连接按钮信号
        self._connect_pid_buttons()
        self.btn_save_param.clicked.connect(self._confirm_save_param)
        self.table_pid_param.cellDoubleClicked.connect(self._sync_pid_params_to_spinbox)

    def _init_pid_table(self):
        """初始化PID参数显示表格"""
        # 设置右键选中
        self.table_pid_param.setSelectRightClickedRow(True)

        # 设置表格样式
        self.table_pid_param.setBorderVisible(True)
        self.table_pid_param.setBorderRadius(8)
        self.table_pid_param.setWordWrap(False)

        # 设置表格尺寸
        self.table_pid_param.setRowCount(3)
        self.table_pid_param.setColumnCount(5)

        # 设置表头
        headers = ["PID环", "Kp", "Ki", "Kd", "Kd滤波"]
        self.table_pid_param.setHorizontalHeaderLabels(headers)
        self.table_pid_param.verticalHeader().hide()

        # 设置行标题
        row_labels = ["速度环", "Id环", "Iq环"]
        for i, label in enumerate(row_labels):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)  # 设置为不可编辑
            self.table_pid_param.setItem(i, 0, item)

        # 初始化空数据
        for i in range(3):
            for j in range(1, 5):
                item = QTableWidgetItem("0.00000")
                item.setFlags(
                    item.flags() & ~QtCore.Qt.ItemIsEditable
                )  # 设置为不可编辑
                item.setTextAlignment(QtCore.Qt.AlignCenter)  # 居中对齐
                self.table_pid_param.setItem(i, j, item)

        # 自适应列宽
        self.table_pid_param.horizontalHeader().setStretchLastSection(True)
        self.table_pid_param.resizeColumnsToContents()

    def _connect_pid_buttons(self):
        """连接所有 PID 设置按钮，并增加确认提示"""
        # 速度环
        self.btn_speed_pid_p.clicked.connect(
            lambda: self._confirm_and_set_pid(15, self.spinbox_speed_pid_p.value(), "速度环 Kp")
        )
        self.btn_speed_pid_i.clicked.connect(
            lambda: self._confirm_and_set_pid(16, self.spinbox_speed_pid_i.value(), "速度环 Ki")
        )

        # Id 环
        self.btn_id_pid_p.clicked.connect(
            lambda: self._confirm_and_set_pid(19, self.spinbox_id_pid_p.value(), "Id 环 Kp")
        )
        self.btn_id_pid_i.clicked.connect(
            lambda: self._confirm_and_set_pid(20, self.spinbox_id_pid_i.value(), "Id 环 Ki")
        )

        # Iq 环
        self.btn_iq_pid_p.clicked.connect(
            lambda: self._confirm_and_set_pid(23, self.spinbox_iq_pid_p.value(), "Iq 环 Kp")
        )
        self.btn_iq_pid_i.clicked.connect(
            lambda: self._confirm_and_set_pid(24, self.spinbox_iq_pid_i.value(), "Iq 环 Ki")
        )

    @asyncSlot()
    async def _set_pid_param(self, reg_addr: int, value: float, param_name: str):
        """设置PID参数"""
        try:
            # 转换为定点数
            param_set_int = int(value * 100000)
            target_addr = (self.cfg.target_host, self.cfg.target_port)

            # 发送设置指令
            success = await self.device_reg_set_func(
                reg_addr, [param_set_int], target_addr=target_addr
            )

            if success:
                InfoBar.success(
                    title='设置成功',
                    content=f'{param_name} 已成功设置为 {value:.5f}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                logger.info(f"PID参数设置成功: 地址{reg_addr}, 值{value}")
            else:
                InfoBar.error(
                    title='设置失败',
                    content=f'{param_name} 设置失败，请检查通信',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                logger.warning(f"PID参数设置失败: 地址{reg_addr}, 值{value}")

        except Exception as e:
            logger.error(f"设置PID参数错误: {e}")

    @asyncSlot()
    async def save_param_cmd(self):
        try:
            target_addr = (self.cfg.target_host, self.cfg.target_port)
            reg_addr = 105
            value = 0xA5
            # 发送设置指令
            success = await self.device_reg_set_func(
                reg_addr, [value], target_addr=target_addr
            )

            if success:
                InfoBar.success(
                    title='保存成功',
                    content='所有参数已成功写入设备 Flash',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                logger.info("参数保存成功")
            else:
                InfoBar.error(
                    title='保存失败',
                    content='参数保存失败，请检查通信',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                logger.warning("参数保存失败")
    
        except Exception as e:
            logger.error(f"设置PID参数错误: {e}")

    def _update_pid_table(
        self, speed_params: tuple, id_params: tuple, iq_params: tuple
    ):
        """更新PID参数表格显示"""
        try:
            # 速度环参数 (行0)
            for j, value in enumerate(speed_params):
                item = QTableWidgetItem(f"{value:.5f}")
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table_pid_param.setItem(0, j + 1, item)

            # Id环参数 (行1)
            for j, value in enumerate(id_params):
                item = QTableWidgetItem(f"{value:.5f}")
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table_pid_param.setItem(1, j + 1, item)

            # Iq环参数 (行2)
            for j, value in enumerate(iq_params):
                item = QTableWidgetItem(f"{value:.5f}")
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table_pid_param.setItem(2, j + 1, item)

        except Exception as e:
            logger.error(f"更新PID表格错误: {e}")

    @asyncSlot(SysREGsUpData)
    async def on_on_sys_regs_uploaded(self, sys_regs_up_data: SysREGsUpData):
        """处理系统寄存器上传数据"""
        try:
            fixed_point_scale = 100000

            # 速度环（Speed Loop）PID参数
            PID_Speed_Kp = uint32_to_int32(sys_regs_up_data.reg[15]) / fixed_point_scale
            PID_Speed_Ki = uint32_to_int32(sys_regs_up_data.reg[16]) / fixed_point_scale
            PID_Speed_Kd = uint32_to_int32(sys_regs_up_data.reg[17]) / fixed_point_scale
            PID_Speed_Kd_Filter = (
                uint32_to_int32(sys_regs_up_data.reg[18]) / fixed_point_scale
            )

            # Id环（Id Loop）PID参数
            PID_Id_Kp = uint32_to_int32(sys_regs_up_data.reg[19]) / fixed_point_scale
            PID_Id_Ki = uint32_to_int32(sys_regs_up_data.reg[20]) / fixed_point_scale
            PID_Id_Kd = uint32_to_int32(sys_regs_up_data.reg[21]) / fixed_point_scale
            PID_Id_Kd_Filter = (
                uint32_to_int32(sys_regs_up_data.reg[22]) / fixed_point_scale
            )

            # Iq环（Iq Loop）PID参数
            PID_Iq_Kp = uint32_to_int32(sys_regs_up_data.reg[23]) / fixed_point_scale
            PID_Iq_Ki = uint32_to_int32(sys_regs_up_data.reg[24]) / fixed_point_scale
            PID_Iq_Kd = uint32_to_int32(sys_regs_up_data.reg[25]) / fixed_point_scale
            PID_Iq_Kd_Filter = (
                uint32_to_int32(sys_regs_up_data.reg[26]) / fixed_point_scale
            )

            # 更新表格显示
            speed_params = (
                PID_Speed_Kp,
                PID_Speed_Ki,
                PID_Speed_Kd,
                PID_Speed_Kd_Filter,
            )
            id_params = (PID_Id_Kp, PID_Id_Ki, PID_Id_Kd, PID_Id_Kd_Filter)
            iq_params = (PID_Iq_Kp, PID_Iq_Ki, PID_Iq_Kd, PID_Iq_Kd_Filter)

            self._update_pid_table(speed_params, id_params, iq_params)

        except Exception as e:
            logger.error(f"解析数据错误: {e}")

    def _sync_pid_params_to_spinbox(self, row: int, column: int):
        try:
            params = []
            for col in range(1, 5):  # 第1~4列是参数
                item = self.table_pid_param.item(row, col)
                if item and item.text():
                    params.append(float(item.text()))
                else:
                    params.append(0.0)

            if row == 0:  # 速度环
                self.spinbox_speed_pid_p.setValue(params[0])
                self.spinbox_speed_pid_i.setValue(params[1])
                # 如果你有Kd和Kd滤波spinbox，也同步
            elif row == 1:  # Id环
                self.spinbox_id_pid_p.setValue(params[0])
                self.spinbox_id_pid_i.setValue(params[1])
            elif row == 2:  # Iq环
                self.spinbox_iq_pid_p.setValue(params[0])
                self.spinbox_iq_pid_i.setValue(params[1])
        except Exception as e:
            logger.error(f"同步PID参数到spinbox失败: {e}")


    def _confirm_and_set_pid(self, reg_addr: int, new_value: float, param_name: str):
        """
        弹出确认框，确认后真正发送 PID 设置指令
        :param reg_addr: 寄存器地址
        :param new_value: 要设置的值
        :param param_name: 参数中文名，用于提示框显示
        """
        title = "确认设置 PID 参数"
        content = f"{param_name} 参数将要从当前值设置为 {new_value:.5f}，请确认是否正确。\n确认后将立即发送设置命令！"

        box = MessageBox(title, content, self)
        if box.exec():
            # 用户点击“确认”
            self._set_pid_param(reg_addr, new_value, param_name)

    def _confirm_save_param(self):
        title = "确认保存参数"
        content = "即将把所有当前参数写入设备 Flash 永久保存，请确认是否继续？"

        box = MessageBox(title, content, self)
        if box.exec():
            self.save_param_cmd()

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            logger.info("DeviceSettingFrom开始关闭")

            # 取消所有正在运行的异步任务
            # DeviceSettingFrom主要是按钮触发的异步操作，通常在关闭时已完成

            logger.info("DeviceSettingFrom正常退出")
            event.accept()

        except Exception as e:
            logger.error(f"关闭DeviceSettingFrom时出错: {e}")
            event.accept()