# -*- coding: utf-8 -*-
"""
API重试机制工具
提供指数退避重试功能，处理速率限制等问题
"""
import asyncio
import random
from typing import Optional, Callable, Any
from utils.logger import bot_logger


async def exponential_backoff_retry(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_on_status: Optional[list] = None
) -> Any:
    """
    使用指数退避策略重试函数调用
    
    Args:
        func: 要重试的异步函数
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        backoff_factor: 退避倍数
        jitter: 是否添加随机抖动
        retry_on_status: 需要重试的HTTP状态码列表，None表示重试所有非200状态码
        
    Returns:
        函数调用结果，失败时返回None
    """
    if retry_on_status is None:
        retry_on_status = [429, 500, 502, 503, 504]  # 默认重试的状态码
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            result = await func()
            
            # 如果结果是HTTP响应对象，检查状态码
            if hasattr(result, 'status'):
                if result.status == 200:
                    return result
                elif result.status in retry_on_status:
                    if attempt < max_retries:
                        delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                        if jitter:
                            delay += random.uniform(0, delay * 0.1)  # 添加10%的随机抖动
                        
                        bot_logger.warning(
                            f"API请求失败 (第{attempt+1}次尝试): 状态码 {result.status}，"
                            f"{delay:.1f}秒后重试..."
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        bot_logger.error(f"API请求最终失败: 状态码 {result.status}")
                        return None
                else:
                    # 不需要重试的状态码
                    bot_logger.error(f"API请求失败: 状态码 {result.status} (不重试)")
                    return None
            else:
                # 非HTTP响应对象，直接返回
                return result
                
        except asyncio.TimeoutError as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                if jitter:
                    delay += random.uniform(0, delay * 0.1)
                
                bot_logger.warning(f"API请求超时 (第{attempt+1}次尝试)，{delay:.1f}秒后重试...")
                await asyncio.sleep(delay)
                continue
            else:
                bot_logger.error("API请求最终超时")
                return None
                
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                if jitter:
                    delay += random.uniform(0, delay * 0.1)
                
                bot_logger.warning(f"API请求异常 (第{attempt+1}次尝试): {e}，{delay:.1f}秒后重试...")
                await asyncio.sleep(delay)
                continue
            else:
                bot_logger.error(f"API请求最终失败: {e}")
                return None
    
    return None


class APIRetryMixin:
    """
    API重试混入类
    为服务类提供统一的重试机制
    """
    
    def __init__(self):
        self.default_retry_config = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 60.0,
            'backoff_factor': 2.0,
            'jitter': True,
            'retry_on_status': [429, 500, 502, 503, 504]
        }
    
    async def retry_api_call(self, func: Callable, **retry_kwargs) -> Any:
        """
        使用默认配置重试API调用
        
        Args:
            func: 要重试的异步函数
            **retry_kwargs: 覆盖默认重试配置的参数
            
        Returns:
            函数调用结果
        """
        config = self.default_retry_config.copy()
        config.update(retry_kwargs)
        
        return await exponential_backoff_retry(func, **config)
