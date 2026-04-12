"""
消息构建器 - 为插件开发者提供便捷的消息构建方法

这个模块提供了统一的消息构建接口，支持多种消息类型：
- 文本消息
- 图片消息
- Markdown消息
- Ark卡片消息
- 带按钮的消息（需要申请）
- 大图消息（模板37）
- 文卡消息（模板23）
- 链接卡片（模板24）

使用示例：
    # 文本消息
    text_msg = MessageBuilder.text("Hello World!")

    # 图片消息（URL方式）
    image_msg = MessageBuilder.image("https://example.com/image.jpg", "图片描述")

    # 图片消息（Base64方式）
    image_msg = MessageBuilder.image(caption="图片描述", base64_data="iVBORw0KGgo...")

    # Markdown消息
    md_msg = MessageBuilder.markdown("# 标题\n**粗体文本**")

    # 卡片消息
    card_msg = MessageBuilder.card("卡片标题", "卡片内容")

    # 带按钮的消息（需要申请）
    button_msg = MessageBuilder.button_card("标题", "内容", [{"text": "按钮", "data": "callback"}])

    # 大图消息（模板37）
    large_img = MessageBuilder.large_image("美图分享", "今日推荐", "https://example.com/large.jpg")

    # 文卡消息（模板23）
    text_card = MessageBuilder.text_card("这是文卡内容", "描述文字", "提示文字")

    # 链接卡片（模板24）
    link_card = MessageBuilder.link_card("文章标题", "文章描述", "https://example.com")
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Adapters.base import BaseEvent
    from Adapters.base.message import BaseMessage


class MessageBuilder:
    """
    消息构建器 - 按照 NoneBot2 设计理念
    
    根据 event 自动返回对应协议的 Message 对象
    必须在事件上下文中调用
    """

    # 线程局部变量，存储当前 event
    _current_event = None

    @classmethod
    def set_current_event(cls, event: 'BaseEvent'):
        """设置当前事件（由框架调用）"""
        cls._current_event = event

    @classmethod
    def clear_current_event(cls):
        """清除当前事件"""
        cls._current_event = None

    @classmethod
    def text(cls, content: str, event: 'BaseEvent' = None) -> 'BaseMessage':
        """
        构建文本消息

        Args:
            content: 文本内容
            event: 事件对象（可选，会自动从线程局部获取）

        Returns:
            协议特定的 Message 对象
        """
        event = event or cls._current_event

        if not event or not hasattr(event, 'bot'):
            raise RuntimeError("必须在事件上下文中调用 MessageBuilder")

        adapter = event.bot.adapter
        return adapter.build_message('text', content=content)

    @classmethod
    def image(cls, image_url_or_file_info: str = "", caption: str = "", auto_upload: bool = True,
              base64_data: str = None, event: 'BaseEvent' = None) -> 'BaseMessage':
        """
        构建图片消息

        Args:
            image_url_or_file_info: 图片URL或已上传的file_info
            caption: 图片说明文字（可选）
            auto_upload: 是否自动上传
            base64_data: base64编码的图片数据
            event: 事件对象（可选）

        Returns:
            协议特定的 Message 对象
        """
        event = event or cls._current_event

        if not event or not hasattr(event, 'bot'):
            raise RuntimeError("必须在事件上下文中调用 MessageBuilder")

        adapter = event.bot.adapter
        return adapter.build_message(
            'image',
            image_url_or_file_info=image_url_or_file_info,
            caption=caption,
            auto_upload=auto_upload,
            base64_data=base64_data
        )

    @classmethod
    def video(cls, video_url: str, caption: str = "", event: 'BaseEvent' = None) -> 'BaseMessage':
        """
        构建视频消息

        Args:
            video_url: 视频URL
            caption: 视频说明文字（可选）
            event: 事件对象（可选）

        Returns:
            协议特定的 Message 对象
        """
        event = event or cls._current_event

        if not event or not hasattr(event, 'bot'):
            raise RuntimeError("必须在事件上下文中调用 MessageBuilder")

        adapter = event.bot.adapter
        return adapter.build_message('video', video_url=video_url, caption=caption)

    @classmethod
    def voice(cls, voice_url: str, event: 'BaseEvent' = None) -> 'BaseMessage':
        """
        构建语音消息

        Args:
            voice_url: 语音URL
            event: 事件对象（可选）

        Returns:
            协议特定的 Message 对象
        """
        event = event or cls._current_event

        if not event or not hasattr(event, 'bot'):
            raise RuntimeError("必须在事件上下文中调用 MessageBuilder")

        adapter = event.bot.adapter
        return adapter.build_message('voice', voice_url=voice_url)

    @classmethod
    def file(cls, file_url: str, filename: str = "", event: 'BaseEvent' = None) -> 'BaseMessage':
        """
        构建文件消息

        Args:
            file_url: 文件URL
            filename: 文件名（可选）
            event: 事件对象（可选）

        Returns:
            协议特定的 Message 对象
        """
        event = event or cls._current_event

        if not event or not hasattr(event, 'bot'):
            raise RuntimeError("必须在事件上下文中调用 MessageBuilder")

        adapter = event.bot.adapter
        if adapter.supports_message_type('file'):
            return adapter.build_message('file', file_url=file_url, filename=filename)
        # 协议不支持文件时统一降级为文本提示
        return adapter.build_message('text', content=f"[文件] {filename or file_url}")

    @classmethod
    def markdown(cls, content: str, template_id: str = "", keyboard_id: str = "",
                 event: 'BaseEvent' = None) -> 'BaseMessage':
        """
        构建 Markdown消息
        
        支持两种模式：
        1. 原生Markdown（仅频道支持）- 不传template_id
        2. 模板Markdown（群/私聊）- 传入在QQ开放平台申请的模板ID

        Args:
            content: Markdown格式的内容，模板模式下使用 {{key}} 占位符
            template_id: 模板ID（群/私聊必填，频道可留空）
            keyboard_id: 按钮模板ID（可选，不为空则发送按钮）
            event: 事件对象（可选）

        Returns:
            协议特定的 Message 对象
            
        Raises:
            ValueError: 如果当前协议不支持 Markdown
        """
        event = event or cls._current_event

        if not event or not hasattr(event, 'bot'):
            raise RuntimeError("必须在事件上下文中调用 MessageBuilder")

        adapter = event.bot.adapter
        if not adapter.supports_message_type('markdown'):
            protocol = adapter.get_protocol_name()
            raise ValueError(f"协议 '{protocol}' 不支持 Markdown 消息，请使用 text() 方法")
        return adapter.build_message('markdown', content=content, template_id=template_id, keyboard_id=keyboard_id)

    @classmethod
    def keyboard(cls, content: str, keyboard_id: str, event: 'BaseEvent' = None) -> 'BaseMessage':
        """
        构建按钮卡片消息（文本 + 按钮）
        
        Args:
            content: 按钮上方的文本内容
            keyboard_id: 在QQ开放平台申请的按钮模板ID
            event: 事件对象（可选）

        Returns:
            协议特定的 Message 对象
            
        Raises:
            ValueError: 如果当前协议不支持按钮
        """
        event = event or cls._current_event

        if not event or not hasattr(event, 'bot'):
            raise RuntimeError("必须在事件上下文中调用 MessageBuilder")

        adapter = event.bot.adapter
        try:
            return adapter.build_message('keyboard', content=content, keyboard_id=keyboard_id)
        except ValueError:
            protocol = adapter.get_protocol_name()
            raise ValueError(f"协议 '{protocol}' 不支持按钮消息")

    @classmethod
    def ark(cls, content: str, template_id: int = 24, event: 'BaseEvent' = None) -> 'BaseMessage':
        """
        构建 ARK 卡片消息
        
        Args:
            content: JSON格式的kv参数，如 [{"key": "#TITLE#", "value": "标题"}]
            template_id: ARK模板ID（如 23, 24, 37）
            event: 事件对象（可选）

        Returns:
            协议特定的 Message 对象
            
        Raises:
            ValueError: 如果当前协议不支持 ARK
        """
        event = event or cls._current_event

        if not event or not hasattr(event, 'bot'):
            raise RuntimeError("必须在事件上下文中调用 MessageBuilder")

        adapter = event.bot.adapter
        if not adapter.supports_message_type('ark'):
            protocol = adapter.get_protocol_name()
            raise ValueError(f"协议 '{protocol}' 不支持 ARK 消息")
        return adapter.build_message('ark', content=content, template_id=template_id)
