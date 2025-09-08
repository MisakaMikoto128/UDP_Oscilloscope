# -*- coding: utf-8 -*-
"""
网络工具函数模块
"""
import socket
import struct
import re


def uint32_to_ipv4(value: int) -> str:
    """将32位无符号整数转换为IPv4地址字符串"""
    return socket.inet_ntoa(struct.pack('!I', value))


def ipv4_to_uint32(ip_str: str) -> int:
    """将IPv4地址字符串转换为32位无符号整数"""
    return struct.unpack('!I', socket.inet_aton(ip_str))[0]


def uint32_to_mac(value: int) -> str:
    """将32位无符号整数转换为MAC地址字符串（低4字节）"""
    return f"00:08:{(value >> 24) & 0xFF:02X}:{(value >> 16) & 0xFF:02X}:{(value >> 8) & 0xFF:02X}:{value & 0xFF:02X}"


def validate_ip(ip_str: str) -> bool:
    """验证IP地址格式"""
    if not ip_str:
        return False
    
    # 使用正则表达式验证IP地址格式
    pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(pattern, ip_str)
    
    if not match:
        return False
    
    # 检查每个数字是否在0-255范围内
    for group in match.groups():
        if int(group) > 255:
            return False
    
    return True


def validate_port(port_str: str) -> bool:
    """验证端口号格式"""
    if not port_str or not port_str.isdigit():
        return False
    
    port = int(port_str)
    return 1 <= port <= 65535


def format_device_info(device_name: str, uid: str, device_ip: str, pc_port: int, device_port: int) -> str:
    """格式化设备信息字符串"""
    return f"{device_name} ({uid}) | 设备IP: {device_ip} | PC端口: {pc_port} | 设备端口: {device_port}"
