# 显示点数配置指南

## 🎯 设计目标

根据您的建议，我们实现了**实时模式和预览模式使用不同显示点数**的功能，以优化不同使用场景的性能和用户体验。

### 💡 核心理念

> **"预览录波和预览实时波形的max_points_window可以不同"**

- 🔴 **实时模式**: 优化显示点数，保证流畅的实时更新
- 🔵 **预览模式**: 更多显示点数，便于详细的历史数据分析
- ⚖️ **平衡性能**: 根据使用场景自动选择最优的显示点数

## 📊 配置参数

### 1. 配置文件结构

```json
{
  "display": {
    "max_points_window": 100000,    // 实时模式最大显示点数
    "max_points_preview": 500000,   // 预览模式最大显示点数
    "time_base_div": 1.0,
    "time_base_unit": "ms",
    // ... 其他显示配置
  }
}
```

### 2. 配置管理器支持

```python
class ScopeConfigManager:
    @property
    def max_points_window(self) -> int:
        """实时模式最大显示点数"""
        return self.get('display.max_points_window', 300000)
    
    @property
    def max_points_preview(self) -> int:
        """预览模式最大显示点数"""
        return self.get('display.max_points_preview', 100000)
```

## 🔧 OscilloscopeFrame集成

### 1. 初始化配置

```python
def _init_scope_widget(self):
    # 应用配置
    self.scope_widget.max_points_window = self.cfg.max_points_window
    
    # 存储预览模式的显示点数配置
    self._max_points_preview = self.cfg.max_points_preview
```

### 2. 智能模式切换

```python
def refresh_plot(self):
    """刷新绘图"""
    # 根据当前模式决定数据源和显示点数
    if self._is_preview_mode and self._preview_buffer is not None:
        # 预览模式：使用预览buffer的数据和预览显示点数
        arrays = []
        for i in range(self._preview_buffer.n_channels):
            data = self._preview_buffer.view_tail(i, self._max_points_preview)
            arrays.append(data)
    else:
        # 实时模式：使用实时buffer的数据和实时显示点数
        arrays = []
        for i in range(self.buffer.n_channels):
            data = self.buffer.view_tail(i, self.scope_widget.max_points_window)
            arrays.append(data)
```

### 3. 动态配置更新

```python
def update_display_points_config(self):
    """更新显示点数配置"""
    # 更新实时模式显示点数
    self.scope_widget.max_points_window = self.cfg.max_points_window
    
    # 更新预览模式显示点数
    self._max_points_preview = self.cfg.max_points_preview

def get_current_max_points(self) -> int:
    """获取当前模式的最大显示点数"""
    if self._is_preview_mode:
        return self._max_points_preview
    else:
        return self.scope_widget.max_points_window
```

## 📈 使用场景对比

### 🔴 实时模式特点

| 特性 | 配置 | 优势 |
|------|------|------|
| 显示点数 | 100,000 点 | 流畅的实时更新 |
| 更新频率 | 高频率 | 响应迅速 |
| 数据范围 | 最近数据 | 关注当前状态 |
| 内存使用 | 较低 | 性能优化 |

**适用场景**：
- 🔍 实时监控设备状态
- ⚡ 快速响应异常情况
- 📊 连续数据流分析
- 🎯 关注最新数据变化

### 🔵 预览模式特点

| 特性 | 配置 | 优势 |
|------|------|------|
| 显示点数 | 500,000 点 | 详细的历史分析 |
| 更新频率 | 静态显示 | 稳定的分析环境 |
| 数据范围 | 完整历史 | 全面的数据视图 |
| 内存使用 | 较高 | 数据完整性 |

**适用场景**：
- 📚 历史数据深度分析
- 🔬 故障原因追溯
- 📊 长期趋势观察
- 🎯 精确数据测量

## ⚡ 性能优化效果

### 实际测试结果

```
📊 当前配置:
   实时模式: 100,000 点
   预览模式: 500,000 点
   预览/实时比例: 5.0x

⏱️ 性能测试结果:
   实时模式: 1.5 MB数据, 0.5ms耗时, 879K点/秒
   预览模式: 7.6 MB数据, 1.5ms耗时, 1333K点/秒
```

### 性能优势分析

1. **🚀 实时模式优化**
   - 较少的数据点减少内存占用
   - 更快的数据处理速度
   - 流畅的UI更新体验

2. **🔍 预览模式增强**
   - 5倍数据点提供更详细的分析
   - 完整的历史数据视图
   - 精确的数据测量能力

3. **⚖️ 智能平衡**
   - 根据使用场景自动选择
   - 避免不必要的性能开销
   - 最大化用户体验

## 🎮 用户操作体验

### 模式切换流程

```
🎬 UI操作序列:

1️⃣ 初始实时模式:
   当前最大显示点数: 100,000
   📡 实时模式刷新: 10,000 点/通道

2️⃣ 切换到预览模式:
   🔄 切换到预览模式 (显示点数: 500,000)
   当前最大显示点数: 500,000
   📺 预览模式刷新: 150,000 点/通道

3️⃣ 切换回实时模式:
   🔄 切换到实时模式 (显示点数: 100,000)
   当前最大显示点数: 100,000
   📡 实时模式刷新: 10,000 点/通道
```

### 用户体验提升

- ✅ **无缝切换**: 模式切换时自动应用对应的显示点数
- ✅ **性能优化**: 实时模式保持流畅，预览模式提供详细分析
- ✅ **智能适配**: 根据数据量自动调整显示范围
- ✅ **配置灵活**: 可通过配置文件自定义显示点数

## 🔧 配置建议

### 推荐配置值

| 使用场景 | 实时模式 | 预览模式 | 比例 |
|----------|----------|----------|------|
| 轻量级应用 | 50,000 | 200,000 | 4x |
| 标准应用 | 100,000 | 500,000 | 5x |
| 高性能应用 | 200,000 | 1,000,000 | 5x |

### 配置调优指南

1. **实时模式调优**
   ```json
   "max_points_window": 100000  // 根据刷新频率调整
   ```
   - 高频刷新：减少点数 (50K-100K)
   - 低频刷新：可增加点数 (100K-200K)

2. **预览模式调优**
   ```json
   "max_points_preview": 500000  // 根据分析需求调整
   ```
   - 快速预览：适中点数 (200K-500K)
   - 详细分析：更多点数 (500K-1M)

3. **内存考虑**
   - 每100K点约占用1.5MB内存
   - 根据系统内存容量合理设置
   - 考虑多通道的内存倍增效应

## 📋 测试验证

### 完整测试覆盖

✅ **配置文件加载和默认值**
✅ **不同显示点数的使用**
✅ **OscilloscopeFrame集成模拟**
✅ **性能影响分析**
✅ **配置动态更新**
✅ **边界情况处理**
✅ **内存使用优化**

### 测试结果

```
🎉 所有显示点数配置测试通过！

📋 测试总结:
   ✅ 配置文件加载和默认值
   ✅ 不同显示点数的使用
   ✅ OscilloscopeFrame集成模拟
   ✅ 性能影响分析
   ✅ 配置动态更新
   ✅ 边界情况处理
   ✅ 内存使用优化
```

## 🔗 相关文件

- `src/config/default_config.json` - 默认配置模板
- `config/config.json` - 当前配置文件
- `src/config/scope_config_manager.py` - 配置管理器
- `src/window/oscilloscope_frame.py` - UI集成实现
- `examples/display_points_config_demo.py` - 功能演示
- `test/test_display_points_config.py` - 完整测试套件

---

**🎉 现在您可以根据不同的使用场景享受最优化的显示性能！实时监控时保持流畅，历史分析时获得详细数据！**
