# -*- coding: utf-8 -*-
"""
Helldivers 2 Steam 更新日志核心业务模块
"""
from typing import Dict, Any, Optional, List
import sys
import os
import aiohttp
import asyncio
from datetime import datetime, timezone

# 确保正确的路径设置
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)

# 添加项目根目录到路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import bot_logger
from utils.translation_cache import translation_cache
from utils.translation_retry_queue import translation_retry_queue
from core.news import TranslationService, clean_game_text
from utils.api_retry import APIRetryMixin


class SteamService(APIRetryMixin):
    """Steam 更新日志服务（基于智能缓存）"""
    
    def __init__(self):
        super().__init__()
        self.api_url = "https://api.helldivers2.dev/api/v1/steam"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.translation_service = TranslationService()
        
    async def fetch_steam_updates_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """
        从API获取原始Steam更新数据（带重试机制）
        
        Returns:
            Steam更新列表或None(如果获取失败)
        """
        # 设置必需的headers
        headers = {
            'X-Super-Client': 'hd2_qqbot',
            'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
            'User-Agent': 'Helldivers2-QQBot/1.0'
        }
        
        async def _api_call():
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                bot_logger.debug(f"正在从API获取Steam更新数据: {self.api_url}")
                async with session.get(self.api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.info(f"成功从API获取Steam更新数据，共 {len(data)} 条")
                        
                        # 按发布时间排序，最新的在前
                        sorted_data = sorted(data, key=lambda x: x.get('publishedAt', ''), reverse=True)
                        return sorted_data
                    else:
                        # 返回带状态码的响应对象，让重试机制处理
                        class APIResponse:
                            def __init__(self, status):
                                self.status = status
                        return APIResponse(response.status)
        
        # 使用重试机制调用API
        result = await self.retry_api_call(_api_call)
        
        # 如果结果是APIResponse对象，说明请求失败
        if hasattr(result, 'status'):
            return None
            
        return result
    
    async def refresh_cache_if_needed(self) -> bool:
        """
        检查并刷新缓存（如果需要）
        由轮转系统调用此方法进行定期刷新
        
        Returns:
            True 如果缓存已刷新
        """
        try:
            # 获取最新的API数据
            new_updates = await self.fetch_steam_updates_from_api()
            if not new_updates:
                bot_logger.warning("无法获取新的Steam更新数据，跳过缓存刷新")
                return False
            
            # 只取最新一条更新进行检查
            latest_update = new_updates[:1] if new_updates else []
            
            # 检查是否需要刷新（比较相似度）
            needs_refresh = await translation_cache.check_content_freshness('steam', latest_update)
            
            if needs_refresh:
                bot_logger.info("开始刷新Steam更新缓存...")
                
                # 只处理最新的一条更新
                updates_to_cache = latest_update
                
                # 清理过期缓存
                current_ids = [str(item.get('id', i)) for i, item in enumerate(updates_to_cache)]
                await translation_cache.clear_outdated_cache('steam', current_ids)
                
                # 翻译并缓存新内容
                await self._translate_and_cache_updates(updates_to_cache)
                
                # 更新内容索引
                await translation_cache.store_content_list('steam', updates_to_cache)
                
                # 更新刷新时间戳
                await translation_cache.update_refresh_timestamp('steam')
                
                bot_logger.info("Steam更新缓存刷新完成")
                return True
            
            # 只在debug级别记录无需刷新的情况，避免频繁日志
            bot_logger.debug("Steam更新内容无变化，跳过缓存刷新")
            return False
            
        except Exception as e:
            bot_logger.error(f"刷新Steam缓存时发生错误: {e}")
            return False
    
    async def _translate_and_cache_updates(self, updates: List[Dict[str, Any]]) -> None:
        """
        翻译并缓存Steam更新数据
        
        Args:
            updates: Steam更新数据列表
        """
        for update in updates:
            try:
                item_id = str(update.get('id', ''))
                original_title = update.get('title', '')
                original_content = update.get('content', '')
                
                if not original_title and not original_content:
                    continue
                
                # 检查是否已有翻译缓存
                cached_translation = await translation_cache.get_translated_content('steam', item_id)
                
                # 构建用于比较的原文（标题+内容）
                original_text = f"{original_title}\n{original_content}" if original_title and original_content else (original_title or original_content)
                
                # 如果没有缓存或原文发生变化，进行翻译
                if not cached_translation or cached_translation.get('original_text') != original_text:
                    bot_logger.info(f"翻译Steam更新 #{item_id}...")
                    
                    # 翻译标题和内容
                    translated_title = ""
                    translated_content = ""
                    
                    if original_title:
                        title_result = await self.translation_service.translate_text(original_title, "zh")
                        if title_result and title_result != original_title:
                            translated_title = title_result
                    
                    if original_content:
                        content_result = await self.translation_service.translate_text(original_content, "zh")
                        if content_result and content_result != original_content:
                            translated_content = content_result
                    
                    # 构建翻译结果（包含原文作为备份）
                    final_title = translated_title if translated_title else original_title
                    final_content = translated_content if translated_content else original_content
                    translated_text = f"{final_title}\n{final_content}" if final_title and final_content else (final_title or final_content)
                    
                    # 存储缓存（无论翻译是否成功，都要缓存以避免重复处理）
                    if translated_text:
                        # 存储翻译结果
                        metadata = {
                            'publishedAt': update.get('publishedAt'),
                            'author': update.get('author'),
                            'url': update.get('url'),
                            'translated_title': translated_title if translated_title else original_title,
                            'translated_content': translated_content if translated_content else original_content,
                            'original_title': original_title,
                            'original_content': original_content,
                            'translation_time': datetime.now().isoformat()
                        }
                        
                        await translation_cache.store_translated_content(
                            'steam', item_id, original_text, translated_text, metadata
                        )
                        if translated_title or translated_content:
                            bot_logger.debug(f"Steam更新 #{item_id} 部分翻译成功并已缓存")
                        else:
                            bot_logger.debug(f"Steam更新 #{item_id} 翻译失败，但原文已缓存")
                else:
                    bot_logger.debug(f"Steam更新 #{item_id} 已有有效翻译缓存")
                    
                # 添加小延迟避免API调用过快
                await asyncio.sleep(0.1)
                
            except Exception as e:
                bot_logger.error(f"翻译Steam更新 {update.get('id')} 时发生错误: {e}")
    
    async def get_latest_steam_update(self) -> Optional[Dict[str, Any]]:
        """
        获取最新的Steam更新数据（优先从缓存）
        缓存刷新由轮转系统自动处理
        
        Returns:
            最新的Steam更新或None(如果获取失败)
        """
        try:
            # 从缓存获取Steam更新列表
            cached_updates = await translation_cache.get_content_list('steam')
            
            if not cached_updates:
                bot_logger.info("缓存中没有Steam更新数据，尝试直接从API获取")
                # 如果缓存为空，直接从API获取并缓存
                api_data = await self.fetch_steam_updates_from_api()
                if api_data:
                    # 只缓存最新的一条数据
                    latest_update = api_data[:1]
                    await self._translate_and_cache_updates(latest_update)
                    await translation_cache.store_content_list('steam', latest_update)
                    cached_updates = latest_update
                else:
                    return None
            
            # 返回最新的一条更新
            return cached_updates[0] if cached_updates else None
            
        except Exception as e:
            bot_logger.error(f"获取Steam更新数据时发生错误: {e}")
            return None
    
    async def format_steam_update_message(self, update: Dict[str, Any]) -> str:
        """
        格式化Steam更新数据为消息（使用缓存翻译）
        
        Args:
            update: Steam更新数据
        
        Returns:
            格式化后的消息
        """
        try:
            if not update:
                return "\n🎮 当前没有Steam更新日志"
            
            # 获取基本信息
            update_id = update.get('id', '')
            title = update.get('title', '无标题')
            content = update.get('content', '无内容')
            author = update.get('author', '未知')
            url = update.get('url', '')
            published_time = self._format_time(update.get('publishedAt', ''))
            
            # 从缓存获取翻译内容
            translated_title = title
            translated_content = content
            
            if update_id:
                cached_translation = await translation_cache.get_translated_content('steam', str(update_id))
                
                if cached_translation and cached_translation.get('metadata'):
                    metadata = cached_translation['metadata']
                    cached_title = metadata.get('translated_title', '')
                    cached_content = metadata.get('translated_content', '')
                    
                    if cached_title:
                        translated_title = cached_title
                    if cached_content:
                        translated_content = cached_content
                    
                    bot_logger.debug(f"使用缓存翻译：Steam更新 #{update_id}")
                else:
                    # 如果没有缓存翻译，使用原文（避免重复翻译）
                    # 翻译应该在缓存阶段完成，这里只是显示
                    bot_logger.warning(f"Steam更新 #{update_id} 没有缓存翻译，使用原文显示")
            
            # 清理游戏格式标签
            translated_title = clean_game_text(translated_title)
            translated_content = clean_game_text(translated_content)
            
            # 截取内容长度，避免消息过长
            if len(translated_content) > 500:
                translated_content = translated_content[:497] + "..."
            
            # 构建消息
            message = f"\n🎮 Steam 更新日志 | HELLDIVERS 2\n"
            message += "-------------\n"
            message += f"▎标题: {translated_title}\n"
            message += f"▎作者: {author}\n"
            message += f"▎时间: {published_time}\n"
            message += "-------------\n"
            message += f"▎内容:\n{translated_content}\n"
            message += "-------------\n"
            
            if url:
                message += f"🔗 详细信息: {url}\n"
                message += "-------------\n"
            
            message += "使用 /steam 可以查看最新更新日志！🌍"
            
            return message
            
        except Exception as e:
            bot_logger.error(f"格式化Steam更新数据时发生错误: {e}")
            return "\n❌ 数据格式化失败，请稍后重试。"
    
    def _format_time(self, time_str: str) -> str:
        """
        格式化时间字符串
        
        Args:
            time_str: ISO格式时间字符串
            
        Returns:
            格式化后的时间字符串
        """
        try:
            # 解析ISO时间格式
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
            # 转换为本地时间显示
            local_dt = dt.replace(tzinfo=timezone.utc).astimezone()
            
            return local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            return "未知时间"


# 创建全局Steam服务实例
steam_service = SteamService()
