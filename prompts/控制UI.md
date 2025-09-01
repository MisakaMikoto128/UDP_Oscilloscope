使用中文同我高效交流

如main.py所示，我又一个self.receiver用于UDP和下位机通信。

我的下位机设置了一堆32bit的寄存器，分为配置寄存器、状态寄存器和命令寄存器，配置寄存器可以通过上位机设置值，状态寄存器只能收到数据并且显示，命令寄存器的寄存器值就是一个命令。

由于寄存器众多，我认为一个个手动设置界面很费时间，所以我觉得可以使用json配置文件来描述每一个寄存器，自动生成界面。

具体来说这个json文件描述了如下信息：

寄存器变量名：变量名字
寄存器别名：寄存器别名，别名存在的情况下就显示别名，否则显示变量名。
寄存器读写权限：三种，r代表能够读取(状态)，rw代表既能够读取也能够写入（配置），w代表只能写入（命令）。
寄存器数据类型：默认都是小端序，包括整数类型：uint32_t、int32_t、int16_t、uint16_t、定点数、还有两个uint16_t组合为一个寄存器的类型，IPV4以uint32_t存储的类型，这些每个类型使用一个32bit的寄存器，即使uint16_t这种也是使用一个完整的32bit的寄存器。
缩放倍数：仅针对定点数存在，默认缩放倍数为100000，即发送时候寄存器的值为目标浮点数乘以缩放倍数，解析的时候除以缩放倍数。
寄存器范围：限定上位机面板设置寄存器时候的有效值，如果用户设置的只不在有效范围就警告。使用list，左边是最小值，右边是最大值，闭区间。
寄存器单位：用于指示寄存器值的单位。
命令值：仅仅命令寄存器有效。
然后是每个寄存器界面相关的配置：
设置时是否弹出二次确认窗口:设置配置寄存器的时候是否需要二次确认，需要二次确认则弹出窗口上面写明需要设置的寄存器的名称，变量从什么变成什么。
变化步长：设置寄存器值的时候spinbox的步长，整数寄存器最小为1，定点数默认为0.1吧，其他的类型不支持步长。
快捷键：可以配置快捷键来通过按键操作，默认没有快捷键。

界面实现上面：
状态寄存器只需要显示寄存器的名称（有别名就显示别名）、值、单位。
配置寄存器
配置寄存器需要显示寄存器的名称（有别名就显示别名）、值、单位、设置按钮、设置值输入的spinbox、双击值可以同步当前接收到的值到spinbox,如果需要二次确认需要弹出确认对话框，确认才设置，否则不设置。
命令寄存器比较特殊，一个命令寄存器可以设置多个按钮发出不同的命令，一次一个配置描述一个按钮功能，点击按钮就发送对应的命令值即可。目前有停机和启动两个命令，就是用下面说的SYS_CMD_REG_ADDR1这个地址发送命令即可，启动命令为0xC1,
停止命令为0xF1。
寄存器界面的qss文件路径：无效则使用默认样式。

具体API:
目前寄存器的数据会通过下位机主动上传，上传的回到函数是def on_sys_regs_upload(self, sys_reg_upload: SysREGsUpData):
位于main.py，下位机会一次性上传所有寄存器，从地址0开始。
收到数据和刷新界面上的数据即可。

对于命令和配置寄存器则通过async def device_reg_set(self, regAddrStart: int, datas: list[int]) -> bool:这个异步函数设置寄存器，这个异步函数如果超时设置失败会返回false，这时候需要气泡提示无需确认的提示，红色显示那个寄存器设置失败了，如果设置成功则绿色气泡无需确认提示一下，显示寄存器值从多少设置为多少成功了。

技术要求：
要求这个界面单独实现，有单独的UI文件，和现有代码尽量解耦合，注意项目使用了qasync，槽函数在某些命名规则下面会自动绑定，我不喜欢自动绑定，所以注意避免槽函数的命名造成自动绑定。

界面上面增加一个下位机在线状态指示，后面我会给UDPReceiver增加一个读取下位机在线状态信号、和读取下位机在线状态的函数指示上位机上下线。

要求界面整体要美观，使用到的qss要单独作为文件存放，避免放到代码里面去。

具体的寄存器列表：
#define SYS_CFG_REG_NUM 55
#define SYS_STATUS_REG_NUM 50
#define SYS_CMD_REG_NUM 2

#define SYS_REG_NUM (SYS_CFG_REG_NUM + SYS_STATUS_REG_NUM + SYS_CMD_REG_NUM)

#define SYS_REG_ADDR_BASE 0
#define SYS_REG_ADDR_END (SYS_REG_ADDR_BASE + SYS_REG_NUM - 1)

#define SYS_CFG_REG_ADDR_BASE (0 + SYS_REG_ADDR_BASE)
#define SYS_CFG_REG_ADDR_END (SYS_CFG_REG_ADDR_BASE + SYS_CFG_REG_NUM - 1)

#define SYS_STATUS_REG_ADDR_BASE (0 + SYS_REG_ADDR_BASE + SYS_CFG_REG_NUM)
#define SYS_STATUS_REG_ADDR_END (SYS_STATUS_REG_ADDR_BASE + SYS_STATUS_REG_NUM - 1)

#define SYS_CMD_REG_ADDR_BASE (0 + SYS_REG_ADDR_BASE + SYS_CFG_REG_NUM + SYS_STATUS_REG_NUM)
#define SYS_CMD_REG_ADDR_END (SYS_CMD_REG_ADDR_BASE + SYS_CMD_REG_NUM - 1)

#define SYS_CMD_REG_ADDR1 (SYS_CMD_REG_ADDR_BASE + 0)
#define SYS_CMD_REG_ADDR2 (SYS_CMD_REG_ADDR_BASE + 1)

如下是我的下位机上传寄存器数据的代码，绝大部分寄存器都是浮点数，除了IPV4寄存器，self_port/dest_port寄存器较为特殊是两个uint16_t组合类型外，其余寄存器均为一个字段一个寄存器。
#define FLOAT_TO_U32_FIXED_POINT(fp32_var) ((uint32_t)((int32_t)((fp32_var) * (100000))))
#define U32_FIXED_POINT_TO_FLOAT(u32_var) (((int32_t)(u32_var)) * 0.00001f)
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






