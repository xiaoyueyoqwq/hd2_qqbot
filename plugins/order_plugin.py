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
from core.order import order_service
from utils.logger import bot_logger

class OrderPlugin(Plugin):
    """最高命令插件"""
    
    def __init__(self):
        super().__init__()
        
    @on_command("order", "查看当前最高命令")
    async def handle_order(self, handler: MessageHandler, content: str):
        """
        处理 /order 命令
        
        Args:
            handler: 消息处理器
            content: 命令内容
        """
        bot_logger.info(f"用户 {handler.user_id} 请求最高命令数据")
        
        try:
            # 发送"正在查询"的提示消息
            await handler.send_text("\n🔍 正在查询最高命令，请稍候...")
            
            # 获取最高命令数据
            orders_data = await order_service.get_current_orders()
            
            if orders_data is not None:
                # 格式化并发送最高命令数据
                formatted_messages = await order_service.format_order_messages(orders_data)
                
                # 发送每条消息
                for message in formatted_messages:
                    await handler.send_text(message)
                
                bot_logger.info(f"成功为用户 {handler.user_id} 提供最高命令数据 (共{len(formatted_messages)}条)")
            else:
                # 数据获取失败
                error_message = (
                    "\n❌ 抱歉，无法获取当前最高命令。\n"
                    "可能的原因：\n"
                    "• API 服务暂时不可用\n"
                    "• 间歇性服务中断\n"
                    "• 机器人通讯干扰\n\n"
                    "如频繁出现问题请联系民主官处理！🌍"
                )
                await handler.send_text(error_message)
                bot_logger.warning(f"为用户 {handler.user_id} 获取最高命令数据失败")
                
        except Exception as e:
            bot_logger.error(f"处理 /order 命令时发生异常: {e}")
            await handler.send_text("\n⚠️ 处理请求时发生错误，请稍后重试。")
