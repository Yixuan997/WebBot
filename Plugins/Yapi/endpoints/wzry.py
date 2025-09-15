"""
王者荣耀登录查询API端点
"""

import threading
import time

from Core.logging.file_logger import log_error, log_info
from Core.message.builder import MessageBuilder


class WzryAPI:
    """王者荣耀API端点"""

    # API配置常量
    BASE_API_URL = 'https://api.makuo.cc/api'
    LOGIN_API_URL = f'{BASE_API_URL}/get.login.qq'
    CHECK_SCAN_API_URL = f'{BASE_API_URL}/get.login.qq?action=check_scan&code='
    CAMP_LOGIN_API_URL = f'{BASE_API_URL}/get.game.wzry?action=营地登录&ticket='
    WZRY_API_URL = f'{BASE_API_URL}/get.game.wzry'

    # ARK按钮模板ID
    ARK_ID = '102084649_1751807812'

    # API动作常量
    ACTIONS = {
        'CHECK_SCAN': 'check_scan',
        'CAMP_LOGIN': '营地登录',
        'ECONOMY': '经济面板',
        'BATTLES': '最近战绩',
        'DETAILS': '具体信息',
        'CAMP_INFO': '营地信息',
        'SEASON_STATS': '赛季统计',
        'HERO_HOTNESS': '英雄热度',
        'BUILD_RECOMMEND': '出装推荐'
    }

    # 配置常量
    LOGIN_EXPIRE_MINUTES = 30
    AUTO_CHECK_MAX_ATTEMPTS = 60
    AUTO_CHECK_INTERVAL = 5

    def __init__(self, client):
        self.client = client

    def _make_api_request(self, url, bot_id=0, operation_name="API请求"):
        """通用API请求方法"""
        try:
            log_info(bot_id, f"开始{operation_name}", f"WZRY_{operation_name.upper()}_START")

            response = self.client.request_sync(url, bot_id=bot_id)
            log_info(bot_id, f"{operation_name}API响应: {response}", f"WZRY_{operation_name.upper()}_RESPONSE")

            if response and str(response.get('code')) == '200':
                return response.get('data', {})
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(bot_id, f"{operation_name}API返回错误: {error_msg}",
                          f"WZRY_{operation_name.upper()}_API_ERROR")
                return None

        except Exception as e:
            log_error(bot_id, f"{operation_name}失败: {e}", f"WZRY_{operation_name.upper()}_EXCEPTION", error=str(e))
            return None

    def _get_ticket_from_login_info(self, login_info):
        """从登录信息中获取ticket"""
        if not login_info:
            return None
        ticket = login_info.get('ticket')
        return ticket

    def _build_wzry_api_url(self, action, ticket=None, **params):
        """构建王者荣耀API URL"""
        url = f"{self.WZRY_API_URL}?action={action}"
        if ticket:
            url += f"&ticket={ticket}"
        for key, value in params.items():
            if value is not None:
                url += f"&{key}={value}"
        return url

    def get_login_qr(self, bot_id=None, user_id=None, target=None, original_msg_id=None):
        """获取王者荣耀登录二维码"""
        try:
            log_info(bot_id or 0, "开始获取王者荣耀登录二维码", "WZRY_LOGIN_START")

            # 使用统一客户端发送请求
            response = self.client.request_sync(self.LOGIN_API_URL, bot_id=bot_id)

            if response and str(response.get('code')) == '200':
                data = response.get('data', {})
                code = data.get('code', '')

                # 启动后台检测任务（如果有必要的参数）
                if code and user_id:
                    # 构建简单的target（用于后台检测）
                    if not target:
                        target = f"user:{user_id}"  # 默认私聊目标
                    if not original_msg_id:
                        original_msg_id = "auto_reply"  # 默认回复标识

                    self._start_auto_check(code, bot_id, user_id, target, original_msg_id)

                return self._format_login_message(response)
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(bot_id or 0, f"获取登录二维码失败: {error_msg}", "WZRY_LOGIN_ERROR", error=error_msg)
                return MessageBuilder.text(f"❌ 获取登录二维码失败: {error_msg}\n\n💡 请稍后重试")

        except Exception as e:
            log_error(bot_id or 0, f"获取王者荣耀登录二维码失败: {str(e)}", "WZRY_LOGIN_EXCEPTION", error=str(e))
            return MessageBuilder.text(f"❌ 获取登录二维码失败: {str(e)}")

    def _start_auto_check(self, code, bot_id, user_id, target, original_msg_id):
        """启动后台自动检测任务"""

        def auto_check_task():
            max_attempts = 60  # 最多检查60次（5分钟）
            check_interval = 5  # 每5秒检查一次

            log_info(bot_id, f"启动自动检测任务: code={code}", "WZRY_AUTO_CHECK_START")

            for attempt in range(max_attempts):
                try:
                    time.sleep(check_interval)

                    # 检查登录状态，传递qq_user_id用于存储
                    result = self.check_scan_status(code, bot_id, user_id)

                    if result:  # 如果有结果（登录成功或失败）
                        # 发送结果消息（回复原消息）
                        self._send_auto_reply(bot_id, target, result, original_msg_id)
                        log_info(bot_id, f"自动检测完成: 第{attempt + 1}次检查", "WZRY_AUTO_CHECK_DONE")
                        break

                except Exception as e:
                    log_error(bot_id, f"自动检测异常: {e}", "WZRY_AUTO_CHECK_ERROR", error=str(e))

            else:
                # 超时未登录
                timeout_msg = MessageBuilder.text("⏰ 登录检测超时\n\n💡 请重新获取登录二维码")
                self._send_auto_reply(bot_id, target, timeout_msg, original_msg_id)
                log_info(bot_id, "自动检测超时", "WZRY_AUTO_CHECK_TIMEOUT")

        # 启动后台线程
        thread = threading.Thread(target=auto_check_task, daemon=True)
        thread.start()

    def _send_auto_reply(self, bot_id, target, message, original_msg_id):
        """发送自动回复（回复原消息）"""
        try:

            # 在后台线程中需要创建Flask应用上下文
            from flask import current_app
            try:
                # 尝试获取当前应用上下文
                app = current_app._get_current_object()
            except RuntimeError:
                # 如果没有应用上下文，导入应用实例
                from app import app

            # 在应用上下文中执行
            with app.app_context():
                from Adapters import get_adapter_manager
                adapter_manager = get_adapter_manager()

                if adapter_manager:

                    # 检查适配器状态
                    running_adapters = adapter_manager.get_running_adapters()

                    if bot_id in running_adapters:
                        pass  # 适配器运行正常
                    else:
                        pass  # 适配器未运行，但仍尝试发送

                    # 使用原始消息ID进行回复
                    success = adapter_manager.send_message(bot_id, target, message, reply_to_msg_id=original_msg_id)
                    if success:
                        log_info(bot_id, "自动消息发送成功", "WZRY_AUTO_MESSAGE_SUCCESS")
                    else:
                        log_error(bot_id, "自动消息发送失败", "WZRY_AUTO_MESSAGE_FAILED")
                else:
                    log_error(bot_id, "无法获取适配器管理器", "WZRY_AUTO_MESSAGE_NO_ADAPTER")

        except Exception as e:
            log_error(bot_id, f"发送自动消息异常: {e}", "WZRY_AUTO_MESSAGE_ERROR", error=str(e))

    def check_scan_status(self, code, bot_id=None, qq_user_id=None):
        """检查二维码扫描状态并自动登录营地"""
        try:
            log_info(bot_id or 0, f"开始检查扫描状态: {code}", "WZRY_CHECK_SCAN_START")

            # 构建检查URL
            check_url = f"{self.CHECK_SCAN_API_URL}{code}"

            # 使用统一客户端发送请求
            response = self.client.request_sync(check_url, bot_id=bot_id)

            if response and str(response.get('code')) == '200':
                data = response.get('data', {})
                ok = data.get('ok', 0)

                if ok == 1:
                    # 扫描成功，获取ticket并进行营地登录
                    ticket = data.get('ticket', '')
                    uin = data.get('uin', '')

                    if ticket:
                        log_info(bot_id or 0, f"扫描成功，开始营地登录: QQ={uin}", "WZRY_SCAN_SUCCESS")
                        return self._camp_login(ticket, uin, bot_id, qq_user_id)
                    else:
                        return MessageBuilder.text("❌ 获取登录票据失败")
                else:
                    # 还未扫描或扫描失败
                    return None  # 返回None表示继续等待
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(bot_id or 0, f"检查扫描状态失败: {error_msg}", "WZRY_CHECK_SCAN_ERROR", error=error_msg)
                return MessageBuilder.text(f"❌ 检查扫描状态失败: {error_msg}\n\n💡 请稍后重试")

        except Exception as e:
            log_error(bot_id or 0, f"检查王者荣耀扫描状态失败: {str(e)}", "WZRY_CHECK_SCAN_EXCEPTION", error=str(e))
            return MessageBuilder.text(f"❌ 检查扫描状态失败: {str(e)}")

    def _camp_login(self, ticket, uin, bot_id=None, qq_user_id=None):
        """使用ticket进行营地登录"""
        try:
            log_info(bot_id or 0, f"开始营地登录: QQ={uin}", "WZRY_CAMP_LOGIN_START")

            # 构建营地登录URL
            camp_url = f"{self.CAMP_LOGIN_API_URL}{ticket}"

            # 使用统一客户端发送请求
            response = self.client.request_sync(camp_url, bot_id=bot_id)

            if response and str(response.get('code')) == '200':
                return self._format_camp_login_result(response, uin, ticket, qq_user_id)
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(bot_id or 0, f"营地登录失败: {error_msg}", "WZRY_CAMP_LOGIN_ERROR", error=error_msg)
                return MessageBuilder.text(f"❌ 营地登录失败: {error_msg}\n\n💡 请稍后重试")

        except Exception as e:
            log_error(bot_id or 0, f"王者荣耀营地登录失败: {str(e)}", "WZRY_CAMP_LOGIN_EXCEPTION", error=str(e))
            return MessageBuilder.text(f"❌ 营地登录失败: {str(e)}")

    def _format_camp_login_result(self, response, uin, ticket, qq_user_id=None):
        """格式化营地登录结果消息"""
        try:
            data = response.get('data', {})
            user_id = data.get('user_id', '')
            role_id = data.get('role_id', '')
            role_desc = data.get('role_desc', '')

            # 存储登录信息到Redis
            if qq_user_id:
                self._save_login_info(qq_user_id, uin, ticket, data)

            # 构建登录成功消息
            content = f"🎮 QQ号：{uin}\n"
            content += f"👤 用户ID：{user_id}\n"
            content += f"🏆 角色信息：{role_desc}\n"
            content += f"✅ 登录完成，现在可以使用王者荣耀相关查询功能了！"

            log_info(0, f"用户 {uin} 王者荣耀营地登录成功", "WZRY_CAMP_LOGIN_SUCCESS",
                     uin=uin, user_id=user_id, role_desc=role_desc)

            return MessageBuilder.text_card(
                text=f"🎉 王者荣耀营地登录成功！\n\n{content}",
                description="王者荣耀营地登录",
                prompt='Yapi-免费API'
            )

        except Exception as e:
            log_error(0, f"格式化营地登录结果失败: {str(e)}", "WZRY_CAMP_FORMAT_ERROR", error=str(e))
            return MessageBuilder.text("❌ 处理登录结果失败，但登录可能已成功")

    def _save_login_info(self, qq_user_id, uin, ticket, login_data):
        """保存用户登录信息到Redis"""
        try:
            import json
            from datetime import datetime, timedelta
            from Database.Redis.client import set_value

            # 构建存储的登录信息
            login_info = {
                'qq_number': uin,
                'ticket': ticket,
                'user_id': login_data.get('user_id'),
                'role_id': login_data.get('role_id'),
                'role_desc': login_data.get('role_desc'),
                'sso_open_id': login_data.get('sso_open_id'),
                'sso_token': login_data.get('sso_token'),
                'sso_business_id': login_data.get('sso_business_id'),
                'sso_app_id': login_data.get('sso_app_id'),
                'login_time': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(minutes=30)).isoformat()  # 30分钟过期
            }

            # 存储到Redis，键格式：wzry_login:{qq_user_id}
            redis_key = f"wzry_login:{qq_user_id}"
            expire_seconds = 30 * 60  # 30分钟
            json_data = json.dumps(login_info)

            # 在应用上下文中使用Redis
            try:
                from app import app
                with app.app_context():
                    from Database.Redis.client import get_redis
                    redis_client = get_redis()
                    # 直接使用Redis存储
                    redis_client.set(redis_key, json_data, ex=expire_seconds)

                    # 立即验证
                    verify_data = redis_client.get(redis_key)

            except Exception as e:
                # 降级使用系统方法
                result = set_value(redis_key, json_data, expire_seconds)

                # 验证降级存储
                from Database.Redis.client import get_value
                verify_data = get_value(redis_key)

            log_info(0, f"王者荣耀登录信息已保存", "WZRY_LOGIN_INFO_SAVED",
                     qq_user_id=qq_user_id, wzry_qq=uin, wzry_user_id=login_data.get('user_id'))

        except Exception as e:
            log_error(0, f"保存王者荣耀登录信息失败: {e}", "WZRY_LOGIN_INFO_SAVE_ERROR", error=str(e))

    def get_login_info(self, qq_user_id):
        """获取用户登录信息"""
        try:
            import json
            from Database.Redis.client import get_value

            redis_key = f"wzry_login:{qq_user_id}"

            # 在应用上下文中使用Redis读取
            try:
                from app import app
                with app.app_context():
                    from Database.Redis.client import get_redis
                    redis_client = get_redis()
                    login_data = redis_client.get(redis_key)

            except Exception as e:
                # 降级使用系统方法
                login_data = get_value(redis_key)

            if login_data:
                result = json.loads(login_data)
                return result
            else:
                return None

        except Exception as e:
            log_error(0, f"获取王者荣耀登录信息失败: {e}", "WZRY_LOGIN_INFO_GET_ERROR", error=str(e))
            return None

    def delete_login_info(self, qq_user_id):
        """删除用户登录信息（退出登录）"""
        try:
            from Database.Redis.client import delete_key, get_value

            redis_key = f"wzry_login:{qq_user_id}"

            # 检查是否存在
            if get_value(redis_key) is not None:
                delete_key(redis_key)
                log_info(0, f"王者荣耀登录信息已删除", "WZRY_LOGIN_INFO_DELETED", qq_user_id=qq_user_id)
                return True
            else:
                return False

        except Exception as e:
            log_error(0, f"删除王者荣耀登录信息失败: {e}", "WZRY_LOGIN_INFO_DELETE_ERROR", error=str(e))
            return False

    def _format_login_message(self, response):
        """格式化登录消息"""
        try:
            data = response.get('data', {})
            qr_url = data.get('qr_url', '')
            code = data.get('code', '')

            content = f"🎮 王者荣耀QQ登录\n\n"
            content += f"💡 扫描成功后会自动回复登录结果"
            # 将URL中的qq.com替换为QQ.com
            formatted_url = qr_url.replace('qq.com', 'QQ.COM')

            # 返回消息
            return MessageBuilder.text_card_link(
                text=content,
                button_text="🔗 点击登录",
                button_url=formatted_url,
                description="王者营地",
                prompt="Yapi-免费API"
            )
        except Exception as e:
            log_error(0, f"格式化登录消息失败: {str(e)}", "WZRY_FORMAT_ERROR", error=str(e))
            return MessageBuilder.text("❌ 处理登录信息失败，请稍后重试")

    def get_economy_panel(self, login_info):
        """获取王者荣耀经济面板信息"""
        ticket = self._get_ticket_from_login_info(login_info)
        if not ticket:
            log_error(0, "登录信息中缺少ticket", "WZRY_ECONOMY_NO_TICKET")
            return None

        url = self._build_wzry_api_url(self.ACTIONS['ECONOMY'], ticket)
        economy_data = self._make_api_request(url, 0, "经济面板")

        if not economy_data:
            return None

        result = self._format_economy_panel(economy_data)
        return result

    def _format_economy_panel(self, economy_data):
        """格式化经济面板信息为ARK卡片"""
        try:
            nickname = economy_data.get('nickname', '未知')
            rolename = economy_data.get('rolename', '未知')
            area_info = economy_data.get('area_info', '未知')
            nobility_level = economy_data.get('nobility_level', '0')

            # 各种货币信息
            diamond = economy_data.get('diamond', '0')
            money = economy_data.get('money', '0')
            coin = economy_data.get('coin', '0')
            blue_coin = economy_data.get('blue_coin', '0')
            purple_coin = economy_data.get('purple_coin', '0')
            battlepass_coin = economy_data.get('battlepass_coin', '0')
            skin_coin = economy_data.get('skin_coin', '0')
            hero_coin = economy_data.get('hero_coin', '0')
            rune_coin = economy_data.get('rune_coin', '0')

            # 构建详细信息
            content = f"💰 王者荣耀经济面板\n\n"
            content += f"👤 昵称：{nickname}\n"
            content += f"🎮 角色：{rolename}\n"
            content += f"🌍 区服：{area_info}\n"
            content += f"👑 贵族等级：{nobility_level}\n\n"
            content += f"💎 钻石：{diamond}\n"
            content += f"💰 金币：{money}\n"
            content += f"🪙 点券：{coin}\n"
            content += f"🔵 蓝色精粹：{blue_coin}\n"
            content += f"🟣 紫色精粹：{purple_coin}\n"
            content += f"🎫 战令币：{battlepass_coin}\n"
            content += f"👗 皮肤币：{skin_coin}\n"
            content += f"🦸 英雄币：{hero_coin}\n"
            content += f"📿 铭文币：{rune_coin}"

            # 返回文卡消息
            result = MessageBuilder.text_card(
                text=content,
                description="王者荣耀经济面板",
                prompt="Yapi-免费API"
            )
            return result

        except Exception as e:
            log_error(0, f"格式化经济面板信息失败: {e}", "WZRY_ECONOMY_FORMAT_ERROR", error=str(e))
            return None

    def get_recent_battles(self, login_info):
        """获取最近战绩信息"""
        try:
            log_info(0, "开始获取最近战绩信息", "WZRY_BATTLES_START")

            # 从登录信息中获取ticket
            ticket = login_info.get('ticket')
            if not ticket:
                log_error(0, "登录信息中缺少ticket", "WZRY_BATTLES_NO_TICKET")
                return None

            # 构建API请求URL
            url = f"https://api.makuo.cc/api/get.game.wzry?action=最近战绩&ticket={ticket}"

            log_info(0, f"请求最近战绩信息", "WZRY_BATTLES_REQUEST")
            # 使用统一客户端发送请求
            response = self.client.request_sync(url, bot_id=0)
            log_info(0, f"最近战绩API响应: {response}", "WZRY_BATTLES_RESPONSE")

            if response and str(response.get('code')) == '200':
                # 解析最近战绩数据
                battles_data = response.get('data', {})

                if not battles_data:
                    log_error(0, "最近战绩数据为空", "WZRY_BATTLES_EMPTY_DATA")
                    return None
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(0, f"最近战绩API返回错误: {error_msg}", "WZRY_BATTLES_API_ERROR")
                return None

            # 格式化最近战绩信息
            result = self._format_recent_battles(battles_data)
            return result

        except Exception as e:
            log_error(0, f"获取最近战绩失败: {e}", "WZRY_BATTLES_EXCEPTION", error=str(e))
            return None

    def _format_recent_battles(self, battles_data):
        """格式化最近战绩信息为文卡"""
        try:

            battles = battles_data.get('battles', [])
            total = battles_data.get('total', 0)

            if not battles:
                return MessageBuilder.text("❌ 暂无战绩数据")

            # 构建战绩内容
            content = f"🎮 王者荣耀最近战绩\n\n"
            content += f"📊 总计：{total} 场比赛\n\n"

            # 显示前5场战绩
            for i, battle in enumerate(battles[:5]):
                game_time = battle.get('game_time', '未知时间')
                kill_count = battle.get('kill_count', 0)
                death_count = battle.get('death_count', 0)
                assist_count = battle.get('assist_count', 0)
                map_name = battle.get('map_name', '未知模式')
                description = battle.get('description', '')
                role_job_name = battle.get('role_job_name', '未知段位')
                game_result = battle.get('game_result', '未知')
                hero_id = battle.get('hero_id', 0)

                # 结果图标
                result_icon = "🏆" if game_result == "获胜" else "💔"

                # KDA信息
                kda = f"{kill_count}/{death_count}/{assist_count}"

                content += f"{result_icon} {game_time}\n"
                content += f"🗺️ {map_name} | {role_job_name}\n"
                content += f"⚔️ KDA: {kda}"
                if description:
                    content += f" | {description}"
                content += f"\n"
                if i < 4 and i < len(battles) - 1:  # 不是最后一个
                    content += "\n"

            if total > 5:
                content += f"\n📝 仅显示最近5场，共{total}场比赛"

            # 返回文卡消息
            result = MessageBuilder.text_card(
                text=content,
                description="王者荣耀最近战绩",
                prompt="Yapi-免费API"
            )
            return result

        except Exception as e:
            log_error(0, f"格式化最近战绩信息失败: {e}", "WZRY_BATTLES_FORMAT_ERROR", error=str(e))
            return None

    def get_details_info(self, login_info):
        """获取具体信息（英雄和皮肤统计）"""
        try:
            log_info(0, "开始获取具体信息", "WZRY_DETAILS_START")

            # 从登录信息中获取ticket
            ticket = login_info.get('ticket')
            if not ticket:
                log_error(0, "登录信息中缺少ticket", "WZRY_DETAILS_NO_TICKET")
                return None

            # 构建API请求URL
            url = f"https://api.makuo.cc/api/get.game.wzry?action=具体信息&ticket={ticket}"

            log_info(0, f"请求具体信息", "WZRY_DETAILS_REQUEST")
            # 使用统一客户端发送请求
            response = self.client.request_sync(url, bot_id=0)
            log_info(0, f"具体信息API响应: {response}", "WZRY_DETAILS_RESPONSE")

            if response and str(response.get('code')) == '200':
                # 解析具体信息数据
                details_data = response.get('data', {})

                if not details_data:
                    log_error(0, "具体信息数据为空", "WZRY_DETAILS_EMPTY_DATA")
                    return None
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(0, f"具体信息API返回错误: {error_msg}", "WZRY_DETAILS_API_ERROR")
                return None

            # 格式化具体信息
            result = self._format_details_info(details_data)
            return result

        except Exception as e:
            log_error(0, f"获取具体信息失败: {e}", "WZRY_DETAILS_EXCEPTION", error=str(e))
            return None

    def _format_details_info(self, details_data):
        """格式化具体信息为文卡"""
        try:

            skin_info = details_data.get('skin_info', {})
            hero_info = details_data.get('hero_info', {})

            # 构建具体信息内容
            content = f"🎮 王者荣耀具体信息\n\n"

            # 皮肤信息
            if skin_info:
                content += f"👗 皮肤统计\n"
                content += f"💎 总价值：{skin_info.get('total_value', 0):,} 点券\n"
                content += f"📦 拥有数量：{skin_info.get('owned', 0)}/{skin_info.get('total_skin_num', 0)}\n"
                content += f"🚫 非卖品：{skin_info.get('not_for_sell', 0)} 个\n"

                # 皮肤类型统计
                skin_types = skin_info.get('skin_types', {})
                if skin_types:
                    content += f"📊 皮肤类型：\n"
                    type_names = {
                        'glory': '荣耀',
                        'epic': '史诗',
                        'legend': '传说',
                        'warrior': '勇者',
                        'battle_pass': '战令',
                        'seasonal': '赛季',
                        'activity_limited': '活动限定',
                        'annual_limited': '年度限定'
                    }
                    for key, value in skin_types.items():
                        if key in type_names:
                            content += f"  • {type_names[key]}：{value}\n"
                content += "\n"

            # 英雄信息
            if hero_info:
                content += f"🦸 英雄统计\n"
                content += f"💰 总价值：{hero_info.get('total_value', 0):,} 金币\n"
                content += f"👥 拥有数量：{hero_info.get('owned', 0)}/{hero_info.get('total_hero_num', 0)}\n"
                content += f"🚫 非卖品：{hero_info.get('not_for_sell', 0)} 个\n"

                # 技能等级统计
                skill_levels = hero_info.get('skill_levels', {})
                if skill_levels:
                    content += f"⚔️ 技能等级：\n"
                    level_names = {
                        'novice': '新手',
                        'senior': '资深',
                        'elite': '精英',
                        'master': '大师',
                        'extraordinary': '非凡',
                        'peak': '巅峰',
                        'legend': '传奇',
                        'myth': '神话'
                    }
                    for key, value in skill_levels.items():
                        if key in level_names and value > 0:
                            content += f"  • {level_names[key]}：{value} 个\n"

                # 荣誉称号统计
                honor_titles = hero_info.get('honor_titles', {})
                if honor_titles:
                    total_titles = sum(honor_titles.values())
                    if total_titles > 0:
                        content += f"🏆 荣誉称号：\n"
                        title_names = {
                            'junior': '初级',
                            'intermediate': '中级',
                            'senior': '高级',
                            'top': '顶级',
                            'national': '国服'
                        }
                        for key, value in honor_titles.items():
                            if key in title_names and value > 0:
                                content += f"  • {title_names[key]}：{value} 个\n"

            # 返回文卡消息
            result = MessageBuilder.text_card(
                text=content,
                description="王者荣耀具体信息",
                prompt="Yapi-免费API"
            )
            return result

        except Exception as e:
            log_error(0, f"格式化具体信息失败: {e}", "WZRY_DETAILS_FORMAT_ERROR", error=str(e))
            return None

    def get_camp_info(self, login_info):
        """获取营地信息"""
        try:
            log_info(0, "开始获取营地信息", "WZRY_CAMP_INFO_START")

            # 从登录信息中获取ticket
            ticket = login_info.get('ticket')
            if not ticket:
                log_error(0, "登录信息中缺少ticket", "WZRY_CAMP_INFO_NO_TICKET")
                return None

            # 构建API请求URL
            url = f"https://api.makuo.cc/api/get.game.wzry?action=营地信息&ticket={ticket}"

            log_info(0, f"请求营地信息", "WZRY_CAMP_INFO_REQUEST")
            # 使用统一客户端发送请求
            response = self.client.request_sync(url, bot_id=0)
            log_info(0, f"营地信息API响应: {response}", "WZRY_CAMP_INFO_RESPONSE")

            if response and str(response.get('code')) == '200':
                # 解析营地信息数据
                camp_data = response.get('data', {})

                if not camp_data:
                    log_error(0, "营地信息数据为空", "WZRY_CAMP_INFO_EMPTY_DATA")
                    return None
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(0, f"营地信息API返回错误: {error_msg}", "WZRY_CAMP_INFO_API_ERROR")
                return None

            # 格式化营地信息
            result = self._format_camp_info(camp_data)
            return result

        except Exception as e:
            log_error(0, f"获取营地信息失败: {e}", "WZRY_CAMP_INFO_EXCEPTION", error=str(e))
            return None

    def _format_camp_info(self, camp_data):
        """格式化营地信息为文卡"""
        try:

            # 基本信息
            user_id = camp_data.get('user_id', '未知')
            level = camp_data.get('level', 0)
            star_num = camp_data.get('star_num', 0)
            role_name = camp_data.get('role_name', '未知')
            role_job_name = camp_data.get('role_job_name', '未知')
            area_name = camp_data.get('area_name', '未知')
            server_name = camp_data.get('server_name', '未知')
            fight_power = camp_data.get('fight_power', '0')
            total_battle_num = camp_data.get('total_battle_num', '0')
            win_rate = camp_data.get('win_rate', '0%')
            mvp_num = camp_data.get('mvp_num', '0')
            hero_owned = camp_data.get('hero_owned', '0')
            hero_total = camp_data.get('hero_total', '0')
            skin_owned = camp_data.get('skin_owned', '0')
            skin_total = camp_data.get('skin_total', '0')

            # 构建营地信息内容
            content = f"🏕️ 王者荣耀营地信息\n\n"

            # 玩家基本信息
            content += f"👤 玩家信息\n"
            content += f"🎮 游戏昵称：{role_name}\n"
            content += f"🏆 当前段位：{role_job_name}"
            if star_num > 0:
                content += f" {star_num}星"
            content += f"\n"
            content += f"📍 服务器：{area_name} {server_name}\n"
            content += f"⭐ 营地等级：{level}\n"
            content += f"⚔️ 战力：{fight_power}\n\n"

            # 战绩统计
            content += f"📊 战绩统计\n"
            content += f"🎯 总场次：{total_battle_num}\n"
            content += f"🏅 胜率：{win_rate}\n"
            content += f"👑 MVP次数：{mvp_num}\n\n"

            # 收集统计
            content += f"📦 收集统计\n"
            content += f"🦸 英雄：{hero_owned}/{hero_total}\n"
            content += f"👗 皮肤：{skin_owned}/{skin_total}\n"

            # 常用英雄
            common_heroes = camp_data.get('common_heroes', [])
            if common_heroes:
                content += f"\n🌟 常用英雄\n"
                for i, hero in enumerate(common_heroes[:3]):  # 显示前3个
                    title = hero.get('title', '未知英雄')
                    play_num = hero.get('play_num', 0)
                    win_rate = hero.get('win_rate', '0%')
                    hero_fight_power = hero.get('hero_fight_power', 0)

                    content += f"  {i + 1}. {title}\n"
                    content += f"     🎮 {play_num}场 | 🏅 {win_rate} | ⚔️ {hero_fight_power}\n"

            # 返回文卡消息
            result = MessageBuilder.text_card(
                text=content,
                description="王者荣耀营地信息",
                prompt="Yapi-免费API"
            )
            return result

        except Exception as e:
            log_error(0, f"格式化营地信息失败: {e}", "WZRY_CAMP_INFO_FORMAT_ERROR", error=str(e))
            return None

    def get_season_stats(self, login_info):
        """获取赛季统计信息"""
        try:
            log_info(0, "开始获取赛季统计信息", "WZRY_SEASON_STATS_START")

            # 从登录信息中获取ticket
            ticket = login_info.get('ticket')
            if not ticket:
                log_error(0, "登录信息中缺少ticket", "WZRY_SEASON_STATS_NO_TICKET")
                return None

            # 构建API请求URL
            url = f"https://api.makuo.cc/api/get.game.wzry?action=赛季统计&ticket={ticket}"

            log_info(0, f"请求赛季统计信息", "WZRY_SEASON_STATS_REQUEST")
            # 使用统一客户端发送请求
            response = self.client.request_sync(url, bot_id=0)
            log_info(0, f"赛季统计API响应: {response}", "WZRY_SEASON_STATS_RESPONSE")

            if response and str(response.get('code')) == '200':
                # 解析赛季统计数据
                season_data = response.get('data', {})

                if not season_data:
                    log_error(0, "赛季统计数据为空", "WZRY_SEASON_STATS_EMPTY_DATA")
                    return None
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(0, f"赛季统计API返回错误: {error_msg}", "WZRY_SEASON_STATS_API_ERROR")
                return None

            # 格式化赛季统计信息
            result = self._format_season_stats(season_data)
            return result

        except Exception as e:
            log_error(0, f"获取赛季统计失败: {e}", "WZRY_SEASON_STATS_EXCEPTION", error=str(e))
            return None

    def _format_season_stats(self, season_data):
        """格式化赛季统计信息为文卡"""
        try:

            basic_info = season_data.get('basic_info', {})
            battle_stats = season_data.get('battle_stats', {})
            common_heroes = season_data.get('common_heroes', [])
            branch_stats = season_data.get('branch_stats', [])

            # 构建赛季统计内容
            content = f"📊 王者荣耀赛季统计\n\n"

            # 基本信息
            if basic_info:
                role_name = basic_info.get('role_name', '未知')
                job_name = basic_info.get('job_name', '未知')
                ranking_star = basic_info.get('ranking_star', 0)
                score = basic_info.get('score', 0)
                game_count = basic_info.get('game_count', 0)
                branch = basic_info.get('branch', '未知')

                content += f"👤 基本信息\n"
                content += f"🎮 昵称：{role_name}\n"
                content += f"🏆 段位：{job_name} {ranking_star}星\n"
                content += f"⭐ 积分：{score}\n"
                content += f"🎯 场次：{game_count}\n"
                content += f"🛤️ 主路：{branch}\n\n"

            # 战绩统计（如果有数据）
            if battle_stats and any(v is not None for v in battle_stats.values()):
                content += f"⚔️ 战绩统计\n"
                if battle_stats.get('win_rate') is not None:
                    win_rate = battle_stats['win_rate']
                    # 处理胜率格式：如果已经是字符串（如"70.4%"），直接使用；如果是数字，格式化为百分比
                    if isinstance(win_rate, str):
                        content += f"🏅 胜率：{win_rate}\n"
                    else:
                        content += f"🏅 胜率：{win_rate:.1%}\n"
                if battle_stats.get('avg_score') is not None:
                    content += f"📈 平均分：{battle_stats['avg_score']}\n"
                if battle_stats.get('mvp') is not None:
                    content += f"👑 MVP：{battle_stats['mvp']}\n"
                if battle_stats.get('god_like') is not None:
                    content += f"🔥 超神：{battle_stats['god_like']}\n"
                if battle_stats.get('three_kill') is not None:
                    content += f"⚡ 三杀：{battle_stats['three_kill']}\n"
                if battle_stats.get('four_kill') is not None:
                    content += f"💥 四杀：{battle_stats['four_kill']}\n"
                if battle_stats.get('five_kill') is not None:
                    content += f"🌟 五杀：{battle_stats['five_kill']}\n"
                if battle_stats.get('lose_mvp') is not None:
                    content += f"💔 败方MVP：{battle_stats['lose_mvp']}\n"
                content += "\n"

            # 常用英雄
            if common_heroes:
                content += f"🌟 常用英雄\n"
                for i, hero in enumerate(common_heroes[:5]):  # 显示前5个
                    hero_name = hero.get('hero_name', '未知英雄')
                    hero_role = hero.get('hero_role', '未知')
                    win_rate = hero.get('win_rate', 0)
                    game_count = hero.get('game_count', 0)

                    # 处理胜率格式：如果是字符串直接使用，如果是数字格式化为百分比
                    if isinstance(win_rate, str):
                        win_rate_str = win_rate
                    else:
                        win_rate_str = f"{win_rate:.1%}"

                    content += f"  {i + 1}. {hero_name} ({hero_role})\n"
                    content += f"     🎮 {game_count}场 | 🏅 {win_rate_str}\n"
                content += "\n"

            # 分路统计（只显示有比赛的分路）
            if branch_stats:
                content += f"🛤️ 分路统计\n"
                for branch in branch_stats:
                    branch_name = branch.get('branch_name', '未知')
                    win_num = branch.get('win_num', 0)
                    lose_num = branch.get('lose_num', 0)
                    win_rate = branch.get('win_rate', '0%')
                    game_count = branch.get('game_count', 0)

                    # 只显示有比赛记录的分路
                    if game_count > 0:
                        content += f"  • {branch_name}：{game_count}场 ({win_rate})\n"
                        content += f"    胜{win_num} 负{lose_num}\n"

            # 返回文卡消息
            result = MessageBuilder.text_card(
                text=content,
                description="王者荣耀赛季统计",
                prompt="Yapi-免费API"
            )
            return result

        except Exception as e:
            log_error(0, f"格式化赛季统计失败: {e}", "WZRY_SEASON_STATS_FORMAT_ERROR", error=str(e))
            return None

    def get_hero_hotness(self, login_info):
        """获取英雄热度排行"""
        try:
            log_info(0, "开始获取英雄热度排行", "WZRY_HERO_HOTNESS_START")

            # 从登录信息中获取ticket
            ticket = login_info.get('ticket')
            if not ticket:
                log_error(0, "登录信息中缺少ticket", "WZRY_HERO_HOTNESS_NO_TICKET")
                return None

            # 构建API请求URL
            url = f"https://api.makuo.cc/api/get.game.wzry?action=英雄热度&ticket={ticket}"

            log_info(0, f"请求英雄热度排行", "WZRY_HERO_HOTNESS_REQUEST")
            # 使用统一客户端发送请求
            response = self.client.request_sync(url, bot_id=0)
            log_info(0, f"英雄热度API响应: {response}", "WZRY_HERO_HOTNESS_RESPONSE")

            if response and str(response.get('code')) == '200':
                # 解析英雄热度数据
                hotness_data = response.get('data', {})

                if not hotness_data:
                    log_error(0, "英雄热度数据为空", "WZRY_HERO_HOTNESS_EMPTY_DATA")
                    return None
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(0, f"英雄热度API返回错误: {error_msg}", "WZRY_HERO_HOTNESS_API_ERROR")
                return None

            # 格式化英雄热度信息
            result = self._format_hero_hotness(hotness_data)
            return result

        except Exception as e:
            log_error(0, f"获取英雄热度失败: {e}", "WZRY_HERO_HOTNESS_EXCEPTION", error=str(e))
            return None

    def _format_hero_hotness(self, hotness_data):
        """格式化英雄热度排行为文卡"""
        try:

            hotness_ranking = hotness_data.get('hotness_ranking', [])

            if not hotness_ranking:
                return MessageBuilder.text("❌ 暂无英雄热度数据")

            # 构建英雄热度内容
            content = f"🔥 王者荣耀英雄热度排行\n\n"

            # 按等级分组显示
            tier_groups = {}
            for hero in hotness_ranking:
                rank = hero.get('rank', 'Unknown')
                if rank not in tier_groups:
                    tier_groups[rank] = []
                tier_groups[rank].append(hero)

            # 定义等级顺序和图标
            tier_order = ['T0', 'T1', 'T2', 'T3', 'T4']
            tier_icons = {
                'T0': '🔥',
                'T1': '⭐',
                'T2': '✨',
                'T3': '💫',
                'T4': '🌟'
            }

            # 按等级顺序显示
            for tier in tier_order:
                if tier in tier_groups:
                    heroes = tier_groups[tier]
                    icon = tier_icons.get(tier, '📊')
                    content += f"{icon} {tier}级英雄 ({len(heroes)}个)\n"

                    # 每行显示3个英雄
                    for i in range(0, len(heroes), 3):
                        line_heroes = heroes[i:i + 3]
                        hero_names = []
                        for hero in line_heroes:
                            hero_name = hero.get('hero_name', '未知')
                            hero_career = hero.get('hero_career', '未知')
                            hero_names.append(f"{hero_name}({hero_career})")
                        content += f"  {' | '.join(hero_names)}\n"
                    content += "\n"

            # 添加说明
            content += "📝 说明：T0为最热门，T1次之，以此类推"

            # 返回文卡消息
            result = MessageBuilder.text_card(
                text=content,
                description="王者荣耀英雄热度排行",
                prompt="Yapi-免费API"
            )
            return result

        except Exception as e:
            log_error(0, f"格式化英雄热度失败: {e}", "WZRY_HERO_HOTNESS_FORMAT_ERROR", error=str(e))
            return None

    def get_build_recommend(self, login_info, hero_name):
        """获取英雄出装推荐"""
        try:
            log_info(0, f"开始获取{hero_name}出装推荐", "WZRY_BUILD_RECOMMEND_START")

            # 从登录信息中获取ticket
            ticket = login_info.get('ticket')
            if not ticket:
                log_error(0, "登录信息中缺少ticket", "WZRY_BUILD_RECOMMEND_NO_TICKET")
                return None

            # 构建API请求URL
            url = f"https://api.makuo.cc/api/get.game.wzry?action=出装推荐&ticket={ticket}&heroName={hero_name}"

            log_info(0, f"请求{hero_name}出装推荐", "WZRY_BUILD_RECOMMEND_REQUEST")
            # 使用统一客户端发送请求
            response = self.client.request_sync(url, bot_id=0)
            log_info(0, f"出装推荐API响应: {response}", "WZRY_BUILD_RECOMMEND_RESPONSE")

            if response and str(response.get('code')) == '200':
                # 解析出装推荐数据
                build_data = response.get('data', {})

                if not build_data:
                    log_error(0, "出装推荐数据为空", "WZRY_BUILD_RECOMMEND_EMPTY_DATA")
                    return None
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(0, f"出装推荐API返回错误: {error_msg}", "WZRY_BUILD_RECOMMEND_API_ERROR")
                return None

            # 格式化出装推荐信息
            result = self._format_build_recommend(build_data)
            return result

        except Exception as e:
            log_error(0, f"获取出装推荐失败: {e}", "WZRY_BUILD_RECOMMEND_EXCEPTION", error=str(e))
            return None

    def _format_build_recommend(self, build_data):
        """格式化出装推荐信息为文卡"""
        try:

            hero_name = build_data.get('hero_name', '未知英雄')
            builds = build_data.get('builds', [])

            if not builds:
                return MessageBuilder.text(f"❌ 暂无{hero_name}的出装推荐数据")

            # 构建出装推荐内容
            content = f"⚔️ {hero_name} 出装推荐\n\n"

            # 显示前3个推荐套装
            for i, build in enumerate(builds[:3]):
                player_name = build.get('player_name', '未知玩家')
                build_name = build.get('build_name', '推荐套装')
                skill = build.get('skill', '闪现')
                runes = build.get('runes', [])
                equipment = build.get('equipment', [])

                content += f"🏆 套装{i + 1}：{build_name}\n"
                content += f"👤 推荐者：{player_name}\n"
                content += f"✨ 召唤师技能：{skill}\n\n"

                # 铭文推荐
                if runes:
                    content += f"📜 铭文搭配：\n"
                    for rune in runes:
                        content += f"  • {rune}\n"
                    content += "\n"

                # 装备推荐
                if equipment:
                    content += f"🛡️ 装备推荐：\n"
                    for j, item in enumerate(equipment):
                        content += f"  {j + 1}. {item}\n"
                    content += "\n"

                # 分隔线（除了最后一个）
                if i < min(len(builds), 3) - 1:
                    content += "─" * 20 + "\n\n"

            # 如果有更多套装，显示提示
            if len(builds) > 3:
                content += f"\n💡 共有{len(builds)}套推荐，已显示前3套"

            # 返回文卡消息
            result = MessageBuilder.text_card(
                text=content,
                description=f"{hero_name}出装推荐",
                prompt="Yapi-免费API"
            )
            return result

        except Exception as e:
            log_error(0, f"格式化出装推荐失败: {e}", "WZRY_BUILD_RECOMMEND_FORMAT_ERROR", error=str(e))
            return None
