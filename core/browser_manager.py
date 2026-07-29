# browser_manager.py
from playwright.async_api import async_playwright, Browser, BrowserContext
import asyncio
import random

class BrowserManager:
    """浏览器池管理器"""

    def __init__(self, pool_size=10):
        self.pool_size = pool_size
        self.browsers = []
        self.contexts = []
        self.playwright = None

    async def initialize(self):
        """初始化浏览器池"""
        self.playwright = await async_playwright().start()

        for i in range(self.pool_size):
            # 启动浏览器
            browser = await self.playwright.chromium.launch(
                headless=False,  # 开发环境使用False便于调试，生产环境使用True
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            # 创建上下文（带指纹伪装）
            context = await browser.new_context(
                viewport={'width': random.randint(1366, 1920),
                         'height': random.randint(768, 1080)},
                user_agent=self._get_random_ua(),
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
                # 代理设置
                proxy={
                    'server': self._get_proxy(),
                } if self._get_proxy() else None
            )

            # 反检测脚本注入 - 增强版
            await context.add_init_script("""
                // 1. 隐藏webdriver属性
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // 2. 模拟Chrome对象
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };

                // 3. 模拟插件
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: 'Chrome PDF Plugin'},
                        {name: 'Chrome PDF Viewer'},
                        {name: 'Native Client'}
                    ]
                });

                // 4. 模拟语言
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en-US', 'en']
                });

                // 5. 隐藏自动化相关的window属性
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

                // 6. 覆盖权限查询（有些验证会检测）
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // 7. 模拟真实的鼠标移动
                // 注入一个全局函数用于模拟更真实的用户行为
                window.__simulateHumanBehavior = true;
            """)

            self.browsers.append(browser)
            self.contexts.append(context)

    def _get_random_ua(self) -> str:
        """获取随机User-Agent"""
        uas = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        return random.choice(uas)

    def _get_proxy(self) -> str:
        """从代理池获取代理"""
        # 这里应该连接到代理池服务
        # 暂时返回None，不使用代理
        return None

    async def get_context(self) -> BrowserContext:
        """获取可用的浏览器上下文"""
        return random.choice(self.contexts)

    async def cleanup(self):
        """清理资源"""
        for browser in self.browsers:
            await browser.close()
        if self.playwright:
            await self.playwright.stop()
