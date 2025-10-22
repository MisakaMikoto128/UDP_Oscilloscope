1. 安装编译加速依赖(最重要)
在Windows上使用MSVC编译器时,clcache会自动启用并包含在Nuitka中 CodersLegacy,但你需要安装一些额外的包:
batchREM 在脚本开头添加
pip install ordered-set --break-system-packages
pip install zstandard --break-system-packages
ordered-set包可以显著加速编译时间 CodersLegacy,这是Nuitka官方推荐的优化。