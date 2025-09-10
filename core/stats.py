# -*- coding: utf-8 -*-
"""
Helldivers 2 战争统计核心业务模块
"""
from typing import Dict, Any, Optional
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
from utils.cache_manager import api_cache_manager, CacheConfig
from utils.config import Settings


class StatsService:
    """战争统计服务（使用新的war API）"""

    def __init__(self):
        self.api_url = "https://api.helldivers2.dev/api/v1/war"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self._register_caches()

    def _register_caches(self):
        """注册缓存"""
        stats_cache_config = CacheConfig(
            key="hd2:stats:war",
            api_fetcher=self._fetch_war_data,
            update_interval=Settings.CACHE_UPDATE_INTERVAL,
            expiry=0  # 不过期，始终使用缓存
        )
        api_cache_manager.register_cache("war_stats", stats_cache_config)
    
    async def _fetch_war_data(self) -> Optional[Dict[str, Any]]:
        """从API获取战争数据"""
        try:
            headers = {
                'X-Super-Client': 'hd2_qqbot',
                'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
                'User-Agent': 'Helldivers2-QQBot/1.0',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession(
                headers=headers,
                timeout=self.timeout
            ) as session:
                bot_logger.debug(f"获取战争统计数据: {self.api_url}")
                async with session.get(self.api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.debug("成功获取战争统计数据")
                        return data
                    else:
                        bot_logger.warning(f"API请求失败，状态码: {response.status}")
                        return None
        except Exception as e:
            bot_logger.error(f"获取战争统计数据时发生错误: {e}")
            return None

    async def get_war_summary(self) -> Optional[Dict[str, Any]]:
        """
        从缓存获取战争总览统计数据
        
        Returns:
            包含银河战争统计数据的字典，失败时返回 None
        """
        try:
            data = await api_cache_manager.get_cached_data("war_stats")
            if data:
                bot_logger.debug("成功从缓存获取战争统计数据")
                return data
            else:
                bot_logger.warning("从缓存获取战争统计数据失败，可能正在更新或API不可用")
                return None
        except Exception as e:
            bot_logger.error(f"获取战争统计数据时发生异常: {e}", exc_info=True)
            return None
    
    def _format_time_duration(self, started: str, now: str) -> str:
        """
        计算战争持续时间
        
        Args:
            started: 战争开始时间
            now: 当前时间
            
        Returns:
            格式化的持续时间字符串
        """
        try:
            start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
            now_dt = datetime.fromisoformat(now.replace('Z', '+00:00'))
            
            duration = now_dt - start_dt
            days = duration.days
            hours = duration.seconds // 3600
            
            if days > 0:
                return f"{days}天{hours}小时"
            else:
                return f"{hours}小时"
        except Exception:
            return "未知"
    
    async def format_stats_message(self, war_data: Dict[str, Any]) -> str:
        """
        格式化战争数据为美观的文本消息
        
        Args:
            war_data: 战争数据（来自新API）
        
        Returns:
            格式化后的文本消息
        """
        try:
            # 格式化数字，添加千位分隔符
            def format_number(num):
                if isinstance(num, (int, float)):
                    return f"{num:,}"
                return str(num)
            
            # 格式化百分比
            def format_percentage(num):
                if isinstance(num, (int, float)):
                    return f"{num:.1f}%"
                return str(num)
            
            # 格式化时间（秒转小时）
            def format_time_hours(seconds):
                if isinstance(seconds, (int, float)) and seconds > 0:
                    hours = int(seconds // 3600)
                    return f"{hours:,}小时"
                return "0小时"
            
            # 获取统计数据
            statistics = war_data.get('statistics', {})
            
            
            message = "\n📊 银河战争统计 | HELLDIVERS 2\n"
            message += "-------------\n"
            message += "🌌战争信息\n"
            message += f"▎在线玩家: {format_number(statistics.get('playerCount', 0))}\n"
            message += f"▎影响系数: {war_data.get('impactMultiplier', 0):.6f}\n"
            message += f"▎发射子弹: {format_number(statistics.get('bulletsFired', 0))}\n"
            message += f"▎冻肉储备数: {format_number(statistics.get('friendlies', 0))}\n"
            message += "-------------\n"
            message += "📜任务统计\n"
            message += f"▎胜利任务: {format_number(statistics.get('missionsWon', 0))}\n"
            message += f"▎失败任务: {format_number(statistics.get('missionsLost', 0))}\n"
            message += f"▎成功率: {format_percentage(statistics.get('missionSuccessRate', 0))}\n"
            message += f"▎总任务时间: {format_time_hours(statistics.get('timePlayed', 0))}\n"
            message += "-------------\n"
            message += "⚔️战斗统计\n"
            message += f"▎虫族击杀: {format_number(statistics.get('terminidKills', 0))}\n"
            message += f"▎机器人击杀: {format_number(statistics.get('automatonKills', 0))}\n"
            message += f"▎光能族击杀: {format_number(statistics.get('illuminateKills', 0))}\n"
            message += f"▎阵亡次数: {format_number(statistics.get('deaths', 0))}\n"
            message += f"▎TK伤亡: {format_number(statistics.get('friendlies', 0))}\n"
            message += "-------------"
            
            return message
            
        except Exception as e:
            bot_logger.error(f"格式化统计数据时发生错误: {e}")
            return "\n❌ 数据格式化失败，请稍后重试。"

# 创建全局统计服务实例
stats_service = StatsService()