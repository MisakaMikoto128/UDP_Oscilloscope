#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的UDP发送测试工具
用于测试您正在运行的UDP接收器
"""

import socket
import time
import sys

def send_udp_packets(target_host='127.0.0.1', target_port=8888, count=5):
    """发送UDP测试数据包"""
    
    print(f"向 {target_host}:{target_port} 发送 {count} 个测试数据包...")
    
    try:
        # 创建IPv4 UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        for i in range(count):
            # 发送简单的测试消息
            message = f"Test packet #{i+1} at {int(time.time())}"
            data = message.encode('utf-8')
            
            print(f"发送: {message}")
            sock.sendto(data, (target_host, target_port))
            
            time.sleep(1)
        
        sock.close()
        print("发送完成")
        
    except Exception as e:
        print(f"发送失败: {e}")

def send_hex_packet(target_host='127.0.0.1', target_port=8888):
    """发送十六进制格式的测试数据包"""
    
    # 模拟一个可能的协议数据包格式
    hex_data = "55AA0010000112345678ABCDEF"  # 示例数据
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data = bytes.fromhex(hex_data)
        
        print(f"发送十六进制数据到 {target_host}:{target_port}")
        print(f"数据: {hex_data}")
        print(f"字节: {data}")
        
        sock.sendto(data, (target_host, target_port))
        sock.close()
        
        print("十六进制数据包发送完成")
        
    except Exception as e:
        print(f"发送失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        host = sys.argv[1]
    else:
        host = '127.0.0.1'
    
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    else:
        port = 8888
    
    print("=" * 50)
    print("UDP发送测试工具")
    print("=" * 50)
    
    print(f"\n1. 发送文本数据包到 {host}:{port}")
    send_udp_packets(host, port, 3)
    
    print(f"\n2. 发送十六进制数据包到 {host}:{port}")
    send_hex_packet(host, port)
    
    print("\n测试完成")
    print("请检查您的UDP接收器是否收到了数据")