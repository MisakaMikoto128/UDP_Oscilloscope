# -*- coding: utf-8 -*-
import sqlite3
import zlib
import logging
import struct
from datetime import datetime, date
from typing import List, Dict, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)

COMPRESSION_ENABLED = True      # 是否启用压缩
COMPRESSION_LEVEL = 1          # 压缩级别 1-9（1最快）
COMPRESSION_THRESHOLD = 100    # 小于此字节数不压缩（避免负优化）

def compress_registers_blob(registers: List[int]) -> bytes:
    """
    将寄存器数组转换并压缩为 BLOB

    格式: [标记头1字节][数据]
    - 0x00: 未压缩
    - 0x01: zlib压缩
    """
    # 转换为二进制
    raw_blob = struct.pack(f"<{len(registers)}I", *[r & 0xFFFFFFFF for r in registers])

    # 判断是否需要压缩
    if not COMPRESSION_ENABLED or len(raw_blob) < COMPRESSION_THRESHOLD:
        return b"\x00" + raw_blob

    # 尝试压缩
    try:
        compressed = zlib.compress(raw_blob, COMPRESSION_LEVEL)
        # 只有节省超过10%才使用压缩版本
        return (
            (b"\x01" + compressed)
            if len(compressed) < len(raw_blob) * 0.9
            else (b"\x00" + raw_blob)
        )
    except Exception as e:
        logger.error(f"压缩失败: {e}")
        return b"\x00" + raw_blob


def decompress_registers_blob(blob: bytes) -> List[int]:
    """
    解压 BLOB 并转换为寄存器数组

    自动识别格式并兼容旧数据
    """
    if not blob:
        return []

    try:
        # 检查标记头
        if blob[0:1] == b"\x01":
            # 已压缩
            raw_blob = zlib.decompress(blob[1:])
        elif blob[0:1] == b"\x00":
            # 未压缩
            raw_blob = blob[1:]
        else:
            # 旧数据（无标记头）
            raw_blob = blob

        # 解析为 uint32 数组
        return list(struct.unpack(f"<{len(raw_blob) // 4}I", raw_blob))
    except:
        # 降级处理：尝试直接解析
        try:
            return list(struct.unpack(f"<{len(blob) // 4}I", blob))
        except Exception as e:
            logger.error(f"解压失败: {e}")
            return []
        
class FullHistoryDatabaseManager:
    """全历史数据库管理器 - 一个设备一张表的高性能实现"""
    
    def __init__(self, db_path: str = "full_history.db"):
        """
        初始化全历史数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 性能优化：缓存已创建的表
        self._created_tables: Set[int] = set()
        
        # 性能优化：复用数据库连接（用于频繁插入）
        self._insert_conn: Optional[sqlite3.Connection] = None
        
        self._init_database()
        self._load_existing_tables()
        
    def _init_database(self):
        """初始化数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建设备表索引表，用于记录所有设备的表名
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS device_tables (
                        device_uid INTEGER PRIMARY KEY,
                        table_name TEXT NOT NULL UNIQUE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logger.info("全历史数据库初始化完成")
                
        except Exception as e:
            logger.error(f"初始化全历史数据库失败: {e}")
            raise
    
    def _load_existing_tables(self):
        """启动时加载所有已存在的设备表到缓存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT device_uid FROM device_tables')
                self._created_tables = {row[0] for row in cursor.fetchall()}
                logger.info(f"加载了 {len(self._created_tables)} 个已存在的设备表")
        except Exception as e:
            logger.warning(f"加载已存在表失败: {e}")
            self._created_tables = set()
    
    def _get_table_name(self, device_uid: int) -> str:
        """
        根据设备UID生成表名
        
        Args:
            device_uid: 设备UID
            
        Returns:
            str: 表名（16位16进制大写字符串）
        """
        # 确保device_uid在64位范围内
        device_uid = device_uid & 0xFFFFFFFFFFFFFFFF
        return f"DEV_{device_uid:016X}"
    
    def _create_device_table(self, device_uid: int) -> bool:
        """
        为设备创建专用表
        
        Args:
            device_uid: 设备UID
            
        Returns:
            bool: 创建是否成功
        """
        # 性能优化：检查缓存，避免重复创建
        if device_uid in self._created_tables:
            return True
        
        try:
            table_name = self._get_table_name(device_uid)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建设备专用表
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp_ms INTEGER NOT NULL,
                        error_code_u32 INTEGER NOT NULL,
                        flag1_uint32 INTEGER NOT NULL,
                        registers_blob BLOB NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(timestamp_ms, error_code_u32, flag1_uint32)
                    )
                ''')
                
                # 创建索引以提高查询性能
                cursor.execute(f'''
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp 
                    ON {table_name}(timestamp_ms)
                ''')
                
                # 记录到设备表索引
                cursor.execute('''
                    INSERT OR IGNORE INTO device_tables (device_uid, table_name)
                    VALUES (?, ?)
                ''', (device_uid, table_name))
                
                conn.commit()
                
                # 添加到缓存
                self._created_tables.add(device_uid)
                logger.info(f"设备表{table_name}创建完成")
                return True
                
        except Exception as e:
            logger.error(f"创建设备表失败: {e}")
            return False
    
    def _get_insert_connection(self) -> sqlite3.Connection:
        """获取或创建用于插入的数据库连接"""
        if self._insert_conn is None:
            self._insert_conn = sqlite3.connect(self.db_path)
            # 性能优化：设置WAL模式和同步模式
            self._insert_conn.execute('PRAGMA journal_mode=WAL')
            self._insert_conn.execute('PRAGMA synchronous=NORMAL')
            self._insert_conn.execute('PRAGMA cache_size=-64000')  # 64MB缓存
            self._insert_conn.execute('PRAGMA temp_store=MEMORY')
            self._insert_conn.execute('PRAGMA mmap_size=268435456')  # 256MB mmap
        return self._insert_conn
    
    def insert_full_record(self, device_uid: int, timestamp_ms: int,
                          error_code_u32: int, flag1_uint32: int,
                          registers: List[int]) -> bool:
        """
        插入全历史记录
        
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
            # 性能优化：只在首次遇到设备时创建表
            if device_uid not in self._created_tables:
                if not self._create_device_table(device_uid):
                    return False
            
            table_name = self._get_table_name(device_uid)
            
            # 将寄存器数组转换为二进制
            # safe_registers = [reg & 0xFFFFFFFF for reg in registers]
            # registers_blob = struct.pack(f'<{len(safe_registers)}I', *safe_registers)
            registers_blob = compress_registers_blob(registers)

            # 性能优化：使用持久连接
            conn = self._get_insert_connection()
            cursor = conn.cursor()
            
            cursor.execute(f'''
                INSERT OR IGNORE INTO {table_name}
                (timestamp_ms, error_code_u32, flag1_uint32, registers_blob)
                VALUES (?, ?, ?, ?)
            ''', (timestamp_ms, error_code_u32, flag1_uint32, registers_blob))
            
            conn.commit()
            
            return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"插入全历史记录失败: {e}")
            return False
    
    def insert_full_records_batch(self, device_uid: int, 
                                  records: List[tuple[int, int, int, List[int]]]) -> int:
        """
        批量插入全历史记录（高性能版本）
        
        Args:
            device_uid: 设备UID
            records: 记录列表，每条记录为 (timestamp_ms, error_code_u32, flag1_uint32, registers)
            
        Returns:
            int: 成功插入的记录数
        """
        try:
            # 确保表存在
            if device_uid not in self._created_tables:
                if not self._create_device_table(device_uid):
                    return 0
            
            table_name = self._get_table_name(device_uid)
            
            # 准备批量插入数据
            batch_data = []
            for timestamp_ms, error_code_u32, flag1_uint32, registers in records:
                # safe_registers = [reg & 0xFFFFFFFF for reg in registers]
                # registers_blob = struct.pack(f'<{len(safe_registers)}I', *safe_registers)
                registers_blob = compress_registers_blob(registers)
                batch_data.append((timestamp_ms, error_code_u32, flag1_uint32, registers_blob))
            
            conn = self._get_insert_connection()
            cursor = conn.cursor()
            
            cursor.executemany(f'''
                INSERT OR IGNORE INTO {table_name}
                (timestamp_ms, error_code_u32, flag1_uint32, registers_blob)
                VALUES (?, ?, ?, ?)
            ''', batch_data)
            
            conn.commit()
            
            inserted_count = cursor.rowcount
            # logger.info(f"批量插入{inserted_count}条记录")
            return inserted_count
            
        except Exception as e:
            logger.error(f"批量插入失败: {e}")
            return 0
    
    def query_full_records(self, device_uid: Optional[int] = None, 
                          start_date: Optional[date] = None,
                          end_date: Optional[date] = None,
                          start_time_ms: Optional[int] = None,
                          only_faults: bool = False,
                          limit: int = 1000,
                          offset: int = 0) -> List[Dict]:
        """
        查询全历史记录
        
        Args:
            device_uid: 设备UID，None表示查询所有设备
            start_date: 开始日期
            end_date: 结束日期
            start_time_ms: 当日起始时间（毫秒，从0点开始计算）
            only_faults: 是否只查询故障记录
            limit: 最大返回记录数
            offset: 偏移量（用于分页）
            
        Returns:
            List[Dict]: 全历史记录列表
        """
        try:
            records = []
            
            # 获取要查询的设备列表
            device_uids = [device_uid] if device_uid is not None else self.get_device_uids()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for uid in device_uids:
                    table_name = self._get_table_name(uid)
                    
                    # 检查表是否存在（优化：使用缓存）
                    if uid not in self._created_tables:
                        continue
                    
                    # 构建查询条件
                    conditions = []
                    params = []
                    
                    if start_date is not None:
                        start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
                        if start_time_ms is not None:
                            start_timestamp += start_time_ms
                        conditions.append("timestamp_ms >= ?")
                        params.append(start_timestamp)
                    
                    if end_date is not None:
                        end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)
                        conditions.append("timestamp_ms <= ?")
                        params.append(end_timestamp)
                    
                    if only_faults:
                        conditions.append("(error_code_u32 != 0 OR flag1_uint32 != 0)")
                    
                    where_clause = " AND ".join(conditions) if conditions else "1=1"
                    
                    query = f'''
                        SELECT id, timestamp_ms, error_code_u32, flag1_uint32,
                               registers_blob, created_at
                        FROM {table_name}
                        WHERE {where_clause}
                        ORDER BY timestamp_ms DESC
                        LIMIT ? OFFSET ?
                    '''
                    params.extend([limit, offset])

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    # 转换为字典列表
                    for row in rows:
                        # 解析二进制寄存器数据
                        # registers_blob = row[4]
                        # registers_count = len(registers_blob) // 4  # 每个uint32占4字节
                        # registers = list(struct.unpack(f'<{registers_count}I', registers_blob))
                        registers = decompress_registers_blob(row[4])

                        record = {
                            'id': row[0],
                            'device_uid': uid,
                            'timestamp_ms': row[1],
                            'error_code_u32': row[2],
                            'flag1_uint32': row[3],
                            'registers': registers,
                            'created_at': row[5]
                        }
                        records.append(record)
                
                # 按时间戳排序
                records.sort(key=lambda x: x['timestamp_ms'], reverse=True)
                
                # 应用limit
                if len(records) > limit:
                    records = records[:limit]
                
                logger.info(f"查询到{len(records)}条全历史记录")
                return records
                
        except Exception as e:
            logger.error(f"查询全历史记录失败: {e}")
            return []
    
    def get_device_uids(self) -> List[int]:
        """获取数据库中所有设备的UID列表"""
        return sorted(list(self._created_tables))

    def get_fault_dates(self, device_uid: Optional[int] = None) -> List[date]:
        """
        获取有故障记录的日期列表

        Args:
            device_uid: 设备UID，None表示查询所有设备

        Returns:
            List[date]: 有故障记录的日期列表
        """
        try:
            dates = set()
            device_uids = [device_uid] if device_uid is not None else self.get_device_uids()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for uid in device_uids:
                    if uid not in self._created_tables:
                        continue
                    
                    table_name = self._get_table_name(uid)

                    cursor.execute(f'''
                        SELECT DISTINCT DATE(timestamp_ms / 1000, 'unixepoch', 'localtime') as fault_date
                        FROM {table_name}
                        WHERE error_code_u32 != 0 OR flag1_uint32 != 0
                        ORDER BY fault_date
                    ''')

                    rows = cursor.fetchall()
                    for row in rows:
                        try:
                            fault_date = datetime.strptime(row[0], '%Y-%m-%d').date()
                            dates.add(fault_date)
                        except ValueError:
                            continue

                return sorted(list(dates))

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

            device_uids = [device_uid] if device_uid is not None else self.get_device_uids()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for uid in device_uids:
                    if uid not in self._created_tables:
                        continue
                    
                    table_name = self._get_table_name(uid)

                    cursor.execute(f'''
                        SELECT COUNT(*) FROM {table_name}
                        WHERE timestamp_ms >= ? AND timestamp_ms <= ?
                        AND (error_code_u32 != 0 OR flag1_uint32 != 0)
                    ''', (start_timestamp, end_timestamp))

                    count = cursor.fetchone()[0]
                    if count > 0:
                        return True

                return False

        except Exception as e:
            logger.error(f"检查故障日期失败: {e}")
            return False

    def count_records(self, device_uid: Optional[int] = None,
                     start_date: Optional[date] = None,
                     end_date: Optional[date] = None,
                     start_time_ms: Optional[int] = None,
                     only_faults: bool = False) -> int:
        """
        统计记录数量（用于分页）

        Args:
            device_uid: 设备UID，None表示查询所有设备
            start_date: 开始日期
            end_date: 结束日期
            start_time_ms: 当日起始时间（毫秒，从0点开始计算）
            only_faults: 是否只统计故障记录

        Returns:
            int: 记录数量
        """
        try:
            total_count = 0
            device_uids = [device_uid] if device_uid is not None else self.get_device_uids()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for uid in device_uids:
                    if uid not in self._created_tables:
                        continue
                    
                    table_name = self._get_table_name(uid)

                    conditions = []
                    params = []

                    if start_date is not None:
                        start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
                        if start_time_ms is not None:
                            start_timestamp += start_time_ms
                        conditions.append("timestamp_ms >= ?")
                        params.append(start_timestamp)

                    if end_date is not None:
                        end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)
                        conditions.append("timestamp_ms <= ?")
                        params.append(end_timestamp)

                    if only_faults:
                        conditions.append("(error_code_u32 != 0 OR flag1_uint32 != 0)")

                    where_clause = " AND ".join(conditions) if conditions else "1=1"

                    query = f'''
                        SELECT COUNT(*) FROM {table_name}
                        WHERE {where_clause}
                    '''

                    cursor.execute(query, params)
                    count = cursor.fetchone()[0]
                    total_count += count

                logger.info(f"统计到{total_count}条记录")
                return total_count

        except Exception as e:
            logger.error(f"统计记录数量失败: {e}")
            return 0

    def clear_old_records(self, days_to_keep: int = 30) -> int:
        """
        清理旧的全历史记录

        Args:
            days_to_keep: 保留的天数

        Returns:
            int: 删除的记录数
        """
        try:
            cutoff_timestamp = int((datetime.now().timestamp() - days_to_keep * 24 * 3600) * 1000)
            total_deleted = 0

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for uid in self._created_tables:
                    table_name = self._get_table_name(uid)

                    cursor.execute(f'''
                        DELETE FROM {table_name}
                        WHERE timestamp_ms < ?
                    ''', (cutoff_timestamp,))

                    deleted_count = cursor.rowcount
                    total_deleted += deleted_count

                    if deleted_count > 0:
                        logger.info(f"设备{uid:08X}清理了{deleted_count}条旧记录")

                conn.commit()
                logger.info(f"总共清理了{total_deleted}条旧全历史记录")
                return total_deleted

        except Exception as e:
            logger.error(f"清理旧全历史记录失败: {e}")
            return 0

    def close(self):
        """关闭数据库连接"""
        if self._insert_conn is not None:
            self._insert_conn.close()
            self._insert_conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

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

            # 准备批量数据
            batch_records = []
            
            for i in range(50000):
                random_hours = random.randint(0, 7 * 24)
                random_minutes = random.randint(0, 59)
                random_seconds = random.randint(0, 59)
                timestamp = base_time - timedelta(hours=random_hours, minutes=random_minutes, seconds=random_seconds)
                timestamp_ms = int(timestamp.timestamp() * 1000)

                has_fault = random.choice([True, False, False, False])

                if has_fault:
                    error_code_u32 = random.choice([0x02010D00, 0x01020000, 0x000102F0])
                    flag1_uint32 = random.choice([0xF00F001, 0x1000F01, 0x2000F02])
                else:
                    error_code_u32 = 0x00000000
                    flag1_uint32 = 0x00000000

                registers = [0] * 107
                registers[55] = 0x50453A08
                registers[63] = error_code_u32
                registers[90] = flag1_uint32
                registers[83] = random.randint(0, 100000) & 0xFFFFFFFF
                registers[62] = random.randint(0, 36000)
                registers[76] = 690000
                registers[77] = 780000
                registers[78] = 120000
                registers[79] = 190000

                batch_records.append((timestamp_ms, error_code_u32, flag1_uint32, registers))
                
                # 每1000条批量插入一次
                if len(batch_records) >= 1000:
                    self.insert_full_records_batch(test_uid, batch_records)
                    batch_records = []
            
            # 插入剩余数据
            if batch_records:
                inserted_count = self.insert_full_records_batch(test_uid, batch_records)
            
            logger.info(f"插入了{inserted_count}条测试数据")
            return inserted_count

        except Exception as e:
            logger.error(f"插入测试数据失败: {e}")
            return 0
