"""
QQ协议Webhook处理模块
"""

from .handler import QQWebhookHandler

# 创建QQ Webhook处理器实例
qq_webhook_handler = QQWebhookHandler()


# 导出处理函数供蓝图使用
def handle_qq_webhook():
    """处理QQ Webhook回调"""
    return qq_webhook_handler.process_webhook()
