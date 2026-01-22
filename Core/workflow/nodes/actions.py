"""
动作节点

执行具体操作，如发送消息、调用API等
"""
from Core.message.builder import MessageBuilder
from .base import BaseNode


class SendMessageNode(BaseNode):
    """发送消息节点 - 支持协议选择"""

    name = "发送消息"
    description = "发送消息给用户"
    category = "action"
    icon = "📤"

    # 输入输出
    inputs = [
        {'name': 'content', 'label': '消息内容', 'required': False, 'type': 'string'},
    ]
    outputs = []  # 发送消息不产生输出变量

    # 协议支持表
    PROTOCOL_SUPPORT = {
        'text': ['qq', 'onebot'],
        'image': ['qq', 'onebot'],
        'video': ['qq', 'onebot'],
        'voice': ['qq', 'onebot'],
        'file': ['qq'],  # OneBot 需用自定义端点 upload_group_file
        'markdown': ['qq'],
        'ark': ['qq']
    }

    config_schema = [
        {
            'name': 'message_type',
            'label': '消息类型',
            'type': 'select',
            'required': True,
            'default': 'text',
            'options': [
                {'value': 'text', 'label': '文本 ✅ 所有协议'},
                {'value': 'image', 'label': '图片 ✅ 所有协议'},
                {'value': 'video', 'label': '视频 ✅ 所有协议'},
                {'value': 'voice', 'label': '语音 ✅ 所有协议'},
                {'value': 'file', 'label': '文件 ⚠️ 仅QQ官方'},
                {'value': 'markdown', 'label': 'Markdown/按钮 ⚠️ 仅QQ官方'},
                {'value': 'ark', 'label': 'ARK模板 ⚠️ 仅QQ官方'}
            ]
        },
        {
            'name': 'content',
            'label': '消息内容',
            'type': 'textarea',
            'required': True,
            'placeholder': '支持变量：{{variable}}\\n支持内置变量：{{user_id}}, {{message}}, {{protocol}}',
            'rows': 5
        },
        {
            'name': 'markdown_template_id',
            'label': 'Markdown模板ID',
            'type': 'text',
            'required': False,
            'default': '',
            'placeholder': '留空使用原生Markdown（仅频道）',
            'help': 'QQ群/私聊需要填写模板ID。填写后，内容使用JSON格式：{"size": "![text #100px #100px]", "title": "标题"}',
            'show_if': {'message_type': 'markdown'}
        },
        {
            'name': 'keyboard_id',
            'label': '按钮ID',
            'type': 'text',
            'required': False,
            'default': '',
            'placeholder': '留空则不发送按钮',
            'help': '在QQ开放平台申请的按钮模板ID，可与Markdown模板配合使用',
            'show_if': {'message_type': 'markdown'}
        },
        {
            'name': 'ark_template_id',
            'label': 'ARK模板ID',
            'type': 'text',
            'required': True,
            'default': '24',
            'placeholder': '如 23, 24, 37',
            'help': '常用模板: 23=文卡, 24=链接卡片, 37=大图',
            'show_if': {'message_type': 'ark'}
        },
        {
            'name': 'skip_if_unsupported',
            'label': '协议不支持时跳过',
            'type': 'checkbox',
            'default': True,
            'help': '如果当前协议不支持该消息类型，跳过此步骤而不是报错'
        },
        {
            'name': 'next_node',
            'label': '执行后跳转到',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '选择下一个要执行的节点（留空则顺序执行）'
        }
    ]

    async def _execute(self, context):
        """执行发送消息"""
        msg_type = self.config['message_type']
        protocol = context.event.bot.adapter.get_protocol_name()

        # 1. 检查协议是否支持
        if protocol not in self.PROTOCOL_SUPPORT.get(msg_type, []):
            if self.config.get('skip_if_unsupported', False):
                # 跳过此步骤
                return None
            else:
                # 抛出错误
                raise ValueError(
                    f"当前协议 '{protocol}' 不支持消息类型 '{msg_type}'"
                )

        # 2. 渲染内容
        content = context.render_template(self.config['content'])

        # 3. 根据类型构建消息 (使用 match-case, Python 3.10+)
        event = context.event
        try:
            match msg_type:
                case 'text':
                    message = MessageBuilder.text(content, event=event)
                case 'image':
                    message = MessageBuilder.image(content, event=event)
                case 'video':
                    message = MessageBuilder.video(content, event=event)
                case 'voice':
                    message = MessageBuilder.voice(content, event=event)
                case 'file':
                    message = MessageBuilder.file(content, event=event)
                case 'markdown':
                    template_id = self.config.get('markdown_template_id', '').strip()
                    keyboard_id = self.config.get('keyboard_id', '').strip()
                    message = MessageBuilder.markdown(content, template_id=template_id, keyboard_id=keyboard_id,
                                                      event=event)
                case 'ark':
                    ark_template_id = int(self.config.get('ark_template_id', '24'))
                    message = MessageBuilder.ark(content, template_id=ark_template_id, event=event)
                case _:
                    message = MessageBuilder.text(content, event=event)

            # 4. 设置响应（不再标记 _handled，由 end 节点统一处理）
            context._response = message

            # 5. 处理跳转
            result = {'success': True}
            if self.config.get('next_node'):
                result['next_node'] = self.config['next_node']

            return result

        except Exception as e:
            # 发送失败
            raise ValueError(f"构建消息失败: {e}")
