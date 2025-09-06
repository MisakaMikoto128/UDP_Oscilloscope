# -*- coding: utf-8 -*-
"""
数据缓存模块
实现高效的环形缓冲区用于示波器数据存储
"""

import numpy as np
import logging
from typing import Tuple, Optional, Dict, List
import threading
from pathlib import Path
from datetime import datetime

from .persistence_manager import WaveformPersistence

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

        # 持久化功能
        self._persistence_manager = WaveformPersistence()
        self.persistence_manager = self._persistence_manager

        logger.info(f"环形缓冲区已初始化: {n_channels}通道, "
                   f"最大样本数: {self.max_samples:,}, "
                   f"内存使用: {max_bytes / 1024 / 1024:.1f}MB")
    
    def append_batch(self, channel_values: List[float]):
        """
        批量添加所有通道的数据（优化版本）

        Args:
            channel_values: 所有通道的数据列表，按通道顺序 [ch0_value, ch1_value, ch2_value, ...]
        """
        if len(channel_values) != self.n_channels:
            raise ValueError(f"数据长度 {len(channel_values)} 与通道数 {self.n_channels} 不匹配")

        with self._lock:
            # 为每个通道添加一个数据点
            for channel, value in enumerate(channel_values):
                buffer = self.buffers[channel]
                write_pos = self.write_positions[channel]
                sample_count = self.sample_counts[channel]

                # 添加单个数据点
                buffer[write_pos] = float(value)

                # 更新位置和计数
                new_write_pos = (write_pos + 1) % self.max_samples
                self.write_positions[channel] = new_write_pos
                self.sample_counts[channel] = min(sample_count + 1, self.max_samples)

            # 持久化存储（批量保存所有通道）
            self._persistence_manager.push_save_data(channel_values)

    def append(self, channel: int, values: Tuple[float, ...]):
        """
        向指定通道添加数据
        
        Args:
            channel: 通道索引
            values: 数据值元组
        """
        if not (0 <= channel < self.n_channels):
            return

        # 转换为numpy数组以利用向量化操作
        if isinstance(values, (list, tuple)):
            values_array = np.array(values, dtype=np.float32)
        else:
            values_array = np.asarray(values, dtype=np.float32)

        if values_array.size == 0:
            return

        with self._lock:
            buffer = self.buffers[channel]
            write_pos = self.write_positions[channel]
            sample_count = self.sample_counts[channel]
            n_values = len(values_array)

            # 优化：批量写入，减少循环开销
            if write_pos + n_values <= self.max_samples:
                # 数据不跨越环形边界，直接批量写入
                buffer[write_pos:write_pos + n_values] = values_array
                new_write_pos = (write_pos + n_values) % self.max_samples
            else:
                # 数据跨越环形边界，分两次写入
                first_part = self.max_samples - write_pos
                buffer[write_pos:] = values_array[:first_part]
                buffer[:n_values - first_part] = values_array[first_part:]
                new_write_pos = n_values - first_part

            # 更新位置和计数
            self.write_positions[channel] = new_write_pos
            self.sample_counts[channel] = min(sample_count + n_values, self.max_samples)
    
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

    def view_all(self, channel: int) -> np.ndarray:
        """
        获取指定通道的所有数据

        Args:
            channel: 通道索引

        Returns:
            数据数组
        """
        if not (0 <= channel < self.n_channels):
            return np.array([], dtype=np.float32)

        with self._lock:
            sample_count = self.sample_counts[channel]
            if sample_count == 0:
                return np.array([], dtype=np.float32)

            buffer = self.buffers[channel]
            write_pos = self.write_positions[channel]

            if sample_count < self.max_samples:
                # 缓冲区未满，直接返回有效数据
                return buffer[:sample_count].copy()
            else:
                # 缓冲区已满，需要重新排列
                result = np.empty(sample_count, dtype=np.float32)
                result[:self.max_samples-write_pos] = buffer[write_pos:]
                result[self.max_samples-write_pos:] = buffer[:write_pos]
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

    # ==================== 持久化功能接口 ====================

    def start_recording(self, channel_config: List[Dict], sample_rate: int = 0, filename: Optional[str] = None) -> Path:
        """
        开始录制数据到文件

        Args:
            filename: 自定义文件名，None则自动生成

        Returns:
            录制文件路径
        """
        return self._persistence_manager.start_recording(channel_config, sample_rate, filename, self.n_channels)

    def stop_recording(self):
        """停止录制数据"""
        self._persistence_manager.stop_recording()

    def is_recording(self) -> bool:
        """检查是否正在录制"""
        return self._persistence_manager.is_recording()

    def get_recording_file(self) -> Optional[Path]:
        """获取当前录制文件路径"""
        return self._persistence_manager.get_current_file()

    def load_waveform_data(self, filepath: Path) -> Dict[int, np.ndarray]:
        """
        从文件加载波形数据到内存

        Args:
            filepath: 文件路径

        Returns:
            字典，键为通道索引，值为数据数组
        """
        return self._persistence_manager.load_data(filepath)

    @staticmethod
    def create_from_file(filepath: Path) -> 'RingBuffer':
        """
        从HDF5文件创建一个新的RingBuffer实例，自动设置合适的缓存大小

        这个方法会创建一个独立的RingBuffer实例用于预览，不会影响实时数据缓冲区

        Args:
            filepath: HDF5文件路径

        Returns:
            加载了文件数据的新RingBuffer实例
        """
        try:
            import h5py

            # 获取文件信息
            with h5py.File(filepath, 'r') as f:
                # 读取元数据
                metadata = f.get('metadata', {})
                n_channels = metadata.attrs.get('n_channels', 4)

                # 估算数据大小
                total_samples = 0
                for ch in range(n_channels):
                    dataset_name = f'channel_{ch:02d}'
                    if dataset_name in f:
                        total_samples = max(total_samples, len(f[dataset_name]))

                # 根据数据量自动设置缓存大小
                # 每个样本约4字节(float32)，加上一些余量
                estimated_bytes = total_samples * n_channels * 4 * 2  # 2倍余量
                # 最小10MB，最大1GB，确保能容纳所有数据
                min_size = 10 * 1024 * 1024
                max_size = 1024 * 1024 * 1024
                buffer_size = max(min_size, min(estimated_bytes, max_size))

                # 如果估算的大小小于最小值，但数据量很大，则适当增加
                if estimated_bytes < min_size and total_samples > 1000:
                    buffer_size = min(estimated_bytes * 5, max_size)  # 5倍余量

                logger.info(f"为预览创建RingBuffer: {n_channels}通道, {total_samples}样本, {buffer_size//1024//1024}MB缓存")

                # 创建新的RingBuffer实例
                preview_buffer = RingBuffer(
                    n_channels=n_channels,
                    max_bytes=buffer_size
                )

                # 加载数据
                for ch in range(n_channels):
                    dataset_name = f'channel_{ch:02d}'
                    if dataset_name in f:
                        data = f[dataset_name][:]
                        preview_buffer.append(ch, data)

                logger.info(f"成功创建预览RingBuffer，加载了{total_samples}样本")
                return preview_buffer

        except Exception as e:
            logger.error(f"从文件创建RingBuffer失败 {filepath}: {e}")
            # 返回一个空的默认buffer
            return RingBuffer(n_channels=4, max_bytes=10*1024*1024)

    def reload_to_buffer(self, filepath: Path):
        """
        从文件重新加载数据到RingBuffer

        Args:
            filepath: 文件路径
        """
        data_dict = self.load_waveform_data(filepath)

        # 清空当前缓冲区
        self.clear()

        # 重新加载数据
        with self._lock:
            for channel, data in data_dict.items():
                if 0 <= channel < self.n_channels and len(data) > 0:
                    # 如果数据太大，只取最新的部分
                    if len(data) > self.max_samples:
                        data = data[-self.max_samples:]

                    # 直接写入缓冲区
                    n_values = len(data)
                    self.buffers[channel][:n_values] = data
                    self.write_positions[channel] = n_values % self.max_samples
                    self.sample_counts[channel] = min(n_values, self.max_samples)

        logger.info(f"已从文件重新加载数据: {filepath}")

    def export_data(self, formats: List[str], output_dir: Optional[Path] = None,
                   filename_prefix: str = "ringbuffer_export") -> Dict[str, Path]:
        """
        导出当前缓冲区数据为多种格式
        注意：HDF5格式通过录制功能实现，其他格式通过转换实现

        Args:
            formats: 要导出的格式列表 ['csv', 'excel', 'matlab', 'hdf5']
            output_dir: 输出目录，如果为None则使用默认data目录
            filename_prefix: 文件名前缀

        Returns:
            格式到输出文件路径的映射
        """
        try:
            if output_dir is None:
                output_dir = Path("data")
            output_dir.mkdir(parents=True, exist_ok=True)

            results = {}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 创建临时HDF5文件（通过录制功能）
            temp_h5_file = None
            if formats:  # 如果有任何格式需要导出
                # 使用录制功能创建HDF5文件
                self.start_recording(f"{filename_prefix}_{timestamp}_temp")

                # 获取所有通道的最大样本数
                max_samples = max(self.get_sample_count(ch) for ch in range(self.n_channels))

                # 逐个样本写入所有通道数据
                for i in range(max_samples):
                    channel_values = []
                    for ch in range(self.n_channels):
                        data = self.view_all(ch)
                        if i < len(data):
                            channel_values.append(data[i])
                        else:
                            channel_values.append(0.0)

                    self.persistence_manager.push_save_data(channel_values)

                self.stop_recording()
                temp_h5_file = self.persistence_manager.get_current_file()

            # 导出各种格式
            for fmt in formats:
                try:
                    fmt_lower = fmt.lower()

                    if fmt_lower == 'hdf5':
                        # HDF5格式直接重命名临时文件
                        output_path = output_dir / f"{filename_prefix}_{timestamp}.h5"
                        if temp_h5_file and temp_h5_file != output_path:
                            import shutil
                            shutil.move(temp_h5_file, output_path)
                            temp_h5_file = output_path  # 更新引用
                        elif temp_h5_file:
                            output_path = temp_h5_file
                        results['hdf5'] = output_path

                    elif fmt_lower == 'csv':
                        if temp_h5_file:
                            output_path = output_dir / f"{filename_prefix}_{timestamp}.csv"
                            results['csv'] = self.persistence_manager.export_to_csv(temp_h5_file, output_path)

                    elif fmt_lower in ['excel', 'xlsx']:
                        if temp_h5_file:
                            output_path = output_dir / f"{filename_prefix}_{timestamp}.xlsx"
                            results['excel'] = self.persistence_manager.export_to_excel(temp_h5_file, output_path)

                    elif fmt_lower in ['matlab', 'mat']:
                        if temp_h5_file:
                            output_path = output_dir / f"{filename_prefix}_{timestamp}.mat"
                            results['matlab'] = self.persistence_manager.export_to_matlab(temp_h5_file, output_path)

                    else:
                        logger.warning(f"不支持的导出格式: {fmt}")

                except Exception as e:
                    logger.error(f"导出格式 {fmt} 失败: {e}")

            # 清理临时文件（如果不需要HDF5格式）
            if temp_h5_file and temp_h5_file.exists() and 'hdf5' not in [f.lower() for f in formats]:
                temp_h5_file.unlink()

            logger.info(f"数据导出完成，共导出 {len(results)} 种格式")
            return results

        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            return {}


