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
    base_delay: float = 3.0,
    max_delay: float = 30.0,
    increment: float = 3.0,
    jitter: bool = True,
    retry_on_status: Optional[list] = None
) -> Any:
    """
    使用线性增量退避策略重试函数调用

    Args:
        func: 要重试的异步函数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        increment: 每次重试增加的延迟时间（秒）
        jitter: 是否添加随机抖动
        retry_on_status: 需要重试的HTTP状态码列表，None表示重试所有非200状态码

    Returns:
        函数调用结果，或在持续失败后返回None
    """
    if retry_on_status is None:
        retry_on_status = [429, 500, 502, 503, 504]  # 默认重试的状态码

    last_exception = None
    attempt = 0
    current_delay = base_delay

    while True:  # 无限重试
        attempt += 1
        try:
            result = await func()

            # 如果结果是HTTP响应对象，检查状态码
            if hasattr(result, 'status'):
                if result.status == 200:
                    return result
                elif result.status in retry_on_status:
                    delay = current_delay
                    if jitter:
                        delay += random.uniform(0, delay * 0.1)  # 添加10%的随机抖动

                    bot_logger.warning(
                        f"API请求失败 (第{attempt}次尝试): 状态码 {result.status}，"
                        f"{delay:.1f}秒后重试..."
                    )
                    await asyncio.sleep(delay)
                    current_delay = min(current_delay + increment, max_delay)
                    continue
                else:
                    # 不需要重试的状态码
                    bot_logger.error(f"API请求失败: 状态码 {result.status} (不重试)")
                    return None
            else:
                # 非HTTP响应对象，直接返回
                return result

        except asyncio.TimeoutError as e:
            last_exception = e
            delay = current_delay
            if jitter:
                delay += random.uniform(0, delay * 0.1)

            bot_logger.warning(f"API请求超时 (第{attempt}次尝试)，{delay:.1f}秒后重试...")
            await asyncio.sleep(delay)
            current_delay = min(current_delay + increment, max_delay)
            continue

        except Exception as e:
            last_exception = e
            delay = current_delay
            if jitter:
                delay += random.uniform(0, delay * 0.1)

            bot_logger.warning(f"API请求异常 (第{attempt}次尝试): {e}，{delay:.1f}秒后重试...")
            await asyncio.sleep(delay)
            current_delay = min(current_delay + increment, max_delay)
            continue

    return None # 理论上不会到达


class APIRetryMixin:
    """
    API重试混入类
    为服务类提供统一的重试机制
    """

    def __init__(self):
        self.default_retry_config = {
            'base_delay': 3.0,
            'max_delay': 30.0,
            'increment': 3.0,
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
