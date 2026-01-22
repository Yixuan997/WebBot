"""
数据存储节点

提供数据持久化存储，支持增删改查操作
"""
import json
import re
import asyncio
from pathlib import Path
from typing import Any

from Core.logging.file_logger import log_error, log_debug
from .base import BaseNode

# 存储根目录
STORAGE_BASE_DIR = Path(__file__).parent.parent.parent.parent / 'Data'

# 文件锁（防止并发写入）
_file_locks: dict[str, asyncio.Lock] = {}


def _get_lock(storage_name: str) -> asyncio.Lock:
    """获取指定存储的锁"""
    if storage_name not in _file_locks:
        _file_locks[storage_name] = asyncio.Lock()
    return _file_locks[storage_name]


def _validate_name(name: str) -> bool:
    """验证名称是否合法（只允许字母、数字、下划线）"""
    return bool(re.match(r'^[a-zA-Z0-9_]+$', name))


def _get_storage_path(storage_name: str) -> Path:
    """获取存储文件路径"""
    STORAGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    return STORAGE_BASE_DIR / f'{storage_name}.json'


def _load_storage(storage_name: str) -> dict:
    """加载存储数据"""
    path = _get_storage_path(storage_name)
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log_error(0, f"加载存储失败: {storage_name} - {e}", "STORAGE_LOAD_ERROR")
            return {}
    return {}


def _save_storage(storage_name: str, data: dict):
    """保存存储数据"""
    path = _get_storage_path(storage_name)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        log_error(0, f"保存存储失败: {storage_name} - {e}", "STORAGE_SAVE_ERROR")
        raise


class DataStorageNode(BaseNode):
    """数据存储节点"""

    name = "数据存储"
    description = "持久化存储数据，支持增删改查"
    category = "data"
    icon = "💾"

    inputs = []
    outputs = [
        {'name': 'result', 'label': 'result - 操作结果', 'type': 'any'},
        {'name': 'success', 'label': 'success - 是否成功', 'type': 'boolean'},
    ]

    config_schema = [
        {
            'name': 'storage_name',
            'label': '存储名称',
            'type': 'text',
            'required': True,
            'placeholder': 'my_data',
            'help': '存储名称，保存到 Data/{名称}.json（只允许字母、数字、下划线）'
        },
        {
            'name': 'operation',
            'label': '操作类型',
            'type': 'select',
            'required': True,
            'default': 'get',
            'options': [
                {'value': 'get', 'label': '查询 - 根据键获取值'},
                {'value': 'set', 'label': '新增/修改 - 设置键值'},
                {'value': 'delete', 'label': '删除 - 删除指定键'},
                {'value': 'exists', 'label': '判断 - 键是否存在'},
                {'value': 'list_keys', 'label': '列出所有键'},
                {'value': 'get_all', 'label': '获取全部数据'},
                {'value': 'clear', 'label': '清空存储'},
            ]
        },
        {
            'name': 'key',
            'label': '键名',
            'type': 'text',
            'required': False,
            'placeholder': '支持变量：{{sender_id}}',
            'help': '查询/设置/删除/判断时需要'
        },
        {
            'name': 'value',
            'label': '值',
            'type': 'textarea',
            'required': False,
            'placeholder': '支持变量：{{message}}',
            'help': '设置操作时的值',
            'rows': 2
        },
        {
            'name': 'default_value',
            'label': '默认值',
            'type': 'text',
            'required': False,
            'placeholder': '键不存在时返回的默认值',
            'help': '查询操作时，键不存在返回此值'
        },
        {
            'name': 'save_to',
            'label': '保存到变量',
            'type': 'text',
            'required': False,
            'default': 'result',
            'placeholder': 'result',
            'help': '将结果保存到指定变量'
        },
    ]

    async def _execute(self, context) -> dict[str, Any]:
        """执行存储操作"""
        storage_name = self.config.get('storage_name', '')
        operation = self.config.get('operation', 'get')
        key_template = self.config.get('key', '')
        value_template = self.config.get('value', '')
        default_value = self.config.get('default_value', '')
        save_to = self.config.get('save_to', 'result')

        # 验证存储名称
        if not storage_name or not _validate_name(storage_name):
            return {
                'success': False,
                'result': None,
                'error': '存储名称无效（只允许字母、数字、下划线）'
            }

        # 渲染键和值
        key = context.render_template(key_template) if key_template else ''
        value = context.render_template(value_template) if value_template else ''

        # 获取文件锁
        lock = _get_lock(storage_name)

        try:
            async with lock:
                result = await self._do_operation(
                    storage_name, operation, key, value, default_value
                )

            # 保存结果到变量
            if save_to and result.get('result') is not None:
                context.set_variable(save_to, result.get('result'))

            log_debug(0, f"数据存储: Data/{storage_name}.json - {operation}({key})", 
                     "STORAGE_OP", operation=operation, key=key)

            return result

        except Exception as e:
            log_error(0, f"数据存储操作失败: {e}", "STORAGE_ERROR",
                     path=f"Data/{storage_name}.json", operation=operation)
            return {
                'success': False,
                'result': None,
                'error': str(e)
            }

    async def _do_operation(self, storage_name: str, operation: str, 
                           key: str, value: str, default_value: str) -> dict[str, Any]:
        """执行具体操作"""
        data = _load_storage(storage_name)

        match operation:
            case 'get':
                # 查询
                if not key:
                    return {'success': False, 'result': None, 'error': '查询操作需要指定键名'}
                result = data.get(key, default_value if default_value else None)
                return {'success': True, 'result': result}

            case 'set':
                # 新增/修改
                if not key:
                    return {'success': False, 'result': None, 'error': '设置操作需要指定键名'}
                
                # 尝试解析 JSON 值
                parsed_value = self._parse_value(value)
                data[key] = parsed_value
                _save_storage(storage_name, data)
                return {'success': True, 'result': parsed_value}

            case 'delete':
                # 删除
                if not key:
                    return {'success': False, 'result': None, 'error': '删除操作需要指定键名'}
                if key in data:
                    deleted = data.pop(key)
                    _save_storage(storage_name, data)
                    return {'success': True, 'result': deleted}
                else:
                    return {'success': True, 'result': None}

            case 'exists':
                # 判断键是否存在
                if not key:
                    return {'success': False, 'result': None, 'error': '判断操作需要指定键名'}
                exists = key in data
                return {'success': True, 'result': exists}

            case 'list_keys':
                # 列出所有键
                keys = list(data.keys())
                return {'success': True, 'result': keys}

            case 'get_all':
                # 获取全部数据
                return {'success': True, 'result': data}

            case 'clear':
                # 清空存储
                _save_storage(storage_name, {})
                return {'success': True, 'result': True}

            case _:
                return {'success': False, 'result': None, 'error': f'未知操作: {operation}'}

    def _parse_value(self, value: str) -> Any:
        """
        尝试解析值
        - 如果是有效的 JSON，解析为对应类型
        - 否则作为字符串保存
        """
        if not value:
            return ''
        
        # 尝试解析为 JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # 不是有效 JSON，作为字符串返回
            return value
