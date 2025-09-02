from PyQt5.QtCore import Qt
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

from .ctrl_panel_frame import CtrlPanelForm
from .device_setting import DeviceSettingFrom
from ..window.oscilloscope_frame import OscilloscopeFrame

class MainWindow(FluentWindow):
    def __init__(self, cfg):
        super().__init__()

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

        self.scope_frame = OscilloscopeFrame(cfg,)
        self.scope_frame.show()

        self.receiver = self.scope_frame.receiver
        self.interface1 = CtrlPanelForm(cfg,None, self.receiver.reg_set, self)
        self.receiver.on_sys_regs_upload.connect(self.interface1.on_on_sys_regs_uploaded)
        self.receiver.client_online_status_changed.connect(self.interface1.on_net_online_status_changed)
        
        self.interface2 = DeviceSettingFrom(cfg,None, self.receiver.reg_set, self)
        self.receiver.on_sys_regs_upload.connect(self.interface2.on_on_sys_regs_uploaded)
        
        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        self.addSubInterface(self.interface1, FIF.GAME, "监控界面")
        self.addSubInterface(self.interface2, FIF.SAVE, "设备设置")
        
        self.switchTo(self.interface1)
        # Theme切换按钮
        self.navigationInterface.addSeparator()

        # add custom widget to bottom
        self.navigationInterface.addWidget(
            routeKey="avatar",
            widget=NavigationAvatarWidget("Yuanlin-Liu", "resource/shoko.png"),
            position=NavigationItemPosition.BOTTOM,
        )
        self.navigationInterface.setAcrylicEnabled(True)

    def initWindow(self):
        # 设置窗口的初始大小 (宽 x 高)
        self.setWindowTitle("卡方-电机控制器上位机")
        self.setWindowIcon(QIcon("./img/star.png"))

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.resize(w, h)
        self.move(0, 0)

    async def start_receiver(self):
        await self.receiver.start()

    async def stop_receiver(self):
        await self.receiver.stop()

    def closeEvent(self, event):
        print("主窗口关闭事件被调用")
