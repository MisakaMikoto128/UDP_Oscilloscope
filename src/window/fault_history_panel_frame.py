# -*- coding: utf-8 -*-
import logging
from typing import Callable, List, Awaitable
from datetime import datetime, date

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QTableWidgetItem
from qasync import asyncSlot
from qfluentwidgets import InfoBar, InfoBarPosition, TableWidget
from PyQt5.QtCore import Qt, QDate

from src.communication.protocol import SysREGsUpData
from src.config.config_manager import ConfigManager
from src.ui import History_Panel_Form
# from src.ui.fault_calendar_picker import FaultCalendarPicker  # 暂时不使用
from src.database.fault_database_manager import FaultDatabaseManager
from src.window.motor_controller_parser import MotorControllerParser
from src.communication.protocol import PACKET_TYPE_SYS_REGS_UP
from src.utils.register_parser import RegisterParser
# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("fault_history_panel_frame.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def uint32_to_int32(value: int) -> int:
    """将无符号32位整数转换为有符号32位整数"""
    if value >= 0x80000000:  # 2^31
        return value - 0x100000000  # 2^32
    return value


class FaultHistoryPanelForm(QtWidgets.QFrame, History_Panel_Form):
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
        self.setObjectName("FaultHistoryPanelForm")

        # 初始化数据库管理器
        self.db_manager = FaultDatabaseManager("data/fault_history.db")

        # 初始化解析器
        self.parser = MotorControllerParser()
        self.register_parser = RegisterParser()

        # 存储上一次的故障状态，用于检测变化
        self.last_error_code = {}  # device_uid -> error_code_u32
        self.last_flag1 = {}       # device_uid -> flag1_uint32

        # 初始化UI组件
        self._init_device_combo()
        self._init_calendar()
        self._init_fault_table()

        # 连接信号
        self._connect_signals()

        # 插入测试数据
        # self.db_manager.insert_test_data()

        # 初始化显示
        self._refresh_fault_table()

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
            # 获取主布局
            # main_layout = self.gridLayout_2

            # # 替换原有的日历选择器为故障日历选择器
            # # 先移除原有的日历控件
            # main_layout.removeWidget(self.calendar_picker_fault_history)
            # self.calendar_picker_fault_history.deleteLater()

            # 创建新的故障日历选择器
            # self.calendar_picker_fault_history = FaultCalendarPicker(self)
            # self.calendar_picker_fault_history.setObjectName("calendar_picker_fault_history")

            # 设置当前日期
            self.calendar_picker_fault_history.setDate(QDate.currentDate())

            # 设置日期格式
            self.calendar_picker_fault_history.setDateFormat('yyyy-MM-dd')

            # # 将新的日历控件添加到主布局中（位置0,0）
            # main_layout.addWidget(self.calendar_picker_fault_history, 0, 0, 1, 1)

            # # 初始化故障日期标记
            # self._update_calendar_fault_dates()

            logger.info("故障日历选择器初始化完成")

        except Exception as e:
            logger.error(f"初始化故障日历选择器失败: {e}")

    def _init_fault_table(self):
        """初始化故障记录表格"""
        try:
            # 设置表格样式
            self.table_fault_history.setSelectRightClickedRow(True)
            self.table_fault_history.setBorderVisible(True)
            self.table_fault_history.setBorderRadius(8)
            self.table_fault_history.setWordWrap(False)

            # 设置表格列
            headers = [
                "日期时间", "设备名称", "报错A", "报错B", "报错C",
                "故障状态", "系统状态", "系统模式",
                "温度信息", "mSpeed", "angle", "Vbus", "Vbus_in", "Id", "Iq", "Ud", "Uq", "Ia", "Ib", "Ic", "Ibus",
                "mDuty", "mPT1", "mPT2", "mPT3", "mPT4", "mPT5",
            ]
            self.table_fault_history.setColumnCount(len(headers))
            self.table_fault_history.setHorizontalHeaderLabels(headers)
            self.table_fault_history.verticalHeader().hide()

            # 列宽设置（用户可手动调节列宽以展开所有错误信息）
            self.table_fault_history.horizontalHeader().setStretchLastSection(True)
            self.table_fault_history.resizeColumnsToContents()

            logger.info("故障记录表格初始化完成")

        except Exception as e:
            logger.error(f"初始化故障记录表格失败: {e}")

    def _connect_signals(self):
        """连接信号槽"""
        try:
            # 设备选择变化信号
            self.combo_box_devices.currentIndexChanged.connect(self._on_device_changed)

            # 日期选择变化信号
            self.calendar_picker_fault_history.dateChanged.connect(self._on_date_changed)

            logger.info("信号连接完成")

        except Exception as e:
            logger.error(f"连接信号失败: {e}")

    def _update_calendar_fault_dates(self):
        """更新日历中的故障日期标记（暂时不实现）"""
        pass

    @asyncSlot(SysREGsUpData)
    async def on_on_sys_regs_uploaded(self, sys_regs_up_data: SysREGsUpData):
        """处理系统寄存器上传数据"""
        try:
            device_uid = sys_regs_up_data.reg[0]

            # 检查寄存器数组长度
            if len(sys_regs_up_data.reg) < 91:
                logger.warning(f"寄存器数组长度不足: {len(sys_regs_up_data.reg)}")
                return

            # 获取故障相关寄存器
            error_code_u32 = sys_regs_up_data.reg[63]  # 错误代码
            flag1_uint32 = sys_regs_up_data.reg[90]    # 故障标志

            # 检查是否是第一次收到数据或故障状态发生变化
            is_first_time = device_uid not in self.last_error_code
            error_changed = (device_uid in self.last_error_code and
                           self.last_error_code[device_uid] != error_code_u32)
            flag_changed = (device_uid in self.last_flag1 and
                          self.last_flag1[device_uid] != flag1_uint32)

            # 如果是第一次或者故障状态发生变化，则记录到数据库
            if is_first_time or error_changed or flag_changed:
                timestamp_ms = int(datetime.now().timestamp() * 1000)

                # 存储到数据库
                success = self.db_manager.insert_fault_record(
                    device_uid=device_uid,
                    timestamp_ms=timestamp_ms,
                    error_code_u32=error_code_u32,
                    flag1_uint32=flag1_uint32,
                    registers=sys_regs_up_data.reg
                )

                if success:
                    logger.info(f"记录故障数据: 设备{device_uid:08X}, 错误码{error_code_u32:08X}, 标志{flag1_uint32:08X}")

                    # 如果当前显示的是该设备的数据，刷新显示
                    current_device_uid = self.combo_box_devices.currentData()
                    if current_device_uid is None or current_device_uid == device_uid:
                        self._refresh_fault_table()

                    # 更新设备下拉框（如果是新设备）
                    if is_first_time:
                        self._update_device_combo()

                    # 更新日历故障日期标记
                    self._update_calendar_fault_dates()

            # 更新上一次的状态
            self.last_error_code[device_uid] = error_code_u32
            self.last_flag1[device_uid] = flag1_uint32

        except Exception as e:
            logger.error(f"处理系统寄存器数据错误: {e}")

    def _on_device_changed(self):
        """设备选择变化处理"""
        try:
            # 更新日历故障日期标记
            self._update_calendar_fault_dates()

            # 刷新故障记录表格
            self._refresh_fault_table()

            logger.info(f"设备选择变化: {self.combo_box_devices.currentText()}")
        except Exception as e:
            logger.error(f"处理设备选择变化错误: {e}")

    def _on_date_changed(self, selected_date: QDate):
        """日期选择变化处理"""
        try:
            self._refresh_fault_table()
            logger.info(f"日期选择变化: {selected_date.toString('yyyy-MM-dd')}")
        except Exception as e:
            logger.error(f"处理日期选择变化错误: {e}")

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
        """刷新故障记录表格"""
        try:
            # 获取当前选择的设备和日期
            device_uid = self.combo_box_devices.currentData()
            # 获取选择的日期
            qdate = self.calendar_picker_fault_history.date
            selected_date = date(qdate.year(), qdate.month(), qdate.day())

            # 查询故障记录
            records = self.db_manager.query_fault_records(
                device_uid=device_uid,
                start_date=selected_date,
                end_date=selected_date,
                limit=1000
            )

            # 清空表格
            self.table_fault_history.setRowCount(0)

            # 填充数据
            for i, record in enumerate(records):
                self.table_fault_history.insertRow(i)

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
                self._set_table_item(i, col, datetime_str); col += 1
                self._set_table_item(i, col, device_name); col += 1

                # 报错A/B/C（显示16进制值+解析值）
                # 报错A (module_d)
                error_d_text = self.register_parser.get_error_text(parsed_data.error_code_u32, 'd')
                error_d = (parsed_data.error_code_u32 >> 24) & 0xFF
                self._set_table_item(i, col, error_d_text, is_fault=bool(error_d)); col += 1

                # 报错B (module_c)
                error_c_text = self.register_parser.get_error_text(parsed_data.error_code_u32, 'c')
                error_c = (parsed_data.error_code_u32 >> 16) & 0xFF
                self._set_table_item(i, col, error_c_text, is_fault=bool(error_c)); col += 1

                # 报错C (module_b)
                error_b_text = self.register_parser.get_error_text(parsed_data.error_code_u32, 'b')
                error_b = (parsed_data.error_code_u32 >> 8) & 0xFF
                self._set_table_item(i, col, error_b_text, is_fault=bool(error_b)); col += 1

                # 故障状态、系统状态、系统模式
                self._set_table_item(i, col, fault_status, is_fault=bool(fault_list)); col += 1
                self._set_table_item(i, col, sys_status); col += 1
                self._set_table_item(i, col, sys_mode); col += 1

                # 温度信息
                self._set_table_item(i, col, temp_info); col += 1

                # 其他数值
                for key in ['mSpeed', 'angle', 'Vbus', 'Vbus_in', 'Id', 'Iq', 'Ud', 'Uq', 'Ia', 'Ib', 'Ic', 'Ibus', 'mDuty', 'mPT1', 'mPT2', 'mPT3', 'mPT4', 'mPT5']:
                    self._set_table_item(i, col, values.get(key, "0.00")); col += 1

            # 自适应列宽
            self.table_fault_history.resizeColumnsToContents()

            logger.info(f"刷新故障记录表格完成，共{len(records)}条记录")

        except Exception as e:
            logger.error(f"刷新故障记录表格错误: {e}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            logger.info("FaultHistoryPanelForm正常退出")
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

            self.table_fault_history.setItem(row, col, item)

        except Exception as e:
            logger.error(f"设置表格项错误: {e}")


