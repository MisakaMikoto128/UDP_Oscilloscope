# -*- coding: utf-8 -*-
"""
CRC校验工具模块
使用CRC-Modbus算法进行数据校验
"""

import crcmod
from functools import reduce

# CRC-Modbus算法配置
# 多项式: 0x8005, 初始值: 0xFFFF, 反向输入: True, 反向输出: True
crc16_modbus = crcmod.mkCrcFun(0x18005, initCrc=0xFFFF, rev=True, xorOut=0x0000)

def calculate_crc(data: bytes) -> int:
    """
    计算CRC-Modbus校验值
    
    Args:
        data: 需要校验的字节数据
        
    Returns:
        CRC校验值 (16位整数)
    """
    return crc16_modbus(data)


def verify_crc(data: bytes, expected_crc: int) -> bool:
    """
    验证CRC校验值
    
    Args:
        data: 需要校验的字节数据
        expected_crc: 期望的CRC值
        
    Returns:
        校验是否通过
    """
    calculated_crc = calculate_crc(data)
    return calculated_crc == expected_crc

def insert_zeros(data: bytes) -> bytes:
    """
    在每个字节之间插入一个 0x00。
    :param data: 原始数据
    :return: 插入 0x00 后的数据
    """
    # 将每个字节和 0x00 组合成一个元组
    pairs = zip(data, [0] * len(data))
    # 将元组中的字节和 0x00 拼接成一个新的字节序列
    result = reduce(lambda x, y: x + bytes([y[0]]) + bytes([y[1]]), pairs, b'')
    return result

def extract_and_verify_crc(data: bytes) -> tuple[bytes, bool]:
    """
    提取并验证数据末尾的CRC校验值
    
    Args:
        data: 包含CRC的完整数据
        
    Returns:
        (原始数据, 校验是否通过)
    """
    if len(data) < 2:
        return data, False
    
    is_valid = False

    # 提取原始数据和CRC
    original_data = data[:-2]
    crc_bytes = data[-2:]
    expected_crc = int.from_bytes(crc_bytes, byteorder='little')
    
    # 验证CRC
    is_valid = verify_crc(original_data, expected_crc)
    return original_data, is_valid
