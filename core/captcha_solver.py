# captcha_solver.py
import asyncio
import random
from playwright.async_api import Page

class CaptchaSolver:
    """验证码解决器 - 处理阿里云验证码"""

    def __init__(self, solver_type='behavioral'):
        """
        solver_type:
        - 'manual': 人工打码平台 (如超级鹰、打码兔)
        - 'ai': AI识别 (准确率较低)
        - 'behavioral': 行为模拟 (最安全但成功率不稳定)
        """
        self.solver_type = solver_type

    async def solve_aliyun_captcha(self, page: Page) -> bool:
        """解决阿里云滑块验证码"""

        if self.solver_type == 'behavioral':
            return await self._solve_by_behavior(page)
        elif self.solver_type == 'manual':
            return await self._solve_by_manual_service(page)
        else:
            return await self._solve_by_ai(page)

    async def _solve_by_behavior(self, page: Page) -> bool:
        """通过模拟真实人类行为解决验证码"""
        try:
            # 等待验证码出现
            slider = await page.wait_for_selector('.nc_iconfont', timeout=5000)

            # 获取滑块和轨道信息
            slider_box = await slider.bounding_box()
            track_box = await page.locator('.nc_wrapper').bounding_box()

            # 计算需要滑动的距离
            distance = track_box['width'] - slider_box['width']

            # 生成人类化的滑动轨迹（贝塞尔曲线）
            track = self._generate_human_track(distance)

            # 执行滑动
            await slider.hover()
            await page.mouse.down()

            for point in track:
                await page.mouse.move(
                    slider_box['x'] + point,
                    slider_box['y'],
                    steps=random.randint(5, 10)
                )
                await asyncio.sleep(random.uniform(0.001, 0.003))

            await asyncio.sleep(random.uniform(0.2, 0.5))
            await page.mouse.up()

            # 等待验证结果
            await asyncio.sleep(2)

            # 检查是否通过
            success_element = await page.query_selector('.nc_iconfont.nc_iconfont-ok')
            return success_element is not None

        except Exception as e:
            print(f"验证码解决失败: {e}")
            return False

    def _generate_human_track(self, distance: float) -> list:
        """生成类人化的滑动轨迹"""
        track = []
        current = 0
        mid = distance * 0.8  # 80%处开始减速

        # 加速阶段
        while current < mid:
            v = random.uniform(5, 8)
            current += v
            track.append(current)

        # 减速阶段
        while current < distance:
            v = random.uniform(2, 4)
            current += v
            track.append(current)

        # 添加小幅回退和修正（真实人类行为）
        for i in range(random.randint(1, 3)):
            track.append(track[-1] - random.uniform(1, 3))
            track.append(track[-1] + random.uniform(1, 2))

        return track

    async def _solve_by_manual_service(self, page: Page) -> bool:
        """使用人工打码平台"""
        # 截图发送到打码平台
        # 等待打码结果
        # 这里需要集成具体的打码平台API
        print("人工打码服务未实现")
        return False

    async def _solve_by_ai(self, page: Page) -> bool:
        """使用AI识别"""
        print("AI识别服务未实现")
        return False
