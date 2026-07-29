# selenium_captcha_handler.py
"""
使用 Selenium + undetected-chromedriver 处理阿里云验证码
"""
import asyncio
import time
import random
from typing import Optional

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth


class SeleniumCaptchaHandler:
    """使用 Selenium 处理阿里云验证码"""

    def __init__(self):
        self.driver = None

    def initialize_driver(self):
        """初始化 undetected-chromedriver"""
        print("  [INFO] 正在初始化 undetected-chromedriver...")

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")

        # 启用浏览器日志
        options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

        try:
            # undetected-chromedriver 会自动下载匹配的 ChromeDriver
            # version_main 参数让它自动检测 Chrome 版本
            self.driver = uc.Chrome(
                options=options,
                headless=False,
                use_subprocess=False,
                version_main=None,  # 自动检测
            )

            print("  [INFO] undetected-chromedriver 初始化完成")

        except Exception as e:
            print(f"  [ERROR] undetected-chromedriver 初始化失败: {e}")
            print("  [INFO] 尝试使用 driver_executable_path 参数...")

            # 如果自动检测失败，让 undetected-chromedriver 自己处理
            self.driver = uc.Chrome(
                options=options,
                headless=False,
                use_subprocess=False,
            )

        # 应用 selenium-stealth
        try:
            stealth(self.driver,
                    languages=["zh-CN", "zh", "en-US", "en"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True)
            print("  [INFO] selenium-stealth 应用完成")
        except Exception as e:
            print(f"  [WARN] selenium-stealth 应用失败: {e}")
            print("  [INFO] 继续使用基础的 undetected-chromedriver")

    def navigate_to_url(self, url: str):
        """导航到指定 URL"""
        if not self.driver:
            self.initialize_driver()

        print(f"  [INFO] 正在导航到: {url}")
        self.driver.get(url)
        time.sleep(3)  # 等待页面加载

    def wait_for_captcha(self, timeout: int = 10) -> bool:
        """等待验证码弹窗出现"""
        try:
            print("  [INFO] 等待验证码弹窗出现...")
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.ID, "aliyunCaptcha-title"))
            )
            print("  [INFO] 检测到验证码弹窗")
            return True
        except:
            print("  [WARN] 未检测到验证码弹窗")
            return False

    def click_captcha_checkbox(self) -> bool:
        """点击验证码 checkbox"""
        try:
            print("  [INFO] 尝试使用 Selenium 点击验证码...")

            # 等待 checkbox 可见
            checkbox_body = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "aliyunCaptcha-checkbox-body"))
            )

            # 确保元素在视口内
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
                checkbox_body
            )
            time.sleep(0.5)

            # 获取元素位置
            location = checkbox_body.location
            size = checkbox_body.size

            # 添加随机偏移
            offset_x = random.uniform(-5, 5)
            offset_y = random.uniform(-5, 5)
            center_x = location['x'] + size['width'] / 2 + offset_x
            center_y = location['y'] + size['height'] / 2 + offset_y

            print(f"  [INFO] Checkbox 位置: ({center_x:.1f}, {center_y:.1f})")

            # 方法1: 直接使用 Selenium 的 click()
            try:
                checkbox_body.click()
                print("  [INFO] Selenium click() 执行成功")
            except Exception as e:
                print(f"  [WARN] Selenium click() 失败: {e}")

                # 方法2: 使用 JavaScript click
                try:
                    self.driver.execute_script("arguments[0].click();", checkbox_body)
                    print("  [INFO] JavaScript click() 执行成功")
                except Exception as e2:
                    print(f"  [WARN] JavaScript click() 失败: {e2}")

                    # 方法3: 使用 ActionChains 模拟鼠标移动和点击
                    try:
                        from selenium.webdriver.common.action_chains import ActionChains

                        actions = ActionChains(self.driver)

                        # 模拟人类行为：移动到元素附近，然后移动到中心，然后点击
                        # 先移动到元素上方
                        actions.move_to_element_with_offset(
                            checkbox_body,
                            int(offset_x - 20),
                            int(offset_y - 20)
                        )
                        actions.pause(random.uniform(0.1, 0.3))

                        # 移动到中心
                        actions.move_to_element_with_offset(
                            checkbox_body,
                            int(offset_x),
                            int(offset_y)
                        )
                        actions.pause(random.uniform(0.2, 0.4))

                        # 点击
                        actions.click()
                        actions.perform()

                        print("  [INFO] ActionChains click 执行成功")
                    except Exception as e3:
                        print(f"  [ERROR] ActionChains click 失败: {e3}")
                        return False

            # 等待验证响应
            print("  [INFO] 等待验证响应...")
            time.sleep(2)

            # 检查验证框文本是否改变
            try:
                checkbox_text = self.driver.find_element(By.ID, "aliyunCaptcha-checkbox-text")
                text_content = checkbox_text.text
                print(f"  [INFO] Checkbox 文本: {text_content}")

                if text_content != "点击开始智能验证":
                    print("  [OK] 验证框响应了点击！")
                    return True
                else:
                    print("  [WARN] 验证框没有响应点击")
                    return False
            except:
                pass

            return False

        except Exception as e:
            print(f"  [ERROR] 点击验证码时出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def check_captcha_passed(self, timeout: int = 15) -> bool:
        """检查验证是否通过"""
        try:
            print("  [INFO] 检查验证是否通过...")
            start_time = time.time()

            while time.time() - start_time < timeout:
                # 检查验证弹窗是否消失
                try:
                    popup = self.driver.find_element(By.ID, "aliyunCaptcha-window-popup")
                    is_visible = popup.is_displayed()

                    if not is_visible:
                        print("  [OK] 验证弹窗已消失，验证通过！")
                        return True
                except:
                    # 元素不存在也说明验证通过了
                    print("  [OK] 验证弹窗已不存在，验证通过！")
                    return True

                time.sleep(0.5)

            print("  [WARN] 验证超时")
            return False

        except Exception as e:
            print(f"  [WARN] 检查验证状态时出错: {e}")
            return False

    def handle_captcha(self, url: str) -> bool:
        """
        完整的验证码处理流程

        Args:
            url: 问卷URL

        Returns:
            是否成功通过验证
        """
        try:
            # 1. 初始化并导航
            self.navigate_to_url(url)

            # 2. 等待验证码出现
            if not self.wait_for_captcha():
                print("  [INFO] 没有验证码，继续...")
                return True

            # 3. 点击验证码
            if not self.click_captcha_checkbox():
                print("  [WARN] 点击验证码失败")
                return False

            # 4. 检查是否通过
            return self.check_captcha_passed()

        except Exception as e:
            print(f"  [ERROR] 处理验证码时出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def close(self):
        """关闭浏览器"""
        if self.driver:
            print("  [INFO] 关闭 Selenium 浏览器...")
            self.driver.quit()
            self.driver = None
