# anti_detection.py
from playwright.async_api import Page

class AntiDetectionSystem:
    """反检测系统 - 多维度对抗"""

    @staticmethod
    def get_evasion_config():
        """获取反检测配置"""
        return {
            # 1. 浏览器指纹层
            'browser_fingerprint': {
                'canvas': 'randomize',  # Canvas指纹随机化
                'webgl': 'randomize',   # WebGL指纹随机化
                'audio': 'randomize',   # AudioContext指纹随机化
                'fonts': 'subset',      # 字体列表随机子集
                'screen': 'randomize',  # 屏幕分辨率随机
                'timezone': ['Asia/Shanghai', 'Asia/Chongqing'],
                'language': ['zh-CN', 'zh'],
                'platform': ['Win32', 'MacIntel'],
            },

            # 2. 行为特征层
            'behavioral': {
                'mouse_movement': True,      # 启用鼠标轨迹模拟
                'scroll_behavior': True,     # 启用滚动行为
                'typing_speed': (50, 150),   # 打字速度范围(ms/字符)
                'hesitation': True,          # 模拟犹豫（返回修改）
                'pause_reading': True,       # 阅读停顿
            },

            # 3. 时间特征层
            'timing': {
                'page_load_wait': (2, 5),          # 页面加载后等待
                'question_think_time': (1, 8),     # 每题思考时间
                'text_input_time': (5, 20),        # 文本输入时间
                'submit_hesitation': (1, 3),       # 提交前犹豫
                'total_time_range': (60, 300),     # 总时长范围(秒)
            },

            # 4. 网络层
            'network': {
                'proxy_rotation': True,      # 代理轮换
                'dns_over_https': True,      # DoH
                'http2': True,               # HTTP/2支持
                'tls_fingerprint': 'chrome', # TLS指纹
            }
        }

    @staticmethod
    async def inject_stealth_scripts(page: Page):
        """注入反检测脚本"""
        await page.add_init_script("""
            // 1. 隐藏webdriver特征
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });

            // 2. 模拟Chrome运行环境
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // 3. 修改navigator属性
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', filename: 'internal-nacl-plugin'}
                ]
            });

            // 4. 覆盖permissions查询
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({state: Notification.permission}) :
                    originalQuery(parameters)
            );

            // 5. Canvas指纹噪声
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const dataURL = originalToDataURL.apply(this, arguments);
                // 添加微小噪声
                return dataURL;
            };

            // 6. WebGL指纹干扰
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.apply(this, arguments);
            };
        """)
