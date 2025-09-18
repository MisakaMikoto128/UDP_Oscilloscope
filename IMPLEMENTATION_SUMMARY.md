# DeviceSettingFrom 功能实现总结

## 实现的功能

### 1. 新增参数设置按钮和输入框功能

实现了以下三个参数的设置功能，与现有PID设置按钮保持一致的交互方式：

#### 1.1 Rottx_Zero_Current (旋变零点电流)
- **控件**: `spinbox_Rottx_Zero_Current` 和 `btn_Rottx_Zero_Current`
- **寄存器地址**: 14
- **数据类型**: 定点数 (scale_factor: 100000)
- **范围**: [-1000.0, 1000.0] A
- **功能**: 点击按钮弹出确认对话框，确认后设置参数

#### 1.2 Motor_Resolver_Zero (旋变零点)
- **控件**: `spinbox_Motor_Resolver_Zero` 和 `btn_Motor_Resolver_Zero`
- **寄存器地址**: 48
- **数据类型**: 定点数 (scale_factor: 100000)
- **范围**: [-3.14159, 3.14159] rad
- **功能**: 点击按钮弹出确认对话框，确认后设置参数

#### 1.3 Motor_Pn (电机极对数)
- **控件**: `spinbox_Motor_Pn` 和 `btn_Motor_Pn`
- **寄存器地址**: 46
- **数据类型**: 定点数 (scale_factor: 100000)
- **范围**: [1.0, 50.0]
- **功能**: 点击按钮弹出确认对话框，确认后设置参数

### 2. 双击表格同步功能

#### 2.1 table_other_param 双击同步
- **功能**: 双击 `table_other_param` 表格的任意行，自动将该行的值同步到对应的 spinbox
- **支持的参数**:
  - 行1: Motor_Pn → spinbox_Motor_Pn
  - 行2: Motor_Resolver_Zero → spinbox_Motor_Resolver_Zero
  - 行4: Rottx_Zero_Current → spinbox_Rottx_Zero_Current

#### 2.2 table_pid_param 双击同步 (已有功能)
- **功能**: 双击 PID 参数表格同步到对应的 PID spinbox

### 3. 代码优化和重构

#### 3.1 减少重复代码
- **通用参数设置函数**: 创建了 `_set_param()` 通用函数，替代原来的 `_set_pid_param()`
- **通用确认对话框函数**: 创建了 `_confirm_and_set_param()` 通用函数
- **向后兼容**: 保留了原有的 `_set_pid_param()` 和 `_confirm_and_set_pid()` 函数，内部调用新的通用函数

#### 3.2 表格数据更新
- **扩展 other_params 表格**: 添加了 `Rottx_Zero_Current` 参数到表格中
- **数据解析**: 在 `on_on_sys_regs_uploaded()` 中添加了 `Rottx_Zero_Current` 的数据解析
- **表格行数**: 将 `table_other_param` 行数从7行增加到8行

## 代码结构

### 新增的主要函数

```python
def _connect_other_param_buttons(self):
    """连接其他参数设置按钮，并增加确认提示"""

async def _set_param(self, reg_addr: int, value: float, param_name: str):
    """设置参数的通用函数"""

async def _confirm_and_set_param(self, reg_addr: int, new_value: float, param_name: str):
    """弹出确认框，确认后真正发送参数设置指令"""

def _sync_other_params_to_spinbox(self, row: int, column: int):
    """双击其他参数表格同步参数到spinbox"""
```

### 修改的主要函数

```python
def __init__():
    # 添加了 _connect_other_param_buttons() 调用
    # 添加了 table_other_param.cellDoubleClicked 信号连接

def _init_other_table():
    # 表格行数从7增加到8
    # 添加了 Rottx_Zero_Current 行

async def on_on_sys_regs_uploaded():
    # 添加了 Rottx_Zero_Current 数据解析
    # 更新了 other_params 数据结构
```

## 使用方法

### 1. 设置参数
1. 在对应的 spinbox 中输入要设置的值
2. 点击旁边的设置按钮
3. 在弹出的确认对话框中确认设置
4. 系统将发送设置命令到设备

### 2. 同步参数
1. 双击 `table_other_param` 表格中的任意行
2. 对应的参数值会自动同步到相应的 spinbox 中
3. 可以进一步修改值并设置

## 测试

创建了 `test_device_setting.py` 测试脚本，可以验证：
- 参数表格显示
- 双击同步功能
- 按钮设置功能
- 确认对话框

运行测试：
```bash
python test_device_setting.py
```

## 兼容性

- **向后兼容**: 所有原有的PID设置功能保持不变
- **代码复用**: 新功能复用了现有的确认对话框和通信机制
- **一致性**: 新功能的交互方式与现有PID设置功能完全一致
