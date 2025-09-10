# -*- coding: utf-8 -*-
"""
Helldivers 2 Steam 更新日志核心业务模块
"""
from typing import Dict, Any, Optional, List
import sys
import os
import re
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
from utils.translation_cache import translation_cache
from utils.translation_retry_queue import translation_retry_queue
from core.news import TranslationService, clean_game_text
from utils.api_retry import APIRetryMixin
from utils.config import settings
from utils.hd2_cache import hd2_cache_service


class SteamService(APIRetryMixin):
    """Steam 更新日志服务（基于智能缓存）"""
    
    def __init__(self):
        super().__init__()
        self.api_url = "https://api.helldivers2.dev/api/v1/steam"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.translation_service = TranslationService()
        
    async def fetch_steam_updates_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """
        从API获取原始Steam更新数据（带重试机制）
        
        Returns:
            Steam更新列表或None(如果获取失败)
        """
        # 设置必需的headers
        headers = {
            'X-Super-Client': 'hd2_qqbot',
            'X-Super-Contact': 'xiaoyueyoqwq@vaiiya.org',
            'User-Agent': 'Helldivers2-QQBot/1.0'
        }
        
        async def _api_call():
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                bot_logger.debug(f"正在从API获取Steam更新数据: {self.api_url}")
                async with session.get(self.api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.info(f"成功从API获取Steam更新数据，共 {len(data)} 条")
                        
                        # 按发布时间排序，最新的在前
                        sorted_data = sorted(data, key=lambda x: x.get('publishedAt', ''), reverse=True)
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
            new_updates = await self.fetch_steam_updates_from_api()
            if not new_updates:
                bot_logger.warning("无法获取新的Steam更新数据，跳过缓存刷新")
                return False
            
            # 只取最新一条更新进行检查
            latest_update = new_updates[:1] if new_updates else []
            
            # 检查是否需要刷新（比较相似度）
            needs_refresh = await translation_cache.check_content_freshness('steam', latest_update)
            
            if needs_refresh:
                bot_logger.info("开始刷新Steam更新缓存...")
                
                # 只处理最新的一条更新
                updates_to_cache = latest_update
                
                # 清理过期缓存
                current_ids = [str(item.get('id', i)) for i, item in enumerate(updates_to_cache)]
                await translation_cache.clear_outdated_cache('steam', current_ids)
                
                # 翻译并缓存新内容
                await self._translate_and_cache_updates(updates_to_cache)
                
                # 更新内容索引
                await translation_cache.store_content_list('steam', updates_to_cache)
                
                # 更新刷新时间戳
                await translation_cache.update_refresh_timestamp('steam')
                
                bot_logger.info("Steam更新缓存刷新完成")
                return True
            
            # 只在debug级别记录无需刷新的情况，避免频繁日志
            bot_logger.debug("Steam更新内容无变化，跳过缓存刷新")
            return False
            
        except Exception as e:
            bot_logger.error(f"刷新Steam缓存时发生错误: {e}")
            return False
    
    async def _translate_and_cache_updates(self, updates: List[Dict[str, Any]]) -> bool:
        """
        翻译并缓存Steam更新数据
        
        Args:
            updates: Steam更新数据列表
        
        Returns:
            bool: 如果至少有一个更新被成功处理，则返回True
        """
        all_successful = True
        processed_count = 0
        for update in updates:
            try:
                item_id = str(update.get('id', ''))
                original_title = update.get('title', '')
                original_content = update.get('content', '')
                
                if not original_title and not original_content:
                    bot_logger.debug(f"Steam更新 #{item_id} 标题和内容都为空，跳过。")
                    continue
                
                # 检查是否已有翻译缓存
                cached_translation = await translation_cache.get_translated_content('steam', item_id)
                
                # 构建用于比较的原文（标题+内容）
                original_text = f"{original_title}\n{original_content}" if original_title and original_content else (original_title or original_content)
                
                # 如果没有缓存或原文发生变化，进行翻译
                if not cached_translation or cached_translation.get('original_text') != original_text:
                    bot_logger.info(f"翻译Steam更新 #{item_id}...")
                    
                    # 翻译标题和内容
                    translated_title = ""
                    translated_content = ""
                    
                    if original_title:
                        title_result = await self.translation_service.translate_text(original_title, "zh")
                        if title_result and title_result != original_title:
                            translated_title = title_result
                    
                    if original_content:
                        content_result = await self.translation_service.translate_text(original_content, "zh")
                        if content_result and content_result != original_content:
                            translated_content = content_result
                    
                    # 如果翻译失败，则跳过此更新的缓存
                    if not translated_title and not translated_content and (original_title or original_content):
                        bot_logger.error(f"Steam更新 #{item_id} 翻译完全失败，跳过缓存。")
                        all_successful = False
                        continue

                    # 构建翻译结果（包含原文作为备份）
                    final_title = translated_title if translated_title else original_title
                    final_content = translated_content if translated_content else original_content
                    translated_text = f"{final_title}\n{final_content}" if final_title and final_content else (final_title or final_content)
                    
                    # 存储缓存（无论翻译是否成功，都要缓存以避免重复处理）
                    if translated_text:
                        # 存储翻译结果
                        metadata = {
                            'publishedAt': update.get('publishedAt'),
                            'author': update.get('author'),
                            'url': update.get('url'),
                            'translated_title': translated_title if translated_title else original_title,
                            'translated_content': translated_content if translated_content else original_content,
                            'original_title': original_title,
                            'original_content': original_content,
                            'translation_time': datetime.now().isoformat()
                        }
                        
                        await translation_cache.store_translated_content(
                            'steam', item_id, original_text, translated_text, metadata
                        )
                        processed_count += 1
                        if translated_title or translated_content:
                            bot_logger.debug(f"Steam更新 #{item_id} 部分翻译成功并已缓存")
                        else:
                            bot_logger.debug(f"Steam更新 #{item_id} 翻译失败，但原文已缓存")
                else:
                    bot_logger.debug(f"Steam更新 #{item_id} 已有有效翻译缓存")
                    
                # 添加小延迟避免API调用过快
                await asyncio.sleep(0.1)
                
            except Exception as e:
                bot_logger.error(f"翻译Steam更新 {update.get('id')} 时发生错误: {e}")
                all_successful = False
        
        return all_successful and processed_count > 0
    
    async def get_latest_steam_update(self) -> Optional[Dict[str, Any]]:
        """
        获取最新的Steam更新数据，严格从缓存获取，确保遵循Redis优先原则。
        """
        try:
            # 优先从统一缓存管理器获取数据
            cached_updates = await hd2_cache_service.get_steam_updates()
            
            if not cached_updates:
                bot_logger.warning("Steam更新缓存为空，数据正在后台更新中...")
                return None
            
            # 获取最新的一条更新
            latest_update = cached_updates[0]
            update_id = str(latest_update.get('id', ''))
            
            if not update_id:
                bot_logger.warning("缓存的Steam更新没有有效ID")
                return None

            cached_item_details = await translation_cache.get_translated_content('steam', update_id)

            # 3. 定义有效缓存的标准
            is_valid = False
            if cached_item_details and cached_item_details.get('metadata'):
                metadata = cached_item_details['metadata']
                has_content = metadata.get('original_title') or metadata.get('original_content')
                # 只要有内容就被认为是有效的，翻译步骤在格式化时处理
                if has_content:
                    is_valid = True

            # 4. 如果缓存无效，则强制刷新；否则返回缓存
            if not is_valid:
                bot_logger.warning(f"最新的缓存Steam更新 #{update_id} 无效（无内容），强制从API刷新。")
                # 刷新缓存后重新尝试获取
                await self.refresh_cache_if_needed()
                # 重新获取刷新后的缓存数据
                cached_updates = await hd2_cache_service.get_steam_updates()
                if cached_updates:
                    return cached_updates[0]
                return None
            else:
                bot_logger.debug(f"发现有效的缓存Steam更新 #{update_id}。")
                return latest_update

        except Exception as e:
            bot_logger.error(f"获取Steam更新数据时发生严重错误: {e}")
            return None
    
    async def format_steam_update_message(self, update: Dict[str, Any]) -> str:
        """
        格式化Steam更新数据为消息（使用缓存翻译）
        
        Args:
            update: Steam更新数据
        
        Returns:
            格式化后的消息
        """
        try:
            if not update:
                return "\n🎮 当前没有Steam更新日志"
            
            # 获取基本信息
            update_id = str(update.get('id', ''))
            
            # 在此阶段，我们信任 get_latest_steam_update 已经确保了缓存的有效性
            # 我们只需要获取完整的翻译详情用于格式化
            cached_translation = await translation_cache.get_translated_content('steam', update_id)

            # 如果即时翻译仍然失败或数据确实为空，则提前退出
            if not cached_translation:
                 bot_logger.warning(f"即使在刷新后，依然无法为 Steam 更新 #{update_id} 找到有效的缓存细节。")
                 return "\n❌ 抱歉，无法获取或翻译最新的Steam更新日志。"

            # 设置默认值
            title = update.get('title', '无标题')
            content = update.get('content', '无内容')
            author = update.get('author', '未知')
            url = update.get('url', '')
            published_time = self._format_time(update.get('publishedAt', ''))
            
            # 优先从完整的缓存细节中获取翻译和元数据
            translated_title = title
            translated_content = content
            
            if cached_translation.get('metadata'):
                metadata = cached_translation['metadata']
                # 如果有翻译则使用翻译，否则使用原文
                translated_title = metadata.get('translated_title') or metadata.get('original_title') or title
                translated_content = metadata.get('translated_content') or metadata.get('original_content') or content
                
                author = metadata.get('author') or author
                published_time = self._format_time(metadata.get('publishedAt')) or published_time
                
                bot_logger.debug(f"使用缓存翻译格式化 Steam 更新 #{update_id}")
            else:
                bot_logger.warning(f"Steam 更新 #{update_id} 的缓存细节中缺少元数据，使用概览信息。")

            # 清理游戏格式标签
            translated_title = clean_game_text(translated_title)
            
            # 智能处理长内容（在清理之前进行，以保留格式信息）
            translated_content = self._smart_truncate_content(translated_content)
            
            # 最后清理并格式化内容
            translated_content = self._format_content_structure(translated_content)
            
            # 构建消息
            message = f"\n🎮 Steam 更新日志 | HELLDIVERS 2\n"
            message += "-------------\n"
            message += f"▎标题: {translated_title}\n"
            message += f"▎作者: {author}\n"
            message += f"▎时间: {published_time}\n"
            message += "-------------\n"
            message += f"▎内容:\n{translated_content}\n"
            message += "-------------"
            
            return message
            
        except Exception as e:
            bot_logger.error(f"格式化Steam更新数据时发生错误: {e}")
            return "\n❌ 数据格式化失败，请稍后重试。"
    
    def _smart_truncate_content(self, content: str, max_length: int = None) -> str:
        """
        智能截取内容，优先提取玩家最感兴趣的部分
        
        Args:
            content: 原始内容
            max_length: 最大长度，None时使用配置值
            
        Returns:
            截取后的内容
        """
        if not content:
            return content
        
        # 使用配置的最大长度
        if max_length is None:
            max_length = settings.STEAM_MAX_CONTENT_LENGTH
            
        # 如果内容较短，直接返回
        if len(content) <= max_length:
            return content
        
        # 提取关键部分（玩家最感兴趣的内容）
        extracted_content = self._extract_key_sections(content)
        
        # 如果提取的内容仍然过长，进行智能截断
        if len(extracted_content) <= max_length:
            return extracted_content
        else:
            return self._truncate_at_boundary(extracted_content, max_length)
    
    def _extract_key_sections(self, content: str) -> str:
        """
        提取Steam更新中玩家最感兴趣的关键部分
        
        Args:
            content: 完整内容
            
        Returns:
            提取的关键内容
        """
        # 直接基于原始内容进行分割，保持更多上下文
        sections = []
        
        # 查找平衡性调整部分
        balancing_start = content.find("⚖️")
        if balancing_start == -1:
            balancing_start = content.lower().find("balancing")
        
        if balancing_start != -1:
            # 找到下一个主要部分的开始
            next_section = content.find("[h2]", balancing_start + 10)
            if next_section == -1:
                balancing_content = content[balancing_start:]
            else:
                balancing_content = content[balancing_start:next_section]
            
            # 清理并限制长度
            cleaned = clean_game_text(balancing_content)
            if len(cleaned) > settings.STEAM_BALANCING_LIMIT:
                cleaned = self._truncate_at_boundary(cleaned, settings.STEAM_BALANCING_LIMIT)
            
            sections.append(f"⚖️ 平衡性调整\n{'-' * 15}\n{cleaned}")
        
        # 查找修复部分
        fixes_start = content.find("🔧")
        if fixes_start == -1:
            fixes_start = content.lower().find("fixes")
        
        if fixes_start != -1:
            # 找到下一个主要部分的开始
            next_section = content.find("[h2]", fixes_start + 10)
            if next_section == -1:
                fixes_content = content[fixes_start:]
            else:
                fixes_content = content[fixes_start:next_section]
            
            # 清理并限制长度
            cleaned = clean_game_text(fixes_content)
            if len(cleaned) > settings.STEAM_FIXES_LIMIT:
                cleaned = self._truncate_at_boundary(cleaned, settings.STEAM_FIXES_LIMIT)
            
            sections.append(f"🔧 修复内容\n{'-' * 15}\n{cleaned}")
        
        # 查找已知问题部分
        issues_start = content.lower().find("known issues")
        if issues_start != -1:
            issues_content = content[issues_start:]
            # 清理并限制长度
            cleaned = clean_game_text(issues_content)
            if len(cleaned) > settings.STEAM_ISSUES_LIMIT:
                cleaned = self._truncate_at_boundary(cleaned, settings.STEAM_ISSUES_LIMIT)
            
            sections.append(f"🐛 已知问题\n{'-' * 15}\n{cleaned}")
        
        if not sections:
            # 如果没有找到关键部分，返回开头部分
            cleaned_full = clean_game_text(content)
            return self._truncate_at_boundary(cleaned_full, 1500) + "\n\n📄 完整内容请查看Steam页面"
        
        # 组合所有部分
        result = "\n\n".join(sections)
        
        # 如果结果太长，只保留前几个部分
        if len(result) > 1800:
            result = "\n\n".join(sections[:settings.STEAM_MAX_SECTIONS-1])
        
        result += "\n\n📄 完整内容请查看Steam页面"
        
        return result
    
    def _format_content_structure(self, content: str) -> str:
        """
        格式化内容结构，改进章节标题和分隔符
        
        Args:
            content: 原始内容
            
        Returns:
            格式化后的内容
        """
        if not content:
            return content
        
        # 先进行基本清理
        formatted = clean_game_text(content)
        
        # 改进章节标题格式
        # 将 "⚖️ **平衡**" 格式化为 "## ⚖️ 平衡"
        formatted = re.sub(r'⚖️\s*\*\*([^*]+)\*\*', r'## ⚖️ \1', formatted)
        # 将 "🔧 **修复**" 格式化为 "## 🔧 修复"
        formatted = re.sub(r'🔧\s*\*\*([^*]+)\*\*', r'## 🔧 \1', formatted)
        
        # 处理独立的修复标题
        formatted = re.sub(r'^\s*🔧\s*修复\s*$', '## 🔧 修复', formatted, flags=re.MULTILINE)
        
        # 将武器名称等双星号标题转换为子标题，但不包括已经转换的主标题
        formatted = re.sub(r'(?<!## )\*\*([^*]+)\*\*', r'**\1**', formatted)
        
        # 确保列表项格式正确
        formatted = re.sub(r'^\*\s*', '* ', formatted, flags=re.MULTILINE)
        
        # 修复错误的格式：* *文本** -> **文本**
        formatted = re.sub(r'\*\s+\*([^*]+)\*\*', r'**\1**', formatted)
        
        # 清理多余的空行
        formatted = re.sub(r'\n\s*\n\s*\n+', '\n\n', formatted)
        
        return formatted.strip()
    
    def _truncate_at_boundary(self, content: str, max_length: int) -> str:
        """
        在合适的边界处截断内容
        
        Args:
            content: 要截断的内容
            max_length: 最大长度
            
        Returns:
            截断后的内容
        """
        if len(content) <= max_length:
            return content
            
        truncate_pos = max_length - 20  # 为后缀预留空间
        
        # 优先在段落边界截断
        last_paragraph = content.rfind('\n\n', 0, truncate_pos)
        if last_paragraph > max_length * 0.6:
            return content[:last_paragraph] + "\n\n..."
        
        # 其次在句子边界截断
        sentence_endings = ['. ', '! ', '? ', '。', '！', '？']
        last_sentence = -1
        for ending in sentence_endings:
            pos = content.rfind(ending, 0, truncate_pos)
            if pos > last_sentence:
                last_sentence = pos + len(ending)
        
        if last_sentence > max_length * 0.7:
            return content[:last_sentence] + "..."
        
        # 最后在单词边界截断
        last_space = content.rfind(' ', 0, truncate_pos)
        if last_space > max_length * 0.8:
            return content[:last_space] + "..."
        
        # 如果找不到合适的边界，直接截断
        return content[:truncate_pos] + "..."
    
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


# 创建全局Steam服务实例
steam_service = SteamService()
