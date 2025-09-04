# -*- coding: utf-8 -*-
"""
通用API缓存管理器
支持定时更新、快速查询和数据一致性
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from utils.redis_manager import redis_manager
from utils.logger import bot_logger
from utils.config import settings


@dataclass
class CacheConfig:
    """缓存配置"""
    key: str  # Redis键名
    api_fetcher: Callable  # API获取函数
    update_interval: int = 30  # 更新间隔（秒）
    expiry: int = 3600  # 过期时间（秒）
    enabled: bool = True  # 是否启用缓存


class APICacheManager:
    """通用API缓存管理器"""
    
    def __init__(self):
        self._cache_configs: Dict[str, CacheConfig] = {}
        self._update_tasks: Dict[str, asyncio.Task] = {}
        self._is_running = False
        
    def register_cache(self, name: str, config: CacheConfig):
        """
        注册一个缓存配置
        
        Args:
            name: 缓存名称
            config: 缓存配置
        """
        self._cache_configs[name] = config
        bot_logger.info(f"注册缓存配置: {name} -> {config.key}")
    
    async def start(self):
        """启动缓存管理器"""
        if self._is_running:
            return
            
        self._is_running = True
        bot_logger.info("启动API缓存管理器...")
        
        # 立即更新所有缓存
        from utils.config import Settings
        if Settings.CACHE_IMMEDIATE_UPDATE:
            bot_logger.info("执行启动时立即缓存更新...")
            for i, (name, config) in enumerate(self._cache_configs.items()):
                if config.enabled:
                    if i > 0:  # 第一个请求不需要延迟
                        await asyncio.sleep(settings.CACHE_REQUEST_DELAY)
                    await self._update_cache(name, config)
        
        # 为每个缓存配置启动更新任务
        for name, config in self._cache_configs.items():
            if config.enabled:
                task = asyncio.create_task(self._update_loop(name, config))
                self._update_tasks[name] = task
                bot_logger.info(f"启动缓存更新任务: {name}")
    
    async def stop(self):
        """停止缓存管理器"""
        if not self._is_running:
            return
            
        self._is_running = False
        bot_logger.info("停止API缓存管理器...")
        
        # 取消所有更新任务
        for name, task in self._update_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            bot_logger.info(f"停止缓存更新任务: {name}")
        
        self._update_tasks.clear()
    
    async def _update_loop(self, name: str, config: CacheConfig):
        """
        缓存更新循环
        
        Args:
            name: 缓存名称
            config: 缓存配置
        """
        while self._is_running:
            try:
                success = await self._update_cache(name, config)
                
                if success:
                    # 更新成功，等待正常间隔
                    await asyncio.sleep(config.update_interval)
                else:
                    # 更新失败，等待较长时间再重试
                    # 由于底层API管理器现在有重试机制，这里延长等待时间避免过于频繁的重试
                    bot_logger.info(f"缓存 {name} 更新失败，{settings.CACHE_RETRY_DELAY}秒后重试...")
                    await asyncio.sleep(settings.CACHE_RETRY_DELAY)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                bot_logger.error(f"缓存 {name} 更新循环异常: {e}")
                await asyncio.sleep(settings.CACHE_RETRY_DELAY)  # 发生错误时使用配置的重试延迟
    
    async def _update_cache(self, name: str, config: CacheConfig) -> bool:
        """
        更新单个缓存
        
        Args:
            name: 缓存名称
            config: 缓存配置
            
        Returns:
            更新是否成功
        """
        try:
            start_time = time.time()
            
            # 调用API获取数据
            data = await config.api_fetcher()
            
            if data is not None:
                # 构建缓存数据
                cache_data = {
                    "data": data,
                    "last_update": datetime.now().isoformat(),
                    "cache_name": name
                }
                
                # 存储到Redis
                if config.expiry > 0:
                    await redis_manager.set(
                        config.key, 
                        json.dumps(cache_data, ensure_ascii=False),
                        expire=config.expiry
                    )
                else:
                    # 不设置过期时间，直接覆盖
                    await redis_manager.set(
                        config.key, 
                        json.dumps(cache_data, ensure_ascii=False)
                    )
                
                elapsed = time.time() - start_time
                bot_logger.debug(f"缓存 {name} 更新成功，耗时 {elapsed:.2f}s")
                return True
            else:
                bot_logger.warning(f"缓存 {name} 更新失败: API返回空数据")
                return False
                
        except Exception as e:
            bot_logger.error(f"更新缓存 {name} 时发生错误: {e}")
            return False
    
    async def get_cached_data(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存数据
        
        Args:
            name: 缓存名称
            
        Returns:
            缓存的数据，如果不存在则返回None
        """
        try:
            config = self._cache_configs.get(name)
            if not config:
                bot_logger.warning(f"未找到缓存配置: {name}")
                return None
            
            # 从Redis获取数据
            cached_json = await redis_manager.get(config.key)
            if not cached_json:
                bot_logger.debug(f"缓存 {name} 中没有数据")
                return None
            
            cached_data = json.loads(cached_json)
            bot_logger.debug(f"从缓存 {name} 获取数据成功")
            return cached_data.get("data")
            
        except Exception as e:
            bot_logger.error(f"获取缓存 {name} 数据时发生错误: {e}")
            return None
    
    async def get_cache_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存信息（包含元数据）
        
        Args:
            name: 缓存名称
            
        Returns:
            缓存信息，包含数据和元数据
        """
        try:
            config = self._cache_configs.get(name)
            if not config:
                return None
            
            cached_json = await redis_manager.get(config.key)
            if not cached_json:
                return None
            
            return json.loads(cached_json)
            
        except Exception as e:
            bot_logger.error(f"获取缓存 {name} 信息时发生错误: {e}")
            return None
    
    async def force_update(self, name: str) -> bool:
        """
        强制更新指定缓存
        
        Args:
            name: 缓存名称
            
        Returns:
            更新是否成功
        """
        try:
            config = self._cache_configs.get(name)
            if not config:
                bot_logger.warning(f"未找到缓存配置: {name}")
                return False
            
            await self._update_cache(name, config)
            bot_logger.info(f"强制更新缓存 {name} 完成")
            return True
            
        except Exception as e:
            bot_logger.error(f"强制更新缓存 {name} 时发生错误: {e}")
            return False
    
    async def clear_cache(self, name: str) -> bool:
        """
        清除指定缓存
        
        Args:
            name: 缓存名称
            
        Returns:
            清除是否成功
        """
        try:
            config = self._cache_configs.get(name)
            if not config:
                return False
            
            await redis_manager.delete(config.key)
            bot_logger.info(f"清除缓存 {name} 完成")
            return True
            
        except Exception as e:
            bot_logger.error(f"清除缓存 {name} 时发生错误: {e}")
            return False
    
    def get_registered_caches(self) -> List[str]:
        """获取所有已注册的缓存名称"""
        return list(self._cache_configs.keys())
    
    async def get_all_cache_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有缓存的状态信息
        
        Returns:
            所有缓存的状态字典
        """
        status = {}
        
        for name in self._cache_configs.keys():
            cache_info = await self.get_cache_info(name)
            config = self._cache_configs[name]
            
            status[name] = {
                "enabled": config.enabled,
                "update_interval": config.update_interval,
                "has_data": cache_info is not None,
                "last_update": cache_info.get("last_update") if cache_info else None,
                "task_running": name in self._update_tasks and not self._update_tasks[name].done()
            }
        
        return status


# 全局缓存管理器实例
api_cache_manager = APICacheManager()
