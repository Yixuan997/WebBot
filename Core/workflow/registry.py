"""
工作流节点注册表
"""
from typing import Type


class NodeRegistry:
    """节点注册表 - 管理所有可用的工作流节点（单例模式，仅使用类方法）"""

    # 类变量：存储所有已注册的节点
    _nodes: dict[str, Type] = {}
    _category_cache: dict[str, list[Type]] = {}  # 分类缓存

    def __init__(self):
        """禁止实例化，请直接使用类方法"""
        raise TypeError("NodeRegistry 不应该被实例化，请直接使用类方法，如 NodeRegistry.register()")

    @classmethod
    def register(cls, node_type: str, node_class: Type):
        """
        注册节点
        
        Args:
            node_type: 节点类型标识（如 "start", "send_message"）
            node_class: 节点类
        """
        cls._nodes[node_type] = node_class
        # 清空分类缓存
        cls._category_cache = {}

    @classmethod
    def get_node(cls, node_type: str) -> Type | None:
        """
        获取节点类
        
        Args:
            node_type: 节点类型标识
            
        Returns:
            节点类，如果不存在返回None
        """
        return cls._nodes.get(node_type)

    @classmethod
    def list_all(cls) -> dict[str, Type]:
        """
        列出所有已注册的节点
        
        Returns:
            dict: {node_type: node_class}
        """
        return cls._nodes.copy()

    @classmethod
    def list_by_category(cls, category: str = None) -> list[Type]:
        """
        按分类列出节点（带缓存）
        
        Args:
            category: 分类名称，如 "core", "action", "condition" 等
                     如果为None，返回所有节点
        
        Returns:
            list: 节点类列表
        """
        if category is None:
            return list(cls._nodes.values())

        # 检查缓存
        if category in cls._category_cache:
            return cls._category_cache[category]

        # 构建缓存
        result = []
        for node_class in cls._nodes.values():
            if hasattr(node_class, 'category') and node_class.category == category:
                result.append(node_class)

        cls._category_cache[category] = result
        return result

    @classmethod
    def get_categories(cls) -> list[str]:
        """
        获取所有分类
        
        Returns:
            list: 分类名称列表
        """
        categories = set()
        for node_class in cls._nodes.values():
            if hasattr(node_class, 'category'):
                categories.add(node_class.category)
        return sorted(list(categories))
