# -*- coding: utf-8 -*-
"""
Helldivers 2 快讯插件
"""
import sys
import os
import asyncio

# 将项目根目录添加到路径中
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.plugin import Plugin, on_command
from utils.message_handler import MessageHandler
from core.news import dispatch_service
from utils.logger import bot_logger


class NewsPlugin(Plugin):
    """快讯插件"""
    
    def __init__(self):
        super().__init__()
        self.description = "查看 Helldivers 2 游戏内快讯 - /news [编号1-5]"
        

    @on_command("news", "查看指定编号的游戏快讯 - 用法: /news [编号1-5]")
    async def handle_news(self, handler: MessageHandler, content: str):
        """
        处理 /news 命令 - 获取指定编号的快讯
        支持参数 1-5 查看对应的快讯
        无参数时默认显示第一条最新快讯
        
        Args:
            handler: 消息处理器
            content: 命令内容
        """
        bot_logger.info(f"用户 {handler.user_id} 请求快讯数据 (news命令)")
        
        try:
            # 解析命令参数
            parts = content.strip().split()
            target_index = 1  # 默认显示第1条最新快讯
            
            if len(parts) > 1:
                try:
                    user_index = int(parts[1])
                    # 限制查询编号在1-5范围内
                    if 1 <= user_index <= 5:
                        target_index = user_index
                    else:
                        await handler.send_text("\n⚠️ 参数范围错误，请输入1-5之间的数字。\n用法: /news [1-5]")
                        return
                except ValueError:
                    await handler.send_text("\n⚠️ 参数格式错误，请输入数字。\n用法: /news [1-5]")
                    return
            
            # 获取最新的5条快讯数据
            dispatches = await dispatch_service.get_dispatches(limit=5)
            
            if dispatches and len(dispatches) >= target_index:
                # 提取指定编号的快讯
                target_dispatch = [dispatches[target_index - 1]]
                
                # 格式化并发送快讯数据
                formatted_messages = await dispatch_service.format_dispatch_messages(target_dispatch)
                
                # 发送格式化后的消息
                await handler.send_text(formatted_messages[0])
                
                bot_logger.info(f"成功为用户 {handler.user_id} 提供第 {target_index} 条快讯")
            else:
                # 数据获取失败或索引超出范围
                error_message = (
                    f"\n❌ 抱歉，无法获取第 {target_index} 条快讯。\n"
                    "可能的原因：\n"
                    "• API 服务暂时不可用\n"
                    "• 当前快讯总数不足\n\n"
                    "如频繁遇到此问题请与民主官联系！🌍"
                )
                await handler.send_text(error_message)
                bot_logger.warning(f"为用户 {handler.user_id} 获取第 {target_index} 条快讯失败")
                
        except Exception as e:
            bot_logger.error(f"处理 /news 命令时发生异常: {e}")
            await handler.send_text("\n⚠️ 处理请求时发生错误，请稍后重试。")
