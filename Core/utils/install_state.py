"""
安装状态管理（基于 instance/install.lock）
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import current_app


INSTALL_LOCK_FILENAME = "install.lock"


def _resolve_app(app=None):
    if app is not None:
        return app
    return current_app


def get_install_lock_path(app=None) -> Path:
    resolved_app = _resolve_app(app)
    return Path(resolved_app.instance_path) / INSTALL_LOCK_FILENAME


def has_install_lock(app=None) -> bool:
    try:
        return get_install_lock_path(app).exists()
    except Exception:
        return False


def write_install_lock(app=None) -> bool:
    try:
        lock_path = get_install_lock_path(app)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            f"installed=1\nupdated_at={datetime.now().isoformat(timespec='seconds')}\n",
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def remove_install_lock(app=None) -> bool:
    try:
        lock_path = get_install_lock_path(app)
        if lock_path.exists():
            lock_path.unlink()
        return True
    except Exception:
        return False
