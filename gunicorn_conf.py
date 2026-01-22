import os

# 项目目录（自动获取当前文件所在目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
chdir = BASE_DIR

# 指定进程数 - 机器人应用使用单worker保持状态一致性
# workers = multiprocessing.cpu_count() * 2 + 1  # 推荐公式：CPU核心数 * 2 + 1
workers = 1  # 单worker，避免多进程状态不一致问题

# 指定每个进程开启的线程数
threads = 1  # 使用多线程 + 全局单例模式，线程安全

# 启动用户
user = 'root'

# 启动模式 - 使用sync模式配合单worker多线程
worker_class = 'sync'

# 重要说明：
# QQ机器人应用需要维护全局状态（BotManager实例、运行状态等）
# 多worker会导致每个进程有独立的内存空间，造成状态不一致
# 现在使用全局单例 + 线程锁的方案，解决了多线程状态一致性问题
# 因此使用单worker + 多线程的方案，既保证状态一致性又提高并发性能

# 绑定的ip与端口
bind = '0.0.0.0:6666'

# 性能优化 - 提高重启阈值和预加载
max_requests = 2000  # 每个worker处理2000个请求后重启
max_requests_jitter = 200  # 随机化重启，避免所有worker同时重启
preload_app = False  # 禁用预加载，避免日志文件写入问题

# 超时设置
timeout = 60  # 请求超时时间（秒）
keepalive = 10  # HTTP连接保持时间（秒）
graceful_timeout = 30  # 优雅关闭超时时间

# 设置进程文件目录（用于停止服务和重启服务，请勿删除）
pidfile = os.path.join(BASE_DIR, 'gunicorn.pid')

# 设置访问日志和错误信息日志路径
# 设置访问日志和错误信息日志路径
accesslog = '/www/wwwlogs/python/Bot/gunicorn_acess.log'
errorlog = '/www/wwwlogs/python/Bot/gunicorn_error.log'

# 日志级别，这个日志级别指的是错误日志的级别，而访问日志的级别无法设置
# debug:调试级别，记录的信息最多；
# info:普通级别；
# warning:警告消息；
# error:错误消息；
# critical:严重错误消息；
loglevel = 'info'
