"""
Webhook基础抽象类
为不同协议的Webhook处理提供统一接口
"""

from abc import ABC, abstractmethod

from flask import request, jsonify

from Core.logging.file_logger import log_info, log_error


class BaseWebhookHandler(ABC):
    """Webhook处理器基础抽象类"""

    def __init__(self, protocol_name: str):
        self.protocol_name = protocol_name

    @abstractmethod
    def validate_request(self, raw_data: bytes, headers: dict) -> tuple[bool, str]:
        """
        验证请求的有效性
        
        参数:
            raw_data: 原始请求数据
            headers: 请求头
            
        返回:
            (是否有效, 错误信息)
        """
        pass

    @abstractmethod
    def parse_event(self, raw_data: bytes) -> dict:
        """
        解析事件数据
        
        参数:
            raw_data: 原始请求数据
            
        返回:
            解析后的事件数据
        """
        pass

    @abstractmethod
    def get_bot_identifier(self, headers: dict, event_data: dict) -> str:
        """
        获取机器人标识符
        
        参数:
            headers: 请求头
            event_data: 事件数据
            
        返回:
            机器人标识符（如AppID）
        """
        pass

    @abstractmethod
    def verify_signature(self, raw_data: bytes, headers: dict, secret: str) -> bool:
        """
        验证签名
        
        参数:
            raw_data: 原始请求数据
            headers: 请求头
            secret: 机器人密钥
            
        返回:
            签名是否有效
        """
        pass

    @abstractmethod
    def handle_event(self, bot_id: int, event_data: dict, bot_manager) -> dict:
        """
        处理具体事件
        
        参数:
            bot_id: 机器人ID
            event_data: 事件数据
            bot_manager: 机器人管理器
            
        返回:
            处理结果
        """
        pass

    def process_webhook(self):
        """
        处理Webhook请求的通用流程
        """
        try:
            # 获取请求数据
            raw_data = request.get_data()
            headers = dict(request.headers)

            # 详细记录请求信息（同时输出到控制台）
            log_message = f"收到{self.protocol_name} Webhook请求"
            log_info(0, log_message, f"{self.protocol_name.upper()}_WEBHOOK_RECEIVED",
                     content_length=len(raw_data),
                     headers=list(headers.keys()))

            # 1. 验证请求
            is_valid, error_msg = self.validate_request(raw_data, headers)
            if not is_valid:
                log_error(0, f"{self.protocol_name} Webhook请求验证失败: {error_msg}",
                          f"{self.protocol_name.upper()}_WEBHOOK_INVALID")
                return jsonify({"error": error_msg}), 400

            # 2. 解析事件数据
            try:
                event_data = self.parse_event(raw_data)
            except Exception as e:
                log_error(0, f"{self.protocol_name} Webhook数据解析失败: {e}",
                          f"{self.protocol_name.upper()}_WEBHOOK_PARSE_ERROR", error=str(e))
                return jsonify({"error": "Invalid event data"}), 400

            # 3. 检查是否是回调验证请求（需要先验证签名）
            if self.is_verification_request(event_data):
                log_info(0, f"{self.protocol_name} 检测到回调验证请求，需要先验证签名",
                         f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_DETECTED")

                # 验证请求也需要签名验证
                # 获取机器人标识符
                bot_identifier = self.get_bot_identifier(headers, event_data)
                if not bot_identifier:
                    log_error(0, f"{self.protocol_name} 验证请求缺少机器人标识符",
                              f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_NO_IDENTIFIER")
                    return jsonify({"error": "Missing bot identifier"}), 400

                # 获取机器人管理器
                bot_manager = self.get_bot_manager()
                if not bot_manager:
                    log_error(0, f"{self.protocol_name} 验证请求时机器人管理器不可用",
                              f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_MANAGER_UNAVAILABLE")
                    return jsonify({"error": "Bot manager unavailable"}), 500

                # 根据标识符找到机器人ID
                bot_id = self.find_bot_by_identifier(bot_identifier, bot_manager)
                if not bot_id:
                    log_error(0, f"{self.protocol_name} 验证请求未找到对应的机器人: {bot_identifier}",
                              f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_BOT_NOT_FOUND")
                    return jsonify({"error": "Bot not found"}), 404

                # 获取机器人密钥并验证签名
                secret = self.get_bot_secret(bot_id, bot_manager)
                if secret and not self.verify_signature(raw_data, headers, secret):
                    log_error(0, f"{self.protocol_name} 验证请求签名验证失败",
                              f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_SIGNATURE_FAILED")
                    return jsonify({"error": "Invalid signature"}), 401

                # 签名验证通过，处理验证请求
                log_info(0, f"{self.protocol_name} 验证请求签名验证通过，处理验证请求",
                         f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_SIGNATURE_OK")
                return self.handle_verification_request(event_data, headers)

            # 4. 获取机器人标识符
            bot_identifier = self.get_bot_identifier(headers, event_data)
            if not bot_identifier:
                log_error(0, f"{self.protocol_name} Webhook缺少机器人标识符",
                          f"{self.protocol_name.upper()}_WEBHOOK_NO_IDENTIFIER")
                return jsonify({"error": "Missing bot identifier"}), 400

            # 5. 获取机器人管理器
            bot_manager = self.get_bot_manager()
            if not bot_manager:
                log_error(0, f"{self.protocol_name} 机器人管理器不可用",
                          f"{self.protocol_name.upper()}_WEBHOOK_MANAGER_UNAVAILABLE")
                return jsonify({"error": "Bot manager unavailable"}), 500

            # 6. 根据标识符找到机器人ID
            bot_id = self.find_bot_by_identifier(bot_identifier, bot_manager)
            if not bot_id:
                log_error(0, f"{self.protocol_name} 未找到对应的机器人: {bot_identifier}",
                          f"{self.protocol_name.upper()}_WEBHOOK_BOT_NOT_FOUND")
                return jsonify({"error": "Bot not found"}), 404

            # 7. 检查机器人是否启用
            if not self.is_bot_enabled(bot_id, bot_manager):
                log_info(bot_id, f"{self.protocol_name} 机器人{bot_id}未启用，忽略消息",
                         f"{self.protocol_name.upper()}_WEBHOOK_BOT_DISABLED")
                return jsonify({"status": "ignored", "reason": "bot_disabled"}), 200

            # 8. 获取机器人密钥并验证签名（验证请求已经在前面处理，这里不会是验证请求）
            secret = self.get_bot_secret(bot_id, bot_manager)
            if secret and not self.verify_signature(raw_data, headers, secret):
                log_error(0, f"{self.protocol_name} 机器人{bot_id}签名验证失败",
                          f"{self.protocol_name.upper()}_WEBHOOK_SIGNATURE_FAILED")
                return jsonify({"error": "Invalid signature"}), 401

            # 9. 处理事件
            response = self.handle_event(bot_id, event_data, bot_manager)

            # 确保响应格式正确
            json_response = jsonify(response)
            json_response.headers['Content-Type'] = 'application/json; charset=utf-8'

            return json_response, 200

        except Exception as e:
            import traceback
            log_error(0, f"{self.protocol_name} Webhook处理异常: {e}",
                      f"{self.protocol_name.upper()}_WEBHOOK_ERROR", error=str(e))
            return jsonify({"error": "Internal server error"}), 500

    def is_verification_request(self, event_data: dict) -> bool:
        """检查是否是回调验证请求"""
        # 默认实现：检查op码是否为13（QQ的验证请求）
        return event_data.get('op') == 13

    def handle_verification_request(self, event_data: dict, headers: dict):
        """处理回调验证请求 - 按照QQ官方要求生成signature"""
        try:
            log_info(0, f"{self.protocol_name} 处理回调验证请求",
                     f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_HANDLE")

            payload = event_data.get('d', {})
            plain_token = payload.get('plain_token')
            event_ts = payload.get('event_ts')

            if plain_token and event_ts:
                # 生成signature（按照QQ官方要求）
                signature = self.generate_verification_signature(event_ts, plain_token)

                if signature:
                    log_info(0, f"{self.protocol_name} 回调验证成功",
                             f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_SUCCESS")

                    # 按照QQ官方要求的响应格式
                    response = {
                        "plain_token": plain_token,
                        "signature": signature
                    }

                    json_response = jsonify(response)
                    json_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                    json_response.status_code = 200

                    return json_response
                else:
                    log_error(0, f"{self.protocol_name} 生成signature失败",
                              f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_SIGNATURE_FAILED")
                    return jsonify({"error": "Failed to generate signature"}), 500
            else:
                log_error(0, f"{self.protocol_name} 回调验证缺少必要参数",
                          f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_MISSING_PARAMS")
                return jsonify({"error": "Missing required parameters"}), 400

        except Exception as e:
            log_error(0, f"{self.protocol_name} 回调验证异常: {e}",
                      f"{self.protocol_name.upper()}_WEBHOOK_VERIFICATION_ERROR")
            return jsonify({"error": "Verification failed"}), 500

    def get_bot_manager(self):
        """获取机器人管理器实例 - 使用全局单例"""
        # 延迟导入避免循环导入
        from BluePrints.admin.bots import get_bot_manager
        return get_bot_manager()

    @abstractmethod
    def find_bot_by_identifier(self, identifier: str, bot_manager) -> int:
        """
        根据标识符查找机器人ID
        
        参数:
            identifier: 机器人标识符
            bot_manager: 机器人管理器
            
        返回:
            机器人ID，未找到返回None
        """
        pass

    def is_bot_enabled(self, bot_id: int, bot_manager) -> bool:
        """检查机器人是否启用消息处理"""
        return bot_id in bot_manager.list_running_bots()

    @abstractmethod
    def get_bot_secret(self, bot_id: int, bot_manager) -> str:
        """
        获取机器人密钥
        
        参数:
            bot_id: 机器人ID
            bot_manager: 机器人管理器
            
        返回:
            机器人密钥
        """
        pass
