"""
自定义端点调用节点

支持调用协议的任意 API 端点
用户可以自定义 API 端点和请求参数
"""
import json
from typing import Any

from Core.logging.file_logger import log_error
from .base import BaseNode


class EndpointNode(BaseNode):
    """自定义端点调用节点 - 支持调用任意 API"""

    name = "自定义端点"
    description = "调用协议的任意 API 端点"
    category = "action"
    icon = "🔌"

    inputs = []
    outputs = [
        {'name': 'endpoint_response', 'label': 'endpoint_response - API 响应结果', 'type': 'any'},
        {'name': 'endpoint_success', 'label': 'endpoint_success - 是否成功', 'type': 'bool'},
        {'name': 'endpoint_error', 'label': 'endpoint_error - 错误信息', 'type': 'string'},
    ]

    config_schema = [
        {
            'name': 'action',
            'label': 'API 端点',
            'type': 'text',
            'required': True,
            'placeholder': 'send_msg',
            'help': 'OneBot API 端点名称，支持变量 {{variable}}'
        },
        {
            'name': 'params',
            'label': '请求参数 (JSON)',
            'type': 'textarea',
            'required': True,
            'default': '{\n  \n}',
            'placeholder': '{"group_id": {{group_id}}, "message": "hello"}',
            'help': 'JSON 格式，支持变量 {{variable}} 和嵌套访问 {{response_json.data.url}}',
            'rows': 8
        },
        {
            'name': 'enable_template',
            'label': '启用变量替换',
            'type': 'checkbox',
            'default': True,
            'help': '是否替换 JSON 中的 {{variable_name}} 变量'
        },
        {
            'name': 'next_node',
            'label': '执行后跳转到',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '选择下一个要执行的节点（留空则终止当前流程）'
        }
    ]

    async def _execute(self, context) -> dict[str, Any]:
        """
        执行自定义端点调用
        
        Args:
            context: 工作流上下文
            
        Returns:
            dict: 执行结果
        """
        action = self.config.get('action', '').strip()
        params_json = self.config.get('params', '{}')
        enable_template = self.config.get('enable_template', True)

        try:
            # 1. 检查协议类型
            if not hasattr(context, 'event') or not hasattr(context.event, 'bot'):
                error_msg = '无法获取机器人信息'
                log_error(0, error_msg, "ONEBOT_API_NO_BOT")
                return {
                    'success': False,
                    'error': error_msg
                }

            protocol = context.event.bot.adapter.get_protocol_name()
            if protocol != 'onebot':
                error_msg = f'此节点仅支持 OneBot 协议，当前协议: {protocol}'
                log_error(0, error_msg, "ONEBOT_API_WRONG_PROTOCOL", protocol=protocol)
                return {
                    'success': False,
                    'error': error_msg
                }

            # 2. 验证 action
            if not action:
                error_msg = 'API 端点不能为空'
                log_error(0, error_msg, "ONEBOT_API_NO_ACTION")
                return {
                    'success': False,
                    'error': error_msg
                }

            # 3. 变量替换
            if enable_template:
                action = context.render_template(action)
                params_json = context.render_template(params_json)

            # 4. 解析参数 JSON
            try:
                params_data = json.loads(params_json)
            except json.JSONDecodeError as e:
                error_msg = f"参数 JSON 格式错误: {str(e)}"
                log_error(0, error_msg, "ONEBOT_API_JSON_ERROR", error=str(e))
                return {
                    'success': False,
                    'error': error_msg
                }

            # 5. 验证参数格式
            if not isinstance(params_data, dict):
                error_msg = '参数必须是 JSON 对象格式，例如：{"key": "value"}'
                log_error(0, error_msg, "ONEBOT_API_PARAMS_FORMAT_ERROR")
                return {
                    'success': False,
                    'error': error_msg
                }

            # 6. 调用 API
            adapter = context.event.bot.adapter
            result = await adapter._call_api(context.event.bot, action, **params_data)

            # 保存响应到上下文变量
            context.set_variable('endpoint_response', result)
            context.set_variable('endpoint_success', True)
            context.set_variable('endpoint_error', '')

            # 标记已处理
            context._response = True

            # 处理跳转
            ret = {'success': True, 'response': result}
            if self.config.get('next_node'):
                ret['next_node'] = self.config['next_node']
            return ret

        except Exception as e:
            error_msg = f"自定义端点调用失败: {str(e)}"
            log_error(0, error_msg, "ONEBOT_API_ERROR", error=str(e))
            context.set_variable('endpoint_response', None)
            context.set_variable('endpoint_success', False)
            context.set_variable('endpoint_error', error_msg)
            return {'success': False, 'error': error_msg}
