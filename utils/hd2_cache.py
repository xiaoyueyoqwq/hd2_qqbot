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
        
        self._cache_initialized = True
        bot_logger.info("HD2缓存服务初始化完成")
    
    async def _fetch_war_summary(self) -> Optional[Dict[str, Any]]:
        """获取战争统计数据"""
        try:
            endpoint = f"/raw/api/Stats/war/{self.war_id}/summary"
            response = await hd2_api.get(endpoint)
            
            if response and "galaxy_stats" in response:
                bot_logger.debug("成功获取战争统计数据")
                return response["galaxy_stats"]
            else:
                bot_logger.warning("API响应中缺少galaxy_stats数据")
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
    

    
    async def force_update_all(self):
        """强制更新所有HD2缓存"""
        caches = ["hd2_war_summary", "hd2_major_orders"]
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
