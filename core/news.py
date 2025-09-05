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
from utils.translation_retry_queue import translation_retry_queue
from utils.api_retry import APIRetryMixin
from utils.config import settings


def clean_game_text(text: str) -> str:
    """
    清理游戏文本中的格式占位符，转换为纯文本格式
    
    支持清理的标签类型：
    - 游戏内 <i=x></i> 占位符：用于高亮显示
    - BBCode标签：[p], [h2], [b], [list], [*] 等
    - HTML标签：<p>, <h2>, <b> 等
    
    Args:
        text: 原始游戏文本
        
    Returns:
        清理后的纯文本
    """
    if not text:
        return text
    
    cleaned = text
    
    # 清理游戏内的 <i=x></i> 占位符
    cleaned = re.sub(r'<i=\d+>', ' ', cleaned)
    cleaned = re.sub(r'</i>', ' ', cleaned)
    
    # 清理BBCode标签 - 保留内容，移除标签
    # 段落标签
    cleaned = re.sub(r'\[/?p\]', '\n', cleaned)
    # 标题标签
    cleaned = re.sub(r'\[/?h[1-6]\]', '\n', cleaned)
    # 粗体标签
    cleaned = re.sub(r'\[/?b\]', '', cleaned)
    # 斜体标签
    cleaned = re.sub(r'\[/?i\]', '', cleaned)
    # 下划线标签
    cleaned = re.sub(r'\[/?u\]', '', cleaned)
    # 列表标签
    cleaned = re.sub(r'\[/?list\]', '\n', cleaned)
    # 列表项标签
    cleaned = re.sub(r'\[\*\]', '\n• ', cleaned)
    cleaned = re.sub(r'\[/\*\]', '', cleaned)
    # 颜色标签
    cleaned = re.sub(r'\[color=[^\]]+\]', '', cleaned)
    cleaned = re.sub(r'\[/color\]', '', cleaned)
    # URL标签
    cleaned = re.sub(r'\[url=[^\]]+\]', '', cleaned)
    cleaned = re.sub(r'\[/url\]', '', cleaned)
    # 其他常见BBCode标签
    cleaned = re.sub(r'\[/?[a-zA-Z][a-zA-Z0-9]*(?:=[^\]]+)?\]', '', cleaned)
    
    # 清理HTML标签（如果有）
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    
    # 清理垃圾链接和样式标签
    # 移除zendesk链接和相关内容
    cleaned = re.sub(r'zendesk\.com[^\s\]]*', '', cleaned)
    cleaned = re.sub(r'style="[^"]*"', '', cleaned)
    cleaned = re.sub(r'\]已知问题.*?$', '', cleaned, flags=re.MULTILINE)
    
    # 清理其他常见的垃圾内容
    cleaned = re.sub(r'https?://[^\s\]]+', '', cleaned)  # 移除所有HTTP链接
    cleaned = re.sub(r'--HELLDIVERS-2-[^\]]*', '', cleaned)  # 移除特定格式的标识符
    
    # 清理多余的空白字符，但保留段落分隔
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)  # 多个连续换行合并为两个
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)  # 多个空格合并为一个
    cleaned = cleaned.strip()
    
    return cleaned


class TranslationService(APIRetryMixin):
    """AI智能翻译服务"""
    
    def __init__(self):
        super().__init__()
        self.api_url = settings.TRANSLATION_API_URL
        self.timeout = aiohttp.ClientTimeout(total=settings.TRANSLATION_TIMEOUT)
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": settings.HD2_API_USER_AGENT
        }
    
    async def translate_text(self, text: str, to_lang: str = "zh-CN") -> Optional[str]:
        """
        使用AI智能翻译文本（带重试机制）
        
        Args:
            text: 待翻译的文本
            to_lang: 目标语言代码，默认为中文简体(zh-CN)
        
        Returns:
            翻译后的文本，失败时返回原文
        """
        if not text or not text.strip() or len(text.strip()) < 3:
            return text
        
        payload = {
            "text": text.strip(),
            "sourceLanguage": "auto",
            "targetLanguage": to_lang
        }
        
        async def _api_call():
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(self.api_url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if "translatedText" in data:
                                translated_text = data["translatedText"].strip()
                                if translated_text and translated_text != text.strip():
                                    return translated_text
                                else:
                                    bot_logger.warning(f"AI翻译结果为空或与原文相同: '{text[:30]}...'")
                                    return text  # 返回原文表示翻译无效
                            else:
                                error_msg = data.get('error', 'Unknown error')
                                bot_logger.error(f"AI翻译API返回错误: {error_msg}")
                                return None # API逻辑错误
                        except Exception as json_error:
                            bot_logger.error(f"解析AI翻译API响应JSON失败: {json_error}")
                            return None # JSON解析错误
                    else:
                        # 返回带状态码的响应对象，让重试机制处理
                        class APIResponse:
                            def __init__(self, status):
                                self.status = status
                        return APIResponse(response.status)

        result = await self.retry_api_call(
            _api_call,
            base_delay=settings.TRANSLATION_RETRY_BASE_DELAY,
            max_delay=settings.TRANSLATION_RETRY_MAX_DELAY,
            increment=settings.TRANSLATION_RETRY_INCREMENT
        )

        if result and not hasattr(result, 'status'):
            return result
        else:
            bot_logger.error(f"AI翻译最终失败，返回原文: '{text[:30]}...'")
            return text


class DispatchService(APIRetryMixin):
    """快讯服务（基于智能缓存）"""
    
    def __init__(self):
        super().__init__()
        self.api_url = "https://api.helldivers2.dev/api/v1/dispatches"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.translation_service = TranslationService()
        
    async def fetch_dispatches_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """
        从API获取原始快讯数据（带重试机制）
        
        Returns:
            快讯列表或None(如果获取失败)
        """
        # 设置必需的headers
        headers = {
            'X-Super-Client': 'hd2_qqbot',
            'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
            'User-Agent': 'Helldivers2-QQBot/1.0'
        }
        
        async def _api_call():
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                bot_logger.debug(f"正在从API获取快讯数据: {self.api_url}")
                async with session.get(self.api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.info(f"成功从API获取快讯数据，共 {len(data)} 条")
                        
                        # 按发布时间排序，最新的在前
                        sorted_data = sorted(data, key=lambda x: x.get('published', ''), reverse=True)
                        return sorted_data
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
            
            # 只在debug级别记录无需刷新的情况，避免频繁日志
            bot_logger.debug("快讯内容无变化，跳过缓存刷新")
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
                    
                    # 只有翻译成功且与原文不同时才存储缓存
                    if translated_text and translated_text != original_message:
                        # 存储翻译结果
                        metadata = {
                            'published': dispatch.get('published'),
                            'type': dispatch.get('type'),
                            'translation_time': datetime.now().isoformat()
                        }
                        
                        await translation_cache.store_translated_content(
                            'dispatches', item_id, original_message, translated_text, metadata
                        )
                        bot_logger.debug(f"快讯 #{item_id} 翻译成功并已缓存")
                    else:
                        # 翻译失败，添加到重试队列
                        metadata = {
                            'published': dispatch.get('published'),
                            'type': dispatch.get('type'),
                            'failed_at': datetime.now().isoformat()
                        }
                        
                        await translation_retry_queue.add_retry_task(
                            'dispatches', item_id, original_message, metadata
                        )
                        bot_logger.info(f"快讯 #{item_id} 翻译失败，已添加到重试队列")
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
                bot_logger.info("缓存中没有快讯数据，尝试直接从API获取")
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
                        bot_logger.info(f"快讯 #{dispatch_id} 没有缓存翻译，进行实时翻译")
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
                message += "使用/news [1-5]可以查看其他快讯！🌍"
                
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
