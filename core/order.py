# -*- coding: utf-8 -*-
"""
Helldivers 2 最高命令核心业务模块
"""
from typing import Dict, Any, Optional, List
import sys
import os
import aiohttp
import asyncio

# 确保正确的路径设置
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)

# 添加项目根目录到路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 从项目根目录导入
import importlib.util
hd2_api_spec = importlib.util.spec_from_file_location("hd2_api_manager", os.path.join(project_root, "utils", "hd2_api_manager.py"))
hd2_api_module = importlib.util.module_from_spec(hd2_api_spec)
hd2_api_spec.loader.exec_module(hd2_api_module)
hd2_api = hd2_api_module.hd2_api

from utils.logger import bot_logger
from utils.translation_cache import translation_cache
from utils.translation_retry_queue import translation_retry_queue
from core.news import TranslationService, clean_game_text
from datetime import datetime



class OrderService:
    """最高命令服务（基于智能缓存）"""
    
    def __init__(self):
        self.translation_service = TranslationService()
    
    async def get_current_orders(self) -> Optional[List[Dict[str, Any]]]:
        """
        从缓存获取当前最高命令
        
        Returns:
            包含最高命令数据的列表，失败时返回 None
        """
        try:
            from utils.hd2_cache import hd2_cache_service
            orders_data = await hd2_cache_service.get_major_orders()
            if orders_data:
                bot_logger.debug("从缓存获取最高命令数据成功")
                return orders_data
            else:
                bot_logger.warning("缓存中没有最高命令数据")
                return None
                
        except Exception as e:
            bot_logger.error(f"从缓存获取最高命令数据时发生错误: {e}")
            return None
    
    async def refresh_cache_if_needed(self) -> bool:
        """
        检查并刷新缓存（如果需要）
        由轮转系统调用此方法进行定期刷新
        
        Returns:
            True 如果缓存已刷新
        """
        try:
            # 获取最新的命令数据
            new_orders = await self.get_current_orders()
            if not new_orders:
                bot_logger.warning("无法获取新的最高命令数据，跳过缓存刷新")
                return False
            
            # 检查是否需要刷新
            needs_refresh = await translation_cache.check_content_freshness('orders', new_orders)
            
            if needs_refresh:
                bot_logger.info("开始刷新最高命令缓存...")
                
                # 清理过期缓存
                current_ids = [str(item.get('id', i)) for i, item in enumerate(new_orders)]
                await translation_cache.clear_outdated_cache('orders', current_ids)
                
                # 翻译并缓存新内容
                await self._translate_and_cache_orders(new_orders)
                
                # 更新内容索引
                await translation_cache.store_content_list('orders', new_orders)
                
                # 更新刷新时间戳
                await translation_cache.update_refresh_timestamp('orders')
                
                bot_logger.info("最高命令缓存刷新完成")
                return True
            
            # 只在debug级别记录无需刷新的情况，避免频繁日志
            bot_logger.debug("最高命令内容无变化，跳过缓存刷新")
            return False
            
        except Exception as e:
            bot_logger.error(f"刷新最高命令缓存时发生错误: {e}")
            return False
    
    async def _translate_and_cache_orders(self, orders: List[Dict[str, Any]]) -> None:
        """
        翻译并缓存最高命令数据
        
        Args:
            orders: 最高命令数据列表
        """
        for order in orders:
            try:
                item_id = str(order.get('id', 0))
                setting = order.get("setting", {})
                
                # 获取需要翻译的内容
                original_title = setting.get("overrideTitle", "")
                original_brief = setting.get("overrideBrief", "")
                original_task = setting.get("taskDescription", "")
                
                if not any([original_title, original_brief, original_task]):
                    continue
                
                # 检查是否已有翻译缓存
                cached_translation = await translation_cache.get_translated_content('orders', item_id)
                
                # 构建用于比较的原文
                original_text = f"{original_title}\n{original_brief}\n{original_task}"
                
                # 如果没有缓存或原文发生变化，进行翻译
                if not cached_translation or cached_translation.get('original_text') != original_text:
                    bot_logger.info(f"翻译最高命令 #{item_id}...")
                    
                    # 翻译各个字段
                    translated_title = ""
                    translated_brief = ""
                    translated_task = ""
                    
                    if original_title:
                        title_result = await self.translation_service.translate_text(original_title, "zh")
                        if title_result and title_result != original_title:
                            translated_title = title_result
                    
                    if original_brief:
                        brief_result = await self.translation_service.translate_text(original_brief, "zh")
                        if brief_result and brief_result != original_brief:
                            translated_brief = brief_result
                    
                    if original_task:
                        task_result = await self.translation_service.translate_text(original_task, "zh")
                        if task_result and task_result != original_task:
                            translated_task = task_result
                    
                    # 构建翻译结果（包含原文作为备份）
                    final_title = translated_title if translated_title else original_title
                    final_brief = translated_brief if translated_brief else original_brief
                    final_task = translated_task if translated_task else original_task
                    translated_text = f"{final_title}\n{final_brief}\n{final_task}"
                    
                    # 存储缓存（无论翻译是否成功，都要缓存以避免重复处理）
                    if translated_text:
                        # 存储翻译结果
                        metadata = {
                            'translated_title': translated_title if translated_title else original_title,
                            'translated_brief': translated_brief if translated_brief else original_brief,
                            'translated_task': translated_task if translated_task else original_task,
                            'original_title': original_title,
                            'original_brief': original_brief,
                            'original_task': original_task,
                            'translation_time': datetime.now().isoformat()
                        }
                        
                        await translation_cache.store_translated_content(
                            'orders', item_id, original_text, translated_text, metadata
                        )
                        if translated_title or translated_brief or translated_task:
                            bot_logger.debug(f"最高命令 #{item_id} 部分翻译成功并已缓存")
                        else:
                            bot_logger.debug(f"最高命令 #{item_id} 翻译失败，但原文已缓存")
                else:
                    bot_logger.debug(f"最高命令 #{item_id} 已有有效翻译缓存")
                    
                # 添加小延迟避免API调用过快
                await asyncio.sleep(0.1)
                
            except Exception as e:
                bot_logger.error(f"翻译最高命令 {order.get('id')} 时发生错误: {e}")
    
    async def format_order_messages(self, orders: List[Dict[str, Any]]) -> List[str]:
        """
        格式化最高命令数据为多条消息
        
        Args:
            orders: 最高命令数据列表
        
        Returns:
            格式化后的消息列表
        """
        try:
            if not orders:
                return ["\n📋 当前没有活跃的最高命令"]
            
            messages = []
            
            for i, order in enumerate(orders, 1):
                setting = order.get("setting", {})
                order_id = str(order.get('id', 0))
                
                # 获取原始内容
                title = setting.get("overrideTitle", "未知命令")
                brief = setting.get("overrideBrief", "")
                task_desc = setting.get("taskDescription", "")
                
                # 从缓存获取翻译内容
                translated_title = title
                translated_brief = brief
                translated_task = task_desc
                
                if order_id and order_id != '0':
                    cached_translation = await translation_cache.get_translated_content('orders', order_id)
                    
                    if cached_translation and cached_translation.get('metadata'):
                        metadata = cached_translation['metadata']
                        cached_title = metadata.get('translated_title', '')
                        cached_brief = metadata.get('translated_brief', '')
                        cached_task = metadata.get('translated_task', '')
                        
                        if cached_title:
                            translated_title = cached_title
                        if cached_brief:
                            translated_brief = cached_brief
                        if cached_task:
                            translated_task = cached_task
                        
                        bot_logger.debug(f"使用缓存翻译：最高命令 #{order_id}")
                    else:
                        # 如果没有缓存翻译，使用原文（避免重复翻译）
                        # 翻译应该在缓存阶段完成，这里只是显示
                        bot_logger.warning(f"最高命令 #{order_id} 没有缓存翻译，使用原文显示")
                
                # 清理游戏格式标签
                translated_title = clean_game_text(translated_title)
                translated_brief = clean_game_text(translated_brief)
                translated_task = clean_game_text(translated_task)
                
                # 使用翻译后的内容
                title = translated_title
                brief = translated_brief
                task_desc = translated_task
                
                # 构建单个命令的消息
                message = f"\n📋 最高命令 {i} | HELLDIVERS 2\n"
                message += "-------------\n"
                message += f"▎命令: {title}\n"
                
                if brief:
                    message += f"▎简介: {brief}\n"
                
                if task_desc:
                    message += f"▎任务: {task_desc}\n"
                
                # 显示进度
                progress = order.get("progress", [])
                if progress:
                    progress_value = progress[0] if progress else 0
                    # 格式化进度值，通常需要除以100万得到百分比
                    formatted_progress = progress_value / 1000000 if progress_value > 1000 else progress_value
                    
                    # 智能格式化百分比：根据数值选择合适的小数位数
                    if formatted_progress >= 10:
                        # 大于等于10%，显示1位小数
                        message += f"▎进度: {formatted_progress:.1f}%\n"
                    elif formatted_progress >= 1:
                        # 1%到10%之间，显示2位小数
                        message += f"▎进度: {formatted_progress:.2f}%\n"
                    else:
                        # 小于1%，显示3位小数
                        message += f"▎进度: {formatted_progress:.3f}%\n"
                
                # 显示过期时间
                expires_in = order.get("expiresIn", 0)
                if expires_in > 0:
                    hours = expires_in // 3600
                    minutes = (expires_in % 3600) // 60
                    if hours > 0:
                        message += f"▎剩余时间: {hours}小时{minutes}分钟\n"
                    else:
                        message += f"▎剩余时间: {minutes}分钟\n"
                
                # 显示奖励
                reward = setting.get("reward")
                if reward and reward.get("amount", 0) > 0:
                    reward_amount = reward.get("amount", 0)
                    message += f"▎奖励: {reward_amount:,}奖章\n"
                
                message += "-------------\n"
                message += "执行命令，为了超级地球！🌍"
                
                messages.append(message)
            
            return messages
            
        except Exception as e:
            bot_logger.error(f"格式化最高命令数据时发生错误: {e}")
            return ["\n❌ 数据格式化失败，请稍后重试。"]

# 创建全局最高命令服务实例
order_service = OrderService()
