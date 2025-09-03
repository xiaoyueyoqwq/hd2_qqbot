# -*- coding: utf-8 -*-
"""
翻译重试队列管理器
处理翻译失败后的延迟重试，避免API拥挤访问
"""
import sys
import os
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta

# 确保正确的路径设置
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)

# 添加项目根目录到路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import bot_logger
from utils.rotation_manager import RotationManager, TimeBasedStrategy
from utils.translation_cache import translation_cache


@dataclass
class RetryTask:
    """重试任务数据结构"""
    content_type: str  # 内容类型，如 'dispatches'
    item_id: str      # 项目ID
    original_text: str  # 原文
    metadata: Dict[str, Any]  # 元数据
    retry_count: int = 0  # 重试次数
    created_at: datetime = None  # 创建时间
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class TranslationRetryQueue:
    """翻译重试队列管理器"""
    
    def __init__(self):
        self.retry_tasks: List[RetryTask] = []
        self.rotation_manager = RotationManager()
        self.is_initialized = False
        self.max_retry_count = 5  # 最大重试次数
        self.retry_interval = 60  # 重试间隔（秒）
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """初始化重试队列轮转系统"""
        if self.is_initialized:
            bot_logger.debug("翻译重试队列已初始化，跳过重复初始化")
            return
        
        bot_logger.info("🔄 初始化翻译重试队列系统...")
        
        try:
            # 注册重试队列处理任务
            await self._register_retry_rotation()
            
            self.is_initialized = True
            bot_logger.info("✅ 翻译重试队列系统初始化完成")
            
        except Exception as e:
            bot_logger.error(f"❌ 翻译重试队列系统初始化失败: {e}")
            raise
    
    async def _register_retry_rotation(self) -> None:
        """注册重试队列处理轮转任务"""
        try:
            async def retry_handler():
                """重试队列处理器"""
                try:
                    await self._process_retry_queue()
                except Exception as e:
                    bot_logger.error(f"❌ 处理翻译重试队列时发生错误: {e}")
            
            # 每分钟检查一次重试队列
            strategy = TimeBasedStrategy(interval=60)
            
            await self.rotation_manager.register_rotation(
                name="translation_retry_queue",
                handler=retry_handler,
                strategy=strategy,
                start_immediately=False  # 不立即开始，等待有任务时再启动
            )
            
            bot_logger.info("✅ 翻译重试队列轮转任务已注册")
            
        except Exception as e:
            bot_logger.error(f"❌ 注册翻译重试队列轮转失败: {e}")
    
    async def add_retry_task(self, content_type: str, item_id: str, original_text: str, 
                           metadata: Dict[str, Any]) -> None:
        """
        添加重试任务到队列
        
        Args:
            content_type: 内容类型
            item_id: 项目ID
            original_text: 原文
            metadata: 元数据
        """
        async with self._lock:
            # 检查是否已存在相同的任务
            existing_task = None
            for task in self.retry_tasks:
                if task.content_type == content_type and task.item_id == item_id:
                    existing_task = task
                    break
            
            if existing_task:
                # 更新现有任务
                existing_task.original_text = original_text
                existing_task.metadata = metadata
                existing_task.retry_count += 1
                bot_logger.debug(f"更新重试任务: {content_type}:{item_id} (第{existing_task.retry_count}次)")
            else:
                # 创建新任务
                task = RetryTask(
                    content_type=content_type,
                    item_id=item_id,
                    original_text=original_text,
                    metadata=metadata
                )
                self.retry_tasks.append(task)
                bot_logger.info(f"添加翻译重试任务: {content_type}:{item_id}")
            
            # 如果队列之前为空，启动轮转任务
            if len(self.retry_tasks) == 1:
                try:
                    await self.rotation_manager.start_rotation("translation_retry_queue")
                    bot_logger.debug("启动翻译重试队列处理")
                except Exception as e:
                    bot_logger.warning(f"启动翻译重试队列失败: {e}")
    
    async def _process_retry_queue(self) -> None:
        """处理重试队列"""
        if not self.retry_tasks:
            # 队列为空，停止轮转
            try:
                await self.rotation_manager.stop_rotation("translation_retry_queue")
                bot_logger.debug("翻译重试队列为空，停止处理")
            except Exception:
                pass  # 忽略停止失败的错误
            return
        
        async with self._lock:
            tasks_to_process = []
            tasks_to_remove = []
            
            current_time = datetime.now()
            
            for task in self.retry_tasks:
                # 检查任务是否应该被处理（1分钟间隔）
                time_since_created = current_time - task.created_at
                if time_since_created >= timedelta(seconds=self.retry_interval):
                    if task.retry_count < self.max_retry_count:
                        tasks_to_process.append(task)
                    else:
                        # 超过最大重试次数，移除任务
                        tasks_to_remove.append(task)
                        bot_logger.warning(f"翻译任务 {task.content_type}:{task.item_id} 超过最大重试次数，放弃重试")
            
            # 移除超时任务
            for task in tasks_to_remove:
                self.retry_tasks.remove(task)
        
        # 处理需要重试的任务
        if tasks_to_process:
            bot_logger.info(f"开始处理 {len(tasks_to_process)} 个翻译重试任务...")
            await self._process_retry_tasks(tasks_to_process)
    
    async def _process_retry_tasks(self, tasks: List[RetryTask]) -> None:
        """
        处理重试任务列表
        
        Args:
            tasks: 需要处理的任务列表
        """
        # 导入翻译服务（避免循环导入）
        try:
            from core.news import TranslationService
            translation_service = TranslationService()
        except ImportError:
            bot_logger.error("无法导入翻译服务，跳过重试任务处理")
            return
        
        successful_tasks = []
        failed_tasks = []
        
        for task in tasks:
            try:
                bot_logger.info(f"重试翻译任务: {task.content_type}:{task.item_id} (第{task.retry_count + 1}次尝试)")
                
                # 尝试翻译
                translated_text = await translation_service.translate_text(
                    task.original_text, "zh", max_retries=1  # 重试队列中只尝试一次
                )
                
                # 检查翻译是否成功
                if translated_text and translated_text != task.original_text:
                    # 翻译成功，存储到缓存
                    await translation_cache.store_translated_content(
                        task.content_type, task.item_id, task.original_text, 
                        translated_text, task.metadata
                    )
                    successful_tasks.append(task)
                    bot_logger.info(f"重试翻译成功: {task.content_type}:{task.item_id}")
                else:
                    # 翻译失败
                    task.retry_count += 1
                    task.created_at = datetime.now()  # 重置时间，等待下次重试
                    failed_tasks.append(task)
                    bot_logger.warning(f"重试翻译失败: {task.content_type}:{task.item_id}")
                
                # 添加延迟，避免API调用过快
                await asyncio.sleep(2)
                
            except Exception as e:
                bot_logger.error(f"处理重试任务 {task.content_type}:{task.item_id} 时发生错误: {e}")
                task.retry_count += 1
                task.created_at = datetime.now()
                failed_tasks.append(task)
        
        # 从队列中移除成功的任务
        async with self._lock:
            for task in successful_tasks:
                if task in self.retry_tasks:
                    self.retry_tasks.remove(task)
        
        bot_logger.info(f"重试任务处理完成: 成功 {len(successful_tasks)} 个，失败 {len(failed_tasks)} 个")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "total_tasks": len(self.retry_tasks),
            "tasks_by_type": {},
            "is_initialized": self.is_initialized
        }
    
    async def stop(self) -> None:
        """停止重试队列系统"""
        try:
            await self.rotation_manager.stop_rotation("translation_retry_queue")
            self.retry_tasks.clear()
            self.is_initialized = False
            bot_logger.info("✅ 翻译重试队列系统已停止")
        except Exception as e:
            bot_logger.error(f"❌ 停止翻译重试队列系统失败: {e}")


# 创建全局翻译重试队列实例
translation_retry_queue = TranslationRetryQueue()
