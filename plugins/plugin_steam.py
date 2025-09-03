# -*- coding: utf-8 -*-
"""
Helldivers 2 Steam 更新日志插件
"""
import sys
import os

# 将项目根目录添加到路径中
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.plugin import Plugin, on_command
from utils.message_handler import MessageHandler
from core.steam import steam_service
from utils.logger import bot_logger


class SteamPlugin(Plugin):
    """Steam 更新日志插件"""
    
    def __init__(self):
        super().__init__()
        self.description = "查看 Helldivers 2 Steam 更新日志 - /steam"

    @on_command("steam", "查看 Steam 游戏更新日志")
    async def handle_steam(self, handler: MessageHandler, content: str):
        """
        处理 /steam 命令 - 获取最新的Steam更新日志
        
        Args:
            handler: 消息处理器
            content: 命令内容
        """
        bot_logger.info(f"用户 {handler.user_id} 请求Steam更新日志 (steam命令)")
        
        try:
            # 发送"正在查询"的提示消息
            await handler.send_text("\n🎮 正在获取最新Steam更新日志，请稍候...")
            
            # 获取最新的Steam更新数据
            latest_update = await steam_service.get_latest_steam_update()
            
            if latest_update:
                # 格式化并发送Steam更新数据
                formatted_message = await steam_service.format_steam_update_message(latest_update)
                await handler.send_text(formatted_message)
                
                bot_logger.info(f"成功为用户 {handler.user_id} 提供Steam更新日志")
            else:
                # 数据获取失败
                error_message = (
                    "\n❌ 抱歉，无法获取Steam更新日志。\n"
                    "可能的原因：\n"
                    "• API 服务暂时不可用\n"
                    "• 网络连接问题\n"
                    "• 服务器维护中\n\n"
                    "如频繁遇到此问题请与民主官联系！🌍"
                )
                await handler.send_text(error_message)
                bot_logger.warning(f"为用户 {handler.user_id} 获取Steam更新日志失败")
                
        except Exception as e:
            bot_logger.error(f"处理 /steam 命令时发生异常: {e}")
            await handler.send_text("\n⚠️ 处理请求时发生错误，请稍后重试。")
