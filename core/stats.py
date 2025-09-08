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
from utils.api_retry import APIRetryMixin

class StatsService(APIRetryMixin):
    """战争统计服务（使用新的war API）"""
    
    def __init__(self):
        super().__init__()
        self.api_url = "https://api.helldivers2.dev/api/v1/war"
        self.timeout = aiohttp.ClientTimeout(total=10)
        
    async def get_war_summary(self) -> Optional[Dict[str, Any]]:
        """
        从新API获取战争总览统计数据（带重试机制）
        
        Returns:
            包含银河战争统计数据的字典，失败时返回 None
        """
        # 设置必需的headers
        headers = {
            'X-Super-Client': 'hd2_qqbot',
            'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
            'User-Agent': 'Helldivers2-QQBot/1.0'
        }
        
        async def _api_call():
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                bot_logger.debug(f"正在从API获取战争统计数据: {self.api_url}")
                async with session.get(self.api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.debug("成功从API获取战争统计数据")
                        return data
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
            message += f"▎总任务时间: {format_time_hours(statistics.get('missionTime', 0))}\n"
            message += f"▎总游戏时间: {format_time_hours(statistics.get('timePlayed', 0))}\n"
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