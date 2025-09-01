#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
寄存器管理界面测试脚本
用于测试寄存器管理界面的功能
"""

import sys
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer
import qasync

from ui.register_integration import RegisterTabWidget
from communication.protocol import SysREGsUpData

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class TestMainWindow(QMainWindow):
    """测试主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("寄存器管理界面测试")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 创建寄存器管理界面
        config_file_path = project_root / "config" / "registers_config_example.json"
        self.register_widget = RegisterTabWidget(
            config_file_path=str(config_file_path),
            device_reg_set_func=self.mock_device_reg_set,
            parent=self
        )
        
        layout.addWidget(self.register_widget)
        
        # 创建模拟数据定时器
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.send_mock_data)
        self.data_timer.start(2000)  # 每2秒发送一次模拟数据
        
        logger.info("测试窗口初始化完成")
    
    async def mock_device_reg_set(self, address: int, data_list: list) -> bool:
        """模拟设备寄存器设置函数"""
        try:
            logger.info(f"模拟设置寄存器 地址={address}, 数据={data_list}")
            
            # 模拟网络延迟
            await asyncio.sleep(0.1)
            
            # 模拟90%的成功率
            import random
            success = random.random() > 0.1
            
            if success:
                logger.info(f"寄存器设置成功: 地址={address}")
            else:
                logger.warning(f"寄存器设置失败: 地址={address}")
            
            return success
            
        except Exception as e:
            logger.error(f"模拟设置寄存器失败: {e}")
            return False
    
    def send_mock_data(self):
        """发送模拟寄存器数据"""
        try:
            import random
            import struct
            
            # 创建模拟寄存器数据（107个寄存器）
            mock_registers = []
            
            for i in range(107):
                if i == 0:  # UID
                    value = 0x12345678
                elif i == 1:  # IP地址 - 使用下位机的字节序格式
                    # 192.168.1.99 = (192<<24)|(168<<16)|(1<<8)|99
                    value = (192 << 24) | (168 << 16) | (1 << 8) | 99
                elif i == 6:  # 端口配置
                    value = (16011 << 16) | 16011
                elif i in [12, 13]:  # 占空比 (定点数)
                    float_val = random.uniform(0.1, 0.9)
                    value = int(float_val * 100000) & 0xFFFFFFFF
                elif i in range(15, 27):  # PID参数 (定点数)
                    float_val = random.uniform(0.001, 10.0)
                    value = int(float_val * 100000) & 0xFFFFFFFF
                elif i in range(73, 90):  # 状态寄存器 (定点数)
                    if i == 73:  # Ia
                        float_val = random.uniform(-100.0, 100.0)
                    elif i == 74:  # Ib
                        float_val = random.uniform(-100.0, 100.0)
                    elif i == 76:  # Vbus
                        float_val = random.uniform(300.0, 400.0)
                    elif i == 83:  # mSpeed
                        float_val = random.uniform(0.0, 3000.0)
                    else:
                        float_val = random.uniform(-50.0, 50.0)
                    
                    # 转换为定点数
                    int_val = int(float_val * 100000)
                    if int_val < 0:
                        value = (int_val + 2**32) & 0xFFFFFFFF
                    else:
                        value = int_val & 0xFFFFFFFF
                else:
                    value = random.randint(0, 1000)
                
                mock_registers.append(value)
            
            # 创建模拟的SysREGsUpData
            mock_data = SysREGsUpData(
                packet_type=0xB1,
                reg_num=len(mock_registers),
                reg=mock_registers
            )
            
            # 发送到寄存器管理界面
            self.register_widget.on_sys_regs_upload(mock_data)
            
            logger.debug(f"发送了 {len(mock_registers)} 个模拟寄存器数据")
            
        except Exception as e:
            logger.error(f"发送模拟数据失败: {e}")


async def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 创建测试窗口
    window = TestMainWindow()
    window.show()
    
    # 运行应用
    await qasync.asyncio.run_forever()


if __name__ == "__main__":
    try:
        # 设置事件循环策略（Windows）
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # 运行应用
        qasync.run(main())
        
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("程序退出")
