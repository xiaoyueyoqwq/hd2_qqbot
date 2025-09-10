# -*- coding: utf-8 -*-
"""
Helldivers 2 API 管理器
负责统一管理 API 请求头和 API 调用
"""
import aiohttp
import asyncio
import sys
import os
from typing import Dict, Any, Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import bot_logger
from utils.api_retry import APIRetryMixin
from utils.config import settings

class HD2ApiManager(APIRetryMixin):
    """Helldivers 2 API 管理器"""
    
    def __init__(self):
        super().__init__()
        self.base_url = settings.HD2_API_BASE_URL
        self.default_headers = {
            "User-Agent": settings.HD2_API_USER_AGENT,
            "X-Super-Client": settings.HD2_API_CLIENT,
            "X-Super-Contact": settings.HD2_API_CONTACT,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.timeout = aiohttp.ClientTimeout(total=settings.HD2_API_TIMEOUT)
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        发送 GET 请求到 Helldivers 2 API（带重试机制）
        
        Args:
            endpoint: API 端点路径
            params: 查询参数
        
        Returns:
            API 响应的 JSON 数据，失败时返回 None
        """
        url = f"{self.base_url}{endpoint}"
        
        async def _api_call():
            async with aiohttp.ClientSession(
                headers=self.default_headers,
                timeout=self.timeout
            ) as session:
                bot_logger.debug(f"发送 API 请求: {url}")
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_logger.debug(f"API 请求成功: {url}")
                        return data
                    else:
                        # 返回带状态码的响应对象，让重试机制处理
                        class APIResponse:
                            def __init__(self, status):
                                self.status = status
                        return APIResponse(response.status)
        
        # 使用重试机制调用API，使用配置的重试参数
        result = await self.retry_api_call(
            _api_call,
            base_delay=settings.HD2_API_RETRY_BASE_DELAY,
            max_delay=settings.HD2_API_RETRY_MAX_DELAY,
            increment=settings.HD2_API_RETRY_INCREMENT
        )
        
        # 如果结果是APIResponse对象，说明请求失败
        if hasattr(result, 'status'):
            return None
            
        return result

# 全局 API 管理器实例
hd2_api = HD2ApiManager()
