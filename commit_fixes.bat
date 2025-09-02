@echo off
echo 提交寄存器管理界面修复...
echo.

REM 检查git状态
git status

echo.
echo 添加修改的文件...
git add src/ui/register_manager.py
git add src/main.py
git add docs/register_manager_fixes.md
git add test/test_register_manager.py

echo.
echo 提交修改...
git commit -m "修复寄存器管理界面问题

1. 修复命令label显示命令值（16进制格式）
2. 修改寄存器管理界面为独立窗口，通过测试按钮控制显示/隐藏
3. 修复刷新配置后界面变空白的问题

- 命令按钮现在显示命令值（如0xC1, 0xF1）
- 寄存器管理界面作为独立窗口运行
- 重新加载配置时保持界面结构完整
- 改进错误处理和用户体验"

echo.
echo 提交完成！
echo.
git log --oneline -5

pause
