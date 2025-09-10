#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存系统测试脚本
验证所有服务是否正确遵循Redis优先原则
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import bot_logger
from utils.redis_manager import redis_manager
from utils.cache_manager import api_cache_manager
from utils.hd2_cache import hd2_cache_service
from core.stats import stats_service
from core.news import dispatch_service

async def test_cache_system():
    """测试缓存系统是否正常工作"""
    
    try:
        bot_logger.info("🧪 开始测试缓存系统...")
        
        # 1. 测试Redis连接
        bot_logger.info("1️⃣ 测试Redis连接...")
        await redis_manager.initialize()
        
        # 2. 初始化HD2缓存服务
        bot_logger.info("2️⃣ 初始化HD2缓存服务...")
        await hd2_cache_service.initialize()
        
        # 3. 启动缓存管理器
        bot_logger.info("3️⃣ 启动缓存管理器...")
        await api_cache_manager.start()
        
        # 4. 等待缓存更新
        bot_logger.info("4️⃣ 等待缓存更新...")
        await asyncio.sleep(10)
        
        # 5. 测试各个服务的缓存获取
        bot_logger.info("5️⃣ 测试统计数据缓存...")
        stats_data = await stats_service.get_war_summary()
        if stats_data:
            bot_logger.info("✅ 统计数据缓存获取成功")
        else:
            bot_logger.warning("⚠️ 统计数据缓存为空")
        
        bot_logger.info("6️⃣ 测试快讯数据缓存...")
        dispatches = await dispatch_service.get_dispatches(3)
        if dispatches:
            bot_logger.info(f"✅ 快讯数据缓存获取成功，数量: {len(dispatches)}")
        else:
            bot_logger.warning("⚠️ 快讯数据缓存为空")
        
        # 6. 测试缓存状态
        bot_logger.info("7️⃣ 检查缓存状态...")
        cache_status = await hd2_cache_service.get_cache_status()
        for cache_name, status in cache_status.items():
            has_data = status.get('has_data', False)
            last_update = status.get('last_update', 'N/A')
            bot_logger.info(f"  {cache_name}: {'✅' if has_data else '❌'} 数据存在, 最后更新: {last_update}")
        
        # 7. 检查注册的缓存
        registered_caches = api_cache_manager.get_registered_caches()
        bot_logger.info(f"8️⃣ 已注册的缓存: {registered_caches}")
        
        # 8. 强制更新测试
        bot_logger.info("9️⃣ 测试强制更新...")
        update_result = await hd2_cache_service.force_update_all()
        bot_logger.info(f"强制更新结果: {'✅ 成功' if update_result else '❌ 失败'}")
        
        bot_logger.info("🎉 缓存系统测试完成!")
        
    except Exception as e:
        bot_logger.error(f"❌ 缓存系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # 清理资源
        try:
            await api_cache_manager.stop()
            await redis_manager.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_cache_system())
