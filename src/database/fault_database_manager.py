# -*- coding: utf-8 -*-
import sqlite3
import logging
import struct
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class FaultDatabaseManager:
    """故障数据库管理器"""
    
    def __init__(self, db_path: str = "fault_history.db"):
        """
        初始化故障数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建故障记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS fault_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_uid INTEGER NOT NULL,
                        timestamp_ms INTEGER NOT NULL,
                        error_code_u32 INTEGER NOT NULL,
                        flag1_uint32 INTEGER NOT NULL,
                        registers_blob BLOB NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(device_uid, timestamp_ms, error_code_u32, flag1_uint32)
                    )
                ''')
                
                # 创建索引以提高查询性能
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_device_timestamp 
                    ON fault_records(device_uid, timestamp_ms)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON fault_records(timestamp_ms)
                ''')
                
                conn.commit()
                logger.info("故障数据库初始化完成")
                
        except Exception as e:
            logger.error(f"初始化故障数据库失败: {e}")
            raise
    
    def insert_fault_record(self, device_uid: int, timestamp_ms: int,
                          error_code_u32: int, flag1_uint32: int,
                          registers: List[int]) -> bool:
        """
        插入故障记录

        Args:
            device_uid: 设备UID
            timestamp_ms: 时间戳（毫秒）
            error_code_u32: 错误代码
            flag1_uint32: 故障标志
            registers: 寄存器数组

        Returns:
            bool: 插入是否成功
        """
        try:
            # 将寄存器数组转换为二进制数据（每个uint32占4字节）
            # 确保所有值都在uint32范围内
            safe_registers = []
            for reg in registers:
                if reg < 0:
                    # 负数转换为无符号32位表示
                    safe_registers.append(reg & 0xFFFFFFFF)
                elif reg > 0xFFFFFFFF:
                    # 超出范围的值截断
                    safe_registers.append(reg & 0xFFFFFFFF)
                else:
                    safe_registers.append(reg)

            registers_blob = struct.pack(f'<{len(safe_registers)}I', *safe_registers)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT OR IGNORE INTO fault_records
                    (device_uid, timestamp_ms, error_code_u32, flag1_uint32, registers_blob)
                    VALUES (?, ?, ?, ?, ?)
                ''', (device_uid, timestamp_ms, error_code_u32, flag1_uint32, registers_blob))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"插入故障记录成功: 设备{device_uid:08X}, 时间戳{timestamp_ms}")
                    return True
                else:
                    logger.debug(f"故障记录已存在，跳过插入: 设备{device_uid:08X}, 时间戳{timestamp_ms}")
                    return False
                    
        except Exception as e:
            logger.error(f"插入故障记录失败: {e}")
            return False
    
    def query_fault_records(self, device_uid: Optional[int] = None, 
                          start_date: Optional[date] = None,
                          end_date: Optional[date] = None,
                          limit: int = 1000) -> List[Dict]:
        """
        查询故障记录
        
        Args:
            device_uid: 设备UID，None表示查询所有设备
            start_date: 开始日期
            end_date: 结束日期
            limit: 最大返回记录数
            
        Returns:
            List[Dict]: 故障记录列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                conditions = []
                params = []
                
                if device_uid is not None:
                    conditions.append("device_uid = ?")
                    params.append(device_uid)
                
                if start_date is not None:
                    start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
                    conditions.append("timestamp_ms >= ?")
                    params.append(start_timestamp)
                
                if end_date is not None:
                    end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)
                    conditions.append("timestamp_ms <= ?")
                    params.append(end_timestamp)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                query = f'''
                    SELECT id, device_uid, timestamp_ms, error_code_u32, flag1_uint32,
                           registers_blob, created_at
                    FROM fault_records
                    WHERE {where_clause}
                    ORDER BY timestamp_ms DESC
                    LIMIT ?
                '''
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                # 转换为字典列表
                records = []
                for row in rows:
                    # 解析二进制寄存器数据
                    registers_blob = row[5]
                    registers_count = len(registers_blob) // 4  # 每个uint32占4字节
                    registers = list(struct.unpack(f'<{registers_count}I', registers_blob))

                    record = {
                        'id': row[0],
                        'device_uid': row[1],
                        'timestamp_ms': row[2],
                        'error_code_u32': row[3],
                        'flag1_uint32': row[4],
                        'registers': registers,
                        'created_at': row[6]
                    }
                    records.append(record)
                
                logger.info(f"查询到{len(records)}条故障记录")
                return records
                
        except Exception as e:
            logger.error(f"查询故障记录失败: {e}")
            return []
    
    def get_device_uids(self) -> List[int]:
        """
        获取数据库中所有设备的UID列表
        
        Returns:
            List[int]: 设备UID列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT DISTINCT device_uid 
                    FROM fault_records 
                    ORDER BY device_uid
                ''')
                
                rows = cursor.fetchall()
                uids = [row[0] for row in rows]
                
                logger.info(f"数据库中共有{len(uids)}个设备")
                return uids
                
        except Exception as e:
            logger.error(f"获取设备UID列表失败: {e}")
            return []
    
    def get_fault_dates(self, device_uid: Optional[int] = None) -> List[date]:
        """
        获取有故障记录的日期列表
        
        Args:
            device_uid: 设备UID，None表示查询所有设备
            
        Returns:
            List[date]: 有故障记录的日期列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if device_uid is not None:
                    cursor.execute('''
                        SELECT DISTINCT DATE(timestamp_ms / 1000, 'unixepoch', 'localtime') as fault_date
                        FROM fault_records 
                        WHERE device_uid = ?
                        ORDER BY fault_date
                    ''', (device_uid,))
                else:
                    cursor.execute('''
                        SELECT DISTINCT DATE(timestamp_ms / 1000, 'unixepoch', 'localtime') as fault_date
                        FROM fault_records 
                        ORDER BY fault_date
                    ''')
                
                rows = cursor.fetchall()
                dates = []
                for row in rows:
                    try:
                        fault_date = datetime.strptime(row[0], '%Y-%m-%d').date()
                        dates.append(fault_date)
                    except ValueError:
                        continue
                
                logger.info(f"找到{len(dates)}个有故障记录的日期")
                return dates
                
        except Exception as e:
            logger.error(f"获取故障日期列表失败: {e}")
            return []
    
    def has_fault_on_date(self, target_date: date, device_uid: Optional[int] = None) -> bool:
        """
        检查指定日期是否有故障记录
        
        Args:
            target_date: 目标日期
            device_uid: 设备UID，None表示查询所有设备
            
        Returns:
            bool: 是否有故障记录
        """
        try:
            start_timestamp = int(datetime.combine(target_date, datetime.min.time()).timestamp() * 1000)
            end_timestamp = int(datetime.combine(target_date, datetime.max.time()).timestamp() * 1000)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if device_uid is not None:
                    cursor.execute('''
                        SELECT COUNT(*) FROM fault_records 
                        WHERE device_uid = ? AND timestamp_ms >= ? AND timestamp_ms <= ?
                    ''', (device_uid, start_timestamp, end_timestamp))
                else:
                    cursor.execute('''
                        SELECT COUNT(*) FROM fault_records 
                        WHERE timestamp_ms >= ? AND timestamp_ms <= ?
                    ''', (start_timestamp, end_timestamp))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"检查故障日期失败: {e}")
            return False
    
    def clear_old_records(self, days_to_keep: int = 30) -> int:
        """
        清理旧的故障记录
        
        Args:
            days_to_keep: 保留的天数
            
        Returns:
            int: 删除的记录数
        """
        try:
            cutoff_timestamp = int((datetime.now().timestamp() - days_to_keep * 24 * 3600) * 1000)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM fault_records 
                    WHERE timestamp_ms < ?
                ''', (cutoff_timestamp,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"清理了{deleted_count}条旧故障记录")
                return deleted_count

        except Exception as e:
            logger.error(f"清理旧故障记录失败: {e}")
            return 0

    def insert_test_data(self) -> int:
        """
        插入测试数据

        Returns:
            int: 插入的记录数
        """
        try:
            import random
            from datetime import timedelta

            test_uid = 0xAABBCCDD
            base_time = datetime.now()
            inserted_count = 0

            # 生成10条测试记录
            for i in range(10):
                # 随机时间（过去7天内）
                random_hours = random.randint(0, 7 * 24)
                timestamp = base_time - timedelta(hours=random_hours)
                timestamp_ms = int(timestamp.timestamp() * 1000)

                # 随机故障状态
                has_fault = random.choice([True, False, False])  # 1/3概率有故障

                if has_fault:
                    error_code_u32 = random.choice([0x02010D00, 0x01020000, 0x000102F0])
                    flag1_uint32 = random.choice([0xF00F001, 0x1000F01, 0x2000F02])
                else:
                    error_code_u32 = 0x00000000
                    flag1_uint32 = 0x00000000

                # 生成模拟寄存器数据
                registers = [0] * 107

                # 设置一些有意义的测试数据（确保在uint32范围内）
                registers[55] = 0x50453A08   # 温度数据
                registers[63] = error_code_u32  # 错误代码
                registers[90] = flag1_uint32    # 故障标志

                # 转换有符号数为uint32表示
                def to_uint32(value):
                    if value < 0:
                        return (value + 2**32) & 0xFFFFFFFF
                    return value & 0xFFFFFFFF

                registers[83] = to_uint32(random.randint(-50000, 50000))  # 转速
                registers[62] = random.randint(0, 36000)       # 角度
                registers[76] = to_uint32(random.randint(30000, 50000))   # Vbus
                registers[77] = to_uint32(random.randint(30000, 50000))   # Vbus_in
                registers[56] = to_uint32(random.randint(-10000, 10000))  # Id
                registers[32] = to_uint32(random.randint(-10000, 10000))  # Iq
                registers[60] = to_uint32(random.randint(-10000, 10000))  # Ud
                registers[61] = to_uint32(random.randint(-10000, 10000))  # Uq
                registers[73] = to_uint32(random.randint(-5000, 5000))    # Ia
                registers[74] = to_uint32(random.randint(-5000, 5000))    # Ib
                registers[75] = to_uint32(random.randint(-5000, 5000))    # Ic
                registers[79] = to_uint32(random.randint(-5000, 5000))    # Ibus
                registers[64] = to_uint32(random.randint(0, 10000))       # mDuty
                registers[65] = to_uint32(random.randint(2000, 8000))     # mPT1
                registers[66] = to_uint32(random.randint(2000, 8000))     # mPT2
                registers[67] = to_uint32(random.randint(2000, 8000))     # mPT3
                registers[68] = to_uint32(random.randint(2000, 8000))     # mPT4
                registers[69] = to_uint32(random.randint(2000, 8000))     # mPT5
                registers[85] = random.randint(0, 7)           # 系统模式

                # 插入记录
                success = self.insert_fault_record(
                    device_uid=test_uid,
                    timestamp_ms=timestamp_ms,
                    error_code_u32=error_code_u32,
                    flag1_uint32=flag1_uint32,
                    registers=registers
                )

                if success:
                    inserted_count += 1

            logger.info(f"插入了{inserted_count}条测试数据")
            return inserted_count

        except Exception as e:
            logger.error(f"插入测试数据失败: {e}")
            return 0
