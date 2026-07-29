#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Selenium + undetected-chromedriver 处理阿里云验证码
使用 Playwright 填写问卷，用 Selenium 自动点击验证码
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.dynamic_submitter import DynamicSubmitter
from core.selenium_captcha_handler import SeleniumCaptchaHandler


async def test_with_selenium_captcha(url: str):
    """
    混合方案：Playwright 填写表单 + Selenium 点击验证码
    """
    print("=" * 80)
    print("测试 Selenium 自动点击阿里云验证码".center(80))
    print("=" * 80)
    print(f"\n问卷URL: {url}\n")

    async with async_playwright() as p:
        # ========== 步骤1: Playwright 分析和填写问卷 ==========
        print("步骤1: 使用 Playwright 分析问卷...")
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()

            analyzer = RuleBasedAnalyzer()
            schema = analyzer.analyze(html, url)

            print(f"  ✅ 问卷分析完成 (活动ID: {schema.activity_id}, 题目: {len(schema.questions)})")

            # ========== 步骤2: 生成答案并填写 ==========
            print(f"\n步骤2: 生成答案并填写表单...")
            generator = DynamicAnswerGenerator(schema)
            answers = generator.generate_answers()

            submitter = DynamicSubmitter(schema)
            for question in schema.questions:
                answer = answers.get(question.id)
                if answer is None:
                    continue
                await submitter._fill_question(page, question, answer)
                await asyncio.sleep(0.05)

            print(f"  ✅ 表单填写完成")

            # ========== 步骤3: 记录 Cookie 并关闭 Playwright ==========
            print(f"\n步骤3: 保存 session 信息...")

            # 获取 cookies（用于 Selenium 恢复 session）
            cookies = await page.context.cookies()
            current_url = page.url

            print(f"  ✅ 已保存 {len(cookies)} 个 cookies")

            # 关闭 Playwright
            await browser.close()
            print(f"  ✅ Playwright 浏览器已关闭")

        except Exception as e:
            print(f"\n❌ Playwright 阶段失败: {e}")
            import traceback
            traceback.print_exc()
            await browser.close()
            return False

    # ========== 步骤4: 使用 Selenium 处理验证码 ==========
    print(f"\n{'=' * 80}")
    print("切换到 Selenium + undetected-chromedriver".center(80))
    print(f"{'=' * 80}\n")

    print("步骤4: 初始化 Selenium...")
    handler = SeleniumCaptchaHandler()

    try:
        handler.initialize_driver()

        # ========== 步骤5: 恢复 session 并导航 ==========
        print(f"\n步骤5: 恢复 session 并导航到问卷...")
        handler.driver.get(current_url)

        # 添加 cookies
        for cookie in cookies:
            try:
                # Selenium 需要的 cookie 格式
                selenium_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie.get('domain', ''),
                    'path': cookie.get('path', '/'),
                }
                if 'sameSite' in cookie:
                    selenium_cookie['sameSite'] = cookie['sameSite']
                handler.driver.add_cookie(selenium_cookie)
            except Exception as e:
                # 某些 cookie 可能无法添加，跳过
                pass

        # 重新加载页面以应用 cookies
        handler.driver.refresh()
        print(f"  ✅ Session 恢复完成")

        # ========== 步骤6: 滚动到底部并点击提交 ==========
        print(f"\n步骤6: 滚动到页面底部...")
        handler.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        import time
        time.sleep(1)

        print(f"\n步骤7: 点击提交按钮...")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        submit_btn = WebDriverWait(handler.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ctlNext"))
        )
        submit_btn.click()
        print(f"  ✅ 已点击提交按钮")

        # ========== 步骤8: 等待并处理验证码 ==========
        print(f"\n步骤8: 等待验证码出现...")
        if handler.wait_for_captcha(timeout=10):
            print(f"  ✅ 检测到验证码！")

            print(f"\n步骤9: 自动点击验证码...")
            success = handler.click_captcha_checkbox()

            if success:
                print(f"\n{'=' * 80}")
                print("✅ 验证码响应了点击！".center(80))
                print(f"{'=' * 80}\n")

                # 等待验证完成
                print("步骤10: 等待验证完成...")
                if handler.check_captcha_passed(timeout=20):
                    print(f"\n{'=' * 80}")
                    print("🎉 验证通过！提交成功！".center(80))
                    print(f"{'=' * 80}\n")

                    handler.driver.save_screenshot("success.png")
                    print("📸 成功截图: success.png")

                    time.sleep(3)
                    handler.close()
                    return True
                else:
                    print(f"\n{'=' * 80}")
                    print("❌ 验证未通过".center(80))
                    print(f"{'=' * 80}\n")

                    handler.driver.save_screenshot("failed.png")
                    print("📸 失败截图: failed.png")

                    time.sleep(3)
                    handler.close()
                    return False
            else:
                print(f"\n{'=' * 80}")
                print("❌ 验证码没有响应".center(80))
                print(f"{'=' * 80}\n")

                handler.driver.save_screenshot("no_response.png")
                print("📸 无响应截图: no_response.png")

                time.sleep(3)
                handler.close()
                return False
        else:
            print(f"  ℹ️ 未检测到验证码（可能直接提交成功）")
            handler.close()
            return True

    except Exception as e:
        print(f"\n❌ Selenium 阶段失败: {e}")
        import traceback
        traceback.print_exc()

        try:
            handler.driver.save_screenshot("error.png")
            print("📸 错误截图: error.png")
        except:
            pass

        handler.close()
        return False


async def main():
    test_url = "https://ks.wjx.com/vm/rsRj1YB.aspx"

    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║          Selenium + undetected-chromedriver 自动验证码测试                     ║
║                                                                              ║
║  测试流程:                                                                    ║
║    1. Playwright: 分析问卷 → 生成答案 → 填写表单                             ║
║    2. 保存 session (cookies) 并关闭 Playwright                               ║
║    3. Selenium: 初始化 undetected-chromedriver                               ║
║    4. Selenium: 恢复 session → 提交表单                                      ║
║    5. Selenium: 自动点击验证码                                                ║
║    6. Selenium: 等待验证通过                                                  ║
║                                                                              ║
║  关键技术:                                                                    ║
║    - undetected-chromedriver: 绕过 Selenium 检测                            ║
║    - selenium-stealth: 移除自动化特征                                        ║
║    - ActionChains: 模拟人类鼠标移动                                          ║
║    - Cookie 传递: 保持 Playwright 填写的表单数据                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        success = await test_with_selenium_captcha(test_url)

        print(f"\n{'=' * 80}")
        if success:
            print("✅ 测试成功！自动化验证码通过！".center(80))
        else:
            print("❌ 测试失败".center(80))
        print(f"{'=' * 80}\n")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
        return 1
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
