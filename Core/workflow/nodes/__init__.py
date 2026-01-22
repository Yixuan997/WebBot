"""
工作流节点模块

自动扫描并注册所有节点类型
"""
import importlib
import re
from pathlib import Path

from Core.logging.file_logger import log_error
from .base import BaseNode
from ..registry import NodeRegistry


def _camel_to_snake(name: str) -> str:
    """将驼峰命名转换为下划线命名：SendMessageNode -> send_message"""
    if name.endswith('Node'):
        name = name[:-4]
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def auto_register_nodes():
    """
    自动扫描 nodes 目录下的所有 .py 文件，注册 BaseNode 子类
    
    规则:
    - 跳过 base.py 和 __init__.py
    - 类名自动转换为 node_type：SendMessageNode -> send_message
    - 如果节点定义了 node_type 属性，优先使用
    """
    nodes_dir = Path(__file__).parent

    for file_path in nodes_dir.glob('*.py'):
        if file_path.stem in ('__init__', 'base') or file_path.stem.startswith('_'):
            continue

        try:
            module = importlib.import_module(f'.{file_path.stem}', package='Core.workflow.nodes')

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if (isinstance(attr, type) and
                        issubclass(attr, BaseNode) and
                        attr is not BaseNode):

                    # 优先使用节点类的 node_type 属性
                    if hasattr(attr, 'node_type') and attr.node_type:
                        node_type = attr.node_type
                    else:
                        node_type = _camel_to_snake(attr.__name__)

                    NodeRegistry.register(node_type, attr)

        except Exception as e:
            log_error(0, f"注册节点模块失败: {file_path.stem}",
                      "NODE_REGISTER_ERROR",
                      module=file_path.stem,
                      error=str(e))


# 模块导入时自动注册
auto_register_nodes()

__all__ = ['auto_register_nodes']
