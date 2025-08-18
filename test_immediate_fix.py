# -*- coding: utf-8 -*-
"""
立即测试修复效果
"""

import sys
import logging
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_main_app():
    """测试主应用程序"""
    import asyncio
    from main import main
    
    print("=" * 60)
    print("立即测试修复效果")
    print("=" * 60)
    print("修复内容:")
    print("1. 滚轮事件：重写graphics_widget的wheelEvent")
    print("2. 通道配置面板：修复布局逻辑")
    print("3. 滚动区域：添加到通道配置页面")
    print()
    print("测试步骤:")
    print("1. 启动后检查右侧是否有通道配置面板")
    print("2. 在黑色示波器区域滚动鼠标滚轮")
    print("3. 按住Ctrl滚动滚轮")
    print("4. 拖拽鼠标测试偏移")
    print("5. 切换自动滚动模式")
    print()
    print("预期结果:")
    print("- 右侧应该显示完整的通道配置界面")
    print("- 滚轮操作应该有控制台输出")
    print("- 所有交互功能正常工作")
    print("=" * 60)
    
    # 启动主应用
    main()

if __name__ == "__main__":
    test_main_app()
