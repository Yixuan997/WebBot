"""
歌曲热评API端点
"""

from Core.logging.file_logger import log_error
from Core.message.builder import MessageBuilder
from ..client import yapi_client


class CommentAPI:
    """歌曲热评API处理类"""

    def __init__(self):
        """初始化热评API"""
        self.client = yapi_client
        self.api_url = "https://api.makuo.cc/api/get.comment.163"

    def get_random_comment(self, bot_id=None):
        """获取歌曲热评"""
        try:
            # 使用统一客户端发送请求
            response = self.client.request_sync(self.api_url, bot_id=bot_id)

            if response and str(response.get('code')) == '200':
                return self._format_comment_message(response)
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                return MessageBuilder.text(f"❌ 获取歌曲热评失败: {error_msg}\n\n💡 请稍后重试")

        except Exception as e:
            log_error(bot_id or 0, f"获取随机歌曲热评失败: {str(e)}", "COMMENT_RANDOM_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 获取歌曲热评失败: {str(e)}")

    def _format_comment_message(self, response):
        """格式化歌曲热评消息"""
        data = response.get('data', {})

        # 提取各个字段
        comment_content = data.get('Content', '暂无热评内容')
        music_name = data.get('Music', '未知歌曲')
        artist_name = data.get('name', '未知歌手')
        commenter_nick = data.get('Nick', '匿名用户')
        picture_url = data.get('Picture', '')

        # 构建文本消息
        content = f"\n\n"
        content += f"🎵 音乐热评\n\n"
        content += f"💬 热评：{comment_content}\n\n"
        content += f"👤 评论者：{commenter_nick}\n\n"
        content += f"🎶 歌曲：{music_name}\n\n"
        content += f"🎤 歌手：{artist_name}"

        # 如果有封面图片，发送图片消息
        if picture_url:
            return MessageBuilder.image(picture_url, content)
        else:
            return MessageBuilder.text(content)
