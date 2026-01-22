"""
工作流开始和结束节点
"""
from typing import Any

from .base import BaseNode


class StartNode(BaseNode):
    """开始节点 - 自动提取事件字段"""

    name = "开始"
    description = "工作流开始,提取事件字段"
    category = "core"
    icon = "▶️"

    # 输入输出
    inputs = []  # 开始节点无需输入
    outputs = [
        {'name': 'event', 'label': 'event - 完整事件对象', 'type': 'object'},
        {'name': 'post_type', 'label': 'post_type - 事件类型 (message/notice/request)', 'type': 'string'},
        {'name': 'message', 'label': 'message - 消息内容(纯文本)', 'type': 'string'},
        {'name': 'message_full', 'label': 'message_full - 完整消息对象', 'type': 'object'},
        {'name': 'message_type', 'label': 'message_type - 消息类型 (text/image/voice)', 'type': 'string'},
        {'name': 'has_image', 'label': 'has_image - 是否包含图片', 'type': 'boolean'},
        {'name': 'has_at', 'label': 'has_at - 是否包含@', 'type': 'boolean'},
        {'name': 'sender.user_id', 'label': 'sender.user_id - 发送者ID', 'type': 'string'},
        {'name': 'sender.nickname', 'label': 'sender.nickname - 发送者昵称', 'type': 'string'},
        {'name': 'sender', 'label': 'sender - 完整sender对象', 'type': 'object'},
        {'name': 'group_id', 'label': 'group_id - 群ID (仅群聊)', 'type': 'string'},
        {'name': 'message_id', 'label': 'message_id - 消息ID', 'type': 'string'},
        {'name': 'is_group', 'label': 'is_group - 是否群聊', 'type': 'boolean'},
        {'name': 'protocol', 'label': 'protocol - 协议类型 (qq/onebot)', 'type': 'string'},
        {'name': 'bot_id', 'label': 'bot_id - 机器人QQ号', 'type': 'string'},
    ]

    config_schema = []  # 开始节点不需要配置

    async def _execute(self, context) -> dict[str, Any]:
        """
        执行开始节点 - 提取事件字段到上下文
        
        Args:
            context: WorkflowContext
            
        Returns:
            dict: 执行结果
        """
        event = context.event
        
        # 保存完整事件对象（脚本可以直接从 event 取任何字段）
        context.set_variable('event', event)
        context.set_variable('post_type', getattr(event, 'post_type', 'message'))

        # 提取消息内容和类型
        message_text = ""
        message_type = "text"
        has_image = False
        has_at = False

        if hasattr(event, 'message') and event.message:
            # 使用extract_plain_text方法提取纯文本
            if hasattr(event.message, 'extract_plain_text'):
                message_text = event.message.extract_plain_text()
            elif hasattr(event.message, 'content'):
                message_text = event.message.content
            else:
                # 备用方案:直接转字符串
                message_text = str(event.message)

            # 检测消息类型
            if hasattr(event.message, '__iter__'):
                for segment in event.message:
                    if hasattr(segment, 'type'):
                        if segment.type == 'image':
                            has_image = True
                            if not message_text:  # 如果没有文本,标记为图片消息
                                message_type = "image"
                        elif segment.type == 'at':
                            has_at = True
                        elif segment.type == 'record':
                            message_type = "voice"
                        elif segment.type == 'video':
                            message_type = "video"

        # 提取发送者信息
        user_id = getattr(event, 'user_id', '')
        sender_obj = getattr(event, 'raw_data', {}).get('sender', {})
        sender_name = sender_obj.get('nickname', '') or sender_obj.get('card', '')

        # 提取群组信息
        group_id = getattr(event, 'group_id', None) or ""
        is_group = bool(group_id)

        # 提取消息ID
        message_id = getattr(event, 'message_id', '')

        # 获取协议类型和机器人ID
        protocol = "unknown"
        bot_id = ""
        if hasattr(event, 'bot') and hasattr(event.bot, 'adapter'):
            protocol = event.bot.adapter.get_protocol_name()
            bot_id = getattr(event.bot, 'self_id', '')

        # 获取原始消息（包含 CQ 码）
        raw_message = getattr(event, 'raw_message', '') or str(getattr(event, 'message', ''))
        
        # 保存到上下文
        context.set_variable('message', message_text)
        context.set_variable('raw_message', raw_message)  # 原始消息（包含 CQ 码）
        context.set_variable('message_full', getattr(event, 'message', None))  # 完整消息对象
        context.set_variable('message_type', message_type)
        context.set_variable('has_image', has_image)
        context.set_variable('has_at', has_at)

        # 发送者信息（同时支持旧格式 user_id 和新格式 sender.user_id）
        context.set_variable('user_id', str(user_id))  # 兼容旧版
        context.set_variable('sender.user_id', str(user_id))
        context.set_variable('sender.nickname', sender_name)
        if sender_obj:
            context.set_variable('sender', sender_obj)  # 完整sender对象

        context.set_variable('group_id', str(group_id))
        context.set_variable('sender_name', sender_name)  # 兼容旧版
        context.set_variable('message_id', str(message_id))
        context.set_variable('is_group', is_group)
        context.set_variable('protocol', protocol)  # 协议类型
        context.set_variable('bot_id', str(bot_id))  # 机器人QQ号

        return {
            'success': True,
            'extracted_fields': {
                'message': message_text,
                'user_id': user_id,
                'group_id': group_id,
                'sender_name': sender_name,
                'is_group': is_group,
            }
        }


class EndNode(BaseNode):
    """结束节点 - 标记工作流结束"""

    name = "结束"
    description = "工作流结束"
    category = "core"
    icon = "⏹️"

    # 输入输出
    inputs = []
    outputs = []

    config_schema = [
        {
            'name': 'allow_continue',
            'label': '允许继续执行',
            'type': 'checkbox',
            'default': True,
            'help': '工作流结束后是否允许后续其他工作流继续匹配处理该消息'
        }
    ]

    async def _execute(self, context) -> dict[str, Any]:
        """
        执行结束节点
        
        Args:
            context: WorkflowContext
            
        Returns:
            dict: 执行结果
        """
        # End 节点只负责中断执行，不设置任何标记
        # 是否处理由 engine 根据 response 判断
        return {
            'success': True
        }

    def should_break(self, result: dict[str, Any]) -> bool:
        """结束节点总是中断当前工作流"""
        return True
