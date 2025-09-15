"""
Yapi插件 - 对接多个API端点
"""

from Core.logging.file_logger import log_info, log_error
from Core.message.builder import MessageBuilder
from Core.plugin.base import BasePlugin
from .client import yapi_client
from .endpoints.comment import CommentAPI
from .endpoints.constellation import ConstellationAPI
from .endpoints.douyin import DouyinAPI
from .endpoints.icp import ICPAPI
from .endpoints.poetry import PoetryAPI
from .endpoints.qq_info import QQInfoAPI
from .endpoints.wzry import WzryAPI


# 常量定义
class Constants:
    """插件常量"""
    # 错误消息
    WZRY_NOT_LOGGED_IN = "❌ 您还没有登录王者荣耀营地，请先使用'王者登录'命令"
    WZRY_REQUEST_FAILED = "❌ 请求失败，请稍后重试"

    # 王者荣耀命令列表
    WZRY_COMMANDS = {
        '王者登录', '退出登录', '经济面板', '最近战绩',
        '具体信息', '营地信息', '赛季统计', '英雄热度', '出装推荐', '王者帮助'
    }

    # 需要message_data的命令列表
    MESSAGE_DATA_COMMANDS = {
        '等级信息'
    }

    # 支持的星座
    VALID_CONSTELLATIONS = [
        '白羊座', '金牛座', '双子座', '巨蟹座', '狮子座', '处女座',
        '天秤座', '天蝎座', '射手座', '摩羯座', '水瓶座', '双鱼座'
    ]


class Plugin(BasePlugin):
    """Yapi API集成插件"""

    def __init__(self):
        super().__init__()
        self.name = "Yapi"
        self.version = "1.0.0"
        self.description = "Yapi API集成插件！"
        self.author = "Yixuan"

        # 使用统一的客户端
        self.client = yapi_client

        # 初始化API端点
        self.poetry_api = PoetryAPI()
        self.comment_api = CommentAPI()
        self.icp_api = ICPAPI()
        self.constellation_api = ConstellationAPI()
        self.douyin_api = DouyinAPI()
        self.wzry_api = WzryAPI(self.client)
        self.qq_info_api = QQInfoAPI(self.client)
        # 未来可以添加更多端点：

        # 注册命令信息（用于展示和帮助）
        self.register_command_info('诗词', '获取随机诗词名句', '/诗词 或 诗词')
        self.register_command_info('热评', '获取随机热评名句', '/热评 或 热评')
        self.register_command_info('备案', '查询域名ICP备案信息', '/备案 <域名> 或 备案 <域名>')
        self.register_command_info('星座', '查询星座今日运势', '/星座 <星座名> 或 星座 <星座名>')
        self.register_command_info('抖音', '解析抖音视频并发送无水印视频', '/抖音 <链接> 或 抖音 <链接>')
        self.register_command_info('王者登录', '获取王者荣耀登录二维码（自动检测登录状态）', '/王者登录 或 王者登录')
        self.register_command_info('经济面板', '查看王者荣耀经济面板信息', '/经济面板 或 经济面板')
        self.register_command_info('具体信息', '查看王者荣耀经济具体', '/具体信息 或 具体信息')
        self.register_command_info('营地信息', '查看王者荣耀营地信息', '/营地信息 或 营地信息')
        self.register_command_info('赛季统计', '查看王者荣耀赛季统计', '/赛季统计 或 赛季统计')
        self.register_command_info('英雄热度', '查看王者荣耀英雄热度排行', '/英雄热度 或 英雄热度')
        self.register_command_info('出装推荐', '查看王者荣耀英雄出装推荐', '/出装推荐 英雄名 或 出装推荐 英雄名')
        self.register_command_info('王者帮助', '显示王者荣耀功能菜单', '/王者帮助 或 王者帮助')
        self.register_command_info('等级信息', '查询QQ等级信息', '/等级信息 或 等级信息')
        self.register_command_info('yapi', 'Yapi API集成服务管理', '/yapi help')

        # 命令处理器
        self.command_handlers = {
            '诗词': self.handle_poetry_command,
            '热评': self.handle_comment_command,
            '备案': self.handle_icp_command,
            '星座': self.handle_constellation_command,
            '抖音': self.handle_douyin_command,
            '王者登录': self.handle_wzry_login_command,
            '退出登录': self.handle_wzry_logout_command,
            '经济面板': self.handle_wzry_economy_command,
            '最近战绩': self.handle_wzry_battles_command,
            '具体信息': self.handle_wzry_details_command,
            '营地信息': self.handle_wzry_camp_info_command,
            '赛季统计': self.handle_wzry_season_stats_command,
            '英雄热度': self.handle_wzry_hero_hotness_command,
            '出装推荐': self.handle_wzry_build_recommend_command,
            '王者帮助': self.handle_wzry_help_command,
            '等级信息': self.handle_qq_level_command,
            'yapi': self.handle_yapi_command
        }

        # 注册Hook事件处理器
        self.hooks = {
            'message_received': [self.handle_message_hook],
            'bot_start': [self.on_bot_start_hook],
            'bot_stop': [self.on_bot_stop_hook]
        }

        log_info(0, "Yapi插件初始化完成", "YAPI_PLUGIN_INIT")

    # ===== 通用方法 =====

    def _check_wzry_login(self, user_id):
        """检查王者荣耀登录状态"""
        login_info = self.wzry_api.get_login_info(user_id)
        if not login_info:
            return None, MessageBuilder.text(Constants.WZRY_NOT_LOGGED_IN)
        return login_info, None

    def _handle_wzry_command(self, command_name, api_method, user_id, bot_id, args=None, error_msg=None):
        """通用王者荣耀命令处理器"""
        try:
            log_info(bot_id or 0, f"处理{command_name}命令 - user_id: {user_id}",
                     f"YAPI_WZRY_{command_name.upper()}_COMMAND")

            # 检查登录状态
            login_info, login_error = self._check_wzry_login(user_id)
            if login_error:
                return login_error

            # 调用API方法
            if args is not None:
                result = api_method(login_info, *args)
            else:
                result = api_method(login_info)

            if result:
                return result
            else:
                return MessageBuilder.text(error_msg or Constants.WZRY_REQUEST_FAILED)

        except Exception as e:
            log_error(bot_id or 0, f"处理{command_name}命令失败: {e}",
                      f"YAPI_WZRY_{command_name.upper()}_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(error_msg or Constants.WZRY_REQUEST_FAILED)

    def _get_target_from_message(self, message_data, user_id):
        """从消息数据中获取目标信息"""
        if not message_data:
            return f"user:{user_id}" if user_id else None

        message_type = message_data.get('type', 'c2c')
        if message_type == 'group_at':
            group_openid = message_data.get('group_openid')
            return f"group:{group_openid}" if group_openid else None
        else:
            return f"user:{user_id}" if user_id else None

    # ===== Hook事件处理器 =====

    def handle_message_hook(self, message_data, user_id=None, bot_id=None):
        """处理消息Hook"""
        try:
            content = message_data.get('content', '').strip()

            # 处理命令（带/或不带/）
            command_result = self._handle_smart_command(content, bot_id, message_data, user_id)
            if command_result.get('handled'):
                return command_result

            return {'handled': False}

        except Exception as e:
            log_error(bot_id or 0, f"Yapi插件处理消息异常: {e}", "YAPI_HOOK_ERROR", error=str(e))
            return {'handled': False}

    def _handle_smart_command(self, content, bot_id, message_data=None, user_id=None):
        """简化的命令处理"""
        # 去掉可能的斜杠前缀
        command_text = content[1:] if content.startswith('/') else content

        # 解析命令和参数
        parts = command_text.split()
        if not parts:
            return {'handled': False}

        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        # 检查命令是否存在（支持大小写不敏感的英文命令）
        handler = None
        if command in self.command_handlers:
            handler = self.command_handlers[command]
        elif command.lower() in self.command_handlers:
            handler = self.command_handlers[command.lower()]

        if not handler:
            return {'handled': False}

        # 执行命令
        try:
            # 王者相关命令需要额外参数
            if command in Constants.WZRY_COMMANDS:
                response = handler(args, bot_id, user_id=user_id, message_data=message_data)
            # 需要message_data的命令
            elif command in Constants.MESSAGE_DATA_COMMANDS:
                response = handler(args, bot_id, user_id=user_id, message_data=message_data)
            else:
                response = handler(args, bot_id)

            return {'handled': True, 'response': response}

        except Exception as e:
            log_error(bot_id or 0, f"执行命令 {command} 失败: {e}", "YAPI_COMMAND_ERROR",
                      command=command, error=str(e))
            return {'handled': True, 'response': MessageBuilder.text(f"❌ 命令执行失败: {str(e)}")}

    def on_bot_start_hook(self, bot_id):
        """机器人启动Hook"""
        try:
            log_info(bot_id, "Yapi插件已为机器人准备就绪", "YAPI_BOT_START")
            return {'message': f'Yapi插件已为机器人 {bot_id} 准备就绪'}
        except Exception as e:
            log_error(bot_id, f"Yapi插件启动Hook异常: {e}", "YAPI_BOT_START_ERROR", error=str(e))
            return {'message': f'Yapi插件启动异常: {str(e)}'}

    def on_bot_stop_hook(self, bot_id):
        """机器人停止Hook"""
        try:
            log_info(bot_id, "Yapi插件正在清理资源", "YAPI_BOT_STOP")
            # 这里可以添加资源清理逻辑，比如关闭HTTP连接
            # await self.client.close()
            return {'message': f'Yapi插件已为机器人 {bot_id} 清理资源'}
        except Exception as e:
            log_error(bot_id, f"Yapi插件停止Hook异常: {e}", "YAPI_BOT_STOP_ERROR", error=str(e))
            return {'message': f'Yapi插件停止异常: {str(e)}'}

    # ===== 命令处理器 =====
    def handle_poetry_command(self, args, bot_id):
        """处理诗词命令"""
        try:
            # args参数预留给未来扩展（如指定诗词类型等）
            _ = args  # 标记参数已使用，避免警告
            return self.poetry_api.get_random_poetry(bot_id=bot_id)
        except Exception as e:
            log_error(bot_id or 0, f"处理诗词命令失败: {e}", "YAPI_POETRY_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 获取诗词失败: {str(e)}")

    def handle_comment_command(self, args, bot_id):
        """处理热评命令"""
        try:
            # args参数预留给未来扩展（如指定热评类型等）
            _ = args  # 标记参数已使用，避免警告
            return self.comment_api.get_random_comment(bot_id=bot_id)
        except Exception as e:
            log_error(bot_id or 0, f"处理热评命令失败: {e}", "YAPI_COMMENT_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 获取热评失败: {str(e)}")

    def handle_icp_command(self, args, bot_id):
        """处理ICP备案查询命令"""
        try:
            if not args:
                return MessageBuilder.text("❌ 请提供要查询的域名\n\n💡 使用方法：/备案 baidu.com 或 备案 baidu.com")

            domain = args[0].strip()
            # 简单的域名格式验证
            if not domain or '.' not in domain:
                return MessageBuilder.text("❌ 域名格式不正确\n\n💡 请输入正确的域名，如：baidu.com")

            return self.icp_api.query_icp(domain, bot_id=bot_id)
        except Exception as e:
            log_error(bot_id or 0, f"处理ICP查询命令失败: {e}", "YAPI_ICP_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 查询ICP备案失败: {str(e)}")

    def handle_constellation_command(self, args, bot_id):
        """处理星座运势查询命令"""
        try:
            if not args:
                return MessageBuilder.text(
                    "❌ 请提供要查询的星座名称\n\n💡 使用方法：/星座 白羊座 或 星座 白羊座\n\n支持的星座：白羊座、金牛座、双子座、巨蟹座、狮子座、处女座、天秤座、天蝎座、射手座、摩羯座、水瓶座、双鱼座")

            constellation_name = args[0].strip()
            # 简单的星座名称验证
            if constellation_name not in Constants.VALID_CONSTELLATIONS:
                return MessageBuilder.text(
                    f"❌ 不支持的星座名称：{constellation_name}\n\n💡 支持的星座：{', '.join(Constants.VALID_CONSTELLATIONS)}")

            return self.constellation_api.query_constellation(constellation_name, bot_id=bot_id)
        except Exception as e:
            log_error(bot_id or 0, f"处理星座查询命令失败: {e}", "YAPI_CONSTELLATION_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 查询星座运势失败: {str(e)}")

    def handle_douyin_command(self, args, bot_id):
        """处理抖音视频解析命令"""
        try:
            if not args:
                return MessageBuilder.text(
                    "❌ 请提供抖音分享内容\n\n💡 使用方法：抖音 <完整分享内容>\n\n示例：抖音 8.28 复制打开抖音，看看【作品】... https://v.douyin.com/xxx")

            # 将所有参数合并为一个字符串（可能包含完整的分享文本）
            url_or_text = ' '.join(args)

            return self.douyin_api.parse_douyin_video(url_or_text, bot_id=bot_id)

        except Exception as e:
            return MessageBuilder.text(f"❌ 解析抖音视频失败: {str(e)}")

    def handle_wzry_login_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀登录命令"""
        try:
            _ = args  # 标记参数已使用，避免警告
            log_info(bot_id or 0, "处理王者荣耀登录命令", "YAPI_WZRY_LOGIN_COMMAND")

            # 获取原始消息ID和目标信息
            original_msg_id = message_data.get('msg_id') if message_data else None
            target = self._get_target_from_message(message_data, user_id)

            # 调用API获取登录二维码
            return self.wzry_api.get_login_qr(
                bot_id=bot_id,
                user_id=user_id,
                target=target,
                original_msg_id=original_msg_id
            )

        except Exception as e:
            log_error(bot_id or 0, f"处理王者荣耀登录命令失败: {e}", "YAPI_WZRY_LOGIN_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 获取王者荣耀登录二维码失败: {str(e)}")

    def handle_wzry_logout_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀退出登录命令"""
        try:
            _ = args  # 标记参数已使用，避免警告
            _ = message_data  # 标记参数已使用，避免警告
            log_info(bot_id or 0, "处理王者荣耀退出登录命令", "YAPI_WZRY_LOGOUT_COMMAND")

            # 检查是否有登录信息
            login_info = self.wzry_api.get_login_info(user_id)
            if not login_info:
                return MessageBuilder.text("❌ 您还没有登录王者荣耀营地")

            # 删除登录信息
            success = self.wzry_api.delete_login_info(user_id)
            if success:
                qq_number = login_info.get('qq_number', '未知')
                role_desc = login_info.get('role_desc', '未知')

                return MessageBuilder.text_card(
                    text=f"✅ 王者荣耀营地退出登录成功！\n\n🎮 QQ号：{qq_number}\n🏆 角色：{role_desc}\n\n💡 如需重新使用相关功能，请发送'王者登录'重新登录",
                    description="王者荣耀营地退出登录",
                    prompt='Yapi-免费API'
                )
            else:
                return MessageBuilder.text("❌ 退出登录失败，请稍后重试")

        except Exception as e:
            log_error(bot_id or 0, f"处理王者荣耀退出登录命令失败: {e}", "YAPI_WZRY_LOGOUT_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 退出登录失败: {str(e)}")

    def handle_yapi_command(self, args, bot_id):
        """处理Yapi管理命令"""
        try:
            if not args or args[0].lower() == 'help':
                return self.handle_help()
            else:
                return MessageBuilder.text(f"❌ 未知的子命令: {args[0]}\n\n使用 `/yapi help` 查看帮助")
        except Exception as e:
            log_error(bot_id or 0, f"处理Yapi命令失败: {e}", "YAPI_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 命令执行失败: {str(e)}")


    # ===== 帮助信息 =====
    def handle_help(self):
        """显示帮助信息"""
        help_text = """
# 🔧 Yapi API集成插件

## 📋 可用命令

### 📜 内容类
- `诗词` - 获取随机诗词名句
- `热评` - 获取网易云音乐热评

### 🔍 查询类
- `备案 <域名>` - 查询域名ICP备案信息
- `星座 <星座名>` - 查询星座今日运势

### 📱 工具类
- `抖音 <分享内容>` - 解析抖音视频并发送无水印视频

### 🎮 王者荣耀
- `王者登录` - 获取登录二维码（自动检测登录状态）
- `退出登录` - 退出王者荣耀营地登录
- `经济面板` - 查看经济面板信息
- `最近战绩` - 查看最近战绩
- `具体信息` - 查看皮肤和英雄详细信息
- `营地信息` - 查看营地个人信息
- `赛季统计` - 查看赛季统计数据
- `英雄热度` - 查看英雄热度排行
- `出装推荐 <英雄名>` - 查看英雄出装推荐

## 💡 使用说明
- 支持的星座：白羊座、金牛座、双子座、巨蟹座、狮子座、处女座、天秤座、天蝎座、射手座、摩羯座、水瓶座、双鱼座
- 抖音解析支持完整分享文本，会自动提取视频信息
- 王者荣耀功能需要先登录，扫码后会自动检测并推送结果
"""

        return MessageBuilder.markdown(help_text)

    def handle_wzry_economy_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀经济面板命令"""
        _ = args, message_data  # 标记参数已使用，避免警告
        return self._handle_wzry_command("经济面板", self.wzry_api.get_economy_panel, user_id, bot_id,
                                         error_msg="❌ 获取经济面板信息失败，请稍后重试")

    def handle_wzry_battles_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀最近战绩命令"""
        _ = args, message_data  # 标记参数已使用，避免警告
        return self._handle_wzry_command("最近战绩", self.wzry_api.get_recent_battles, user_id, bot_id,
                                         error_msg="❌ 获取最近战绩失败，请稍后重试")

    def handle_wzry_details_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀具体信息命令"""
        _ = args, message_data  # 标记参数已使用，避免警告
        return self._handle_wzry_command("具体信息", self.wzry_api.get_details_info, user_id, bot_id,
                                         error_msg="❌ 获取具体信息失败，请稍后重试")

    def handle_wzry_camp_info_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀营地信息命令"""
        _ = args, message_data  # 标记参数已使用，避免警告
        return self._handle_wzry_command("营地信息", self.wzry_api.get_camp_info, user_id, bot_id,
                                         error_msg="❌ 获取营地信息失败，请稍后重试")

    def handle_wzry_season_stats_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀赛季统计命令"""
        _ = args, message_data  # 标记参数已使用，避免警告
        return self._handle_wzry_command("赛季统计", self.wzry_api.get_season_stats, user_id, bot_id,
                                         error_msg="❌ 获取赛季统计失败，请稍后重试")

    def handle_wzry_hero_hotness_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀英雄热度命令"""
        _ = args, message_data  # 标记参数已使用，避免警告
        return self._handle_wzry_command("英雄热度", self.wzry_api.get_hero_hotness, user_id, bot_id,
                                         error_msg="❌ 获取英雄热度排行失败，请稍后重试")

    def handle_wzry_build_recommend_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者荣耀出装推荐命令"""
        try:
            _ = message_data  # 标记参数已使用，避免警告
            log_info(bot_id or 0, f"处理王者出装推荐命令 - user_id: {user_id}, args: {args}",
                     "YAPI_WZRY_BUILD_RECOMMEND_COMMAND")

            # 检查是否提供了英雄名称
            if not args or len(args) == 0:
                return MessageBuilder.text('❌ 请提供英雄名称，例如：出装推荐 瑶')

            hero_name = ' '.join(args)  # 支持多字英雄名

            # 使用通用方法处理
            return self._handle_wzry_command("出装推荐", self.wzry_api.get_build_recommend, user_id, bot_id,
                                             args=[hero_name],
                                             error_msg=f"❌ 获取{hero_name}出装推荐失败，请检查英雄名称是否正确")

        except Exception as e:
            log_error(bot_id or 0, f"处理王者荣耀出装推荐命令失败: {e}", "YAPI_WZRY_BUILD_RECOMMEND_COMMAND_ERROR",
                      error=str(e))
            return MessageBuilder.text(f"❌ 获取出装推荐失败，请稍后重试")

    def handle_wzry_help_command(self, args, bot_id, user_id=None, message_data=None):
        """处理王者帮助命令 - 发送王者功能菜单图片"""
        try:
            _ = args, user_id, message_data  # 标记参数已使用，避免警告
            log_info(bot_id or 0, "处理王者帮助命令", "YAPI_WZRY_HELP_COMMAND")

            # 发送王者荣耀菜单图片
            image_url = "https://img10.360buyimg.com/ddimg/jfs/t1/301111/3/22080/28916/687b633dFaa18d19d/841a46b59d40fedd.jpg"
            return MessageBuilder.image(image_url)

        except Exception as e:
            log_error(bot_id or 0, f"处理王者帮助命令失败: {e}", "YAPI_WZRY_HELP_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 显示王者菜单失败: {str(e)}")

    def handle_qq_level_command(self, args, bot_id, user_id=None, message_data=None):
        """处理等级信息命令 - 查询QQ等级信息"""
        try:
            _ = args, user_id  # 标记参数已使用，避免警告
            log_info(bot_id or 0, "处理等级信息命令", "YAPI_QQ_LEVEL_COMMAND")

            if not message_data:
                return MessageBuilder.text("❌ 无法获取消息数据")

            # 从消息数据中提取QQ号
            qq_number = self.qq_info_api.get_user_qq_from_message(message_data)

            if not qq_number:
                return MessageBuilder.text("❌ 无法获取您的QQ号，请稍后重试")

            # 获取QQ等级信息
            level_data = self.qq_info_api.get_qq_level_info(qq_number, bot_id=bot_id)

            if not level_data:
                return MessageBuilder.text("❌ 获取QQ等级信息失败，请稍后重试")

            # 创建等级信息消息（合并为一条消息）
            return self.qq_info_api.create_level_info_message(level_data, bot_id)

        except Exception as e:
            log_error(bot_id or 0, f"处理等级信息命令失败: {e}", "YAPI_QQ_LEVEL_COMMAND_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 获取QQ等级信息失败: {str(e)}")


# 插件实例
plugin_instance = Plugin()
