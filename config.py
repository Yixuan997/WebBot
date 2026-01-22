"""
@Project ：WebBot
@File    ：config.py
@IDE     ：PyCharm
@Author  ：杨逸轩
@Date    ：2023-8-19 13:41
"""
import os
from datetime import timedelta

import redis
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class BaseConfig:
    """基础配置类"""

    # 基础配置
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'  # 默认关闭调试模式
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_secret_key_for_development_only')  # 确保开发环境有默认值

    # 密钥轮换列表 - Flask 3.1新增
    # 允许更改SECRET_KEY而不使现有会话失效
    SECRET_KEY_FALLBACKS = None  # 禁用密钥轮换，简化配置

    # JSON配置
    # 这些在Flask 2.3+中通过app.json对象设置，见init_json_config函数
    JSON_CONFIG = {
        'sort_keys': False,  # 禁止对JSON键进行排序
        'ensure_ascii': False,  # 允许非ASCII字符
        'compact': False,  # 紧凑输出
    }

    # 时间配置（秒）
    SESSION_LIFETIME = int(os.getenv('PERMANENT_SESSION_LIFETIME', 7200))  # 已登录用户会话过期时间：2小时
    GUEST_SESSION_LIFETIME = int(os.getenv('GUEST_SESSION_LIFETIME', 900))  # 未登录用户会话过期时间：15分钟
    CAPTCHA_LIFETIME = int(os.getenv('CAPTCHA_LIFETIME', 300))  # 验证码过期时间：5分钟
    CACHE_LIFETIME = int(os.getenv('CACHE_LIFETIME', 3600))  # 缓存过期时间：1小时

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 数据库连接池
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.getenv('DB_POOL_SIZE', 20)),  # 连接池大小
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', 10)),  # 等待超时
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', 1800)),  # 3更频繁回收连接
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 10)),  # 溢出连接
        'pool_pre_ping': True,
        'pool_reset_on_return': 'commit',  # 优化连接重置策略
        'echo': False,  # 关闭SQL日志以提升性能
    }

    # Redis配置
    REDIS_URL = os.getenv('REDIS_URL')

    # Redis连接池配置
    REDIS_POOL_CONFIG = {
        'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', 50)),
        'socket_timeout': int(os.getenv('REDIS_SOCKET_TIMEOUT', 3)),
        'socket_connect_timeout': int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', 3)),
        'socket_keepalive': True,
        'health_check_interval': int(os.getenv('REDIS_HEALTH_CHECK_INTERVAL', 180)),
        'retry_on_timeout': True,
        'retry_on_error': [ConnectionError, TimeoutError],
    }

    # Redis客户端配置
    REDIS_CLIENT_CONFIG = {
        'retry_threshold': int(os.getenv('REDIS_RETRY_THRESHOLD', 2)),  # 重试次数
        'pool_preconnect': int(os.getenv('REDIS_POOL_PRECONNECT', 5)),  # 预连接
        'client_timeout': float(os.getenv('REDIS_CLIENT_TIMEOUT', 0.5)),  # 超时时间
        'pool_usage_warning': int(os.getenv('REDIS_POOL_USAGE_WARNING', 75)),
        'server_max_clients': int(os.getenv('REDIS_SERVER_MAX_CLIENTS', 10000)),
        'decode_responses': False,
        'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', 50)),  # 增加最大连接数
        'socket_timeout': float(os.getenv('REDIS_SOCKET_TIMEOUT', 5.0)),  # 增加socket超时
        'socket_connect_timeout': float(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', 5.0)),
        'socket_keepalive': False,  # 暂时禁用socket保活
        'health_check_interval': int(os.getenv('REDIS_HEALTH_CHECK_INTERVAL', 30)),
    }

    # 数据库文件路径配置
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'Bot.Y')

    # 默认管理员配置
    DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD')
    DEFAULT_ADMIN_EMAIL = os.getenv('DEFAULT_ADMIN_EMAIL')
    DEFAULT_ADMIN_QQ = os.getenv('DEFAULT_ADMIN_QQ')

    @classmethod
    def get_database_path(cls, app_instance_path: str = None) -> str:
        """
        获取数据库文件的完整路径

        参数:
            app_instance_path: Flask应用的instance_path，如果为None则使用当前工作目录

        返回:
            str: 数据库文件的完整路径
        """
        if cls.SQLALCHEMY_DATABASE_URI and cls.SQLALCHEMY_DATABASE_URI.startswith('sqlite:///'):
            # 从URI中提取数据库文件名
            db_filename = cls.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
            if app_instance_path:
                return os.path.join(app_instance_path, db_filename)
            else:
                return db_filename
        return None

    @classmethod
    def ensure_database_exists(cls, app) -> bool:
        """
        检查数据库表是否存在
        SQLAlchemy初始化时会自动创建空文件，所以需要检查表是否存在

        参数:
            app: Flask应用实例

        返回:
            bool: 数据库表是否存在
        """
        try:
            from sqlalchemy import inspect
            from Models import db

            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            # 检查关键表是否存在
            required_tables = ['user', 'system']
            return all(table in tables for table in required_tables)
        except Exception:
            return False

    @classmethod
    def ensure_default_admin_exists(cls) -> bool:
        """
        确保默认管理员账号存在

        返回:
            bool: 是否创建了新的管理员账号
        """
        try:
            from Models import db, User
            from werkzeug.security import generate_password_hash

            # 检查是否已存在管理员用户
            admin_user = User.query.filter_by(username=cls.DEFAULT_ADMIN_USERNAME).first()
            if admin_user:
                return False

            # 创建新的管理员用户
            admin_user = User(
                username=cls.DEFAULT_ADMIN_USERNAME,
                password=generate_password_hash(cls.DEFAULT_ADMIN_PASSWORD),
                email=cls.DEFAULT_ADMIN_EMAIL,
                qq=cls.DEFAULT_ADMIN_QQ,
                role='admin',
                vip=True  # 管理员默认为VIP
            )

            db.session.add(admin_user)
            db.session.commit()

            print(f"✓ 默认管理员账号创建成功:")
            print(f"  用户名: {cls.DEFAULT_ADMIN_USERNAME}")
            print(f"  密码: {cls.DEFAULT_ADMIN_PASSWORD}")
            print(f"  邮箱: {cls.DEFAULT_ADMIN_EMAIL}")
            print(f"  角色: admin")

            return True

        except Exception as e:
            print(f"❌ 创建默认管理员时出错: {e}")
            try:
                from Models import db
                db.session.rollback()
            except:
                pass
            return False

    @classmethod
    def ensure_default_system_exists(cls) -> bool:
        """
        确保默认系统配置存在

        返回:
            bool: 是否创建了新的系统配置
        """
        try:
            from Models import db, System

            # 检查是否已存在系统配置
            system = System.query.first()
            if system:
                return False

            # 创建默认系统配置
            system = System(
                title='QQ机器人管理系统',
                des='智能、便捷、高效的QQ机器人管理平台',
                key='QQ机器人,管理系统,自动化,智能助手',
                email='admin@qqbot.local',
                icp='备案号待填写',
                cop='© 2024 QQ机器人管理系统. All rights reserved.'
            )

            db.session.add(system)
            db.session.commit()

            print("✓ 默认系统配置创建成功")
            return True

        except Exception as e:
            print(f"❌ 创建默认系统配置时出错: {e}")
            try:
                from Models import db
                db.session.rollback()
            except:
                pass
            return False

    # Session基础配置
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)  # 延长会话寿命到1天，避免过早过期
    SESSION_KEY_PREFIX = 'bot:session:'
    SESSION_COOKIE_NAME = 'bot_session'  # 使用更简单的名称
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # 开发环境必须关闭
    SESSION_COOKIE_PATH = '/'
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_PARTITIONED = False
    SESSION_USE_SIGNER = False  # 禁用签名，简化会话机制
    SESSION_REFRESH_EACH_REQUEST = True

    # Redis会话配置
    if REDIS_URL:
        SESSION_REDIS = redis.Redis.from_url(
            REDIS_URL,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=300
        )
    else:
        SESSION_REDIS = redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD'),
            db=int(os.getenv('REDIS_DB', 0)),
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=300
        )

    # 会话更新频率
    SESSION_REDIS_RETRY_NUMBER = 3

    # Flask 3.0新增 - 控制是否自动为路由添加OPTIONS方法处理
    PROVIDE_AUTOMATIC_OPTIONS = True

    # 安全配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    CORS_ALLOW_CREDENTIALS = True
    CORS_SUPPORTS_CREDENTIALS = True

    def init_app(self, app):
        """
        初始化Flask应用的额外配置
        用于设置Flask 2.3+中需要通过app对象设置的配置项
        """
        # 设置JSON配置
        app.json.sort_keys = self.JSON_CONFIG.get('sort_keys', False)
        app.json.ensure_ascii = self.JSON_CONFIG.get('ensure_ascii', False)
        app.json.compact = self.JSON_CONFIG.get('compact', False)

        # 设置会话文件存储目录到实例目录
        if self.SESSION_TYPE == 'filesystem' and not self.SESSION_FILE_DIR:
            session_dir = os.path.join(app.instance_path, 'sessions')
            os.makedirs(session_dir, exist_ok=True)
            app.config['SESSION_FILE_DIR'] = session_dir

        # 可以在这里添加其他需要通过app对象设置的配置


class DevelopmentConfig(BaseConfig):
    """开发环境配置"""
    DEBUG = True
    # 开发环境使用简单且稳定的会话配置
    SECRET_KEY = "dev_secret_key_for_development_only"  # 固定密钥，避免重启后变化
    SESSION_COOKIE_SECURE = False
    SESSION_USE_SIGNER = False  # 开发环境禁用签名
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # 开发环境使用更长的会话


class ProductionConfig(BaseConfig):
    """生产环境配置"""
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY')
    SESSION_COOKIE_SECURE = False  # TODO: 配置HTTPS后改为True
    SESSION_USE_SIGNER = True  # 生产环境启用签名
    SESSION_COOKIE_PARTITIONED = False  # 需要HTTPS才能启用

    # 生产环境JSON配置
    JSON_CONFIG = {
        'sort_keys': False,
        'ensure_ascii': False,
        'compact': True,  # 生产环境使用紧凑输出以减少传输大小
    }

    def __init__(self):
        if not self.SECRET_KEY:
            raise ValueError('生产环境必须设置 SECRET_KEY')


# 根据环境变量选择配置
env = os.getenv('FLASK_ENV', 'development')
if env == 'production':
    config_class = ProductionConfig
elif env == 'development':
    config_class = DevelopmentConfig
else:
    config_class = BaseConfig

config = config_class()
