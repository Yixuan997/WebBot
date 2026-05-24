"""
Redis Key 统一构造模块

职责：
1. 统一命名空间前缀（避免多项目/多环境冲突）
2. 统一 key 结构（避免散落字符串拼接）
"""

import os


def _get_namespace_prefix() -> str:
    """
    获取 Redis key 命名空间前缀

    优先级：
    1. REDIS_KEY_PREFIX 环境变量（显式配置）
    2. 默认值 webbot:{FLASK_ENV}
    """
    explicit = (os.getenv("REDIS_KEY_PREFIX") or "").strip()
    if explicit:
        return explicit.rstrip(":")

    env = (os.getenv("FLASK_ENV") or "development").strip() or "development"
    return f"webbot:{env}"


def namespaced_key(*parts) -> str:
    """构造带命名空间前缀的 Redis key"""
    safe_parts = [str(p).strip(":") for p in parts if p is not None and str(p) != ""]
    if not safe_parts:
        return _get_namespace_prefix()
    return f"{_get_namespace_prefix()}:{':'.join(safe_parts)}"


def namespaced_prefix(*parts) -> str:
    """构造带命名空间前缀的 key 前缀（结尾带冒号）"""
    return f"{namespaced_key(*parts)}:"


def captcha_key(captcha_id: str) -> str:
    return namespaced_key("captcha", captcha_id)


def email_verification_key(purpose: str, email: str) -> str:
    return namespaced_key("email_verification", purpose, email)


def qq_event_dedup_key(date_str: str, event_id: str) -> str:
    return namespaced_key("qq_event_dedup", date_str, event_id)


def qq_message_raw_key(bot_id: int, message_id: str) -> str:
    return namespaced_key("qq_message_raw", bot_id, message_id)


def workflow_debug_key(workflow_id: int) -> str:
    return namespaced_key("workflow_debug", workflow_id)


def workflow_globals_key() -> str:
    return namespaced_key("workflow", "globals")


def bot_mapping_key(protocol: str, cache_key: str) -> str:
    return namespaced_key("bot", "mapping", protocol, cache_key)


def bot_status_key(bot_id: int) -> str:
    return namespaced_key("bot", "status", bot_id)


def bot_config_key(bot_id: int) -> str:
    return namespaced_key("bot", "config", bot_id)
