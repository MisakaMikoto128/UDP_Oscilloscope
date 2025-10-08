# -*- coding: utf-8 -*-
"""
寄存器解析器
统一管理系统寄存器的解析逻辑，方便复用和维护
"""

import logging
from typing import Dict, Any, List
from dataclasses import dataclass

from src.communication.protocol import SysREGsUpData
from src.window.motor_controller_parser import MotorControllerParser
from src.utils.data_utils import uint32_to_int32

logger = logging.getLogger(__name__)


@dataclass
class RegisterMapping:
    """寄存器映射定义"""
    # 基础寄存器地址
    TEMPERATURE = 55        # 温度数据
    ID = 56                # Id电流
    IQ = 32                # Iq电流
    UD = 60                # Ud电压
    UQ = 61                # Uq电压
    ANGLE = 62             # 角度
    ERROR_CODE = 63        # 错误代码
    M_DUTY = 64            # 占空比
    M_PT1 = 65             # 电机温度1
    M_PT2 = 66             # 电机温度2
    M_PT3 = 67             # 电机温度3
    M_PT4 = 68             # 电机温度4
    M_PT5 = 69             # 电机温度5
    IA = 73                # A相电流
    IB = 74                # B相电流
    IC = 75                # C相电流
    VBUS = 76              # 母线电压
    VBUS_IN = 77           # 输入电压
    IBUS = 79              # 母线电流
    M_SPEED = 83           # 转速
    SYS_MODE = 85          # 系统模式
    FLAG1 = 90             # 故障标志


@dataclass
class ParsedRegisterData:
    """解析后的寄存器数据"""
    # 原始数据
    device_uid: int
    registers: List[int]
    
    # 电流相关
    mSpeed: float
    angle: float
    Id: float
    Iq: float
    Ia: float
    Ib: float
    Ic: float
    Ibus: float
    
    # 电压相关
    Vbus: float
    Vbus_in: float
    Ud: float
    Uq: float
    
    # 温度相关
    temperature_u32: int
    temp_info: Dict[str, Any]
    info: Dict[str, Any]
    mPT1: float
    mPT2: float
    mPT3: float
    mPT4: float
    mPT5: float
    
    # 控制相关
    mDuty: float
    
    # 故障相关
    error_code_u32: int
    flag1_uint32: int
    error_info: Dict[str, Any]
    fault_info: Dict[str, Any]
    
    # 系统状态
    sys_mode: int
    sys_mode_name: str
    zero_enabled: bool


class RegisterParser:
    """寄存器解析器"""
    
    def __init__(self):
        self.parser = MotorControllerParser()
        self.fixed_point_scale = 100000
        self.register_map = RegisterMapping()
        
        # 系统模式映射
        self.sys_mode_dict = {
            0: "unknown",
            1: "current", 
            2: "speed"
        }
    
    def parse_sys_regs_data(self, sys_regs_up_data: SysREGsUpData) -> ParsedRegisterData:
        """
        解析系统寄存器数据
        
        Args:
            sys_regs_up_data: 系统寄存器数据
            
        Returns:
            ParsedRegisterData: 解析后的数据
        """
        try:
            registers = sys_regs_up_data.reg
            
            # 检查寄存器数组长度
            if len(registers) < 91:
                logger.warning(f"寄存器数组长度不足: {len(registers)}")
                # 补齐到最小长度
                registers = registers + [0] * (91 - len(registers))
            
            # 解析基础数值（应用固定点缩放）
            uid = sys_regs_up_data.reg[0]
            mSpeed = -uint32_to_int32(registers[self.register_map.M_SPEED]) / self.fixed_point_scale
            angle = registers[self.register_map.ANGLE] / self.fixed_point_scale
            Id = uint32_to_int32(registers[self.register_map.ID]) / self.fixed_point_scale
            Iq = uint32_to_int32(registers[self.register_map.IQ]) / self.fixed_point_scale
            Ud = uint32_to_int32(registers[self.register_map.UD]) / self.fixed_point_scale
            Uq = uint32_to_int32(registers[self.register_map.UQ]) / self.fixed_point_scale
            Vbus = uint32_to_int32(registers[self.register_map.VBUS]) / self.fixed_point_scale
            Vbus_in = uint32_to_int32(registers[self.register_map.VBUS_IN]) / self.fixed_point_scale
            Ia = uint32_to_int32(registers[self.register_map.IA]) / self.fixed_point_scale
            Ib = uint32_to_int32(registers[self.register_map.IB]) / self.fixed_point_scale
            Ic = uint32_to_int32(registers[self.register_map.IC]) / self.fixed_point_scale
            Ibus = uint32_to_int32(registers[self.register_map.IBUS]) / self.fixed_point_scale
            mDuty = uint32_to_int32(registers[self.register_map.M_DUTY]) / self.fixed_point_scale
            mPT1 = uint32_to_int32(registers[self.register_map.M_PT1]) / self.fixed_point_scale
            mPT2 = uint32_to_int32(registers[self.register_map.M_PT2]) / self.fixed_point_scale
            mPT3 = uint32_to_int32(registers[self.register_map.M_PT3]) / self.fixed_point_scale
            mPT4 = uint32_to_int32(registers[self.register_map.M_PT4]) / self.fixed_point_scale
            mPT5 = uint32_to_int32(registers[self.register_map.M_PT5]) / self.fixed_point_scale
            
            # 解析原始状态数据
            temperature_u32 = registers[self.register_map.TEMPERATURE]
            error_code_u32 = registers[self.register_map.ERROR_CODE]
            flag1_uint32 = registers[self.register_map.FLAG1]
            
            # 解析温度和故障信息
            temp_info = self.parser.parse_temperature(temperature_u32)
            error_info = self.parser.parse_error_code(error_code_u32)
            fault_info = self.parser.parse_fault_flags(flag1_uint32)
            info = self.parser.get_display_info(temperature_u32, error_code_u32)
            
            # 解析系统模式
            sys_mode = registers[self.register_map.SYS_MODE] & 0x07
            zero_enabled = bool((registers[self.register_map.SYS_MODE] >> 3) & 0x01)
            sys_mode_name = self.sys_mode_dict.get(sys_mode, "unknown")
            RotTX_ZeroEN_FLG_dict = {0: "未启动", 1: "已启动"}
            
            return ParsedRegisterData(
                device_uid=uid,
                registers=registers,
                mSpeed=mSpeed,
                angle=angle,
                Id=Id,
                Iq=Iq,
                Ia=Ia,
                Ib=Ib,
                Ic=Ic,
                Ibus=Ibus,
                Vbus=Vbus,
                Vbus_in=Vbus_in,
                Ud=Ud,
                Uq=Uq,
                temperature_u32=temperature_u32,
                temp_info=temp_info,
                info=info,
                mPT1=mPT1,
                mPT2=mPT2,
                mPT3=mPT3,
                mPT4=mPT4,
                mPT5=mPT5,
                mDuty=mDuty,
                error_code_u32=error_code_u32,
                flag1_uint32=flag1_uint32,
                error_info=error_info,
                fault_info=fault_info,
                sys_mode=sys_mode,
                sys_mode_name=sys_mode_name,
                zero_enabled=zero_enabled
            )
            
        except Exception as e:
            logger.error(f"解析寄存器数据失败: {e}")
            raise
    
    def get_error_codes_breakdown(self, error_code_u32: int) -> Dict[str, int]:
        """
        获取错误代码的分解
        
        Args:
            error_code_u32: 32位错误代码
            
        Returns:
            Dict: 包含各模块错误代码的字典
        """
        return {
            'error_d': (error_code_u32 >> 24) & 0xFF,  # 模块D
            'error_c': (error_code_u32 >> 16) & 0xFF,  # 模块C  
            'error_b': (error_code_u32 >> 8) & 0xFF,   # 模块B
            'error_a': error_code_u32 & 0xFF          # 模块A
        }
    
    def get_fault_status_text(self, flag1_uint32: int) -> str:
        """
        获取故障状态文本
        
        Args:
            flag1_uint32: 故障标志
            
        Returns:
            str: 故障状态文本
        """
        fault_info = self.parser.parse_fault_flags(flag1_uint32)
        fault_list = []
        for category, status in fault_info.items():
            if status:
                fault_list.extend(status)
        
        if fault_list:
            return f"0x{flag1_uint32:08X}: {', '.join(fault_list)}"
        else:
            return "正常"
    
    def get_error_text(self, error_code_u32: int, module: str) -> str:
        """
        获取指定模块的错误文本
        
        Args:
            error_code_u32: 错误代码
            module: 模块名称 ('d', 'c', 'b', 'a')
            
        Returns:
            str: 错误文本
        """
        error_breakdown = self.get_error_codes_breakdown(error_code_u32)
        error_info = self.parser.parse_error_code(error_code_u32)
        
        module_key = f'module_{module}'
        if module_key in error_info['error_codes']:
            module_info = error_info['error_codes'][module_key]
            error_value = error_breakdown[f'error_{module}']
            
            if module_info['has_error']:
                error_names = [err['name_cn'] for err in module_info['active_errors']]
                return f"0x{error_value:02X}: {', '.join(error_names)}"
            else:
                return "正常"
        else:
            return "正常"
