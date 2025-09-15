#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
俄罗斯轮盘赌游戏核心逻辑
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Player:
    """玩家类"""
    name: str
    hp: int = 3
    max_hp: int = 3
    items: List[str] = field(default_factory=list)
    is_ai: bool = False

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, damage: int = 1) -> bool:
        """受到伤害，返回是否死亡"""
        self.hp = max(0, self.hp - damage)
        return not self.is_alive()

    def heal(self, amount: int = 1) -> int:
        """治疗，返回实际恢复的血量"""
        old_hp = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - old_hp


@dataclass
class GameState:
    """游戏状态类"""
    bullets: List[bool] = field(default_factory=list)  # True=实弹, False=空弹
    current_bullet: int = 0
    current_player: int = 0  # 0=玩家, 1=人机
    round_num: int = 1
    damage_multiplier: int = 1  # 伤害倍数（锯子效果）
    game_over: bool = False
    winner: Optional[str] = None

    def get_remaining_bullets(self) -> Tuple[int, int]:
        """获取剩余子弹数量 (实弹数, 空弹数)"""
        remaining = self.bullets[self.current_bullet:]
        real_bullets = sum(remaining)
        blank_bullets = len(remaining) - real_bullets
        return real_bullets, blank_bullets

    def is_current_bullet_real(self) -> bool:
        """当前子弹是否为实弹"""
        if self.current_bullet >= len(self.bullets):
            return False
        return self.bullets[self.current_bullet]

    def advance_bullet(self):
        """推进到下一发子弹"""
        self.current_bullet += 1


class RussianRouletteGame:
    """俄罗斯轮盘赌游戏类"""

    # 道具定义
    ITEMS = {
        "magnifier": {"name": "🔍放大镜", "desc": "查看下一发子弹"},
        "cigarette": {"name": "🚬香烟", "desc": "恢复1点生命"},
        "saw": {"name": "⚡锯子", "desc": "下次实弹伤害翻倍"},
        "handcuffs": {"name": "🔗手铐", "desc": "对手跳过下回合"},
        "beer": {"name": "🍺啤酒", "desc": "跳过当前子弹"},
        "medicine": {"name": "💊药品", "desc": "恢复2点生命"},
        "adrenaline": {"name": "💉肾上腺素", "desc": "偷取对手道具"},
        "inverter": {"name": "🔄逆转器", "desc": "反转枪口方向"}
    }

    def __init__(self, player_name: str, difficulty: str = "normal"):
        """初始化游戏"""
        self.player = Player(name=player_name, hp=3, max_hp=3)
        self.ai = Player(name="人机", hp=3, max_hp=3, is_ai=True)
        self.state = GameState()
        self.difficulty = difficulty
        self.skip_next_turn = False  # 手铐效果
        self.last_action = ""  # 记录最后操作

        # 根据难度设置
        if difficulty == "easy":
            self.bullet_count = 6
            self.item_count = 4
        elif difficulty == "hard":
            self.bullet_count = 8
            self.item_count = 3
        else:  # normal
            self.bullet_count = 6
            self.item_count = 3

        self._start_new_round()

    def _start_new_round(self):
        """开始新一轮"""
        # 生成子弹序列
        real_bullets = random.randint(1, self.bullet_count - 1)
        blank_bullets = self.bullet_count - real_bullets

        bullets = [True] * real_bullets + [False] * blank_bullets
        random.shuffle(bullets)

        self.state.bullets = bullets
        self.state.current_bullet = 0
        self.state.damage_multiplier = 1

        # 分配道具
        self._distribute_items()

    def _distribute_items(self):
        """分配道具给玩家"""
        available_items = list(self.ITEMS.keys())

        # 玩家道具
        player_items = random.sample(available_items, self.item_count)
        self.player.items = player_items

        # 人机道具
        ai_items = random.sample(available_items, self.item_count)
        self.ai.items = ai_items

    def get_current_player(self) -> Player:
        """获取当前玩家"""
        return self.player if self.state.current_player == 0 else self.ai

    def get_opponent(self) -> Player:
        """获取对手"""
        return self.ai if self.state.current_player == 0 else self.player

    def switch_turn(self):
        """切换回合"""
        self.state.current_player = 1 - self.state.current_player

    def shoot(self, target_self: bool = True) -> Dict:
        """开枪操作"""
        current_player = self.get_current_player()
        target_player = current_player if target_self else self.get_opponent()

        is_real = self.state.is_current_bullet_real()
        damage = self.state.damage_multiplier if is_real else 0

        result = {
            "shooter": current_player.name,
            "target": target_player.name,
            "is_real": is_real,
            "damage": damage,
            "target_died": False,
            "continue_turn": False
        }

        if is_real:
            # 实弹命中
            target_died = target_player.take_damage(damage)
            result["target_died"] = target_died

            if target_died:
                self.state.game_over = True
                self.state.winner = self.get_opponent().name if target_player == current_player else current_player.name
        else:
            # 空弹，如果打自己可以继续
            if target_self:
                result["continue_turn"] = True

        # 推进子弹
        self.state.advance_bullet()

        # 重置伤害倍数
        self.state.damage_multiplier = 1

        # 检查是否需要新一轮
        if self.state.current_bullet >= len(self.state.bullets) and not self.state.game_over:
            self.state.round_num += 1
            self._start_new_round()

        return result

    def use_item(self, item_index: int) -> Dict:
        """使用道具"""
        current_player = self.get_current_player()

        if item_index < 0 or item_index >= len(current_player.items):
            return {"success": False, "message": "道具不存在"}

        item_key = current_player.items[item_index]
        item_info = self.ITEMS[item_key]

        result = {"success": True, "item": item_info["name"], "effect": ""}

        # 执行道具效果
        if item_key == "magnifier":
            if self.state.current_bullet < len(self.state.bullets):
                bullet_type = "实弹" if self.state.is_current_bullet_real() else "空弹"
                result["effect"] = f"下一发是: {bullet_type}"
            else:
                result["effect"] = "没有子弹了"

        elif item_key == "cigarette":
            healed = current_player.heal(1)
            result["effect"] = f"恢复了{healed}点生命"

        elif item_key == "saw":
            self.state.damage_multiplier = 2
            result["effect"] = "下次实弹伤害翻倍"

        elif item_key == "beer":
            if self.state.current_bullet < len(self.state.bullets):
                bullet_type = "实弹" if self.state.is_current_bullet_real() else "空弹"
                self.state.advance_bullet()
                result["effect"] = f"跳过了一发{bullet_type}"
            else:
                result["effect"] = "没有子弹可跳过"

        elif item_key == "medicine":
            healed = current_player.heal(2)
            result["effect"] = f"恢复了{healed}点生命"

        elif item_key == "handcuffs":
            self.skip_next_turn = True
            result["effect"] = "对手将跳过下回合"

        # 移除使用的道具
        current_player.items.pop(item_index)

        return result
