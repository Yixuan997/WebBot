"""
条件判断节点
"""
from typing import Any

from .base import BaseNode


class ConditionNode(BaseNode):
    """条件判断节点 - 支持多种比较运算"""

    name = "条件判断"
    description = "根据条件判断跳转到不同分支"
    category = "logic"
    icon = "🔀"

    # 输入输出
    inputs = [
        {'name': 'variable_name', 'label': '字段/变量', 'required': True, 'type': 'string'},
        {'name': 'compare_value', 'label': '比较内容', 'required': False, 'type': 'string'},
    ]
    outputs = [
        {'name': 'result', 'label': '判断结果', 'type': 'boolean'},
    ]

    config_schema = [
        {
            'name': 'mode',
            'label': '模式',
            'type': 'select',
            'required': True,
            'default': 'simple',
            'options': [
                {'value': 'simple', 'label': '简单模式 - 单个条件'},
                {'value': 'advanced', 'label': '高级模式 - 多条件组合'},
            ],
            'help': '选择判断模式'
        },
        {
            'name': 'variable_name',
            'label': '字段/变量',
            'type': 'variable_select',
            'required': False,
            'placeholder': '选择或输入变量',
            'help': '选择上游节点产生的变量'
        },
        {
            'name': 'condition_type',
            'label': '怎么比较',
            'type': 'select',
            'required': False,
            'default': 'equals',
            'options': [
                {'value': 'equals', 'label': '等于 (==)'},
                {'value': 'not_equals', 'label': '不等于 (!=)'},
                {'value': 'contains', 'label': '包含'},
                {'value': 'not_contains', 'label': '不包含'},
                {'value': 'starts_with', 'label': '开头是'},
                {'value': 'ends_with', 'label': '结尾是'},
                {'value': 'greater_than', 'label': '大于 (>)'},
                {'value': 'less_than', 'label': '小于 (<)'},
                {'value': 'is_empty', 'label': '为空'},
                {'value': 'is_not_empty', 'label': '不为空'},
                {'value': 'regex', 'label': '正则匹配'},
            ],
            'help': '选择判断方式'
        },
        {
            'name': 'compare_value',
            'label': '比较内容',
            'type': 'text',
            'required': False,
            'placeholder': '比较的目标值',
            'help': '某些运算符（如"为空"）不需要此项'
        },
        {
            'name': 'logic_type',
            'label': '多条件关系',
            'type': 'select',
            'required': False,
            'default': 'AND',
            'options': [
                {'value': 'AND', 'label': '全部满足才算通过'},
                {'value': 'OR', 'label': '满足一个就算通过'},
            ],
            'help': '有多个条件时，怎么算通过'
        },
        {
            'name': 'conditions',
            'label': '条件列表',
            'type': 'textarea',
            'required': False,
            'default': '',
            'placeholder': 'message|contains|你好\nsender.user_id|equals|123',
            'help': '格式: 变量名|运算符|比较值，每行一个',
            'help_extra': [
                {'label': '运算符',
                 'values': ['equals(等于)', 'not_equals(不等于)', 'contains(包含)', 'starts_with(开头)',
                            'ends_with(结尾)', 'regex(正则)', 'is_empty(为空)', 'is_not_empty(不为空)']}
            ]
        },
        {
            'name': 'true_branch',
            'label': '满足条件跳转到',
            'type': 'select',  # 改为select以触发前端动态渲染
            'required': False,
            'default': '',
            'options': [],  # 前端动态填充
            'help': '选择跳转目标节点（留空则继续下一个节点）'
        },
        {
            'name': 'false_branch',
            'label': '不满足条件跳转到',
            'type': 'select',  # 改为select以触发前端动态渲染
            'required': False,
            'default': '',
            'options': [],  # 前端动态填充
            'help': '选择跳转目标节点（留空则继续下一个节点或中断）'
        },
        {
            'name': 'stop_after_branch',
            'label': '分支执行后停止',
            'type': 'checkbox',
            'default': False,
            'help': '执行完分支后停止执行后续节点（在循环中会继续下一次迭代）'
        },
    ]

    async def _execute(self, context) -> Any:
        """执行条件判断"""
        mode = self.config.get('mode', 'simple')

        if mode == 'advanced':
            # 高级模式：多条件组合
            result = self._execute_advanced(context)
        else:
            # 简单模式：单个条件
            result = self._execute_simple(context)

        return result

    def _execute_simple(self, context) -> Any:
        """简单模式：单个条件判断"""
        # 获取配置参数
        variable_name = self.config.get('variable_name', '')
        compare_value = self.config.get('compare_value', '')
        operator = self.config.get('condition_type', 'equals')

        # 从上下文获取变量值
        value1 = str(context.get_variable(variable_name, ''))
        # 比较值支持模板渲染
        value2 = context.render_template(str(compare_value))
        
        # 执行判断
        result = False

        # 根据运算符执行比较
        match operator:
            case 'equals':
                result = value1 == value2
            case 'not_equals':
                result = value1 != value2
            case 'contains':
                result = value2 in value1
            case 'not_contains':
                result = value2 not in value1
            case 'starts_with':
                result = value1.startswith(value2)
            case 'ends_with':
                result = value1.endswith(value2)
            case 'greater_than':
                try:
                    result = float(value1) > float(value2)
                except ValueError:
                    result = False
            case 'less_than':
                try:
                    result = float(value1) < float(value2)
                except ValueError:
                    result = False
            case 'is_empty':
                result = not value1 or value1.strip() == ''
            case 'is_not_empty':
                result = bool(value1 and value1.strip())
            case 'regex':
                import re
                try:
                    result = bool(re.search(value2, value1))
                except re.error:
                    result = False

        # 保存结果到上下文
        context.set_variable('result', result)

        # 确定跳转目标
        if result:
            next_node = self.config.get('true_branch')
        else:
            next_node = self.config.get('false_branch')
        
        stop_after = self.config.get('stop_after_branch', False)

        return {
            'success': True,
            'result': result,
            'next_node': next_node if next_node else None,
            'stop_sequence': stop_after
        }

    def _execute_advanced(self, context) -> Any:
        """高级模式：多条件组合判断"""
        logic_type = self.config.get('logic_type', 'AND')
        conditions_text = self.config.get('conditions', '').strip()

        if not conditions_text:
            # 没有条件，默认返回True
            return self._build_result(context, True)

        # 解析条件
        conditions = []
        for line in conditions_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):  # 跳过空行和注释
                continue

            parts = line.split('|')
            if len(parts) < 2:
                continue  # 格式不正确，跳过

            variable_name = parts[0].strip()
            operator = parts[1].strip()
            compare_value = parts[2].strip() if len(parts) > 2 else ''

            conditions.append({
                'variable': variable_name,
                'operator': operator,
                'value': compare_value
            })

        if not conditions:
            # 解析后没有有效条件
            return self._build_result(context, True)

        # 执行条件判断
        results = []
        for cond in conditions:
            variable_name = cond['variable']
            operator = cond['operator']
            compare_value = cond['value']

            # 从上下文获取变量值，统一使用模板语法
            value1 = str(context.render_template(variable_name))
            # 比较值支持模板渲染
            value2 = context.render_template(str(compare_value))

            # 执行单个条件判断
            result = self._evaluate_single_condition(value1, operator, value2)
            results.append(result)

        # 根据逻辑类型组合结果
        if logic_type == 'AND':
            final_result = all(results)
        else:  # OR
            final_result = any(results)

        return self._build_result(context, final_result)

    def _evaluate_single_condition(self, value1: str, operator: str, value2: str) -> bool:
        """评估单个条件（用于高级模式）"""
        try:
            if operator == 'equals':
                return value1 == value2
            elif operator == 'not_equals':
                return value1 != value2
            elif operator == 'contains':
                return value2 in value1
            elif operator == 'not_contains':
                return value2 not in value1
            elif operator == 'starts_with':
                return value1.startswith(value2)
            elif operator == 'ends_with':
                return value1.endswith(value2)
            elif operator == 'greater_than':
                try:
                    return float(value1) > float(value2)
                except ValueError:
                    return False
            elif operator == 'less_than':
                try:
                    return float(value1) < float(value2)
                except ValueError:
                    return False
            elif operator == 'is_empty':
                return not value1 or value1.strip() == ''
            elif operator == 'is_not_empty':
                return bool(value1 and value1.strip())
            elif operator == 'regex':
                import re
                try:
                    return bool(re.search(value2, value1))
                except re.error:
                    return False
            else:
                return False
        except Exception:
            return False

    def _build_result(self, context, condition_result: bool) -> dict:
        """构建返回结果"""
        # 保存结果到上下文
        context.set_variable('result', condition_result)

        # 确定跳转目标
        if condition_result:
            next_node = self.config.get('true_branch')
        else:
            next_node = self.config.get('false_branch')

        return {
            'success': True,
            'result': condition_result,
            'next_node': next_node if next_node else None
        }

    def should_break(self, result: Any) -> bool:
        """判断是否应该中断流程"""
        if not isinstance(result, dict):
            return False

        condition_result = result.get('result', False)
        next_node = result.get('next_node')

        # 如果条件为假，且没有指定下一步跳转节点，则中断流程
        if not condition_result and not next_node:
            return True

        return False
