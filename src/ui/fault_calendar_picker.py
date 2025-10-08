# -*- coding: utf-8 -*-
"""
故障日历选择器
支持标记有故障数据的日期
"""

import logging
from datetime import date
from typing import List, Optional

from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QTextCharFormat, QColor
from qfluentwidgets import CalendarPicker

logger = logging.getLogger(__name__)


class FaultCalendarPicker(CalendarPicker):
    """
    故障日历选择器
    继承自CalendarPicker，增加故障日期标记功能
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 存储有故障数据的日期
        self.fault_dates: List[date] = []
        
        # 设置日期格式
        self._setup_date_formats()
        
        logger.info("故障日历选择器初始化完成")
    
    def _setup_date_formats(self):
        """设置日期格式"""
        try:
            # 获取日历控件
            calendar = self.calendarWidget()
            
            # 设置有故障数据的日期格式（红色背景）
            self.fault_format = QTextCharFormat()
            self.fault_format.setBackground(QColor(255, 200, 200))  # 浅红色背景
            self.fault_format.setForeground(QColor(139, 0, 0))     # 深红色字体
            
            # 设置正常日期格式
            self.normal_format = QTextCharFormat()
            self.normal_format.setBackground(QColor(255, 255, 255))  # 白色背景
            self.normal_format.setForeground(QColor(0, 0, 0))       # 黑色字体
            
            # 设置今天的格式
            self.today_format = QTextCharFormat()
            self.today_format.setBackground(QColor(200, 220, 255))   # 浅蓝色背景
            self.today_format.setForeground(QColor(0, 0, 139))      # 深蓝色字体
            
        except Exception as e:
            logger.error(f"设置日期格式失败: {e}")
    
    def set_fault_dates(self, fault_dates: List[date]):
        """
        设置有故障数据的日期列表
        
        Args:
            fault_dates: 有故障数据的日期列表
        """
        try:
            self.fault_dates = fault_dates.copy()
            self._update_calendar_display()
            logger.info(f"设置故障日期列表，共{len(fault_dates)}个日期")
            
        except Exception as e:
            logger.error(f"设置故障日期列表失败: {e}")
    
    def add_fault_date(self, fault_date: date):
        """
        添加故障日期
        
        Args:
            fault_date: 故障日期
        """
        try:
            if fault_date not in self.fault_dates:
                self.fault_dates.append(fault_date)
                self._update_calendar_display()
                logger.debug(f"添加故障日期: {fault_date}")
                
        except Exception as e:
            logger.error(f"添加故障日期失败: {e}")
    
    def remove_fault_date(self, fault_date: date):
        """
        移除故障日期
        
        Args:
            fault_date: 要移除的故障日期
        """
        try:
            if fault_date in self.fault_dates:
                self.fault_dates.remove(fault_date)
                self._update_calendar_display()
                logger.debug(f"移除故障日期: {fault_date}")
                
        except Exception as e:
            logger.error(f"移除故障日期失败: {e}")
    
    def clear_fault_dates(self):
        """清空所有故障日期"""
        try:
            self.fault_dates.clear()
            self._update_calendar_display()
            logger.info("清空所有故障日期")
            
        except Exception as e:
            logger.error(f"清空故障日期失败: {e}")
    
    def _update_calendar_display(self):
        """更新日历显示"""
        try:
            calendar = self.calendarWidget()
            
            # 清除所有日期格式
            calendar.setDateTextFormat(QDate(), QTextCharFormat())
            
            # 设置今天的格式
            today = QDate.currentDate()
            calendar.setDateTextFormat(today, self.today_format)
            
            # 设置故障日期的格式
            for fault_date in self.fault_dates:
                qdate = QDate(fault_date.year, fault_date.month, fault_date.day)
                
                # 如果是今天且有故障，使用特殊格式
                if qdate == today:
                    special_format = QTextCharFormat()
                    special_format.setBackground(QColor(255, 150, 150))  # 更深的红色背景
                    special_format.setForeground(QColor(139, 0, 0))     # 深红色字体
                    calendar.setDateTextFormat(qdate, special_format)
                else:
                    calendar.setDateTextFormat(qdate, self.fault_format)
            
            logger.debug("日历显示更新完成")
            
        except Exception as e:
            logger.error(f"更新日历显示失败: {e}")
    
    def has_fault_on_date(self, target_date: date) -> bool:
        """
        检查指定日期是否有故障
        
        Args:
            target_date: 目标日期
            
        Returns:
            bool: 是否有故障
        """
        return target_date in self.fault_dates
    
    def get_fault_dates_in_month(self, year: int, month: int) -> List[date]:
        """
        获取指定月份的故障日期
        
        Args:
            year: 年份
            month: 月份
            
        Returns:
            List[date]: 该月份的故障日期列表
        """
        try:
            month_fault_dates = []
            for fault_date in self.fault_dates:
                if fault_date.year == year and fault_date.month == month:
                    month_fault_dates.append(fault_date)
            
            return month_fault_dates
            
        except Exception as e:
            logger.error(f"获取月份故障日期失败: {e}")
            return []
    
    def refresh_display(self):
        """刷新显示"""
        try:
            self._update_calendar_display()
            logger.debug("刷新日历显示")
            
        except Exception as e:
            logger.error(f"刷新日历显示失败: {e}")


# 使用示例
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget
    from datetime import datetime, timedelta
    
    app = QApplication(sys.argv)
    
    # 创建测试窗口
    window = QWidget()
    layout = QVBoxLayout(window)
    
    # 创建故障日历选择器
    calendar = FaultCalendarPicker()
    layout.addWidget(calendar)
    
    # 添加一些测试故障日期
    today = date.today()
    test_dates = [
        today,
        today - timedelta(days=1),
        today - timedelta(days=3),
        today - timedelta(days=7),
    ]
    calendar.set_fault_dates(test_dates)
    
    # 连接日期变化信号
    calendar.dateChanged.connect(lambda d: print(f"选择日期: {d.toString('yyyy-MM-dd')}"))
    
    window.show()
    sys.exit(app.exec_())
