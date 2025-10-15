# -*- coding: utf-8 -*-
import logging
from datetime import datetime, date
from typing import Callable, List, Awaitable

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import QTableWidgetItem
from qasync import asyncSlot
from qfluentwidgets import PipsScrollButtonDisplayMode

from src.communication.protocol import PACKET_TYPE_SYS_REGS_UP
from src.communication.protocol import SysREGsUpData
from src.config.config_manager import ConfigManager
from src.database.full_history_database_manager import FullHistoryDatabaseManager
from src.ui import Full_History_Panel_Form
from src.utils.register_parser import RegisterParser
from src.window.motor_controller_parser import MotorControllerParser

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("full_history_panel_frame.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def uint32_to_int32(value: int) -> int:
    """将无符号32位整数转换为有符号32位整数"""
    if value >= 0x80000000:  # 2^31
        return value - 0x100000000  # 2^32
    return value


class FullHistoryPanelForm(QtWidgets.QFrame, Full_History_Panel_Form):
    """故障历史记录窗口类"""

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
        self.cfg: ConfigManager = cfg
        self.config_file_path = config_file_path
        self.device_reg_set_func = device_reg_set_func
        self.setObjectName("FullHistoryPanelForm")

        # 初始化数据库管理器
        self.db_manager = FullHistoryDatabaseManager("data/full_history.db")

        # 初始化解析器
        self.parser = MotorControllerParser()
        self.register_parser = RegisterParser()

        # 分页相关属性
        self.records_per_page = 100  # 每页显示的最大记录条数
        self.current_page = 0       # 当前页码（从0开始）
        self.total_records = 0      # 总记录数
        self.total_pages = 0        # 总页数

        # 每多少条消息记录一次的配置（方便后期修改）
        self.record_interval = 1   # 每1条消息记录一次（可以调整为更大的值来减少记录频率）

        # 使能实时记录
        self.enable_record = False
        
        # # 初始化UI组件
        self._init_device_combo()
        self._init_calendar()
        self._init_time_picker()
        self._init_fault_table()
        self._init_pager()
        self.switch_btn_enable_record.setChecked(False)

        # # 连接信号
        self._connect_signals()

        # # 插入测试数据
        # self.db_manager.insert_test_data()

        # 初始化显示
        self._refresh_fault_table()
        self._update_pager()

    def _init_device_combo(self):
        """初始化设备选择下拉框"""
        try:
            # 清空现有选项
            self.combo_box_devices.clear()

            # 添加"所有设备"选项
            self.combo_box_devices.addItem("所有设备", userData=None)

            # 从数据库获取设备UID列表
            device_uids = self.db_manager.get_device_uids()

            # 添加设备选项
            for uid in device_uids:
                device_name = self.cfg.get_device_name(uid)
                self.combo_box_devices.addItem(device_name, userData=uid)

            # 设置默认选择第一个选项
            if self.combo_box_devices.count() > 0:
                self.combo_box_devices.setCurrentIndex(0)

            logger.info(f"设备下拉框初始化完成，共{len(device_uids)}个设备")

        except Exception as e:
            logger.error(f"初始化设备下拉框失败: {e}")

    def _init_calendar(self):
        """初始化日历选择器"""
        try:
            # 设置当前日期
            self.calendar_picker_full_history.setDate(QDate.currentDate())

            # 设置日期格式
            self.calendar_picker_full_history.setDateFormat('yyyy-MM-dd')

            logger.info("全历史日历选择器初始化完成")

        except Exception as e:
            logger.error(f"初始化全历史日历选择器失败: {e}")

    def _init_time_picker(self):
        """初始化时间选择器"""
        try:
            # 设置默认时间为0点
            from PyQt5.QtCore import QTime
            self.time_picker_full_history.setTime(QTime(0, 0, 0))

            logger.info("时间选择器初始化完成")

        except Exception as e:
            logger.error(f"初始化时间选择器失败: {e}")

    def _init_pager(self):
        """初始化分页器"""
        try:
            horizontal_pips_pager = self.horizontal_pips_pager
  
            # 设置页数（初始为1页）
            horizontal_pips_pager.setPageNumber(1)

            # 设置可见圆点数量
            horizontal_pips_pager.setVisibleNumber(8)

            # 始终显示前进和后退按钮
            horizontal_pips_pager.setNextButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)
            horizontal_pips_pager.setPreviousButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)

            # 设置当前页码
            horizontal_pips_pager.setCurrentIndex(0)

            logger.info("分页器初始化完成")

        except Exception as e:
            logger.error(f"初始化分页器失败: {e}")

    def _init_fault_table(self):
        """初始化故障记录表格"""
        try:
            # 创建表格控件

            # 设置表格样式
            self.table_full_history.setSelectRightClickedRow(True)
            self.table_full_history.setBorderVisible(True)
            self.table_full_history.setBorderRadius(8)
            self.table_full_history.setWordWrap(False)

            # 设置表格列
            headers = [
                "日期时间", "设备名称", "报错A", "报错B", "报错C",
                "故障状态", "系统状态", "系统模式",
                "温度信息", "mSpeed", "angle", "Vbus", "Vbus_in", "Id", "Iq", "Ud", "Uq", "Ia", "Ib", "Ic", "Ibus",
                "mDuty", "mPT1", "mPT2", "mPT3", "mPT4", "mPT5",
            ]
            self.table_full_history.setColumnCount(len(headers))
            self.table_full_history.setHorizontalHeaderLabels(headers)
            self.table_full_history.verticalHeader().hide()


            # 列宽设置（用户可手动调节列宽以展开所有错误信息）
            self.table_full_history.horizontalHeader().setStretchLastSection(True)
            self.table_full_history.resizeColumnsToContents()

            logger.info("故障记录表格初始化完成")

        except Exception as e:
            logger.error(f"初始化故障记录表格失败: {e}")

    def _connect_signals(self):
        """连接信号槽"""
        try:
            # 设备选择变化信号
            self.combo_box_devices.currentIndexChanged.connect(self._on_device_changed)

            # 日期选择变化信号
            self.calendar_picker_full_history.dateChanged.connect(self._on_date_changed)

            # 时间选择变化信号
            self.time_picker_full_history.timeChanged.connect(self._on_time_changed)

            # 故障筛选单选按钮信号
            self.radio_btn_full_history.toggled.connect(self._on_fault_filter_changed)

            # 分页器页码变化信号
            self.horizontal_pips_pager.currentIndexChanged.connect(self._on_page_changed)

            # 实时记录开关信号
            self.switch_btn_enable_record.toggled.connect(self.on_enable_record_toggled)

            logger.info("信号连接完成")

        except Exception as e:
            logger.error(f"连接信号失败: {e}")

    def _update_calendar_fault_dates(self):
        """更新日历中的故障日期标记（暂时不实现）"""
        pass

    @asyncSlot(SysREGsUpData)
    async def on_on_sys_regs_uploaded(self, sys_regs_up_data: SysREGsUpData):
        """处理系统寄存器上传数据"""
        if not self.enable_record:
            return
        
        try:
            device_uid = sys_regs_up_data.uid

            # 检查寄存器数组长度
            if len(sys_regs_up_data.reg) < 91:
                logger.warning(f"寄存器数组长度不足: {len(sys_regs_up_data.reg)}")
                return

            # 获取故障相关寄存器
            error_code_u32 = sys_regs_up_data.reg[63]  # 错误代码
            flag1_uint32 = sys_regs_up_data.reg[90]    # 故障标志


            # 记录到数据库
        
            timestamp_ms = int(datetime.now().timestamp() * 1000)

            # 存储到数据库
            success = self.db_manager.insert_full_record(
                device_uid=device_uid,
                timestamp_ms=timestamp_ms,
                error_code_u32=error_code_u32,
                flag1_uint32=flag1_uint32,
                registers=sys_regs_up_data.reg
            )

            if success:
                logger.info(f"记录全历史数据: 设备{device_uid:08X}, 错误码{error_code_u32:08X}, 标志{flag1_uint32:08X}")

                # 更新设备下拉框（如果是新设备）
                if device_uid not in self.last_error_code:
                    self._update_device_combo()

                # 更新日历故障日期标记
                self._update_calendar_fault_dates()

        except Exception as e:
            logger.error(f"处理系统寄存器数据错误: {e}")

    def _on_device_changed(self):
        """设备选择变化处理"""
        try:
            # 更新日历故障日期标记
            self._update_calendar_fault_dates()

            # 刷新故障记录表格
            self._refresh_fault_table()
            self._update_pager()

            logger.info(f"设备选择变化: {self.combo_box_devices.currentText()}")
        except Exception as e:
            logger.error(f"处理设备选择变化错误: {e}")

    def _on_date_changed(self, selected_date: QDate):
        """日期选择变化处理"""
        try:
            self.current_page = 0  # 重置到第一页
            self._refresh_fault_table()
            self._update_pager()
            logger.info(f"日期选择变化: {selected_date.toString('yyyy-MM-dd')}")
        except Exception as e:
            logger.error(f"处理日期选择变化错误: {e}")

    def _on_time_changed(self):
        """时间选择变化处理"""
        try:
            self.current_page = 0  # 重置到第一页
            self._refresh_fault_table()
            self._update_pager()
            logger.info(f"时间选择变化: {self.time_picker_full_history.time.toString('HH:mm:ss')}")
        except Exception as e:
            logger.error(f"处理时间选择变化错误: {e}")

    def _on_fault_filter_changed(self, checked: bool):
        """故障筛选变化处理"""
        try:
            self.current_page = 0  # 重置到第一页
            self._refresh_fault_table()
            self._update_pager()
            filter_text = "仅显示故障" if checked else "显示全部"
            logger.info(f"故障筛选变化: {filter_text}")
        except Exception as e:
            logger.error(f"处理故障筛选变化错误: {e}")

    def _on_page_changed(self, page_index: int):
        """分页变化处理"""
        try:
            self.current_page = page_index
            self._refresh_fault_table()
            logger.info(f"页码变化: {page_index + 1}/{self.total_pages}")
        except Exception as e:
            logger.error(f"处理页码变化错误: {e}")

    def on_enable_record_toggled(self, checked: bool):
        self.enable_record = checked
        logger.info(f"实时记录开关: {checked}")

    def _update_device_combo(self):
        """更新设备下拉框"""
        try:
            current_selection = self.combo_box_devices.currentData()
            current_text = self.combo_box_devices.currentText()

            # 重新初始化设备下拉框
            self._init_device_combo()

            # 尝试恢复之前的选择
            for i in range(self.combo_box_devices.count()):
                if self.combo_box_devices.itemData(i) == current_selection:
                    self.combo_box_devices.setCurrentIndex(i)
                    break
            else:
                # 如果找不到之前的选择，尝试按文本匹配
                for i in range(self.combo_box_devices.count()):
                    if self.combo_box_devices.itemText(i) == current_text:
                        self.combo_box_devices.setCurrentIndex(i)
                        break

        except Exception as e:
            logger.error(f"更新设备下拉框错误: {e}")

    def _refresh_fault_table(self):
        """刷新全历史记录表格"""
        try:
            # 获取当前选择的设备和日期
            device_uid = self.combo_box_devices.currentData()
            # 获取选择的日期
            qdate = self.calendar_picker_full_history.date
            selected_date = date(qdate.year(), qdate.month(), qdate.day())

            # 获取选择的时间（转换为毫秒）
            qtime = self.time_picker_full_history.time
            start_time_ms = (qtime.hour() * 3600 + qtime.minute() * 60 + qtime.second()) * 1000

            # 获取故障筛选状态
            only_faults = self.radio_btn_full_history.isChecked()

            # 避免无意义的查询
            if device_uid is None and not only_faults:
                # 如果选择了"所有设备"且不筛选故障，可能数据量很大，给出提示
                logger.warning("查询所有设备的全部记录可能数据量很大，建议选择特定设备或启用故障筛选")

            # 首先统计总记录数
            self.total_records = self.db_manager.count_records(
                device_uid=device_uid,
                start_date=selected_date,
                end_date=selected_date,
                start_time_ms=start_time_ms,
                only_faults=only_faults
            )

            # 计算总页数
            self.total_pages = max(1, (self.total_records + self.records_per_page - 1) // self.records_per_page)

            # 确保当前页码在有效范围内
            if self.current_page >= self.total_pages:
                self.current_page = max(0, self.total_pages - 1)

            # 查询当前页的记录
            offset = self.current_page * self.records_per_page
            records = self.db_manager.query_full_records(
                device_uid=device_uid,
                start_date=selected_date,
                end_date=selected_date,
                start_time_ms=start_time_ms,
                only_faults=only_faults,
                limit=self.records_per_page,
                offset=offset
            )

            # 清空表格
            self.table_full_history.setRowCount(0)

            # 填充数据
            for i, record in enumerate(records):
                self.table_full_history.insertRow(i)

                # 解析时间戳（精确到毫秒）
                timestamp = datetime.fromtimestamp(record['timestamp_ms'] / 1000)
                datetime_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # 保留3位毫秒

                # 获取设备名称
                device_name = self.cfg.get_device_name(record['device_uid'])

                # 创建SysREGsUpData对象并使用统一的寄存器解析器
                sys_regs_data = SysREGsUpData(
                    packet_type=PACKET_TYPE_SYS_REGS_UP,
                    reg_num=len(record['registers']),
                    reg=record['registers'],
                )

                # 使用统一的寄存器解析器
                parsed_data = self.register_parser.parse_sys_regs_data(sys_regs_data)

                # 获取故障状态文本
                fault_status = self.register_parser.get_fault_status_text(parsed_data.flag1_uint32)
                fault_list = []
                for category, status in parsed_data.fault_info.items():
                    if status:
                        fault_list.extend(status)

                # 获取温度和状态信息
                info = parsed_data.info
                temp_info = f"A:{info['temp_d']}°C B:{info['temp_c']}°C C:{info['temp_b']}°C"
                sys_status = f"{info['state_en']}:{info['state_cn']}"
                sys_mode = parsed_data.sys_mode_name
                if parsed_data.zero_enabled:
                    sys_mode += " (Zero)"

                # 使用解析后的数值（已经格式化为字符串）
                values = {
                    'mSpeed': f"{parsed_data.mSpeed:.2f}",
                    'angle': f"{parsed_data.angle:.2f}",
                    'Vbus': f"{parsed_data.Vbus:.2f}",
                    'Vbus_in': f"{parsed_data.Vbus_in:.2f}",
                    'Id': f"{parsed_data.Id:.2f}",
                    'Iq': f"{parsed_data.Iq:.2f}",
                    'Ud': f"{parsed_data.Ud:.2f}",
                    'Uq': f"{parsed_data.Uq:.2f}",
                    'Ia': f"{parsed_data.Ia:.2f}",
                    'Ib': f"{parsed_data.Ib:.2f}",
                    'Ic': f"{parsed_data.Ic:.2f}",
                    'Ibus': f"{parsed_data.Ibus:.2f}",
                    'mDuty': f"{parsed_data.mDuty:.2f}",
                    'mPT1': f"{parsed_data.mPT1:.2f}",
                    'mPT2': f"{parsed_data.mPT2:.2f}",
                    'mPT3': f"{parsed_data.mPT3:.2f}",
                    'mPT4': f"{parsed_data.mPT4:.2f}",
                    'mPT5': f"{parsed_data.mPT5:.2f}",
                }

                # 填充表格数据
                col = 0
                self._set_table_item(i, col, datetime_str)
                col += 1
                self._set_table_item(i, col, device_name)
                col += 1

                # 报错A/B/C（显示16进制值+解析值）
                # 报错A (module_d)
                error_d_text = self.register_parser.get_error_text(parsed_data.error_code_u32, 'd')
                error_d = (parsed_data.error_code_u32 >> 24) & 0xFF
                self._set_table_item(i, col, error_d_text, is_fault=bool(error_d))
                col += 1

                # 报错B (module_c)
                error_c_text = self.register_parser.get_error_text(parsed_data.error_code_u32, 'c')
                error_c = (parsed_data.error_code_u32 >> 16) & 0xFF
                self._set_table_item(i, col, error_c_text, is_fault=bool(error_c))
                col += 1

                # 报错C (module_b)
                error_b_text = self.register_parser.get_error_text(parsed_data.error_code_u32, 'b')
                error_b = (parsed_data.error_code_u32 >> 8) & 0xFF
                self._set_table_item(i, col, error_b_text, is_fault=bool(error_b))
                col += 1

                # 故障状态、系统状态、系统模式
                self._set_table_item(i, col, fault_status, is_fault=bool(fault_list))
                col += 1
                self._set_table_item(i, col, sys_status)
                col += 1
                self._set_table_item(i, col, sys_mode)
                col += 1

                # 温度信息
                self._set_table_item(i, col, temp_info)
                col += 1

                # 其他数值
                for key in ['mSpeed', 'angle', 'Vbus', 'Vbus_in', 'Id', 'Iq', 'Ud', 'Uq', 'Ia', 'Ib', 'Ic', 'Ibus', 'mDuty', 'mPT1', 'mPT2', 'mPT3', 'mPT4', 'mPT5']:
                    self._set_table_item(i, col, values.get(key, "0.00"))
                    col += 1

            # 自适应列宽
            self.table_full_history.resizeColumnsToContents()

            logger.info(f"刷新全历史记录表格完成，第{self.current_page + 1}/{self.total_pages}页，共{len(records)}条记录，总计{self.total_records}条")

        except Exception as e:
            logger.error(f"刷新全历史记录表格错误: {e}")

    def _update_pager(self):
        """更新分页器"""
        try:
            # 设置总页数
            self.horizontal_pips_pager.setPageNumber(self.total_pages)

            # 设置当前页码
            self.horizontal_pips_pager.setCurrentIndex(self.current_page)

            # 如果只有一页，隐藏分页器
            if self.total_pages <= 1:
                self.horizontal_pips_pager.setVisible(False)
            else:
                self.horizontal_pips_pager.setVisible(True)

            logger.debug(f"分页器更新: 第{self.current_page + 1}/{self.total_pages}页")

        except Exception as e:
            logger.error(f"更新分页器错误: {e}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            logger.info("FaultHistoryPanelForm正常退出")
            self.db_manager.close()
            event.accept()
        except Exception as e:
            logger.error(f"关闭FaultHistoryPanelForm时出错: {e}")
            event.accept()

    def _set_table_item(self, row: int, col: int, text: str, is_fault: bool = False):
        """设置表格项"""
        try:
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignCenter)

            # 设置字体和颜色
            font = item.font()
            if is_fault:
                # 故障项：加粗红色字体，浅红色背景
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QtGui.QColor(139, 0, 0))  # 深红色字体
                item.setBackground(QtGui.QColor(255, 240, 240))  # 浅红色背景
            else:
                # 正常项：普通字体
                if text == "正常":
                    item.setForeground(QtGui.QColor(0, 128, 0))  # 绿色字体
                    item.setBackground(QtGui.QColor(240, 255, 240))  # 浅绿色背景
                else:
                    item.setForeground(QtGui.QColor(0, 0, 0))  # 黑色字体

            self.table_full_history.setItem(row, col, item)

        except Exception as e:
            logger.error(f"设置表格项错误: {e}")

