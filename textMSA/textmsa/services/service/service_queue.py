"""
服务执行队列管理模块

控制最大并发执行数，超出限制的任务将排队等待。
使用"完成回调"模式：任务完成时自动从队列取出下一个执行，零延迟。
"""
from __future__ import annotations

import queue
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

from textmsa.logging_config import get_logger

logger = get_logger(__name__)

# 默认最大并发执行数
DEFAULT_MAX_CONCURRENT = 3


class ServiceQueue:
    """
    线程安全的服务执行队列。

    使用计数器 + 锁控制最大并发数，超出部分排入 Queue。
    任务完成时通过回调自动取出下一个排队任务执行，无需后台轮询线程。
    """

    def __init__(self, max_concurrent: int = DEFAULT_MAX_CONCURRENT) -> None:
        self._max_concurrent = max_concurrent
        self._queue: queue.Queue[tuple[Future, Callable, tuple, dict]] = queue.Queue()
        self._running_count = 0
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent,
            thread_name_prefix="service_queue_worker",
        )
        logger.info(f"ServiceQueue 已初始化: max_concurrent={max_concurrent}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        """
        提交任务到队列。

        如果当前运行数 < max_concurrent 则立即执行，否则排队等待。
        排队的任务会在前序任务完成时自动被取出执行（零延迟）。

        Args:
            fn: 要执行的可调用对象
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Future 对象
        """
        future: Future = Future()

        with self._lock:
            if self._running_count < self._max_concurrent:
                # 有空闲槽位，立即执行
                self._running_count += 1
                self._executor.submit(self._run_task, future, fn, args, kwargs)
                logger.info(
                    f"[ServiceQueue] 任务立即执行, "
                    f"当前运行: {self._running_count}/{self._max_concurrent}, "
                    f"排队中: {self._queue.qsize()}"
                )
            else:
                # 无空闲槽位，排入队列
                self._queue.put((future, fn, args, kwargs))
                logger.info(
                    f"[ServiceQueue] 任务已排队等待, "
                    f"当前运行: {self._running_count}/{self._max_concurrent}, "
                    f"排队中: {self._queue.qsize()}"
                )

        return future

    def get_queue_status(self) -> dict[str, Any]:
        """返回队列状态信息。"""
        with self._lock:
            return {
                "max_concurrent": self._max_concurrent,
                "running_count": self._running_count,
                "queued_count": self._queue.qsize(),
            }

    def shutdown(self, wait: bool = True) -> None:
        """优雅关闭队列。"""
        logger.info("[ServiceQueue] 正在关闭...")
        self._executor.shutdown(wait=wait)
        logger.info("[ServiceQueue] 已关闭")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_task(
        self,
        future: Future,
        fn: Callable,
        args: tuple,
        kwargs: dict,
    ) -> None:
        """执行任务，完成后通过回调自动调度下一个排队任务。"""
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)
        finally:
            self._on_task_complete()

    def _on_task_complete(self) -> None:
        """
        任务完成回调：释放槽位，并立即从队列中取出下一个任务执行。

        这种设计的优势：
        - 零延迟：排队任务在前序任务完成的瞬间就被调度，无需等待轮询间隔
        - 无后台线程：不需要额外的调度线程持续运行
        - 线程安全：所有状态变更都在锁内完成
        """
        next_item = None
        with self._lock:
            self._running_count -= 1
            try:
                next_item = self._queue.get_nowait()
                self._running_count += 1  # 立即占用槽位
            except queue.Empty:
                pass

        if next_item is not None:
            future, fn, args, kwargs = next_item
            logger.info(
                f"[ServiceQueue] 自动调度排队任务, "
                f"当前运行: {self._running_count}/{self._max_concurrent}, "
                f"剩余排队: {self._queue.qsize()}"
            )
            self._executor.submit(self._run_task, future, fn, args, kwargs)
        else:
            logger.debug(
                f"[ServiceQueue] 任务完成, 队列为空, "
                f"当前运行: {self._running_count}/{self._max_concurrent}"
            )
