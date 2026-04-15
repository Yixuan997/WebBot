"""
全局网络代理配置工具
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

from Core.logging.file_logger import log_info, log_warn
from Models import GlobalVariable, db

PROXY_ENABLED_KEY = "network_proxy_enabled"
PROXY_URL_KEY = "network_proxy_url"
PROXY_NO_PROXY_KEY = "network_proxy_no_proxy"

PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)

NO_PROXY_ENV_KEYS = ("NO_PROXY", "no_proxy")


def _to_bool(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _upsert_global_var(key: str, value: str, description: str, is_secret: bool = False) -> None:
    item = GlobalVariable.get_by_key(key)
    if item:
        item.value = value
        item.description = description
        item.is_secret = is_secret
        return

    db.session.add(GlobalVariable(
        key=key,
        value=value,
        description=description,
        is_secret=is_secret,
    ))


def _mask_proxy_url(proxy_url: str) -> str:
    if not proxy_url:
        return ""
    try:
        parsed = urlsplit(proxy_url)
        if not parsed.password:
            return proxy_url

        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        username = parsed.username or ""
        auth = f"{username}:***@" if username else "***@"
        netloc = f"{auth}{host}{port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    except Exception:
        return proxy_url


def get_global_proxy_settings() -> dict:
    try:
        enabled_var = GlobalVariable.get_by_key(PROXY_ENABLED_KEY)
        url_var = GlobalVariable.get_by_key(PROXY_URL_KEY)
        no_proxy_var = GlobalVariable.get_by_key(PROXY_NO_PROXY_KEY)

        enabled = _to_bool(enabled_var.value if enabled_var else "0")
        proxy_url = (url_var.value if url_var else "").strip()
        no_proxy = (no_proxy_var.value if no_proxy_var else "").strip()

        return {
            "loaded": True,
            "enabled": enabled,
            "proxy_url": proxy_url,
            "no_proxy": no_proxy,
            "proxy_url_masked": _mask_proxy_url(proxy_url),
        }
    except Exception as error:
        log_warn(0, f"读取全局代理配置失败: {error}", "GLOBAL_PROXY_LOAD_FAILED", error=str(error))
        return {
            "loaded": False,
            "enabled": False,
            "proxy_url": "",
            "no_proxy": "",
            "proxy_url_masked": "",
        }


def save_global_proxy_settings(enabled: bool, proxy_url: str, no_proxy: str, commit: bool = True) -> None:
    _upsert_global_var(PROXY_ENABLED_KEY, "1" if enabled else "0", "全局网络代理开关")
    _upsert_global_var(PROXY_URL_KEY, (proxy_url or "").strip(), "全局网络代理地址", is_secret=True)
    _upsert_global_var(PROXY_NO_PROXY_KEY, (no_proxy or "").strip(), "全局代理直连地址（NO_PROXY）")
    if commit:
        db.session.commit()


def _set_proxy_env(proxy_url: str, no_proxy: str) -> None:
    for env_key in PROXY_ENV_KEYS:
        os.environ[env_key] = proxy_url

    if no_proxy:
        for env_key in NO_PROXY_ENV_KEYS:
            os.environ[env_key] = no_proxy
    else:
        for env_key in NO_PROXY_ENV_KEYS:
            os.environ.pop(env_key, None)


def _clear_proxy_env() -> None:
    for env_key in (*PROXY_ENV_KEYS, *NO_PROXY_ENV_KEYS):
        os.environ.pop(env_key, None)


def apply_global_proxy_settings() -> dict:
    settings = get_global_proxy_settings()
    if not settings.get("loaded"):
        return settings

    enabled = settings.get("enabled", False)
    proxy_url = (settings.get("proxy_url") or "").strip()
    no_proxy = (settings.get("no_proxy") or "").strip()

    if enabled and proxy_url:
        _set_proxy_env(proxy_url, no_proxy)
        log_info(
            0,
            "全局网络代理已启用",
            "GLOBAL_PROXY_APPLIED",
            proxy_url=settings.get("proxy_url_masked", ""),
            no_proxy=no_proxy or "",
        )
    else:
        _clear_proxy_env()
        log_info(0, "全局网络代理已关闭", "GLOBAL_PROXY_CLEARED")

    return settings

