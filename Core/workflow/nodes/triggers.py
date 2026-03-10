"""
触发器节点 - 用于工作流的触发条件
"""
from typing import Any

from .base import BaseNode


class KeywordTriggerNode(BaseNode):
    """关键词触发节点"""

    name = "关键词触发"
    description = "检查消息是否包含特定关键词"
    category = "trigger"
    icon = "🔑"

    inputs = []
    outputs = [
        {'name': 'matched', 'label': 'matched - 是否匹配', 'type': 'boolean'},
        {'name': 'keyword', 'label': 'keyword - 匹配的关键词', 'type': 'string'},
    ]

    config_schema = [
        {
            'name': 'keywords',
            'label': '关键词列表',
            'type': 'textarea',
            'required': True,
            'placeholder': '你好\n查询\nhelp',
            'help': '每行一个关键词，匹配任一即触发',
            'rows': 5
        },
        {
            'name': 'match_type',
            'label': '匹配类型',
            'type': 'select',
            'default': 'contains',
            'options': [
                {'value': 'contains', 'label': '包含'},
                {'value': 'equals', 'label': '完全匹配'},
                {'value': 'starts_with', 'label': '开头匹配'},
            ]
        },
        {
            'name': 'next_node',
            'label': '下一个节点',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '匹配通过后跳转到的节点'
        },
    ]

    async def _execute(self, context):
        """执行关键词检查"""
        keywords_text = self.config.get('keywords', '')
        match_type = self.config.get('match_type', 'contains')

        # 解析关键词列表
        keywords = [k.strip() for k in keywords_text.split('\n') if k.strip()]

        # 获取消息内容
        message = context.get_variable('message', '')

        # 检查匹配
        matched_keyword = None
        for keyword in keywords:
            if match_type == 'contains' and keyword in message:
                matched_keyword = keyword
                break
            elif match_type == 'equals' and keyword == message:
                matched_keyword = keyword
                break
            elif match_type == 'starts_with' and message.startswith(keyword):
                matched_keyword = keyword
                break

        # 保存结果
        matched = matched_keyword is not None
        context.set_variable('matched', matched)
        context.set_variable('keyword', matched_keyword or '')

        return {
            'success': True,
            'matched': matched,
            'keyword': matched_keyword
        }

    def should_break(self, result: Any) -> bool:
        """如果不匹配，则中断流程"""
        # result 是 execute 的返回值字典
        if isinstance(result, dict):
            return not result.get('matched', False)
        return False
