# -*- coding: utf-8 -*-
"""
简化版RingBuffer测试
测试性能优化和简化的持久化功能
"""

import unittest
import numpy as np
import time
import tempfile
import shutil
from pathlib import Path
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.data_buffer import RingBuffer


class TestSimplifiedRingBuffer(unittest.TestCase):
    """简化版RingBuffer测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.n_channels = 4
        self.max_bytes = 1024 * 1024  # 1MB
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_basic_functionality_compatibility(self):
        """测试基本功能的向后兼容性"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        # 测试原有接口
        buffer.append(0, (1.0, 2.0, 3.0))
        buffer.append(1, (4.0, 5.0))
        
        # 验证数据
        data_ch0 = buffer.view_tail(0, 10)
        data_ch1 = buffer.view_tail(1, 10)
        
        np.testing.assert_array_equal(data_ch0, [1.0, 2.0, 3.0])
        np.testing.assert_array_equal(data_ch1, [4.0, 5.0])
        
        # 测试其他原有方法
        self.assertEqual(buffer.get_sample_count(0), 3)
        self.assertEqual(buffer.get_sample_count(1), 2)
        self.assertEqual(buffer.get_latest_value(0), 3.0)
        self.assertEqual(buffer.get_latest_value(1), 5.0)
    
    def test_performance_optimization(self):
        """测试性能优化"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        # 测试批量append性能
        n_samples = 10000
        test_data = np.random.random(n_samples).astype(np.float32)
        
        # 测试单个append（原方式）
        start_time = time.perf_counter()
        for i in range(1000):
            buffer.append(0, (test_data[i],))
        single_append_time = time.perf_counter() - start_time
        
        # 清空缓冲区
        buffer.clear(0)
        
        # 测试批量append（新方式）
        start_time = time.perf_counter()
        buffer.append(0, test_data[:1000])
        batch_append_time = time.perf_counter() - start_time
        
        print(f"单个append时间: {single_append_time:.4f}s")
        print(f"批量append时间: {batch_append_time:.4f}s")
        print(f"性能提升: {single_append_time / batch_append_time:.2f}x")
        
        # 批量append应该更快
        self.assertLess(batch_append_time, single_append_time)
    
    def test_waveform_persistence(self):
        """测试波形持久化功能"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        # 修改持久化管理器的基础目录
        buffer._persistence_manager.base_dir = Path(self.temp_dir)
        
        # 开始录制
        file_path = buffer.start_recording("test_waveform")
        self.assertIsNotNone(file_path)
        self.assertTrue(buffer.is_recording())
        
        # 添加测试数据
        test_data = np.random.random(1000).astype(np.float32)
        buffer.append(0, test_data)
        buffer.append(1, test_data * 2)
        
        # 等待数据写入
        time.sleep(0.2)
        
        # 停止录制
        buffer.stop_recording()
        self.assertFalse(buffer.is_recording())
        
        # 验证文件存在
        self.assertTrue(file_path.exists())
        
        # 测试数据加载
        loaded_data = buffer.load_waveform_data(file_path)
        self.assertIn(0, loaded_data)
        self.assertIn(1, loaded_data)
        
        # 验证数据正确性
        np.testing.assert_array_almost_equal(loaded_data[0], test_data, decimal=5)
        np.testing.assert_array_almost_equal(loaded_data[1], test_data * 2, decimal=5)
    
    def test_reload_to_buffer(self):
        """测试重新加载数据到缓冲区"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        buffer._persistence_manager.base_dir = Path(self.temp_dir)
        
        # 准备测试数据
        original_data = {
            0: np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
            1: np.array([6.0, 7.0, 8.0, 9.0, 10.0])
        }
        
        # 录制数据
        file_path = buffer.start_recording("reload_test")
        for ch, data in original_data.items():
            buffer.append(ch, data)
        time.sleep(0.1)
        buffer.stop_recording()
        
        # 清空缓冲区并添加其他数据
        buffer.clear()
        buffer.append(0, (99.0, 98.0))
        
        # 重新加载数据
        buffer.reload_to_buffer(file_path)
        
        # 验证数据已正确加载
        reloaded_ch0 = buffer.view_tail(0, 10)
        reloaded_ch1 = buffer.view_tail(1, 10)
        
        np.testing.assert_array_almost_equal(reloaded_ch0, original_data[0], decimal=5)
        np.testing.assert_array_almost_equal(reloaded_ch1, original_data[1], decimal=5)
    
    def test_auto_filename_generation(self):
        """测试自动文件名生成"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        buffer._persistence_manager.base_dir = Path(self.temp_dir)
        
        # 不指定文件名，应该自动生成
        file_path1 = buffer.start_recording()
        self.assertIsNotNone(file_path1)
        self.assertTrue(file_path1.name.startswith("waveform_"))
        self.assertTrue(file_path1.name.endswith(".npz"))
        buffer.stop_recording()
        
        # 再次录制，应该生成不同的文件名
        file_path2 = buffer.start_recording()
        self.assertIsNotNone(file_path2)
        self.assertNotEqual(file_path1, file_path2)
        buffer.stop_recording()
    
    def test_on_sample_received_scenario(self):
        """测试实际使用场景：on_sample_received"""
        buffer = RingBuffer(self.n_channels, self.max_bytes)
        
        def on_sample_received(fmt: int, values: list):
            """模拟实际的on_sample_received方法"""
            try:
                # fmt: 0xA1 for uint16, 0xA2 for float32 (当前都作为float处理)
                for ch in range(min(buffer.n_channels, len(values))):
                    sample_value = float(values[ch])
                    buffer.append(ch, (sample_value,))
            except Exception as e:
                print(f"处理采样数据时出错: {e}")
        
        # 模拟接收数据
        for i in range(100):
            values = [i * 0.1, i * 0.2, i * 0.3, i * 0.4]
            on_sample_received(0xA2, values)
        
        # 验证数据
        for ch in range(self.n_channels):
            data = buffer.view_tail(ch, 100)
            self.assertEqual(len(data), 100)
            # 验证最后一个值
            expected_last_value = 99 * (ch + 1) * 0.1
            self.assertAlmostEqual(data[-1], expected_last_value, places=5)
    
    def test_large_data_handling(self):
        """测试大数据量处理"""
        buffer = RingBuffer(2, 1024 * 100)  # 100KB缓冲区
        
        # 生成大量数据
        large_data = np.random.random(10000).astype(np.float32)
        
        # 批量添加
        start_time = time.perf_counter()
        buffer.append(0, large_data)
        batch_time = time.perf_counter() - start_time
        
        print(f"大数据量批量添加时间: {batch_time:.4f}s")
        print(f"数据量: {len(large_data)} 样本")
        print(f"处理速度: {len(large_data) / batch_time:.0f} 样本/秒")
        
        # 验证环形缓冲区正确处理溢出
        max_samples = buffer.max_samples
        result_data = buffer.view_tail(0, len(large_data))
        
        if len(large_data) > max_samples:
            # 应该只保留最新的max_samples个数据
            expected_data = large_data[-max_samples:]
            np.testing.assert_array_equal(result_data, expected_data)
        else:
            np.testing.assert_array_equal(result_data, large_data)


if __name__ == '__main__':
    unittest.main()
