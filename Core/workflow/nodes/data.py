"""
数据处理节点
"""
import re
from typing import Any

from Core.logging.file_logger import log_error
from .base import BaseNode


class SetVariableNode(BaseNode):
    """设置变量节点"""

    name = "设置变量"
    description = "设置或修改上下文变量"
    category = "data"
    icon = "📝"

    inputs = []
    outputs = []

    config_schema = [
        {
            'name': 'variable_name',
            'label': '变量名',
            'type': 'text',
            'required': True,
            'placeholder': 'my_variable',
            'help': '要设置的变量名'
        },
        {
            'name': 'variable_value',
            'label': '变量值',
            'type': 'textarea',
            'required': True,
            'placeholder': '支持变量：{{message}} 或 固定值',
            'help': '支持变量替换',
            'rows': 3
        },
        {
            'name': 'next_node',
            'label': '下一个节点',
            'type': 'select',
            'required': False,
            'options': [],
            'help': '执行完成后跳转到的节点'
        },
    ]

    async def _execute(self, context):
        """执行设置变量"""
        variable_name = self.config.get('variable_name', '')
        variable_value_template = self.config.get('variable_value', '')

        # 渲染值
        variable_value = context.render_template(variable_value_template)
        
        # 设置变量
        context.set_variable(variable_name, variable_value)

        result = {
            'success': True,
            'variable': variable_name,
            'value': variable_value
        }
        
        next_node = self.config.get('next_node')
        if next_node:
            result['next_node'] = next_node
        
        return result


class StringOperationNode(BaseNode):
    """字符串操作节点"""

    name = "字符串处理"
    description = "对字符串进行各种处理操作"
    category = "data"
    icon = "✂️"

    inputs = [
        {'name': 'input', 'label': '输入字符串', 'required': True, 'type': 'string'},
    ]
    outputs = [
        {'name': 'output', 'label': 'output - 处理后的字符串', 'type': 'string'},
    ]

    config_schema = [
        {
            'name': 'input',
            'label': '输入字符串',
            'type': 'variable_select',
            'required': True,
            'help': '选择要处理的变量'
        },
        {
            'name': 'operation',
            'label': '操作类型',
            'type': 'select',
            'required': True,
            'default': 'trim',
            'options': [
                {'value': 'trim', 'label': '去除首尾空格'},
                {'value': 'upper', 'label': '转大写'},
                {'value': 'lower', 'label': '转小写'},
                {'value': 'replace', 'label': '替换'},
                {'value': 'regex_extract', 'label': '正则提取'},
                {'value': 'regex_replace', 'label': '正则替换'},
                {'value': 'substring', 'label': '截取子串'},
                {'value': 'split', 'label': '分割'},
            ]
        },
        {
            'name': 'param1',
            'label': '查找内容/正则/分隔符',
            'type': 'text',
            'required': False,
            'placeholder': '',
            'help': '替换:要查找的内容 | 正则提取/替换:正则表达式 | 截取:起始,结束 | 分割:分隔符'
        },
        {
            'name': 'param2',
            'label': '替换为',
            'type': 'text',
            'required': False,
            'placeholder': '',
            'help': '替换/正则替换时的目标内容'
        },
        {
            'name': 'save_to',
            'label': '保存到变量',
            'type': 'text',
            'required': True,
            'default': 'output',
            'placeholder': 'output',
            'help': '结果保存的变量名'
        },
        {
            'name': 'next_node',
            'label': '下一个节点',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '处理完成后跳转到的节点'
        },
    ]

    async def _execute(self, context) -> dict[str, Any]:
        """执行字符串操作"""
        # 从变量选择器获取变量名，然后获取变量值
        input_var = self.config.get('input', '')
        input_str = str(context.get_variable(input_var, ''))
        operation = self.config.get('operation', 'trim')
        param1 = self.config.get('param1', '')
        param2 = self.config.get('param2', '')
        save_to = self.config.get('save_to', 'output')

        result = input_str

        try:
            match operation:
                case 'trim':
                    result = input_str.strip()
                case 'upper':
                    result = input_str.upper()
                case 'lower':
                    result = input_str.lower()
                case 'replace':
                    if param1:
                        result = input_str.replace(param1, param2)
                case 'regex_extract':
                    # 正则提取：param1 是正则表达式，提取第一个匹配或第一个捕获组
                    if param1:
                        match = re.search(param1, input_str)
                        if match:
                            # 如果有捕获组，返回第一个捕获组，否则返回整个匹配
                            result = match.group(1) if match.groups() else match.group(0)
                        else:
                            result = ''  # 没匹配到返回空字符串
                case 'regex_replace':
                    # 正则替换：param1 是正则表达式，param2 是替换内容（支持 \1 等反向引用）
                    if param1:
                        result = re.sub(param1, param2, input_str)
                case 'substring':
                    if param1:
                        parts = param1.split(',')
                        if len(parts) == 2:
                            start, end = int(parts[0]), int(parts[1])
                            result = input_str[start:end]
                        elif len(parts) == 1:
                            start = int(parts[0])
                            result = input_str[start:]
                case 'split':
                    if param1:
                        result = input_str.split(param1)

            # 保存结果
            context.set_variable(save_to, result)

            return {'success': True, 'output': result}

        except Exception as e:
            log_error(0, f"字符串处理节点: 操作失败 - {e}", "STRING_OP_ERROR", operation=operation)
            return {'success': False, 'error': str(e)}
