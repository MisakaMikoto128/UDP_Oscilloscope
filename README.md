# UDP示波器 - 电机控制板上位机软件

一个基于PyQt5和pyqtgraph的高性能UDP示波器应用，专为电机控制板数据监控和参数配置而设计。

## 功能特性

### 核心功能
- **实时数据显示**: 支持10通道同时显示，刷新率可达120fps
- **UDP通信**: 异步UDP数据接收，支持CRC校验和丢包统计
- **滚动模式**: 专业示波器风格的滚动显示模式
- **数据存储**: 1GB内存缓存 + 可选永久存储(HDF5格式)
- **OpenGL加速**: 使用OpenGL硬件加速提升绘图性能

### 界面功能
- **通道配置**: 每通道独立的垂直挡位、偏移、单位、颜色设置
- **光标测量**: X/Y轴光标，支持时间和幅值测量
- **统计信息**: 实时显示最小值、最大值、平均值、RMS值
- **配置管理**: JSON配置文件，支持热重载

### 通信协议
- **数据格式**: 支持uint16和float32两种采样数据格式
- **配置传输**: 支持PID参数的上传和下载
- **错误处理**: CRC校验失败时智能恢复，避免数据丢失

## 系统要求

- **操作系统**: Windows 11 (推荐) / Windows 10
- **Python版本**: Python 3.11.4+
- **内存**: 建议4GB以上
- **显卡**: 支持OpenGL的显卡

## 安装和运行

### 1. 环境准备

```bash
# 克隆项目
git clone <repository_url>
cd UDP_Oscilloscope

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 运行应用

```bash
# 方法1: 直接运行
python src/main.py

# 方法2: 使用测试脚本
python test_app.py
```

### 3. 测试模拟器

```bash
# 启动下位机模拟器 (用于测试)
python test_simulator.py
```

- 设备管理：添加、编辑、删除设备
- OTA升级：支持单个设备和批量设备升级
- 任务管理：查看OTA升级任务状态和进度
- 实时更新：使用WebSocket实时更新任务状态

## 安装步骤

1. 安装依赖

```bash
cd web_admin
pip install -r requirements.txt
```

2. 初始化数据库

```bash
python app.py
```

首次运行时会自动创建数据库和管理员用户。

## 使用方法

1. 启动服务器

```bash
python app.py
```

2. 访问系统

打开浏览器，访问 http://localhost:5000

3. 登录系统

默认管理员账号：
- 用户名：admin
- 密码：admin

## 目录结构

```
web_admin/
├── app.py              # 主应用程序
├── requirements.txt    # 依赖列表
├── static/             # 静态文件
├── templates/          # HTML模板
│   ├── base.html       # 基础模板
│   ├── index.html      # 首页
│   ├── login.html      # 登录页
│   ├── devices.html    # 设备列表页
│   ├── device_form.html # 设备表单页
│   └── ota_tasks.html  # OTA任务页
└── README.md           # 说明文档
```

## 注意事项

- 确保父目录中的OTA客户端模块可以正常导入
- 默认使用SQLite数据库，数据文件保存在当前目录
- 生产环境部署时请修改SECRET_KEY和数据库配置 