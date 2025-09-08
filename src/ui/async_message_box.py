# -*- coding: utf-8 -*-
"""
异步消息框组件
提供基于qfluentwidgets MessageBox的异步确认对话框
"""

import asyncio
from typing import Optional
from PyQt5.QtCore import QObject
from qfluentwidgets import MessageBox


class AsyncMessageBox(QObject):
    """异步消息框类

    基于qfluentwidgets MessageBox实现的异步确认对话框
    支持async/await语法，避免在异步函数中使用同步MessageBox导致的事件循环问题
    """

    def __init__(self, title: str, content: str, parent=None):
        """
        初始化异步消息框

        Args:
            title: 对话框标题
            content: 对话框内容
            parent: 父窗口
        """
        super().__init__(parent)
        self.title = title
        self.content = content
        self.parent = parent
        self._future: Optional[asyncio.Future] = None
        self._message_box: Optional[MessageBox] = None

    async def exec_async(self) -> bool:
        """
        异步执行对话框

        Returns:
            bool: True表示用户点击确认，False表示用户点击取消或关闭
        """
        # 创建Future对象用于异步等待
        self._future = asyncio.Future()

        # 创建MessageBox
        self._message_box = MessageBox(self.title, self.content, self.parent)

        # 连接信号槽
        self._message_box.accepted.connect(self._on_accepted)
        self._message_box.rejected.connect(self._on_rejected)
        self._message_box.finished.connect(self._on_finished)

        # 显示对话框
        self._message_box.show()

        # 等待用户操作
        try:
            result = await self._future
            return result
        except asyncio.CancelledError:
            # 如果任务被取消，关闭对话框
            if self._message_box:
                self._message_box.close()
            return False
        finally:
            self._cleanup()

    def _on_accepted(self):
        """用户点击确认按钮"""
        if self._future and not self._future.done():
            self._future.set_result(True)

    def _on_rejected(self):
        """用户点击取消按钮"""
        if self._future and not self._future.done():
            self._future.set_result(False)

    def _on_finished(self, result):
        """对话框关闭时的处理"""
        # 如果Future还没有设置结果，说明是通过其他方式关闭的（如点击X按钮）
        if self._future and not self._future.done():
            # result: 0=Rejected, 1=Accepted
            self._future.set_result(result == 1)

    def _cleanup(self):
        """清理资源"""
        if self._message_box:
            # 断开信号连接
            try:
                self._message_box.accepted.disconnect()
                self._message_box.rejected.disconnect()
                self._message_box.finished.disconnect()
            except:
                pass
            self._message_box = None
        self._future = None


class AsyncConfirmDialog:
    """异步确认对话框的便捷类

    提供静态方法快速创建和使用异步确认对话框
    """

    @staticmethod
    async def confirm(title: str, content: str, parent=None) -> bool:
        """
        显示异步确认对话框

        Args:
            title: 对话框标题
            content: 对话框内容
            parent: 父窗口

        Returns:
            bool: True表示用户确认，False表示用户取消

        Example:
            confirmed = await AsyncConfirmDialog.confirm("确认", "是否继续？", self)
            if confirmed:
                # 用户点击了确认
                pass
        """
        dialog = AsyncMessageBox(title, content, parent)
        return await dialog.exec_async()

    @staticmethod
    async def show_info(title: str, content: str, parent=None):
        """
        显示异步信息对话框（只有确认按钮）

        Args:
            title: 对话框标题
            content: 对话框内容
            parent: 父窗口
        """
        dialog = AsyncMessageBox(title, content, parent)
        await dialog.exec_async()


# 为了向后兼容，提供一个简单的函数接口
async def async_confirm(title: str, content: str, parent=None) -> bool:
    """
    异步确认对话框的简单函数接口

    Args:
        title: 对话框标题
        content: 对话框内容
        parent: 父窗口

    Returns:
        bool: True表示用户确认，False表示用户取消

    Example:
        if await async_confirm("确认删除", "确定要删除这个文件吗？", self):
            # 执行删除操作
            pass
    """
    return await AsyncConfirmDialog.confirm(title, content, parent)


async def async_info(title: str, content: str, parent=None):
    """
    异步信息对话框的简单函数接口

    Args:
        title: 对话框标题
        content: 对话框内容
        parent: 父窗口

    Example:
        await async_info("操作完成", "文件已成功保存", self)
    """
    await AsyncConfirmDialog.show_info(title, content, parent)