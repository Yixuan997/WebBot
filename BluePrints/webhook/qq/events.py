"""
QQ事件处理器

专门处理各种QQ Webhook事件的业务逻辑
"""

from Core.logging.file_logger import log_info, log_error, log_warn, log_debug


class QQEventProcessor:
    """QQ事件处理器"""

    def __init__(self):
        pass

    def _clean_channel_at_content(self, content: str, mentions: list = None) -> str:
        """
        清理频道@消息中的@标记（仅用于频道消息）

        Args:
            content: 原始消息内容
            mentions: QQ官方提供的mentions数组

        Returns:
            清理后的消息内容
        """
        if not mentions:
            # 如果没有mentions信息，使用正则表达式清理
            import re
            cleaned = re.sub(r'<@!?\d+>', '', content)
            return cleaned.strip()

        # 使用官方mentions信息精确清理@标记
        cleaned_content = content

        for mention in mentions:
            if isinstance(mention, dict):
                user_id = mention.get('id', '')
                if user_id:
                    # 移除 <@!用户ID> 和 <@用户ID> 格式
                    cleaned_content = cleaned_content.replace(f'<@!{user_id}>', '')
                    cleaned_content = cleaned_content.replace(f'<@{user_id}>', '')

        return cleaned_content.strip()

    def _process_message_safely(self, bot_id: int, message_data: dict, bot_manager):
        """
        事件处理消息（新架构）
        
        Args:
            bot_id: 机器人ID
            message_data: 原始Webhook数据
            bot_manager: BotManager实例
        """
        try:
            log_debug(bot_id, f"开始处理消息", "QQ_MESSAGE_START",
                      message_type=message_data.get('type'),
                      content_preview=message_data.get('content', '')[:30])

            # 获取Flask应用实例
            from flask import current_app
            try:
                app = current_app._get_current_object()
            except RuntimeError:
                from app import app

            # 在Flask应用上下文中处理消息
            with app.app_context():
                # 新架构：使用适配器解析事件
                from Adapters import get_adapter_manager
                from Adapters.qq.adapter import QQAdapter

                adapter_manager = get_adapter_manager()
                adapter = adapter_manager.running_adapters.get(bot_id)

                if not adapter:
                    log_error(bot_id, "适配器未运行", "QQ_ADAPTER_NOT_RUNNING")
                    return

                # 解析为Event对象
                event = QQAdapter.json_to_event(message_data)
                if not event:
                    log_warn(bot_id, "解析事件失败", "QQ_EVENT_PARSE_FAILED")
                    return

                # 注入bot实例
                event.bot = adapter.bot

                # 调用新架构的消息处理器
                import asyncio
                import threading

                def run_handler():
                    asyncio.run(adapter.bot.handle_event(event))

                # 在单独线程中运行异步函数
                threading.Thread(target=run_handler, daemon=True).start()

                log_debug(bot_id, f"消息处理完成", "QQ_MESSAGE_DONE")


        except Exception as process_error:
            import traceback
            log_error(bot_id, f"消息处理异常: {process_error}", "QQ_MESSAGE_PROCESS_ERROR",
                      error=str(process_error))

    def handle_c2c_message(self, bot_id: int, payload: dict, bot_manager) -> dict:
        """处理QQ单聊消息"""
        try:
            # 解析单聊消息
            message_data = {
                'id': payload.get('id'),  # 消息ID
                'openid': payload.get('author', {}).get('user_openid'),  # 发送者ID
                'content': payload.get('content', ''),  # 消息内容
                'timestamp': payload.get('timestamp'),  # 时间戳
                'author': payload.get('author', {}),  # 发送者信息
                'type': 'c2c',  # 消息类型
                'msg_id': payload.get('id'),  # 原始消息ID用于回复
                'message_scene': payload.get('message_scene', {})  # 消息场景信息
            }

            # 记录单聊消息事件
            log_info(bot_id, f"💬 收到单聊消息", "QQ_C2C_MESSAGE_WEBHOOK",
                     openid=message_data['openid'],
                     content_preview=message_data['content'][:50],
                     timestamp=message_data['timestamp'],
                     message_id=message_data['id'])

            # 调用机器人管理器处理消息
            if bot_manager:
                self._process_message_safely(bot_id, message_data, bot_manager)
            else:
                log_error(bot_id, "bot_manager为空，无法处理消息", "QQ_C2C_MESSAGE_NO_MANAGER")

            return {"status": "success", "message": "C2C message processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ单聊消息异常: {e}", "QQ_C2C_MESSAGE_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_channel_message(self, bot_id: int, payload: dict, bot_manager) -> dict:
        """处理QQ频道消息"""
        try:
            # 获取原始消息内容
            raw_content = payload.get('content', '')

            # 频道普通消息可能包含@标记，需要清理
            mentions = payload.get('mentions', [])
            cleaned_content = self._clean_channel_at_content(raw_content, mentions) if mentions else raw_content.strip()

            if mentions:
                pass
            else:
                pass

            # 按照官方文档格式解析频道消息
            message_data = {
                'id': payload.get('id'),  # 消息ID
                'channel_id': payload.get('channel_id'),  # 频道ID
                'guild_id': payload.get('guild_id'),  # 服务器ID
                'content': cleaned_content,  # 清理后的消息内容
                'raw_content': raw_content,  # 保留原始内容
                'timestamp': payload.get('timestamp'),  # 时间戳
                'author': payload.get('author', {}),  # 发送者信息
                'type': 'channel',  # 消息类型
                'msg_id': payload.get('id')  # 添加原始消息ID用于回复
            }

            log_info(bot_id, f"📢 收到频道消息", "QQ_CHANNEL_MESSAGE_WEBHOOK",
                     channel_id=message_data['channel_id'],
                     guild_id=message_data['guild_id'],
                     content_preview=message_data['content'][:50],
                     timestamp=message_data['timestamp'],
                     message_id=message_data['id'])

            # 调用机器人管理器处理消息
            if bot_manager:
                self._process_message_safely(bot_id, message_data, bot_manager)
            else:
                log_warn(bot_id, "bot_manager为空，无法处理消息", "QQ_CHANNEL_MESSAGE_NO_MANAGER")

            return {"status": "success", "message": "Channel message processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ频道消息异常: {e}", "QQ_CHANNEL_MESSAGE_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_group_at_message(self, bot_id: int, payload: dict, bot_manager) -> dict:
        """处理QQ群聊@消息"""
        try:
            log_debug(bot_id, f"开始处理群聊@消息", "QQ_GROUP_AT_START",
                      payload_keys=list(payload.keys()) if payload else [],
                      content_preview=payload.get('content', '')[:50] if payload.get('content') else '')

            # 获取原始消息内容
            raw_content = payload.get('content', '')

            # 群聊@消息QQ官方已经自动清理了@标记，直接使用原始内容
            cleaned_content = raw_content.strip()  # 只需要去除首尾空格

            # 按照官方文档格式解析群聊@消息
            message_data = {
                'id': payload.get('id'),  # 消息ID
                'group_openid': payload.get('group_openid'),  # 群组ID
                'content': cleaned_content,  # 清理后的消息内容
                'raw_content': raw_content,  # 保留原始内容
                'timestamp': payload.get('timestamp'),  # 时间戳
                'author': payload.get('author', {}),  # 发送者信息
                'type': 'group_at',  # 消息类型
                'msg_id': payload.get('id'),  # 原始消息ID用于回复
                'message_scene': payload.get('message_scene', {})  # 消息场景信息
            }

            # 获取author_openid
            author_info = message_data['author']
            author_openid = (author_info.get('member_openid') or
                             author_info.get('user_openid') or
                             author_info.get('id') or
                             author_info.get('openid'))

            log_info(bot_id, f"‍👥 收到群聊@消息", "QQ_GROUP_AT_MESSAGE_WEBHOOK",
                     message_id=message_data['id'],
                     group_openid=message_data['group_openid'],
                     content_preview=message_data['content'][:50],
                     timestamp=message_data['timestamp'],
                     author_openid=author_openid)

            # 调用机器人管理器处理消息
            if bot_manager:
                log_debug(bot_id, f"调用机器人管理器处理消息", "QQ_GROUP_AT_CALL_MANAGER")
                self._process_message_safely(bot_id, message_data, bot_manager)
                log_debug(bot_id, f"机器人管理器处理完成", "QQ_GROUP_AT_MANAGER_DONE")
            else:
                log_error(bot_id, "bot_manager为空，无法处理消息", "QQ_GROUP_AT_MESSAGE_NO_MANAGER")

            return {"status": "success", "message": "Group at message processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ群聊@消息异常: {e}", "QQ_GROUP_AT_MESSAGE_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_at_message(self, bot_id: int, payload: dict, bot_manager) -> dict:
        """处理QQ公域频道@消息"""
        try:
            # 获取原始消息内容和mentions信息
            raw_content = payload.get('content', '')
            mentions = payload.get('mentions', [])

            # 频道@消息需要清理@标记
            cleaned_content = self._clean_channel_at_content(raw_content, mentions)

            # 按照官方文档格式解析公域频道@消息
            message_data = {
                'id': payload.get('id'),  # 消息ID
                'channel_id': payload.get('channel_id'),  # 频道ID
                'guild_id': payload.get('guild_id'),  # 服务器ID
                'content': cleaned_content,  # 清理后的消息内容
                'raw_content': raw_content,  # 保留原始内容
                'mentions': mentions,  # 保留mentions信息
                'timestamp': payload.get('timestamp'),  # 时间戳
                'author': payload.get('author', {}),  # 发送者信息
                'type': 'at_message',  # 消息类型
                'msg_id': payload.get('id')  # 原始消息ID用于回复
            }

            log_info(bot_id, f"📣 收到公域频道@消息", "QQ_AT_MESSAGE_WEBHOOK",
                     channel_id=message_data['channel_id'],
                     guild_id=message_data['guild_id'],
                     content_preview=message_data['content'][:50],
                     timestamp=message_data['timestamp'],
                     message_id=message_data['id'])

            # 调用机器人管理器处理消息
            if bot_manager:
                self._process_message_safely(bot_id, message_data, bot_manager)

            return {"status": "success", "message": "At message processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ公域频道@消息异常: {e}", "QQ_AT_MESSAGE_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_direct_message(self, bot_id: int, payload: dict, bot_manager) -> dict:
        """处理QQ私信消息"""
        try:
            # 获取原始消息内容
            raw_content = payload.get('content', '')

            # 频道私信可能包含@标记，需要清理
            mentions = payload.get('mentions', [])
            cleaned_content = self._clean_channel_at_content(raw_content, mentions) if mentions else raw_content.strip()

            if mentions:
                pass
            else:
                pass

            # 按照官方文档格式解析私信消息
            message_data = {
                'id': payload.get('id'),  # 消息ID
                'guild_id': payload.get('guild_id'),  # 服务器ID
                'content': cleaned_content,  # 清理后的消息内容
                'raw_content': raw_content,  # 保留原始内容
                'mentions': mentions,  # 保留mentions信息
                'timestamp': payload.get('timestamp'),  # 时间戳
                'author': payload.get('author', {}),  # 发送者信息
                'type': 'direct_message',  # 消息类型
                'msg_id': payload.get('id')  # 添加原始消息ID用于回复
            }

            log_info(bot_id, f"📩 收到私信消息", "QQ_DIRECT_MESSAGE_WEBHOOK",
                     guild_id=message_data['guild_id'],
                     content_preview=message_data['content'][:50],
                     timestamp=message_data['timestamp'],
                     message_id=message_data['id'])

            # 调用机器人管理器处理消息
            if bot_manager:
                self._process_message_safely(bot_id, message_data, bot_manager)

            return {"status": "success", "message": "Direct message processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ私信消息异常: {e}", "QQ_DIRECT_MESSAGE_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_guild_event(self, bot_id: int, event_type: str, payload: dict, bot_manager) -> dict:
        """处理QQ频道管理事件"""
        try:
            guild_info = {
                'id': payload.get('id'),  # 消息ID
                'name': payload.get('name'),  # 服名称
                'description': payload.get('description'),  # 服描述
                'owner_id': payload.get('owner_id'),  # 所有者ID
                'member_count': payload.get('member_count'),  # 频道成员数量
                'event_type': event_type  # 事件类型
            }

            # 根据事件类型选择emoji
            event_emoji = {"GUILD_CREATE": "🏰➕", "GUILD_UPDATE": "🏰🔄", "GUILD_DELETE": "🏰➖"}.get(event_type, "🏰")

            log_info(bot_id, f"{event_emoji} 频道管理事件: {event_type}", "QQ_GUILD_EVENT_WEBHOOK",
                     guild_id=guild_info['id'],
                     guild_name=guild_info['name'],
                     event_type=event_type,
                     member_count=guild_info['member_count'])

            # 触发频道管理钩子
            if bot_manager and hasattr(bot_manager, 'plugin_manager'):
                bot_manager.plugin_manager.trigger_hook('guild_event', guild_info, bot_id=bot_id)

            return {"status": "success", "message": f"Guild event {event_type} processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ频道管理事件异常: {e}", "QQ_GUILD_EVENT_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_channel_event(self, bot_id: int, event_type: str, payload: dict, bot_manager) -> dict:
        """处理QQ子频道管理事件"""
        try:
            channel_info = {
                'id': payload.get('id'),  # 子频道ID
                'guild_id': payload.get('guild_id'),  # 服务器ID
                'name': payload.get('name'),  # 子频道名称
                'type': payload.get('type'),  # 子频道类型
                'position': payload.get('position'),  # 子频道位置
                'event_type': event_type  # 事件类型
            }

            # 根据事件类型选择emoji
            event_emoji = {"CHANNEL_CREATE": "📺➕", "CHANNEL_UPDATE": "📺🔄", "CHANNEL_DELETE": "📺➖"}.get(event_type, "📺")

            log_info(bot_id, f"{event_emoji} 子频道管理事件: {event_type}", "QQ_CHANNEL_EVENT_WEBHOOK",
                     channel_id=channel_info['id'],
                     guild_id=channel_info['guild_id'],
                     channel_name=channel_info['name'],
                     event_type=event_type)

            # 触发子频道管理钩子
            if bot_manager and hasattr(bot_manager, 'plugin_manager'):
                bot_manager.plugin_manager.trigger_hook('channel_event', channel_info, bot_id=bot_id)

            return {"status": "success", "message": f"Channel event {event_type} processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ子频道管理事件异常: {e}", "QQ_CHANNEL_EVENT_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_member_event(self, bot_id: int, event_type: str, payload: dict, bot_manager) -> dict:
        """处理QQ频道成员事件"""
        try:
            member_info = {
                'user': payload.get('user', {}),  # 成员用户信息
                'guild_id': payload.get('guild_id'),  # 服务器ID
                'nick': payload.get('nick'),  # 成员昵称
                'roles': payload.get('roles', []),  # 成员角色
                'joined_at': payload.get('joined_at'),  # 成员加入时间
                'event_type': event_type  # 事件类型
            }

            # 根据事件类型选择emoji
            event_emoji = {"GUILD_MEMBER_ADD": "👤➕", "GUILD_MEMBER_UPDATE": "👤🔄", "GUILD_MEMBER_REMOVE": "👤➖"}.get(
                event_type, "👤")

            log_info(bot_id, f"{event_emoji} 频道成员事件: {event_type}", "QQ_MEMBER_EVENT_WEBHOOK",
                     user_id=member_info['user'].get('id'),
                     guild_id=member_info['guild_id'],
                     nick=member_info['nick'],
                     joined_at=member_info['joined_at'],
                     event_type=event_type)

            # 触发成员管理钩子
            if bot_manager and hasattr(bot_manager, 'plugin_manager'):
                bot_manager.plugin_manager.trigger_hook('member_event', member_info, bot_id=bot_id)

            return {"status": "success", "message": f"Member event {event_type} processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ频道成员事件异常: {e}", "QQ_MEMBER_EVENT_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_friend_event(self, bot_id: int, event_type: str, payload: dict, bot_manager) -> dict:
        """处理QQ好友管理事件"""
        try:
            friend_info = {
                'openid': payload.get('openid'),
                'timestamp': payload.get('timestamp'),
                'event_type': event_type
            }

            action = "添加" if event_type == 'FRIEND_ADD' else "删除"
            emoji = "👥➕" if event_type == 'FRIEND_ADD' else "👥➖"
            log_info(bot_id, f"{emoji} 好友{action}事件", "QQ_FRIEND_EVENT_WEBHOOK",
                     openid=friend_info['openid'],
                     event_type=event_type,
                     timestamp=friend_info['timestamp'])

            # 触发好友管理钩子
            if bot_manager and hasattr(bot_manager, 'plugin_manager'):
                bot_manager.plugin_manager.trigger_hook('friend_event', friend_info, bot_id=bot_id)

            return {"status": "success", "message": f"Friend event {event_type} processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ好友管理事件异常: {e}", "QQ_FRIEND_EVENT_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_group_robot_event(self, bot_id: int, event_type: str, payload: dict, bot_manager) -> dict:
        """处理QQ群聊机器人管理事件"""
        try:
            group_info = {
                'group_openid': payload.get('group_openid'),
                'op_member_openid': payload.get('op_member_openid'),
                'timestamp': payload.get('timestamp'),
                'event_type': event_type
            }

            action = "添加到" if event_type == 'GROUP_ADD_ROBOT' else "移出"
            emoji = "🤖➕" if event_type == 'GROUP_ADD_ROBOT' else "🤖➖"
            log_info(bot_id, f"{emoji} 机器人被{action}群聊", "QQ_GROUP_ROBOT_EVENT_WEBHOOK",
                     group_openid=group_info['group_openid'],
                     op_member_openid=group_info['op_member_openid'],
                     event_type=event_type,
                     timestamp=group_info['timestamp'])

            # 触发群聊机器人管理钩子
            if bot_manager and hasattr(bot_manager, 'plugin_manager'):
                bot_manager.plugin_manager.trigger_hook('group_robot_event', group_info, bot_id=bot_id)

            return {"status": "success", "message": f"Group robot event {event_type} processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ群聊机器人管理事件异常: {e}", "QQ_GROUP_ROBOT_EVENT_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_message_setting_event(self, bot_id: int, event_type: str, payload: dict, bot_manager) -> dict:
        """处理QQ消息推送开关事件"""
        try:
            setting_info = {
                'openid': payload.get('openid'),
                'group_openid': payload.get('group_openid'),
                'timestamp': payload.get('timestamp'),
                'event_type': event_type
            }

            # 解析事件类型
            if 'C2C' in event_type:
                scope = "单聊"
                target = setting_info['openid']
            else:
                scope = "群聊"
                target = setting_info['group_openid']

            action = "开启" if 'RECEIVE' in event_type else "关闭"
            emoji = "🔔" if 'RECEIVE' in event_type else "🔕"

            log_info(bot_id, f"{emoji} {scope}消息推送{action}", "QQ_MESSAGE_SETTING_EVENT_WEBHOOK",
                     target=target,
                     event_type=event_type,
                     timestamp=setting_info['timestamp'])

            # 触发消息设置钩子
            if bot_manager and hasattr(bot_manager, 'plugin_manager'):
                bot_manager.plugin_manager.trigger_hook('message_setting_event', setting_info, bot_id=bot_id)

            return {"status": "success", "message": f"Message setting event {event_type} processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ消息推送开关事件异常: {e}", "QQ_MESSAGE_SETTING_EVENT_WEBHOOK_ERROR",
                      error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_interaction_event(self, bot_id: int, payload: dict, bot_manager) -> dict:
        """处理QQ互动事件"""
        try:
            interaction_info = {
                'id': payload.get('id'),  # 事件ID
                'type': payload.get('type'),  # 事件类型
                'data': payload.get('data', {}),  # 事件数据
                'guild_id': payload.get('guild_id'),  # 服务器ID
                'channel_id': payload.get('channel_id'),  # 频道ID
                'user': payload.get('user', {}),  # 用户信息
                'timestamp': payload.get('timestamp')  # 时间戳
            }

            log_info(bot_id, f"🎮 收到互动事件", "QQ_INTERACTION_EVENT_WEBHOOK",
                     interaction_id=interaction_info['id'],
                     interaction_type=interaction_info['type'],
                     guild_id=interaction_info['guild_id'],
                     timestamp=interaction_info['timestamp'])

            # 触发互动事件钩子
            if bot_manager and hasattr(bot_manager, 'plugin_manager'):
                bot_manager.plugin_manager.trigger_hook('interaction_event', interaction_info, bot_id=bot_id)

            return {"status": "success", "message": "Interaction event processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ互动事件异常: {e}", "QQ_INTERACTION_EVENT_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_audit_event(self, bot_id: int, event_type: str, payload: dict, bot_manager) -> dict:
        """处理QQ消息审核事件"""
        try:
            audit_info = {
                'message_id': payload.get('message_id'),  # 消息ID
                'guild_id': payload.get('guild_id'),  # 频道ID
                'channel_id': payload.get('channel_id'),  # 子频道ID
                'audit_id': payload.get('audit_id'),  # 审核ID
                'audit_time': payload.get('audit_time'),  # 审核时间
                'create_time': payload.get('create_time'),  # 创建时间
                'event_type': event_type  # 审核事件类型
            }

            result = "通过" if event_type == 'MESSAGE_AUDIT_PASS' else "拒绝"
            emoji = "✅" if event_type == 'MESSAGE_AUDIT_PASS' else "❌"
            log_info(bot_id, f"{emoji} 消息审核{result}", "QQ_AUDIT_EVENT_WEBHOOK",
                     message_id=audit_info['message_id'],
                     audit_id=audit_info['audit_id'],
                     audit_time=audit_info['audit_time'],
                     create_time=audit_info['create_time'],
                     event_type=event_type)

            # 触发审核事件钩子
            if bot_manager and hasattr(bot_manager, 'plugin_manager'):
                bot_manager.plugin_manager.trigger_hook('audit_event', audit_info, bot_id=bot_id)

            return {"status": "success", "message": f"Audit event {event_type} processed"}

        except Exception as e:
            log_error(bot_id, f"处理QQ消息审核事件异常: {e}", "QQ_AUDIT_EVENT_WEBHOOK_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}

    def handle_callback_verification(self, bot_id: int, payload: dict) -> dict:
        """处理QQ回调地址验证"""
        try:
            plain_token = payload.get('plain_token')
            if plain_token:
                log_info(bot_id, "✅ 处理QQ回调地址验证成功", "QQ_WEBHOOK_CALLBACK_VERIFICATION",
                         plain_token=plain_token[:10] + "...")

                # 根据QQ官方文档，回调验证需要返回plain_token
                response = {"plain_token": plain_token}
                return response
            else:
                log_error(bot_id, "❌ QQ回调验证缺少plain_token", "QQ_WEBHOOK_VERIFICATION_ERROR")
                return {"error": "Missing plain_token in payload"}
        except Exception as e:
            log_error(bot_id, f"❌ QQ回调验证异常: {e}", "QQ_WEBHOOK_VERIFICATION_EXCEPTION", error=str(e))
            return {"error": f"Verification failed: {str(e)}"}
