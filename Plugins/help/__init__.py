"""
About插件 - 显示机器人信息
通过Hook系统处理about命令
"""
from Core.logging.file_logger import log_info
from Core.message.builder import MessageBuilder
from Core.plugin.base import BasePlugin


class Plugin(BasePlugin):
    """About插件 - 显示机器人信息"""

    def __init__(self):
        super().__init__()

        # 插件信息
        self.name = "Help"
        self.version = "1.0.0"
        self.description = "About插件 - 显示机器人信息"
        self.author = "Yixuan"

        # 只注册Hook事件处理器
        self.hooks = {
            'message_received': [self.handle_message_hook],
            'bot_start': [self.on_bot_start_hook],
            'bot_stop': [self.on_bot_stop_hook]
        }

        # 注册命令信息（只有about功能）
        self.register_command_info('about', '关于机器人', '/about 或 about')

        # 命令处理器
        self.command_handlers = {
            'about': self.handle_about
        }

    # Hook事件处理器

    def handle_message_hook(self, message_data, user_id=None, bot_id=None):
        """处理消息Hook - 智能命令处理（支持带/和不带/）"""
        try:
            content = message_data.get('content', '').strip()

            # 先尝试处理命令（带/或不带/）
            command_result = self._handle_smart_command(content, bot_id)
            if command_result.get('handled'):
                return command_result

            return {'handled': False}

        except Exception as e:
            log_info(bot_id or 0, f"About插件Hook处理消息异常: {e}", "ABOUT_HOOK_ERROR")
            return {'handled': False}

    def _handle_smart_command(self, content, bot_id=None):
        """智能命令处理 - 支持带/和不带/的命令"""
        # 检查是否是带/的命令
        if content.startswith('/'):
            return self._handle_command(content, bot_id)

        # 检查是否是不带/的命令
        parts = content.split()
        if not parts:
            return {'handled': False}

        command = parts[0].lower()

        # 检查是否是支持的命令
        if command in self.command_handlers:
            try:
                args = parts[1:] if len(parts) > 1 else []
                handler = self.command_handlers[command]
                response = handler(args)
                return {
                    'response': response,
                    'handled': True
                }
            except Exception as e:
                log_info(bot_id or 0, f"About插件命令处理异常: {e}", "ABOUT_COMMAND_ERROR")
                return {
                    'response': MessageBuilder.text(f"❌ 命令执行出错: {str(e)}"),
                    'handled': True
                }

        return {'handled': False}

    def _handle_command(self, content, bot_id=None):
        """处理命令消息"""
        # 解析命令
        parts = content[1:].split()  # 去掉/前缀并分割
        if not parts:
            return {'handled': False}

        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # 检查是否是支持的命令
        if command in self.command_handlers:
            try:
                handler = self.command_handlers[command]
                response = handler(args)
                return {
                    'response': response,
                    'handled': True
                }
            except Exception as e:
                log_info(bot_id or 0, f"Help插件命令处理异常: {e}", "HELP_COMMAND_ERROR")
                return {
                    'response': MessageBuilder.text(f"❌ 帮助命令执行出错: {str(e)}"),
                    'handled': True
                }

        return {'handled': False}

    # Hook命令处理器

    def handle_about(self, args):
        """处理about命令"""
        about_text = """🤖 QQ机器人系统

📊 版本信息:
• 机器人版本: 2.0.0
• 插件系统: Hook模式
• 消息系统: 多媒体支持
• Hook系统: 已启用

🔧 技术栈:
• Python + Flask
• 插件化架构
• Hook事件系统
• Webhook回调
• 统一消息对象

✨ 新功能:
• 支持图片消息
• 支持Markdown格式
• 支持卡片消息
• 支持按钮交互

👥 开发团队:
• Yixuan
"""
        return MessageBuilder.text(about_text)

    def on_bot_start_hook(self, bot_id):
        """机器人启动Hook"""
        return {'message': f'About插件已为机器人 {bot_id} 准备就绪'}

    def on_bot_stop_hook(self, bot_id):
        """机器人停止Hook"""
        return {'message': f'About插件已为机器人 {bot_id} 清理资源'}

    def on_enable(self):
        """插件启用时调用"""
        super().on_enable()
        log_info(0, "About插件已启用，可以使用 /about 命令", "ABOUT_PLUGIN_ENABLED")

    def on_disable(self):
        """插件禁用时调用"""
        super().on_disable()
        log_info(0, "About插件已禁用", "ABOUT_PLUGIN_DISABLED")
