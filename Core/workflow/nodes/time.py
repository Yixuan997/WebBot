"""
时间和延迟相关节点
"""
import time
from datetime import datetime
from typing import Any

from .base import BaseNode


class DelayNode(BaseNode):
    """延迟节点"""

    name = "延迟等待"
    description = "暂停指定时间后继续执行"
    category = "time"
    icon = "⏱️"

    inputs = []
    outputs = []

    config_schema = [
        {
            'name': 'delay_seconds',
            'label': '延迟时间(秒)',
            'type': 'text',
            'required': True,
            'default': '1',
            'placeholder': '1',
            'help': '暂停的秒数,支持小数如0.5'
        },
        {
            'name': 'next_node',
            'label': '下一个节点',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '延迟完成后跳转到的节点'
        },
    ]

    def _execute(self, context):
        """
        执行延迟
        
        Args:
            context: WorkflowContext
            
        Returns:
            dict: 执行结果
        """
        delay_str = self.config.get('delay_seconds', '1')

        try:
            delay_seconds = float(delay_str)
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            return {'success': True, 'delayed': delay_seconds}
        except ValueError:
            return {'success': False, 'error': 'Invalid delay value'}


class ScheduleCheckNode(BaseNode):
    """时间段检查节点"""

    name = "时间段检查"
    description = "检查当前时间是否在指定时间段内"
    category = "time"
    icon = "🕒"

    inputs = []
    outputs = [
        {'name': 'in_schedule', 'label': 'in_schedule - 是否在时间段内', 'type': 'boolean'},
        {'name': 'current_time', 'label': 'current_time - 当前时间', 'type': 'string'},
    ]

    config_schema = [
        {
            'name': 'start_time',
            'label': '开始时间',
            'type': 'text',
            'required': True,
            'placeholder': '09:00',
            'help': '时间格式: HH:MM (如09:00)'
        },
        {
            'name': 'end_time',
            'label': '结束时间',
            'type': 'text',
            'required': True,
            'placeholder': '18:00',
            'help': '时间格式: HH:MM (如18:00)'
        },
        {
            'name': 'weekdays_only',
            'label': '只在工作日生效',
            'type': 'checkbox',
            'default': False,
            'help': '勾选后周六日不触发'
        },
        {
            'name': 'next_node',
            'label': '下一个节点',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '时间段检查后跳转到的节点'
        },
    ]

    async def _execute(self, context) -> dict[str, Any]:
        """
        检查时间段
        
        Args:
            context: WorkflowContext
            
        Returns:
            dict: 执行结果
        """
        start_time_str = self.config.get('start_time', '00:00')
        end_time_str = self.config.get('end_time', '23:59')
        weekdays_only = self.config.get('weekdays_only', False)

        now = datetime.now()
        current_time_str = now.strftime('%H:%M:%S')

        # 检查是否是工作日
        if weekdays_only:
            weekday = now.weekday()  # 0=Monday, 6=Sunday
            if weekday >= 5:  # 周六日
                context.set_variable('in_schedule', False)
                context.set_variable('current_time', current_time_str)
                return {'success': True, 'in_schedule': False, 'reason': 'weekend'}

        # 解析时间
        try:
            start_hour, start_min = map(int, start_time_str.split(':'))
            end_hour, end_min = map(int, end_time_str.split(':'))

            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min

            # 检查是否在时间段内
            in_schedule = start_minutes <= current_minutes <= end_minutes

            context.set_variable('in_schedule', in_schedule)
            context.set_variable('current_time', current_time_str)

            return {'success': True, 'in_schedule': in_schedule}

        except (ValueError, AttributeError) as e:
            context.set_variable('in_schedule', False)
            context.set_variable('current_time', current_time_str)
            return {'success': False, 'error': str(e)}


class TimestampNode(BaseNode):
    """时间戳节点"""

    name = "获取时间"
    description = "获取当前时间和时间戳"
    category = "time"
    icon = "📅"

    inputs = []
    outputs = [
        {'name': 'timestamp', 'label': 'timestamp - Unix时间戳', 'type': 'integer'},
        {'name': 'datetime', 'label': 'datetime - 日期时间', 'type': 'string'},
        {'name': 'date', 'label': 'date - 日期', 'type': 'string'},
        {'name': 'time', 'label': 'time - 时间', 'type': 'string'},
        {'name': 'year', 'label': 'year - 年份', 'type': 'integer'},
        {'name': 'month', 'label': 'month - 月份', 'type': 'integer'},
        {'name': 'day', 'label': 'day - 日期', 'type': 'integer'},
        {'name': 'hour', 'label': 'hour - 小时', 'type': 'integer'},
        {'name': 'minute', 'label': 'minute - 分钟', 'type': 'integer'},
        {'name': 'weekday', 'label': 'weekday - 星期几', 'type': 'string'},
    ]

    config_schema = [
        {
            'name': 'format',
            'label': '日期格式',
            'type': 'select',
            'options': [
                {'value': '%Y-%m-%d %H:%M:%S', 'label': '2024-01-01 12:00:00'},
                {'value': '%Y/%m/%d %H:%M:%S', 'label': '2024/01/01 12:00:00'},
                {'value': '%Y年%m月%d日 %H:%M:%S', 'label': '2024年01月01日 12:00:00'},
                {'value': '%Y-%m-%d', 'label': '2024-01-01'},
                {'value': '%H:%M:%S', 'label': '12:00:00'},
            ],
            'default': '%Y-%m-%d %H:%M:%S',
            'required': False,
            'help': '时间显示格式'
        },
        {
            'name': 'next_node',
            'label': '下一个节点',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '获取时间后跳转到的节点'
        },
    ]

    async def _execute(self, context) -> dict[str, Any]:
        """
        获取时间信息
        
        Args:
            context: WorkflowContext
            
        Returns:
            dict: 执行结果
        """
        date_format = self.config.get('format', '%Y-%m-%d %H:%M:%S')

        now = datetime.now()

        # 星期几
        weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        weekday = weekdays[now.weekday()]

        # 保存各种时间格式
        context.set_variable('timestamp', int(now.timestamp()))
        context.set_variable('datetime', now.strftime(date_format))
        context.set_variable('date', now.strftime('%Y-%m-%d'))
        context.set_variable('time', now.strftime('%H:%M:%S'))
        context.set_variable('year', now.year)
        context.set_variable('month', now.month)
        context.set_variable('day', now.day)
        context.set_variable('hour', now.hour)
        context.set_variable('minute', now.minute)
        context.set_variable('weekday', weekday)

        return {'success': True}
