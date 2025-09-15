#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
俄罗斯轮盘赌游戏显示模块
"""

from typing import Dict

try:
    from .game import RussianRouletteGame, Player
except ImportError:
    from game import RussianRouletteGame, Player


class GameDisplay:
    """游戏显示类"""

    @staticmethod
    def format_hp(hp: int, max_hp: int) -> str:
        """格式化生命值显示"""
        hearts = "❤️" * hp + "⚫" * (max_hp - hp)
        return f"{hearts} ({hp}/{max_hp}血)"

    @staticmethod
    def format_bullets(game: RussianRouletteGame) -> str:
        """格式化子弹显示"""
        bullets_display = "[?]" * (len(game.state.bullets) - game.state.current_bullet)
        real_count, blank_count = game.state.get_remaining_bullets()

        return f"🔫 {bullets_display} | 实弹×{real_count} 空弹×{blank_count}"

    @staticmethod
    def format_items(player: Player) -> str:
        """格式化道具显示"""
        if not player.items:
            return "🎒 道具: 无"

        items_display = []
        for i, item_key in enumerate(player.items):
            item_info = RussianRouletteGame.ITEMS[item_key]
            items_display.append(f"{i + 1}️⃣{item_info['name']}")

        return f"🎒 道具: {' '.join(items_display)}"

    @staticmethod
    def format_game_state(game: RussianRouletteGame) -> str:
        """格式化完整游戏状态"""
        current_player = game.get_current_player()

        # 标题
        title = f"🎰 俄罗斯轮盘赌 - 第{game.state.round_num}轮"

        # 玩家状态
        player_hp = GameDisplay.format_hp(game.player.hp, game.player.max_hp)
        ai_hp = GameDisplay.format_hp(game.ai.hp, game.ai.max_hp)
        players = f"👤 {game.player.name}: {player_hp}  🤖 {game.ai.name}: {ai_hp}"

        # 子弹状态
        bullets = GameDisplay.format_bullets(game)

        # 当前玩家道具
        items = GameDisplay.format_items(current_player)

        # 回合提示
        turn_indicator = f"💭 轮到{'你' if current_player == game.player else '人机'}了！"

        # 操作提示
        if current_player == game.player:
            commands = "🔫 轮盘 开枪 | 🔫 轮盘 开枪对手 | 🎒 轮盘 1~3 | 📖 轮盘 状态"
        else:
            commands = "💭 轮到人机了！"

        # 特殊效果提示
        effects = []
        if game.state.damage_multiplier > 1:
            effects.append("⚡ 锯子效果激活 - 下次实弹伤害翻倍")
        if game.skip_next_turn:
            effects.append("🔗 手铐效果 - 对手将跳过回合")

        effect_text = "\n".join(effects)

        # 组装完整显示
        parts = [title, "", players, "", bullets, "", items, "", turn_indicator, commands]

        if effect_text:
            parts.insert(-2, effect_text)
            parts.insert(-2, "")

        return "\n".join(parts)

    @staticmethod
    def format_shoot_result(result: Dict) -> str:
        """格式化开枪结果"""
        shooter = result["shooter"]
        target = result["target"]
        is_real = result["is_real"]
        damage = result["damage"]
        target_died = result["target_died"]
        continue_turn = result["continue_turn"]

        # 基础结果
        bullet_type = "💥实弹" if is_real else "💨空弹"
        action = f"🔫 {shooter} 开枪 → {target}"

        if is_real:
            if target_died:
                return f"{action}\n{bullet_type}！💀 {target} 被击中身亡！"
            else:
                return f"{action}\n{bullet_type}！💔 {target} 受到{damage}点伤害！"
        else:
            if continue_turn:
                return f"{action}\n{bullet_type}！😅 虚惊一场，{shooter} 可以继续操作！"
            else:
                return f"{action}\n{bullet_type}！😮‍💨 没有命中，回合结束！"

    @staticmethod
    def format_item_result(result: Dict) -> str:
        """格式化道具使用结果"""
        if not result["success"]:
            return f"❌ {result['message']}"

        item_name = result["item"]
        effect = result["effect"]

        return f"✨ 使用了 {item_name}\n💫 效果: {effect}"

    @staticmethod
    def format_game_over(game: RussianRouletteGame) -> str:
        """格式化游戏结束"""
        winner = game.state.winner

        if winner == game.player.name:
            return f"🎉 恭喜！你击败了人机获得胜利！\n\n💀 最终状态:\n👤 {game.player.name}: {GameDisplay.format_hp(game.player.hp, game.player.max_hp)}\n🤖 {game.ai.name}: {GameDisplay.format_hp(game.ai.hp, game.ai.max_hp)}"
        else:
            return f"💀 很遗憾，你被人机击败了！\n\n💀 最终状态:\n👤 {game.player.name}: {GameDisplay.format_hp(game.player.hp, game.player.max_hp)}\n🤖 {game.ai.name}: {GameDisplay.format_hp(game.ai.hp, game.ai.max_hp)}"

    @staticmethod
    def format_help() -> str:
        """格式化帮助信息"""
        return """🎯 经典轮盘游戏 - 游戏规则

🎮 基础玩法:
• 转轮装有不同类型的弹药
• 玩家和人机轮流进行操作
• 可以选择对自己或对手使用
• 有效弹药命中扣除生命，空弹无效果
• 对自己使用空弹可继续操作
• 生命值归零即失败

🎒 道具系统:
🔍 放大镜 - 查看下一发弹药类型
🚬 香烟 - 恢复1点生命值
⚡ 锯子 - 下次有效弹药伤害翻倍
🔗 手铐 - 让对手跳过下回合
🍺 啤酒 - 跳过当前弹药
💊 药品 - 恢复2点生命值

📝 操作指令:
• 轮盘 - 开始新游戏
• 轮盘 开火 - 对自己使用
• 轮盘 攻击 - 对人机使用
• 轮盘 1/2/3 - 使用对应道具
• 轮盘 状态 - 查看游戏状态
• 轮盘 投降 - 结束游戏

🎯 获胜条件: 战胜对手获得胜利"""

    @staticmethod
    def format_start_game(game: RussianRouletteGame) -> str:
        """格式化游戏开始"""
        return f"""🎰 俄罗斯轮盘赌游戏开始！

🎯 难度: {game.difficulty}
🔫 子弹数: {game.bullet_count}发
🎒 道具数: {game.item_count}个

{GameDisplay.format_game_state(game)}

💡 输入 "轮盘 帮助" 查看详细规则"""
