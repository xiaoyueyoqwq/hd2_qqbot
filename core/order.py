# -*- coding: utf-8 -*-
"""
Helldivers 2 最高命令核心业务模块
"""
from typing import Dict, Any, Optional, List
import sys
import os
import aiohttp
import asyncio

# 确保正确的路径设置
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)

# 添加项目根目录到路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 从项目根目录导入
import importlib.util
hd2_api_spec = importlib.util.spec_from_file_location("hd2_api_manager", os.path.join(project_root, "utils", "hd2_api_manager.py"))
hd2_api_module = importlib.util.module_from_spec(hd2_api_spec)
hd2_api_spec.loader.exec_module(hd2_api_module)
hd2_api = hd2_api_module.hd2_api

from utils.logger import bot_logger

class TranslationService:
    """AI智能翻译服务"""
    
    def __init__(self):
        self.api_url = "https://uapis.cn/api/v1/ai/translate"
        self.timeout = aiohttp.ClientTimeout(total=20)  # 增加超时时间
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "hd2_qqbot/1.0"
        }
    
    async def translate_text(self, text: str, to_lang: str = "zh") -> Optional[str]:
        """
        使用AI智能翻译文本
        
        Args:
            text: 待翻译的文本
            to_lang: 目标语言代码，默认为中文(zh)
        
        Returns:
            翻译后的文本，失败时返回原文
        """
        if not text or not text.strip():
            return text
        
        # 如果文本很短，跳过翻译
        if len(text.strip()) < 3:
            return text
            
        try:
            # 构建完整URL（包含查询参数）
            url = f"{self.api_url}?target_lang={to_lang}"
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # 构建请求数据 - 使用新的AI翻译接口
                payload = {
                    "text": text.strip(),
                    "source_lang": "en",  # 指定源语言为英语
                    "style": "casual",  # 使用随意口语化风格，适合游戏内容
                    "context": "entertainment",  # 娱乐上下文，适合游戏
                    "fast_mode": False,  # 不启用快速模式
                    "preserve_format": True  # 保留格式
                }
                
                bot_logger.debug(f"AI翻译请求: '{text}' -> {to_lang}")
                bot_logger.debug(f"请求载荷: {payload}")
                
                async with session.post(url, json=payload, headers=self.headers) as response:
                    response_text = await response.text()
                    bot_logger.debug(f"AI翻译API响应状态: {response.status}")
                    bot_logger.debug(f"AI翻译API响应内容: {response_text}")
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            
                            # 检查新API的响应格式
                            if data.get("code") == 200 and "data" in data:
                                translated_text = data["data"].get("translated_text", "").strip()
                                confidence = data["data"].get("confidence_score", 0)
                                
                                if translated_text and translated_text != text.strip():
                                    bot_logger.info(f"AI翻译成功 (置信度: {confidence:.2f}): '{text}' -> '{translated_text}'")
                                    return translated_text
                                else:
                                    bot_logger.warning(f"AI翻译结果为空或与原文相同: '{text}'")
                                    return text
                            else:
                                error_msg = data.get('message', 'Unknown error')
                                bot_logger.warning(f"AI翻译API返回错误: {error_msg}")
                                return text
                        except Exception as json_error:
                            bot_logger.error(f"解析AI翻译API响应JSON失败: {json_error}")
                            return text
                    else:
                        bot_logger.warning(f"AI翻译API请求失败: 状态码 {response.status}")
                        bot_logger.warning(f"错误响应: {response_text}")
                        return text
                        
        except asyncio.TimeoutError:
            bot_logger.error("AI翻译API请求超时")
            return text
        except aiohttp.ClientError as e:
            bot_logger.error(f"AI翻译API网络错误: {e}")
            return text
        except Exception as e:
            bot_logger.error(f"AI翻译请求异常: {e}")
            return text

class OrderService:
    """最高命令服务（基于缓存）"""
    
    def __init__(self):
        self.translation_service = TranslationService()
    
    async def get_current_orders(self) -> Optional[List[Dict[str, Any]]]:
        """
        从缓存获取当前最高命令
        
        Returns:
            包含最高命令数据的列表，失败时返回 None
        """
        try:
            from utils.hd2_cache import hd2_cache_service
            orders_data = await hd2_cache_service.get_major_orders()
            if orders_data:
                bot_logger.debug("从缓存获取最高命令数据成功")
                return orders_data
            else:
                bot_logger.warning("缓存中没有最高命令数据")
                return None
                
        except Exception as e:
            bot_logger.error(f"从缓存获取最高命令数据时发生错误: {e}")
            return None
    
    async def format_order_messages(self, orders: List[Dict[str, Any]]) -> List[str]:
        """
        格式化最高命令数据为多条消息
        
        Args:
            orders: 最高命令数据列表
        
        Returns:
            格式化后的消息列表
        """
        try:
            if not orders:
                return ["\n📋 当前没有活跃的最高命令"]
            
            messages = []
            
            for i, order in enumerate(orders, 1):
                setting = order.get("setting", {})
                
                # 获取标题和描述
                title = setting.get("overrideTitle", "未知命令")
                brief = setting.get("overrideBrief", "")
                task_desc = setting.get("taskDescription", "")
                
                # 翻译标题
                if title and title != "未知命令":
                    translated_title = await self.translation_service.translate_text(title, "zh")
                    if translated_title and translated_title != title:
                        title = translated_title
                
                # 翻译简介
                if brief:
                    translated_brief = await self.translation_service.translate_text(brief, "zh")
                    if translated_brief and translated_brief != brief:
                        brief = translated_brief
                
                # 翻译任务描述
                if task_desc:
                    translated_task = await self.translation_service.translate_text(task_desc, "zh")
                    if translated_task and translated_task != task_desc:
                        task_desc = translated_task
                
                # 构建单个命令的消息
                message = f"\n📋 最高命令 {i} | HELLDIVERS 2\n"
                message += "-------------\n"
                message += f"▎命令: {title}\n"
                
                if brief:
                    message += f"▎简介: {brief}\n"
                
                if task_desc:
                    message += f"▎任务: {task_desc}\n"
                
                # 显示进度
                progress = order.get("progress", [])
                if progress:
                    progress_value = progress[0] if progress else 0
                    # 格式化进度值，通常需要除以100万得到百分比
                    formatted_progress = progress_value / 1000000 if progress_value > 1000 else progress_value
                    
                    # 智能格式化百分比：根据数值选择合适的小数位数
                    if formatted_progress >= 10:
                        # 大于等于10%，显示1位小数
                        message += f"▎进度: {formatted_progress:.1f}%\n"
                    elif formatted_progress >= 1:
                        # 1%到10%之间，显示2位小数
                        message += f"▎进度: {formatted_progress:.2f}%\n"
                    else:
                        # 小于1%，显示3位小数
                        message += f"▎进度: {formatted_progress:.3f}%\n"
                
                # 显示过期时间
                expires_in = order.get("expiresIn", 0)
                if expires_in > 0:
                    hours = expires_in // 3600
                    minutes = (expires_in % 3600) // 60
                    if hours > 0:
                        message += f"▎剩余时间: {hours}小时{minutes}分钟\n"
                    else:
                        message += f"▎剩余时间: {minutes}分钟\n"
                
                # 显示奖励
                reward = setting.get("reward")
                if reward and reward.get("amount", 0) > 0:
                    reward_amount = reward.get("amount", 0)
                    message += f"▎奖励: {reward_amount:,}奖章\n"
                
                message += "-------------\n"
                message += "执行命令，为了超级地球！🌍"
                
                messages.append(message)
            
            return messages
            
        except Exception as e:
            bot_logger.error(f"格式化最高命令数据时发生错误: {e}")
            return ["\n❌ 数据格式化失败，请稍后重试。"]

# 创建全局最高命令服务实例
order_service = OrderService()
