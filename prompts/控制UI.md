请使用中文与我高效交流。

基于main.py中的self.receiver UDP通信模块，我需要创建一个基于JSON配置文件的寄存器管理界面系统。由于寄存器众多，我认为一个个手动设置界面很费时间，所以我觉得可以使用json配置文件来描述每一个寄存器，自动生成界面。

## 背景

下位机有107个32位小端序寄存器，分为三类：

- 配置寄存器（55个，地址0-54）：可读写，用于设置参数
- 状态寄存器（50个，地址55-104）：只读，用于显示状态
- 命令寄存器（2个，地址105-106）：只写，用于发送命令，命令寄存器的寄存器值就是一个命令

## JSON配置文件规范

每个寄存器需要以下字段：

1. **JSON配置基本信息字段**：
   - `var_name`：寄存器变量名
   - `alias`：寄存器别名（可选，有别名时显示别名，否则显示变量名）
   - `permission`：读写权限（"r"=只读状态，"rw"=读写配置，"w"=只写命令）
   - `address`：寄存器地址（0-106）
   - `scale_factor`：缩放倍数（仅定点数类型，默认100000）
   - `range`：有效值范围 [最小值, 最大值]（闭区间）
   - `unit`：数值单位字符串

- `command_value`：命令值（如启动命令0xC1，停止命令0xF1,仅仅命令寄存器有效）

2. **数据类型**（小端序）：
   - `data_type`：支持类型
     - `"uint32_t"`：32位无符号整数
     - `"int32_t"`：32位有符号整数  
     - `"uint16_t"`：16位无符号整数（占用完整32位寄存器）
     - `"int16_t"`：16位有符号整数（占用完整32位寄存器）
     - `"fixed_point"`：定点数（浮点数*缩放倍数存储）
     - `"dual_uint16"`：两个uint16_t组合（如端口号）
     - `"ipv4"`：IPv4地址（以uint32_t存储）

3. **JSON配置界面配置信息字段**：
   - `confirm_dialog`：设置时是否需要二次确认（布尔值）
   - `step_size`：SpinBox步长（整数最小1，定点数默认0.1）
   - `hotkey`：快捷键（可选）
   - `qss_file_path`：自定义样式文件路径（可选，没有或者加载失败就不生效）

## 界面实现要求

### 显示逻辑
- **状态寄存器**：显示名称（别名优先）、当前值、单位
- **配置寄存器**：显示名称、当前值、单位、设置按钮、SpinBox输入框
  - 双击当前值可同步到SpinBox
  - 如需二次确认，弹出对话框显示"将寄存器[名称]从[旧值]设置为[新值]"
- **命令寄存器**：每个命令值对应一个按钮，点击发送对应命令

### 技术实现
1. **数据接收**：通过`on_sys_regs_upload(self, sys_reg_upload: SysREGsUpData)`接收下位机上传的所有寄存器数据（从地址0开始）
2. **寄存器配置发送**：通过`async def device_reg_set(self, regAddrStart: int, datas: list[int]) -> bool`设置寄存器
   - 成功：绿色气泡提示"寄存器[名称]从[旧值]设置为[新值]成功"
   - 失败：红色气泡提示"寄存器[名称]设置失败"
3. **在线状态**：界面需包含下位机在线状态指示器（后续会添加相关信号和函数）

### 代码架构要求
- 创建独立的UI文件和Python模块，与现有代码解耦
- 使用qasync异步框架
- 避免槽函数自动绑定（避免特定命名规则）
- QSS样式文件独立存放，不写在代码中
- 界面美观，用户体验良好

### 寄存器地址定义
```c
#define SYS_CFG_REG_NUM 55        // 配置寄存器数量
#define SYS_STATUS_REG_NUM 50     // 状态寄存器数量  
#define SYS_CMD_REG_NUM 2         // 命令寄存器数量

// 地址范围
#define SYS_CFG_REG_ADDR_BASE 0                    // 配置寄存器起始地址
#define SYS_STATUS_REG_ADDR_BASE 55                // 状态寄存器起始地址
#define SYS_CMD_REG_ADDR_BASE 105                  // 命令寄存器起始地址

// 命令寄存器地址
#define SYS_CMD_REG_ADDR1 105     // 启动/停止命令寄存器
#define SYS_CMD_REG_ADDR2 106     // 预留命令寄存器
```

### 数据转换规则
下位机使用以下转换：
```c
#define FLOAT_TO_U32_FIXED_POINT(fp32_var) ((uint32_t)((int32_t)((fp32_var) * (100000))))
#define U32_FIXED_POINT_TO_FLOAT(u32_var) (((int32_t)(u32_var)) * 0.00001f)
```

大部分寄存器为定点数类型，特殊类型包括：
- IPv4地址寄存器（地址1,2,3,5）
- 端口号寄存器（地址6）：dual_uint16类型
- UID和MAC地址寄存器：uint32_t类型
- 其他整数配置寄存器：uint32_t类型

请基于以上规范实现完整的寄存器管理界面系统。

具体的寄存器列表：

// Sync cpu1's default variable to registers, for first save
    WR(0, GetUID0());                         // UID
    WR(1, IPV4_TO_UINT32(192, 168, 137, 99)); // Self IP
    WR(2, IPV4_TO_UINT32(192, 168, 137, 2));  // Gateway IP
    WR(3, IPV4_TO_UINT32(255, 255, 255, 0));  // Netmask
    WR(4, GetUID0());                         // MAC Address Low 4 bytes, here use UID
    WR(5, IPV4_TO_UINT32(192, 168, 137, 2));  // Dest IP
    uint16_t self_port = 16011;
    uint16_t dest_port = 16011;
    uint32_t port = ((uint32_t)self_port << 16) | dest_port;
    WR(6, port); // Dest IP
    WR(7, 0);    // 保留

    // USER_VAR_STORE mVar_RAM
    extern USER_VAR_STORE mVar_RAM;
    extern const USER_VAR_STORE mVar_Store_InUse;
    int addr = 8;
    WR(addr++, mVar_RAM.EPWM_PERIOD_Base);
    WR(addr++, mVar_RAM.EPWM_DB);
    WR(addr++, mVar_RAM.TIMER0_PRD);
    WR(addr++, mVar_RAM.TIMER1_PRD);
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.DutyMAX));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.DutyMIN));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Rottx_Zero_Current));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Speed.PID_Kp));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Speed.PID_Ki));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Speed.PID_Kd));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Speed.PID_Kd_Filter));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Id.PID_Kp));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Id.PID_Ki));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Id.PID_Kd));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Id.PID_Kd_Filter));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Iq.PID_Kp));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Iq.PID_Ki));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Iq.PID_Kd));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.PID_Parameters.PID_Iq.PID_Kd_Filter));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Id_Max));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Id_Min));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Id_Min));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Id_Max_Lowspeed));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Id_Min_Lowspeed));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Iq_Max));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Iq_Min));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Iq_Max_Lowspeed));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Iq_Min_Lowspeed));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Speed_Max));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Motor_Speed_Min));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Reserved1));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Limits.Reserved2));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Ld));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Ld_Inv));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Lq));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Lq_Inv));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Flux));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Rs));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Pn));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Pn_Inv));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_Resolver_Zero));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(mVar_RAM.Motor_Parameters.Motor_RpstoRpm_COEF));
    WR(addr++, mVar_RAM.mEncrypt); // 8+43 = 51

    addr = SYS_STATUS_REG_ADDR_BASE;
    extern MOTOR_CONTROL_VARIABLES MCV;
    // SYS_STATUS_REG_ADDR_BASE
    WR(addr++, PACK_U32_FROM_U16(MCV.MotorPosition, MCV.ResovlerFault));
    WR(addr++, PACK_U32_FROM_U16(MCV.mAngle, MCV.Reserved));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEtheta));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEtheta1));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEthetaAVG));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEthetaRad));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mEthetaZero));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Vdd_P_3V3));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mPT1));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mPT2));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mPT3));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mPT4));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mPT5));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Vdd_P_5V));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mNTC1));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mNTC2));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mTempNTC1));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mTempNTC2));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Ia));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Ib));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Ic));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Vbus));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Vbus_protect));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Vbus_filter));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Ibus));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Set_Speed_Ref));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Last_Set_Speed_Ref));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.RampSet_Speed_Ref));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mSpeed));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mDuty));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.we));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.mTe_ref));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Va));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Vb));
    WR(addr++, FLOAT_TO_U32_FIXED_POINT(MCV.Vc));
