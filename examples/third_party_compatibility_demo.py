# -*- coding: utf-8 -*-
"""
第三方软件兼容性演示
展示HDF5数据格式转换为各种第三方软件支持的格式
"""

import sys
import os
import numpy as np
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.data_buffer import RingBuffer
from data.persistence_manager import WaveformPersistence


def create_sample_data():
    """创建示例数据"""
    print("📊 创建示例数据...")
    
    # 创建RingBuffer
    buffer = RingBuffer(n_channels=4, max_bytes=1024*1024*10)
    
    # 生成测试数据
    sample_count = 50000
    sample_rate = 1000.0
    
    for i in range(sample_count):
        t = i / sample_rate
        values = [
            np.sin(2 * np.pi * 1 * t),      # 1Hz正弦波
            np.cos(2 * np.pi * 2 * t),      # 2Hz余弦波
            np.sin(2 * np.pi * 5 * t) * 0.5, # 5Hz正弦波，幅度0.5
            np.random.normal(0, 0.1)        # 噪声
        ]
        buffer.append_batch(values)
    
    print(f"✅ 生成了 {sample_count:,} 个样本，采样率 {sample_rate} Hz")
    return buffer


def demo_hdf5_export():
    """演示HDF5格式导出"""
    print("\n" + "=" * 70)
    print("📁 HDF5格式导出演示")
    print("=" * 70)
    
    # 创建示例数据
    buffer = create_sample_data()
    
    # 导出HDF5文件
    hdf5_file = buffer.start_recording("third_party_demo")
    buffer.stop_recording()
    
    print(f"📁 HDF5文件已保存: {hdf5_file}")
    
    # 显示文件信息
    import h5py
    with h5py.File(hdf5_file, 'r') as f:
        print("\n📋 HDF5文件结构:")
        print(f"   元数据组: {list(f['metadata'].attrs.keys())}")
        print(f"   数据集: {list(f.keys())}")
        
        for key in f.keys():
            if key.startswith('channel_'):
                dataset = f[key]
                print(f"   {key}: {dataset.shape} 样本, 数据类型: {dataset.dtype}")
    
    return hdf5_file


def demo_format_conversion(hdf5_file):
    """演示格式转换功能"""
    print("\n" + "=" * 70)
    print("🔄 格式转换演示")
    print("=" * 70)
    
    # 创建持久化管理器
    persistence = WaveformPersistence()
    
    # 转换为各种格式
    formats = ['csv', 'excel', 'matlab']
    
    print("🔄 开始格式转换...")
    results = persistence.export_batch(hdf5_file, formats)
    
    print("\n✅ 转换完成:")
    for fmt, output_file in results.items():
        file_size = output_file.stat().st_size / 1024 / 1024  # MB
        print(f"   {fmt.upper():6}: {output_file} ({file_size:.1f} MB)")
    
    return results


def demo_third_party_compatibility(results):
    """演示第三方软件兼容性"""
    print("\n" + "=" * 70)
    print("🔗 第三方软件兼容性分析")
    print("=" * 70)
    
    compatibility_info = {
        'csv': {
            'software': ['Microsoft Excel', 'LibreOffice Calc', 'Google Sheets', 'Python pandas', 'R', 'MATLAB'],
            'advantages': ['通用性强', '文件小', '易于查看和编辑'],
            'disadvantages': ['精度可能损失', '不保存元数据结构']
        },
        'excel': {
            'software': ['Microsoft Excel', 'LibreOffice Calc', 'Python pandas', 'MATLAB'],
            'advantages': ['保留格式', '支持多工作表', '包含元数据'],
            'disadvantages': ['文件较大', '需要特定软件']
        },
        'matlab': {
            'software': ['MATLAB', 'Octave', 'Python scipy', 'R'],
            'advantages': ['保留数据结构', '高精度', '包含元数据'],
            'disadvantages': ['需要特定软件或库']
        }
    }
    
    for fmt, info in compatibility_info.items():
        if fmt in results:
            print(f"\n📊 {fmt.upper()} 格式兼容性:")
            print(f"   支持的软件: {', '.join(info['software'])}")
            print(f"   优势: {', '.join(info['advantages'])}")
            print(f"   劣势: {', '.join(info['disadvantages'])}")


def demo_matlab_compatibility():
    """演示MATLAB兼容性"""
    print("\n" + "=" * 70)
    print("🔬 MATLAB兼容性详细演示")
    print("=" * 70)
    
    print("📋 MATLAB读取示例代码:")
    matlab_code = """
% MATLAB读取导出的.mat文件
data = load('third_party_demo.mat');

% 查看数据结构
disp('数据字段:');
disp(fieldnames(data));

% 绘制通道数据
figure;
subplot(2,2,1); plot(data.time_axis, data.channel_00); title('Channel 0');
subplot(2,2,2); plot(data.time_axis, data.channel_01); title('Channel 1');
subplot(2,2,3); plot(data.time_axis, data.channel_02); title('Channel 2');
subplot(2,2,4); plot(data.time_axis, data.channel_03); title('Channel 3');

% 显示元数据
disp('元数据:');
disp(data.metadata);
"""
    print(matlab_code)


def demo_python_pandas_compatibility():
    """演示Python pandas兼容性"""
    print("\n" + "=" * 70)
    print("🐍 Python pandas兼容性详细演示")
    print("=" * 70)
    
    print("📋 Python pandas读取示例代码:")
    python_code = """
import pandas as pd
import matplotlib.pyplot as plt

# 读取CSV文件
df = pd.read_csv('third_party_demo.csv')

# 查看数据结构
print("数据形状:", df.shape)
print("列名:", df.columns.tolist())
print("前5行数据:")
print(df.head())

# 绘制数据
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
axes = axes.flatten()

for i, col in enumerate(['Channel_00', 'Channel_01', 'Channel_02', 'Channel_03']):
    if col in df.columns:
        axes[i].plot(df['Time_s'], df[col])
        axes[i].set_title(col)
        axes[i].set_xlabel('Time (s)')
        axes[i].set_ylabel('Amplitude')

plt.tight_layout()
plt.show()

# 数据分析
print("\\n数据统计:")
print(df.describe())
"""
    print(python_code)


def demo_excel_compatibility():
    """演示Excel兼容性"""
    print("\n" + "=" * 70)
    print("📊 Excel兼容性详细演示")
    print("=" * 70)
    
    print("📋 Excel使用说明:")
    excel_instructions = """
1. 打开导出的 .xlsx 文件
2. 查看 "Metadata" 工作表了解数据信息
3. 查看 "Data" 工作表查看实际数据
4. 使用Excel的图表功能创建可视化:
   - 选择时间列和通道数据列
   - 插入 -> 图表 -> 散点图或折线图
   - 可以创建多个图表显示不同通道

5. 数据分析功能:
   - 使用Excel的统计函数 (AVERAGE, MAX, MIN, STDEV等)
   - 创建数据透视表进行深度分析
   - 使用条件格式突出显示异常值
"""
    print(excel_instructions)


def demo_performance_comparison():
    """演示性能对比"""
    print("\n" + "=" * 70)
    print("⚡ 格式性能对比")
    print("=" * 70)
    
    # 创建测试数据
    buffer = RingBuffer(n_channels=4, max_bytes=1024*1024*20)
    
    # 生成大量数据
    sample_count = 100000
    print(f"📊 生成 {sample_count:,} 样本进行性能测试...")
    
    for i in range(sample_count):
        values = [np.random.random() for _ in range(4)]
        buffer.append_batch(values)
    
    # 导出性能测试
    import time
    
    formats = ['csv', 'excel', 'matlab', 'hdf5']
    performance_results = {}
    
    for fmt in formats:
        print(f"🔄 测试 {fmt.upper()} 格式导出...")
        
        start_time = time.time()
        try:
            results = buffer.export_data([fmt], Path("data"), f"performance_test_{fmt}")
            end_time = time.time()
            
            if results:
                file_path = list(results.values())[0]
                file_size = file_path.stat().st_size / 1024 / 1024  # MB
                export_time = end_time - start_time
                
                performance_results[fmt] = {
                    'time': export_time,
                    'size': file_size,
                    'speed': sample_count * 4 / export_time / 1000  # K samples/sec
                }
                
        except Exception as e:
            print(f"   ❌ {fmt} 导出失败: {e}")
    
    # 显示性能结果
    print("\n📊 性能对比结果:")
    print(f"{'格式':<8} {'耗时(s)':<10} {'文件大小(MB)':<12} {'速度(K样本/s)':<15}")
    print("-" * 50)
    
    for fmt, result in performance_results.items():
        print(f"{fmt.upper():<8} {result['time']:<10.2f} {result['size']:<12.1f} {result['speed']:<15.0f}")


def main():
    """主演示函数"""
    print("🎉 第三方软件兼容性和格式转换演示")
    print("=" * 80)
    
    try:
        # 1. HDF5导出演示
        hdf5_file = demo_hdf5_export()
        
        # 2. 格式转换演示
        results = demo_format_conversion(hdf5_file)
        
        # 3. 第三方软件兼容性分析
        demo_third_party_compatibility(results)
        
        # 4. 具体软件兼容性演示
        demo_matlab_compatibility()
        demo_python_pandas_compatibility()
        demo_excel_compatibility()
        
        # 5. 性能对比
        demo_performance_comparison()
        
        print("\n" + "=" * 80)
        print("🎊 第三方软件兼容性演示完成！")
        print("\n📋 总结:")
        print("   ✅ HDF5原始格式 - 最高精度，支持MATLAB、Python等")
        print("   ✅ CSV格式 - 最广泛兼容性，支持Excel、pandas等")
        print("   ✅ Excel格式 - 商业软件友好，支持元数据")
        print("   ✅ MATLAB格式 - 科学计算优化，保留数据结构")
        print("\n🔗 推荐使用场景:")
        print("   📊 数据分析: CSV + pandas/R")
        print("   🔬 科学计算: MATLAB .mat格式")
        print("   📈 商业报告: Excel .xlsx格式")
        print("   🗄️ 长期存储: HDF5原始格式")
        
    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
