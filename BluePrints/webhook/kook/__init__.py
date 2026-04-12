"""
KOOK 协议 Webhook 处理模块
"""

from .handler import KookWebhookHandler

kook_webhook_handler = KookWebhookHandler()


def handle_kook_webhook():
    """处理 KOOK Webhook 回调"""
    return kook_webhook_handler.process_webhook()

