"""
协议相关节点
"""
from Adapters import get_adapter_manager

from .base import BaseNode


def _get_protocol_options():
    manager = get_adapter_manager()
    options = []
    for protocol, adapter_class in manager.adapters.items():
        options.append({
            'value': protocol,
            'label': adapter_class.get_display_name()
        })
    return options


def _get_protocol_outputs():
    manager = get_adapter_manager()
    outputs = [
        {'name': 'protocol', 'label': 'protocol - 协议名称', 'type': 'string'},
    ]
    for protocol in manager.adapters.keys():
        outputs.append({
            'name': f'is_{protocol}',
            'label': f'is_{protocol} - 是否{protocol}',
            'type': 'boolean'
        })
    return outputs


class ProtocolCheckNode(BaseNode):
    """协议检查节点 - 检查当前协议类型"""

    name = "协议检查"
    description = "检查当前使用的协议类型"
    category = "logic"
    icon = ""

    inputs = []
    outputs = _get_protocol_outputs()

    config_schema = [
        {
            'name': 'target_protocol',
            'label': '目标协议',
            'type': 'select',
            'options': _get_protocol_options(),
            'required': False,
            'help': '选择要检查的协议（可选）'
        },
        {
            'name': 'next_node',
            'label': '下一个节点',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '协议检查后跳转到的节点'
        },
    ]

    def _execute(self, context):
        """执行协议检查"""
        # 获取当前协议
        protocol = context.event.bot.adapter.get_protocol_name()

        # 保存到上下文
        context.set_variable('protocol', protocol)
        manager = get_adapter_manager()
        for protocol_id in manager.adapters.keys():
            context.set_variable(f'is_{protocol_id}', protocol == protocol_id)

        # 如果配置了目标协议，检查是否匹配
        target_protocol = self.config.get('target_protocol')
        if target_protocol:
            match = protocol == target_protocol
            return {'success': True, 'protocol': protocol, 'match': match}

        return {'success': True, 'protocol': protocol}
