# Device Setting 功能更新说明

## 更新概述

根据用户需求，在 `device_setting.py` 页面中新增了以下控件和功能：

### 1. 新增的 Spinbox 和 Button 控件

#### 1.1 新增的参数控件
- `spinbox_Motor_Id_Max` + `btn_Motor_Id_Max` - 电机Id上限设置
- `spinbox_Motor_Id_Min` + `btn_Motor_Id_Min` - 电机Id下限设置  
- `spinbox_Idref` + `btn_Idref` - d轴电流参考值设置
- `spinbox_Iqref` + `btn_Iqref` - q轴电流参考值设置
- `spinbox_Vdcset_ref` + `btn_Vdcset_ref` - 母线电压设置参考值
- `spinbox_Iset_d_ref` + `btn_Iset_d_ref` - d轴电流参考值设置

#### 1.2 寄存器地址映射
根据下位机代码，新增参数的寄存器地址映射如下：
- 地址 8: `Vdcset_ref` (Uint16类型)
- 地址 9: `Iset_d_ref` (Uint16类型)  
- 地址 31: `Idref` (float类型)
- 地址 32: `Iqref` (float类型)
- 地址 33: `Motor_Id_Max` (float类型)
- 地址 34: `Motor_Id_Min` (float类型)

### 2. table_other_param 表格更新

#### 2.1 新增显示参数
在 `table_other_param` 中新增了以下参数的显示：
- `mEthetaAVG` - 旋变输出电角度平均值 (地址82)
- `mEthetaRad` - 旋变输出电角度弧度 (地址92)  
- `Motor_Id_Max` - 电机Id上限 (地址33)
- `Motor_Id_Min` - 电机Id下限 (地址34)
- `ResovlerFault` - 旋变故障状态 (地址91)

#### 2.2 寄存器地址更新
根据下位机代码更新，部分寄存器地址有所调整：
- 地址 62: `mEtheta1` 
- 地址 80: `mEtheta`
- 地址 81: `mEthetaZero`
- 地址 82: `mEthetaAVG` (新增)
- 地址 91: `ResovlerFault` (新增)
- 地址 92: `mEthetaRad` (新增)

### 3. 双击同步功能增强

#### 3.1 table_other_param 双击同步
更新了 `_sync_other_params_to_spinbox` 函数，支持双击表格行同步到对应的 spinbox：
- 行1: Motor_Pn → spinbox_Motor_Pn
- 行2: Motor_Resolver_Zero → spinbox_Motor_Resolver_Zero  
- 行4: Rottx_Zero_Current → spinbox_Rottx_Zero_Current
- 行10: Motor_Id_Max → spinbox_Motor_Id_Max (新增)
- 行11: Motor_Id_Min → spinbox_Motor_Id_Min (新增)

注意：旋变相关参数（mEtheta系列）和ResovlerFault为只读参数，不支持同步到spinbox。

### 4. 数据类型处理优化

#### 4.1 智能数据转换
在 `_set_param` 函数中增加了智能数据类型处理：
- 地址 8, 9: Uint16类型，直接发送整数值
- 其他地址: float类型，转换为定点数 (值 × 100000)

#### 4.2 数据解析优化  
在 `on_on_sys_regs_uploaded` 函数中正确处理不同数据类型：
- Uint16类型参数直接使用寄存器值
- float类型参数除以定点数比例因子 (100000)
- ResovlerFault为整数类型，不进行定点数转换

### 5. 代码结构改进

#### 5.1 按钮连接扩展
在 `_connect_other_param_buttons` 函数中添加了所有新增按钮的信号连接，每个按钮都有确认对话框保护。

#### 5.2 表格初始化更新
- 将 `table_other_param` 行数从8行增加到13行
- 更新了表格的初始化数据结构
- 添加了新参数的中文别名

### 6. 实时数据更新

#### 6.1 Spinbox 值同步
在接收到系统寄存器数据时，自动更新所有新增 spinbox 的显示值：
- `spinbox_Vdcset_ref`
- `spinbox_Iset_d_ref`  
- `spinbox_Idref`
- `spinbox_Iqref`
- `spinbox_Motor_Id_Max`
- `spinbox_Motor_Id_Min`

#### 6.2 表格数据同步
实时更新 `table_other_param` 中所有参数的显示值，包括新增的旋变相关参数。

## 技术要点

1. **数据类型兼容性**: 正确处理Uint16和float两种数据类型
2. **寄存器地址映射**: 严格按照下位机代码的地址分配
3. **用户交互优化**: 所有设置操作都有确认对话框
4. **实时数据同步**: 接收数据时自动更新界面显示
5. **双击同步功能**: 方便用户快速设置参数值

## 测试建议

1. 测试所有新增按钮的参数设置功能
2. 验证双击表格行的同步功能
3. 检查不同数据类型的正确处理
4. 确认实时数据更新的准确性
5. 测试确认对话框的用户体验
