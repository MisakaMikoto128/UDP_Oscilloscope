#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDP接收诊断工具
用于排查UDP接收问题
"""

import asyncio
import logging
import socket
import sys
import time

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class MinimalUDPReceiver:
    """最简单的UDP接收器，不依赖任何其他模块"""
    
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.transport = None
        self.protocol = None
        self.packet_count = 0
        
    async def start(self):
        """启动接收器"""
        logger.info(f"启动最简UDP接收器，监听 {self.host}:{self.port}")
        
        loop = asyncio.get_event_loop()
        try:
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: SimpleUDPProtocol(self.on_packet_received),
                local_addr=(self.host, self.port),
                family=socket.AF_INET  # 强制IPv4
            )
            
            # 获取实际绑定的地址
            sockname = self.transport.get_extra_info('sockname')
            logger.info(f"UDP接收器已启动，实际绑定地址: {sockname}")
            
            # 获取socket信息
            sock = self.transport.get_extra_info('socket')
            logger.info(f"Socket详细信息: family={sock.family}, type={sock.type}, proto={sock.proto}")
            
        except Exception as e:
            logger.error(f"启动失败: {e}")
            raise
    
    def on_packet_received(self, data: bytes, addr: tuple):
        """收到数据包的回调"""
        self.packet_count += 1
        logger.info(f"*** 收到第 {self.packet_count} 个数据包 ***")
        logger.info(f"来源地址: {addr}")
        logger.info(f"数据长度: {len(data)} bytes")
        logger.info(f"数据内容(hex): {data.hex()}")
        logger.info(f"数据内容(前100字节): {data[:100]}")
        print("=" * 60)
    
    async def stop(self):
        """停止接收器"""
        if self.transport:
            self.transport.close()
        logger.info(f"UDP接收器已停止，总共收到 {self.packet_count} 个数据包")

class SimpleUDPProtocol(asyncio.DatagramProtocol):
    """简单的UDP协议处理器"""
    
    def __init__(self, callback):
        self.callback = callback
    
    def connection_made(self, transport):
        logger.info("UDP连接已建立")
        self.transport = transport
    
    def datagram_received(self, data, addr):
        logger.debug(f"协议层收到数据: {len(data)} bytes from {addr}")
        if self.callback:
            self.callback(data, addr)
    
    def error_received(self, exc):
        logger.error(f"UDP错误: {exc}")
    
    def connection_lost(self, exc):
        if exc:
            logger.error(f"连接丢失: {exc}")
        else:
            logger.info("连接正常关闭")

def check_port_availability(host, port):
    """检查端口是否可用"""
    logger.info(f"检查端口 {host}:{port} 是否可用...")
    
    try:
        # 尝试绑定端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        
        # 获取实际绑定的地址
        actual_addr = sock.getsockname()
        logger.info(f"端口可用，实际绑定地址: {actual_addr}")
        
        sock.close()
        return True
        
    except OSError as e:
        logger.error(f"端口不可用: {e}")
        return False

def send_test_packet(target_host, target_port):
    """发送测试数据包"""
    logger.info(f"发送测试数据包到 {target_host}:{target_port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_data = b"Hello UDP Test " + str(int(time.time())).encode()
        sock.sendto(test_data, (target_host, target_port))
        sock.close()
        logger.info(f"测试数据包已发送: {test_data}")
        return True
    except Exception as e:
        logger.error(f"发送测试数据包失败: {e}")
        return False

async def run_diagnostic(host='localhost', port=8888):
    """运行诊断"""
    
    print("=" * 60)
    print("UDP接收诊断工具")
    print("=" * 60)
    
    # 1. 检查端口可用性
    if not check_port_availability(host, port):
        print("端口检查失败，退出诊断")
        return
    
    # 2. 创建最简接收器
    receiver = MinimalUDPReceiver(host, port)
    
    try:
        # 3. 启动接收器
        await receiver.start()
        
        # 4. 发送测试数据包
        logger.info("等待2秒，然后发送测试数据包...")
        await asyncio.sleep(2)
        
        send_test_packet(host, port)
        
        # 5. 等待数据
        logger.info("等待接收数据（20秒）...")
        logger.info("请在另一个工具中发送数据到此端口进行测试")
        
        await asyncio.sleep(20)
        
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"诊断过程中出错: {e}")
    finally:
        await receiver.stop()

if __name__ == "__main__":
    # 可以通过命令行参数指定地址和端口
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8888
    
    print(f"开始诊断 {host}:{port}")
    asyncio.run(run_diagnostic(host, port))