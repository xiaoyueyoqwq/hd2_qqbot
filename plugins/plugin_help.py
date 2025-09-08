# -*- coding: utf-8 -*-
import sys
import os

# 确保正确的路径设置
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)

# 添加项目根目录到路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.plugin import Plugin, on_command
from utils.message_handler import MessageHandler
from utils.logger import bot_logger

class HelpPlugin(Plugin):
    """帮助插件"""
    
    def __init__(self):
        super().__init__()
        
    @on_command("help", "显示可用命令列表")
    async def handle_help(self, handler: MessageHandler, content: str):
        """
        处理 /help 命令，显示所有可用命令
        
        Args:
            handler: 消息处理器
            content: 命令内容
        """
        bot_logger.info(f"用户 {handler.user_id} 请求帮助信息")
        
        help_message = (
            "\n🤖 Helldivers机器人帮助\n"
            "-------------\n"
            "▎可用命令:\n"
            "▎/stats - 查看银河战争统计数据\n"
            "▎/order - 查看当前最高命令\n"
            "▎/news [1-5] - 查看游戏快讯\n"
            "▎/help - 显示此帮助信息\n"
            "▎/steam - 查看最新更新日志\n"
            "-------------\n"
            "▎联系方式:\n"
            "▎民主官邮箱: xiaoyueyoqwq@vaiiya,org\n"
            "-------------\n"
            "如遇问题请随时与民主官联系！🌍"
        )
        await handler.send_text(help_message)
        bot_logger.info(f"成功为用户 {handler.user_id} 提供帮助信息")
