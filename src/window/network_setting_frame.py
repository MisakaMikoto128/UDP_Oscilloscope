# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from qasync import asyncSlot
from src.ui.async_message_box import async_confirm
from qfluentwidgets import InfoBar, InfoBarPosition

from src.communication.protocol import SysREGsUpData
from src.config.config_manager import ConfigManager
from src.ui import Network_Setting_From
from src.utils.network_utils import uint32_to_ipv4, ipv4_to_uint32, uint32_to_mac, validate_ip, validate_port

logger = logging.getLogger(__name__)


class NetworkSettingFrom(QtWidgets.QFrame, Network_Setting_From):
    """网络设置窗口类"""

    # 定义信号：设备信息更新信号
    device_info_updated = pyqtSignal(str, str, str, int, int)  # device_name, uid, device_ip, pc_port, device_port

    def __init__(
        self,
        cfg: ConfigManager,
        config_file_path: str,
        device_reg_set_func: Callable[[int, List[int]], Awaitable[bool]],
        parent=None,
    ):
        super().__init__(parent=parent)
        self.setupUi(self)

        # 配置管理器
        self.cfg = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        self.setObjectName("Network_Setting_From")

        # 连接按钮信号
        self._connect_network_buttons()
        self.btn_save_net_param.clicked.connect(self._confirm_save_param)

    def _connect_network_buttons(self):
        """连接网络设置按钮"""
        # 本机IP设置按钮
        self.btn_pc_ip_set.clicked.connect(self._set_pc_ip)
        
        # 本机端口设置按钮（与设备端口绑定设置）
        self.btn_pc_port_set.clicked.connect(self._set_port_config)
        
        # 设备IP设置按钮
        self.btn_device_ip_set.clicked.connect(self._set_device_ip)
        
        # 设备端口设置按钮（与本机端口绑定设置）
        self.btn_device_port_set.clicked.connect(self._set_port_config)

        # 设备名称设置按钮
        self.btn_device_name_set.clicked.connect(self._set_device_name)

        # 子网掩码设置按钮（如果存在的话）
        self.btn_device_ip_mask_set.clicked.connect(self._set_netmask)

        # 连接双击label事件
        self._connect_label_double_click()

    def _show_error(self, title: str, content: str):
        """显示错误信息条"""
        InfoBar.error(
            title=title, content=content, orient=Qt.Horizontal,
            isClosable=True, position=InfoBarPosition.TOP,
            duration=2000, parent=self
        )

    def _show_success(self, title: str, content: str):
        """显示成功信息条"""
        InfoBar.success(
            title=title, content=content, orient=Qt.Horizontal,
            isClosable=True, position=InfoBarPosition.TOP,
            duration=2000, parent=self
        )

    def _connect_label_double_click(self):
        """连接label双击事件"""
        # 双击label同步值到对应的输入控件
        self.label_pc_ip.mouseDoubleClickEvent = lambda _: self._sync_label_to_input('pc_ip')
        self.label_pc_port.mouseDoubleClickEvent = lambda _: self._sync_label_to_input('pc_port')
        self.label_device_ip.mouseDoubleClickEvent = lambda _: self._sync_label_to_input('device_ip')
        self.label_device_port.mouseDoubleClickEvent = lambda _: self._sync_label_to_input('device_port')
        self.label_device_name.mouseDoubleClickEvent = lambda _: self._sync_label_to_input('device_name')
        self.label_device_ip_mask.mouseDoubleClickEvent = lambda _: self._sync_label_to_input('device_ip_mask')

    def _sync_label_to_input(self, field_type: str):
        """将label的值同步到对应的输入控件"""
        try:
            if field_type == 'pc_ip':
                self.line_edit_pc_ip.setText(self.label_pc_ip.text())
            elif field_type == 'pc_port':
                try:
                    port_value = int(self.label_pc_port.text())
                    self.spinbox_pc_port.setValue(port_value)
                except ValueError:
                    pass
            elif field_type == 'device_ip':
                self.line_edit_device_ip.setText(self.label_device_ip.text())
            elif field_type == 'device_port':
                try:
                    port_value = int(self.label_device_port.text())
                    self.spinbox_device_port.setValue(port_value)
                except ValueError:
                    pass
            elif field_type == 'device_name':
                self.line_edit_device_name.setText(self.label_device_name.text())
            elif field_type == 'device_ip_mask':
                self.line_edit_device_ip_mask.setText(self.label_device_ip_mask.text())

            logger.info(f"已同步{field_type}的值到输入控件")
        except Exception as e:
            logger.error(f"同步{field_type}值到输入控件失败: {e}")

    @asyncSlot()
    async def _set_pc_ip(self):
        """设置本机IP地址"""
        try:
            new_ip = self.line_edit_pc_ip.text().strip()
            if not validate_ip(new_ip):
                self._show_error('IP地址格式错误', '请输入正确的IP地址格式')
                return
            
            # 获取当前IP用于确认对话框
            current_ip = self.label_pc_ip.text()
            
            # 确认对话框
            title = "确认设置本机IP地址"
            content = f"本机IP地址将从 {current_ip} 设置为 {new_ip}\n\n确认后将立即发送设置命令！"

            confirmed = await async_confirm(title, content, self)
            if confirmed:
                # 转换IP为uint32
                ip_uint32 = ipv4_to_uint32(new_ip)
                target_addr = (self.cfg.target_host, self.cfg.target_port)
                
                # 设置PC IP 和 网关IP
                success1 = await self.device_reg_set_func(2, [ip_uint32], target_addr=target_addr)
                success2 = await self.device_reg_set_func(5, [ip_uint32], target_addr=target_addr)
                
                if success1 and success2:
                    self._show_success('设置成功', f'PC IP和网关IP已设置为 {new_ip}，保存参数重启设备后生效。')
                    logger.info(f"PC IP和网关IP设置成功: {new_ip}")
                    # 注意：ConfigManager更新将在保存参数成功后进行
                else:
                    InfoBar.error(
                        title='设置失败',
                        content='PC IP和网关IP设置失败，请检查通信',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    logger.warning("PC IP和网关IP设置失败")
        
        except Exception as e:
            logger.error(f"设置PC IP和网关IP地址错误: {e}")

    @asyncSlot()
    async def _set_device_ip(self):
        """设置设备IP地址"""
        try:
            new_ip = self.line_edit_device_ip.text().strip()
            if not validate_ip(new_ip):
                InfoBar.error(
                    title='IP地址格式错误',
                    content='请输入正确的IP地址格式',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
            
            # 获取当前IP用于确认对话框
            current_device_ip = self.label_device_ip.text()
            
            # 确认对话框
            title = "确认设置设备IP地址"
            content = f"设备IP地址将从 {current_device_ip} 设置为 {new_ip}\n\n确认后将立即发送设置命令！"

            confirmed = await async_confirm(title, content, self)
            if confirmed:
                # 转换IP为uint32
                ip_uint32 = ipv4_to_uint32(new_ip)
                target_addr = (self.cfg.target_host, self.cfg.target_port)
                
                # 设置设备IP
                success = await self.device_reg_set_func(1, [ip_uint32], target_addr=target_addr)
                
                if success:
                    InfoBar.success(
                        title='设置成功',
                        content=f'设备IP已设置为 {new_ip}',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    logger.info(f"设备IP地址设置成功: {new_ip}")
                else:
                    InfoBar.error(
                        title='设置失败',
                        content='设备IP地址设置失败，请检查通信',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    logger.warning("设备IP地址设置失败")
        
        except Exception as e:
            logger.error(f"设置设备IP地址错误: {e}")

    @asyncSlot()
    async def _set_netmask(self):
        """设置子网掩码"""
        try:
            new_netmask = self.line_edit_device_ip_mask.text().strip()
            if not validate_ip(new_netmask):
                InfoBar.error(
                    title='子网掩码格式错误',
                    content='请输入正确的子网掩码格式',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return

            # 获取当前子网掩码用于确认对话框
            current_netmask = self.label_device_ip_mask.text()

            # 确认对话框
            title = "确认设置子网掩码"
            content = f"子网掩码将从 {current_netmask} 设置为 {new_netmask}\n\n确认后将立即发送设置命令！"

            confirmed = await async_confirm(title, content, self)
            if confirmed:
                # 转换子网掩码为uint32
                netmask_uint32 = ipv4_to_uint32(new_netmask)
                target_addr = (self.cfg.target_host, self.cfg.target_port)

                # 设置子网掩码 (寄存器地址3)
                success = await self.device_reg_set_func(3, [netmask_uint32], target_addr=target_addr)

                if success:
                    InfoBar.success(
                        title='设置成功',
                        content=f'子网掩码已设置为 {new_netmask}',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    logger.info(f"子网掩码设置成功: {new_netmask}")
                    # 注意：ConfigManager更新将在保存参数成功后进行
                else:
                    InfoBar.error(
                        title='设置失败',
                        content='子网掩码设置失败，请检查通信',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    logger.warning("子网掩码设置失败")

        except Exception as e:
            logger.error(f"设置子网掩码错误: {e}")

    @asyncSlot()
    async def _set_device_name(self):
        """设置设备名称"""
        try:
            # 获取当前UID
            uid_text = self.label_device_uid.text()
            if uid_text.startswith("0x"):
                uid = int(uid_text, 16)
                device_name = self.line_edit_device_name.text().strip()
                current_name = self.label_device_name.text()

                if device_name and device_name != current_name:
                    # 确认对话框
                    title = "确认设置设备名称"
                    content = f"设备名称将从 '{current_name}' 设置为 '{device_name}'\n\n确认后将立即保存到配置文件！"

                    confirmed = await async_confirm(title, content, self)
                    if confirmed:
                        self.cfg.set_device_name(uid, device_name)
                        self.label_device_name.setText(device_name)

                        InfoBar.success(
                            title='设置成功',
                            content=f'设备名称已设置为 {device_name}',
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP,
                            duration=2000,
                            parent=self
                        )
                        logger.info(f"设备名称已更新: UID {uid_text} -> {device_name}")
                else:
                    InfoBar.warning(
                        title='无需设置',
                        content='设备名称未发生变化',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
        except Exception as e:
            logger.error(f"设置设备名称错误: {e}")
            InfoBar.error(
                title='设置失败',
                content='设备名称设置失败',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    @asyncSlot()
    async def _set_port_config(self):
        """设置端口配置（本机端口和设备端口绑定设置）"""
        try:
            pc_port = self.spinbox_pc_port.value()
            device_port = self.spinbox_device_port.value()

            # 获取当前端口用于确认对话框
            current_pc_port = self.label_pc_port.text()
            current_device_port = self.label_device_port.text()

            # 确认对话框
            title = "确认设置端口配置"
            content = f"本机端口将从 {current_pc_port} 设置为 {pc_port}\n设备端口将从 {current_device_port} 设置为 {device_port}\n\n确认后将立即发送设置命令！"

            confirmed = await async_confirm(title, content, self)
            if confirmed:
                # 按照下位机格式：高16位为设备端口，低16位为本机端口
                port_config = ((device_port & 0xFFFF) << 16) | (pc_port & 0xFFFF)
                target_addr = (self.cfg.target_host, self.cfg.target_port)

                # 设置端口配置 (寄存器地址6)
                success = await self.device_reg_set_func(6, [port_config], target_addr=target_addr)

                if success:
                    InfoBar.success(
                        title='设置成功',
                        content=f'端口配置已设置：本机端口 {pc_port}，设备端口 {device_port}',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    logger.info(f"端口配置设置成功: PC端口{pc_port}, 设备端口{device_port}")
                    # 注意：ConfigManager更新将在保存参数成功后进行
                else:
                    InfoBar.error(
                        title='设置失败',
                        content='端口配置设置失败，请检查通信',
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    logger.warning("端口配置设置失败")

        except Exception as e:
            logger.error(f"设置端口配置错误: {e}")

    @asyncSlot()
    async def save_param_cmd(self):
        """保存网络参数到Flash"""
        try:
            target_addr = (self.cfg.target_host, self.cfg.target_port)
            reg_addr = 105
            value = 0xA5
            # 发送设置指令
            success = await self.device_reg_set_func(
                reg_addr, [value], target_addr=target_addr
            )

            if success:
                InfoBar.success(
                    title='保存成功',
                    content='所有网络参数已成功写入设备 Flash',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                logger.info("网络参数保存成功")

                # 保存成功后更新ConfigManager中的网络参数
                self._update_config_after_save()
            else:
                InfoBar.error(
                    title='保存失败',
                    content='网络参数保存失败，请检查通信',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                logger.warning("网络参数保存失败")

        except Exception as e:
            logger.error(f"保存网络参数错误: {e}")

    def _update_config_after_save(self):
        """保存参数成功后更新ConfigManager中的网络参数"""
        try:
            # 获取当前显示的网络参数
            pc_ip = self.label_pc_ip.text()
            device_ip = self.label_device_ip.text()
            netmask = self.label_device_ip_mask.text()
            pc_port = self.label_pc_port.text()
            device_port = self.label_device_port.text()

            # 更新ConfigManager - 映射到原有的udp配置结构
            if pc_ip and validate_ip(pc_ip):
                self.cfg.set('udp.host', pc_ip)  # pc_ip -> host

            if device_ip and validate_ip(device_ip):
                self.cfg.set('udp.target_host', device_ip)  # device_ip -> target_host

            if netmask and validate_ip(netmask):
                self.cfg.set('udp.netmask', netmask)  # 新增netmask到udp下

            if pc_port.isdigit():
                self.cfg.set('udp.port', int(pc_port))  # pc_port -> port

            if device_port.isdigit():
                self.cfg.set('udp.target_port', int(device_port))  # device_port -> target_port

            # 保存配置文件
            self.cfg.save()
            logger.info("网络参数已更新到ConfigManager")

        except Exception as e:
            logger.error(f"更新ConfigManager失败: {e}")

    @asyncSlot()
    async def _confirm_save_param(self):
        """确认保存参数"""
        title = "确认保存网络参数"
        content = "即将把所有当前网络参数写入设备 Flash 永久保存，请确认是否继续？"

        confirmed = await async_confirm(title, content, self)
        if confirmed:
            await self.save_param_cmd()

    @asyncSlot(SysREGsUpData)
    async def on_on_sys_regs_uploaded(self, sys_regs_up_data: SysREGsUpData):
        """处理系统寄存器上传数据，解析网络参数"""
        try:
            # 解析网络参数
            if len(sys_regs_up_data.reg) > 6:
                # UID (寄存器0)
                uid = sys_regs_up_data.reg[0]
                uid_str = f"0x{uid:08X}"
                self.label_device_uid.setText(uid_str)

                # 获取设备名称
                device_name = self.cfg.get_device_name(uid)
                self.label_device_name.setText(device_name)

                # 设备IP (寄存器1)
                device_ip = uint32_to_ipv4(sys_regs_up_data.reg[1])
                self.label_device_ip.setText(device_ip)

                # 网关IP (寄存器2)
                # gateway_ip = uint32_to_ipv4(sys_regs_up_data.reg[2])

                # 子网掩码 (寄存器3)
                netmask = uint32_to_ipv4(sys_regs_up_data.reg[3])
                self.label_device_ip_mask.setText(netmask)

                # MAC地址低4字节 (寄存器4)
                mac_low = sys_regs_up_data.reg[4]
                mac_str = uint32_to_mac(mac_low)
                self.label_device_mac_addr.setText(mac_str)

                # PC IP (寄存器5)
                pc_ip = uint32_to_ipv4(sys_regs_up_data.reg[5])
                self.label_pc_ip.setText(pc_ip)

                # 端口配置 (寄存器6)
                port_config = sys_regs_up_data.reg[6]
                device_port = (port_config >> 16) & 0xFFFF
                pc_port = port_config & 0xFFFF

                self.label_pc_port.setText(str(pc_port))
                self.label_device_port.setText(str(device_port))

                # logger.info(f"网络参数已更新: UID={uid_str}, PC_IP={pc_ip}, Device_IP={device_ip}, PC_Port={pc_port}, Device_Port={device_port}")

                # 发射设备信息更新信号给主窗口
                self.device_info_updated.emit(device_name, uid_str, device_ip, pc_port, device_port)

        except Exception as e:
            logger.error(f"处理网络参数数据错误: {e}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            logger.info("NetworkSettingFrom开始关闭")
            logger.info("NetworkSettingFrom正常退出")
            event.accept()

        except Exception as e:
            logger.error(f"关闭NetworkSettingFrom时出错: {e}")
            event.accept()
