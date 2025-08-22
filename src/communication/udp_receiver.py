# -*- coding: utf-8 -*-
"""
UDP接收器模块
实现异步UDP数据接收和处理
"""

import asyncio
import logging
from typing import Optional, List, Tuple, Dict, Any
from typing import Callable, Optional, Any
from communication.protocol import ProtocolParser, MotorSampleData, ConfigData
PACKET_TYPE_MOTOR_U16 = 0xA1
PACKET_TYPE_MOTOR_F32 = 0xA2
PACKET_TYPE_CONFIG_DOWN = 0xF3
PACKET_TYPE_CONFIG_UP = 0xF4

import socket
logger = logging.getLogger(__name__)


class UDPReceiver:
    """UDP数据接收器"""
    
    def __init__(self, 
                 host: str = '0.0.0.0', 
                 port: int = 8888,
                 on_sample: Optional[Callable[[int, list], None]] = None,
                 on_config: Optional[Callable[[dict], None]] = None):
        """
        初始化UDP接收器
        
        Args:
            host: 监听地址
            port: 监听端口
            on_sample: 采样数据回调函数 (packet_type, channels)
            on_config: 配置数据回调函数 (config_dict)
        """
        self.host = host
        self.port = port
        self.on_sample = on_sample
        self.on_config = on_config
        
        self.parser = ProtocolParser()
        self.transport = None
        self.protocol = None
        self.running = False
        
    async def start(self):
        """启动UDP接收器"""
        if self.running:
            return
            
        try:
            loop = asyncio.get_event_loop()
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self._on_data_received),
                local_addr=(self.host, self.port),
                family=socket.AF_INET  # 强制IPv4
            )

            # 获取socket并设置更大的接收缓冲区
            sock = self.transport.get_extra_info('socket')
            # 设置接收缓冲区为50MB
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024*50)
            
            # 可选：设置发送缓冲区
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024*1024)

            # 获取实际绑定的地址
            sockname = self.transport.get_extra_info('sockname')
            logger.info(f"UDP接收器已启动，实际绑定地址: {sockname}")
            
            # 获取socket信息
            sock = self.transport.get_extra_info('socket')
            family_name = "AF_INET" if sock.family == socket.AF_INET else f"family={sock.family}"
            logger.info(f"Socket详细信息: {family_name}, type={sock.type}, proto={sock.proto}")
            
            self.running = True
            logger.info(f"UDP接收器已启动，监听 {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"启动UDP接收器失败: {e}")
            raise
    
    async def stop(self):
        """停止UDP接收器"""
        if not self.running:
            return
            
        if self.transport:
            self.transport.close()
            self.transport = None
            self.protocol = None
        
        self.running = False
        logger.info("UDP接收器已停止")
    
    def _on_data_received(self, data: bytes, addr: tuple):
        """处理接收到的UDP数据"""
        try:
            packets = self.parser.feed_data(data)
            
            for packet in packets:
                # 处理电机采样数据
                if packet.packet_type == PACKET_TYPE_MOTOR_U16 or \
                    packet.packet_type == PACKET_TYPE_MOTOR_F32:
                    self._handle_motor_data(packet)
                
                # 处理配置数据
                if packet.packet_type == PACKET_TYPE_CONFIG_DOWN or \
                    packet.packet_type == PACKET_TYPE_CONFIG_UP:
                    self._handle_config_data(packet)
                    
        except Exception as e:
            logger.error(f"处理UDP数据时出错: {e}")
    
    def _handle_motor_data(self, motor_data: MotorSampleData):
        """处理电机采样数据"""
        if self.on_sample:
            try:
                # 将packet_type转换为格式标识: 0xA1->0, 0xA2->1
                self.on_sample(motor_data.packet_type, motor_data.channels)
            except Exception as e:
                logger.error(f"处理电机采样数据回调时出错: {e}")
    
    def _handle_config_data(self, config_data: ConfigData):
        """处理配置数据"""
        if self.on_config:
            try:
                config_dict = {
                    'packet_type': config_data.packet_type,
                    'kp': config_data.kp,
                    'ki': config_data.ki,
                    'kd': config_data.kd,
                    'kp1': config_data.kp1,
                    'ki1': config_data.ki1,
                    'kd1': config_data.kd1
                }
                self.on_config(config_dict)
            except Exception as e:
                logger.error(f"处理配置数据回调时出错: {e}")
    
    def get_statistics(self) -> dict:
        """获取接收统计信息"""
        return self.parser.get_statistics()
    
    def reset_statistics(self):
        """重置统计信息"""
        self.parser.reset_statistics()
    
    async def send_config(self, kp: float, ki: float, kd: float, 
                         kp1: float, ki1: float, kd1: float,
                         target_addr: tuple = ('192.168.1.100', 8889)):
        """
        发送配置数据到下位机
        
        Args:
            kp, ki, kd, kp1, ki1, kd1: PID参数
            target_addr: 目标地址 (ip, port)
        """
        if not self.running or not self.transport:
            logger.warning("UDP接收器未运行，无法发送配置")
            return
        
        try:
            # 构造配置下传数据包
            import struct
            from utils.crc import append_crc
            
            # 子数据包：类型 + 6个float32参数
            sub_packet = struct.pack('<B6f', 0xF3, kp, ki, kd, kp1, ki1, kd1)
            
            # 主数据包：包头 + 剩余长度 + 序号 + 子数据包 + CRC
            sequence = getattr(self, '_send_sequence', 0)
            self._send_sequence = (sequence + 1) & 0xFFFF
            
            remaining_length = len(sub_packet) + 2  # 子数据包 + CRC
            header_data = struct.pack('<HHH', 0x55AA, remaining_length, sequence)
            
            # 添加CRC校验
            packet_data = append_crc(header_data + sub_packet)
            
            # 发送数据
            self.transport.sendto(packet_data, target_addr)
            logger.info(f"配置数据已发送到 {target_addr}")
            
        except Exception as e:
            logger.error(f"发送配置数据失败: {e}")


class UDPProtocol(asyncio.DatagramProtocol):
    """UDP协议处理器"""
    
    def __init__(self, data_callback: Callable[[bytes, tuple], None]):
        self.data_callback = data_callback
    
    def connection_made(self, transport):
        self.transport = transport
    
    def datagram_received(self, data: bytes, addr: tuple):
        """接收到UDP数据包"""
        if self.data_callback:
            self.data_callback(data, addr)
    
    def error_received(self, exc):
        """接收错误"""
        logger.error(f"UDP接收错误: {exc}")
    
    def connection_lost(self, exc):
        """连接丢失"""
        if exc:
            logger.error(f"UDP连接丢失: {exc}")
        else:
            logger.info("UDP连接正常关闭")
