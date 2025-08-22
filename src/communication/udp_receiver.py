# -*- coding: utf-8 -*-
"""
UDP接收器模块
实现异步UDP数据接收和处理
"""

import asyncio
import logging
import time
import socket
import threading
from typing import Optional, List, Tuple, Dict, Any
from typing import Callable, Optional, Any
from collections import deque
from communication.protocol import ProtocolParser, MotorSampleData, ConfigData

PACKET_TYPE_MOTOR_U16 = 0xA1
PACKET_TYPE_MOTOR_F32 = 0xA2
PACKET_TYPE_CONFIG_DOWN = 0xF3
PACKET_TYPE_CONFIG_UP = 0xF4

logger = logging.getLogger(__name__)


class UDPReceiver:
    """UDP数据接收器 - 15KHz高频优化版本"""
    
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
        self.transport = None  # 保持兼容性，实际不使用
        self.protocol = None   # 保持兼容性，实际不使用
        self.running = False
        
        # 高性能接收配置
        self.socket = None
        self.receive_thread = None
        self.process_thread = None
        
        # 高速数据队列 - 使用线程安全的deque
        self.data_queue = deque(maxlen=5000)  # 15KHz下约333ms缓冲
        self.queue_lock = threading.Lock()
        
        # 统计信息
        self.receive_count = 0
        self.process_count = 0
        self.drop_count = 0
        self.last_report_time = time.time()
        
        # 发送socket（用于send_config）
        self.send_socket = None
        
    async def start(self):
        """启动UDP接收器"""
        if self.running:
            return
            
        try:
            # 创建高性能UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Windows下的socket优化
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 100*1024*1024)  # 100MB
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 绑定地址
            self.socket.bind((self.host, self.port))
            
            # 获取实际缓冲区大小
            actual_rcvbuf = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
            
            # 创建发送socket（用于send_config）
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024*1024)
            
            # 获取实际绑定地址
            sockname = self.socket.getsockname()
            logger.info(f"UDP接收器已启动，实际绑定地址: {sockname}")
            logger.info(f"Socket详细信息: AF_INET, type={self.socket.type}, proto={self.socket.proto}")
            logger.info(f"实际接收缓冲区大小: {actual_rcvbuf} 字节")
            
            self.running = True
            
            # 启动专用高速接收线程
            self.receive_thread = threading.Thread(
                target=self._high_speed_receive_loop,
                name="UDP_Receiver_15KHz",
                daemon=True
            )
            self.receive_thread.start()
            
            # 启动数据处理线程
            self.process_thread = threading.Thread(
                target=self._process_loop,
                name="UDP_Processor",
                daemon=True
            )
            self.process_thread.start()
            
            logger.info(f"UDP接收器已启动，监听 {self.host}:{self.port} (高频15KHz优化)")
            
        except Exception as e:
            logger.error(f"启动UDP接收器失败: {e}")
            raise
    
    async def stop(self):
        """停止UDP接收器"""
        if not self.running:
            return
        
        self.running = False
        
        # 等待线程结束
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1.0)
        
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=1.0)
        
        # 关闭socket
        if self.socket:
            self.socket.close()
            self.socket = None
        
        if self.send_socket:
            self.send_socket.close()
            self.send_socket = None
        
        logger.info("UDP接收器已停止")
    
    def _high_speed_receive_loop(self):
        """专用高速接收循环 - 15KHz优化"""
        self.socket.settimeout(0.01)  # 10ms超时，快速检查running状态
        
        logger.info("高速UDP接收线程已启动")
        
        while self.running:
            try:
                # 批量接收优化 - 关键性能点
                batch_count = 0
                batch_start = time.perf_counter()
                
                # 在10ms内尽可能多接收数据包
                while batch_count < 500 and (time.perf_counter() - batch_start) < 0.01:
                    try:
                        data, addr = self.socket.recvfrom(65536)  # 最大UDP包大小
                        
                        # 快速入队 - 避免锁争用
                        if len(self.data_queue) < self.data_queue.maxlen:
                            self.data_queue.append((data, addr))
                        else:
                            # 队列满，丢弃数据
                            self.drop_count += 1
                        
                        self.receive_count += 1
                        batch_count += 1
                        
                    except socket.timeout:
                        # 超时正常，继续下一批
                        break
                    except OSError as e:
                        if self.running:
                            logger.error(f"socket接收错误: {e}")
                        break
                
            except Exception as e:
                if self.running:
                    logger.error(f"接收循环出错: {e}")
                    time.sleep(0.01)
        
        logger.info("高速UDP接收线程已退出")
    
    def _process_loop(self):
        """数据处理循环 - 批量处理优化"""
        logger.info("UDP数据处理线程已启动")
        
        while self.running:
            try:
                # 批量处理数据
                batch_size = min(200, len(self.data_queue))
                
                if batch_size == 0:
                    time.sleep(0.001)  # 1ms等待
                    continue
                
                # 批量取出数据进行处理
                batch_data = []
                for _ in range(batch_size):
                    if self.data_queue:
                        batch_data.append(self.data_queue.popleft())
                
                # 批量处理
                for data, addr in batch_data:
                    self._on_data_received(data, addr)
                    self.process_count += 1
                
                # 性能报告
                self._report_performance()
                
                # 根据队列情况调整处理频率
                queue_size = len(self.data_queue)
                if queue_size > 1000:
                    # 队列积压严重，继续处理
                    continue
                elif queue_size > 200:
                    time.sleep(0.0001)  # 0.1ms
                else:
                    time.sleep(0.001)   # 1ms
                    
            except Exception as e:
                if self.running:
                    logger.error(f"数据处理循环出错: {e}")
                    time.sleep(0.01)
        
        logger.info("UDP数据处理线程已退出")
    
    def _report_performance(self):
        """性能统计报告"""
        now = time.time()
        if now - self.last_report_time >= 2.0:  # 每2秒报告一次
            elapsed = now - self.last_report_time
            receive_rate = self.receive_count / elapsed
            process_rate = self.process_count / elapsed
            drop_rate = self.drop_count / elapsed if self.drop_count > 0 else 0
            queue_size = len(self.data_queue)
            
            logger.info(f"UDP高频统计 - 接收:{receive_rate:.0f}/s, 处理:{process_rate:.0f}/s, "
                       f"丢弃:{drop_rate:.0f}/s, 队列:{queue_size}/{self.data_queue.maxlen}")
            
            # 重置计数器
            self.receive_count = 0
            self.process_count = 0
            self.drop_count = 0
            self.last_report_time = now
    
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
        parser_stats = self.parser.get_statistics()
        parser_stats.update({
            'queue_size': len(self.data_queue),
            'queue_max_size': self.data_queue.maxlen,
            'is_running': self.running,
            'receive_thread_alive': self.receive_thread.is_alive() if self.receive_thread else False,
            'process_thread_alive': self.process_thread.is_alive() if self.process_thread else False,
        })
        return parser_stats
    
    def reset_statistics(self):
        """重置统计信息"""
        self.parser.reset_statistics()
        self.receive_count = 0
        self.process_count = 0
        self.drop_count = 0
    
    async def send_config(self, kp: float, ki: float, kd: float, 
                         kp1: float, ki1: float, kd1: float,
                         target_addr: tuple = ('192.168.1.100', 8889)):
        """
        发送配置数据到下位机
        
        Args:
            kp, ki, kd, kp1, ki1, kd1: PID参数
            target_addr: 目标地址 (ip, port)
        """
        if not self.running or not self.send_socket:
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
            
            # 使用专用发送socket发送数据
            self.send_socket.sendto(packet_data, target_addr)
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
