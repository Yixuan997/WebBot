"""
诗词API端点
"""

from Core.logging.file_logger import log_error
from Core.message.builder import MessageBuilder
from ..client import yapi_client


class PoetryAPI:
    """诗词API处理类"""

    def __init__(self):
        """初始化诗词API"""
        self.client = yapi_client
        self.api_url = "https://api.makuo.cc/api/get.mottos.poetry"

    def get_random_poetry(self, bot_id=None):
        """获取随机诗词"""
        try:
            # 使用统一客户端发送请求
            response = self.client.request_sync(self.api_url, bot_id=bot_id)

            if response and str(response.get('code')) == '200':
                return self._format_poetry_message(response)
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                return MessageBuilder.text(f"❌ 获取诗词失败: {error_msg}\n\n💡 请稍后重试")

        except Exception as e:
            log_error(bot_id or 0, f"获取随机诗词失败: {str(e)}", "POETRY_RANDOM_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 获取诗词失败: {str(e)}")

    def _format_poetry_message(self, response):
        """格式化诗词消息"""
        poetry_text = response.get('data', '暂无诗词')

        # 解析诗词和作者
        if '——' in poetry_text:
            poem, author = poetry_text.split('——', 1)
            poem = poem.strip()
            author = author.strip()
        else:
            poem = poetry_text
            author = '佚名'

        # 构建文本消息
        content = f"📜 诗词名句\n\n"
        content += f"📖 诗句：{poem}\n"
        content += f"✍️ 作者：{author}"

        return MessageBuilder.text(content)
