#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能缓存轮转系统集成示例
展示如何将智能翻译缓存系统集成到现有的轮转管理器中
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from utils.logger import bot_logger
from utils.cache_rotation_integration import cache_rotation_integration


async def main():
    """主程序示例"""
    try:
        bot_logger.info("🎮 Helldivers 2 QQ Bot 启动中...")
        
        # 初始化智能缓存轮转系统
        await cache_rotation_integration.initialize_cache_rotations()
        
        # 显示轮转状态
        status = cache_rotation_integration.get_cache_rotation_status()
        bot_logger.info("📊 缓存轮转状态:")
        for rotation_name, is_active in status.items():
            status_icon = "✅" if is_active else "❌"
            bot_logger.info(f"   {status_icon} {rotation_name}: {'运行中' if is_active else '未运行'}")
        
        bot_logger.info("🚀 机器人启动完成，智能缓存系统已激活")
        bot_logger.info("📋 系统特性:")
        bot_logger.info("   • 快讯每5分钟自动刷新")
        bot_logger.info("   • 最高命令每10分钟自动刷新")
        bot_logger.info("   • 缓存每小时自动清理")
        bot_logger.info("   • 99%相似度智能检测")
        bot_logger.info("   • 自动翻译和持久化存储")
        
        # 示例：手动刷新所有缓存
        bot_logger.info("\n🔧 演示手动刷新功能...")
        await cache_rotation_integration.manual_refresh_all_caches()
        
        # 示例：测试快讯功能
        bot_logger.info("\n📰 测试快讯功能...")
        await test_dispatch_functionality()
        
        # 保持程序运行（在实际应用中，这里会是你的主程序逻辑）
        bot_logger.info("\n⏰ 程序将保持运行，轮转系统在后台工作...")
        bot_logger.info("按 Ctrl+C 退出程序")
        
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        bot_logger.info("👋 收到退出信号...")
    except Exception as e:
        bot_logger.error(f"❌ 程序运行错误: {e}")
    finally:
        # 清理资源
        await cache_rotation_integration.stop_all_cache_rotations()
        bot_logger.info("🛑 程序已退出")


async def test_dispatch_functionality():
    """测试快讯功能"""
    try:
        from core.news import dispatch_service
        
        # 获取快讯数据（会优先使用缓存）
        dispatches = await dispatch_service.get_dispatches(limit=3)
        
        if dispatches:
            bot_logger.info(f"✅ 成功获取 {len(dispatches)} 条快讯")
            
            # 格式化消息（会使用缓存的翻译）
            messages = await dispatch_service.format_dispatch_messages(dispatches)
            
            bot_logger.info("📋 快讯示例:")
            for i, message in enumerate(messages[:1], 1):  # 只显示第一条
                bot_logger.info(f"--- 快讯 {i} ---")
                for line in message.split('\n')[:5]:  # 只显示前5行
                    if line.strip():
                        bot_logger.info(f"   {line}")
                bot_logger.info("   ...")
        else:
            bot_logger.warning("⚠️ 未能获取快讯数据")
            
    except Exception as e:
        bot_logger.error(f"❌ 测试快讯功能失败: {e}")


if __name__ == "__main__":
    # 设置日志级别以便看到更多信息
    import logging
    logging.basicConfig(level=logging.INFO)
    
    asyncio.run(main())

