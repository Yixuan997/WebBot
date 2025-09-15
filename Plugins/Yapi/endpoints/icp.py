"""
ICP备案查询API端点
"""

from Core.logging.file_logger import log_error
from Core.message.builder import MessageBuilder
from ..client import yapi_client


class ICPAPI:
    """ICP备案查询API处理类"""

    def __init__(self):
        """初始化ICP备案查询API"""
        self.client = yapi_client
        self.api_url = "https://api.makuo.cc/api/get.other.icp"
        # 提取重复的按钮配置
        self.button_text = "🔗 Yapi-免费API"
        self.button_url = "https://api.makuo.CC"

    def query_icp(self, domain, bot_id=None):
        """查询域名ICP备案信息"""
        try:
            # 构建完整的请求URL，将域名拼接到URL中
            full_url = f"{self.api_url}?url={domain}"

            # 使用统一客户端发送GET请求
            response = self.client.request_sync(full_url, bot_id=bot_id)

            if response and str(response.get('code')) == '200':
                return self._format_icp_message(response)
            else:
                error_msg = response.get('msg', '未知错误') if response else '请求失败'
                return self._build_error_message(f"查询失败: {error_msg}")

        except Exception as e:
            log_error(bot_id or 0, f"查询ICP备案失败: {str(e)}", "ICP_QUERY_ERROR", error=str(e))
            return self._build_error_message(f"查询异常: {str(e)}")

    def _build_error_message(self, error_msg):
        """构建错误消息，避免重复代码"""
        content = f"🔍 ICP备案查询结果\n\n❌ {error_msg}\n\n💡 请检查域名格式或稍后重试"
        return MessageBuilder.text_card_link(
            text=content,
            button_text=self.button_text,
            button_url=self.button_url,
            description="ICP备案查询失败",
            prompt="Yapi-免费API"
        )

    def _format_icp_message(self, response):
        """格式化ICP备案信息消息"""
        data = response.get('data', {})

        # 提取各个字段
        domain = data.get('domain', '未知域名')
        icp = data.get('icp', '无备案信息')
        nature_name = data.get('natureName', '未知')
        unit_name = data.get('unitName', '未知单位')
        update_time = data.get('updateRecordTime', '未知时间')

        # 构建文本消息
        content = f"🔍 ICP备案查询结果\n\n"
        content += f"🌐 域名：{domain.upper()}\n"
        content += f"📋 备案号：{icp}\n"
        content += f"🏢 单位名称：{unit_name}\n"
        content += f"📊 性质：{nature_name}\n"
        content += f"🕒 更新时间：{update_time}"

        return MessageBuilder.text_card_link(
            text=content,
            button_text=self.button_text,
            button_url=self.button_url,
            description="ICP备案查询成功",
            prompt="Yapi-免费API"
        )
