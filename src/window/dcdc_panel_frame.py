# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QTableWidgetItem
from qasync import asyncSlot
from src.ui.async_message_box import async_confirm
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

        # 初始化DCDC参数监控组件
        self._init_dcdc_param_table()
        self._init_dcdc_fault_table()

    def _init_dcdc_param_table(self):
        """初始化PID参数显示表格"""
        # 设置右键选中
        self.table_dcdc_param.setSelectRightClickedRow(True)

        # 设置表格样式
        self.table_dcdc_param.setBorderVisible(True)
        self.table_dcdc_param.setBorderRadius(8)
        self.table_dcdc_param.setWordWrap(False)

        # 设置表格尺寸
        self.table_dcdc_param.setRowCount(3)
        self.table_dcdc_param.setColumnCount(5)

        # 设置表头
        headers = ["PID环", "Kp", "Ki", "Kd", "Kd滤波"]
        self.table_dcdc_param.setHorizontalHeaderLabels(headers)
        self.table_dcdc_param.verticalHeader().hide()

        # 设置行标题
        row_labels = ["速度环", "Id环", "Iq环"]
        for i, label in enumerate(row_labels):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)  # 设置为不可编辑
            self.table_dcdc_param.setItem(i, 0, item)

        # 初始化空数据
        for i in range(3):
            for j in range(1, 5):
                item = QTableWidgetItem("0.00000")
                item.setFlags(
                    item.flags() & ~QtCore.Qt.ItemIsEditable
                )  # 设置为不可编辑
                item.setTextAlignment(QtCore.Qt.AlignCenter)  # 居中对齐
                self.table_dcdc_param.setItem(i, j, item)

        # 自适应列宽
        self.table_dcdc_param.horizontalHeader().setStretchLastSection(True)
        self.table_dcdc_param.resizeColumnsToContents()

    def _init_dcdc_fault_table(self):
        """初始化其他参数显示表格"""
        # 初始化空数据
        headers = ["变量名称", "变量别名", "值"]
        other_params = [
            ["Motor_Rs", "-", "0.00000"],
            ["Motor_Pn", "机对数", "0.00000"],
            ["Vdcset_ref", "母线电压", "0.00000"],
            ["Iset_d_ref", "d轴电流", "0.00000"],
            ["Motor_Resolver_Zero", "校准值", "0.00000"],
            ["Motor_RpstoRpm_COEF", "-", "0.00000"],
            ["Rottx_Zero_Current", "旋变零点电流", "0.00000"],
            ["mEtheta", "角度", "0.00000"],
            ["mEtheta1", "角度", "0.00000"],
            ["mEthetaAVG", "平均角度", "0.00000"],
            ["mEthetaRad", "角度弧度", "0.00000"],
            ["mEthetaZero", "零点角度", "0.00000"],
            ["Motor_Id_Max", "Id上限", "0.00000"],
            ["Motor_Id_Min", "Id下限", "0.00000"],
            ["ResovlerFault", "旋变故障", "0"],
            ["Iset_q_ref", "q轴电流", "0.00000"],
            ["Idref", "d轴电流参考值", "0.00000"],
            ["Iqref", "q轴电流参考值", "0.00000"],
            ["Te_set_ref", "电磁转矩设定", "0.00000"],
            ["Motor_Flux", "电机磁链", "0.00000"],
            ["inv_Kt", "转矩常数倒数", "0.00000"],
        ]

        # 设置右键选中
        self.table_other_param.setSelectRightClickedRow(True)

        # 设置表格样式
        self.table_other_param.setBorderVisible(True)
        self.table_other_param.setBorderRadius(8)
        self.table_other_param.setWordWrap(False)

        # 设置表格尺寸
        self.table_other_param.setRowCount(len(other_params))
        self.table_other_param.setColumnCount(3)

        # 设置表头
        self.table_other_param.setHorizontalHeaderLabels(headers)
        self.table_other_param.verticalHeader().hide()

        self._update_other_table(other_params)

        # 自适应列宽
        self.table_other_param.horizontalHeader().setStretchLastSection(True)
        self.table_other_param.resizeColumnsToContents()

    def _connect_pid_buttons(self):
        """连接所有 PID 设置按钮，并增加确认提示"""
        # 速度环
        self.btn_speed_pid_p.clicked.connect(
            lambda: self._confirm_and_set_pid(
                15, self.spinbox_speed_pid_p.value(), "速度环 Kp"
            )
        )
        self.btn_speed_pid_i.clicked.connect(
            lambda: self._confirm_and_set_pid(
                16, self.spinbox_speed_pid_i.value(), "速度环 Ki"
            )
        )

        # Id 环
        self.btn_id_pid_p.clicked.connect(
            lambda: self._confirm_and_set_pid(
                19, self.spinbox_id_pid_p.value(), "Id 环 Kp"
            )
        )
        self.btn_id_pid_i.clicked.connect(
            lambda: self._confirm_and_set_pid(
                20, self.spinbox_id_pid_i.value(), "Id 环 Ki"
            )
        )

        # Iq 环
        self.btn_iq_pid_p.clicked.connect(
            lambda: self._confirm_and_set_pid(
                23, self.spinbox_iq_pid_p.value(), "Iq 环 Kp"
            )
        )
        self.btn_iq_pid_i.clicked.connect(
            lambda: self._confirm_and_set_pid(
                24, self.spinbox_iq_pid_i.value(), "Iq 环 Ki"
            )
        )

    def _connect_other_param_buttons(self):
        """连接其他参数设置按钮，并增加确认提示"""
        # Rottx_Zero_Current - 旋变零点电流
        self.btn_Rottx_Zero_Current.clicked.connect(
            lambda: self._confirm_and_set_param(
                14, self.spinbox_Rottx_Zero_Current.value(), "旋变零点电流"
            )
        )

        # Motor_Resolver_Zero - 旋变零点
        self.btn_Motor_Resolver_Zero.clicked.connect(
            lambda: self._confirm_and_set_param(
                48, self.spinbox_Motor_Resolver_Zero.value(), "旋变零点"
            )
        )

        # Motor_Pn - 电机极对数
        self.btn_Motor_Pn.clicked.connect(
            lambda: self._confirm_and_set_param(
                46, self.spinbox_Motor_Pn.value(), "电机极对数"
            )
        )

        # 新增的参数按钮连接
        # Motor_Id_Max - 电机Id上限
        self.btn_Motor_Id_Max.clicked.connect(
            lambda: self._confirm_and_set_param(
                33, self.spinbox_Motor_Id_Max.value(), "电机Id上限"
            )
        )

        # Motor_Id_Min - 电机Id下限
        self.btn_Motor_Id_Min.clicked.connect(
            lambda: self._confirm_and_set_param(
                34, self.spinbox_Motor_Id_Min.value(), "电机Id下限"
            )
        )

        # Idref - d轴电流参考值
        self.btn_Idref.clicked.connect(
            lambda: self._confirm_and_set_param(
                31, self.spinbox_Idref.value(), "d轴电流参考值"
            )
        )

        # Iqref - q轴电流参考值
        self.btn_Iqref.clicked.connect(
            lambda: self._confirm_and_set_param(
                32, self.spinbox_Iqref.value(), "q轴电流参考值"
            )
        )

        # Vdcset_ref - 母线电压设置参考值
        self.btn_Vdcset_ref.clicked.connect(
            lambda: self._confirm_and_set_param(
                8, self.spinbox_Vdcset_ref.value(), "母线电压设置参考值", "uint16"
            )
        )

        # Iset_d_ref - d轴电流参考值
        self.btn_Iset_d_ref.clicked.connect(
            lambda: self._confirm_and_set_param(
                9, self.spinbox_Iset_d_ref.value(), "d轴电流参考值", "uint16"
            )
        )

    @asyncSlot()
    async def _set_param(
        self, reg_addr: int, value: float, param_name: str, value_type: str = "float32"
    ):
        """设置参数的通用函数"""
        try:
            # 根据寄存器地址确定数据类型和转换方式
            # 地址8和9是Uint16类型，直接发送整数值
            # 其他地址是float类型，需要转换为定点数
            if value_type == "uint16":
                param_set_int = int(value)
            elif value_type == "float32":
                param_set_int = int(value * 100000)

            target_addr = (self.cfg.target_host, self.cfg.target_port)

            # 发送设置指令
            success = await self.device_reg_set_func(
                reg_addr, [param_set_int], target_addr=target_addr
            )
            self.infobar(
                success,
                "设置参数结果",
                f"{param_name} 已成功设置为 {value:.5f}",
                f"{param_name} 设置失败，请检查通信",
            )

        except Exception as e:
            logger.error(f"设置参数错误: {e}")

    @asyncSlot()
    async def _set_pid_param(self, reg_addr: int, value: float, param_name: str):
        """设置PID参数（保持向后兼容）"""
        await self._set_param(reg_addr, value, param_name)

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
            self.infobar(
                success,
                title="保存参数结果",
                success_content="所有参数已成功写入设备 Flash",
                error_content="参数保存命令发送超时，请检查通信！",
            )
        except Exception as e:
            logger.error(f"设置PID参数错误: {e}")

    @asyncSlot()
    async def launch_zero_calibration_cmd(self):
        try:
            target_addr = (self.cfg.target_host, self.cfg.target_port)
            reg_addr = 105
            value = 0x1C
            # 发送设置指令
            success = await self.device_reg_set_func(
                reg_addr, [value], target_addr=target_addr
            )
            self.infobar(
                success,
                title="校准启动结果",
                success_content="控制板收到校准命令！",
                error_content="校准启动命令发送超时！",
            )

        except Exception as e:
            logger.error(f"校准启动错误: {e}")

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
                self.table_dcdc_param.setItem(0, j + 1, item)

            # Id环参数 (行1)
            for j, value in enumerate(id_params):
                item = QTableWidgetItem(f"{value:.5f}")
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table_dcdc_param.setItem(1, j + 1, item)

            # Iq环参数 (行2)
            for j, value in enumerate(iq_params):
                item = QTableWidgetItem(f"{value:.5f}")
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table_dcdc_param.setItem(2, j + 1, item)

        except Exception as e:
            logger.error(f"更新PID表格错误: {e}")

    def _update_other_table(self, other_params: list):
        """更新其他参数表格显示"""
        try:
            for i, songInfo in enumerate(other_params):
                for j in range(3):
                    item = QTableWidgetItem(songInfo[j])
                    item.setFlags(
                        item.flags() & ~QtCore.Qt.ItemIsEditable
                    )  # 设置为不可编辑
                    item.setTextAlignment(QtCore.Qt.AlignCenter)  # 居中对齐
                    self.table_other_param.setItem(i, j, item)

        except Exception as e:
            logger.error(f"更新其他表格错误: {e}")

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

            # 其他参数解析
            """
            根据下位机代码的寄存器映射：
            [27] = &mVar_RAM.Motor_Parameters.Motor_Rs,
            [28] = &mVar_RAM.Motor_Parameters.Motor_Pn,
            [29] = &mVar_RAM.Motor_Parameters.Motor_Resolver_Zero,
            [30] = &mVar_RAM.Motor_Parameters.Motor_RpstoRpm_COEF,
            [31] = &Idref,
            [32] = &Iqref,
            [33] = &mVar_RAM.Motor_Limits.Motor_Id_Max,
            [34] = &mVar_RAM.Motor_Limits.Motor_Id_Min,
            APP_Net_WriteReg(addr++, Vdcset_ref);//8
            APP_Net_WriteReg(addr++, Iset_d_ref);//9
            APP_Net_WriteReg(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEtheta1));                                  // 62
            APP_Net_WriteReg(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEtheta));                                   // 80
            APP_Net_WriteReg(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEthetaZero));                               // 81
            APP_Net_WriteReg(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEthetaAVG));                                // 82
            APP_Net_WriteReg(addr++, MCV.ResovlerFault);                                                        // 91
            APP_Net_WriteReg(addr++, MCV.mEthetaRad);                                                           // 92
            """
            Motor_Rs = uint32_to_int32(sys_regs_up_data.reg[27]) / fixed_point_scale
            Motor_Pn = uint32_to_int32(sys_regs_up_data.reg[28]) / fixed_point_scale
            Motor_Resolver_Zero = (
                uint32_to_int32(sys_regs_up_data.reg[29]) / fixed_point_scale
            )
            Motor_RpstoRpm_COEF = (
                uint32_to_int32(sys_regs_up_data.reg[30]) / fixed_point_scale
            )
            Rottx_Zero_Current = (
                uint32_to_int32(sys_regs_up_data.reg[14]) / fixed_point_scale
            )

            # 新增的参数解析
            # 地址8和9是Uint16类型，直接使用
            Vdcset_ref = sys_regs_up_data.reg[8]  # Uint16类型
            Iset_d_ref = sys_regs_up_data.reg[9]  # Uint16类型

            # 地址31-34是float类型，需要定点数转换
            Idref = uint32_to_int32(sys_regs_up_data.reg[31]) / fixed_point_scale
            Iqref = uint32_to_int32(sys_regs_up_data.reg[32]) / fixed_point_scale
            Motor_Id_Max = uint32_to_int32(sys_regs_up_data.reg[33]) / fixed_point_scale
            Motor_Id_Min = uint32_to_int32(sys_regs_up_data.reg[34]) / fixed_point_scale

            # 旋变相关参数
            mEtheta1 = uint32_to_int32(sys_regs_up_data.reg[62]) / fixed_point_scale
            mEtheta = uint32_to_int32(sys_regs_up_data.reg[80]) / fixed_point_scale
            mEthetaZero = uint32_to_int32(sys_regs_up_data.reg[81]) / fixed_point_scale
            mEthetaAVG = uint32_to_int32(sys_regs_up_data.reg[82]) / fixed_point_scale
            ResovlerFault = sys_regs_up_data.reg[
                91
            ]  # 这个是整数，不需要除以fixed_point_scale
            mEthetaRad = uint32_to_int32(sys_regs_up_data.reg[92]) / fixed_point_scale
            Iset_q_ref = uint32_to_int32(sys_regs_up_data.reg[38]) / fixed_point_scale
            Te_set_ref = uint32_to_int32(sys_regs_up_data.reg[39]) / fixed_point_scale
            Motor_Flux = uint32_to_int32(sys_regs_up_data.reg[44]) / fixed_point_scale
            inv_Kt = uint32_to_int32(sys_regs_up_data.reg[45]) / fixed_point_scale

            # 添加表格数据
            other_params = [
                ["Motor_Rs", "-", f"{Motor_Rs:.5f}"],
                ["Motor_Pn", "机对数", f"{Motor_Pn:.5f}"],
                ["Vdcset_ref", "母线电压", f"{Vdcset_ref}"],
                ["Iset_d_ref", "d轴电流", f"{Iset_d_ref}"],
                ["Motor_Resolver_Zero", "校准值", f"{Motor_Resolver_Zero:.5f}"],
                ["Motor_RpstoRpm_COEF", "-", f"{Motor_RpstoRpm_COEF:.5f}"],
                ["Rottx_Zero_Current", "旋变零点电流", f"{Rottx_Zero_Current:.5f}"],
                ["mEtheta", "角度", f"{mEtheta:.5f}"],
                ["mEtheta1", "角度", f"{mEtheta1:.5f}"],
                ["mEthetaAVG", "平均角度", f"{mEthetaAVG:.5f}"],
                ["mEthetaRad", "角度弧度", f"{mEthetaRad:.5f}"],
                ["mEthetaZero", "零点角度", f"{mEthetaZero:.5f}"],
                ["Motor_Id_Max", "Id上限", f"{Motor_Id_Max:.5f}"],
                ["Motor_Id_Min", "Id下限", f"{Motor_Id_Min:.5f}"],
                ["ResovlerFault", "旋变故障", f"{ResovlerFault}"],
                ["Iset_q_ref", "q轴电流", f"{Iset_q_ref:.5f}"],
                ["Idref", "d轴电流参考值", f"{Idref:.5f}"],
                ["Iqref", "q轴电流参考值", f"{Iqref:.5f}"],
                ["Te_set_ref", "电磁转矩设定", f"{Te_set_ref:.5f}"],
                ["Motor_Flux", "电机磁链", f"{Motor_Flux:.5f}"],
                ["inv_Kt", "转矩常数倒数", f"{inv_Kt:.5f}"],
            ]
            self._update_other_table(other_params)

            # 系统模式
            """
            union _SYS_MODE_REG {
                Uint32 all;
                struct  _SYS_MODE_REG_BITS bit;
            };
            union _SYS_MODE_REG sys_mode_reg;
            sys_mode_reg.bit.Reserved = 0;
            sys_mode_reg.bit.RotTX_ZeroEN_FLG = RotTX_ZeroEN_FLG;
            sys_mode_reg.bit.SYS_OpertionMode = SYS_OpertionMode;
            APP_Net_WriteReg(addr++, sys_mode_reg.all);    
            Uint16 RotTX_ZeroEN_FLG = 0; // 0:当前未启动旋变校准,1:当前已启动旋变校准
            Uint16 SYS_OpertionMode = 2; // 模式---1----电流环模式，2---速度环模式, 0---其他                                                    // 85
            """
            SYS_OpertionMode = sys_regs_up_data.reg[85] & 0x07
            RotTX_ZeroEN_FLG = (sys_regs_up_data.reg[85] >> 3) & 0x01
            SYS_OpertionMode_dict = {1: "电流环模式", 2: "速度环模式", 0: "其他模式"}
            RotTX_ZeroEN_FLG_dict = {0: "未启动", 1: "已启动"}
            self.label_speed_ctrl_mode_select.setText(
                f"当前为{SYS_OpertionMode_dict.get(SYS_OpertionMode, '其他模式')}"
            )
            self.label_start_resolver_calibration.setText(
                f"当前{RotTX_ZeroEN_FLG_dict.get(RotTX_ZeroEN_FLG, '未知状态')}旋变校准"
            )
            self.btn_ctrl_mode_select.setChecked(SYS_OpertionMode == 1)

        except Exception as e:
            logger.error(f"解析数据错误: {e}")

    def _sync_pid_params_to_spinbox(self, row: int, column: int):
        """双击PID表格同步参数到spinbox"""
        try:
            params = []
            for col in range(1, 5):  # 第1~4列是参数
                item = self.table_dcdc_param.item(row, col)
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

    def _sync_other_params_to_spinbox(self, row: int, column: int):
        """双击其他参数表格同步参数到spinbox"""
        try:
            # 获取第3列（值列）的数据
            item = self.table_other_param.item(row, 2)
            if not item or not item.text():
                return

            # 根据行号确定对应的spinbox
            # 表格行顺序：
            # 0: Motor_Rs, 1: Motor_Pn, 2: Vdcset_ref, 3: Iset_d_ref, 5: Motor_Resolver_Zero, 6: Motor_RpstoRpm_COEF,
            # 7: Rottx_Zero_Current, 8: mEtheta, 9: mEtheta1, 10: mEthetaAVG, 8: mEthetaRad,
            # 11: mEthetaZero, 12: Motor_Id_Max, 13: Motor_Id_Min, 14: ResovlerFault

            # 对于ResovlerFault（整数类型），特殊处理
            if row == 12:  # ResovlerFault
                value = int(item.text())
                # ResovlerFault没有对应的spinbox，只显示不可编辑
                return
            else:
                value = float(item.text())

            # 同步到对应的spinbox（只有可编辑的参数才有spinbox）
            if row == 1:  # Motor_Pn
                self.spinbox_Motor_Pn.setValue(value)
            elif row == 2:  # Vdcset_ref
                self.spinbox_Vdcset_ref.setValue(value)
            elif row == 3:  # Iset_d_ref
                self.spinbox_Iset_d_ref.setValue(value)
            elif row == 4:  # Motor_Resolver_Zero
                self.spinbox_Motor_Resolver_Zero.setValue(value)
            elif row == 5:  # Rottx_Zero_Current
                self.spinbox_Rottx_Zero_Current.setValue(value)
            elif row == 12:  # Motor_Id_Max
                self.spinbox_Motor_Id_Max.setValue(value)
            elif row == 13:  # Motor_Id_Min
                self.spinbox_Motor_Id_Min.setValue(value)
            # 注意：mEtheta相关参数是只读的，不需要同步到spinbox

        except Exception as e:
            logger.error(f"同步其他参数到spinbox失败: {e}")

    @asyncSlot()
    async def _confirm_and_set_param(
        self,
        reg_addr: int,
        new_value: float,
        param_name: str,
        value_type: str = "float32",
    ):
        """
        弹出确认框，确认后真正发送参数设置指令
        :param reg_addr: 寄存器地址
        :param new_value: 要设置的值
        :param param_name: 参数中文名，用于提示框显示
        """
        title = "确认设置参数"
        content = f"{param_name} 参数将要从当前值设置为 {new_value:.5f}，请确认是否正确。\n确认后将立即发送设置命令！"

        confirmed = await async_confirm(title, content, self)
        if confirmed:
            # 用户点击“确认”
            await self._set_param(reg_addr, new_value, param_name, value_type)

    @asyncSlot()
    async def _confirm_and_set_pid(
        self, reg_addr: int, new_value: float, param_name: str
    ):
        """
        弹出确认框，确认后真正发送 PID 设置指令（保持向后兼容）
        :param reg_addr: 寄存器地址
        :param new_value: 要设置的值
        :param param_name: 参数中文名，用于提示框显示
        """
        await self._confirm_and_set_param(reg_addr, new_value, param_name)

    @asyncSlot()
    async def _confirm_save_param(self):
        title = "确认保存参数"
        content = "即将把所有当前参数写入设备 Flash 永久保存，请确认是否继续？"

        confirmed = await async_confirm(title, content, self)
        if confirmed:
            await self.save_param_cmd()

    @asyncSlot()
    async def _confirm_launch_zero_calibration(self):
        title = "确认启动旋变零点校准"
        content = "即将启动旋变零点校准，请确认是否继续？"

        confirmed = await async_confirm(title, content, self)
        if confirmed:
            await self.launch_zero_calibration_cmd()

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            logger.info("DeviceSettingFrom正常退出")
            event.accept()
        except Exception as e:
            logger.error(f"关闭DeviceSettingFrom时出错: {e}")
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
