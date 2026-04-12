"""
协议服务

统一提供协议元数据、配置解析和展示能力，避免业务层硬编码协议分支。
"""

from Adapters import get_adapter_manager


def list_protocols() -> list[dict]:
    """返回所有已注册协议的元数据列表"""
    manager = get_adapter_manager()
    metas = manager.get_protocol_meta()
    protocols = [metas[k] for k in sorted(metas.keys())]
    return protocols


def get_default_protocol_id() -> str:
    """获取默认协议标识（按已注册协议排序后的第一个）"""
    protocols = list_protocols()
    if not protocols:
        return ""
    return protocols[0]["id"]


def get_protocol_meta(protocol: str) -> dict:
    """返回指定协议元数据"""
    manager = get_adapter_manager()
    return manager.get_protocol_meta(protocol) or {}


def get_protocol_adapter_class(protocol: str):
    """返回协议适配器类"""
    manager = get_adapter_manager()
    return manager.get_adapter_class(protocol)


def parse_protocol_config_from_form(protocol: str, form, existing_config: dict | None = None) -> dict:
    """按协议定义解析表单配置"""
    adapter_class = get_protocol_adapter_class(protocol)
    if not adapter_class:
        raise ValueError(f"不支持的协议类型: {protocol}")
    return adapter_class.parse_bot_config_from_form(form, existing_config or {})


def validate_protocol_config(protocol: str, config: dict) -> tuple[bool, str]:
    """按协议定义验证配置"""
    adapter_class = get_protocol_adapter_class(protocol)
    if not adapter_class:
        return False, f"不支持的协议类型: {protocol}"
    return adapter_class.validate_bot_config(config)


def get_protocol_name(protocol: str) -> str:
    """协议显示名"""
    meta = get_protocol_meta(protocol)
    return meta.get("name") or protocol


def get_protocol_label_map() -> dict[str, str]:
    """协议标识 -> 显示名"""
    return {item["id"]: item["name"] for item in list_protocols()}


def summarize_protocol_config(protocol: str, config: dict) -> str:
    """协议配置摘要"""
    adapter_class = get_protocol_adapter_class(protocol)
    if not adapter_class:
        return "unknown protocol"
    return adapter_class.get_config_summary(config or {})


def validate_protocol_config_uniqueness(
        protocol: str,
        config: dict,
        exclude_bot_id: int | None = None
) -> tuple[bool, str]:
    """
    校验协议配置中的唯一性字段

    Args:
        protocol: 协议标识
        config: 协议配置
        exclude_bot_id: 排除的机器人ID（编辑场景）
    """
    adapter_class = get_protocol_adapter_class(protocol)
    if not adapter_class:
        return False, f"不支持的协议类型: {protocol}"

    unique_fields = adapter_class.get_unique_config_fields()
    if not unique_fields:
        return True, ""

    from Models import Bot

    protocol_bots = Bot.query.filter_by(protocol=protocol).all()
    for field_name in unique_fields:
        value = str(config.get(field_name) or "").strip()
        if not value:
            continue

        for bot in protocol_bots:
            if exclude_bot_id and bot.id == exclude_bot_id:
                continue

            existing_value = str(bot.get_config().get(field_name) or "").strip()
            if existing_value and existing_value == value:
                label = adapter_class.get_config_field_label(field_name)
                return False, f"{adapter_class.get_display_name()} 配置项「{label}」已被机器人 #{bot.id} 使用"

    return True, ""
