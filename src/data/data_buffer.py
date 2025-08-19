# -*- coding: utf-8 -*-
"""
数据缓存模块
实现高效的环形缓冲区用于示波器数据存储
"""

import numpy as np
import logging
from typing import Tuple, Optional
from collections import deque
import threading

logger = logging.getLogger(__name__)


class RingBuffer:
    """
    高效的环形缓冲区实现
    支持多通道数据存储，自动管理内存使用
    """
    
    def __init__(self, n_channels: int, max_bytes: int = 1024 * 1024 * 1024):
        """
        初始化环形缓冲区
        
        Args:
            n_channels: 通道数量
            max_bytes: 最大内存使用量（字节）
        """
        self.n_channels = n_channels
        self.max_bytes = max_bytes
        
        # 估算每个样本的字节数（float32 * 通道数）
        self.bytes_per_sample = n_channels * 4
        self.max_samples = max_bytes // self.bytes_per_sample
        
        # 为每个通道创建缓冲区
        self.buffers = []
        self.write_positions = []
        self.sample_counts = []
        
        for i in range(n_channels):
            # 使用numpy数组作为底层存储
            buffer = np.zeros(self.max_samples, dtype=np.float32)
            self.buffers.append(buffer)
            self.write_positions.append(0)
            self.sample_counts.append(0)
        
        # 线程锁保证线程安全
        self._lock = threading.RLock()
        
        logger.info(f"环形缓冲区已初始化: {n_channels}通道, "
                   f"最大样本数: {self.max_samples:,}, "
                   f"内存使用: {max_bytes / 1024 / 1024:.1f}MB")
    
    def append(self, channel: int, values: Tuple[float, ...]):
        """
        向指定通道添加数据
        
        Args:
            channel: 通道索引
            values: 数据值元组
        """
        if not (0 <= channel < self.n_channels):
            return
        
        with self._lock:
            buffer = self.buffers[channel]
            write_pos = self.write_positions[channel]
            sample_count = self.sample_counts[channel]
            
            for value in values:
                buffer[write_pos] = value
                write_pos = (write_pos + 1) % self.max_samples
                sample_count = min(sample_count + 1, self.max_samples)
            
            self.write_positions[channel] = write_pos
            self.sample_counts[channel] = sample_count
    
    def view_tail(self, channel: int, max_points: int) -> np.ndarray:
        """
        获取指定通道的最新数据视图
        
        Args:
            channel: 通道索引
            max_points: 最大点数
            
        Returns:
            数据数组
        """
        if not (0 <= channel < self.n_channels):
            return np.array([], dtype=np.float32)
        
        with self._lock:
            buffer = self.buffers[channel]
            write_pos = self.write_positions[channel]
            sample_count = self.sample_counts[channel]
            
            if sample_count == 0:
                return np.array([], dtype=np.float32)
            
            # 计算实际返回的点数
            actual_points = min(max_points, sample_count)
            
            if sample_count < self.max_samples:
                # 缓冲区未满，直接返回从开始到写入位置的数据
                start_idx = max(0, write_pos - actual_points)
                return buffer[start_idx:write_pos].copy()
            else:
                # 缓冲区已满，需要处理环形结构
                if actual_points >= self.max_samples:
                    # 返回整个缓冲区
                    result = np.empty(self.max_samples, dtype=np.float32)
                    result[:self.max_samples - write_pos] = buffer[write_pos:]
                    result[self.max_samples - write_pos:] = buffer[:write_pos]
                    return result
                else:
                    # 返回最新的actual_points个点
                    result = np.empty(actual_points, dtype=np.float32)
                    start_pos = (write_pos - actual_points) % self.max_samples
                    
                    if start_pos + actual_points <= self.max_samples:
                        # 数据连续
                        result[:] = buffer[start_pos:start_pos + actual_points]
                    else:
                        # 数据跨越环形边界
                        first_part = self.max_samples - start_pos
                        result[:first_part] = buffer[start_pos:]
                        result[first_part:] = buffer[:actual_points - first_part]
                    
                    return result
    
    def view_range(self, channel: int, start_idx: int, end_idx: int) -> np.ndarray:
        """
        获取指定通道的指定范围数据
        
        Args:
            channel: 通道索引
            start_idx: 起始索引（相对于最早的数据）
            end_idx: 结束索引（相对于最早的数据）
            
        Returns:
            数据数组
        """
        if not (0 <= channel < self.n_channels):
            return np.array([], dtype=np.float32)
        
        with self._lock:
            buffer = self.buffers[channel]
            write_pos = self.write_positions[channel]
            sample_count = self.sample_counts[channel]
            
            if sample_count == 0 or start_idx >= sample_count:
                return np.array([], dtype=np.float32)
            
            # 调整索引范围
            start_idx = max(0, start_idx)
            end_idx = min(sample_count, end_idx)
            
            if start_idx >= end_idx:
                return np.array([], dtype=np.float32)
            
            length = end_idx - start_idx
            result = np.empty(length, dtype=np.float32)
            
            if sample_count < self.max_samples:
                # 缓冲区未满
                result[:] = buffer[start_idx:end_idx]
            else:
                # 缓冲区已满，需要计算实际位置
                actual_start = (write_pos + start_idx) % self.max_samples
                
                if actual_start + length <= self.max_samples:
                    # 数据连续
                    result[:] = buffer[actual_start:actual_start + length]
                else:
                    # 数据跨越环形边界
                    first_part = self.max_samples - actual_start
                    result[:first_part] = buffer[actual_start:]
                    result[first_part:] = buffer[:length - first_part]
            
            return result
    
    def get_sample_count(self, channel: int) -> int:
        """
        获取指定通道的样本数量
        
        Args:
            channel: 通道索引
            
        Returns:
            样本数量
        """
        if not (0 <= channel < self.n_channels):
            return 0
        
        with self._lock:
            return self.sample_counts[channel]
    
    def get_memory_usage(self) -> dict:
        """
        获取内存使用情况
        
        Returns:
            内存使用信息字典
        """
        with self._lock:
            total_samples = sum(self.sample_counts)
            used_bytes = total_samples * 4  # float32
            usage_percent = (used_bytes / self.max_bytes) * 100
            
            return {
                'total_samples': total_samples,
                'used_bytes': used_bytes,
                'max_bytes': self.max_bytes,
                'usage_percent': usage_percent,
                'channels': [
                    {
                        'channel': i,
                        'samples': self.sample_counts[i],
                        'bytes': self.sample_counts[i] * 4
                    }
                    for i in range(self.n_channels)
                ]
            }
    
    def clear(self, channel: Optional[int] = None):
        """
        清空缓冲区数据
        
        Args:
            channel: 指定通道索引，None表示清空所有通道
        """
        with self._lock:
            if channel is not None:
                if 0 <= channel < self.n_channels:
                    self.write_positions[channel] = 0
                    self.sample_counts[channel] = 0
                    self.buffers[channel].fill(0)
            else:
                for i in range(self.n_channels):
                    self.write_positions[i] = 0
                    self.sample_counts[i] = 0
                    self.buffers[i].fill(0)
    
    def get_latest_value(self, channel: int) -> Optional[float]:
        """
        获取指定通道的最新值
        
        Args:
            channel: 通道索引
            
        Returns:
            最新值，如果没有数据则返回None
        """
        if not (0 <= channel < self.n_channels):
            return None
        
        with self._lock:
            sample_count = self.sample_counts[channel]
            if sample_count == 0:
                return None
            
            write_pos = self.write_positions[channel]
            # 最新值在写入位置的前一个位置
            latest_pos = (write_pos - 1) % self.max_samples
            return float(self.buffers[channel][latest_pos])
    
    def get_statistics(self, channel: int) -> dict:
        """
        获取指定通道的统计信息
        
        Args:
            channel: 通道索引
            
        Returns:
            统计信息字典
        """
        if not (0 <= channel < self.n_channels):
            return {}
        
        with self._lock:
            sample_count = self.sample_counts[channel]
            if sample_count == 0:
                return {
                    'count': 0,
                    'min': 0.0,
                    'max': 0.0,
                    'mean': 0.0,
                    'std': 0.0
                }
            
            # 获取所有有效数据
            data = self.view_tail(channel, sample_count)
            
            return {
                'count': sample_count,
                'min': float(np.min(data)),
                'max': float(np.max(data)),
                'mean': float(np.mean(data)),
                'std': float(np.std(data))
            }
