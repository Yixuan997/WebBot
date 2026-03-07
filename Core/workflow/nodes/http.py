"""
HTTP请求相关节点
"""
import asyncio
import json

import aiohttp

from Core.logging.file_logger import log_error
from .base import BaseNode


class HttpRequestNode(BaseNode):
    """HTTP请求节点"""

    name = "HTTP请求"
    description = "发送HTTP请求到外部API"
    category = "network"
    icon = "🌐"

    # 输入输出
    inputs = []  # 可以引用任意变量
    outputs = [
        {'name': 'response_status', 'label': 'response_status - 状态码', 'type': 'integer'},
        {'name': 'response_text', 'label': 'response_text - 响应文本', 'type': 'string'},
        {'name': 'response_json', 'label': 'response_json - JSON响应', 'type': 'object'},
        {'name': 'response_error', 'label': 'response_error - 错误信息', 'type': 'string'},
        {'name': 'response_success', 'label': 'response_success - 是否成功', 'type': 'boolean'},
    ]

    config_schema = [
        {
            'name': 'method',
            'label': '请求方法',
            'type': 'select',
            'options': [
                {'value': 'GET', 'label': 'GET'},
                {'value': 'POST', 'label': 'POST'},
                {'value': 'PUT', 'label': 'PUT'},
                {'value': 'DELETE', 'label': 'DELETE'},
            ],
            'default': 'GET',
            'required': True,
            'help': '选择HTTP请求方法'
        },
        {
            'name': 'url',
            'label': 'URL',
            'type': 'text',
            'required': True,
            'placeholder': 'https://api.example.com/data',
            'help': '请求地址,支持变量如 https://api.com/user/{{user_id}}'
        },
        {
            'name': 'headers',
            'label': '请求头',
            'type': 'textarea',
            'required': False,
            'placeholder': '{"Content-Type": "application/json", "Authorization": "Bearer token"}',
            'help': 'JSON格式的请求头(可选)'
        },
        {
            'name': 'body',
            'label': '请求体',
            'type': 'textarea',
            'required': False,
            'placeholder': '{"key": "value"}',
            'help': 'POST/PUT请求的body,支持变量'
        },
        {
            'name': 'timeout',
            'label': '超时时间(秒)',
            'type': 'text',
            'default': '10',
            'required': False,
            'help': '请求超时时间'
        },
        {
            'name': 'response_type',
            'label': '响应类型',
            'type': 'select',
            'options': [
                {'value': 'auto', 'label': '自动检测'},
                {'value': 'json', 'label': 'JSON'},
                {'value': 'text', 'label': '文本'},
            ],
            'default': 'auto',
            'required': False,
            'help': '期望的响应类型'
        },
    ]

    async def _execute(self, context):
        """
        执行HTTP请求
        
        Args:
            context: WorkflowContext
            
        Returns:
            dict: 执行结果
        """
        method = self.config.get('method', 'GET')
        url = self.config.get('url', '')
        headers_str = self.config.get('headers', '')
        body_str = self.config.get('body', '')
        timeout = int(self.config.get('timeout', 10))
        response_type = self.config.get('response_type', 'auto')

        # 使用context的render_template替换URL中的变量
        url = context.render_template(url)

        # 解析请求头
        headers = {}
        if headers_str:
            try:
                rendered_headers = context.render_template(headers_str)
                headers = json.loads(rendered_headers)
            except json.JSONDecodeError as e:
                log_error(0, f"HTTP请求节点: 请求头JSON格式错误 - {e}", "HTTP_NODE_ERROR", url=url)
                context.set_variable('response_error', '请求头JSON格式无效')
                context.set_variable('response_success', False)
                return {'success': False, 'error': '请求头无效'}

        # 解析请求体
        body = None
        if body_str and method in ['POST', 'PUT']:
            body_rendered = context.render_template(body_str)
            try:
                # 尝试解析为JSON
                body = json.loads(body_rendered)
            except json.JSONDecodeError:
                # 如果不是JSON,就当作纯文本
                body = body_rendered

        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                kwargs = {
                    'method': method,
                    'url': url,
                    'headers': headers,
                }
                
                if body is not None:
                    if isinstance(body, dict):
                        kwargs['json'] = body
                    else:
                        kwargs['data'] = body
                
                async with session.request(**kwargs) as response:
                    response_status = response.status
                    response_text = await response.text()
                    
                    context.set_variable('response_status', response_status)
                    context.set_variable('response_text', response_text)
                    context.set_variable('response_success', response_status < 400)
                    
                    if response_type in ['auto', 'json']:
                        response_json = None
                        response_error = ''
                        try:
                            # 放宽 Content-Type 限制，兼容返回 JSON 但头不规范的接口
                            response_json = await response.json(content_type=None)
                        except (json.JSONDecodeError, aiohttp.ContentTypeError, ValueError):
                            # auto 模式下尝试使用响应文本兜底解析
                            if response_type == 'auto':
                                try:
                                    response_json = json.loads(response_text)
                                except (json.JSONDecodeError, ValueError):
                                    response_json = None
                            else:
                                response_error = '响应不是有效的JSON格式'
                        except TypeError:
                            if response_type == 'json':
                                response_error = '响应不是有效的JSON格式'
                        
                        context.set_variable('response_json', response_json)
                        context.set_variable('response_error', response_error)
                    else:
                        context.set_variable('response_json', None)
                        context.set_variable('response_error', '')
                    
                    return {
                        'success': True,
                        'status_code': response_status,
                    }

        except asyncio.TimeoutError:
            error_msg = f'请求超时，超过 {timeout} 秒未响应'
            log_error(0, f"HTTP请求节点: 请求超时 - {error_msg}", "HTTP_NODE_ERROR", url=url)
            context.set_variable('response_error', error_msg)
            context.set_variable('response_success', False)
            return {'success': False, 'error': error_msg}

        except aiohttp.ClientError as e:
            error_msg = f'请求失败: {str(e)}'
            log_error(0, f"HTTP请求节点: 请求失败 - {error_msg}", "HTTP_NODE_ERROR", url=url)
            context.set_variable('response_error', error_msg)
            context.set_variable('response_success', False)
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f'请求失败: {str(e)}'
            log_error(0, f"HTTP请求节点: 请求异常 - {error_msg}", "HTTP_NODE_ERROR", url=url)
            context.set_variable('response_error', error_msg)
            context.set_variable('response_success', False)
            return {'success': False, 'error': error_msg}


class JsonExtractNode(BaseNode):
    """JSON提取节点"""

    name = "JSON提取"
    description = "从JSON中提取指定字段"
    category = "data"
    icon = "📋"

    # 输入输出
    inputs = [
        {'name': 'json_source', 'label': 'JSON源变量', 'required': True, 'type': 'object'},
    ]
    outputs = []  # 动态输出,根据配置

    config_schema = [
        {
            'name': 'json_source',
            'label': 'JSON源变量',
            'type': 'select',
            'options': [
                {'value': 'response_json', 'label': 'response_json - HTTP响应'},
                {'value': 'endpoint_response', 'label': 'endpoint_response - 自定义端点响应'},
                {'value': 'raw_data', 'label': 'raw_data - 消息原始数据'},
                {'value': 'message', 'label': 'message - 消息内容'},
            ],
            'required': True,
            'help': '包含JSON数据的变量名'
        },
        {
            'name': 'extract_path',
            'label': '提取路径',
            'type': 'text',
            'required': True,
            'placeholder': 'data.user.name 或 items[0].id',
            'help': '使用点号和方括号访问嵌套字段'
        },
        {
            'name': 'save_to',
            'label': '保存到变量',
            'type': 'text',
            'required': True,
            'placeholder': 'user_name',
            'help': '提取后保存到的变量名'
        },
        {
            'name': 'default_value',
            'label': '默认值',
            'type': 'text',
            'required': False,
            'placeholder': '',
            'help': '如果提取失败使用的默认值(可选)'
        },
    ]

    async def _execute(self, context) -> dict[str, any]:
        """
        执行JSON提取
        
        Args:
            context: WorkflowContext
            
        Returns:
            dict: 执行结果
        """
        json_source_name = self.config.get('json_source', '')
        extract_path = self.config.get('extract_path', '')
        save_to = self.config.get('save_to', '')
        default_value = self.config.get('default_value', None)

        # 获取JSON源数据
        json_data = context.get_variable(json_source_name)

        if not json_data:
            log_error(0, f"JSON提取节点: JSON源为空 - {json_source_name}", "JSON_EXTRACT_ERROR")
            context.set_variable(save_to, default_value)
            return {'success': False, 'error': 'JSON源数据为空'}

        # 如果是字符串,尝试解析为JSON
        if isinstance(json_data, str):
            try:
                json_data = json.loads(json_data)
            except json.JSONDecodeError as e:
                log_error(0, f"JSON提取节点: 无效的JSON字符串 - {e}", "JSON_EXTRACT_ERROR")
                context.set_variable(save_to, default_value)
                return {'success': False, 'error': '无效的JSON字符串'}

        # 提取字段
        try:
            value = self._extract_value(json_data, extract_path)
            context.set_variable(save_to, value)
            return {'success': True, 'value': value}
        except Exception as e:
            log_error(0, f"JSON提取节点: 提取失败 - {e}", "JSON_EXTRACT_ERROR", path=extract_path)
            context.set_variable(save_to, default_value)
            return {'success': False, 'error': str(e)}

    def _extract_value(self, data: any, path: str) -> any:
        """
        从嵌套数据结构中提取值
        
        Args:
            data: 数据源
            path: 提取路径,如 "data.user.name" 或 "items[0].id"
            
        Returns:
            提取的值
        """
        if not path:
            return data

        # 分割路径
        parts = path.replace('[', '.').replace(']', '').split('.')

        current = data
        for part in parts:
            if not part:
                continue

            # 尝试作为数组索引
            if part.isdigit():
                current = current[int(part)]
            # 尝试作为字典键
            elif isinstance(current, dict):
                current = current.get(part)
            # 尝试作为对象属性
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                raise KeyError(f'无法访问路径 "{path}" 中的 "{part}"')

            if current is None:
                break

        return current
