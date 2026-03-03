"""
文档系统路由

处理插件开发文档的浏览和显示
"""

import os

import markdown
from flask import render_template, abort, current_app

from . import docs_bp


def get_docs_directory():
    """获取文档目录路径"""
    # 获取当前蓝图文件所在目录
    blueprint_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(blueprint_dir, 'docs')


def get_available_docs():
    """获取所有可用的文档列表"""
    docs_dir = get_docs_directory()
    if not os.path.exists(docs_dir):
        return []

    docs = []
    for filename in os.listdir(docs_dir):
        if filename.endswith('.md'):
            name = filename[:-3]  # 移除.md扩展名
            title = name.replace('-', ' ').replace('_', ' ').title()
            docs.append({
                'name': name,
                'title': title,
                'filename': filename
            })

    # 按名称排序
    docs.sort(key=lambda x: x['name'])
    return docs


def render_markdown_file(filename):
    """渲染Markdown文件为HTML"""
    docs_dir = get_docs_directory()
    file_path = os.path.join(docs_dir, filename)

    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 配置Markdown渲染器
        md = markdown.Markdown(extensions=[
            'codehilite',  # 代码高亮
            'fenced_code',  # 围栏代码块
            'tables',  # 表格支持
            'toc',  # 目录生成
        ], extension_configs={
            'toc': {
                'anchorlink': True,  # 为标题添加锚点链接
                'permalink': True,  # 添加永久链接
                'permalink_title': '链接到此标题',
                'permalink_class': 'toc-permalink',
                'permalink_leading': False,
            }
        })

        # 预处理Mermaid代码块
        import re

        def replace_mermaid(match):
            mermaid_code = match.group(1)
            return f'<div class="mermaid">\n{mermaid_code}\n</div>'

        # 使用正则表达式替换Mermaid代码块
        content = re.sub(r'```mermaid\n(.*?)\n```', replace_mermaid, content, flags=re.DOTALL)

        html_content = md.convert(content)
        return {
            'content': html_content,
            'toc': md.toc if hasattr(md, 'toc') else ''
        }
    except Exception as e:
        current_app.logger.error(f"读取文档文件失败: {e}")
        return None


@docs_bp.route('/')
def index():
    """文档首页 - 直接显示插件开发文档"""
    # 直接显示插件开发文档
    filename = "workflow-development.md"
    result = render_markdown_file(filename)

    if result is None:
        abort(404)

    title = "插件开发指南"

    return render_template('docs/view.html',
                           title=title,
                           content=result['content'],
                           toc=result['toc'],
                           doc_name='plugin-development')


@docs_bp.route('/<doc_name>')
def view_doc(doc_name):
    """查看具体文档"""
    filename = f"{doc_name}.md"
    result = render_markdown_file(filename)

    if result is None:
        abort(404)

    # 获取文档标题
    title = doc_name.replace('-', ' ').replace('_', ' ').title()

    return render_template('docs/view.html',
                           title=title,
                           content=result['content'],
                           toc=result['toc'],
                           doc_name=doc_name)
