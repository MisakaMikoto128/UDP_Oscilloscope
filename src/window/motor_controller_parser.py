class MotorControllerParser:
    """电机控制器上位机数据解析器"""

    # 状态机定义
    STATE_MACHINE = {
        0x00: {"cn": "空闲", "en": "IDLE"},
        0x01: {"cn": "速度模式选择", "en": "Speed_Mode_SEL"},
        0x02: {"cn": "低速模式", "en": "LoSpeed_MODE"},
        0x03: {"cn": "高速模式", "en": "HiSpeed_MODE"},
        0x04: {"cn": "直流母线充电", "en": "Bus_CHARGE"},
        0x05: {"cn": "直流母线充电延时", "en": "Bus_CHARGE_DELAY"},
        0x06: {"cn": "直流母线充电预结束", "en": "Bus_CHARGE_OVER_PRE"},
        0x07: {"cn": "直流母线充电结束", "en": "Bus_CHARGE_OVER"},
        0x08: {"cn": "电机驱动器运行", "en": "MD_RUN"},
        0x09: {"cn": "电机驱动器停止功率输出", "en": "MD_PWM_OFF"},
        0x40: {"cn": "系统准备急停", "en": "SYSTEM_STOP_PRE"},
        0x41: {"cn": "系统急停", "en": "SYSTEM_STOP"},
        0x50: {"cn": "准备零位校准", "en": "ROTTX_ZERO_EN_PRE"},
        0x51: {"cn": "准备零位校准2", "en": "ROTTX_ZERO_EN_PRE2"},
        0x52: {"cn": "发送小脉冲", "en": "ROTTX_ZERO_PULSE_ON"},
        0x53: {"cn": "获得零位数据", "en": "ROTTX_ZERO_DATA_READ"},
        0x54: {"cn": "存数据", "en": "ROTTX_ZERO_DATA_LOG"},
        0xFE: {"cn": "故障", "en": "FAULT"},
        0xFF: {"cn": "故障返回", "en": "FAULT_RET"},
    }

    # 错误代码位定义
    ERROR_BITS = {
        0: {"cn": "自检异常", "en": "RSVD2"},
        1: {"cn": "过温保护", "en": "NTC_FLT"},
        2: {"cn": "5V电源故障", "en": "FLT5V"},
        3: {"cn": "15V电源故障", "en": "FLT15V"},
        4: {"cn": "功率器件保护2", "en": "DESAT2"},
        5: {"cn": "功率器件保护1", "en": "DESAT1"},
        6: {"cn": "保留1", "en": "RSVD1"},
        7: {"cn": "总故障标志", "en": "FaultALL"},
    }

    # 故障标志位定义
    FAULT_FLAGS = {
        # MOTSTATUS (位 0-7)
        "MOTSTATUS": [
            ("位置传感器异常", 1 << 0),
            ("内部超速", 1 << 1),
            ("CPLD_FLT", 1 << 2),
            ("FLT4_Flag", 1 << 3),
            ("FLT3_Flag", 1 << 4),
            ("FLT2_Flag", 1 << 5),
            ("FLT1_Flag", 1 << 6),
            ("Ic_Err", 1 << 7),
        ],
        # INVSTATUS (位 8-15)
        "INVSTATUS": [
            ("Ib_Err", 1 << 8),
            ("Ia_Err", 1 << 9),
            ("Ibus_Err", 1 << 10),
            ("Vbus_Err", 1 << 11),
            ("NTC4_Err", 1 << 12),
            ("NTC3_Err", 1 << 13),
            ("NTC2_Err", 1 << 14),
            ("NTC1_Err", 1 << 15),
        ],
        # SYSSTATUS (位 16-23)
        "SYSSTATUS": [
            ("自检异常", 1 << 16),
            ("缺相", 1 << 17),
            ("电机过热", 1 << 18),
            ("逆变器过温", 1 << 19),
            ("功率器件保护", 1 << 20),
            ("母线欠压", 1 << 21),
            ("母线过压", 1 << 22),
            ("逆变器过流", 1 << 23),
        ],
        # OCFLT (位 24-31)
        "OCFLT": [
            ("C相硬件过流", 1 << 24),
            ("B相硬件过流", 1 << 25),
            ("A相硬件过流", 1 << 26),
            ("母线硬件过流", 1 << 27),
            ("C相软件过流", 1 << 28),
            ("B相软件过流", 1 << 29),
            ("A相软件过流", 1 << 30),
            ("母线软件过流", 1 << 31),
        ],
    }

    def parse_temperature(self, temperature_u32):
        """
        解析温度数据
        Args:
            temperature_u32: 来自sys_regs_up_data.reg[55]的32位数据
        Returns:
            dict: 包含温度和状态信息
        """
        # 提取各字节
        temp_d = (temperature_u32 >> 24) & 0xFF  # 最高字节
        temp_c = (temperature_u32 >> 16) & 0xFF
        temp_b = (temperature_u32 >> 8) & 0xFF
        state = temperature_u32 & 0xFF  # 最低字节为状态机

        # 获取状态机信息
        state_info = self.STATE_MACHINE.get(state, {"cn": "未知状态", "en": "UNKNOWN"})

        return {
            "temperatures": {"temp_d": temp_d, "temp_c": temp_c, "temp_b": temp_b},
            "state": {
                "code": state,
                "name_cn": state_info["cn"],
                "name_en": state_info["en"],
            },
        }

    def parse_error_code(self, error_code_u32):
        """
        解析错误代码
        Args:
            error_code_u32: 来自sys_regs_up_data.reg[63]的32位数据
        Returns:
            dict: 包含各模块错误信息
        """
        # 提取各字节的错误代码
        error_d = (error_code_u32 >> 24) & 0xFF
        error_c = (error_code_u32 >> 16) & 0xFF
        error_b = (error_code_u32 >> 8) & 0xFF

        return {
            "error_codes": {
                "module_d": self._parse_single_error(error_d),
                "module_c": self._parse_single_error(error_c),
                "module_b": self._parse_single_error(error_b),
            },
            "has_error": any([error_d, error_c, error_b]),
        }

    def parse_fault_flags(self, flag1_uint32):
        """
        解析故障标志位
        Args:
            flag1_uint32: 来自sys_regs_up_data.reg[90]的32位故障标志数据
        Returns:
            dict: 包含各类故障信息
        """
        result = {}

        for category, flag_bits in self.FAULT_FLAGS.items():
            active_faults = []
            for fault_name, mask in flag_bits:
                if flag1_uint32 & mask:
                    active_faults.append(fault_name)
            result[category] = active_faults

        return result

    def _parse_single_error(self, error_byte):
        """
        解析单个字节的错误代码
        Args:
            error_byte: 8位错误代码
        Returns:
            dict: 错误详情
        """
        errors = []
        for bit in range(8):
            if error_byte & (1 << bit):
                error_info = self.ERROR_BITS.get(
                    bit, {"cn": "未知错误", "en": "UNKNOWN"}
                )
                errors.append(
                    {
                        "bit": bit,
                        "name_cn": error_info["cn"],
                        "name_en": error_info["en"],
                    }
                )

        return {
            "raw_value": error_byte,
            "active_errors": errors,
            "has_error": bool(error_byte),
        }

    def parse_all(self, temperature_u32, error_code_u32, fault_flags_u32=None):
        """
        一次性解析所有数据
        Args:
            temperature_u32: 温度数据
            error_code_u32: 错误代码数据
            fault_flags_u32: 故障标志数据（可选）
        Returns:
            dict: 完整解析结果
        """
        temp_result = self.parse_temperature(temperature_u32)
        error_result = self.parse_error_code(error_code_u32)

        result = {
            "timestamp": None,  # 可以添加时间戳
            "temperature_data": temp_result,
            "error_data": error_result,
            "system_status": "FAULT" if error_result["has_error"] else "NORMAL",
        }

        if fault_flags_u32 is not None:
            fault_result = self.parse_fault_flags(fault_flags_u32)
            result["fault_flags"] = fault_result
            # 如果有故障标志，也算作故障状态
            has_faults = any(faults for faults in fault_result.values())
            if has_faults:
                result["system_status"] = "FAULT"

        return result

    def get_display_info(self, temperature_u32, error_code_u32):
        """
        获取用于界面显示的简化信息
        Returns:
            dict: 界面显示用的数据
        """
        temp_info = self.parse_temperature(temperature_u32)
        error_info = self.parse_error_code(error_code_u32)

        # 收集所有错误信息
        all_errors = []
        module_name_cn = {
            "module_d": "驱动器1",
            "module_c": "驱动器2",
            "module_b": "驱动器3",
        }
        for module_name, module_data in error_info["error_codes"].items():
            for error in module_data["active_errors"]:
                all_errors.append(f"{module_name_cn[module_name]}:{error['name_cn']}")

        return {
            "temp_d": temp_info["temperatures"]["temp_d"],
            "temp_c": temp_info["temperatures"]["temp_c"],
            "temp_b": temp_info["temperatures"]["temp_b"],
            "state_en": temp_info["state"]["name_en"],
            "state_cn": temp_info["state"]["name_cn"],
            "has_error": error_info["has_error"],
            "all_errors": all_errors,
            "error_codes": error_info["error_codes"],
        }


# 使用示例
if __name__ == "__main__":
    parser = MotorControllerParser()

    # 模拟数据
    temperature_u32 = 0x50453A08  # 示例数据
    error_code_u32 = 0x02010000  # 示例数据
    fault_flags_u32 = 0xF00F001  # 示例故障标志

    # 解析温度
    temp_info = parser.parse_temperature(temperature_u32)
    print("温度信息:", temp_info)

    # 解析错误代码
    error_info = parser.parse_error_code(error_code_u32)
    print("错误信息:", error_info)

    # 解析故障标志
    fault_info = parser.parse_fault_flags(fault_flags_u32)
    print("故障标志:", fault_info)

    # 一次性解析
    all_info = parser.parse_all(temperature_u32, error_code_u32, fault_flags_u32)
    print("完整信息:", all_info)
