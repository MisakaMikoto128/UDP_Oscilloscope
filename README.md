# OTA设备管理系统

这是一个用于管理OTA设备升级的Web后台管理系统，基于Flask框架开发。

## 功能特点

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