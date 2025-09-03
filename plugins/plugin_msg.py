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
from core.msg import dispatch_service
from utils.logger import bot_logger


class MsgPlugin(Plugin):
    """快讯插件"""
    
    def __init__(self):
        super().__init__()
        self.description = "查看 Helldivers 2 游戏内快讯 - /news [1-5]"
        

    @on_command("news", "查看游戏快讯 - 用法: /news [1-5]")
    async def handle_news(self, handler: MessageHandler, content: str):
        """
        处理 /news 命令 - 优化的快讯查看
        支持参数 1-5 查看对应数量的快讯
        无参数时默认显示第一条最新快讯
        
        Args:
            handler: 消息处理器
            content: 命令内容
        """
        bot_logger.info(f"用户 {handler.user_id} 请求快讯数据 (news命令)")
        
        try:
            # 发送"正在查询"的提示消息
            await handler.send_text("\n📰 正在获取最新快讯，请稍候...")
            
            # 解析命令参数
            parts = content.strip().split()
            limit = 1  # 默认显示1条最新快讯
            
            if len(parts) > 1:
                try:
                    user_limit = int(parts[1])
                    # 限制查询数量在1-5范围内
                    if 1 <= user_limit <= 5:
                        limit = user_limit
                    else:
                        await handler.send_text("\n⚠️ 参数范围错误，请输入1-5之间的数字。\n用法: /news [1-5]")
                        return
                except ValueError:
                    await handler.send_text("\n⚠️ 参数格式错误，请输入数字。\n用法: /news [1-5]")
                    return
            
            # 获取快讯数据
            dispatches = await dispatch_service.get_dispatches(limit=limit)
            
            if dispatches:
                # 格式化并发送快讯数据
                formatted_messages = await dispatch_service.format_dispatch_messages(dispatches)
                
                # 发送所有格式化后的消息
                for formatted_message in formatted_messages:
                    await handler.send_text(formatted_message)
                    # 稍微延迟避免消息发送过快
                    if len(formatted_messages) > 1:
                        await asyncio.sleep(0.5)
                
                # 根据数量显示不同的结果信息
                if limit == 1:
                    bot_logger.info(f"成功为用户 {handler.user_id} 提供最新快讯")
                else:
                    bot_logger.info(f"成功为用户 {handler.user_id} 提供 {len(dispatches)} 条快讯")
            else:
                # 数据获取失败
                error_message = (
                    "\n❌ 抱歉，无法获取快讯数据。\n"
                    "可能的原因：\n"
                    "• API 服务暂时不可用\n"
                    "• 网络连接问题\n"
                    "• 服务器维护中\n\n"
                    "请稍后重试，为了超级地球！🌍"
                )
                await handler.send_text(error_message)
                bot_logger.warning(f"为用户 {handler.user_id} 获取快讯数据失败")
                
        except Exception as e:
            bot_logger.error(f"处理 /news 命令时发生异常: {e}")
            await handler.send_text("\n⚠️ 处理请求时发生错误，请稍后重试。")
