# -*- coding: utf-8 -*-
"""
永久存储模块
实现数据的持久化存储功能
"""

import h5py
import numpy as np
import logging
import threading
import queue
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PersistentStorage:
    """
    永久存储管理器
    使用HDF5格式存储示波器数据
    """
    
    def __init__(self, file_path: str, n_channels: int, enabled: bool = False):
        """
        初始化永久存储
        
        Args:
            file_path: 存储文件路径
            n_channels: 通道数量
            enabled: 是否启用存储
        """
        self.file_path = Path(file_path)
        self.n_channels = n_channels
        self.enabled = enabled
        
        # 存储队列和线程
        self._storage_queue = queue.Queue(maxsize=1000)
        self._storage_thread = None
        self._stop_event = threading.Event()
        
        # HDF5文件对象
        self._h5_file = None
        self._datasets = {}
        
        if self.enabled:
            self._start_storage_thread()
    
    def _start_storage_thread(self):
        """启动存储线程"""
        if self._storage_thread is not None:
            return
        
        try:
            # 确保目录存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 打开HDF5文件
            self._h5_file = h5py.File(self.file_path, 'a')
            
            # 创建或获取数据集
            self._create_datasets()
            
            # 启动存储线程
            self._stop_event.clear()
            self._storage_thread = threading.Thread(
                target=self._storage_worker,
                name="PersistentStorage",
                daemon=True
            )
            self._storage_thread.start()
            
            logger.info(f"永久存储已启动: {self.file_path}")
            
        except Exception as e:
            logger.error(f"启动永久存储失败: {e}")
            self.enabled = False
    
    def _create_datasets(self):
        """创建HDF5数据集"""
        # 创建元数据组
        if 'metadata' not in self._h5_file:
            metadata_group = self._h5_file.create_group('metadata')
            metadata_group.attrs['created_time'] = datetime.now().isoformat()
            metadata_group.attrs['n_channels'] = self.n_channels
            metadata_group.attrs['version'] = '1.0.0'
        
        # 为每个通道创建数据集
        for channel in range(self.n_channels):
            dataset_name = f'channel_{channel:02d}'
            
            if dataset_name not in self._h5_file:
                # 创建可扩展的数据集
                dataset = self._h5_file.create_dataset(
                    dataset_name,
                    shape=(0,),
                    maxshape=(None,),
                    dtype=np.float32,
                    chunks=True,
                    compression='gzip',
                    compression_opts=1  # 轻度压缩，平衡速度和大小
                )
                dataset.attrs['channel_name'] = f'CH{channel + 1}'
                dataset.attrs['unit'] = 'V'
                dataset.attrs['scale_factor'] = 1.0
            else:
                dataset = self._h5_file[dataset_name]
            
            self._datasets[channel] = dataset
    
    def _storage_worker(self):
        """存储工作线程"""
        batch_data = {ch: [] for ch in range(self.n_channels)}
        last_flush_time = time.time()
        flush_interval = 1.0  # 每秒刷新一次
        
        while not self._stop_event.is_set():
            try:
                # 从队列获取数据，设置超时避免阻塞
                try:
                    item = self._storage_queue.get(timeout=0.1)
                except queue.Empty:
                    # 检查是否需要刷新批量数据
                    current_time = time.time()
                    if (current_time - last_flush_time) > flush_interval:
                        self._flush_batch_data(batch_data)
                        last_flush_time = current_time
                    continue
                
                if item is None:  # 停止信号
                    break
                
                channel, values = item
                if channel in batch_data:
                    batch_data[channel].extend(values)
                
                # 检查批量大小或时间间隔
                total_samples = sum(len(data) for data in batch_data.values())
                current_time = time.time()
                
                if (total_samples >= 1000 or 
                    (current_time - last_flush_time) > flush_interval):
                    self._flush_batch_data(batch_data)
                    last_flush_time = current_time
                
                self._storage_queue.task_done()
                
            except Exception as e:
                logger.error(f"存储线程错误: {e}")
        
        # 刷新剩余数据
        self._flush_batch_data(batch_data)
        logger.info("存储线程已停止")
    
    def _flush_batch_data(self, batch_data: Dict[int, list]):
        """刷新批量数据到文件"""
        if not self._h5_file:
            return
        
        try:
            for channel, values in batch_data.items():
                if values and channel in self._datasets:
                    dataset = self._datasets[channel]
                    
                    # 扩展数据集
                    old_size = dataset.shape[0]
                    new_size = old_size + len(values)
                    dataset.resize((new_size,))
                    
                    # 写入数据
                    dataset[old_size:new_size] = np.array(values, dtype=np.float32)
            
            # 清空批量数据
            for channel in batch_data:
                batch_data[channel].clear()
            
            # 刷新到磁盘
            self._h5_file.flush()
            
        except Exception as e:
            logger.error(f"刷新数据到文件失败: {e}")
    
    def store_data(self, channel: int, values: list):
        """
        存储数据到永久存储
        
        Args:
            channel: 通道索引
            values: 数据值列表
        """
        if not self.enabled or not values:
            return
        
        try:
            # 非阻塞方式添加到队列
            self._storage_queue.put_nowait((channel, values))
        except queue.Full:
            logger.warning("存储队列已满，丢弃数据")
    
    def stop(self):
        """停止永久存储"""
        if not self.enabled or self._storage_thread is None:
            return
        
        try:
            # 发送停止信号
            self._stop_event.set()
            self._storage_queue.put_nowait(None)
            
            # 等待线程结束
            if self._storage_thread.is_alive():
                self._storage_thread.join(timeout=5.0)
            
            # 关闭HDF5文件
            if self._h5_file:
                self._h5_file.close()
                self._h5_file = None
            
            self._storage_thread = None
            self._datasets.clear()
            
            logger.info("永久存储已停止")
            
        except Exception as e:
            logger.error(f"停止永久存储时出错: {e}")
    
    def get_file_info(self) -> Dict[str, Any]:
        """
        获取存储文件信息
        
        Returns:
            文件信息字典
        """
        if not self.file_path.exists():
            return {'exists': False}
        
        try:
            file_size = self.file_path.stat().st_size
            
            info = {
                'exists': True,
                'path': str(self.file_path),
                'size_bytes': file_size,
                'size_mb': file_size / (1024 * 1024),
                'channels': {}
            }
            
            if self._h5_file:
                # 获取每个通道的数据量
                for channel in range(self.n_channels):
                    dataset_name = f'channel_{channel:02d}'
                    if dataset_name in self._h5_file:
                        dataset = self._h5_file[dataset_name]
                        info['channels'][channel] = {
                            'samples': dataset.shape[0],
                            'size_bytes': dataset.size * 4  # float32
                        }
            
            return info
            
        except Exception as e:
            logger.error(f"获取文件信息失败: {e}")
            return {'exists': True, 'error': str(e)}
    
    def export_data(self, output_path: str, channel: Optional[int] = None,
                   start_time: Optional[float] = None, 
                   end_time: Optional[float] = None) -> bool:
        """
        导出数据到CSV文件
        
        Args:
            output_path: 输出文件路径
            channel: 指定通道，None表示所有通道
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            
        Returns:
            是否导出成功
        """
        if not self._h5_file:
            logger.error("HDF5文件未打开")
            return False
        
        try:
            import pandas as pd
            
            # 准备数据
            data_dict = {}
            
            channels_to_export = [channel] if channel is not None else range(self.n_channels)
            
            for ch in channels_to_export:
                dataset_name = f'channel_{ch:02d}'
                if dataset_name in self._h5_file:
                    dataset = self._h5_file[dataset_name]
                    
                    # 读取数据
                    if start_time is not None or end_time is not None:
                        # TODO: 实现时间范围选择（需要时间戳信息）
                        data = dataset[:]
                    else:
                        data = dataset[:]
                    
                    data_dict[f'CH{ch + 1}'] = data
            
            if not data_dict:
                logger.warning("没有数据可导出")
                return False
            
            # 创建DataFrame并保存
            df = pd.DataFrame(data_dict)
            df.to_csv(output_path, index=False)
            
            logger.info(f"数据已导出到: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            return False
    
    def __del__(self):
        """析构函数"""
        self.stop()
