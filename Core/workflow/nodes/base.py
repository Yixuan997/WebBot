"""
工作流节点基类

所有节点类型的基础抽象类
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseNode(ABC):
    """节点基类"""

    # 节点元信息（子类需要定义）
    name = "Base Node"
    description = ""
    category = "other"  # trigger, condition, action, data
    icon = "📦"

    # 配置项定义（用于前端生成表单）
    config_schema = []

    # 输入输出定义
    inputs = []  # 输入变量: [{'name': 'var', 'label': 'Label', 'required': True/False, 'type': 'string'}]
    outputs = []  # 输出变量: [{'name': 'result', 'label': 'Result', 'type': 'string'}]
    """
    示例:
    [
        {
            'name': 'pattern',
            'label': '匹配内容',
            'type': 'text',
            'required': True,
            'placeholder': '请输入...'
        }
    ]
    """

    def __init__(self, config: dict[str, Any]):
        """
        初始化节点
        
        Args:
            config: 节点配置字典
        """
        self.config = config

    async def execute(self, context) -> Any:
        """
        执行节点（引擎调用入口）
        
        此方法不应被子类覆盖，子类应该实现 _execute() 方法。
        
        Args:
            context: WorkflowContext 执行上下文
            
        Returns:
            执行结果
        """
        # 1. 执行节点逻辑
        result = await self._execute(context)

        # 2. 统一注入显式跳转
        # 节点可只在 config 中声明 next_node，这里统一回填到 result
        if isinstance(result, dict):
            next_node = self.config.get('next_node')
            if next_node and 'next_node' not in result:
                result['next_node'] = next_node

        # 3. 自动保存输出到 context
        self._auto_save_outputs(context, result)

        # 4. 返回结果给引擎
        return result

    @abstractmethod
    async def _execute(self, context) -> Any:
        """
        执行节点逻辑（子类实现此方法）
        
        Args:
            context: WorkflowContext 执行上下文
            
        Returns:
            执行结果，通常是 dict 类型
        """
        pass

    def _auto_save_outputs(self, context, result: Any):
        """
        自动保存节点输出到 context
        
        根据节点的 outputs 声明，自动将结果中的变量保存到上下文。
        
        Args:
            context: WorkflowContext 执行上下文
            result: 节点执行结果
        """
        if not isinstance(result, dict):
            return

        # 获取声明的输出变量名称
        output_names = {out['name'] for out in self.outputs}

        # 只保存声明的输出变量
        for key, value in result.items():
            if key in output_names and value is not None:
                context.set_variable(key, value)

    def should_break(self, result: Any) -> bool:
        """
        判断是否应该中断流程
        
        Args:
            result: execute()的返回值
            
        Returns:
            是否中断
        """
        return False

    def validate_config(self) -> tuple[bool, str]:
        """
        验证配置是否有效
        
        Returns:
            (是否有效, 错误信息)
        """
        # 检查必填字段
        for field in self.config_schema:
            if field.get('required') and field['name'] not in self.config:
                return False, f"缺少必填字段: {field['label']}"
        return True, ""

    def validate_inputs(self, context) -> tuple[bool, str]:
        """
        验证输入变量是否满足
        
        Args:
            context: WorkflowContext 执行上下文
            
        Returns:
            (是否有效, 错误信息)
        """
        for input_def in self.inputs:
            if input_def.get('required', False):
                var_name = input_def['name']
                if var_name not in context.variables:
                    return False, f"缺少必需输入变量: {input_def.get('label', var_name)}"
        return True, ""

    def get_available_outputs(self) -> list[str]:
        """
        获取节点会产生的输出变量名称列表
        
        Returns:
            输出变量名称列表
        """
        return [out['name'] for out in self.outputs]
