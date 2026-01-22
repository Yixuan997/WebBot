"""
工作流执行上下文

管理工作流执行过程中的变量、事件和响应
"""
import json
from typing import Any

from jinja2 import Environment


class MessageAPI:
    """消息API封装，供代码片段使用"""

    def __init__(self, context: "WorkflowContext"):
        self.context = context

    def send_message(self, content):
        """发送消息"""
        from Core.message.builder import MessageBuilder
        from Adapters.base.message import BaseMessage

        if isinstance(content, BaseMessage):
            message = content
        else:
            message = MessageBuilder.text(str(content), event=self.context.event)
        self.context.set_response(message)

    def reply(self, content):
        """回复消息（send_message 的别名）"""
        self.send_message(content)


class WorkflowContext:
    """工作流执行上下文"""

    def __init__(self, event):
        """
        初始化上下文
        
        Args:
            event: BaseEvent 事件对象
        """
        self.event = event
        self.variables = {}  # 变量存储
        self._response = None  # 响应消息

        # 设置事件原始数据
        if hasattr(event, 'raw_data'):
            self.variables['raw_data'] = event.raw_data

        # 设置 message_api，用于代码片段中发送消息
        self._setup_message_api()

    def set_variable(self, key: str, value: Any):
        """
        设置变量
        
        Args:
            key: 变量名
            value: 变量值
        """
        self.variables[key] = value

    def get_variable(self, key: str, default=None) -> Any:
        """
        获取变量，支持点号访问嵌套属性
        
        Args:
            key: 变量名，支持 response_json.code 这样的嵌套访问
            default: 默认值
            
        Returns:
            变量值
        """
        # 先检查完整 key 是否存在（优先级最高）
        if key in self.variables:
            return self.variables[key]
        
        # 如果包含点号，尝试嵌套访问
        if '.' in key:
            parts = key.split('.')
            value = self.variables.get(parts[0])
            if value is None:
                return default
            try:
                for part in parts[1:]:
                    if isinstance(value, dict):
                        value = value.get(part)
                    elif hasattr(value, part):
                        value = getattr(value, part)
                    else:
                        return default
                    if value is None:
                        return default
                return value
            except Exception:
                return default
        return default

    def render_template(self, template_str: str) -> str:
        """
        渲染模板字符串（支持Jinja2语法）
        
        Args:
            template_str: 模板字符串，如 "Hello {{user_id}}" 或 "{{global.api_key}}"
            
        Returns:
            str: 渲染后的字符串
        """
        try:
            from Core.workflow.globals import global_variables
            
            env = Environment()
            # 添加 json_safe 过滤器：转义字符串中的特殊字符，使其可以安全嵌入 JSON
            env.filters['json_safe'] = lambda s: json.dumps(str(s), ensure_ascii=False)[1:-1] if s else ''
            template = env.from_string(template_str)
            
            # 注入全局变量，支持 {{global.xxx}} 语法
            render_vars = {**self.variables, 'global': global_variables.get_all()}
            return template.render(**render_vars)
        except Exception:
            # 如果模板渲染失败，返回原字符串
            return template_str

    def set_response(self, message: Any):
        """
        设置响应消息
        
        Args:
            message: BaseMessage 对象或消息内容
        """
        self._response = message
        # 标记为已处理
        self.variables['_handled'] = True

    def get_response(self) -> Any | None:
        """
        获取响应消息
        
        Returns:
            BaseMessage 对象或 None
        """
        return self._response

    def clear_response(self):
        """清除响应消息"""
        self._response = None

    def get_all_variables(self) -> dict:
        """
        获取所有变量（用于调试）
        
        Returns:
            dict: 变量字典副本（排除不可序列化的对象）
        """
        result = {}
        for key, value in self.variables.items():
            # 排除不可序列化的对象
            if key.startswith('_') or key == 'message_api':
                continue
            try:
                # 尝试序列化测试
                json.dumps(value, default=str)
                result[key] = value
            except Exception:
                result[key] = str(value)[:500]
        return result

    def _setup_message_api(self):
        """设置 message_api，用于代码片段中发送消息"""
        self.variables['message_api'] = MessageAPI(self)
