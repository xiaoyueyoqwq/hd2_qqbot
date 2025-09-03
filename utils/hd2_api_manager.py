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

class HD2ApiManager:
    """Helldivers 2 API 管理器"""
    
    def __init__(self):
        self.base_url = "https://api.helldivers2.dev"
        self.default_headers = {
            "User-Agent": "hd2_qqbot/1.0",
            "X-Super-Client": "hd2_qqbot",
            "X-Super-Contact": "xiaoyueyoqwq@vaiiya.org",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.timeout = aiohttp.ClientTimeout(total=30)
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        发送 GET 请求到 Helldivers 2 API
        
        Args:
            endpoint: API 端点路径
            params: 查询参数
        
        Returns:
            API 响应的 JSON 数据，失败时返回 None
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
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
                    elif response.status == 429:
                        retry_after = response.headers.get('Retry-After', '10')
                        bot_logger.warning(f"API 请求频率限制: {url}, 建议 {retry_after} 秒后重试")
                        return None
                    else:
                        bot_logger.warning(f"API 请求失败: {url}, 状态码: {response.status}")
                        return None
                        
        except aiohttp.ClientError as e:
            bot_logger.error(f"API 请求异常: {url}, 错误: {e}")
            return None
        except asyncio.TimeoutError:
            bot_logger.error(f"API 请求超时: {url}")
            return None
        except Exception as e:
            bot_logger.error(f"API 请求未知错误: {url}, 错误: {e}")
            return None

# 全局 API 管理器实例
hd2_api = HD2ApiManager()
