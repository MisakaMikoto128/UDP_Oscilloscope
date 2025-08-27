# -*- coding: utf-8 -*-
"""
UDP通信协议解析模块
实现电机控制板通信协议的数据包解析
"""

import struct
import logging
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from utils.crc import extract_and_verify_crc

logger = logging.getLogger(__name__)

# 协议常量
PACKET_HEADER = 0x55AA
PACKET_TYPE_MOTOR_U16 = 0xA1
PACKET_TYPE_MOTOR_F32 = 0xA2
PACKET_TYPE_SYS_REGS_UP = 0xF3
PACKET_TYPE_SYS_REGS_SET = 0x10

# 数据包大小定义
MOTOR_U16_PACKET_SIZE = 21  # 1 + 10*2
MOTOR_F32_PACKET_SIZE = 41  # 1 + 10*4
SYS_REG_PACKET_HEAD_SIZE = 3
SYS_REG_SET_PACKET_SIZE = 5


@dataclass
class MotorSampleData:
    """电机采样数据"""

    packet_type: int
    channels: List[float]  # 统一转换为float


@dataclass
class SysREGsUpData:
    """配置数据"""
    packet_type: int
    reg_num: int
    reg: List[int]


@dataclass
class ParsedPacket:
    """解析后的数据包"""

    sequence: int
    motor_data: Optional[List[MotorSampleData]] = None
    sys_regs_up_datas: Optional[List[SysREGsUpData]] = None


class ProtocolParser:
    """协议解析器"""

    def __init__(self):
        self.buffer = bytearray()
        self.last_sequence = None
        self.packet_count = 0
        self.lost_packets = 0
        self.duplicate_packets = 0

    def feed_data(self, data: bytes) -> List[ParsedPacket]:
        """
        输入数据并解析数据包

        Args:
            data: 接收到的UDP数据

        Returns:
            解析出的数据包列表
        """
        self.buffer.extend(data)
        packets = []

        while len(self.buffer) >= 6:  # 最小包头大小
            packets_ = self._try_parse_packet()
            packets.extend(packets_)

        return packets

    def _try_parse_packet(self) -> Optional[ParsedPacket]:
        """尝试解析一个完整的数据包"""
        # 查找包头
        header_pos = self._find_header()
        if header_pos == -1:
            # 没有找到包头，清空缓冲区
            self.buffer.clear()
            return None

        # 移除包头前的无效数据
        if header_pos > 0:
            self.buffer = self.buffer[header_pos:]

        # 检查是否有足够的数据解析包头
        if len(self.buffer) < 6:
            return None

        # 解析包头
        try:
            header, remaining_length, sequence = struct.unpack("<HHH", self.buffer[:6])
            if header != PACKET_HEADER:
                # 包头不匹配，移除第一个字节继续查找
                self.buffer = self.buffer[1:]
                return None
        except struct.error:
            return None

        # 检查是否有足够的数据
        total_length = 6 + remaining_length
        if len(self.buffer) < total_length:
            return None

        # 提取完整数据包
        packet_data = bytes(self.buffer[:total_length])
        self.buffer = self.buffer[total_length:]

        # CRC校验
        payload_with_crc = packet_data[6:]  # 去掉包头
        payload, crc_valid = extract_and_verify_crc(payload_with_crc)

        # if not crc_valid:
        #     logger.warning(f"CRC校验失败，序号: {sequence}")
        #     return None

        # 统计丢包和重复包
        self._update_statistics(sequence)

        # 解析子数据包
        parsed_packets = self._parse_sub_packets(payload)

        return parsed_packets

    def _find_header(self) -> int:
        """查找包头位置"""
        for i in range(len(self.buffer) - 1):
            if self.buffer[i] == 0xAA and self.buffer[i + 1] == 0x55:
                return i
        return -1

    def _update_statistics(self, sequence: int):
        """更新统计信息"""
        self.packet_count += 1

        if self.last_sequence is not None:
            expected_sequence = (self.last_sequence + 1) & 0xFFFF
            if sequence == self.last_sequence:
                self.duplicate_packets += 1
                logger.debug(f"重复包，序号: {sequence}")
                return
            elif sequence != expected_sequence:
                # 计算丢失的包数量
                if sequence > expected_sequence:
                    lost = sequence - expected_sequence
                else:
                    # 处理序号回绕
                    lost = (0x10000 - expected_sequence) + sequence
                self.lost_packets += lost
                logger.debug(
                    f"丢包检测，期望: {expected_sequence}, 实际: {sequence}, 丢失: {lost}"
                )

        self.last_sequence = sequence

    def _parse_sub_packets(self, payload: bytes):
        """解析子数据包"""
        offset = 0
        parsed_packets = []

        while offset < len(payload):
            if offset >= len(payload):
                break

            packet_type = payload[offset]

            if packet_type == PACKET_TYPE_MOTOR_U16:
                motor_data = self._parse_motor_u16(payload[offset:])
                if motor_data:
                    parsed_packets.append(motor_data)
                    offset += MOTOR_U16_PACKET_SIZE
                else:
                    break

            elif packet_type == PACKET_TYPE_MOTOR_F32:
                motor_data = self._parse_motor_f32(payload[offset:])
                if motor_data:
                    parsed_packets.append(motor_data)
                    offset += MOTOR_F32_PACKET_SIZE
                else:
                    break
            elif packet_type == PACKET_TYPE_SYS_REGS_UP:
                SYS_REG_PACKET_SIZE, sys_regs_up_data = self._parse_sys_regs_upload(
                    payload[offset:]
                )
                if sys_regs_up_data:
                    parsed_packets.append(sys_regs_up_data)
                    offset += SYS_REG_PACKET_SIZE
                else:
                    break
            elif packet_type == PACKET_TYPE_SYS_REGS_SET:
                sys_regs_set_resp = self._parse_sys_regs_set_resp(payload[offset:])
                if sys_regs_set_resp:
                    parsed_packets.append(sys_regs_set_resp)
                    offset += SYS_REG_SET_PACKET_SIZE
                else:
                    break
            else:
                logger.warning(f"未知数据包类型: 0x{packet_type:02X}")
                break

        return parsed_packets

    def _parse_motor_u16(self, data: bytes) -> Optional[MotorSampleData]:
        """解析uint16电机采样数据"""
        if len(data) < MOTOR_U16_PACKET_SIZE:
            return None

        try:
            # 解析数据包类型和10个通道数据
            values = struct.unpack("<B10H", data[:MOTOR_U16_PACKET_SIZE])
            packet_type = values[0]
            channels = [float(v) for v in values[1:]]

            return MotorSampleData(packet_type=packet_type, channels=channels)
        except struct.error:
            return None

    def _parse_motor_f32(self, data: bytes) -> Optional[MotorSampleData]:
        """解析float32电机采样数据"""
        if len(data) < MOTOR_F32_PACKET_SIZE:
            return None

        try:
            # 解析数据包类型和10个通道数据
            values = struct.unpack("<B10f", data[:MOTOR_F32_PACKET_SIZE])
            packet_type = values[0]
            channels = list(values[1:])

            return MotorSampleData(packet_type=packet_type, channels=channels)
        except struct.error:
            return None

    def _parse_sys_regs_upload(self, data: bytes) -> Optional[SysREGsUpData]:
        """解析配置数据"""
        if len(data) < SYS_REG_PACKET_HEAD_SIZE:
            return None

        try:
            # 解析type和reg_num
            values = struct.unpack("<BH", data[:SYS_REG_PACKET_HEAD_SIZE])
            packet_type = values[0]
            reg_num = values[1]
            SYS_REG_PACKET_SIZE = SYS_REG_PACKET_HEAD_SIZE + reg_num * 4

            # 验证数据包长度
            if len(data) < SYS_REG_PACKET_SIZE:
                raise ValueError(
                    f"数据包长度不足，期望 {SYS_REG_PACKET_SIZE} 字节，实际 {len(data)} 字节"
                )

            # 解析寄存器数据
            regs = struct.unpack(
                f"<{reg_num}I", data[SYS_REG_PACKET_HEAD_SIZE:SYS_REG_PACKET_SIZE]
            )

            # 可选：将结果封装为字典
            result = SysREGsUpData(packet_type=packet_type, reg_num=reg_num, reg=list(regs))
            return SYS_REG_PACKET_SIZE, result
        except struct.error:
            return None

    def _parse_sys_regs_set_resp(self, data: bytes) -> Optional[SysREGsUpData]:
        """解析配置数据"""
        if len(data) < SYS_REG_SET_PACKET_SIZE:
            return None

        try:
            # 解析type和reg_num
            values = struct.unpack("<BHH", data[:SYS_REG_SET_PACKET_SIZE])
            packet_type = values[0]
            reg_addr_start = values[1]
            trg_wroten_num = values[2]

            # 可选：将结果封装为字典
            result = {
                "type": packet_type,
                "reg_addr_start": reg_addr_start,
                "trg_wroten_num": trg_wroten_num,
            }
            return result
        except struct.error:
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_expected = self.packet_count + self.lost_packets
        loss_rate = (
            (self.lost_packets / total_expected * 100) if total_expected > 0 else 0
        )
        duplicate_rate = (
            (self.duplicate_packets / self.packet_count * 100)
            if self.packet_count > 0
            else 0
        )

        return {
            "total_packets": self.packet_count,
            "lost_packets": self.lost_packets,
            "duplicate_packets": self.duplicate_packets,
            "loss_rate": loss_rate,
            "duplicate_rate": duplicate_rate,
        }

    def reset_statistics(self):
        """重置统计信息"""
        self.last_sequence = None
        self.packet_count = 0
        self.lost_packets = 0
        self.duplicate_packets = 0
