"""
代码片段节点
"""
from typing import Any

from Core.logging.file_logger import log_error
from .base import BaseNode


class PythonSnippetNode(BaseNode):
    """Python代码片段节点"""

    name = "Python代码"
    description = "执行Python代码片段"
    category = "advanced"
    icon = "🐍"

    inputs = []
    outputs = [
        {'name': 'result', 'label': 'result - 执行结果', 'type': 'Any'},
    ]

    config_schema = [
        {
            'name': 'snippet_name',
            'label': '代码片段',
            'type': 'select',
            'required': True,
            'default': '',
            'options': [],  # 前端动态加载
            'help': '选择预定义的代码片段，存储在 Snippets/ 目录中'
        },
    ]

    async def _execute(self, context):
        """执行Python代码片段（支持异步）"""
        import os

        snippet_name = self.config.get('snippet_name', '')

        if not snippet_name:
            log_error(0, "Python代码节点: 代码片段名称为空", "SNIPPET_ERROR")
            return {'success': False, 'error': 'Snippet name is empty'}

        try:
            # 构建代码片段文件路径
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            snippets_dir = os.path.join(base_dir, 'Snippets')
            snippet_path = os.path.join(snippets_dir, snippet_name)

            # 检查文件是否存在
            if not os.path.exists(snippet_path):
                log_error(0, f"Python代码节点: 代码片段文件不存在 - {snippet_name}", "SNIPPET_ERROR")
                return {'success': False, 'error': f'Snippet file not found: {snippet_name}'}

            # 读取代码片段
            with open(snippet_path, 'r', encoding='utf-8') as f:
                code = f.read()

            # 创建异步执行环境
            exec_globals = {
                'context': context,
                '__builtins__': __builtins__,
                '__file__': snippet_path,
                '__snippets_dir__': snippets_dir,
            }

            # 将代码包装在异步函数中
            async_code = f'''
async def __snippet_main__():
{chr(10).join('    ' + line for line in code.splitlines())}
    return locals().get("result", None)
'''

            # 执行并获取异步函数
            exec(async_code, exec_globals)
            result = await exec_globals['__snippet_main__']()

            context.set_variable('result', result)

            return {'success': True, 'result': result}

        except Exception as e:
            log_error(0, f"Python代码节点: 执行失败 - {e}", "SNIPPET_ERROR", snippet=snippet_name)
            return {'success': False, 'error': str(e)}


class CommentNode(BaseNode):
    """注释节点"""

    name = "注释"
    description = "添加注释说明（不执行任何操作）"
    category = "utility"
    icon = "💬"

    inputs = []
    outputs = []

    config_schema = [
        {
            'name': 'comment',
            'label': '注释内容',
            'type': 'textarea',
            'required': False,
            'placeholder': '在此输入注释说明...',
            'help': '此节点仅用于说明，不会执行任何操作',
            'rows': 3
        },
    ]

    def execute(self, context) -> dict[str, Any]:
        """注释节点不执行任何操作"""
        return {'success': True}
