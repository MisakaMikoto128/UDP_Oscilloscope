# -*- coding: utf-8 -*-
"""
示波器进程间通信模块
高性能的数据传输机制，专门用于卡方火箭电机控制器
"""

import logging
import multiprocessing as mp
import queue
import time
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class SampleData:
    """采样数据结构"""
    timestamp: float
    packet_type: int
    channels: List[float]


class ScopeDataSender:
    """示波器数据发送器（主进程端）"""
    
    def __init__(self, data_queue: mp.Queue):
        """
        初始化数据发送器
        
        Args:
            data_queue: 数据传输队列
        """
        self.data_queue = data_queue
        self.sent_count = 0
        self.drop_count = 0
        
    def send_sample(self, packet_type: int, channels: List[float]) -> bool:
        """
        发送采样数据
        
        Args:
            packet_type: 数据包类型
            channels: 通道数据列表
            
        Returns:
            是否发送成功
        """
        try:
            sample = SampleData(
                timestamp=time.time(),
                packet_type=packet_type,
                channels=channels.copy()  # 避免引用问题
            )
            
            # 非阻塞发送，保证主进程性能
            self.data_queue.put_nowait(sample)
            self.sent_count += 1
            return True
            
        except queue.Full:
            # 队列满时丢弃数据，记录统计
            self.drop_count += 1
            # if self.drop_count % 1000 == 0:  # 每1000次丢包记录一次
            #     logger.warning(f"数据队列满，已丢弃 {self.drop_count} 个数据包")
            return False
        except Exception as e:
            logger.error(f"发送采样数据失败: {e}")
            return False
    
    def get_stats(self) -> dict:
        """获取发送统计"""
        return {
            'sent_count': self.sent_count,
            'drop_count': self.drop_count,
            'queue_size': self.data_queue.qsize() if hasattr(self.data_queue, 'qsize') else -1
        }


class ScopeDataReceiver:
    """示波器数据接收器（示波器进程端）"""
    
    def __init__(self, data_queue: mp.Queue):
        """
        初始化数据接收器
        
        Args:
            data_queue: 数据传输队列
        """
        self.data_queue = data_queue
        self.received_count = 0
        self.last_receive_time = time.time()
        
    def receive_sample(self, timeout: float = 0.001) -> Optional[SampleData]:
        """
        接收采样数据
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            采样数据或None
        """
        try:
            sample = self.data_queue.get(timeout=timeout)
            self.received_count += 1
            self.last_receive_time = time.time()
            return sample
            
        except queue.Empty:
            return None
        except Exception as e:
            logger.error(f"接收采样数据失败: {e}")
            return None
    
    def receive_batch(self, max_count: int = 50, timeout: float = 0.001) -> List[SampleData]:
        """
        批量接收采样数据（提高性能）
        
        Args:
            max_count: 最大接收数量
            timeout: 单次接收超时时间
            
        Returns:
            采样数据列表
        """
        samples = []
        
        for _ in range(max_count):
            sample = self.receive_sample(timeout)
            if sample is None:
                break
            samples.append(sample)
        
        return samples
    
    def get_stats(self) -> dict:
        """获取接收统计"""
        current_time = time.time()
        time_since_last = current_time - self.last_receive_time
        
        return {
            'received_count': self.received_count,
            'time_since_last_receive': time_since_last,
            'queue_size': self.data_queue.qsize() if hasattr(self.data_queue, 'qsize') else -1
        }


class ScopeIPC:
    """示波器进程间通信管理器"""
    
    def __init__(self, queue_size: int = 10000):
        """
        初始化IPC管理器
        
        Args:
            queue_size: 队列大小（15KHz下约667ms缓冲）
        """
        # 创建高性能数据队列
        self.data_queue = mp.Queue(maxsize=queue_size)
        
        # 进程控制事件
        self.shutdown_event = mp.Event()
        self.scope_ready_event = mp.Event()
        
        # 创建发送器和接收器
        self.sender = ScopeDataSender(self.data_queue)
        self.receiver = ScopeDataReceiver(self.data_queue)
        
        logger.info(f"示波器IPC管理器初始化完成，队列大小: {queue_size}")
    
    def get_sender(self) -> ScopeDataSender:
        """获取数据发送器（主进程使用）"""
        return self.sender
    
    def get_receiver(self) -> ScopeDataReceiver:
        """获取数据接收器（示波器进程使用）"""
        return self.receiver
    
    def signal_shutdown(self):
        """发送关闭信号"""
        self.shutdown_event.set()
        logger.info("已发送示波器进程关闭信号")
    
    def is_shutdown_requested(self) -> bool:
        """检查是否请求关闭"""
        return self.shutdown_event.is_set()
    
    def signal_scope_ready(self):
        """示波器进程就绪信号"""
        self.scope_ready_event.set()
        logger.info("示波器进程已就绪")
    
    def wait_scope_ready(self, timeout: float = 10.0) -> bool:
        """等待示波器进程就绪"""
        return self.scope_ready_event.wait(timeout)
    
    def get_combined_stats(self) -> dict:
        """获取综合统计信息"""
        sender_stats = self.sender.get_stats()
        receiver_stats = self.receiver.get_stats()
        
        return {
            'sender': sender_stats,
            'receiver': receiver_stats,
            'queue_health': 'good' if sender_stats['drop_count'] < 100 else 'warning'
        }
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清空队列
            while not self.data_queue.empty():
                try:
                    self.data_queue.get_nowait()
                except queue.Empty:
                    break
                except Exception:
                    break
            
            logger.info("示波器IPC资源已清理")
        except Exception as e:
            logger.error(f"清理IPC资源失败: {e}")


def create_scope_ipc(queue_size: int = 10000) -> ScopeIPC:
    """
    创建示波器IPC管理器的工厂函数
    
    Args:
        queue_size: 队列大小
        
    Returns:
        ScopeIPC实例
    """
    return ScopeIPC(queue_size)
