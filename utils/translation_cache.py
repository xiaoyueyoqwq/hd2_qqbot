# -*- coding: utf-8 -*-
"""
智能翻译缓存系统
自动获取、翻译、缓存和刷新游戏内容
"""
import asyncio
import orjson as json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from utils.redis_manager import redis_manager
from utils.text_matcher import text_matcher
from utils.logger import bot_logger


class TranslationCache:
    """智能翻译缓存管理器"""
    
    def __init__(self):
        self.cache_prefix = "translation_cache"
        self.default_ttl = 3600  # 1小时默认TTL
        self.refresh_intervals = {
            'dispatches': 300,  # 快讯每5分钟检查一次
            'orders': 600,      # 最高命令每10分钟检查一次
        }
        self.last_refresh = {}
        
    async def get_cache_key(self, content_type: str, item_id: str = None) -> str:
        """生成缓存键"""
        if item_id:
            return f"{self.cache_prefix}:{content_type}:{item_id}"
        return f"{self.cache_prefix}:{content_type}"
    
    async def store_translated_content(self, content_type: str, item_id: str, 
                                     original_text: str, translated_text: str, 
                                     metadata: Dict = None) -> None:
        """
        存储翻译后的内容
        
        Args:
            content_type: 内容类型 (dispatches/orders)
            item_id: 项目ID
            original_text: 原文
            translated_text: 译文
            metadata: 额外元数据
        """
        try:
            cache_key = await self.get_cache_key(content_type, item_id)
            
            cache_data = {
                'original_text': original_text,
                'translated_text': translated_text,
                'metadata': metadata or {},
                'created_at': datetime.now().isoformat(),
                'content_type': content_type,
                'item_id': item_id
            }
            
            # 序列化并存储
            serialized_data = json.dumps(cache_data)
            await redis_manager.set(cache_key, serialized_data, expire=self.default_ttl)
            
            bot_logger.debug(f"已缓存翻译内容: {content_type}:{item_id}")
            
        except Exception as e:
            bot_logger.error(f"存储翻译缓存失败: {e}")
    
    async def get_translated_content(self, content_type: str, item_id: str) -> Optional[Dict]:
        """
        获取翻译后的内容
        
        Args:
            content_type: 内容类型
            item_id: 项目ID
            
        Returns:
            缓存的翻译数据或None
        """
        try:
            cache_key = await self.get_cache_key(content_type, item_id)
            cached_data = await redis_manager.get(cache_key)
            
            if cached_data:
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode('utf-8')
                
                return json.loads(cached_data)
            
            return None
            
        except Exception as e:
            bot_logger.error(f"获取翻译缓存失败: {e}")
            return None
    
    async def store_content_list(self, content_type: str, items: List[Dict]) -> None:
        """
        存储内容列表的索引
        
        Args:
            content_type: 内容类型
            items: 项目列表
        """
        try:
            index_key = await self.get_cache_key(f"{content_type}_index")
            
            # 只存储基本信息用于比较
            index_data = []
            for item in items:
                item_info = {
                    'id': item.get('id'),
                    'published': item.get('published'),
                    'message': item.get('message', ''),
                    'type': item.get('type'),
                    'cached_at': datetime.now().isoformat()
                }
                index_data.append(item_info)
            
            serialized_data = json.dumps(index_data)
            await redis_manager.set(index_key, serialized_data, expire=self.default_ttl * 2)
            
            bot_logger.debug(f"已更新内容索引: {content_type}, 共 {len(items)} 项")
            
        except Exception as e:
            bot_logger.error(f"存储内容索引失败: {e}")
    
    async def get_content_list(self, content_type: str) -> List[Dict]:
        """
        获取内容列表索引
        
        Args:
            content_type: 内容类型
            
        Returns:
            缓存的内容列表
        """
        try:
            index_key = await self.get_cache_key(f"{content_type}_index")
            cached_data = await redis_manager.get(index_key)
            
            if cached_data:
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode('utf-8')
                
                return json.loads(cached_data)
            
            return []
            
        except Exception as e:
            bot_logger.error(f"获取内容索引失败: {e}")
            return []
    
    async def check_content_freshness(self, content_type: str, new_items: List[Dict]) -> bool:
        """
        检查内容是否需要刷新
        
        Args:
            content_type: 内容类型
            new_items: 新获取的项目列表
            
        Returns:
            True 如果需要刷新缓存
        """
        try:
            # 检查刷新间隔
            last_refresh_time = self.last_refresh.get(content_type)
            refresh_interval = self.refresh_intervals.get(content_type, 300)
            
            if last_refresh_time:
                time_since_refresh = (datetime.now() - last_refresh_time).total_seconds()
                if time_since_refresh < refresh_interval:
                    bot_logger.debug(f"{content_type} 刷新间隔未到，跳过检查")
                    return False
            
            # 获取缓存的内容列表
            cached_items = await self.get_content_list(content_type)
            
            if not cached_items:
                bot_logger.info(f"{content_type} 缓存为空，需要刷新")
                return True
            
            # 检查内容变化
            added, updated, deleted = text_matcher.find_content_changes(
                cached_items, new_items, 'message'
            )
            
            needs_refresh = len(added) > 0 or len(updated) > 0 or len(deleted) > 0
            
            if needs_refresh:
                bot_logger.info(f"{content_type} 检测到内容变化，需要刷新缓存")
            else:
                bot_logger.debug(f"{content_type} 内容无变化，无需刷新")
            
            return needs_refresh
            
        except Exception as e:
            bot_logger.error(f"检查内容新鲜度失败: {e}")
            return True  # 出错时强制刷新
    
    async def clear_outdated_cache(self, content_type: str, current_item_ids: List[str]) -> None:
        """
        清理过期的缓存项
        
        Args:
            content_type: 内容类型
            current_item_ids: 当前有效的项目ID列表
        """
        try:
            # 获取所有相关的缓存键
            pattern = f"{self.cache_prefix}:{content_type}:*"
            cached_keys = await redis_manager._get_client().keys(pattern)
            
            # 提取项目ID并检查是否过期
            outdated_keys = []
            for key in cached_keys:
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                
                # 提取项目ID
                parts = key.split(':')
                if len(parts) >= 3:
                    item_id = parts[2]
                    if item_id not in current_item_ids:
                        outdated_keys.append(key)
            
            # 删除过期的缓存
            if outdated_keys:
                await redis_manager._get_client().delete(*outdated_keys)
                bot_logger.info(f"已清理 {len(outdated_keys)} 个过期的 {content_type} 缓存项")
            
        except Exception as e:
            bot_logger.error(f"清理过期缓存失败: {e}")
    
    async def update_refresh_timestamp(self, content_type: str) -> None:
        """更新刷新时间戳"""
        self.last_refresh[content_type] = datetime.now()
        bot_logger.debug(f"已更新 {content_type} 刷新时间戳")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计数据
        """
        try:
            stats = {}
            
            for content_type in ['dispatches', 'orders']:
                # 统计缓存项数量
                pattern = f"{self.cache_prefix}:{content_type}:*"
                keys = await redis_manager._get_client().keys(pattern)
                stats[f"{content_type}_cached_items"] = len(keys)
                
                # 获取最后刷新时间
                last_refresh = self.last_refresh.get(content_type)
                stats[f"{content_type}_last_refresh"] = last_refresh.isoformat() if last_refresh else None
            
            return stats
            
        except Exception as e:
            bot_logger.error(f"获取缓存统计失败: {e}")
            return {}


# 创建全局翻译缓存实例
translation_cache = TranslationCache()

