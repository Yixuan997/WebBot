"""
@Project :WebBot 
@File    :install.py
@IDE     :VScode 
@Author  :杨逸轩
@Date    :2025-12-10 13:06
"""

import importlib.util
import os
import sys
from pathlib import Path

from flask import current_app, render_template, request, redirect

from http_json import success_api, fail_api, table_api

# 常量定义
PACKAGE_NAME_MAP = {
    "opencv_python": "cv2",
    "pillow": "PIL",
    "pyjwt": "jwt",
    "python_dotenv": "dotenv",
    "python_whois": "whois",
    "beautifulsoup4": "bs4",
    "fake_useragent": "fake_useragent",
    "pycryptodome": "Crypto",
    "pynacl": "nacl",
    "websocket_client": "websocket"
}

DEFAULT_SYSTEM_CONFIG = {
    "title": "WebBot",
    "des": "智能、便捷、高效的QQ机器人管理平台，提供完整的机器人生命周期管理解决方案",
    "key": "QQ机器人,机器人管理,智能客服,自动化,聊天机器人",
    "email": "93653142@qq.com",
    "icp": "备案号",
    "cop": "© 2026 WebBot. All rights reserved."
}

DEFAULT_ADMIN_CONFIG = {
    "username": "admin",
    "password": "scrypt:32768:8:1$20trG8SdwyMZgJW8$4f4011e9d7f83fe1c975cd1e8162ded2f9cd76cc5c52999d89cfa9f6b07a56a352e514a766edf6a36d1d596297518c364822d7fe06a171875f87ebb7da51f5af",
    "qq": "93653142",
    "email": "93653142@qq.com",
    "role": "admin"
}


def get_sqlite_db_path() -> str:
    """
    根据 SQLALCHEMY_DATABASE_URI 推导出 SQLite 实际文件路径
    例如: sqlite:///instance/api.Y  ->  <instance_path>/api.Y
    """
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    prefix = "sqlite:///"
    if uri.startswith(prefix):
        relative_path = uri[len(prefix):]
        if relative_path.startswith("instance/"):
            filename = relative_path.split("instance/", 1)[1]
            return os.path.join(current_app.instance_path, filename)
        return os.path.abspath(relative_path)
    return ""


def is_installed() -> bool:
    """
    通过判断数据库表是否存在来判断是否已经安装
    SQLAlchemy 初始化时会自动创建空文件，所以需要检查表是否存在
    """
    from config import config
    return config.ensure_database_exists(current_app)


def install_index():
    """
    安装首页 - 多步骤向导
    """
    # 如果已安装，重定向到首页
    if is_installed():
        return redirect("/")

    return render_template("install.html")


def check_env():
    """
    第一步：环境检查
    检查 Python 版本和 requirements.txt 中的依赖
    """
    result = {
        "success": True,
        "python_version": sys.version,
        "python_ok": sys.version_info >= (3, 8),
        "packages": [],
        "missing_packages": [],
        "db_path": get_sqlite_db_path()
    }

    # 读取 requirements.txt
    req_file = Path(current_app.root_path) / "requirements.txt"

    if not req_file.exists():
        result["success"] = False
        result["error"] = f"未找到 requirements.txt 文件: {req_file}"
        return table_api(msg="环境检查失败", **result)

    # 检查每个包是否已安装
    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 提取包名（去掉版本号等）
            import re
            package = re.split(r'[=<>~!\[\]]', line)[0].strip()

            # 某些包导入名和安装名不一致，需要映射
            import_name = package.lower().replace("-", "_")
            import_name = PACKAGE_NAME_MAP.get(import_name, import_name)

            # 检查是否已安装
            installed = importlib.util.find_spec(import_name) is not None
            result["packages"].append({"name": package, "installed": installed})

            if not installed:
                result["missing_packages"].append(package)
                result["success"] = False

    return table_api(msg="环境检查完成", **result)


def test_redis():
    """测试 Redis 连接"""
    data = request.get_json()

    try:
        from redis import Redis

        redis_client = Redis(
            host=data.get("host", "localhost"),
            port=int(data.get("port", 6379)),
            password=data.get("password") or None,
            db=int(data.get("db", 0)),
            socket_connect_timeout=5,
            decode_responses=True
        )
        redis_client.ping()
        redis_client.close()

        return success_api("Redis 连接成功")
    except Exception as e:
        return fail_api(f"Redis 连接失败: {str(e)}")


def save_config():
    """
    第二步：保存数据库配置到 .env 文件
    """
    data = request.get_json()

    # 构建新的配置项
    new_config = {}

    # Redis 配置
    redis_host = data.get("redis_host")
    redis_port = data.get("redis_port")
    redis_password = data.get("redis_password")
    redis_db = data.get("redis_db")

    if redis_host and redis_port:
        if redis_password:
            new_config["REDIS_URL"] = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            new_config["REDIS_URL"] = f"redis://{redis_host}:{redis_port}/{redis_db}"

    # 写入 .env 文件
    try:
        env_file = Path(current_app.root_path) / ".env"

        # 读取现有内容
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        # 更新配置项
        updated_keys = set()
        new_lines = []

        for line in lines:
            stripped = line.strip()

            # 保留空行和注释
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            # 解析 key=value
            if "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in new_config:
                    # 替换为新值
                    new_lines.append(f"{key}={new_config[key]}\r\n")
                    updated_keys.add(key)
                else:
                    # 保留原有配置
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # 添加未更新的新配置项
        for key, value in new_config.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\r\n")

        # 写回文件
        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        return success_api("配置已保存到 .env 文件")
    except Exception as e:
        return fail_api(f"保存配置失败: {str(e)}")


def run_install():
    """第三步：执行数据库初始化"""
    try:
        from Models import db, System, User

        # 创建空的数据库文件
        db_path = get_sqlite_db_path()
        if not db_path:
            return fail_api("无法获取数据库路径")

        # 确保父目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(db_path).touch(exist_ok=True)

        # 创建数据库表
        db.create_all()

        # 插入默认数据
        # 创建系统配置
        if not System.query.first():
            db.session.add(System(**DEFAULT_SYSTEM_CONFIG))

        # 创建管理员用户
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(**DEFAULT_ADMIN_CONFIG))

        db.session.commit()

        return success_api("数据库初始化完成！")
    except Exception as e:
        import traceback
        return fail_api(f"初始化失败: {str(e)}\n{traceback.format_exc()}")
