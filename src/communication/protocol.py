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
PACKET_TYPE_CONFIG_DOWN = 0xF3
PACKET_TYPE_CONFIG_UP = 0xF4

# 数据包大小定义
MOTOR_U16_PACKET_SIZE = 21  # 1 + 10*2
MOTOR_F32_PACKET_SIZE = 41  # 1 + 10*4
CONFIG_PACKET_SIZE = 25     # 1 + 6*4


@dataclass
class MotorSampleData:
    """电机采样数据"""
    packet_type: int
    channels: List[float]  # 统一转换为float


@dataclass
class ConfigData:
    """配置数据"""
    packet_type: int
    kp: float
    ki: float
    kd: float
    kp1: float
    ki1: float
    kd1: float


@dataclass
class ParsedPacket:
    """解析后的数据包"""
    sequence: int
    motor_data: Optional[List[MotorSampleData]] = None
    config_datas: Optional[List[ConfigData]] = None


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
        
        while len(self.buffer) >= 8:  # 最小包头大小
            packets = self._try_parse_packet()
            
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
        if len(self.buffer) < 8:
            return None
        
        # 解析包头
        try:
            header, data_filed_len, channel, sequence = struct.unpack('<HHHH', self.buffer[:8])
            if header != PACKET_HEADER:
                # 包头不匹配，移除第一个字节继续查找
                self.buffer = self.buffer[1:]
                return None
        except struct.error:
            return None
        
        # 检查是否有足够的数据
        total_length = 8 + data_filed_len
        if len(self.buffer) < total_length:
            logger.info("err")
            return None
        
        # 提取完整数据包
        packet_data = bytes(self.buffer[:total_length])
        self.buffer = self.buffer[total_length:]
        
        # CRC校验
        payload_with_crc = packet_data[8:]  # 去掉包头
        payload, crc_valid = extract_and_verify_crc(payload_with_crc)
        
        # if not crc_valid:
        #     logger.warning(f"CRC校验失败，序号: {sequence}")
        #     return None
        
        # 统计丢包和重复包
        self._update_statistics(sequence)
        
        # 解析子数据包
        if channel == 0:
            parsed_packets = self._parse_sub_packets(payload)
        else:
            logger.info("cmd")
        
        return parsed_packets
    
    def _find_header(self) -> int:
        """查找包头位置"""
        for i in range(len(self.buffer) - 1):
            if (self.buffer[i] == 0xAA and 
                self.buffer[i + 1] == 0x55):
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
                logger.debug(f"丢包检测，期望: {expected_sequence}, 实际: {sequence}, 丢失: {lost}")
        
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
                    
            elif packet_type in (PACKET_TYPE_CONFIG_DOWN, PACKET_TYPE_CONFIG_UP):
                config_data = self._parse_config(payload[offset:])
                if config_data:
                    parsed_packets.append(config_data)
                    offset += CONFIG_PACKET_SIZE
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
            values = struct.unpack('<B10H', data[:MOTOR_U16_PACKET_SIZE])
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
            values = struct.unpack('<B10f', data[:MOTOR_F32_PACKET_SIZE])
            packet_type = values[0]
            channels = list(values[1:])
            
            return MotorSampleData(packet_type=packet_type, channels=channels)
        except struct.error:
            return None
    
    def _parse_config(self, data: bytes) -> Optional[ConfigData]:
        """解析配置数据"""
        if len(data) < CONFIG_PACKET_SIZE:
            return None
        
        try:
            # 解析数据包类型和6个PID参数
            values = struct.unpack('<B6f', data[:CONFIG_PACKET_SIZE])
            packet_type = values[0]
            
            return ConfigData(
                packet_type=packet_type,
                kp=values[1],
                ki=values[2],
                kd=values[3],
                kp1=values[4],
                ki1=values[5],
                kd1=values[6]
            )
        except struct.error:
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_expected = self.packet_count + self.lost_packets
        loss_rate = (self.lost_packets / total_expected * 100) if total_expected > 0 else 0
        duplicate_rate = (self.duplicate_packets / self.packet_count * 100) if self.packet_count > 0 else 0
        
        return {
            'total_packets': self.packet_count,
            'lost_packets': self.lost_packets,
            'duplicate_packets': self.duplicate_packets,
            'loss_rate': loss_rate,
            'duplicate_rate': duplicate_rate
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.last_sequence = None
        self.packet_count = 0
        self.lost_packets = 0
        self.duplicate_packets = 0
