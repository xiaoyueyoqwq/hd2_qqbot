# -*- coding: utf-8 -*-
"""
Helldivers 2 战争统计核心业务模块
"""
from typing import Dict, Any, Optional
import sys
import os

# 确保正确的路径设置
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)

# 添加项目根目录到路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import bot_logger
from utils.hd2_cache import hd2_cache_service

class StatsService:
    """战争统计服务（基于缓存）"""
    
    def __init__(self):
        pass  # 不再需要存储war_id，使用缓存服务
    
    async def get_war_summary(self) -> Optional[Dict[str, Any]]:
        """
        从缓存获取战争总览统计数据
        
        Returns:
            包含银河系统计数据的字典，失败时返回 None
        """
        try:
            stats_data = await hd2_cache_service.get_war_summary()
            if stats_data:
                bot_logger.debug("从缓存获取战争统计数据成功")
                return stats_data
            else:
                bot_logger.warning("缓存中没有战争统计数据")
                return None
                
        except Exception as e:
            bot_logger.error(f"从缓存获取战争统计数据时发生错误: {e}")
            return None
    
    async def get_total_friendlies(self, stats: Dict[str, Any]) -> int:
        """
        从galaxy_stats中获取活跃潜兵总数
        
        Args:
            stats: 银河系统计数据
            
        Returns:
            活跃潜兵总数
        """
        try:
            return stats.get('friendlies', 0)
        except Exception as e:
            bot_logger.error(f"获取活跃潜兵数时发生错误: {e}")
            return 0
    
    async def format_stats_message(self, stats: Dict[str, Any]) -> str:
        """
        格式化统计数据为美观的文本消息
        
        Args:
            stats: 银河系统计数据
        
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
            
            # 格式化时间（假设是秒）- 只显示小时
            def format_time(seconds):
                if isinstance(seconds, (int, float)) and seconds > 0:
                    hours = int(seconds // 3600)
                    return f"{hours:,}小时"
                return "0小时"
            
            # 获取活跃潜兵数
            total_friendlies = await self.get_total_friendlies(stats)
            
            message = "\n📊 银河战争统计 | HELLDIVERS 2\n"
            message += "-------------\n"
            message += "📜任务统计\n"
            message += f"▎胜利任务: {format_number(stats.get('missionsWon', 0))}\n"
            message += f"▎失败任务: {format_number(stats.get('missionsLost', 0))}\n"
            message += f"▎成功率: {format_percentage(stats.get('missionSuccessRate', 0))}\n"
            message += f"▎总任务时间: {format_time(stats.get('missionTime', 0))}\n"
            message += f"▎冻肉储备数: {format_number(total_friendlies)}\n"
            message += "-------------\n"
            message += "⚔️战斗统计\n"
            message += f"▎虫族击杀: {format_number(stats.get('bugKills', 0))}\n"
            message += f"▎机器人击杀: {format_number(stats.get('automatonKills', 0))}\n"
            message += f"▎光能族击杀: {format_number(stats.get('illuminateKills', 0))}\n"
            message += f"▎阵亡次数: {format_number(stats.get('deaths', 0))}\n"
            message += f"▎TK伤亡: {format_number(stats.get('friendlies', 0))}\n"
            message += "-------------"
            
            return message
            
        except Exception as e:
            bot_logger.error(f"格式化统计数据时发生错误: {e}")
            return "\n❌ 数据格式化失败，请稍后重试。"

# 创建全局统计服务实例
stats_service = StatsService()
