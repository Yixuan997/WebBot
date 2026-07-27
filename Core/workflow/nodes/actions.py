"""
动作节点

执行具体操作，如发送消息、调用API等
"""
import json

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

    config_schema = [
        {
            'name': 'message_type',
            'label': '消息类型',
            'type': 'select',
            'required': True,
            'default': 'text',
            'options': [
                {'value': 'text', 'label': '文本'},
                {'value': 'image', 'label': '图片'},
                {'value': 'video', 'label': '视频'},
                {'value': 'voice', 'label': '语音'},
                {'value': 'file', 'label': '文件'},
                {'value': 'markdown', 'label': 'Markdown/按钮'},
                {'value': 'ark', 'label': 'ARK模板'}
            ]
        },
        {
            'name': 'content',
            'label': '消息内容',
            'type': 'textarea',
            'required': True,
            'placeholder': '支持变量：{{variable}}\\n支持内置变量：{{sender.user_id}}, {{message}}, {{protocol}}',
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
            'name': 'keyboard_content',
            'label': '自定义按钮JSON',
            'type': 'textarea',
            'required': False,
            'default': '',
            'rows': 8,
            'placeholder': '{"rows":[{"buttons":[{"id":"1","render_data":{"label":"按钮1","visited_label":"已点击"},"action":{"type":2,"data":"/搜索"}}]}],"bot_appid":123123123}',
            'help': 'QQ Markdown 可选：自定义 keyboard.content JSON。填写后优先于按钮ID发送。',
            'show_if': {'message_type': 'markdown'}
        },
        {
            'name': 'button_text',
            'label': '按钮文字',
            'type': 'text',
            'required': False,
            'default': '',
            'placeholder': '例如：点击查看',
            'help': 'QQ Markdown 按钮简写。若填写自定义按钮JSON，则优先使用自定义JSON。',
            'show_if': {'message_type': 'markdown'}
        },
        {
            'name': 'button_link',
            'label': '按钮链接',
            'type': 'text',
            'required': False,
            'default': '',
            'placeholder': 'https://example.com',
            'help': '按钮跳转链接，支持变量。',
            'show_if': {'message_type': 'markdown'}
        },
        {
            'name': 'button_data',
            'label': '按钮指令',
            'type': 'text',
            'required': False,
            'default': '',
            'placeholder': '/菜单',
            'help': '不填按钮链接时可填写指令数据。',
            'show_if': {'message_type': 'markdown'}
        },
        {
            'name': 'button_style',
            'label': '按钮样式',
            'type': 'select',
            'required': False,
            'default': '1',
            'options': [
                {'value': '0', 'label': '灰色'},
                {'value': '1', 'label': '蓝色'}
            ],
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
            'name': 'ark_preset',
            'label': 'ARK预设',
            'type': 'select',
            'required': False,
            'default': 'custom',
            'options': [
                {'value': 'custom', 'label': '自定义JSON'},
                {'value': 'text_card', 'label': '文卡 23'},
                {'value': 'link_card', 'label': '链接卡片 24'},
                {'value': 'large_image', 'label': '大图 37'}
            ],
            'help': '选择预设后，可用下方字段生成 ARK kv，无需手写 JSON。',
            'show_if': {'message_type': 'ark'}
        },
        {
            'name': 'ark_title',
            'label': 'ARK标题',
            'type': 'text',
            'required': False,
            'default': '',
            'show_if': {'message_type': 'ark'}
        },
        {
            'name': 'ark_description',
            'label': 'ARK描述',
            'type': 'textarea',
            'required': False,
            'default': '',
            'rows': 3,
            'show_if': {'message_type': 'ark'}
        },
        {
            'name': 'ark_url',
            'label': 'ARK链接',
            'type': 'text',
            'required': False,
            'default': '',
            'show_if': {'message_type': 'ark'}
        },
        {
            'name': 'ark_image',
            'label': 'ARK图片',
            'type': 'text',
            'required': False,
            'default': '',
            'placeholder': 'https://example.com/cover.png',
            'show_if': {'message_type': 'ark'}
        },
        {
            'name': 'ark_prompt',
            'label': 'ARK提示',
            'type': 'text',
            'required': False,
            'default': '',
            'placeholder': '显示在消息列表中的提示',
            'show_if': {'message_type': 'ark'}
        },
        {
            'name': 'ark_button_text',
            'label': 'ARK按钮文字',
            'type': 'text',
            'required': False,
            'default': '',
            'help': '文卡 23 可用，用于生成第二行可点击链接。',
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
            'help': '选择下一个要执行的节点（留空则终止当前流程）'
        }
    ]

    @staticmethod
    def _json_dump(data: dict) -> str:
        return json.dumps(data, ensure_ascii=False)

    def _build_keyboard_content(self, context) -> str:
        """优先使用高级 JSON；未填写时使用按钮简写字段生成。"""
        keyboard_content = context.render_template(self.config.get('keyboard_content', '')).strip()
        if keyboard_content:
            return keyboard_content

        text = context.render_template(self.config.get('button_text', '')).strip()
        link = context.render_template(self.config.get('button_link', '')).strip()
        data = context.render_template(self.config.get('button_data', '')).strip()
        if not text or not (link or data):
            return ""

        payload = {
            "text": text,
            "style": self.config.get('button_style', '1')
        }
        if link:
            payload["link"] = link
        else:
            payload["data"] = data
        return self._json_dump(payload)

    def _build_ark_content(self, context, content: str) -> tuple[str, int]:
        """根据 ARK 预设生成 JSON 对象；custom 时保留原内容。"""
        preset = self.config.get('ark_preset', 'custom')
        template_id = int(self.config.get('ark_template_id', '24'))
        if preset == 'text_card':
            template_id = 23
        elif preset == 'link_card':
            template_id = 24
        elif preset == 'large_image':
            template_id = 37

        if preset == 'custom':
            return content, template_id

        data = {
            "title": context.render_template(self.config.get('ark_title', '')).strip(),
            "description": context.render_template(self.config.get('ark_description', '')).strip() or content,
            "url": context.render_template(self.config.get('ark_url', '')).strip(),
            "image": context.render_template(self.config.get('ark_image', '')).strip(),
            "prompt": context.render_template(self.config.get('ark_prompt', '')).strip(),
            "button_text": context.render_template(self.config.get('ark_button_text', '')).strip(),
        }
        return self._json_dump(data), template_id

    async def _execute(self, context):
        """执行发送消息"""
        msg_type = self.config['message_type']
        adapter = context.event.bot.adapter
        protocol = adapter.get_protocol_name()

        # 1. 检查协议是否支持
        if not adapter.supports_message_type(msg_type):
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
                    keyboard_content = self._build_keyboard_content(context)
                    if keyboard_content:
                        try:
                            parsed = json.loads(keyboard_content)
                            if not isinstance(parsed, dict):
                                raise ValueError("keyboard_content 必须是 JSON 对象")
                            if not (
                                isinstance(parsed.get('rows'), list) or
                                ('text' in parsed and ('link' in parsed or 'data' in parsed))
                            ):
                                raise ValueError("keyboard_content 需为官方 keyboard.content（含 rows）或简写格式（含 text/link 或 text/data）")
                        except Exception as e:
                            raise ValueError(f"自定义按钮JSON格式错误: {e}")
                    message = MessageBuilder.markdown(
                        content,
                        template_id=template_id,
                        keyboard_id=keyboard_id,
                        keyboard_content=keyboard_content,
                        event=event
                    )
                case 'ark':
                    ark_content, ark_template_id = self._build_ark_content(context, content)
                    message = MessageBuilder.ark(ark_content, template_id=ark_template_id, event=event)
                case _:
                    message = MessageBuilder.text(content, event=event)

            # 4. 设置响应；没有后续节点时由引擎结束流程。
            context._response = message

            # 5. 处理跳转
            result = {'success': True}
            if self.config.get('next_node'):
                result['next_node'] = self.config['next_node']

            return result

        except Exception as e:
            # 发送失败
            raise ValueError(f"构建消息失败: {e}")
