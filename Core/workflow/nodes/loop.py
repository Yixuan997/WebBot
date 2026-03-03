"""
循环节点

支持遍历列表执行循环体
"""
from typing import Any

from Core.logging.file_logger import log_debug, log_error
from .base import BaseNode


class ForeachNode(BaseNode):
    """
    循环节点 - 遍历列表执行循环体
    
    工作原理：
    1. 从变量中获取列表
    2. 遍历列表，每次将当前元素存入指定变量
    3. 跳转到循环体节点执行
    4. 循环体执行完后返回 foreach 继续下一轮
    5. 遍历完成后跳转到下一个节点
    """

    name = "遍历循环"
    description = "遍历列表，对每个元素执行循环体内的节点"
    category = "control"
    icon = "🔄"

    inputs = [
        {'name': 'list', 'label': '要遍历的列表', 'required': True, 'type': 'array'},
    ]
    outputs = [
        {'name': 'loop_index', 'label': 'loop_index - 当前索引', 'type': 'int'},
        {'name': 'loop_item', 'label': 'loop_item - 当前元素', 'type': 'any'},
        {'name': 'loop_total', 'label': 'loop_total - 列表总数', 'type': 'int'},
    ]

    config_schema = [
        {
            'name': 'list_variable',
            'label': '要循环的列表',
            'type': 'text',
            'required': True,
            'placeholder': 'response_json',
            'help': '填变量名，比如 user_list，会依次取出里面每个元素'
        },
        {
            'name': 'item_variable',
            'label': '每个元素叫什么',
            'type': 'text',
            'required': True,
            'default': 'item',
            'placeholder': 'item',
            'help': '给当前元素起个名字，后面用 {{这个名字}} 来使用它'
        },
        {
            'name': 'loop_body',
            'label': '循环开始的节点',
            'type': 'select',
            'required': True,
            'options': [],
            'help': '每轮循环从哪个节点开始执行'
        },
        {
            'name': 'delay',
            'label': '每轮间隔(秒)',
            'type': 'number',
            'required': False,
            'default': '0',
            'help': '每轮循环之间的间隔时间，防止执行过快'
        },
        {
            'name': 'next_node',
            'label': '循环结束后跳转',
            'type': 'select',
            'required': False,
            'default': '',
            'options': [],
            'help': '所有循环执行完毕后跳转到的节点（留空则顺序执行）'
        }
    ]

    async def _execute(self, context) -> dict[str, Any]:
        """
        执行循环节点
        
        通过 context 中的循环状态来管理迭代进度
        """
        list_variable = self.config.get('list_variable', '').strip()
        item_variable = self.config.get('item_variable', 'item').strip()
        loop_body = self.config.get('loop_body', '').strip()
        delay = float(self.config.get('delay', 0) or 0)

        if not loop_body:
            log_error(0, "未指定循环体节点", "FOREACH_NO_BODY")
            return {'success': False, 'error': '未指定循环体节点'}

        # 获取或初始化循环状态
        # 使用节点配置生成唯一key，而不是id(self)，因为每次执行都会创建新实例
        loop_state_key = f'_foreach_state_{list_variable}_{item_variable}'
        loop_state = context.get_variable(loop_state_key)

        if loop_state is None:
            # 第一次执行：从变量获取列表，并保存到循环状态
            items = context.get_variable(list_variable)
            if items is None:
                log_error(0, f"循环变量 {list_variable} 不存在", "FOREACH_VAR_NOT_FOUND")
                return {'success': False, 'error': f'变量 {list_variable} 不存在'}

            # 智能转换为列表
            if isinstance(items, dict):
                # 字典 → [{key: k, value: v}, ...]
                items = [{'key': k, 'value': v} for k, v in items.items()]
            elif not isinstance(items, (list, tuple)):
                log_error(0, f"变量 {list_variable} 不是列表或字典类型", "FOREACH_NOT_ITERABLE")
                return {'success': False, 'error': f'变量 {list_variable} 不是列表或字典'}

            if not items:
                log_debug(0, f"列表 {list_variable} 为空，跳过循环", "FOREACH_EMPTY_LIST")
                result = {'success': True, 'loop_total': 0}
                if self.config.get('next_node'):
                    result['next_node'] = self.config['next_node']
                return result

            # 初始化循环状态，保存转换后的列表
            loop_state = {
                'index': 0,
                'total': len(items),
                'items': list(items)  # 保存转换后的列表
            }
            context.set_variable(loop_state_key, loop_state)

        # 从状态中获取列表，而不是重新获取变量
        items = loop_state['items']
        current_index = loop_state['index']
        total = loop_state['total']
        
        if current_index >= total:
            # 循环完成，清理状态
            context.set_variable(loop_state_key, None)
            log_debug(0, f"循环完成，共 {total} 轮", "FOREACH_DONE")
            
            result = {
                'success': True,
                'loop_total': total
            }
            if self.config.get('next_node'):
                result['next_node'] = self.config['next_node']
            return result

        # 设置当前元素和索引
        current_item = items[current_index]
        context.set_variable(item_variable, current_item)
        context.set_variable('loop_index', current_index)
        context.set_variable('loop_item', current_item)
        context.set_variable('loop_total', total)

        # 更新循环状态
        loop_state['index'] = current_index + 1
        context.set_variable(loop_state_key, loop_state)

        log_debug(0, f"循环执行: {current_index + 1}/{total}", "FOREACH_ITERATION",
                  index=current_index, total=total)

        # 返回循环控制信息
        return {
            'success': True,
            'loop': True,
            'loop_body': loop_body,
            'loop_return': True,  # 标记需要返回 foreach
            'delay': delay,
            'loop_index': current_index,
            'loop_total': total
        }
