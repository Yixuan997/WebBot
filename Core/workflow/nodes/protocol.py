"""
协议相关节点
"""
from .base import BaseNode


class ProtocolCheckNode(BaseNode):
    """协议检查节点 - 检查当前协议类型"""

    name = "协议检查"
    description = "检查当前使用的协议类型"
    category = "logic"
    icon = "🔌"

    inputs = []
    outputs = [
        {'name': 'protocol', 'label': 'protocol - 协议名称', 'type': 'string'},
        {'name': 'is_qq', 'label': 'is_qq - 是否QQ官方', 'type': 'boolean'},
        {'name': 'is_onebot', 'label': 'is_onebot - 是否OneBot', 'type': 'boolean'},
    ]

    config_schema = [
        {
            'name': 'target_protocol',
            'label': '目标协议',
            'type': 'select',
            'options': [
                {'value': 'qq', 'label': 'QQ官方协议'},
                {'value': 'onebot', 'label': 'OneBot协议'},
            ],
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
        context.set_variable('is_qq', protocol == 'qq')
        context.set_variable('is_onebot', protocol == 'onebot')

        # 如果配置了目标协议，检查是否匹配
        target_protocol = self.config.get('target_protocol')
        if target_protocol:
            match = protocol == target_protocol
            return {'success': True, 'protocol': protocol, 'match': match}

        return {'success': True, 'protocol': protocol}
