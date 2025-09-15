"""
星座运势查询API端点
"""

from Core.logging.file_logger import log_error
from Core.message.builder import MessageBuilder
from ..client import yapi_client


class ConstellationAPI:
    """星座运势查询API处理类"""

    def __init__(self):
        """初始化星座运势查询API"""
        self.client = yapi_client
        self.api_url = "https://api.makuo.cc/api/get.info.constellation"

    def query_constellation(self, constellation_name, bot_id=None):
        """查询星座运势信息"""
        try:
            # 构建完整的请求URL，将星座名称拼接到URL中
            full_url = f"{self.api_url}?name={constellation_name}"

            # 使用统一客户端发送GET请求
            response = self.client.request_sync(full_url, bot_id=bot_id)

            if response and str(response.get('code')) == '200':
                return self._format_constellation_message(response)
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                return MessageBuilder.text(f"❌ 查询星座运势失败: {error_msg}\n\n💡 请检查星座名称或稍后重试")

        except Exception as e:
            log_error(bot_id or 0, f"查询星座运势失败: {str(e)}", "CONSTELLATION_QUERY_ERROR", error=str(e))
            return MessageBuilder.text(f"❌ 查询星座运势失败: {str(e)}")

    def _format_constellation_message(self, response):
        """格式化星座运势信息消息"""
        data = response.get('data', {})

        # 提取各个字段
        constellation = data.get('constellation', '未知星座')
        benefactor_direction = data.get('benefactor_direction', '未知')
        benefactor_constellation = data.get('benefactor_constellation', '未知')
        lucky_number = data.get('lucky_number', '未知')
        lucky_color = data.get('lucky_color', '未知')
        love_fortune = data.get('love_fortune', '暂无信息')
        wealth_fortune = data.get('wealth_fortune', '暂无信息')
        career_fortune = data.get('career_fortune', '暂无信息')
        overall_fortune = data.get('overall_fortune', '暂无信息')
        tips = data.get('tips', '暂无提示')

        # 构建文本消息
        content = f"\n✨ {constellation}座今日运势\n\n"
        content += f"🧭 贵人方位：{benefactor_direction}\n"
        content += f"🌟 贵人星座：{benefactor_constellation}\n"
        content += f"🔢 幸运数字：{lucky_number}\n"
        content += f"🎨 幸运颜色：{lucky_color}\n\n"

        content += f"💕 爱情运势：\n{love_fortune.strip()}\n\n"
        content += f"💰 财富运势：\n{wealth_fortune.strip()}\n\n"
        content += f"💼 事业运势：\n{career_fortune.strip()}\n\n"
        content += f"🌈 综合运势：\n{overall_fortune.strip()}\n\n"
        content += f"💡 今日提示：{tips}"

        return MessageBuilder.text(content)
