import asyncio
import sys
import logging
import winloop
import pyqtgraph as pg
from PyQt5 import QtWidgets
from config.config_manager import ConfigManager
from window.main_window import MainWindow

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("oscilloscope.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


async def main_async(app, window):
    """异步主函数"""
    await window.receiver.start()
    logger.info("应用程序启动完成")
    # 等待 Qt 退出信号
    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)
    await app_close_event.wait()
    await window.receiver.stop()


def main():
    """主入口函数"""
    try:
        # 启用OpenGL加速
        pg.setConfigOptions(
            useOpenGL=True,  # 启用OpenGL加速
            # enableExperimental=True,  # 启用实验性功能
            antialias=False,  # 关闭抗锯齿（性能提升明显）
            crashWarning=False,  # 关闭崩溃警告
        )

        try:
            winloop.install()  # 必须在任何 asyncio/qasync 调用之前
            logger.info("winloop 已启用")
        except Exception as e:
            logger.warning("winloop 不可用，回退到默认事件循环: %s", e)

        print(type(asyncio.get_event_loop()))
        # # 在Windows上设置事件循环策略
        # if sys.platform == "win32":
        #     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        #     # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # 创建Qt应用
        app = QtWidgets.QApplication(sys.argv)
        app.setApplicationName("UDP示波器")
        app.setApplicationVersion("1.0.0")

        # 加载配置
        cfg = ConfigManager()

        # 创建主窗口
        window = MainWindow(cfg)
        window.show()

        # 设置异步事件循环
        # 3. 让qasync基于当前事件循环（winloop）创建QEventLoop
        from qasync import QEventLoop

        event_loop = QEventLoop(app)
        asyncio.set_event_loop(event_loop)

        app_close_event = asyncio.Event()
        app.aboutToQuit.connect(app_close_event.set)

        print(type(asyncio.get_event_loop()))

        with event_loop:
            event_loop.run_until_complete(main_async(app, window))
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
