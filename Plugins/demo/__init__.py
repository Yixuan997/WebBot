"""
Demo插件 - 完全基于Hook系统的示例插件

这个插件展示了如何完全使用Hook系统来构建插件：
- 使用message_received hook处理消息
- 使用message_sent hook监听消息发送
- 使用bot_start/bot_stop hook处理生命周期
- 使用user_join/user_leave hook处理用户事件
- 展示各种消息类型的构建方法

命令：
- demo - 显示功能菜单
- demo_text - 演示文本消息
- demo_image - 演示图片消息
- demo_card - 演示卡片消息
- demo_markdown - 演示Markdown消息
- demo_buttons - 演示按钮交互
- demo_hooks - 显示Hook系统信息
"""

import time
from datetime import datetime

from Core.message.builder import MessageBuilder
from Core.plugin.base import BasePlugin


class Plugin(BasePlugin):
    """Demo插件 - 完全基于Hook系统"""

    def __init__(self):
        super().__init__()

        # 插件信息
        self.name = "Demo"
        self.version = "1.0.0"
        self.description = "Demo插件"
        self.author = "Yixuan"
        self.priority = 100  # 设置较低优先级，让其他插件先处理

        # 统计信息
        self.stats = {
            'messages_processed': 0,
            'commands_executed': 0,
            'start_time': time.time(),
            'last_activity': None
        }

        # 注册命令信息
        self.register_command_info('demo', 'Demo插件功能菜单', '/demo 或 demo')
        self.register_command_info('demo_text', '文本消息演示', '/demo_text 或 demo_text')
        self.register_command_info('demo_image', '图片消息演示', '/demo_image 或 demo_image')
        self.register_command_info('demo_card', '卡片消息演示', '/demo_card 或 demo_card')
        self.register_command_info('demo_markdown', 'Markdown消息演示', '/demo_markdown 或 demo_markdown')
        self.register_command_info('demo_buttons', '按钮交互演示', '/demo_buttons 或 demo_buttons')
        self.register_command_info('demo_hooks', 'Hook系统信息', '/demo_hooks 或 demo_hooks')
        self.register_command_info('demo_stats', '插件统计信息', '/demo_stats 或 demo_stats')
        self.register_command_info('demo_large_image', '大图演示', '/demo_large_image 或 demo_large_image')

        # 命令处理器
        self.command_handlers = {
            'demo': self.cmd_menu,
            'demo_text': self.cmd_text,
            'demo_image': self.cmd_image,
            'demo_card': self.cmd_card,
            'demo_markdown': self.cmd_markdown,
            'demo_buttons': self.cmd_buttons,
            'demo_hooks': self.cmd_hooks,
            'demo_stats': self.cmd_stats,
            'demo_large_image': self.demo_large_image
        }

        # 注册所有Hook事件处理器
        self.hooks = {
            'message_received': [self.on_message_received],
            'message_sent': [self.on_message_sent],
            'message_not_handled': [self.on_message_not_handled],
            'bot_start': [self.on_bot_start],
            'bot_stop': [self.on_bot_stop],
            'user_join': [self.on_user_join],
            'user_leave': [self.on_user_leave],
            'plugin_loaded': [self.on_plugin_loaded],
            'plugin_unloaded': [self.on_plugin_unloaded]
        }

    # ===== Hook事件处理器 =====

    def on_message_received(self, message_data, user_id=None, bot_id=None):
        """处理接收到的消息"""
        try:

            self.stats['messages_processed'] += 1
            self.stats['last_activity'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 保存当前消息数据，供命令处理器使用
            self._current_message_data = message_data
            self._current_user_id = user_id
            self._current_bot_id = bot_id

            content = message_data.get('content', '').strip()

            # 处理特殊关键词
            if content.lower() in ['hello', '你好', 'hi']:
                return {
                    'response': MessageBuilder.text(f"👋 你好！我是Demo插件，发送 'demo' 查看功能菜单"),
                    'handled': True
                }

            # 先尝试处理命令（带/和不带/）
            command_result = self._handle_smart_command(content, bot_id)
            if command_result.get('handled'):
                self.stats['commands_executed'] += 1
                return command_result

            # 对于非Demo命令，总是返回False，让其他插件先处理
            # 兜底处理将通过message_not_handled Hook实现
            return {'handled': False}

        except Exception as e:
            import traceback
            return {
                'response': MessageBuilder.text(f"❌ Demo插件处理消息异常: {str(e)}"),
                'handled': True
            }

    def on_message_sent(self, message_data, user_id=None, bot_id=None):
        """监听消息发送事件"""
        # 这里可以记录发送的消息，做统计等
        _ = message_data, user_id, bot_id  # 忽略未使用的参数
        return {'handled': False}

    def on_message_not_handled(self, message_data, user_id=None, bot_id=None):
        """处理未被任何插件处理的消息"""
        try:
            _ = bot_id  # 忽略未使用的参数
            content = message_data.get('content', '').strip()

            # 生成帮助图片
            error_message = self._generate_help_message(content, user_id)

            return {
                'response': error_message,
                'handled': True
            }

        except Exception as e:
            return {
                'response': MessageBuilder.text(f"❌ 处理未知命令时出错: {str(e)}"),
                'handled': True
            }

    def on_bot_start(self, bot_id):
        """机器人启动事件"""
        return {
            'message': f'🚀 Demo插件已为机器人 {bot_id} 启动完成！',
            'handled': True
        }

    def on_bot_stop(self, bot_id):
        """机器人停止事件"""
        return {
            'message': f'🛑 Demo插件已为机器人 {bot_id} 清理完成！',
            'handled': True
        }

    def on_user_join(self, user_id, group_id=None, bot_id=None):
        """用户加入事件"""
        _ = user_id, group_id, bot_id  # 忽略未使用的参数
        return {
            'response': MessageBuilder.text(f"🎉 欢迎新用户！发送 'demo' 了解Demo插件功能"),
            'handled': False  # 让其他插件也能处理
        }

    def on_user_leave(self, user_id, group_id=None, bot_id=None):
        """用户离开事件"""
        _ = user_id, group_id, bot_id  # 忽略未使用的参数
        return {'handled': False}

    def on_plugin_loaded(self, plugin_name):
        """插件加载事件"""
        if plugin_name != self.name:  # 不处理自己的加载事件
            return {'handled': False}
        return {'handled': True}

    def on_plugin_unloaded(self, plugin_name):
        """插件卸载事件"""
        _ = plugin_name  # 忽略未使用的参数
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
                response = handler(args, self._current_message_data, self._current_user_id, self._current_bot_id)
                return {
                    'response': response,
                    'handled': True
                }
            except Exception as e:
                return {
                    'response': MessageBuilder.text(f"❌ 命令执行出错: {str(e)}"),
                    'handled': True
                }

        return {'handled': False}

    def _handle_command(self, content, bot_id=None):
        """处理带/的命令"""
        _ = bot_id  # 忽略未使用的参数
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
                response = handler(args, self._current_message_data, self._current_user_id, self._current_bot_id)
                return {
                    'response': response,
                    'handled': True
                }
            except Exception as e:
                return {
                    'response': MessageBuilder.text(f"❌ 命令执行出错: {str(e)}"),
                    'handled': True
                }

        return {'handled': False}

    # ===== 命令处理方法 =====

    def cmd_menu(self, args, message_data=None, user_id=None, bot_id=None):
        """显示Demo插件功能菜单"""
        _ = args, message_data, user_id, bot_id  # 忽略未使用的参数
        uptime = int(time.time() - self.stats['start_time'])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60

        return MessageBuilder.markdown(f"""
# 🎮 Demo插件功能菜单

欢迎使用完全基于Hook系统的Demo插件！

## 📝 消息类型演示
- `demo_text` - 文本消息演示
- `demo_image` - 图片消息演示
- `demo_card` - 卡片消息演示
- `demo_markdown` - Markdown消息演示
- `demo_buttons` - 按钮交互演示

## 🔧 系统功能
- `demo_hooks` - 显示Hook系统信息
- `demo_stats` - 显示插件统计信息

## 📊 当前状态
- **运行时间**: {hours}小时{minutes}分钟
- **处理消息**: {self.stats['messages_processed']}条
- **执行命令**: {self.stats['commands_executed']}次
- **最后活动**: {self.stats['last_activity'] or '无'}

---
*Demo插件 v3.0.0 - 完全基于Hook系统*
        """)

    def cmd_text(self, args, message_data=None, user_id=None, bot_id=None):
        """演示文本消息"""
        _ = message_data  # 忽略未使用的参数
        return MessageBuilder.text(
            f"📝 这是一条文本消息演示！\n\n"
            f"✨ 消息信息：\n"
            f"• 用户ID: {user_id}\n"
            f"• 机器人ID: {bot_id}\n"
            f"• 处理时间: {datetime.now().strftime('%H:%M:%S')}\n"
            f"• 参数: {' '.join(args) if args else '无'}\n\n"
            f"🎯 这条消息通过Hook+命令系统处理！"
        )

    def cmd_image(self, args, message_data=None, user_id=None, bot_id=None):
        """演示图片消息"""
        _ = args, message_data, bot_id  # 忽略未使用的参数
        return MessageBuilder.image(
            "https://q2.qlogo.cn/headimg_dl?spec=100&dst_uin=93653142",
            f"🖼️ 图片消息演示 - 用户{user_id}",
            auto_upload=True
        )

    def cmd_card(self, args, message_data=None, user_id=None, bot_id=None):
        """演示卡片消息"""
        _ = args, message_data  # 忽略未使用的参数
        return MessageBuilder.text_card(
            text=f"🎯 这是一个卡片消息演示\n\n"
                 f"📊 Hook+命令系统信息：\n"
                 f"• 当前用户: {user_id}\n"
                 f"• 机器人ID: {bot_id}\n"
                 f"• 消息时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                 f"• 插件版本: {self.version}\n\n"
                 f"✨ 通过Hook+命令系统处理！",
            description="Demo插件卡片演示",
            prompt="Hook+命令系统演示"
        )

    def cmd_markdown(self, args, message_data=None, user_id=None, bot_id=None):
        """演示Markdown消息"""
        _ = message_data  # 忽略未使用的参数
        return MessageBuilder.markdown(f"""
# 📋 Markdown消息演示

这是一条**Markdown格式**的消息，通过Hook+命令系统处理！

## 📊 当前信息
- **用户ID**: {user_id}
- **机器人ID**: {bot_id}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **参数**: {' '.join(args) if args else '无'}

## 🔧 Hook+命令系统特性
1. **事件驱动** - 基于Hook事件的消息处理
2. **命令注册** - 使用command_handlers注册命令
3. **智能识别** - 支持带/和不带/的命令
4. **统一接口** - 标准化的消息格式

### ✨ 支持的Hook类型
- `message_received` - 消息接收
- `message_sent` - 消息发送
- `bot_start` - 机器人启动
- `bot_stop` - 机器人停止
- `user_join` - 用户加入
- `user_leave` - 用户离开

---
*通过Hook+命令系统生成 - {datetime.now().strftime('%H:%M:%S')}*
        """)

    def cmd_buttons(self, args, message_data=None, user_id=None, bot_id=None):
        """演示按钮交互"""
        _ = args, message_data, bot_id  # 忽略未使用的参数
        return MessageBuilder.button_card(
            "🎮 Hook+命令系统交互演示",
            f"用户 {user_id} 请选择一个操作：",
            [
                {'text': '📊 查看统计', 'data': 'demo_stats'},
                {'text': '🔧 Hook信息', 'data': 'demo_hooks'},
                {'text': '📝 发送文本', 'data': 'demo_text'},
                {'text': '🖼️ 发送图片', 'data': 'demo_image'}
            ]
        )

    def cmd_hooks(self, args, message_data=None, user_id=None, bot_id=None):
        """显示Hook系统信息"""
        _ = args, message_data, user_id, bot_id  # 忽略未使用的参数
        # 获取当前注册的Hook信息
        hook_info = []
        for hook_name, handlers in self.hooks.items():
            hook_info.append(f"• {hook_name}: {len(handlers)}个处理器")

        # 获取当前注册的命令信息
        command_info = []
        for command_name in self.command_handlers.keys():
            command_info.append(f"• {command_name}: 已注册")

        return MessageBuilder.text_card(
            text=f"🔧 Hook+命令系统信息\n\n"
                 f"📋 当前插件注册的Hook:\n"
                 f"{chr(10).join(hook_info)}\n\n"
                 f"📋 当前插件注册的命令:\n"
                 f"{chr(10).join(command_info)}\n\n"
                 f"🎯 Hook+命令系统工作原理:\n"
                 f"1. Hook事件触发 - 系统事件自动触发Hook\n"
                 f"2. 命令识别 - 在Hook中识别并处理命令\n"
                 f"3. 命令分发 - 调用command_handlers中的处理器\n"
                 f"4. 响应生成 - 处理器生成MessageBuilder响应\n"
                 f"5. 消息发送 - 系统发送响应消息\n\n"
                 f"📊 处理统计:\n"
                 f"• 消息处理: {self.stats['messages_processed']}次\n"
                 f"• 命令执行: {self.stats['commands_executed']}次\n"
                 f"• 运行时长: {int(time.time() - self.stats['start_time'])}秒\n\n"
                 f"Hook+命令系统状态 - {datetime.now().strftime('%H:%M:%S')}",
            description="Hook+命令系统详细信息",
            prompt="完全基于Hook系统"
        )

    def cmd_stats(self, args, message_data=None, user_id=None, bot_id=None):
        """显示插件统计信息"""
        _ = args, message_data  # 忽略未使用的参数
        uptime = int(time.time() - self.stats['start_time'])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60

        return MessageBuilder.text_card(
            text=f"📊 Demo插件统计信息\n\n"
                 f"🕐 运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
                 f"📨 处理消息: {self.stats['messages_processed']}条\n"
                 f"⚡ 执行命令: {self.stats['commands_executed']}次\n"
                 f"🔄 最后活动: {self.stats['last_activity'] or '无'}\n"
                 f"👤 当前用户: {user_id}\n"
                 f"🤖 机器人ID: {bot_id}\n\n"
                 f"✨ 插件版本: {self.version}\n"
                 f"👨‍💻 作者: {self.author}",
            description="Demo插件运行统计",
            prompt="Hook+命令系统"
        )

    def demo_large_image(self, args, message_data=None, user_id=None, bot_id=None):
        """大图卡片演示"""
        _ = args, message_data  # 忽略未使用的参数
        return MessageBuilder.large_image(
            title='WebBot',
            subtitle='❓ 未知命令:  - 插件使用指南',
            image_url='https://img10.360buyimg.com/ddimg/jfs/t1/307235/17/22613/41425/688ee471Fe2007142/e461aa0fc213ed32.jpg',
            prompt='❓ 未知命令:  - 插件使用指南'
        )

    # ===== 插件生命周期方法 =====

    def on_enable(self):
        """插件启用时调用"""
        super().on_enable()
        self.stats['start_time'] = time.time()  # 重置启动时间

    def on_disable(self):
        """插件禁用时调用"""
        super().on_disable()

    def _generate_help_message(self, content, user_id):
        """生成帮助消息"""
        _ = user_id  # 忽略未使用的参数

        try:
            # 导入浏览器模块
            from Core.tools.browser import browser

            # 模板路径（相对于Plugins目录）
            template_path = 'demo/plugin_help.html'

            # 准备模板数据
            template_data = {
                'unknown_command': content
            }

            # 渲染HTML为base64图片
            image_data = browser.render(template_path, template_data, width=900)

            if image_data:
                result = MessageBuilder.image(
                    base64_data=image_data,
                    caption=f"❓ 未知命令:  - 插件使用指南"
                )
                return result
            else:
                return MessageBuilder.text(f"❓ 未知命令:  - 插件使用指南")

        except Exception as e:
            # 异常处理，返回简单文本
            return MessageBuilder.text(f"❓ 未知命令:  - 插件使用指南")
