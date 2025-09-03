# -*- coding: utf-8 -*-
"""
Helldivers 2 快讯核心业务模块
"""
from typing import Dict, Any, Optional, List
import sys
import os
import aiohttp
import asyncio
import re
from datetime import datetime, timezone

# 确保正确的路径设置
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)

# 添加项目根目录到路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import bot_logger
from utils.translation_cache import translation_cache


def clean_game_text(text: str) -> str:
    """
    清理游戏文本中的格式占位符，转换为纯文本格式
    
    游戏内的 <i=x></i> 占位符说明：
    - <i=1></i>: 通常用于重要信息高亮（如星球名称、武器名称）
    - <i=2></i>: 用于次要信息强调
    - <i=3></i>: 用于标题或警告信息强调
    这些占位符在游戏内会显示为不同颜色或样式，在机器人中转换为空格分隔
    
    Args:
        text: 原始游戏文本
        
    Returns:
        清理后的纯文本
    """
    if not text:
        return text
    
    # 将开始标签 <i=数字> 替换为空格，保持文本分隔
    cleaned = re.sub(r'<i=\d+>', ' ', text)
    # 将结束标签 </i> 替换为空格，保持文本分隔
    cleaned = re.sub(r'</i>', ' ', cleaned)
    
    # 清理多余的空白字符，但保留必要的分隔
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


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
                    "fast_mode": True,  # 启用快速模式
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


class DispatchService:
    """快讯服务（基于智能缓存）"""
    
    def __init__(self):
        self.api_url = "https://api.helldivers2.dev/api/v1/dispatches"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.translation_service = TranslationService()
        
    async def fetch_dispatches_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """
        从API获取原始快讯数据
        
        Returns:
            快讯列表或None(如果获取失败)
        """
        try:
            # 设置必需的headers
            headers = {
                'X-Super-Client': 'hd2_qqbot',
                'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
                'User-Agent': 'Helldivers2-QQBot/1.0'
            }
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                bot_logger.info(f"正在从API获取快讯数据: {self.api_url}")
                async with session.get(self.api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.info(f"成功从API获取快讯数据，共 {len(data)} 条")
                        
                        # 按发布时间排序，最新的在前
                        sorted_data = sorted(data, key=lambda x: x.get('published', ''), reverse=True)
                        
                        return sorted_data
                    else:
                        bot_logger.error(f"获取快讯失败，HTTP状态码: {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            bot_logger.error("获取快讯超时")
            return None
        except aiohttp.ClientError as e:
            bot_logger.error(f"网络请求错误: {e}")
            return None
        except Exception as e:
            bot_logger.error(f"获取快讯时发生未知错误: {e}")
            return None
    
    async def refresh_cache_if_needed(self) -> bool:
        """
        检查并刷新缓存（如果需要）
        由轮转系统调用此方法进行定期刷新
        
        Returns:
            True 如果缓存已刷新
        """
        try:
            # 获取最新的API数据
            new_dispatches = await self.fetch_dispatches_from_api()
            if not new_dispatches:
                bot_logger.warning("无法获取新的快讯数据，跳过缓存刷新")
                return False
            
            # 检查是否需要刷新
            # 检查内容是否需要刷新（比较相似度），只检查前5条
            needs_refresh = await translation_cache.check_content_freshness('dispatches', new_dispatches[:5])
            
            if needs_refresh:
                bot_logger.info("开始刷新快讯缓存...")
                
                # 只处理前5条快讯
                dispatches_to_cache = new_dispatches[:5]
                
                # 清理过期缓存
                current_ids = [str(item.get('id', i)) for i, item in enumerate(dispatches_to_cache)]
                await translation_cache.clear_outdated_cache('dispatches', current_ids)
                
                # 翻译并缓存新内容
                await self._translate_and_cache_dispatches(dispatches_to_cache)
                
                # 更新内容索引
                await translation_cache.store_content_list('dispatches', dispatches_to_cache)
                
                # 更新刷新时间戳
                await translation_cache.update_refresh_timestamp('dispatches')
                
                bot_logger.info("快讯缓存刷新完成")
                return True
            
            return False
            
        except Exception as e:
            bot_logger.error(f"刷新缓存时发生错误: {e}")
            return False
    
    async def _translate_and_cache_dispatches(self, dispatches: List[Dict[str, Any]]) -> None:
        """
        翻译并缓存快讯数据
        
        Args:
            dispatches: 快讯数据列表
        """
        for dispatch in dispatches:
            try:
                item_id = str(dispatch.get('id', 0))
                original_message = dispatch.get('message', '')
                
                if not original_message:
                    continue
                
                # 检查是否已有翻译缓存
                cached_translation = await translation_cache.get_translated_content('dispatches', item_id)
                
                # 如果没有缓存或原文发生变化，进行翻译
                if not cached_translation or cached_translation.get('original_text') != original_message:
                    bot_logger.info(f"翻译快讯 #{item_id}...")
                    
                    translated_text = await self.translation_service.translate_text(original_message, "zh")
                    
                    # 存储翻译结果
                    metadata = {
                        'published': dispatch.get('published'),
                        'type': dispatch.get('type'),
                        'translation_time': datetime.now().isoformat()
                    }
                    
                    await translation_cache.store_translated_content(
                        'dispatches', item_id, original_message, translated_text, metadata
                    )
                else:
                    bot_logger.debug(f"快讯 #{item_id} 已有有效翻译缓存")
                    
                # 添加小延迟避免API调用过快
                await asyncio.sleep(0.1)
                
            except Exception as e:
                bot_logger.error(f"翻译快讯 {dispatch.get('id')} 时发生错误: {e}")
    
    async def get_dispatches(self, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        获取快讯数据（优先从缓存）
        缓存刷新由轮转系统自动处理
        默认获取最新的5条快讯
        
        Args:
            limit: 返回的快讯数量限制
            
        Returns:
            快讯列表或None(如果获取失败)
        """
        try:
            # 从缓存获取快讯列表
            cached_dispatches = await translation_cache.get_content_list('dispatches')
            
            if not cached_dispatches:
                bot_logger.warning("缓存中没有快讯数据，尝试直接从API获取")
                # 如果缓存为空，直接从API获取并缓存
                api_data = await self.fetch_dispatches_from_api()
                if api_data:
                    # 只缓存前5条数据
                    await self._translate_and_cache_dispatches(api_data[:5])
                    await translation_cache.store_content_list('dispatches', api_data[:5])
                    cached_dispatches = api_data[:limit]
                else:
                    return None
            
            # 限制返回数量
            return cached_dispatches[:limit]
            
        except Exception as e:
            bot_logger.error(f"获取快讯数据时发生错误: {e}")
            return None
    
    async def format_dispatch_messages(self, dispatches: List[Dict[str, Any]]) -> List[str]:
        """
        格式化快讯数据为多条消息（使用缓存翻译）
        
        Args:
            dispatches: 快讯数据列表
        
        Returns:
            格式化后的消息列表
        """
        try:
            if not dispatches:
                return ["\n📰 当前没有活跃的快讯"]
            
            messages = []
            
            for i, dispatch in enumerate(dispatches, 1):
                # 获取基本信息
                dispatch_id = dispatch.get('id', 0)
                published_time = self._format_time(dispatch.get('published', ''))
                dispatch_type = self._get_dispatch_type_name(dispatch.get('type', 0))
                original_message = dispatch.get('message', '无内容')
                
                # 从缓存获取翻译内容
                translated_message = original_message
                if original_message and original_message != '无内容':
                    cached_translation = await translation_cache.get_translated_content('dispatches', str(dispatch_id))
                    
                    if cached_translation and cached_translation.get('translated_text'):
                        translated_message = cached_translation['translated_text']
                        bot_logger.debug(f"使用缓存翻译：快讯 #{dispatch_id}")
                    else:
                        # 如果没有缓存翻译，实时翻译
                        bot_logger.warning(f"快讯 #{dispatch_id} 没有缓存翻译，进行实时翻译")
                        translated_content = await self.translation_service.translate_text(original_message, "zh")
                        if translated_content and translated_content != original_message:
                            translated_message = translated_content
                
                # 清理游戏格式标签
                translated_message = clean_game_text(translated_message)
                
                # 构建单个快讯的消息
                message = f"\n📰 快讯 {i} | HELLDIVERS 2\n"
                message += "-------------\n"
                message += f"▎类型: {dispatch_type}\n"
                message += f"▎编号: #{dispatch_id}\n"
                message += f"▎时间: {published_time}\n"
                message += f"▎内容: {translated_message}\n"
                message += "-------------\n"
                message += "获取最新情报，为了超级地球！🌍"
                
                messages.append(message)
            
            return messages
            
        except Exception as e:
            bot_logger.error(f"格式化快讯数据时发生错误: {e}")
            return ["\n❌ 数据格式化失败，请稍后重试。"]
    
    def _format_time(self, time_str: str) -> str:
        """
        格式化时间字符串
        
        Args:
            time_str: ISO格式时间字符串
            
        Returns:
            格式化后的时间字符串
        """
        try:
            # 解析ISO时间格式
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
            # 转换为本地时间显示
            local_dt = dt.replace(tzinfo=timezone.utc).astimezone()
            
            return local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            return "未知时间"
    
    def _get_dispatch_type_name(self, dispatch_type: int) -> str:
        """
        获取快讯类型名称
        
        Args:
            dispatch_type: 快讯类型ID
            
        Returns:
            快讯类型名称
        """
        type_names = {
            0: "一般快讯",
            1: "紧急通告", 
            2: "战术更新",
            3: "系统公告"
        }
        
        return type_names.get(dispatch_type, f"类型{dispatch_type}")


# 创建全局快讯服务实例
dispatch_service = DispatchService()
