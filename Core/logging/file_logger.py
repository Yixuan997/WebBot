"""
简洁高效的文件日志系统
每个机器人独立目录，按日期分文件
"""

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from queue import Queue

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def get_beijing_time() -> datetime:
    """获取北京时间"""
    return datetime.now(BEIJING_TZ)


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class BotFileLogger:
    """机器人文件日志系统"""

    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        self.log_queue = Queue(maxsize=1000)
        self.running = False
        self.worker_thread = None
        self.lock = threading.Lock()

        # 批量写入
        self.batch_size = 100  # 增加批量大小
        self.batch_timeout = 0.5  # 减少超时
        self.file_handles = {}  # 文件句柄缓存

        # 性能优化
        self.format_cache = {}  # 格式化缓存
        self.path_cache = {}  # 路径缓存

        # 创建日志根目录
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(os.path.join(log_dir, "system"), exist_ok=True)

        # 启动后台写入线程
        self.start_worker()

    def start_worker(self):
        """启动后台日志写入线程"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._process_logs, daemon=False)
            self.worker_thread.start()

    def stop_worker(self):
        """停止后台线程"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=3)

    def log(self, bot_id: int, level: LogLevel, message: str,
            event_type: str = "", **metadata):
        """记录日志"""
        # 检查后台线程状态
        if not self.running or not self.worker_thread or not self.worker_thread.is_alive():
            self.start_worker()

        timestamp = get_beijing_time()
        log_entry = {
            'bot_id': bot_id,
            'timestamp': timestamp,
            'level': level.value,
            'event_type': event_type,
            'message': message,
            'metadata': metadata
        }

        try:
            self.log_queue.put_nowait(log_entry)
        except Exception:
            # 队列满时，直接写入（阻塞模式）
            self._write_log_entry(log_entry)

    def _process_logs(self):
        """后台处理日志队列"""
        batch = []
        last_flush_time = time.time()

        while self.running:
            try:
                # 尝试获取日志条目
                try:
                    log_entry = self.log_queue.get(timeout=0.1)
                    batch.append(log_entry)
                except Exception:
                    pass

                current_time = time.time()

                # 批量写入条件：达到批量大小或超时
                if (len(batch) >= self.batch_size or
                        (batch and current_time - last_flush_time >= self.batch_timeout)):
                    self._write_batch(batch)
                    batch.clear()
                    last_flush_time = current_time

            except Exception as e:
                # 出错时也要写入当前批次
                if batch:
                    self._write_batch(batch)
                    batch.clear()
                continue

        # 退出时写入剩余日志
        if batch:
            self._write_batch(batch)

    def _write_batch(self, batch):
        """批量写入日志条目 - 高性能优化"""
        if not batch:
            return

        # 按文件分组
        file_groups = {}
        for log_entry in batch:
            file_path = self._build_log_file_path(log_entry['bot_id'], log_entry['timestamp'])
            if file_path not in file_groups:
                file_groups[file_path] = []
            file_groups[file_path].append(log_entry)

        # 批量写入每个文件
        for file_path, entries in file_groups.items():
            self._write_entries_to_file(file_path, entries)

    def _build_log_file_path(self, bot_id, timestamp):
        """构建日志文件路径"""
        if bot_id == 0:  # 系统日志
            log_dir = os.path.join(self.log_dir, "system")
            filename = f"{timestamp.strftime('%Y-%m-%d')}.log"
        else:  # 机器人日志
            log_dir = os.path.join(self.log_dir, f"bot_{bot_id}")
            filename = f"{timestamp.strftime('%Y-%m-%d')}.log"

        return os.path.join(log_dir, filename)

    def _write_entries_to_file(self, file_path, entries):
        """批量写入条目到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 批量格式化
            lines = []
            for entry in entries:
                line = self._format_log_line(entry)
                lines.append(line)

            # 一次性写入
            with open(file_path, 'a', encoding='utf-8') as f:
                f.writelines(lines)
                f.flush()  # 确保写入磁盘

        except Exception as e:
            # 写入失败时回退到单条写入
            for entry in entries:
                self._write_log_entry(entry)

    def _format_log_line(self, log_entry: dict):
        """格式化日志行"""
        timestamp_str = log_entry['timestamp'].strftime("%H:%M:%S")
        level = log_entry['level']
        event_type = log_entry['event_type']
        message = log_entry['message']

        # 构建基础日志行
        if event_type:
            log_line = f"[{timestamp_str}] [{level}] [{event_type}] {message}"
        else:
            log_line = f"[{timestamp_str}] [{level}] {message}"

        # 添加元数据
        if log_entry['metadata']:
            metadata_parts = []
            for key, value in log_entry['metadata'].items():
                if key != 'traceback':  # traceback单独处理
                    metadata_parts.append(f"{key}={value}")

            if metadata_parts:
                log_line += f" | {', '.join(metadata_parts)}"

        log_line += "\n"

        # 处理traceback
        if 'traceback' in log_entry['metadata']:
            log_line += f"{log_entry['metadata']['traceback']}\n"

        return log_line

    def _write_log_entry(self, log_entry):
        """写入单条日志"""
        try:
            bot_id = log_entry['bot_id']
            timestamp = log_entry['timestamp']

            # 确定日志文件路径
            if bot_id == 0:  # 系统日志
                log_dir = os.path.join(self.log_dir, "system")
                filename = f"{timestamp.strftime('%Y-%m-%d')}.log"
            else:  # 机器人日志
                log_dir = os.path.join(self.log_dir, f"bot_{bot_id}")
                filename = f"{timestamp.strftime('%Y-%m-%d')}.log"

            # 创建目录
            os.makedirs(log_dir, exist_ok=True)

            # 格式化日志内容
            log_line = self._format_log_line(log_entry)

            # 写入文件
            log_file = os.path.join(log_dir, filename)
            with self.lock:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(log_line)

        except Exception as e:
            pass  # 静默处理日志写入失败

    def get_bot_logs(self, bot_id: int, date: str = None, limit: int = 100) -> list[str]:
        """获取机器人日志"""
        if date is None:
            date = get_beijing_time().strftime('%Y-%m-%d')

        if bot_id == 0:
            log_file = os.path.join(self.log_dir, "system", f"{date}.log")
        else:
            log_file = os.path.join(self.log_dir, f"bot_{bot_id}", f"{date}.log")

        if not os.path.exists(log_file):
            return []

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 返回最后N行（最新的日志）
            return [line.strip() for line in lines[-limit:]]

        except Exception as e:
            return []

    def get_recent_logs(self, bot_id: int, days: int = 3, limit: int = 200) -> list[dict]:
        """获取最近几天的日志"""
        logs = []

        for i in range(days):
            date = (get_beijing_time() - timedelta(days=i)).strftime('%Y-%m-%d')
            day_logs = self.get_bot_logs(bot_id, date, limit // days)

            for line in day_logs:
                # 解析日志行
                log_dict = self._parse_log_line(line, date)
                if log_dict:
                    logs.append(log_dict)

        # 按时间倒序
        logs.sort(key=lambda x: x['datetime'], reverse=True)
        return logs[:limit]

    def _parse_log_line(self, line: str, date: str) -> dict | None:
        """解析日志行"""
        try:
            # 格式：HH:MM:SS.mmm [LEVEL] EVENT_TYPE - MESSAGE | metadata
            parts = line.split(' - ', 1)
            if len(parts) < 2:
                return None

            header = parts[0]
            content_and_meta = parts[1]

            # 解析头部：时间 [级别] 事件类型
            header_parts = header.split('] ', 1)
            if len(header_parts) < 2:
                return None

            time_and_level = header_parts[0]
            event_type = header_parts[1].strip()

            # 解析时间和级别
            time_part = time_and_level.split(' [')[0]
            level_part = time_and_level.split(' [')[1] if ' [' in time_and_level else 'INFO'

            # 解析消息和元数据
            if ' | ' in content_and_meta:
                message, metadata_str = content_and_meta.split(' | ', 1)
            else:
                message = content_and_meta
                metadata_str = ""

            return {
                'time': time_part,
                'datetime': f"{date} {time_part}",
                'level': level_part.strip(),
                'event_type': event_type,
                'message': message.strip(),
                'metadata': metadata_str
            }

        except Exception:
            return None

    def list_bot_log_files(self, bot_id: int) -> list[str]:
        """列出机器人的所有日志文件"""
        if bot_id == 0:
            log_dir = os.path.join(self.log_dir, "system")
        else:
            log_dir = os.path.join(self.log_dir, f"bot_{bot_id}")

        if not os.path.exists(log_dir):
            return []

        files = []
        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                file_path = os.path.join(log_dir, filename)
                file_size = os.path.getsize(file_path)
                files.append({
                    'filename': filename,
                    'date': filename.replace('.log', ''),
                    'size': file_size,
                    'size_mb': round(file_size / 1024 / 1024, 2)
                })

        # 按日期倒序
        files.sort(key=lambda x: x['date'], reverse=True)
        return files

    def cleanup_old_logs(self, days_to_keep: int = 30):
        """清理旧日志"""
        cutoff_date = get_beijing_time() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        cleaned_count = 0

        try:
            # 遍历所有机器人目录
            for item in os.listdir(self.log_dir):
                item_path = os.path.join(self.log_dir, item)
                if os.path.isdir(item_path):
                    # 清理目录中的旧日志文件
                    for filename in os.listdir(item_path):
                        if filename.endswith('.log'):
                            file_date = filename.replace('.log', '')
                            if file_date < cutoff_str:
                                file_path = os.path.join(item_path, filename)
                                os.remove(file_path)
                                cleaned_count += 1


        except Exception as e:
            pass  # 静默处理日志清理失败

    def get_log_stats(self) -> dict:
        """获取日志统计信息"""
        stats = {
            'total_bots': 0,
            'total_files': 0,
            'total_size_mb': 0,
            'bots': {}
        }

        try:
            for item in os.listdir(self.log_dir):
                item_path = os.path.join(self.log_dir, item)
                if os.path.isdir(item_path) and (item.startswith('bot_') or item == 'system'):
                    bot_files = self.list_bot_log_files(
                        0 if item == 'system' else int(item.replace('bot_', ''))
                    )

                    bot_size = sum(f['size'] for f in bot_files)
                    stats['bots'][item] = {
                        'files': len(bot_files),
                        'size_mb': round(bot_size / 1024 / 1024, 2)
                    }

                    stats['total_bots'] += 1
                    stats['total_files'] += len(bot_files)
                    stats['total_size_mb'] += stats['bots'][item]['size_mb']

            stats['total_size_mb'] = round(stats['total_size_mb'], 2)

        except Exception as e:
            pass  # 静默处理日志统计失败

        return stats


# 全局日志实例
_file_logger = None


def get_file_logger() -> BotFileLogger:
    """获取全局文件日志实例"""
    global _file_logger
    if _file_logger is None:
        _file_logger = BotFileLogger()
    return _file_logger


# 便捷函数
def log_info(bot_id: int, message: str, event_type: str = "INFO", **metadata):
    """记录信息日志"""
    logger = get_file_logger()
    logger.log(bot_id, LogLevel.INFO, message, event_type, **metadata)


def log_error(bot_id: int, message: str, event_type: str = "ERROR", **metadata):
    """记录错误日志"""
    logger = get_file_logger()
    logger.log(bot_id, LogLevel.ERROR, message, event_type, **metadata)


def log_warn(bot_id: int, message: str, event_type: str = "WARN", **metadata):
    """记录警告日志"""
    logger = get_file_logger()
    logger.log(bot_id, LogLevel.WARN, message, event_type, **metadata)


def log_debug(bot_id: int, message: str, event_type: str = "DEBUG", **metadata):
    """记录调试日志"""
    logger = get_file_logger()
    logger.log(bot_id, LogLevel.DEBUG, message, event_type, **metadata)
