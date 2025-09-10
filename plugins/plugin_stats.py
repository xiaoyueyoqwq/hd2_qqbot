# -*- coding: utf-8 -*-
"""
Helldivers 2 战争统计插件
"""
import sys
import os

# 将 qqbot_sdk 添加到路径中
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'qqbot_sdk'))

from core.plugin import Plugin, on_command
from utils.message_handler import MessageHandler
from core.stats import stats_service
from utils.logger import bot_logger

class StatsPlugin(Plugin):
    """战争统计插件"""
    
    def __init__(self):
        super().__init__()
        self.description = "查看 Helldivers 2 银河战争统计数据"
        
    @on_command("stats", "查看当前银河战争统计数据")
    async def handle_stats(self, handler: MessageHandler, content: str):
        """
        处理 /stats 命令
        
        Args:
            handler: 消息处理器
            content: 命令内容
        """
        bot_logger.info(f"用户 {handler.user_id} 请求战争统计数据")
        
        try:
            # 获取统计数据
            stats_data = await stats_service.get_war_summary()
            
            if stats_data:
                # 格式化并发送统计数据
                formatted_message = await stats_service.format_stats_message(stats_data)
                await handler.send_text(formatted_message)
                bot_logger.info(f"成功为用户 {handler.user_id} 提供战争统计数据")
            else:
                # 数据获取失败
                error_message = (
                    "\n❌ 抱歉，无法获取当前战争统计数据。\n"
                    "可能的原因：\n"
                    "• API 服务暂时不可用\n"
                    "• 网络连接问题\n"
                    "• 服务器维护中\n\n"
                    "如频繁遇到此问题请与民主官联系！🌍"
                )
                await handler.send_text(error_message)
                bot_logger.warning(f"为用户 {handler.user_id} 获取战争统计数据失败")
                
        except Exception as e:
            bot_logger.error(f"处理 /stats 命令时发生异常: {e}")
            await handler.send_text("\n⚠️ 处理请求时发生错误，请稍后重试。")


