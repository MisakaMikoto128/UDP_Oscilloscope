# -*- coding: utf-8 -*-
"""
UDP接收器模块
实现异步UDP数据接收和处理
"""

import asyncio
import logging
import time
import socket
import threading
import struct
import queue
from utils.crc import calculate_crc
from typing import Optional, List, Tuple, Dict, Any
from typing import Callable, Optional, Any
from collections import deque
from PyQt5.QtCore import QObject, pyqtSignal
from communication.protocol import (
    ProtocolParser,
    MotorSampleData,
    SysREGsUpData,
    SysREGsSetResp,
)
from communication.protocol import *

logger = logging.getLogger(__name__)


class UDPReceiver(QObject):
    """UDP数据接收器 - 15KHz高频优化版本"""

    # 在线/离线状态信号
    online_status_changed = pyqtSignal(bool)  # True=在线, False=离线

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8888,
        on_sample: Optional[Callable[[int, list], None]] = None,
        on_sys_regs_upload: Optional[Callable[[SysREGsUpData], None]] = None,
    ):
        """
        初始化UDP接收器

        Args:
            host: 监听地址
            port: 监听端口
            on_sample: 采样数据回调函数 (packet_type, channels)
            on_config: 配置数据回调函数 (config_dict)
        """
        super().__init__()
        self.host = host
        self.port = port
        self.on_sample = on_sample
        self.on_sys_regs_upload = on_sys_regs_upload

        self.parser = ProtocolParser()
        self.transport = None  # 保持兼容性，实际不使用
        self.protocol = None  # 保持兼容性，实际不使用
        self.running = False

        # 高性能接收配置
        self.socket = None
        self.receive_thread = None
        self.process_thread = None

        # 高速数据队列 - 使用线程安全的deque
        self.data_queue = deque(maxlen=5000)  # 15KHz下约333ms缓冲
        self.queue_lock = threading.Lock()

        # 在线状态检测
        self.online_status = False
        self.last_data_time = 0
        self.online_timeout = 1.0  # 1秒超时
        self.status_check_thread = None

        # 统计信息
        self.receive_count = 0
        self.process_count = 0
        self.drop_count = 0
        self.last_report_time = time.time()

        # 发送socket
        self.send_socket = None
        self.req_seq = 0
        self.resp_queue = queue.Queue(maxsize=1)

    async def start(self):
        """启动UDP接收器"""
        if self.running:
            return

        try:
            # 创建高性能UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Windows下的socket优化
            self.socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, 100 * 1024 * 1024
            )  # 100MB
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 绑定地址
            self.socket.bind((self.host, self.port))

            # 获取实际缓冲区大小
            actual_rcvbuf = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)

            # 创建发送socket
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.send_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024
            )

            # 获取实际绑定地址
            sockname = self.socket.getsockname()
            logger.info(f"UDP接收器已启动，实际绑定地址: {sockname}")
            logger.info(
                f"Socket详细信息: AF_INET, type={self.socket.type}, proto={self.socket.proto}"
            )
            logger.info(f"实际接收缓冲区大小: {actual_rcvbuf} 字节")

            self.running = True

            # 启动专用高速接收线程
            self.receive_thread = threading.Thread(
                target=self._high_speed_receive_loop,
                name="UDP_Receiver_15KHz",
                daemon=True,
            )
            self.receive_thread.start()

            # 启动数据处理线程
            self.process_thread = threading.Thread(
                target=self._process_loop, name="UDP_Processor", daemon=True
            )
            self.process_thread.start()

            # 启动在线状态检测线程
            self.status_check_thread = threading.Thread(
                target=self._status_check_loop, name="UDP_Status_Checker", daemon=True
            )
            self.status_check_thread.start()

            logger.info(
                f"UDP接收器已启动，监听 {self.host}:{self.port} (高频15KHz优化)"
            )

        except Exception as e:
            logger.error(f"启动UDP接收器失败: {e}")
            raise

    async def stop(self):
        """停止UDP接收器"""
        if not self.running:
            return

        self.running = False

        # 等待线程结束
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1.0)

        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=1.0)

        # 关闭socket
        if self.socket:
            self.socket.close()
            self.socket = None

        if self.send_socket:
            self.send_socket.close()
            self.send_socket = None

        logger.info("UDP接收器已停止")

    def _high_speed_receive_loop(self):
        """专用高速接收循环 - 15KHz优化"""
        self.socket.settimeout(0.01)  # 10ms超时，快速检查running状态

        logger.info("高速UDP接收线程已启动")

        while self.running:
            try:
                # 批量接收优化 - 关键性能点
                batch_count = 0
                batch_start = time.perf_counter()

                # 在10ms内尽可能多接收数据包
                while batch_count < 500 and (time.perf_counter() - batch_start) < 0.01:
                    try:
                        data, addr = self.socket.recvfrom(65536)  # 最大UDP包大小

                        # 快速入队 - 避免锁争用
                        if len(self.data_queue) < self.data_queue.maxlen:
                            self.data_queue.append((data, addr))
                        else:
                            # 队列满，丢弃数据
                            self.drop_count += 1

                        self.receive_count += 1
                        batch_count += 1

                    except socket.timeout:
                        # 超时正常，继续下一批
                        break
                    except OSError as e:
                        if self.running:
                            logger.error(f"socket接收错误: {e}")
                        break

            except Exception as e:
                if self.running:
                    logger.error(f"接收循环出错: {e}")
                    time.sleep(0.01)

        logger.info("高速UDP接收线程已退出")

    def _status_check_loop(self):
        """在线状态检测循环"""
        logger.info("在线状态检测线程已启动")

        while self.running:
            try:
                current_time = time.time()

                # 检查是否超时
                if self.last_data_time > 0:
                    time_since_last_data = current_time - self.last_data_time
                    should_be_online = time_since_last_data <= self.online_timeout

                    # 状态发生变化时发射信号
                    if should_be_online != self.online_status:
                        self.online_status = should_be_online
                        self.online_status_changed.emit(self.online_status)
                        if self.online_status:
                            logger.info("设备上线")
                        else:
                            logger.info("设备离线")

                # 每0.1秒检查一次
                time.sleep(0.1)

            except Exception as e:
                if self.running:
                    logger.error(f"状态检测循环出错: {e}")
                    time.sleep(0.1)

        logger.info("在线状态检测线程已退出")

    def _process_loop(self):
        """数据处理循环 - 批量处理优化"""
        logger.info("UDP数据处理线程已启动")

        while self.running:
            try:
                # 批量处理数据
                batch_size = min(200, len(self.data_queue))

                if batch_size == 0:
                    time.sleep(0.001)  # 1ms等待
                    continue

                # 批量取出数据进行处理
                batch_data = []
                for _ in range(batch_size):
                    if self.data_queue:
                        batch_data.append(self.data_queue.popleft())

                # 批量处理
                for data, addr in batch_data:
                    self._on_data_received(data, addr)
                    self.process_count += 1

                # 性能报告
                self._report_performance()

                # 根据队列情况调整处理频率
                queue_size = len(self.data_queue)
                if queue_size > 1000:
                    # 队列积压严重，继续处理
                    continue
                elif queue_size > 200:
                    time.sleep(0.0001)  # 0.1ms
                else:
                    time.sleep(0.001)  # 1ms

            except Exception as e:
                if self.running:
                    logger.error(f"数据处理循环出错: {e}")
                    time.sleep(0.01)

        logger.info("UDP数据处理线程已退出")

    def _report_performance(self):
        """性能统计报告"""
        now = time.time()
        if now - self.last_report_time >= 2.0:  # 每2秒报告一次
            elapsed = now - self.last_report_time
            receive_rate = self.receive_count / elapsed
            process_rate = self.process_count / elapsed
            drop_rate = self.drop_count / elapsed if self.drop_count > 0 else 0
            queue_size = len(self.data_queue)

            # logger.info(
            #     f"UDP高频统计 - 接收:{receive_rate:.0f}/s, 处理:{process_rate:.0f}/s, "
            #     f"丢弃:{drop_rate:.0f}/s, 队列:{queue_size}/{self.data_queue.maxlen}"
            # )

            # 重置计数器
            self.receive_count = 0
            self.process_count = 0
            self.drop_count = 0
            self.last_report_time = now

    def _on_data_received(self, data: bytes, addr: tuple):
        """处理接收到的UDP数据"""
        try:
            # 更新最后数据接收时间
            self.last_data_time = time.time()

            packets = self.parser.feed_data(data)

            for packet in packets:
                # 处理电机采样数据
                if (
                    packet.packet_type == PACKET_TYPE_MOTOR_U16
                    or packet.packet_type == PACKET_TYPE_MOTOR_F32
                ):
                    self._handle_motor_data(packet)
                # 处理寄存器上传数据
                elif packet.packet_type == PACKET_TYPE_SYS_REGS_UP:
                    self._handle_sys_regs_upload_data(packet)
                elif packet.packet_type == PACKET_TYPE_SYS_REGS_SET:
                    self._handle_sys_regs_set_resp(packet)
        except Exception as e:
            logger.error(f"处理UDP数据时出错: {e}")

    def _handle_motor_data(self, motor_data: MotorSampleData):
        """处理电机采样数据"""
        if self.on_sample:
            try:
                # 将packet_type转换为格式标识: 0xA1->0, 0xA2->1
                self.on_sample(motor_data.packet_type, motor_data.channels)
            except Exception as e:
                logger.error(f"处理电机采样数据回调时出错: {e}")

    def _handle_sys_regs_upload_data(self, sys_regs_up_data: SysREGsUpData):
        """处理配置数据"""
        if self.on_sys_regs_upload:
            try:
                self.on_sys_regs_upload(sys_regs_up_data)
            except Exception as e:
                logger.error(f"处理配置数据回调时出错: {e}")

    def _handle_sys_regs_set_resp(self, sys_regs_set_resp: SysREGsSetResp):
        """处理寄存器设置响应数据"""
        try:
            # 使用线程安全的queue
            self.resp_queue.put_nowait(sys_regs_set_resp)
        except Exception as e:
            logger.error(f"处理响应失败: {e}")
   
    def get_statistics(self) -> dict:
        """获取接收统计信息"""
        parser_stats = self.parser.get_statistics()
        parser_stats.update(
            {
                "queue_size": len(self.data_queue),
                "queue_max_size": self.data_queue.maxlen,
                "is_running": self.running,
                "receive_thread_alive": self.receive_thread.is_alive()
                if self.receive_thread
                else False,
                "process_thread_alive": self.process_thread.is_alive()
                if self.process_thread
                else False,
            }
        )
        return parser_stats

    def reset_statistics(self):
        """重置统计信息"""
        self.parser.reset_statistics()
        self.receive_count = 0
        self.process_count = 0
        self.drop_count = 0

    async def _send_packet(self, packet_data: bytes, target_addr: tuple) -> None:
        """异步发送数据包"""
        loop = asyncio.get_running_loop()
        try:
            # 使用线程池执行同步的socket操作
            await loop.run_in_executor(
                None, self.send_socket.sendto, packet_data, target_addr
            )
            logger.debug(
                f"配置数据包已发送到 {target_addr}, 大小: {len(packet_data)} 字节"
            )
        except Exception as e:
            raise ConnectionError(f"发送数据包失败: {e}")

    def _build_reg_set_packet(
        self, regAddrStart: int, regNum: int, datas: list[int], req_seq: int
    ) -> bytes:
        """构造配置数据包"""
        sub_packet = struct.pack(
            f"<BHH{regNum}I", PACKET_TYPE_SYS_REGS_SET, regAddrStart, regNum, *datas
        )

        # 主数据包：包头 + 剩余长度 + 序号 + 子数据包 + CRC
        remaining_length = len(sub_packet) + 2  # 子数据包 + CRC
        crc = calculate_crc(sub_packet)
        header_data = struct.pack("<HHH", 0x55AA, remaining_length, req_seq)

        return header_data + sub_packet + struct.pack("<H", crc)

    async def _wait_for_response(self, timeout: float) -> "SysREGsSetResp":
        """等待配置响应"""
        loop = asyncio.get_running_loop()
        try:
            # 在线程池中执行阻塞的get操作
            resp = await loop.run_in_executor(None, self.resp_queue.get, True, timeout)
            return resp
        except queue.Empty:
            raise asyncio.TimeoutError("等待响应超时")

    async def reg_set(
        self, 
        regAddrStart: int, datas: list[int], timeout: float = 1.0,
        target_addr: tuple = ("192.168.1.100", 8889)
    ) -> bool:
        """
        发送配置数据到下位机

        Args:
            regAddrStart: 起始寄存器地址
            datas: 配置数据列表
            timeout: 响应超时时间(秒)

        Returns:
            bool: 配置是否成功

        Raises:
            ConfigurationError: 配置参数错误
            TimeoutError: 等待响应超时
            ConnectionError: 网络连接错误
        """
        # 参数验证
        if not self.running or not self.send_socket:
            return False

        if not datas:
            return False

        if regAddrStart < 0:
            return False

        # 限制寄存器数量
        if len(datas) > 20:
            logger.warning(f"数据长度超过限制，截取前20个: {len(datas)} -> 20")
            datas = datas[:20]

        regNum = len(datas)
        req_seq = (self.req_seq + 1) & 0xFFFF
        self.req_seq = req_seq

        try:
            # 构造数据包
            packet_data = self._build_reg_set_packet(
                regAddrStart, regNum, datas, req_seq
            )

            # 发送数据包
            await self._send_packet(packet_data, target_addr)

            # 等待响应
            resp = await self._wait_for_response(timeout)

            if (
                resp.packet_type == PACKET_TYPE_SYS_REGS_SET
                and resp.reg_addr_start == regAddrStart
            ):  # 响应类型和序号和地址都匹配时认为成功完成配置
                logger.info(f"配置成功完成，响应: {resp}")
                return True
            else:
                logger.warning(
                    f"响应类型错误，期望 {PACKET_TYPE_SYS_REGS_SET}，实际 {resp.packet_type}"
                )
                return False  # 响应类型错误，丢弃响应并返回失败

        except asyncio.TimeoutError:
            logger.warning(f"等待配置响应超时 (序号: {req_seq})")
            # 清空队列中可能的旧响应
            try:
                self.resp_queue.get_nowait()
            except queue.Empty:
                pass
        except OSError as e:
            logger.error(f"网络发送失败: {e}")
            raise ConnectionError(f"网络连接错误: {e}")
        except Exception as e:
            logger.error(f"发送配置数据失败: {e}")
            raise
