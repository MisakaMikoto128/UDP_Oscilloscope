import logging
import multiprocessing as mp
import asyncio
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QMenu,
    QSystemTrayIcon,
)
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout
from qfluentwidgets import (
    FluentIcon as FIF,
)
from qfluentwidgets import (
    NavigationItemPosition,
    FluentWindow,
    NavigationAvatarWidget,
    SubtitleLabel,
    setFont,
)
import time
from .ctrl_panel_frame import CtrlPanelForm
from .device_setting import DeviceSettingFrom
from .network_setting_frame import NetworkSettingFrom
from .setting_frame import SettingForm
from .oscilloscope_frame import OscilloscopeFrame
from ..communication.udp_master import UDPMaster
from ..communication.scope_ipc import create_scope_ipc
from PyQt5.QtGui import QCloseEvent
from qasync import asyncClose, asyncSlot
from qfluentwidgets import InfoLevel, setThemeColor
from qfluentwidgets import (NavigationItemPosition, MessageBox, FluentWindow,
                            NavigationAvatarWidget, SubtitleLabel, setFont)
from qfluentwidgets.components.material import AcrylicMenu
from qfluentwidgets import FluentIcon as FIF, TableWidget, Theme, setTheme, SwitchButton, AvatarWidget, BodyLabel, \
    CaptionLabel, HyperlinkButton, isDarkTheme, FluentIcon, Action
from PyQt5.QtGui import QFont, QStandardItemModel, QColor
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon, QTableWidgetItem, QHeaderView, QWidget

logger = logging.getLogger(__name__)


def _run_scope_process(scope_ipc):
    """在独立进程中运行示波器"""
    import sys
    from PyQt5.QtWidgets import QApplication
    import pyqtgraph as pg

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # 高性能OpenGL配置
    pg.setConfigOptions(
        useOpenGL=True,  # 启用OpenGL加速
        antialias=False,  # 关闭抗锯齿（性能提升明显）
        crashWarning=False,  # 关闭崩溃警告
        useNumba=True,  # 启用Numba加速（如果可用）
        enableExperimental=False,  # 关闭实验性功能
        # leftButtonPan=False,  # 禁用不必要的交互
    )
    try:
        # 创建Qt应用（独立进程）
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(True)

        # 预设样式表（减少运行时计算）
        app.setStyleSheet("QWidget { font-family: 'Microsoft YaHei'; }")

        # 创建示波器窗口（仅IPC模式）
        scope_frame = OscilloscopeFrame(scope_ipc)

        # 设置窗口关闭事件为隐藏而非退出
        def on_close_event(event):
            scope_frame.hide()  # 隐藏窗口
            # 通过命令队列发送预览模式命令
            try:
                command_queue = scope_ipc.get_command_queue()
                command_queue.put_nowait({'action': 'set_preview_mode'})
            except Exception:
                pass  # 队列满时忽略
            event.ignore()  # 忽略关闭事件

        scope_frame.closeEvent = on_close_event
        scope_frame.show()

        logger.info("示波器进程启动完成")

        # 运行Qt事件循环
        app.exec_()

    except Exception as e:
        logger.error(f"示波器进程运行失败: {e}")
        raise
        
class MainWindow(FluentWindow):
    def __init__(self, cfg):
        super().__init__()

        # 保存配置引用
        self.cfg = cfg

        # 初始化进程间通信
        self.scope_ipc = create_scope_ipc(queue_size=1024*1024*5)

        # 初始化UDP接收器（移到主进程）
        self.receiver = UDPMaster(
            host=cfg.udp_host,
            port=cfg.udp_port,
            on_sample=self._on_sample_received,
        )

        # 示波器进程
        self.scope_process = None
        self.scope_window_visible = True  # 示波器窗口可见状态

        # 添加一个退出菜单项
        exitAction = QAction(QIcon("./img/sp-exit.png"), "Exit", self)
        exitAction.triggered.connect(self.close)

        # 创建托盘菜单
        trayMenu = QMenu(self)
        trayMenu.addAction(exitAction)
        # 创建系统托盘图标
        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setIcon(QIcon("./img/star.png"))
        self.trayIcon.setContextMenu(trayMenu)
        self.trayIcon.show()

        self.interface1 = CtrlPanelForm(cfg, None, self.receiver.reg_set, self)
        self.receiver.on_sys_regs_upload.connect(self.interface1.on_on_sys_regs_uploaded)
        self.receiver.client_online_status_changed.connect(self.interface1.on_net_online_status_changed)

        self.interface2 = DeviceSettingFrom(cfg, None, self.receiver.reg_set, self)
        self.receiver.on_sys_regs_upload.connect(self.interface2.on_on_sys_regs_uploaded)
        self.interface1.set_sw_btn_ctrl_mode_select(self.interface2.btn_ctrl_mode_select)

        self.interface3 = NetworkSettingFrom(cfg, None, self.receiver.reg_set, self)
        self.receiver.on_sys_regs_upload.connect(self.interface3.on_on_sys_regs_uploaded)
        # 连接设备信息更新信号
        self.interface3.device_info_updated.connect(self.update_window_title)

        self.settingInterface = SettingForm(cfg, None, self.receiver.reg_set, self)
        self.settingInterface.sw_scope.checkedChanged.connect(
            lambda checked: self.show_scope_window()
            if checked
            else self.hide_scope_window()
        )

        # 初始化界面
        self.initNavigation()
        self.initWindow()

        # 启动性能监控
        self._init_performance_monitor()

        # 启动示波器进程（非阻塞）
        self._start_scope_process_async()
        self.start_time = time.time()

    def initNavigation(self):
        self.addSubInterface(self.interface1, FIF.GAME, "监控界面")
        self.addSubInterface(self.interface2, FIF.SAVE, "设备设置")
        self.addSubInterface(self.interface3, FIF.WIFI, "网络设置")
        
        self.switchTo(self.interface1)
        # Theme切换按钮
        self.navigationInterface.addSeparator()

        # add custom widget to bottom
        self.navigationInterface.addWidget(
            routeKey="avatar",
            widget=NavigationAvatarWidget("Yuanlin-Liu", "resource/h.png"),
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(self.settingInterface, FIF.SETTING, 'Settings', NavigationItemPosition.BOTTOM)
        self.navigationInterface.setAcrylicEnabled(True)


    def initWindow(self):
        # 设置窗口的初始大小 (宽 x 高)
        self.setWindowTitle("卡方-电机控制器上位机")
        self.setWindowIcon(QIcon("./img/star.png"))

        self.showMaximized()

    def update_window_title(self, device_name: str, uid: str, device_ip: str, pc_port: int, device_port: int):
        """更新窗口标题显示设备信息"""
        try:
            # 构建美观的标题
            base_title = "卡方-电机控制器上位机"
            device_info = f"{device_name} ({uid}) | 设备IP: {device_ip} | PC端口: {pc_port} | 设备端口: {device_port}"
            full_title = f"{base_title} - {device_info}"

            self.setWindowTitle(full_title)

            # 同时更新示波器窗口标题
            if self.scope_process and self.scope_process.is_alive():
                scope_title = f"示波器 - {device_info}"
                self.scope_ipc.send_scope_command({
                    'action': 'update_title',
                    'title': scope_title
                })

            # logger.info(f"窗口标题已更新: {device_info}")

        except Exception as e:
            logger.error(f"更新窗口标题失败: {e}")
            # 如果更新失败，至少保持基本标题
            self.setWindowTitle("卡方-电机控制器上位机")

    def _init_performance_monitor(self):
        """初始化性能监控"""
        self.perf_timer = QTimer(self)
        self.perf_timer.timeout.connect(self._update_performance_stats)
        self.perf_timer.start(5000)  # 每5秒更新一次

    def _update_performance_stats(self):
        """更新性能统计"""
        try:
            stats = self.scope_ipc.get_combined_stats()
            logger.debug(f"性能统计: {stats}")

            # 检查队列健康状态
            if stats['sender']['drop_count'] > 100:
                logger.warning(f"检测到队列丢包: {stats['sender']['drop_count']}")

        except Exception as e:
            logger.error(f"更新性能统计失败: {e}")

    def _start_scope_process_async(self):
        """异步启动示波器进程（避免主界面卡顿）"""
        def start_in_thread():
            try:
                success = self.start_scope_process()
                if success:
                    logger.info("示波器进程异步启动成功")
                else:
                    logger.error("示波器进程异步启动失败")
            except Exception as e:
                logger.error(f"异步启动示波器进程失败: {e}")

        import threading
        thread = threading.Thread(target=start_in_thread, daemon=True)
        thread.start()

    def _on_sample_received(self, fmt: int, values: list):
        """UDP采样数据回调 - 转发到示波器进程"""
        try:
            # 高性能转发到示波器进程
            sender = self.scope_ipc.get_sender()
            success = sender.send_sample(fmt, values)
            if not success:
                # 记录转发失败，但不影响主进程性能
                pass
        except Exception as e:
            logger.error(f"转发采样数据失败: {e}")

    def start_scope_process(self):
        """启动示波器进程"""
        try:
            self.scope_process = mp.Process(
                target=_run_scope_process,
                args=(self.scope_ipc,),
                name="ScopeProcess",
                daemon=True
            )
            self.scope_process.start()

            # 等待示波器进程就绪
            if self.scope_ipc.wait_scope_ready(timeout=10):
                logger.info("示波器进程启动成功")
                return True
            else:
                logger.error("示波器进程启动超时")
                return False

        except Exception as e:
            logger.error(f"启动示波器进程失败: {e}")
            return False

    async def start_receiver(self):
        """启动UDP接收器"""
        try:
            await self.receiver.start()
            logger.info("UDP接收器已启动")
        except Exception as e:
            logger.error(f"启动UDP接收器失败: {e}")

    async def stop_receiver(self):
        """停止UDP接收器"""
        try:
            await self.receiver.stop()
            logger.info("UDP接收器已停止")
        except Exception as e:
            logger.error(f"停止UDP接收器失败: {e}")

    def show_scope_window(self):
        """显示示波器窗口"""
        try:
            if self.scope_process and self.scope_process.is_alive():
                self.scope_ipc.send_scope_command({'action': 'show_window'})
                self.scope_window_visible = True
                logger.info("示波器窗口已显示")
            else:
                logger.warning("示波器进程未运行，无法显示窗口")
        except Exception as e:
            logger.error(f"显示示波器窗口失败: {e}")

    def hide_scope_window(self):
        """隐藏示波器窗口"""
        try:
            if self.scope_process and self.scope_process.is_alive():
                self.scope_ipc.send_scope_command({'action': 'hide_window'})
                self.scope_ipc.send_scope_command({'action': 'set_preview_mode'})  # 设置为预览模式减少GPU占用
                self.scope_window_visible = False
                logger.info("示波器窗口已隐藏并切换到预览模式")
            else:
                logger.warning("示波器进程未运行，无法隐藏窗口")
        except Exception as e:
            logger.error(f"隐藏示波器窗口失败: {e}")

    def toggle_scope_window(self):
        """切换示波器窗口显示/隐藏状态"""
        if self.scope_window_visible:
            self.hide_scope_window()
        else:
            self.show_scope_window()

    def stop_scope_process(self):
        """停止示波器进程"""
        try:
            if self.scope_process and self.scope_process.is_alive():
                self.scope_ipc.signal_shutdown()
                self.scope_process.join(timeout=3)
                if self.scope_process.is_alive():
                    logger.warning("强制终止示波器进程")
                    self.scope_process.terminate()
                    self.scope_process.join(timeout=2)
                logger.info("示波器进程已停止")

            # 清理IPC资源
            self.scope_ipc.cleanup()

        except Exception as e:
            logger.error(f"停止示波器进程失败: {e}")

    @asyncSlot(QCloseEvent)
    async def closeEvent(self, event):
        """窗口关闭事件"""
        print("主窗口关闭事件被调用")

        # 0. 关闭子窗口
        # try:
        #     if hasattr(self, 'interface1') and self.interface1:
        #         self.interface1.close()
        #         logger.info("CtrlPanelForm已关闭")
        #     if hasattr(self, 'interface2') and self.interface2:
        #         self.interface2.close()
        #         logger.info("DeviceSettingFrom已关闭")
        # except Exception as e:
        #     logger.error(f"关闭子窗口失败: {e}")
        await self.interface1.close_user()
        await self.stop_receiver()
        
        # 1. 取消所有异步任务（主线程）
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 创建任务但不等待完成，让事件循环自然处理
                asyncio.create_task(self.stop_receiver())
            else:
                # 如果事件循环未运行，同步停止
                asyncio.run(self.stop_receiver())
        except Exception as e:
            logger.error(f"停止UDP接收器失败: {e}")
        
        try:
            # 3. 停止示波器进程（后台线程，避免阻塞主线程）
            def stop_scope_in_background():
                try:
                    self.stop_scope_process()
                    logger.info("示波器进程后台清理完成")
                except Exception as e:
                    logger.error(f"后台停止示波器进程失败: {e}")
            import threading
            scope_cleanup_thread = threading.Thread(target=stop_scope_in_background, daemon=True)
            scope_cleanup_thread.start()

            logger.info("主窗口关闭处理完成")

        except Exception as e:
            logger.error(f"关闭窗口时出错: {e}")
        finally:
            # 接受关闭事件
            event.accept()

    

