"""
消息序号管理器

基于msg_id生成递增的msg_seq，确保同一消息的多次回复有唯一的序号。
符合QQ官方API要求：相同的 msg_id + msg_seq 组合不能重复发送。
"""

import threading
import time
from typing import Optional


class MsgSeqManager:
    """消息序号管理器 - 基于msg_id的递增计数器"""

    def __init__(self):
        self.msg_counters = {}  # {msg_id: counter}
        self.max_msg_ids = 100  # 只保留最近100个消息的计数器，防止内存泄漏
        self._lock = threading.Lock()  # 线程安全锁

    def get_msg_seq(self, msg_id: Optional[str] = None) -> int:
        """
        获取消息序号
        
        Args:
            msg_id: 原始消息ID，用于回复消息时关联
            
        Returns:
            int: 消息序号
            
        说明:
            - 如果有msg_id，返回该消息的递增序号（1, 2, 3...）
            - 如果没有msg_id，返回基于时间戳的随机序号
        """
        if not msg_id:
            # 没有msg_id时使用时间戳+随机数，确保唯一性
            import random
            timestamp_part = int(time.time() * 1000) % 1000  # 时间戳后3位
            random_part = random.randint(100, 999)  # 3位随机数
            return timestamp_part * 1000 + random_part

        with self._lock:
            if msg_id not in self.msg_counters:
                # 新消息，从1开始计数
                self.msg_counters[msg_id] = 1
                self._cleanup_old_counters()
            else:
                # 已存在的消息，递增计数
                self.msg_counters[msg_id] += 1

            return self.msg_counters[msg_id]

    def _cleanup_old_counters(self):
        """清理旧的计数器，防止内存泄漏"""
        if len(self.msg_counters) > self.max_msg_ids:
            # 删除最旧的计数器（FIFO）
            oldest_key = next(iter(self.msg_counters))
            del self.msg_counters[oldest_key]

    def get_counter_stats(self) -> dict:
        """获取计数器统计信息"""
        with self._lock:
            return {
                'total_msg_ids': len(self.msg_counters),
                'max_seq_value': max(self.msg_counters.values()) if self.msg_counters else 0,
                'memory_usage_kb': len(str(self.msg_counters)) / 1024
            }


# 全局单例实例
_msg_seq_manager = None
_manager_lock = threading.Lock()


def get_msg_seq_manager() -> MsgSeqManager:
    """获取全局msgseq管理器实例（单例模式）"""
    global _msg_seq_manager

    if _msg_seq_manager is None:
        with _manager_lock:
            if _msg_seq_manager is None:
                _msg_seq_manager = MsgSeqManager()

    return _msg_seq_manager


def get_msg_seq(msg_id: Optional[str] = None) -> int:
    """
    便捷函数：获取消息序号
    
    Args:
        msg_id: 原始消息ID
        
    Returns:
        int: 消息序号
    """
    return get_msg_seq_manager().get_msg_seq(msg_id)
