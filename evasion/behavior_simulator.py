# behavior_simulator.py
import asyncio
import random
from playwright.async_api import Page

class BehaviorSimulator:
    """人类行为模拟器"""

    @staticmethod
    async def simulate_mouse_movement(page: Page, target_selector: str):
        """模拟自然的鼠标移动"""
        target = await page.query_selector(target_selector)
        if not target:
            return

        box = await target.bounding_box()

        # 当前鼠标位置（随机起点）
        current_x = random.randint(100, 500)
        current_y = random.randint(100, 500)

        # 目标位置（添加随机偏移）
        target_x = box['x'] + box['width'] / 2 + random.uniform(-5, 5)
        target_y = box['y'] + box['height'] / 2 + random.uniform(-5, 5)

        # 生成贝塞尔曲线路径
        path = BehaviorSimulator._bezier_curve(
            (current_x, current_y),
            (target_x, target_y),
            num_points=random.randint(30, 50)
        )

        # 沿路径移动
        for x, y in path:
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.001, 0.005))

        # 小幅抖动
        for _ in range(random.randint(1, 3)):
            await page.mouse.move(
                target_x + random.uniform(-2, 2),
                target_y + random.uniform(-2, 2)
            )
            await asyncio.sleep(0.01)

    @staticmethod
    def _bezier_curve(start, end, num_points):
        """生成贝塞尔曲线路径"""
        # 生成控制点
        ctrl1_x = start[0] + (end[0] - start[0]) * random.uniform(0.2, 0.4)
        ctrl1_y = start[1] + (end[1] - start[1]) * random.uniform(-0.2, 0.2)
        ctrl2_x = start[0] + (end[0] - start[0]) * random.uniform(0.6, 0.8)
        ctrl2_y = start[1] + (end[1] - start[1]) * random.uniform(-0.2, 0.2)

        points = []
        for i in range(num_points):
            t = i / num_points
            # 三次贝塞尔曲线公式
            x = (1-t)**3 * start[0] + \
                3 * (1-t)**2 * t * ctrl1_x + \
                3 * (1-t) * t**2 * ctrl2_x + \
                t**3 * end[0]
            y = (1-t)**3 * start[1] + \
                3 * (1-t)**2 * t * ctrl1_y + \
                3 * (1-t) * t**2 * ctrl2_y + \
                t**3 * end[1]
            points.append((x, y))

        return points

    @staticmethod
    async def simulate_typing(page: Page, selector: str, text: str):
        """模拟自然的打字行为"""
        element = await page.query_selector(selector)
        if not element:
            return

        await element.click()

        for char in text:
            await page.keyboard.type(char)
            # 打字速度变化
            delay = random.gauss(100, 30)  # 平均100ms，标准差30ms
            delay = max(50, min(200, delay))  # 限制范围
            await asyncio.sleep(delay / 1000)

            # 偶尔打错字然后删除
            if random.random() < 0.05:  # 5%概率
                await page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.1, 0.3))

    @staticmethod
    async def simulate_reading(page: Page, duration: float):
        """模拟阅读行为（滚动+停顿）"""
        scroll_times = random.randint(2, 5)
        time_per_scroll = duration / scroll_times

        for _ in range(scroll_times):
            # 滚动
            scroll_amount = random.randint(100, 300)
            await page.evaluate(f'window.scrollBy(0, {scroll_amount})')

            # 阅读停顿
            await asyncio.sleep(time_per_scroll)
