"""
HTML渲染节点

将HTML模板渲染为图片
"""
import os
from typing import Any

from Core.logging.file_logger import log_error
from .base import BaseNode


def get_render_templates() -> list[dict]:
    """获取 Render 目录下的所有 HTML 模板"""
    templates = []
    render_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'Render')

    if not os.path.exists(render_dir):
        return templates

    for root, dirs, files in os.walk(render_dir):
        for file in files:
            if file.endswith('.html'):
                # 获取相对于 Render 目录的路径
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, render_dir)
                # 统一使用正斜杠
                rel_path = rel_path.replace('\\', '/')
                templates.append({
                    'value': rel_path,
                    'label': rel_path
                })

    return sorted(templates, key=lambda x: x['label'])


class HtmlRenderNode(BaseNode):
    """HTML渲染节点 - 将模板渲染为图片"""

    name = "HTML渲染"
    description = "将HTML模板渲染为Base64图片"
    category = "action"
    icon = "🖼️"

    inputs = []
    outputs = [
        {'name': 'image_base64', 'label': 'image_base64 - 图片Base64数据', 'type': 'string'},
        {'name': 'render_success', 'label': 'render_success - 渲染是否成功', 'type': 'boolean'},
    ]

    @property
    def config_schema(self):
        """动态生成配置schema，实时获取模板列表"""
        return [
            {
                'name': 'template_path',
                'label': '模板文件',
                'type': 'select',
                'required': True,
                'options': get_render_templates(),
                'help': '选择 Render 目录下的 HTML 模板文件'
            },
            {
                'name': 'template_data',
                'label': '模板数据 (JSON)',
                'type': 'textarea',
                'required': False,
                'default': '{}',
                'placeholder': '{"key": "{{variable}}", "user_id": "{{sender.user_id}}"}',
                'help': '传递给模板的数据，JSON格式，支持变量替换',
                'rows': 6
            },
            {
                'name': 'width',
                'label': '图片宽度',
                'type': 'text',
                'required': False,
                'default': '',
                'placeholder': '800',
                'help': '图片宽度（像素），留空则自适应'
            },
            {
                'name': 'height',
                'label': '图片高度',
                'type': 'text',
                'required': False,
                'default': '',
                'placeholder': '',
                'help': '图片高度（像素），留空则自适应'
            },
            {
                'name': 'next_node',
                'label': '下一个节点',
                'type': 'select',
                'required': False,
                'default': '',
                'options': [],
                'help': '渲染完成后跳转到的节点'
            },
        ]

    async def _execute(self, context) -> dict[str, Any]:
        """执行HTML渲染"""
        import json
        from Core.tools.browser import browser

        template_path_raw = self.config.get('template_path', '').strip()
        # 支持变量替换，如 {{render_template}}
        template_path = context.render_template(template_path_raw)
        template_data_str = self.config.get('template_data', '{}')
        width_str = self.config.get('width', '').strip()
        height_str = self.config.get('height', '').strip()

        # 1. 验证模板路径
        if not template_path:
            log_error(0, "HTML渲染节点: 模板路径不能为空", "RENDER_ERROR")
            context.set_variable('render_success', False)
            context.set_variable('image_base64', '')
            return {
                'success': False,
                'render_success': False,
                'error': '模板路径不能为空'
            }

        # 2. 检查浏览器是否运行
        if not browser.is_running:
            log_error(0, "HTML渲染节点: 浏览器管理器未运行", "RENDER_ERROR")
            context.set_variable('render_success', False)
            context.set_variable('image_base64', '')
            return {
                'success': False,
                'render_success': False,
                'error': '浏览器管理器未运行，请在管理后台启动'
            }

        # 3. 解析模板数据
        try:
            # 先进行变量替换
            rendered_data_str = context.render_template(template_data_str)
            # 将 Python 布尔值转换为 JSON 格式
            rendered_data_str = rendered_data_str.replace(': True', ': true').replace(': False', ': false')
            rendered_data_str = rendered_data_str.replace(':True', ':true').replace(':False', ':false')
            template_data = json.loads(rendered_data_str)
        except json.JSONDecodeError as e:
            log_error(0, f"HTML渲染节点 JSON 解析失败: {e}", "RENDER_JSON_ERROR",
                      raw_data=template_data_str[:500], rendered_data=rendered_data_str[:500])
            context.set_variable('render_success', False)
            context.set_variable('image_base64', '')
            return {
                'success': False,
                'render_success': False,
                'error': f'模板数据JSON格式错误: {e}'
            }

        # 4. 自动注入所有上下文变量到模板数据
        # 将 context.variables 中的所有变量注入到模板数据（如果模板数据中没有定义）
        for var_name, value in context.variables.items():
            # 将点号替换为下划线作为模板变量名
            safe_name = var_name.replace('.', '_')
            if safe_name not in template_data:
                # 跳过不可序列化的对象（如 event, message_api）
                if not callable(value) and not hasattr(value, '__dict__') or isinstance(value, (dict, list, str, int, float, bool, type(None))):
                    template_data[safe_name] = value

        # 5. 解析宽高
        width = int(width_str) if width_str.isdigit() else None
        height = int(height_str) if height_str.isdigit() else None

        # 6. 调用浏览器渲染
        try:
            image_base64 = browser.render(
                template_path=template_path,
                data=template_data,
                width=width,
                height=height
            )

            if image_base64:
                # 渲染成功，保存到上下文变量
                context.set_variable('image_base64', image_base64)
                context.set_variable('render_success', True)

                return {
                    'success': True,
                    'render_success': True,
                    'image_base64': image_base64
                }
            else:
                # 渲染失败
                log_error(0, f"HTML渲染节点: 渲染失败，模板路径={template_path}", "RENDER_ERROR")
                context.set_variable('render_success', False)
                context.set_variable('image_base64', '')
                return {
                    'success': False,
                    'render_success': False,
                    'error': '渲染失败，请检查模板路径是否正确'
                }

        except Exception as e:
            log_error(0, f"HTML渲染节点异常: {e}", "RENDER_ERROR",
                      template_path=template_path, error=str(e))
            context.set_variable('render_success', False)
            context.set_variable('image_base64', '')
            return {
                'success': False,
                'render_success': False,
                'error': f'渲染异常: {str(e)}'
            }
