# task_scheduler.py
import asyncio
import time
from typing import Optional

class TaskScheduler:
    """任务调度器 - 支持高并发"""

    def __init__(self,
                 target_count: int,
                 concurrent_workers: int = 50,
                 rate_limit_per_minute: int = 100):
        self.target_count = target_count
        self.concurrent_workers = concurrent_workers
        self.rate_limit = rate_limit_per_minute

        # 统计信息
        self.completed = 0
        self.failed = 0
        self.start_time = None

        # 限流令牌
        self.rate_tokens = 0
        self.rate_lock = asyncio.Lock()

    async def run(self, url: str):
        """运行调度任务"""
        from core.browser_manager import BrowserManager
        from core.answer_generator import AnswerGenerator
        from core.captcha_solver import CaptchaSolver
        from core.submitter import QuestionnaireSubmitter

        self.start_time = time.time()

        # 初始化浏览器池
        print(f"正在初始化 {self.concurrent_workers} 个浏览器实例...")
        browser_manager = BrowserManager(pool_size=self.concurrent_workers)
        await browser_manager.initialize()
        print("浏览器池初始化完成")

        # 创建任务队列
        tasks_queue = asyncio.Queue()
        for i in range(self.target_count):
            await tasks_queue.put(i)

        # 启动工作协程
        workers = [
            asyncio.create_task(
                self._worker(tasks_queue, browser_manager, worker_id, url)
            )
            for worker_id in range(self.concurrent_workers)
        ]

        # 启动限流器
        rate_limiter = asyncio.create_task(self._rate_limiter())

        # 启动监控器
        monitor = asyncio.create_task(self._monitor())

        # 等待所有任务完成
        await tasks_queue.join()

        # 清理
        for w in workers:
            w.cancel()
        rate_limiter.cancel()
        monitor.cancel()

        await browser_manager.cleanup()

        self._print_summary()

    async def _worker(self, queue: asyncio.Queue, browser_manager, worker_id: int, url: str):
        """工作协程"""
        from core.answer_generator import AnswerGenerator
        from core.captcha_solver import CaptchaSolver
        from core.submitter import QuestionnaireSubmitter

        answer_generator = AnswerGenerator()
        captcha_solver = CaptchaSolver(solver_type='behavioral')
        submitter = QuestionnaireSubmitter(
            url=url,
            answer_generator=answer_generator,
            captcha_solver=captcha_solver,
            browser_manager=browser_manager
        )

        while True:
            try:
                # 等待限流许可
                await self._acquire_rate_limit()

                # 获取任务
                task_id = await queue.get()

                # 执行提交
                result = await submitter.submit_one()

                if result['status'] == 'success':
                    self.completed += 1
                    print(f"[Worker-{worker_id}] Task {task_id} 成功")
                else:
                    self.failed += 1
                    print(f"[Worker-{worker_id}] Task {task_id} 失败: {result.get('reason', 'unknown')}")

                    # 验证码失败的任务可以选择重试
                    # if result.get('reason') == 'captcha_failed':
                    #     await queue.put(task_id)  # 重新入队

                queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Worker-{worker_id}] 异常: {e}")
                queue.task_done()

    async def _rate_limiter(self):
        """流量限制器 - 防止请求过快"""
        interval = 60 / self.rate_limit  # 每个请求的时间间隔

        while True:
            await asyncio.sleep(interval)
            # 释放一个许可
            async with self.rate_lock:
                self.rate_tokens += 1

    async def _acquire_rate_limit(self):
        """获取限流许可"""
        while True:
            async with self.rate_lock:
                if self.rate_tokens > 0:
                    self.rate_tokens -= 1
                    break
            await asyncio.sleep(0.1)

    async def _monitor(self):
        """监控协程 - 实时显示进度"""
        while True:
            await asyncio.sleep(5)
            elapsed = time.time() - self.start_time
            total = self.completed + self.failed
            rate = total / elapsed if elapsed > 0 else 0

            print(f"\n{'='*60}")
            print(f"进度: {total}/{self.target_count} "
                  f"({total/self.target_count*100:.1f}%)")
            print(f"成功: {self.completed} | 失败: {self.failed}")
            print(f"速率: {rate:.2f} 份/秒")
            if rate > 0:
                print(f"预计剩余时间: {(self.target_count-total)/rate/60:.1f} 分钟")
            print(f"{'='*60}\n")

    def _print_summary(self):
        """打印总结"""
        elapsed = time.time() - self.start_time
        print(f"\n{'='*60}")
        print(f"任务完成!")
        print(f"总数: {self.target_count}")
        print(f"成功: {self.completed}")
        print(f"失败: {self.failed}")
        print(f"总耗时: {elapsed/60:.2f} 分钟")
        if elapsed > 0:
            print(f"平均速率: {self.completed/elapsed:.2f} 份/秒")
        print(f"{'='*60}")
