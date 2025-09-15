"""
抖音视频解析API端点
"""

import re

from Core.logging.file_logger import log_error, log_info
from Core.message.builder import MessageBuilder
from ..client import yapi_client


class DouyinAPI:
    """抖音视频解析API处理类"""

    def __init__(self):
        """初始化抖音API"""
        self.client = yapi_client
        self.api_url = "https://api.makuo.cc/api/get.video.douyin"

    def parse_douyin_video(self, url_or_text, bot_id=None):
        """解析抖音视频

        Args:
            url_or_text: 抖音分享链接或包含链接的文本
            bot_id: 机器人ID，用于日志记录

        Returns:
            MessageBuilder对象: 包含视频信息的消息
        """
        try:
            # 提取抖音链接
            douyin_url = self._extract_douyin_url(url_or_text)
            if not douyin_url:
                return MessageBuilder.text(
                    "❌ 未找到有效的抖音链接\n\n"
                    "💡 请发送抖音分享链接，支持格式：\n"
                    "• https://v.douyin.com/xxx\n"
                    "• https://www.douyin.com/video/xxx\n"
                    "• 包含抖音链接的分享文本"
                )

            log_info(bot_id or 0, f"开始解析抖音视频: {douyin_url}", "DOUYIN_PARSE_START")

            # 调用API解析视频（GET请求）
            params = {'url': douyin_url}
            response = self.client.request_sync(self.api_url, method='GET', params=params, bot_id=bot_id)

            if response and str(response.get('code')) == '200':
                return self._format_video_message(response)
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                log_error(bot_id or 0, f"抖音视频解析失败: {error_msg}", "DOUYIN_PARSE_FAILED",
                          url=douyin_url, response=response)
                return MessageBuilder.text(f"❌ 解析抖音视频失败: {error_msg}\n\n💡 请检查链接是否正确或稍后重试")

        except Exception as e:
            log_error(bot_id or 0, f"解析抖音视频异常: {str(e)}", "DOUYIN_PARSE_ERROR",
                      url_or_text=url_or_text, error=str(e))
            return MessageBuilder.text(f"❌ 解析抖音视频失败: {str(e)}")

    def _extract_douyin_url(self, text):
        """从文本中提取抖音链接"""
        # 抖音链接的正则表达式模式
        patterns = [
            r'https?://v\.douyin\.com/[A-Za-z0-9]+/?',  # 短链接
            r'https?://www\.douyin\.com/video/\d+/?',  # 完整链接
            r'https?://www\.iesdouyin\.com/share/video/\d+/?',  # 另一种格式
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    def _format_video_message(self, response):
        """格式化视频消息并发送视频文件"""
        try:
            data = response.get('data', {})

            # 提取视频信息
            title = data.get('title', '无标题')
            author = data.get('author', '未知作者')
            like_count = data.get('like', 0)
            video_url = data.get('video_url', '')
            music_name = data.get('music_Name', '未知音乐')

            # 格式化点赞数
            like_str = self._format_number(like_count)

            # 构建视频消息
            if video_url:
                log_info(0, f"发送抖音视频: {title}", "DOUYIN_SEND_VIDEO",
                         title=title, author=author, likes=like_count)

                # 构建视频说明文字
                caption = f"📱 {title}\n👤 {author} ❤️ {like_str}"

                # 使用MessageBuilder发送视频，系统会自动上传并获取file_info
                return MessageBuilder.video(
                    video_url_or_file_info=video_url,
                    caption=caption,
                    auto_upload=True  # 自动上传视频文件
                )
            else:
                # 如果没有视频链接，返回错误信息
                return MessageBuilder.text(f"❌ 未获取到视频链接\n\n🎬 标题：{title}\n👤 作者：{author}")

        except Exception as e:
            log_error(0, f"格式化抖音视频消息失败: {str(e)}", "DOUYIN_FORMAT_ERROR",
                      response=response, error=str(e))
            return MessageBuilder.text(f"❌ 处理视频信息失败: {str(e)}")

    def _format_number(self, num):
        """格式化数字显示"""
        try:
            num = int(num)
            if num >= 10000:
                return f"{num / 10000:.1f}万"
            else:
                return str(num)
        except (ValueError, TypeError):
            return "0"
