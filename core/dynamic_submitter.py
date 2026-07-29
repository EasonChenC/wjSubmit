# dynamic_submitter.py
"""
动态表单填写器

基于QuestionnaireSchema和答案动态填写问卷表单，替代硬编码的submitter.py。
支持9种题型的自动化填写。
"""

import asyncio
from typing import Dict, Any, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .schema import (
    QuestionnaireSchema,
    Question,
    QuestionType,
)


class DynamicSubmitter:
    """动态表单填写器

    根据问卷Schema和生成的答案自动填写表单。
    """

    def __init__(self, schema: QuestionnaireSchema):
        """初始化填写器

        Args:
            schema: 问卷结构定义
        """
        self.schema = schema

    async def fill_and_submit(self, page: Page, answers: Dict[str, Any]) -> bool:
        """填写并提交表单

        Args:
            page: Playwright页面对象
            answers: 答案字典

        Returns:
            是否成功提交
        """
        try:
            # 1. 填写所有题目
            for question in self.schema.questions:
                answer = answers.get(question.id)
                if answer is None:
                    continue

                await self._fill_question(page, question, answer)

                # 每题之间暂停一小段时间，模拟真实用户
                await asyncio.sleep(0.1)

            # 2. 提交表单
            success = await self._submit_form(page)

            return success

        except Exception as e:
            print(f"[ERROR] 填写表单失败: {str(e)}")
            raise

    async def _fill_question(self, page: Page, question: Question, answer: Any):
        """填写单个题目

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 答案
        """
        try:
            # 检查题目是否可见（支持条件跳转逻辑）
            is_visible = await self._is_question_visible(page, question)
            if not is_visible:
                print(f"  [SKIP] 题目已隐藏，跳过: {question.id}")
                return

            if question.type == QuestionType.RADIO:
                await self._fill_radio(page, question, answer)

            elif question.type == QuestionType.CHECKBOX:
                await self._fill_checkbox(page, question, answer)

            elif question.type == QuestionType.SELECT:
                await self._fill_select(page, question, answer)

            elif question.type == QuestionType.TEXT:
                await self._fill_text(page, question, answer)

            elif question.type == QuestionType.TEXTAREA:
                await self._fill_textarea(page, question, answer)

            elif question.type == QuestionType.MATRIX:
                await self._fill_matrix(page, question, answer)

            elif question.type == QuestionType.RATING:
                await self._fill_rating(page, question, answer)

            elif question.type == QuestionType.NPS:
                await self._fill_nps(page, question, answer)

            elif question.type == QuestionType.SORT:
                await self._fill_sort(page, question, answer)

            else:
                print(f"[WARN] 未知题型: {question.id} - {question.type}")

        except Exception as e:
            print(f"[WARN] 填写题目 {question.id} 失败: {str(e)}")
            # 继续填写其他题目，不中断整个流程
            pass

    async def _is_question_visible(self, page: Page, question: Question) -> bool:
        """检查题目是否可见（用于处理条件跳转逻辑）

        Args:
            page: Playwright页面对象
            question: 题目对象

        Returns:
            是否可见
        """
        try:
            # 策略1: 检查题目容器div是否可见
            question_num = question.id.replace('q', '')
            div_selectors = [
                f'#div{question_num}',
                f'div[topic="{question_num}"]',
            ]

            for selector in div_selectors:
                try:
                    # 检查元素是否存在且可见
                    is_visible = await page.evaluate(f"""
                        (function() {{
                            var elem = document.querySelector('{selector}');
                            if (!elem) return null;

                            // 检查display
                            var style = window.getComputedStyle(elem);
                            if (style.display === 'none') return false;
                            if (style.visibility === 'hidden') return false;
                            if (style.opacity === '0') return false;

                            // 检查父元素是否隐藏
                            var parent = elem.parentElement;
                            while (parent && parent.tagName !== 'BODY') {{
                                var pStyle = window.getComputedStyle(parent);
                                if (pStyle.display === 'none') return false;
                                if (pStyle.visibility === 'hidden') return false;
                                parent = parent.parentElement;
                            }}

                            return true;
                        }})();
                    """)

                    if is_visible is not None:
                        return is_visible
                except:
                    continue

            # 策略2: 尝试定位题目的第一个可交互元素
            if question.type == QuestionType.RADIO:
                test_selector = f'input[id^="{question.id}_"]'
            elif question.type == QuestionType.CHECKBOX:
                test_selector = f'input[id^="{question.id}_"]'
            elif question.type == QuestionType.TEXT:
                test_selector = f'#{question.id}'
            else:
                # 其他类型，假设可见
                return True

            try:
                elem = await page.query_selector(test_selector)
                if elem:
                    is_visible = await elem.is_visible()
                    return is_visible
            except:
                pass

            # 默认假设可见
            return True

        except Exception as e:
            # 检测失败，假设可见（保持原有行为）
            return True

    async def _fill_radio(self, page: Page, question: Question, answer: int):
        """填写单选题

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 选项ID
        """
        # 尝试多种选择器策略
        selectors = [
            # 策略1: 点击 jqradio 链接（新问卷格式）
            f'input[id="{question.id}_{answer}"] ~ a.jqradio',
            # 策略2: 点击 label 标签（旧问卷格式）
            f'.label[for="{question.id}_{answer}"]',
            f'label[for="{question.id}_{answer}"]',
            # 策略3: 直接点击 input（兜底）
            f'#{question.id}_{answer}',
        ]

        for selector in selectors:
            try:
                await page.click(selector, timeout=2000)
                return  # 成功就返回
            except:
                continue

        # 都失败了，打印警告
        print(f"  [WARN] 无法点击单选题: {question.id}_{answer}")

    async def _fill_checkbox(self, page: Page, question: Question, answer: List[int]):
        """填写多选题

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 选项ID列表
        """
        for option_id in answer:
            # 尝试多种选择器策略
            selectors = [
                # 策略1: 点击 jqcheck 链接（新问卷格式）
                f'input[id="{question.id}_{option_id}"] ~ a.jqcheck',
                # 策略2: 点击 label 标签（旧问卷格式）
                f'.label[for="{question.id}_{option_id}"]',
                f'label[for="{question.id}_{option_id}"]',
                # 策略3: 直接点击 input（兜底）
                f'#{question.id}_{option_id}',
            ]

            clicked = False
            for selector in selectors:
                try:
                    await page.click(selector, timeout=2000)
                    clicked = True
                    break
                except:
                    continue

            if not clicked:
                print(f"  [WARN] 无法点击多选项: {question.id}_{option_id}")
            else:
                # 检查是否是"其他"选项，如果是，需要等待文本框出现
                if question.metadata and f'other_text_{option_id}' in question.metadata:
                    await asyncio.sleep(0.2)  # 等待文本框显示

            await asyncio.sleep(0.05)  # 多选项之间短暂暂停

    async def _fill_select(self, page: Page, question: Question, answer: int):
        """填写下拉选择题

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 选项值
        """
        selector = f'select[name="{question.id}"]'
        await page.select_option(selector, str(answer), timeout=5000)

    async def _fill_text(self, page: Page, question: Question, answer: str):
        """填写文本输入题

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 文本内容
        """
        # 转换answer为字符串
        answer_str = str(answer)

        # 检查是否是contenteditable类型
        if question.metadata and question.metadata.get('contenteditable'):
            await self._fill_contenteditable(page, question, answer_str)
            return

        # 检查是否是匿名输入框（没有id属性的input）
        if question.metadata and question.metadata.get('anonymous'):
            await self._fill_anonymous_text(page, question, answer_str)
            return

        # 检查selector中的特殊处理
        if question.selector and question.selector.special_handling:
            if question.selector.special_handling == "contenteditable":
                await self._fill_contenteditable(page, question, answer_str)
                return
            elif question.selector.special_handling == "contenteditable_with_id":
                # 使用选择器直接填充contenteditable span
                try:
                    selector = question.selector.template
                    await page.fill(selector, answer_str, timeout=3000)
                    return
                except Exception as e:
                    print(f"  [WARN] 无法使用选择器填写contenteditable: {selector}, 错误: {str(e)}")
                    # 尝试备选方案：直接通过input id查找相邻的span
                    try:
                        result = await page.evaluate(f"""
                            (function() {{
                                var input = document.getElementById('{question.id}');
                                if (input) {{
                                    var label = input.nextElementSibling;
                                    if (label && label.tagName === 'LABEL') {{
                                        var span = label.querySelector('span.textCont[contenteditable="true"]');
                                        if (span) {{
                                            span.textContent = `{answer_str}`;
                                            var event = new Event('input', {{ bubbles: true }});
                                            span.dispatchEvent(event);
                                            return true;
                                        }}
                                    }}
                                }}
                                return false;
                            }})();
                        """)
                        if result:
                            return
                    except:
                        pass
                    return
            elif question.selector.special_handling == "anonymous_input":
                # 使用selector中的模板
                try:
                    selector = question.selector.template
                    await page.fill(selector, answer_str, timeout=3000)
                    return
                except:
                    print(f"  [WARN] 无法使用选择器填写: {selector}")
                    return

        # 方法1: 尝试直接使用getElementById
        try:
            result = await page.evaluate(f"""
                (function() {{
                    var elem = document.getElementById('{question.id}');
                    if (elem) {{
                        elem.value = `{answer_str}`;
                        return true;
                    }}
                    return false;
                }})();
            """)
            if result:
                return
        except:
            pass

        # 方法2: 尝试使用CSS选择器
        try:
            selector = f'#{question.id}'
            await page.fill(selector, answer_str, timeout=3000)
            return
        except:
            pass

        # 方法3: 尝试使用 input[name] 选择器
        try:
            selector = f'input[name="{question.id}"]'
            await page.fill(selector, answer_str, timeout=3000)
            return
        except:
            pass

        # 都失败了，跳过而不是抛出异常（允许部分题目失败）
        print(f"  [WARN] 跳过无法填写的文本输入框: {question.id}")

    async def _fill_anonymous_text(self, page: Page, question: Question, answer: str):
        """填写匿名文本框（没有id/name属性的input）

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 文本内容
        """
        topic_num = question.metadata.get('topic_num')
        if not topic_num:
            print(f"  [WARN] 匿名输入框缺少topic_num: {question.id}")
            return

        # 策略1: 使用选择器
        selector = f'#div{topic_num} input[type="text"]'
        try:
            await page.fill(selector, answer, timeout=3000)
            return
        except:
            pass

        # 策略2: 使用evaluate直接操作
        try:
            result = await page.evaluate(f"""
                (function() {{
                    var div = document.getElementById('div{topic_num}');
                    if (div) {{
                        var inputs = div.querySelectorAll('input[type="text"]');
                        if (inputs.length > 0) {{
                            inputs[0].value = `{answer}`;
                            return true;
                        }}
                    }}
                    return false;
                }})();
            """)
            if result:
                return
        except:
            pass

        print(f"  [WARN] 无法填写匿名输入框: div{topic_num}")

    async def _fill_contenteditable(self, page: Page, question: Question, answer: str):
        """填写contenteditable span元素

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 文本内容
        """
        topic_num = question.metadata.get('topic_num')
        if not topic_num:
            print(f"  [WARN] contenteditable元素缺少topic_num: {question.id}")
            return

        # 策略1: 使用选择器直接填充
        selector = f'#div{topic_num} span.textCont[contenteditable="true"]'
        try:
            # Playwright的fill方法支持contenteditable元素
            await page.fill(selector, answer, timeout=3000)
            return
        except:
            pass

        # 策略2: 使用evaluate直接操作textContent
        try:
            result = await page.evaluate(f"""
                (function() {{
                    var div = document.getElementById('div{topic_num}');
                    if (div) {{
                        var span = div.querySelector('span.textCont[contenteditable="true"]');
                        if (span) {{
                            span.textContent = `{answer}`;
                            // 触发input事件以确保表单同步
                            var event = new Event('input', {{ bubbles: true }});
                            span.dispatchEvent(event);
                            return true;
                        }}
                    }}
                    return false;
                }})();
            """)
            if result:
                return
        except Exception as e:
            pass

        print(f"  [WARN] 无法填写contenteditable元素: div{topic_num}")

    async def _fill_textarea(self, page: Page, question: Question, answer: str):
        """填写多行文本题

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 文本内容
        """
        selector = f'textarea#{question.id}'
        await page.fill(selector, answer, timeout=5000)

    async def _fill_matrix(self, page: Page, question: Question, answer: str):
        """填写矩阵评分题（单行）

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 评分值
        """
        # 矩阵题的选择器：tr[fid="q7_0"] a[dval="4"]
        # question.id 已经包含行号，如 "q7_0"
        selector = f'tr[fid="{question.id}"] a[dval="{answer}"]'
        await page.click(selector, timeout=5000)

    async def _fill_rating(self, page: Page, question: Question, answer: int):
        """填写评分题（1-5分）

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 评分值
        """
        # 评分题选择器：#div10 a.rate-off[val="5"]
        # 从 question.id 提取数字部分（如 q10 -> 10）
        q_num = question.id[1:]  # 去掉 'q' 前缀
        selector = f'#div{q_num} a.rate-off[val="{answer}"]'
        await page.click(selector, timeout=5000)

    async def _fill_nps(self, page: Page, question: Question, answer: int):
        """填写NPS推荐度（0-10分）

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 推荐度分值
        """
        # NPS选择器：#div11 a.rate-off[val="6"]
        # 注意：val属性从1-11对应分数0-10，所以需要 +1
        q_num = question.id[1:]
        val = answer + 1
        selector = f'#div{q_num} a.rate-off[val="{val}"]'
        await page.click(selector, timeout=5000)

    async def _fill_sort(self, page: Page, question: Question, answer: List[int]):
        """填写排序题

        Args:
            page: Playwright页面对象
            question: 题目对象
            answer: 排序后的serial值列表
        """
        # 排序题选择器：#div12 li.ui-li-static[serial="3"]
        # 需要按顺序点击所有选项
        q_num = question.id[1:]

        for serial in answer:
            selector = f'#div{q_num} li.ui-li-static[serial="{serial}"]'
            await page.click(selector, timeout=5000)
            await asyncio.sleep(0.4)  # 排序项之间暂停

    async def _submit_form(self, page: Page) -> bool:
        """提交表单

        Args:
            page: Playwright页面对象

        Returns:
            是否提交成功
        """
        try:
            # 点击提交按钮
            submit_button = page.locator('#ctlNext')
            await submit_button.click(timeout=5000)

            print(f"  [INFO] 已点击提交按钮，等待验证弹窗出现...")

            # 等待验证弹窗出现 - 最多等待5秒
            captcha_appeared = False
            for i in range(10):  # 每0.5秒检查一次，最多5秒
                await asyncio.sleep(0.5)

                # 检查阿里云验证框是否出现
                aliyun_title = await page.query_selector('#aliyunCaptcha-title')
                if aliyun_title and await aliyun_title.is_visible():
                    print(f"  [INFO] 检测到验证弹窗（等待{(i+1)*0.5}秒后出现）")
                    captcha_appeared = True
                    break

            # 如果验证框出现，处理它
            if captcha_appeared:
                captcha_handled = await self._handle_smart_captcha(page)
                if captcha_handled:
                    print(f"  [OK] 智能验证已通过")
                    # 验证通过后再等待一下
                    await asyncio.sleep(2)
                else:
                    print(f"  [WARN] 智能验证未通过")
                    return False
            else:
                print(f"  [INFO] 未检测到验证弹窗，继续检查提交结果...")

            # 检查是否有错误提示
            error_div = page.locator('div.errorinfo')
            is_visible = await error_div.is_visible()

            if is_visible:
                error_text = await error_div.inner_text()
                print(f"[ERROR] 提交失败，错误信息: {error_text}")
                return False

            # 检查是否跳转到成功页面
            current_url = page.url
            if 'complete' in current_url.lower() or 'success' in current_url.lower():
                print(f"[OK] 提交成功")
                return True

            # 检查页面内容是否包含"提交成功"等关键词
            page_content = await page.content()
            if '提交成功' in page_content or '感谢您的参与' in page_content:
                print(f"[OK] 提交成功")
                return True

            # 检查验证框是否还在（如果还在说明没通过）
            aliyun_title = await page.query_selector('#aliyunCaptcha-title')
            if aliyun_title and await aliyun_title.is_visible():
                print(f"[WARN] 验证框仍然存在，提交未完成")
                return False

            # 未明确确认成功，返回True（假定成功）
            print(f"[OK] 提交成功（假定）")
            return True

        except PlaywrightTimeoutError:
            print(f"[WARN] 提交超时")
            return False
        except Exception as e:
            print(f"[ERROR] 提交异常: {str(e)}")
            return False

    async def _handle_smart_captcha(self, page: Page) -> bool:
        """处理智能验证弹窗

        目前只支持阿里云点击型验证

        Args:
            page: Playwright页面对象

        Returns:
            是否成功处理验证
        """
        try:
            # 检测阿里云验证弹窗
            aliyun_title = await page.query_selector('#aliyunCaptcha-title')
            if not aliyun_title or not await aliyun_title.is_visible():
                return False

            print(f"  [INFO] 检测到阿里云智能验证弹窗")
            return await self._handle_aliyun_captcha(page)

        except Exception as e:
            print(f"  [WARN] 处理验证时出错: {str(e)}")
            return False

    async def _handle_aliyun_captcha(self, page: Page) -> bool:
        """处理阿里云点击型验证

        Args:
            page: Playwright页面对象

        Returns:
            是否成功处理
        """
        try:
            print(f"  [INFO] 开始处理阿里云验证...")

            # 先确认验证框是否可见
            title = await page.query_selector('#aliyunCaptcha-title')
            if not title or not await title.is_visible():
                print(f"  [WARN] 验证框不可见")
                return False

            # 确保验证框在视口内
            await page.evaluate("""
                () => {
                    const elem = document.querySelector('#aliyunCaptcha-window-popup');
                    if (elem) {
                        elem.scrollIntoView({block: 'center', inline: 'center'});
                    }
                }
            """)
            await asyncio.sleep(0.5)

            # 使用最直接的方法：获取元素坐标，然后用鼠标点击
            selector = '#aliyunCaptcha-checkbox-body'

            try:
                print(f"  [INFO] 尝试点击验证元素: {selector}")

                # 检查元素是否存在且可见
                elem = await page.query_selector(selector)
                if not elem:
                    print(f"  [WARN] 元素 {selector} 不存在")
                    return False

                is_visible = await elem.is_visible()
                if not is_visible:
                    print(f"  [WARN] 元素 {selector} 不可见")
                    return False

                print(f"  [INFO] 元素 {selector} 存在且可见，获取坐标...")

                # 获取元素的bounding box
                box = await elem.bounding_box()
                if not box:
                    print(f"  [WARN] 无法获取元素坐标")
                    return False

                # 计算元素中心点，但添加随机偏移（模拟人类不精确的点击）
                import random
                offset_x = random.uniform(-10, 10)
                offset_y = random.uniform(-5, 5)
                center_x = box['x'] + box['width'] / 2 + offset_x
                center_y = box['y'] + box['height'] / 2 + offset_y

                print(f"  [INFO] 元素中心坐标: ({center_x:.1f}, {center_y:.1f})")
                print(f"  [INFO] 模拟人类鼠标移动和点击...")

                # 模拟更真实的人类鼠标移动
                # 从当前位置开始，经过几个中间点到达目标

                # 起点：远离目标的位置
                start_x = center_x - random.uniform(100, 200)
                start_y = center_y - random.uniform(50, 100)

                # 移动到起点
                await page.mouse.move(start_x, start_y)
                await asyncio.sleep(random.uniform(0.1, 0.2))

                # 第一个中间点
                mid1_x = start_x + (center_x - start_x) * 0.3
                mid1_y = start_y + (center_y - start_y) * 0.3
                await page.mouse.move(mid1_x, mid1_y)
                await asyncio.sleep(random.uniform(0.05, 0.1))

                # 第二个中间点
                mid2_x = start_x + (center_x - start_x) * 0.7
                mid2_y = start_y + (center_y - start_y) * 0.7
                await page.mouse.move(mid2_x, mid2_y)
                await asyncio.sleep(random.uniform(0.05, 0.1))

                # 移动到目标位置
                await page.mouse.move(center_x, center_y)

                # 在目标位置悬停一小会（模拟人类思考）
                await asyncio.sleep(random.uniform(0.2, 0.4))

                # 执行点击（mousedown + 短暂延迟 + mouseup）
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.15))  # 人类按下鼠标的时间
                await page.mouse.up()

                print(f"  [INFO] 鼠标点击完成，等待验证响应...")
                await asyncio.sleep(1)

                # 检查验证框是否还在（如果消失说明点击到了外面）
                title_after = await page.query_selector('#aliyunCaptcha-title')
                if not title_after or not await title_after.is_visible():
                    print(f"  [WARN] 点击后验证框消失，可能点击位置不准确")
                    return False

                # 检查checkbox的文本是否变化
                checkbox_text = await page.query_selector('#aliyunCaptcha-checkbox-text')
                if checkbox_text:
                    text_content = await checkbox_text.inner_text()
                    print(f"  [INFO] Checkbox文本: {text_content}")

                # 等待验证完成 - 最多等待15秒
                for i in range(30):  # 每0.5秒检查一次，最多15秒
                    await asyncio.sleep(0.5)
                    success = await self._verify_aliyun_captcha_success(page)
                    if success:
                        print(f"  [INFO] 阿里云验证通过（耗时{(i+1)*0.5}秒）")
                        return True

                print(f"  [WARN] 验证超时（等待15秒后仍未通过）")
                return False

            except Exception as e:
                print(f"  [WARN] 点击验证异常: {str(e)}")
                import traceback
                traceback.print_exc()
                return False

        except Exception as e:
            print(f"  [WARN] 阿里云验证处理失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def _verify_aliyun_captcha_success(self, page: Page) -> bool:
        """验证阿里云验证码是否成功通过

        Args:
            page: Playwright页面对象

        Returns:
            是否成功
        """
        try:
            # 等待阿里云验证弹窗消失
            try:
                await page.wait_for_selector(
                    '#aliyunCaptcha-window-popup, #aliyunCaptcha-mask',
                    state='hidden',
                    timeout=3000
                )
                return True
            except:
                pass

            # 或者检查弹窗是否还可见
            popup = await page.query_selector('#aliyunCaptcha-window-popup')
            if popup:
                is_visible = await popup.is_visible()
                return not is_visible

            # 假定成功
            return True

        except:
            # 假定成功
            return True


class SubmitResult:
    """提交结果

    封装提交结果信息，便于统计和分析。
    """

    def __init__(self, success: bool, error_msg: str = None,
                 duration: float = 0, answers: Dict[str, Any] = None):
        """初始化提交结果

        Args:
            success: 是否成功
            error_msg: 错误信息（如果失败）
            duration: 提交耗时（秒）
            answers: 提交的答案
        """
        self.success = success
        self.error_msg = error_msg
        self.duration = duration
        self.answers = answers or {}

    def __repr__(self) -> str:
        if self.success:
            return f"SubmitResult(success=True, duration={self.duration:.1f}s)"
        else:
            return f"SubmitResult(success=False, error={self.error_msg})"
