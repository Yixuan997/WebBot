"""
Echo插件 - 智能聊天插件
所有功能通过Hook系统实现，不使用传统命令系统
"""
import base64

from Core.logging.file_logger import log_info, log_error
from Core.message.builder import MessageBuilder
from Core.plugin.base import BasePlugin


class Plugin(BasePlugin):
    """智能回声插件"""

    def __init__(self):
        super().__init__()

        # 插件信息
        self.name = "Echo"
        self.version = "1.0.0"
        self.description = "Echo插件 - 重复用户输入的内容"
        self.author = "Yixuan"
        self.priority = 5  # 设置较高优先级，优先处理echo命令

        # 只注册Hook事件处理器，不注册命令
        self.hooks = {
            'message_received': [self.handle_message_hook],
            'bot_start': [self.on_bot_start_hook],
            'bot_stop': [self.on_bot_stop_hook]
        }

        # 注册命令信息
        self.register_command_info('echo', '重复发送的内容', '/echo <内容> 或 echo <内容>')
        self.register_command_info('我的信息', '显示用户信息', '/我的信息 或 我的信息')

        # 支持的命令处理器
        self.command_handlers = {
            'echo': self.handle_echo,
            '我的信息': self.handle_my_info
        }

    # 工具函数

    def parse_refidx(self, refidx_str):
        """
        解析 REFIDX 格式的消息索引，提取QQ号

        Args:
            refidx_str: 格式如 "REFIDX_CIHZAhD/y8jDBhiWkdQs"

        Returns:
            dict: {'msg_seq': int, 'timestamp': int, 'qq_number': int} 或 None
        """
        if not refidx_str.startswith("REFIDX_"):
            return None

        try:
            # 提取Base64部分
            encoded_part = refidx_str[7:]

            # Base64解码
            decoded = base64.b64decode(encoded_part + "==")

            # 解析protobuf字段
            def parse_varint(data, offset):
                result = 0
                shift = 0
                while offset < len(data):
                    byte = data[offset]
                    result |= (byte & 0x7F) << shift
                    offset += 1
                    if (byte & 0x80) == 0:
                        break
                    shift += 7
                return result, offset

            # 解析各个字段
            offset = 1  # 跳过第一个字段标识
            msg_seq, offset = parse_varint(decoded, offset)
            offset += 1  # 跳过第二个字段标识
            timestamp, offset = parse_varint(decoded, offset)
            offset += 1  # 跳过第三个字段标识
            qq_number, offset = parse_varint(decoded, offset)

            return {
                'msg_seq': msg_seq,
                'timestamp': timestamp,
                'qq_number': qq_number
            }

        except Exception as e:
            log_error(0, f"解析REFIDX失败: {e}", "ECHO_PARSE_REFIDX_ERROR")
            return None

    def get_user_qq_from_message(self, message_data):
        """从消息数据中提取用户QQ号"""
        try:
            # 获取消息场景信息
            message_scene = message_data.get('message_scene', {})
            ext_info = message_scene.get('ext', [])

            # 解析REFIDX获取真实QQ号
            for ext in ext_info:
                if ext.startswith('msg_idx=REFIDX_'):
                    refidx = ext[8:]  # 去掉 "msg_idx=" 前缀
                    parsed = self.parse_refidx(refidx)
                    if parsed:
                        return parsed['qq_number']

            return None
        except Exception as e:
            log_error(0, f"提取QQ号失败: {e}", "ECHO_GET_QQ_ERROR")
            return None

    # Hook命令处理器

    def handle_echo(self, args):
        """处理echo命令"""
        if args:
            content = " ".join(args)
            return MessageBuilder.text(f"🔄 你说：{content}")
        else:
            return MessageBuilder.text("❓ 请在后面输入要重复的内容，比如：/echo 你好")

    def handle_my_info(self, args, message_data=None):
        """处理我的信息命令"""
        try:
            if not message_data:
                return MessageBuilder.text("❌ 无法获取消息数据")

            # 尝试获取真实QQ号
            qq_number = self.get_user_qq_from_message(message_data)

            if qq_number:
                return MessageBuilder.text(f"📱 你的QQ号: {qq_number}")
            else:
                return MessageBuilder.text("❌ 无法获取QQ号")

        except Exception as e:
            log_error(0, f"处理我的信息命令异常: {e}", "ECHO_MY_INFO_ERROR")
            return MessageBuilder.text(f"❌ 获取信息失败: {str(e)}")

    # Hook事件处理器

    def handle_message_hook(self, message_data, user_id=None, bot_id=None):
        """处理消息Hook - 智能命令处理（支持带/和不带/）"""
        try:
            # 保存当前消息数据，供命令处理器使用
            self._current_message_data = message_data

            original_content = message_data.get('content', '')
            content = original_content.strip()

            # 先尝试处理命令（带/或不带/）
            command_result = self._handle_smart_command(content, bot_id)
            if command_result.get('handled'):
                return command_result

            # 处理自然语言交互
            return self._handle_natural_language(content, bot_id)

        except Exception as e:
            log_error(bot_id or 0, f"Echo插件处理消息异常: {e}", "ECHO_HOOK_ERROR", error=str(e))
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
                # 为需要message_data的命令传递额外参数
                if command == '我的信息':
                    response = handler(args, message_data=self._current_message_data)
                else:
                    response = handler(args)
                return {
                    'response': response,
                    'handled': True
                }
            except Exception as e:
                log_error(bot_id or 0, f"Echo插件命令处理异常: {e}", "ECHO_COMMAND_ERROR", error=str(e))
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
                # 为需要message_data的命令传递额外参数
                if command == '我的信息':
                    response = handler(args, message_data=self._current_message_data)
                else:
                    response = handler(args)
                return {
                    'response': response,
                    'handled': True
                }
            except Exception as e:
                log_error(bot_id or 0, f"Echo插件命令处理异常: {e}", "ECHO_COMMAND_ERROR", error=str(e))
                return {
                    'response': MessageBuilder.text(f"❌ 命令执行出错: {str(e)}"),
                    'handled': True
                }

        # 检查是否是echo命令的输入错误（更精确的检测）
        if command == 'echo' or (command.startswith('echo') and len(command) <= 6):
            return {
                'response': MessageBuilder.text(
                    '❌ 命令格式错误！正确格式是：/echo <内容> 或 echo <内容>\n例如：/echo 你好'),
                'handled': True
            }

        return {'handled': False}

    def _handle_natural_language(self, content, bot_id=None):
        """处理自然语言消息 - 简化版本"""
        # Echo插件不处理自然语言，只处理echo命令
        return {'handled': False}

    def on_bot_start_hook(self, bot_id):
        """机器人启动Hook"""
        return {'message': f'Echo插件已为机器人 {bot_id} 准备就绪'}

    def on_bot_stop_hook(self, bot_id):
        """机器人停止Hook"""
        return {'message': f'Echo插件已为机器人 {bot_id} 清理资源'}

    # 插件生命周期

    def on_enable(self):
        """插件启用时调用"""
        super().on_enable()
        log_info(0, "Echo插件已启用（命令+Hook模式），支持智能回复和事件监听", "ECHO_PLUGIN_ENABLED")

    def on_disable(self):
        """插件禁用时调用"""
        super().on_disable()
        log_info(0, "Echo插件已禁用", "ECHO_PLUGIN_DISABLED")
