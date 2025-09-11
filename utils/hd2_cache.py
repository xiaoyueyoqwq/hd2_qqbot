# -*- coding: utf-8 -*-
"""
Helldivers 2 API缓存服务
管理所有HD2 API数据的缓存
"""
from typing import Dict, Any, Optional, List
from utils.cache_manager import api_cache_manager, CacheConfig
from utils.hd2_api_manager import hd2_api
from utils.logger import bot_logger
from utils.config import Settings


class HD2CacheService:
    """Helldivers 2 缓存服务"""
    
    def __init__(self):
        self.war_id = 801
        self._cache_initialized = False
    
    async def initialize(self):
        """初始化缓存配置"""
        if self._cache_initialized:
            return
        
        # 注册战争统计缓存
        api_cache_manager.register_cache(
            "hd2_war_summary",
            CacheConfig(
                key="hd2:war:summary",
                api_fetcher=self._fetch_war_summary,
                update_interval=Settings.CACHE_UPDATE_INTERVAL,
                expiry=0  # 不过期
            )
        )
        

        
        # 注册最高命令缓存
        api_cache_manager.register_cache(
            "hd2_major_orders",
            CacheConfig(
                key="hd2:major:orders",
                api_fetcher=self._fetch_major_orders,
                update_interval=Settings.CACHE_UPDATE_INTERVAL,
                expiry=0  # 不过期
            )
        )
        
        # 注册Steam更新缓存
        api_cache_manager.register_cache(
            "hd2_steam_updates",
            CacheConfig(
                key="hd2:steam:updates",
                api_fetcher=self._fetch_steam_updates,
                update_interval=Settings.CACHE_UPDATE_INTERVAL,
                expiry=0  # 不过期
            )
        )
        
        # 注册快讯缓存
        api_cache_manager.register_cache(
            "hd2_dispatches",
            CacheConfig(
                key="hd2:dispatches",
                api_fetcher=self._fetch_dispatches,
                update_interval=Settings.CACHE_UPDATE_INTERVAL,
                expiry=0  # 不过期
            )
        )
        
        self._cache_initialized = True
        bot_logger.info("HD2缓存服务初始化完成")
    
    async def _fetch_war_summary(self) -> Optional[Dict[str, Any]]:
        """获取完整的战争数据（包含playerCount和impactMultiplier）"""
        try:
            # 使用完整的war API获取所有数据
            import aiohttp
            headers = {
                'X-Super-Client': 'hd2_qqbot',
                'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
                'User-Agent': 'Helldivers2-QQBot/1.0',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                url = "https://api.helldivers2.dev/api/v1/war"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 构建包含所有需要字段的统计数据
                        if 'statistics' in data:
                            statistics = data['statistics'].copy()
                            # 添加playerCount和impactMultiplier到统计数据中
                            statistics['playerCount'] = statistics.get('playerCount', 0)
                            statistics['impactMultiplier'] = data.get('impactMultiplier', 0)
                            
                            # 处理字段名差异，确保使用bugKills作为terminidKills的别名
                            if 'terminidKills' in statistics:
                                statistics['bugKills'] = statistics['terminidKills']
                                
                            bot_logger.debug("成功获取完整战争统计数据")
                            return statistics
                        else:
                            bot_logger.warning("API响应中缺少statistics数据")
                            return None
                    else:
                        bot_logger.warning(f"API请求失败，状态码: {response.status}")
                        return None
                        
        except Exception as e:
            bot_logger.error(f"获取战争统计数据时发生错误: {e}")
            return None
    

    
    async def _fetch_major_orders(self) -> Optional[List[Dict[str, Any]]]:
        """获取最高命令数据"""
        try:
            endpoint = f"/raw/api/v2/Assignment/War/{self.war_id}"
            response = await hd2_api.get(endpoint)
            
            if response and isinstance(response, list):
                bot_logger.debug("成功获取最高命令数据")
                return response
            else:
                bot_logger.warning("API响应格式不正确或为空")
                return None
                
        except Exception as e:
            bot_logger.error(f"获取最高命令数据时发生错误: {e}")
            return None
    
    async def get_war_summary(self) -> Optional[Dict[str, Any]]:
        """获取缓存的战争统计数据"""
        return await api_cache_manager.get_cached_data("hd2_war_summary")
    

    
    async def get_major_orders(self) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的最高命令数据"""
        return await api_cache_manager.get_cached_data("hd2_major_orders")
    
    async def _fetch_steam_updates(self) -> Optional[List[Dict[str, Any]]]:
        """获取Steam更新数据"""
        try:
            endpoint = "https://api.helldivers2.dev/api/v1/steam"
            import aiohttp
            headers = {
                'X-Super-Client': 'hd2_qqbot',
                'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
                'User-Agent': 'Helldivers2-QQBot/1.0'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.debug(f"成功获取Steam更新数据，共 {len(data)} 条")
                        # 按发布时间排序，最新的在前
                        sorted_data = sorted(data, key=lambda x: x.get('publishedAt', ''), reverse=True)
                        return sorted_data
                    else:
                        bot_logger.warning(f"Steam API请求失败，状态码: {response.status}")
                        return None
                        
        except Exception as e:
            bot_logger.error(f"获取Steam更新数据时发生错误: {e}")
            return None
    
    async def _fetch_dispatches(self) -> Optional[List[Dict[str, Any]]]:
        """获取快讯数据"""
        try:
            endpoint = "https://api.helldivers2.dev/api/v1/dispatches"
            import aiohttp
            headers = {
                'X-Super-Client': 'hd2_qqbot',
                'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
                'User-Agent': 'Helldivers2-QQBot/1.0'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.debug(f"成功获取快讯数据，共 {len(data)} 条")
                        # 按发布时间排序，最新的在前
                        sorted_data = sorted(data, key=lambda x: x.get('published', ''), reverse=True)
                        return sorted_data
                    else:
                        bot_logger.warning(f"快讯API请求失败，状态码: {response.status}")
                        return None
                        
        except Exception as e:
            bot_logger.error(f"获取快讯数据时发生错误: {e}")
            return None
    
    async def get_steam_updates(self) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的Steam更新数据"""
        return await api_cache_manager.get_cached_data("hd2_steam_updates")
    
    async def get_dispatches(self) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的快讯数据"""
        return await api_cache_manager.get_cached_data("hd2_dispatches")
    
    async def force_update_all(self):
        """强制更新所有HD2缓存"""
        caches = ["hd2_war_summary", "hd2_major_orders", "hd2_steam_updates", "hd2_dispatches"]
        results = []
        
        for cache_name in caches:
            result = await api_cache_manager.force_update(cache_name)
            results.append(result)
            
        bot_logger.info(f"强制更新HD2缓存完成: {sum(results)}/{len(results)} 成功")
        return all(results)
    
    async def get_cache_status(self) -> Dict[str, Any]:
        """获取HD2缓存状态"""
        all_status = await api_cache_manager.get_all_cache_status()
        hd2_status = {
            name: status for name, status in all_status.items() 
            if name.startswith("hd2_")
        }
        return hd2_status


# 全局HD2缓存服务实例
hd2_cache_service = HD2CacheService()
