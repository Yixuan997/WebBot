"""
插件开发文档系统

简单的文档浏览系统，专注于插件开发文档：
- 读取Markdown文件
- 渲染为HTML显示
- 支持代码高亮
"""

from flask import Blueprint

# 创建文档蓝图
docs_bp = Blueprint(
    'docs',
    __name__,
    url_prefix='/docs',
    template_folder='templates',
    static_folder='static'
)

# 导入路由
from . import main


def register_docs_blueprint(app):
    """注册文档蓝图到Flask应用"""
    app.register_blueprint(docs_bp)
