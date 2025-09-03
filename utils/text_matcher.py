# -*- coding: utf-8 -*-
"""
文本相似度匹配工具
用于检测文本内容的变化和相似度
"""
import re
import difflib
from typing import List, Dict, Tuple, Optional
from utils.logger import bot_logger


class TextMatcher:
    """文本相似度匹配器"""
    
    def __init__(self):
        self.similarity_threshold = 0.99  # 99% 相似度阈值
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            相似度分数 (0.0 - 1.0)
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
            
        # 预处理文本：去除多余空白和标点
        clean_text1 = self._clean_text(text1)
        clean_text2 = self._clean_text(text2)
        
        # 使用 SequenceMatcher 计算相似度
        matcher = difflib.SequenceMatcher(None, clean_text1, clean_text2)
        similarity = matcher.ratio()
        
        bot_logger.debug(f"文本相似度: {similarity:.4f}")
        bot_logger.debug(f"文本1: {clean_text1[:100]}...")
        bot_logger.debug(f"文本2: {clean_text2[:100]}...")
        
        return similarity
    
    def is_content_outdated(self, cached_text: str, new_text: str) -> bool:
        """
        检查缓存内容是否已过期
        
        Args:
            cached_text: 缓存中的文本
            new_text: 新获取的文本
            
        Returns:
            True 如果内容已过期，False 如果内容仍然有效
        """
        similarity = self.calculate_similarity(cached_text, new_text)
        is_outdated = similarity < self.similarity_threshold
        
        if is_outdated:
            bot_logger.info(f"检测到过期内容，相似度: {similarity:.4f} < {self.similarity_threshold}")
        else:
            bot_logger.debug(f"内容仍然有效，相似度: {similarity:.4f} >= {self.similarity_threshold}")
            
        return is_outdated
    
    def find_content_changes(self, cached_items: List[Dict], new_items: List[Dict], 
                           content_key: str = 'message') -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        查找内容变化：新增、更新、删除的项目
        
        Args:
            cached_items: 缓存中的项目列表
            new_items: 新获取的项目列表
            content_key: 用于比较的内容字段名
            
        Returns:
            (新增项目, 更新项目, 删除项目)
        """
        cached_dict = {item.get('id', i): item for i, item in enumerate(cached_items)}
        new_dict = {item.get('id', i): item for i, item in enumerate(new_items)}
        
        # 找出新增的项目
        added_items = []
        for item_id, item in new_dict.items():
            if item_id not in cached_dict:
                added_items.append(item)
        
        # 找出更新的项目（ID相同但内容不同）
        updated_items = []
        for item_id, new_item in new_dict.items():
            if item_id in cached_dict:
                cached_content = cached_dict[item_id].get(content_key, '')
                new_content = new_item.get(content_key, '')
                
                if self.is_content_outdated(cached_content, new_content):
                    updated_items.append(new_item)
        
        # 找出删除的项目
        deleted_items = []
        for item_id, item in cached_dict.items():
            if item_id not in new_dict:
                deleted_items.append(item)
        
        bot_logger.info(f"内容变化检测: 新增 {len(added_items)}, 更新 {len(updated_items)}, 删除 {len(deleted_items)}")
        
        return added_items, updated_items, deleted_items
    
    def _clean_text(self, text: str) -> str:
        """
        清理文本，移除影响比较的格式字符
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return ""
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符，保留字母、数字、中文和基本标点
        text = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:\'"-]', '', text)
        
        return text.strip().lower()


# 创建全局文本匹配器实例
text_matcher = TextMatcher()

