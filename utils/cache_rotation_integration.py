# -*- coding: utf-8 -*-
"""
缓存轮转集成模块
将智能翻译缓存系统集成到现有的轮转管理器中
"""
import sys
import os

# 确保正确的路径设置
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)

# 添加项目根目录到路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.rotation_manager import RotationManager, TimeBasedStrategy
from utils.translation_cache import translation_cache
from utils.text_matcher import text_matcher
from utils.logger import bot_logger
from typing import Optional


class CacheRotationIntegration:
    """缓存轮转集成器"""
    
    def __init__(self):
        self.rotation_manager = RotationManager()
        self.is_initialized = False
    
    async def initialize_cache_rotations(self) -> None:
        """
        初始化缓存相关的轮转任务
        """
        if self.is_initialized:
            bot_logger.info("缓存轮转已初始化，跳过重复初始化")
            return
        
        bot_logger.info("🔄 初始化智能缓存轮转系统...")
        
        try:
            # 注册快讯缓存刷新任务
            await self._register_dispatch_rotation()
            
            # 注册最高命令缓存刷新任务
            await self._register_order_rotation()
            
            # 注册缓存清理任务
            await self._register_cache_cleanup_rotation()
            
            self.is_initialized = True
            bot_logger.info("✅ 智能缓存轮转系统初始化完成")
            
        except Exception as e:
            bot_logger.error(f"❌ 缓存轮转系统初始化失败: {e}")
            raise
    
    async def _register_dispatch_rotation(self) -> None:
        """注册快讯缓存刷新轮转任务"""
        try:
            from core.msg import dispatch_service
            
            async def dispatch_refresh_handler():
                """快讯缓存刷新处理器"""
                try:
                    bot_logger.debug("🔄 执行快讯缓存刷新检查...")
                    refreshed = await dispatch_service.refresh_cache_if_needed()
                    
                    if refreshed:
                        bot_logger.info("📰 快讯缓存已刷新")
                    else:
                        bot_logger.debug("📰 快讯缓存无需刷新")
                        
                except Exception as e:
                    bot_logger.error(f"❌ 快讯缓存刷新失败: {e}")
            
            # 使用基于时间的策略，每5分钟执行一次
            from utils.rotation_manager import TimeBasedStrategy
            strategy = TimeBasedStrategy(interval=300)  # 5分钟间隔
            
            await self.rotation_manager.register_rotation(
                name="dispatch_cache_refresh",
                handler=dispatch_refresh_handler,
                strategy=strategy,
                start_immediately=True
            )
            
            bot_logger.info("✅ 快讯缓存刷新轮转任务已注册")
            
        except ImportError:
            bot_logger.warning("⚠️ 快讯模块未找到，跳过快讯缓存轮转注册")
        except Exception as e:
            bot_logger.error(f"❌ 注册快讯缓存轮转失败: {e}")
    
    async def _register_order_rotation(self) -> None:
        """注册最高命令缓存刷新轮转任务"""
        try:
            from core.order import order_service
            
            async def order_refresh_handler():
                """最高命令缓存刷新处理器"""
                try:
                    bot_logger.debug("🔄 执行最高命令缓存刷新检查...")
                    
                    # 获取当前最高命令（这会触发缓存检查）
                    orders = await order_service.get_current_orders()
                    
                    if orders:
                        bot_logger.debug(f"📋 最高命令缓存检查完成，当前有 {len(orders)} 条命令")
                    else:
                        bot_logger.debug("📋 当前没有活跃的最高命令")
                        
                except Exception as e:
                    bot_logger.error(f"❌ 最高命令缓存刷新失败: {e}")
            
            # 使用基于时间的策略，每10分钟执行一次
            strategy = TimeBasedStrategy(interval=600)  # 10分钟间隔
            
            await self.rotation_manager.register_rotation(
                name="order_cache_refresh",
                handler=order_refresh_handler,
                strategy=strategy,
                start_immediately=True
            )
            
            bot_logger.info("✅ 最高命令缓存刷新轮转任务已注册")
            
        except ImportError:
            bot_logger.warning("⚠️ 最高命令模块未找到，跳过最高命令缓存轮转注册")
        except Exception as e:
            bot_logger.error(f"❌ 注册最高命令缓存轮转失败: {e}")
    
    async def _register_cache_cleanup_rotation(self) -> None:
        """注册缓存清理轮转任务"""
        try:
            async def cache_cleanup_handler():
                """缓存清理处理器"""
                try:
                    bot_logger.debug("🧹 执行缓存清理任务...")
                    
                    # 获取缓存统计
                    stats = await translation_cache.get_cache_stats()
                    
                    if stats:
                        bot_logger.debug("📊 缓存统计:")
                        for key, value in stats.items():
                            if value is not None:
                                bot_logger.debug(f"   {key}: {value}")
                    
                    bot_logger.debug("✅ 缓存清理任务完成")
                    
                except Exception as e:
                    bot_logger.error(f"❌ 缓存清理失败: {e}")
            
            # 使用基于时间的策略，每小时执行一次
            strategy = TimeBasedStrategy(interval=3600)  # 1小时间隔
            
            await self.rotation_manager.register_rotation(
                name="cache_cleanup",
                handler=cache_cleanup_handler,
                strategy=strategy,
                start_immediately=True
            )
            
            bot_logger.info("✅ 缓存清理轮转任务已注册")
            
        except Exception as e:
            bot_logger.error(f"❌ 注册缓存清理轮转失败: {e}")
    
    async def manual_refresh_all_caches(self) -> None:
        """手动刷新所有缓存"""
        try:
            bot_logger.info("🔄 手动刷新所有缓存...")
            
            # 手动执行快讯缓存刷新
            await self.rotation_manager.manual_rotate("dispatch_cache_refresh")
            
            # 手动执行最高命令缓存刷新
            await self.rotation_manager.manual_rotate("order_cache_refresh")
            
            # 手动执行缓存清理
            await self.rotation_manager.manual_rotate("cache_cleanup")
            
            bot_logger.info("✅ 所有缓存手动刷新完成")
            
        except Exception as e:
            bot_logger.error(f"❌ 手动刷新缓存失败: {e}")
            raise
    
    def get_cache_rotation_status(self) -> dict:
        """获取缓存轮转状态"""
        active_rotations = self.rotation_manager.get_active_rotations()
        
        cache_rotations = [
            "dispatch_cache_refresh",
            "order_cache_refresh", 
            "cache_cleanup"
        ]
        
        status = {}
        for rotation in cache_rotations:
            status[rotation] = rotation in active_rotations
        
        return status
    
    async def stop_all_cache_rotations(self) -> None:
        """停止所有缓存相关的轮转任务"""
        try:
            bot_logger.info("🛑 停止所有缓存轮转任务...")
            
            cache_rotations = [
                "dispatch_cache_refresh",
                "order_cache_refresh",
                "cache_cleanup"
            ]
            
            for rotation_name in cache_rotations:
                await self.rotation_manager.stop_rotation(rotation_name)
            
            self.is_initialized = False
            bot_logger.info("✅ 所有缓存轮转任务已停止")
            
        except Exception as e:
            bot_logger.error(f"❌ 停止缓存轮转任务失败: {e}")


# 创建全局缓存轮转集成器实例
cache_rotation_integration = CacheRotationIntegration()

