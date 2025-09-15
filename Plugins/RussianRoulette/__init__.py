#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
俄罗斯轮盘赌游戏插件
"""

from typing import Dict, Optional

from Core.logging.file_logger import log_error
from Core.message.builder import MessageBuilder
from Core.plugin.base import BasePlugin
from .ai import RouletteAI
from .display import GameDisplay
from .game import RussianRouletteGame


class Plugin(BasePlugin):
    """俄罗斯轮盘赌插件"""

    def __init__(self):
        super().__init__()

        # 插件信息
        self.name = "RussianRoulette"
        self.version = "1.0.0"
        self.description = "经典的俄罗斯轮盘赌游戏，带有道具系统和人机对战"
        self.author = "Yixuan"

        # 注册命令信息
        self.register_command_info('轮盘', '俄罗斯轮盘赌游戏', '轮盘 [操作]')

        # 命令处理器
        self.command_handlers = {
            "轮盘": self.handle_roulette_command
        }

        # 注册Hook事件处理器
        self.hooks = {
            'message_received': [self.handle_message_hook]
        }

        # 游戏实例存储
        self.games = {}  # 内存中的游戏实例 {bot_id:user_id: game}

    def handle_message_hook(self, message_data, user_id, bot_id):
        """处理消息Hook"""
        content = message_data.get('content', '').strip()

        # 检查是否是轮盘命令
        if content.startswith('轮盘'):
            result = self.handle_roulette_command(bot_id, message_data)
            if result is not None:  # 明确检查不是None
                # 如果result已经是Hook格式，直接返回
                if isinstance(result, dict) and 'handled' in result:
                    return result
                # 否则包装成Hook格式
                return {
                    'handled': True,
                    'response': result
                }

        return {'handled': False}

    def get_game_key(self, bot_id: str, user_id: str) -> str:
        """获取游戏键"""
        return f"{bot_id}:{user_id}"

    def save_game(self, bot_id: str, user_id: str, game: RussianRouletteGame):
        """保存游戏状态到内存"""
        game_key = self.get_game_key(bot_id, user_id)
        self.games[game_key] = game

    def load_game(self, bot_id: str, user_id: str) -> Optional[RussianRouletteGame]:
        """从内存加载游戏状态"""
        game_key = self.get_game_key(bot_id, user_id)
        return self.games.get(game_key)

    def delete_game(self, bot_id: str, user_id: str):
        """删除游戏状态"""
        game_key = self.get_game_key(bot_id, user_id)
        if game_key in self.games:
            del self.games[game_key]

    def handle_roulette_command(self, bot_id: str, message: Dict) -> Optional[Dict]:
        """处理轮盘指令"""
        try:
            content = message.get("content", "").strip()
            user_id = message.get("author", {}).get("id", "")
            user_name = message.get("author", {}).get("username", "玩家")

            # 解析指令
            parts = content.split()

            if len(parts) == 1:
                # 只有 "轮盘" - 开始新游戏
                return self._start_new_game(bot_id, user_id, user_name)

            command = parts[1].lower()

            # 帮助命令应该在任何情况下都能回复，所以放在最前面
            if command in ["帮助", "规则", "help"]:
                return MessageBuilder.text(GameDisplay.format_help())

            # 加载现有游戏
            game = self.load_game(bot_id, user_id)

            if not game:
                return MessageBuilder.text("❌ 没有进行中的游戏\n💡 输入 '轮盘' 开始新游戏")

            if game.state.game_over:
                return MessageBuilder.text("❌ 游戏已结束\n💡 输入 '轮盘' 开始新游戏")

            # 处理特定命令，如果是人机回合且不是查看状态，则自动执行人机操作
            if game.state.current_player != 0 and command not in ["状态", "查看", "info", "帮助", "规则", "help"]:
                # 执行人机操作（不需要额外的"人机正在思考"消息）
                ai_results = self._execute_ai_turn(bot_id, user_id, game)

                # 直接返回人机操作结果
                if isinstance(ai_results, list):
                    return {
                        'handled': True,
                        'response': ai_results
                    }
                else:
                    return {
                        'handled': True,
                        'response': ai_results
                    }

            # 处理玩家指令
            if command in ["开枪", "射击", "fire"]:
                return self._handle_shoot(bot_id, user_id, game, target_self=True)

            elif command in ["开枪对手", "射击对手", "攻击"]:
                return self._handle_shoot(bot_id, user_id, game, target_self=False)

            elif command.isdigit():
                item_index = int(command) - 1
                return self._handle_use_item(bot_id, user_id, game, item_index)

            elif command in ["状态", "查看", "info"]:
                status_text = GameDisplay.format_game_state(game)
                if game.state.current_player != 0:  # 人机回合
                    status_text += "\n\n💡 提示：现在是人机回合，人机会自动操作\n🎮 你可以等待人机完成操作，或输入其他命令"
                return MessageBuilder.text(status_text)

            elif command in ["投降", "退出", "quit"]:
                self.delete_game(bot_id, user_id)
                return MessageBuilder.text("🏳️ 你选择了投降，游戏结束")

            else:
                return MessageBuilder.text("❌ 未知指令\n💡 输入 '轮盘 帮助' 查看指令列表")

        except Exception as e:
            log_error(bot_id, f"处理轮盘指令失败: {e}", "ROULETTE_COMMAND_ERROR")
            return MessageBuilder.text("❌ 游戏出现错误，请重新开始")

    def _start_new_game(self, bot_id: str, user_id: str, user_name: str) -> Dict:
        """开始新游戏"""
        try:
            # 删除旧游戏
            self.delete_game(bot_id, user_id)

            # 创建新游戏
            game = RussianRouletteGame(user_name, difficulty="normal")

            # 保存游戏状态
            self.save_game(bot_id, user_id, game)

            return MessageBuilder.text(GameDisplay.format_start_game(game))

        except Exception as e:
            log_error(bot_id, f"开始新游戏失败: {e}", "ROULETTE_START_ERROR")
            return MessageBuilder.text("❌ 创建游戏失败，请稍后重试")

    def _handle_shoot(self, bot_id: str, user_id: str, game: RussianRouletteGame, target_self: bool) -> Dict:
        """处理开枪操作"""
        try:
            # 执行开枪
            result = game.shoot(target_self)

            # 格式化结果
            response = GameDisplay.format_shoot_result(result)

            # 检查游戏是否结束
            if game.state.game_over:
                response += "\n\n" + GameDisplay.format_game_over(game)
                self.delete_game(bot_id, user_id)
                return MessageBuilder.text(response)
            else:
                # 保存游戏状态
                self.save_game(bot_id, user_id, game)

                # 如果不是继续回合，切换到人机
                if not result.get("continue_turn", False):
                    game.switch_turn()
                    self.save_game(bot_id, user_id, game)

                    # 检查是否轮到人机，如果是则返回多条消息
                    if game.state.current_player == 1:  # 人机回合
                        # 第一条消息：开枪结果 + 游戏状态（已经包含"人机正在思考"）
                        first_response = response + "\n\n" + GameDisplay.format_game_state(game)

                        # 人机操作结果
                        ai_results = self._execute_ai_turn(bot_id, user_id, game)

                        # 构建完整的消息列表（不包含重复的"人机正在思考"）
                        all_messages = [MessageBuilder.text(first_response)]

                        if isinstance(ai_results, list):
                            all_messages.extend(ai_results)
                        else:
                            all_messages.append(ai_results)

                        # 返回所有消息
                        return {
                            'handled': True,
                            'response': all_messages
                        }
                    else:
                        # 还是玩家回合，正常返回
                        response += "\n\n" + GameDisplay.format_game_state(game)
                        return MessageBuilder.text(response)
                else:
                    # 继续回合，正常返回
                    response += "\n\n" + GameDisplay.format_game_state(game)
                    return MessageBuilder.text(response)

        except Exception as e:
            log_error(bot_id, f"处理开枪操作失败: {e}", "ROULETTE_SHOOT_ERROR")
            return MessageBuilder.text("❌ 开枪操作失败")

    def _handle_use_item(self, bot_id: str, user_id: str, game: RussianRouletteGame, item_index: int) -> Dict:
        """处理使用道具"""
        try:
            # 使用道具
            result = game.use_item(item_index)

            # 格式化结果
            response = GameDisplay.format_item_result(result)

            if result["success"]:
                # 保存游戏状态
                self.save_game(bot_id, user_id, game)
                response += "\n\n" + GameDisplay.format_game_state(game)

            return MessageBuilder.text(response)

        except Exception as e:
            log_error(bot_id, f"处理道具使用失败: {e}", "ROULETTE_ITEM_ERROR")
            return MessageBuilder.text("❌ 道具使用失败")

    def _execute_ai_turn(self, bot_id: str, user_id: str, game: RussianRouletteGame,
                         collect_messages: list = None) -> Dict:
        """执行人机回合操作"""
        try:
            # 如果是收集消息模式，初始化消息列表
            if collect_messages is None:
                collect_messages = []
                is_root_call = True
            else:
                is_root_call = False

            # 检查手铐效果
            if game.skip_next_turn:
                game.skip_next_turn = False
                game.switch_turn()
                self.save_game(bot_id, user_id, game)

                response = "🔗 人机被手铐束缚，跳过了回合！\n\n"
                response += GameDisplay.format_game_state(game)

                if is_root_call:
                    return MessageBuilder.text(response)
                else:
                    collect_messages.append(MessageBuilder.text(response))
                    return None

            # 创建人机实例
            ai = RouletteAI(game)

            # 人机做决策
            action = ai.make_decision()

            # 直接显示人机的行动，不再显示"人机正在思考"
            response = ai.get_action_description(action) + "\n\n"

            # 执行人机行动
            if action["action"] == "use_item":
                result = game.use_item(action["item_index"])
                response += GameDisplay.format_item_result(result)

                # 通知人机道具使用事件
                ai.process_game_event("item_used", {
                    "user": "人机",
                    "item": result.get("item", ""),
                    "effect": result.get("effect", "")
                })

                # 添加当前操作到消息列表（包含游戏状态）
                collect_messages.append(MessageBuilder.text(response + "\n" + GameDisplay.format_game_state(game)))

                # 人机使用道具后，如果还是人机回合，继续执行下一次人机操作
                if game.state.current_player == 1:  # 还是人机回合
                    # 保存当前状态
                    self.save_game(bot_id, user_id, game)

                    # 递归执行人机的下一次操作
                    self._execute_ai_turn(bot_id, user_id, game, collect_messages)

                    # 递归调用后直接返回，避免重复处理
                    if is_root_call:
                        return collect_messages
                    else:
                        return None
                else:
                    # 人机回合结束，不需要递归
                    game.switch_turn()

            elif action["action"] == "shoot":
                result = game.shoot(action["target_self"])
                response += GameDisplay.format_shoot_result(result)

                # 通知人机子弹推进事件
                ai.process_game_event("bullet_advanced", {})

                # 如果人机可以继续回合，递归执行下一次人机操作
                if result.get("continue_turn", False):
                    # 添加当前操作到消息列表（人机还可以继续，显示当前状态）
                    collect_messages.append(MessageBuilder.text(response + "\n" + GameDisplay.format_game_state(game)))

                    # 保存当前状态
                    self.save_game(bot_id, user_id, game)

                    # 递归执行人机的下一次操作
                    self._execute_ai_turn(bot_id, user_id, game, collect_messages)

                    # 递归调用后直接返回，避免重复处理
                    if is_root_call:
                        return collect_messages
                    else:
                        return None
                else:
                    # 人机回合结束，先切换到玩家，再添加消息（显示正确的回合状态）
                    game.switch_turn()
                    collect_messages.append(MessageBuilder.text(response + "\n" + GameDisplay.format_game_state(game)))

            # 检查游戏是否结束
            if game.state.game_over:
                response += "\n\n" + GameDisplay.format_game_over(game)
                self.delete_game(bot_id, user_id)
                # 游戏结束时添加最终消息
                collect_messages.append(MessageBuilder.text(response))
            else:
                # 保存游戏状态
                self.save_game(bot_id, user_id, game)
                # 游戏未结束时，最后一条消息已经包含了游戏状态，不需要重复添加

            # 如果是根调用，返回所有消息
            if is_root_call:
                return collect_messages
            else:
                return None

        except Exception as e:
            log_error(bot_id, f"处理人机回合失败: {e}", "ROULETTE_AI_ERROR")
            return MessageBuilder.text("❌ 人机操作失败")
