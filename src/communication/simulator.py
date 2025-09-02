# -*- coding: utf-8 -*-
"""
下位机模拟器
用于测试UDP通信和协议解析
"""

import asyncio
import socket
import struct
import time
import math
import logging
from utils.crc import append_crc

logger = logging.getLogger(__name__)


class MotorSimulator:
    """
    电机控制板模拟器
    模拟发送电机采样数据和配置数据
    """
    
    def __init__(self, target_host: str = '127.0.0.1', target_port: int = 8888):
        """
        初始化模拟器
        
        Args:
            target_host: 目标主机地址
            target_port: 目标端口
        """
        self.target_host = target_host
        self.target_port = target_port
        self.socket = None
        self.running = False
        
        # 模拟参数
        self.sequence = 0
        self.sample_rate = 1000  # Hz
        self.send_interval = 0.01  # 10ms发送一次
        
        # 时间基准
        self.curr_tick = 0
    
    async def start(self):
        """启动模拟器"""
        if self.running:
            return
        
        try:
            # 创建UDP套接字
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            self.running = True
            logger.info(f"模拟器已启动，目标: {self.target_host}:{self.target_port}")
            
            # 启动发送任务
            await asyncio.gather(
                self._send_motor_data_task(),
            )
            
        except Exception as e:
            logger.error(f"启动模拟器失败: {e}")
            await self.stop()
    
    async def stop(self):
        """停止模拟器"""
        self.running = False
        
        if self.socket:
            self.socket.close()
            self.socket = None
        
        logger.info("模拟器已停止")
    
    async def _send_motor_data_task(self):
        """发送电机数据任务"""
        while self.running:
            try:
                # 生成模拟数据
                motor_data = self._generate_motor_data()
                
                # 创建数据包
                packet = self._create_motor_packet(motor_data)
                
                # 发送数据包
                self.socket.sendto(packet, (self.target_host, self.target_port))
                
                # 等待下次发送
                await asyncio.sleep(self.send_interval)

            except Exception as e:
                logger.error(f"发送电机数据失败: {e}")
                await asyncio.sleep(1.0)
    
    def _generate_motor_data(self) -> list:
        """
        生成模拟的电机数据
        
        Returns:
            10个通道的数据值列表
        """
        # 生成带有噪声的正弦波数据
        data = []
        
        for i in range(10):
            # 基础频率和幅值
            freq = 50 + i * 5  # 50Hz, 55Hz, 60Hz...
            amplitude = 100 + i * 20
            offset = i * 10
            
            # 正弦波 + 噪声
            value = (amplitude * math.sin(2 * math.pi * freq * self.curr_tick) + 
                    offset)  # 5%噪声
            
            data.append(value)

        self.curr_tick += 0.0001
        return data
    
    def _create_motor_packet(self, data: list, use_float: bool = True) -> bytes:
        """
        创建电机数据包
        
        Args:
            data: 10个通道的数据
            use_float: 是否使用float32格式
            
        Returns:
            完整的UDP数据包
        """
        # 选择数据包类型和格式
        if use_float:
            packet_type = 0xA2
            format_str = '<B10f'  # uint8 + 10个float32
            values = [packet_type] + data
        else:
            packet_type = 0xA1
            format_str = '<B10H'  # uint8 + 10个uint16
            # 将float转换为uint16 (0-65535范围)
            uint16_data = [max(0, min(65535, int(v + 32768))) for v in data]
            values = [packet_type] + uint16_data
        
        # 打包子数据包
        sub_packet = struct.pack(format_str, *values)

        # 创建主数据包
        return self._create_main_packet(sub_packet)
    
    def _create_config_packet(self) -> bytes:
        """
        创建配置数据包
        
        Returns:
            完整的UDP数据包
        """
        # 配置上传数据包 (0xF4)
        packet_type = 0xF4
        
        # 打包配置数据
        sub_packet = struct.pack('<B6f',
            packet_type,
            self.pid_config['kp'],
            self.pid_config['ki'],
            self.pid_config['kd'],
            self.pid_config['kp1'],
            self.pid_config['ki1'],
            self.pid_config['kd1']
        )
        
        # 创建主数据包
        return self._create_main_packet(sub_packet)
    
    def _create_main_packet(self, sub_packet: bytes) -> bytes:
        """
        创建主数据包
        
        Args:
            sub_packet: 子数据包内容
            
        Returns:
            完整的UDP数据包
        """
        # 包头
        header = 0x55AA
        
        # 剩余长度 (子数据包 + CRC)
        remaining_length = len(sub_packet) + 2
        
        # 序号
        sequence = self.sequence
        self.sequence = (self.sequence + 1) & 0xFFFF
        
        # 打包包头
        header_data = struct.pack('<HHH', header, remaining_length, sequence)
        
        # 组合数据 (包头 + 子数据包)
        packet_data = header_data + sub_packet
        
        # 添加CRC校验
        full_packet = append_crc(packet_data)
        
        return full_packet
    
    def update_pid_config(self, kp: float, ki: float, kd: float,
                         kp1: float, ki1: float, kd1: float):
        """
        更新PID配置
        
        Args:
            kp, ki, kd, kp1, ki1, kd1: PID参数
        """
        self.pid_config.update({
            'kp': kp, 'ki': ki, 'kd': kd,
            'kp1': kp1, 'ki1': ki1, 'kd1': kd1
        })
        
        logger.info(f"PID配置已更新: {self.pid_config}")
    
    def set_sample_rate(self, rate: float):
        """
        设置采样率
        
        Args:
            rate: 采样率 (Hz)
        """
        self.sample_rate = rate
        self.send_interval = 1.0 / rate
        logger.info(f"采样率设置为: {rate} Hz")
    
    def get_statistics(self) -> dict:
        """
        获取模拟器统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'running': self.running,
            'sequence': self.sequence,
            'sample_rate': self.sample_rate,
            'target': f"{self.target_host}:{self.target_port}",
            'uptime': time.time() - self.curr_tick if self.running else 0
        }


async def main():
    """模拟器主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='电机控制板模拟器')
    parser.add_argument('--host', default='127.0.0.1', help='目标主机地址')
    parser.add_argument('--port', type=int, default=8888, help='目标端口')
    parser.add_argument('--rate', type=float, default=10000, help='发送频率 (Hz)')
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建模拟器
    simulator = MotorSimulator(args.host, args.port)
    simulator.set_sample_rate(args.rate)
    
    try:
        logger.info("启动电机控制板模拟器...")
        logger.info(f"目标地址: {args.host}:{args.port}")
        logger.info(f"发送频率: {args.rate} Hz")
        logger.info("按 Ctrl+C 停止模拟器")
        
        await simulator.start()
        
    except KeyboardInterrupt:
        logger.info("用户中断，正在停止模拟器...")
    except Exception as e:
        logger.error(f"模拟器运行出错: {e}")
    finally:
        await simulator.stop()


if __name__ == "__main__":
    asyncio.run(main())
