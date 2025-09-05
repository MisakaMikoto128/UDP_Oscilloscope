# -*- coding: utf-8 -*-
"""
HDF5版本RingBuffer测试
测试批量添加和HDF5持久化功能
"""

import unittest
import numpy as np
import h5py
import time
import tempfile
import shutil
from pathlib import Path
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.data_buffer import RingBuffer


class TestHDF5RingBuffer(unittest.TestCase):
    """HDF5版本RingBuffer测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.n_channels = 4
        self.max_bytes = 1024 * 1024  # 1MB
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_batch_append_functionality(self):
        """测试批量添加功能"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        # 测试批量添加
        test_data = [1.0, 2.0, 3.0, 4.0]  # 4个通道的数据
        buffer.append_batch(test_data)
        
        # 验证数据
        for ch in range(self.n_channels):
            data = buffer.view_tail(ch, 10)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0], test_data[ch])
    
    def test_multiple_batch_append(self):
        """测试多次批量添加"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        # 添加多批数据
        for i in range(10):
            test_data = [i * 0.1, i * 0.2, i * 0.3, i * 0.4]
            buffer.append_batch(test_data)
        
        # 验证数据
        for ch in range(self.n_channels):
            data = buffer.view_tail(ch, 10)
            self.assertEqual(len(data), 10)
            # 验证最后一个值
            expected_last_value = 9 * (ch + 1) * 0.1
            self.assertAlmostEqual(data[-1], expected_last_value, places=5)
    
    def test_hdf5_persistence(self):
        """测试HDF5持久化功能"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        # 修改持久化管理器的基础目录
        buffer._persistence_manager.base_dir = Path(self.temp_dir)
        
        # 开始录制
        file_path = buffer.start_recording("test_hdf5")
        self.assertIsNotNone(file_path)
        self.assertTrue(file_path.name.endswith('.h5'))
        self.assertTrue(buffer.is_recording())
        
        # 添加测试数据
        for i in range(100):
            test_data = [i * 0.1, i * 0.2, i * 0.3, i * 0.4]
            buffer.append_batch(test_data)
        
        # 等待数据写入
        time.sleep(0.5)
        
        # 停止录制
        buffer.stop_recording()
        self.assertFalse(buffer.is_recording())
        
        # 验证文件存在
        self.assertTrue(file_path.exists())
        
        # 验证HDF5文件结构
        with h5py.File(file_path, 'r') as f:
            # 检查元数据
            self.assertIn('metadata', f)
            metadata = f['metadata']
            self.assertEqual(metadata.attrs['n_channels'], self.n_channels)
            self.assertEqual(metadata.attrs['format'], 'HDF5_Waveform')
            
            # 检查通道数据
            for ch in range(self.n_channels):
                dataset_name = f'channel_{ch:02d}'
                self.assertIn(dataset_name, f)
                dataset = f[dataset_name]
                self.assertEqual(len(dataset), 100)  # 100个数据点
                self.assertEqual(dataset.attrs['channel'], ch)
                self.assertEqual(dataset.attrs['unit'], 'V')
    
    def test_hdf5_data_loading(self):
        """测试HDF5数据加载"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        buffer._persistence_manager.base_dir = Path(self.temp_dir)
        
        # 准备测试数据
        original_data = []
        for i in range(50):
            test_data = [i * 0.1, i * 0.2, i * 0.3, i * 0.4]
            original_data.append(test_data)
        
        # 录制数据
        file_path = buffer.start_recording("load_test")
        for data in original_data:
            buffer.append_batch(data)
        time.sleep(0.2)
        buffer.stop_recording()
        
        # 测试数据加载
        loaded_data = buffer.load_waveform_data(file_path)
        self.assertEqual(len(loaded_data), self.n_channels)
        
        # 验证数据正确性
        for ch in range(self.n_channels):
            self.assertIn(ch, loaded_data)
            channel_data = loaded_data[ch]
            self.assertEqual(len(channel_data), 50)
            
            # 验证数据值
            for i in range(50):
                expected_value = i * (ch + 1) * 0.1
                self.assertAlmostEqual(channel_data[i], expected_value, places=5)
    
    def test_on_sample_received_scenario(self):
        """测试实际使用场景：on_sample_received优化版"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        buffer._persistence_manager.base_dir = Path(self.temp_dir)
        
        def on_sample_received_optimized(fmt: int, values: list):
            """优化版的on_sample_received方法"""
            try:
                # 直接批量添加所有通道数据
                if len(values) >= buffer.n_channels:
                    channel_values = [float(values[ch]) for ch in range(buffer.n_channels)]
                    buffer.append_batch(channel_values)
            except Exception as e:
                print(f"处理采样数据时出错: {e}")
        
        # 开始录制
        file_path = buffer.start_recording("optimized_test")
        
        # 模拟接收数据
        for i in range(100):
            values = [i * 0.1, i * 0.2, i * 0.3, i * 0.4, i * 0.5]  # 5个值，只用前4个
            on_sample_received_optimized(0xA2, values)
        
        time.sleep(0.2)
        buffer.stop_recording()
        
        # 验证数据
        for ch in range(self.n_channels):
            data = buffer.view_tail(ch, 100)
            self.assertEqual(len(data), 100)
            # 验证最后一个值
            expected_last_value = 99 * (ch + 1) * 0.1
            self.assertAlmostEqual(data[-1], expected_last_value, places=5)
        
        # 验证文件中的数据
        loaded_data = buffer.load_waveform_data(file_path)
        for ch in range(self.n_channels):
            self.assertEqual(len(loaded_data[ch]), 100)
    
    def test_large_data_performance(self):
        """测试大数据量性能"""
        buffer = RingBuffer(self.n_channels, 1024 * 1024 * 10)  # 10MB
        buffer._persistence_manager.base_dir = Path(self.temp_dir)
        
        # 开始录制
        file_path = buffer.start_recording("performance_test")
        
        # 测试大量数据
        n_samples = 10000
        start_time = time.perf_counter()
        
        for i in range(n_samples):
            test_data = [i * 0.001, i * 0.002, i * 0.003, i * 0.004]
            buffer.append_batch(test_data)
        
        append_time = time.perf_counter() - start_time
        
        # 等待写入完成
        time.sleep(1.0)
        buffer.stop_recording()
        
        print(f"批量添加{n_samples}个样本时间: {append_time:.4f}s")
        print(f"处理速度: {n_samples / append_time:.0f} 样本/秒")
        
        # 验证文件
        self.assertTrue(file_path.exists())
        file_size = file_path.stat().st_size
        print(f"HDF5文件大小: {file_size / 1024:.2f} KB")
        
        # 验证数据完整性
        loaded_data = buffer.load_waveform_data(file_path)
        for ch in range(self.n_channels):
            self.assertEqual(len(loaded_data[ch]), n_samples)
    
    def test_backward_compatibility(self):
        """测试向后兼容性"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        # 测试原有的append方法仍然工作
        buffer.append(0, (1.0, 2.0, 3.0))
        buffer.append(1, [4.0, 5.0])
        
        # 验证数据
        data_ch0 = buffer.view_tail(0, 10)
        data_ch1 = buffer.view_tail(1, 10)
        
        np.testing.assert_array_equal(data_ch0, [1.0, 2.0, 3.0])
        np.testing.assert_array_equal(data_ch1, [4.0, 5.0])
    
    def test_error_handling(self):
        """测试错误处理"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        # 测试通道数不匹配
        with self.assertRaises(ValueError):
            buffer.append_batch([1.0, 2.0])  # 只有2个值，但需要4个
        
        with self.assertRaises(ValueError):
            buffer.append_batch([1.0, 2.0, 3.0, 4.0, 5.0])  # 5个值，但只需要4个


if __name__ == '__main__':
    unittest.main()
