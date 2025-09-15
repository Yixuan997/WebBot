#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
俄罗斯轮盘赌人机逻辑
"""

import random
from typing import Dict

try:
    from .game import RussianRouletteGame
except ImportError:
    from game import RussianRouletteGame


class RouletteAI:
    """俄罗斯轮盘赌人机"""

    def __init__(self, game: RussianRouletteGame):
        self.game = game
        self.known_next_bullet = None  # 人机使用放大镜后记住的信息

    def make_decision(self) -> Dict:
        """人机做决策"""
        # 分析当前局势
        analysis = self._analyze_situation()

        # 决定是否使用道具
        item_action = self._consider_items(analysis)
        if item_action:
            return item_action

        # 决定开枪目标
        shoot_action = self._decide_shoot_target(analysis)
        return shoot_action

    def _analyze_situation(self) -> Dict:
        """分析当前局势"""
        real_bullets, blank_bullets = self.game.state.get_remaining_bullets()
        total_bullets = real_bullets + blank_bullets

        if total_bullets == 0:
            real_probability = 0
        else:
            real_probability = real_bullets / total_bullets

        # 人机血量状况
        ai_hp_ratio = self.game.ai.hp / self.game.ai.max_hp
        player_hp_ratio = self.game.player.hp / self.game.player.max_hp

        # 是否处于劣势
        is_disadvantaged = ai_hp_ratio < player_hp_ratio

        # 是否危险（血量低）
        is_critical = self.game.ai.hp <= 1

        return {
            "real_probability": real_probability,
            "blank_probability": 1 - real_probability,
            "total_bullets": total_bullets,
            "real_bullets": real_bullets,
            "blank_bullets": blank_bullets,
            "ai_hp_ratio": ai_hp_ratio,
            "player_hp_ratio": player_hp_ratio,
            "is_disadvantaged": is_disadvantaged,
            "is_critical": is_critical,
            "known_next": self.known_next_bullet
        }

    def _consider_items(self, analysis: Dict) -> Dict:
        """考虑是否使用道具"""
        ai = self.game.ai

        if not ai.items:
            return None

        # 按优先级检查道具
        for i, item_key in enumerate(ai.items):
            action = self._evaluate_item_usage(item_key, i, analysis)
            if action:
                return action

        return None

    def _evaluate_item_usage(self, item_key: str, item_index: int, analysis: Dict) -> Dict:
        """评估道具使用"""
        ai = self.game.ai

        # 放大镜 - 信息收集
        if item_key == "magnifier" and analysis["total_bullets"] > 0:
            # 如果不知道下一发子弹，优先使用
            if analysis["known_next"] is None:
                return {"action": "use_item", "item_index": item_index}

        # 香烟/药品 - 治疗
        if item_key in ["cigarette", "medicine"] and ai.hp < ai.max_hp:
            # 血量低时优先治疗
            if analysis["is_critical"]:
                return {"action": "use_item", "item_index": item_index}
            # 或者在安全时机治疗
            elif analysis["blank_probability"] > 0.6:
                return {"action": "use_item", "item_index": item_index}

        # 锯子 - 攻击增强
        if item_key == "saw" and self.game.state.damage_multiplier == 1:
            # 如果知道下一发是实弹，或实弹概率高
            if (analysis["known_next"] is True or
                    analysis["real_probability"] > 0.5):
                return {"action": "use_item", "item_index": item_index}

        # 啤酒 - 跳过子弹
        if item_key == "beer" and analysis["total_bullets"] > 0:
            # 如果知道下一发是实弹，跳过它
            if analysis["known_next"] is True:
                return {"action": "use_item", "item_index": item_index}
            # 或者实弹概率很高时
            elif analysis["real_probability"] > 0.7:
                return {"action": "use_item", "item_index": item_index}

        # 手铐 - 控制
        if item_key == "handcuffs":
            # 在劣势时使用，争取时间
            if analysis["is_disadvantaged"] or analysis["is_critical"]:
                return {"action": "use_item", "item_index": item_index}

        return None

    def _decide_shoot_target(self, analysis: Dict) -> Dict:
        """决定开枪目标"""
        # 如果知道下一发子弹类型
        if analysis["known_next"] is not None:
            if analysis["known_next"]:  # 实弹
                return {"action": "shoot", "target_self": False}  # 射击玩家
            else:  # 空弹
                return {"action": "shoot", "target_self": True}  # 射击自己继续

        # 基于概率决策
        real_prob = analysis["real_probability"]

        # 如果没有子弹了，随机选择
        if analysis["total_bullets"] == 0:
            return {"action": "shoot", "target_self": random.choice([True, False])}

        # 决策逻辑
        if real_prob > 0.6:
            # 实弹概率高，射击对手
            return {"action": "shoot", "target_self": False}
        elif real_prob < 0.4:
            # 空弹概率高，射击自己
            return {"action": "shoot", "target_self": True}
        else:
            # 概率接近，根据血量情况决定
            if analysis["is_critical"]:
                # 血量危险，保守射击对手
                return {"action": "shoot", "target_self": False}
            elif analysis["ai_hp_ratio"] > analysis["player_hp_ratio"]:
                # 血量优势，可以冒险射击自己
                return {"action": "shoot", "target_self": True}
            else:
                # 血量劣势，射击对手
                return {"action": "shoot", "target_self": False}

    def process_game_event(self, event_type: str, event_data: Dict):
        """处理游戏事件，更新人机状态"""
        if event_type == "item_used":
            # 如果人机使用了放大镜
            if (event_data.get("user") == "人机" and
                    "magnifier" in event_data.get("item", "")):
                # 从效果文本中提取信息
                effect = event_data.get("effect", "")
                if "实弹" in effect:
                    self.known_next_bullet = True
                elif "空弹" in effect:
                    self.known_next_bullet = False

        elif event_type == "bullet_advanced":
            # 子弹推进后，清除已知信息
            self.known_next_bullet = None

        elif event_type == "round_start":
            # 新一轮开始，重置人机状态
            self.known_next_bullet = None

    def get_action_description(self, action: Dict) -> str:
        """获取人机行动描述"""
        if action["action"] == "use_item":
            item_key = self.game.ai.items[action["item_index"]]
            item_name = self.game.ITEMS[item_key]["name"]
            return f"🤖 人机使用了 {item_name}"

        elif action["action"] == "shoot":
            if action["target_self"]:
                return "🤖 人机选择对自己开枪"
            else:
                return "🤖 人机选择对你开枪"

        return "🤖 人机正在思考..."
