"""
Redis 数据存储节点

提供 Redis 的通用增删查操作，支持：
- set: 设置键值（可选 TTL）
- get: 获取键值
- delete: 删除键
- exists: 判断键是否存在
"""

import json
from typing import Any

from Core.logging.file_logger import log_debug, log_error
from Database.Redis.client import delete_key, get_value, set_value
from Database.Redis.keys import namespaced_key

from .base import BaseNode


class RedisStorageNode(BaseNode):
    """Redis 数据存储节点"""

    name = "Redis 操作"
    description = "通过 Redis 执行增删查操作（支持 TTL）"
    category = "data"
    icon = "🧰"

    inputs = []
    outputs = [
        {"name": "result", "label": "result - 操作结果", "type": "any"},
        {"name": "success", "label": "success - 是否成功", "type": "boolean"},
    ]

    config_schema = [
        {
            "name": "operation",
            "label": "操作类型",
            "type": "select",
            "required": True,
            "default": "get",
            "options": [
                {"value": "get", "label": "查询 - 获取键值"},
                {"value": "set", "label": "新增/修改 - 设置键值"},
                {"value": "delete", "label": "删除 - 删除键"},
                {"value": "exists", "label": "判断 - 键是否存在"},
            ],
        },
        {
            "name": "namespace",
            "label": "业务命名空间",
            "type": "text",
            "required": False,
            "default": "workflow",
            "placeholder": "workflow",
            "help": "会自动拼接到 Redis key，例如 webbot:production:workflow:{key}",
        },
        {
            "name": "key",
            "label": "键名",
            "type": "text",
            "required": True,
            "placeholder": "支持变量：{{group_id}}:counter",
            "help": "原始键名，支持模板变量",
        },
        {
            "name": "value",
            "label": "值（set 时）",
            "type": "textarea",
            "required": False,
            "placeholder": "支持变量：{{message}} 或 JSON 字符串",
            "rows": 2,
        },
        {
            "name": "expire_seconds",
            "label": "TTL 秒数（set 时，可选）",
            "type": "text",
            "required": False,
            "default": "",
            "placeholder": "604800",
            "help": "为空表示不过期；支持模板变量",
        },
        {
            "name": "default_value",
            "label": "默认值（get 时）",
            "type": "text",
            "required": False,
            "default": "",
            "placeholder": "键不存在时返回该值",
        },
        {
            "name": "save_to",
            "label": "保存到变量",
            "type": "text",
            "required": False,
            "default": "result",
            "placeholder": "result",
            "help": "将结果保存到该变量",
        },
        {
            "name": "next_node",
            "label": "下一个节点",
            "type": "select",
            "required": False,
            "default": "",
            "options": [],
            "help": "执行完成后跳转到的节点",
        },
    ]

    async def _execute(self, context) -> dict[str, Any]:
        operation = str(self.config.get("operation", "get")).strip().lower()
        namespace_tpl = self.config.get("namespace", "workflow")
        key_tpl = self.config.get("key", "")
        value_tpl = self.config.get("value", "")
        expire_tpl = self.config.get("expire_seconds", "")
        default_tpl = self.config.get("default_value", "")
        save_to = self.config.get("save_to", "result")

        namespace = context.render_template(namespace_tpl).strip() if namespace_tpl else ""
        key = context.render_template(key_tpl).strip() if key_tpl else ""
        value_rendered = context.render_template(value_tpl) if value_tpl else ""
        default_value = context.render_template(default_tpl) if default_tpl else ""
        expire_rendered = context.render_template(expire_tpl).strip() if expire_tpl else ""

        if not key:
            return {"success": False, "result": None, "error": "键名不能为空"}

        redis_key = namespaced_key(namespace, key) if namespace else namespaced_key(key)

        try:
            result: Any = None

            if operation == "set":
                expire_seconds = self._parse_expire_seconds(expire_rendered)
                value_to_store = self._prepare_set_value(value_rendered)
                set_value(redis_key, value_to_store, expire_seconds=expire_seconds)
                result = value_to_store

            elif operation == "get":
                raw = get_value(redis_key)
                if raw is None:
                    result = default_value if default_value != "" else None
                else:
                    result = self._parse_get_value(raw)

            elif operation == "delete":
                existed = get_value(redis_key) is not None
                delete_key(redis_key)
                result = existed

            elif operation == "exists":
                result = get_value(redis_key) is not None

            else:
                return {"success": False, "result": None, "error": f"未知操作: {operation}"}

            if save_to:
                context.set_variable(save_to, result)

            log_debug(
                0,
                f"Redis节点: {operation}({redis_key})",
                "WORKFLOW_REDIS_NODE",
                operation=operation,
                key=redis_key,
            )

            return {"success": True, "result": result}

        except Exception as e:
            log_error(
                0,
                f"Redis节点执行失败: {e}",
                "WORKFLOW_REDIS_NODE_ERROR",
                operation=operation,
                key=redis_key,
            )
            return {"success": False, "result": None, "error": str(e)}

    @staticmethod
    def _parse_expire_seconds(expire_text: str) -> int | None:
        """解析 TTL 秒数，空值返回 None。"""
        if not expire_text:
            return None
        try:
            value = int(expire_text)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"TTL 秒数无效: {expire_text}") from exc
        if value <= 0:
            raise ValueError(f"TTL 秒数必须大于 0: {expire_text}")
        return value

    @staticmethod
    def _prepare_set_value(value: str) -> str:
        """
        统一 Redis 存储值为字符串。
        - 传入 JSON（对象/数组/数字/布尔/空）时，规范化为 JSON 字符串
        - 普通字符串保持原样
        """
        if value is None:
            return ""
        if value == "":
            return ""
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return str(value)
        return json.dumps(parsed, ensure_ascii=False)

    @staticmethod
    def _parse_get_value(raw: Any) -> Any:
        """读取时优先尝试 JSON 反序列化，失败则返回字符串。"""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        if not isinstance(raw, str):
            return raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
