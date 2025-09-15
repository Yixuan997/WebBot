"""
QQ信息相关API端点
提供QQ等级信息查询等功能
"""

from Core.logging.file_logger import log_info, log_error
from Core.message.builder import MessageBuilder


class QQInfoAPI:
    """QQ信息API类"""

    def __init__(self, client):
        """
        初始化QQ信息API

        Args:
            client: Yapi客户端实例
        """
        self.client = client
        self.level_url = "https://api.makuo.cc/api/get.qq.level"

    def get_qq_level_info(self, qq_number, cookie="", bot_id=None):
        """
        获取QQ等级信息

        Args:
            qq_number: QQ号
            cookie: Cookie信息（暂时留空）
            bot_id: 机器人ID

        Returns:
            dict: QQ等级信息响应
        """
        try:
            log_info(bot_id or 0, f"请求QQ等级信息: {qq_number}", "QQ_LEVEL_REQUEST", qq=qq_number)

            # 构建form-data参数
            form_data = {
                'qq': str(qq_number),
                'cookie': "ETK=; pt2gguin=o0093653142; pt_clientip=86bc6faa06d6798e; pt_guid_sig=39e02a4c4d10fb1fba591373e6c5a5f5a6fa0a366fea14e08107ec7b7b969e3c; pt_local_token=-1061884190; pt_login_sig=zXtHCgxOjSE9DqfLt*H0hMaCyyiCWqfxrL68sUkpEndTRscB1XNU0ADDvfsnGi20; pt_recent_uins=d1a80eb34f56d7dfaf54848edaaedcd61e1e13adb1611f371804144d173ea7171cbbfee6d2ccb51459fd61f6021842d599618c33b0555757; pt_serverip=3ab07f0000012728; ptnick_93653142=e980b8e8bda9eaa6bfe0bdbc; qrsig=efe85610f01a9d7ec9097df817902652eab2432a206df1ee86b718d37595aaeb81acba91c55c233d0bf41160e17d06886311ff370a37d9f7be75ad99dc804f98; superkey=-NmY75*q5Zcw7c*ZsvRKdVEvzWkU6DA1mm-Xbw3Jq4M_; supertoken=2518191917; superuin=o0093653142; uikey=9adacf33a46ceb8c1dbcf690b2be504cbc0e619155281e14e2546ff5411bcf1a; RK=Nfn1i8C7Qq; ptcz=91c1f348fd36fd6454f7249def6392e9ef12f35918019368194e7ea0e37eb2e5; skey=@0ShZOv8yA; uin=o0093653142; p_skey=VZ8y7tE1AjpOXMnw19FLJk3SB68a*e1kXqL8CzwA5Pw_; p_uin=o0093653142; pt4_token=evDMwFp9qQjYHrpwU7IdRyanagXBjjjrdanXTIgz-s0_"
            }

            # 使用简化的客户端发送POST请求（自动form-data格式）
            response = self.client.request_sync(
                url=self.level_url,
                method='POST',
                data=form_data,
                bot_id=bot_id
            )

            if not response:
                log_error(bot_id or 0, "QQ等级信息请求失败: 无响应", "QQ_LEVEL_NO_RESPONSE")
                return None

            # 检查响应状态
            if response.get('code') != 200:
                error_msg = response.get('msg', '未知错误')
                log_error(bot_id or 0, f"QQ等级信息请求失败: {error_msg}", "QQ_LEVEL_ERROR",
                          error=error_msg)
                return None

            # 提取数据
            data = response.get('data', {})

            if not data:
                log_error(bot_id or 0, "QQ等级信息响应数据为空", "QQ_LEVEL_EMPTY_DATA")
                return None

            log_info(bot_id or 0, f"QQ等级信息获取成功: {qq_number}", "QQ_LEVEL_SUCCESS",
                     qq=qq_number, qq_level=data.get('iQQLevel', 'N/A'))

            return {
                'data': data,
                'msg': response.get('msg', '请求成功'),
                'time': response.get('time')
            }

        except Exception as e:
            log_error(bot_id or 0, f"QQ等级信息请求异常: {e}", "QQ_LEVEL_EXCEPTION", error=str(e))
            return None

    def create_level_info_message(self, level_data, bot_id=None):
        """
        创建QQ等级信息消息（合并为一条消息）

        Args:
            level_data: QQ等级数据
            bot_id: 机器人ID

        Returns:
            dict: 包含头像和详细信息的单条消息
        """
        try:
            if not level_data or not level_data.get('data'):
                return MessageBuilder.text("❌ QQ等级数据无效")

            data = level_data['data']
            time_info = level_data.get('time', '')

            # 构建包含头像和详细信息的消息
            # 替换大头像
            face_url = data.get('sFaceUrl').replace('s=100', 's=640')
            nickname = data.get('sNickName', 'N/A')

            # 基本信息
            message_text = f"\n👤 **基本信息**\n"
            message_text += f"QQ号: {data.get('qq', 'N/A')}\n"
            message_text += f"昵称: {nickname}\n"
            message_text += f"等级: {data.get('iQQLevel', 'N/A')}\n"
            message_text += f"升级还需: {data.get('iNextLevelDay', 'N/A')}天\n\n"

            # 会员信息（只有VIP或SVIP用户才显示）
            if data.get('iVip') == '1' or data.get('iSVip') == '1':
                message_text += f"💎 **会员信息**\n"

                # 智能显示会员等级
                if data.get('iSVip') == '1':
                    # 如果是SVIP，显示SVIP等级
                    message_text += f"SVIP等级: {data.get('iVipLevel', 'N/A')}\n"
                    message_text += f"年费SVIP: {'是' if data.get('iYearVip') == '1' else '否'}\n"
                elif data.get('iVip') == '1':
                    # 如果只是VIP，显示VIP等级
                    message_text += f"VIP等级: {data.get('iVipLevel', 'N/A')}\n"
                    message_text += f"年费VIP: {'是' if data.get('iYearVip') == '1' else '否'}\n"

                # 显示加速倍率
                message_text += f"会员加速倍率: {data.get('iVipSpeedRate', 'N/A')}%\n"

            # 只有当大会员开启时才显示
            if data.get('iBigClubVipFlag') == '1':
                message_text += f"大会员等级: {data.get('iBigClubLevel', 'N/A')}\n"
                message_text += f"年费大会员: {'是' if data.get('iYearBigClubFlag') == '1' else '否'}\n"
                message_text += f"大会员成长值: {data.get('iBigClubGrowth', 'N/A')}\n"
                message_text += f"大会员加速: {data.get('iBigClubSpeed', 'N/A')}%\n"

            # 只有当超级QQ开启时才显示
            if data.get('iSqq') == '1':
                message_text += f"超级QQ: 是\n"
                message_text += f"超级QQ等级: {data.get('iSqqLevel', 'N/A')}\n"
                message_text += f"超级QQ加速倍率: {data.get('iSqqSpeedRate', 'N/A')}%\n"

            # 在线信息
            message_text += f"\n⏰ **在线信息**\n"
            message_text += f"总在线天数: {data.get('iTotalDays', 'N/A')}天\n"
            message_text += f"活跃天数: {data.get('iTotalActiveDay', 'N/A')}天\n"
            message_text += f"真实活跃天数: {data.get('iRealDays', 'N/A')}天\n"
            message_text += f"基础天数: {data.get('iBaseDays', 'N/A')}天\n"
            message_text += f"服务器计算天数: {data.get('iSvrDays', 'N/A')}天\n"
            message_text += f"手机QQ在线: {'是' if data.get('iMobileQQOnline') == '1' else '否'}\n"
            message_text += f"电脑QQ在线: {'是' if data.get('iPCQQOnline') == '1' else '否'}\n"
            message_text += f"手机QQ在线时长: {self._format_time(data.get('iMobileQQOnlineTime', '0'))}\n"
            message_text += f"电脑QQ在线时长: {self._format_time(data.get('iPCQQOnlineTime', '0'))}\n"
            message_text += f"当前在线时长: {data.get('lineTime', 'N/A')}小时\n\n"

            # 等级相关
            message_text += f"📈 **等级相关**\n"
            message_text += f"最高等级总天数: {data.get('iMaxLvlTotalDays', 'N/A')}天\n"
            message_text += f"最高等级实际天数: {data.get('iMaxLvlRealDays', 'N/A')}天"

            # 只显示有星级的信息
            star_info = []
            if int(data.get('speedStar', '0')) > 0:
                star_info.append(f"加速星: {data.get('speedStar', '0')}")
            if int(data.get('speedStarv2', '0')) > 0:
                star_info.append(f"加速星v2: {data.get('speedStarv2', '0')}")
            if int(data.get('speedStarv3', '0')) > 0:
                star_info.append(f"加速星v3: {data.get('speedStarv3', '0')}")
            if int(data.get('SVIPStar', '0')) > 0:
                star_info.append(f"SVIP星: {data.get('SVIPStar', '0')}")

            if star_info:
                message_text += f"⭐ **星级信息**\n"
                for star in star_info:
                    message_text += f"{star}\n"

            # 如果有头像，使用图片消息；否则使用文本消息
            if face_url:
                result_message = MessageBuilder.image(
                    image_url_or_file_info=face_url,
                    caption=message_text,
                    auto_upload=True
                )
            else:
                result_message = MessageBuilder.text(message_text)

            log_info(bot_id or 0, f"QQ等级信息消息创建成功", "QQ_LEVEL_MESSAGE_CREATED",
                     qq=data.get('qq', 'N/A'))

            return result_message

        except Exception as e:
            log_error(bot_id or 0, f"创建QQ等级信息消息异常: {e}", "QQ_LEVEL_MESSAGE_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 创建等级信息消息失败: {str(e)}")

    def _format_time(self, seconds_str):
        """
        格式化时间（秒转换为时分秒）

        Args:
            seconds_str: 秒数字符串

        Returns:
            str: 格式化后的时间
        """
        try:
            seconds = int(seconds_str)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60

            if hours > 0:
                return f"{hours}小时{minutes}分{secs}秒"
            elif minutes > 0:
                return f"{minutes}分{secs}秒"
            else:
                return f"{secs}秒"
        except:
            return seconds_str

    def get_user_qq_from_message(self, message_data):
        """
        从消息数据中提取用户QQ号（参考echo插件实现）

        Args:
            message_data: 消息数据

        Returns:
            str: QQ号或None
        """
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
                        return str(parsed['qq_number'])

            return None

        except Exception as e:
            log_error(0, f"从消息数据提取QQ号异常: {e}", "QQ_EXTRACT_QQ_ERROR", error=str(e))
            return None

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
            import base64

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
            log_error(0, f"解析REFIDX失败: {e}", "QQ_PARSE_REFIDX_ERROR")
            return None
