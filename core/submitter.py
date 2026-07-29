# submitter.py
import asyncio
import random
from datetime import datetime
from playwright.async_api import BrowserContext, Page

class QuestionnaireSubmitter:
    """问卷提交核心逻辑"""

    def __init__(self, url: str, answer_generator, captcha_solver, browser_manager):
        self.url = url
        self.answer_generator = answer_generator
        self.captcha_solver = captcha_solver
        self.browser_manager = browser_manager

    async def submit_one(self) -> dict:
        """提交一份问卷"""
        context = await self.browser_manager.get_context()
        page = await context.new_page()

        try:
            # 1. 访问问卷页面
            await page.goto(self.url, wait_until='networkidle')
            await asyncio.sleep(random.uniform(1, 3))

            # 2. 设置starttime隐藏字段
            start_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            await page.evaluate(f'''
                const starttimeInput = document.querySelector('input[name="starttime"]');
                if (starttimeInput) {{
                    starttimeInput.value = "{start_time}";
                }}
            ''')

            # 3. 生成答案
            answers = self.answer_generator.generate_answers({})
            answers = self.answer_generator.add_timing_data(answers)

            # 4. 填写问卷（模拟真实用户）
            await self._fill_questionnaire(page, answers)

            # 5. 处理验证码
            has_captcha = await page.query_selector('.nc_wrapper')
            if has_captcha:
                captcha_solved = await self.captcha_solver.solve_aliyun_captcha(page)
                if not captcha_solved:
                    return {'status': 'failed', 'reason': 'captcha_failed'}

            # 6. 提交 - 使用jQuery trigger方法
            await page.evaluate("$('#ctlNext').trigger('click')")
            await asyncio.sleep(2)

            # 7. 检查提交结果
            success = await self._check_submit_success(page)

            return {
                'status': 'success' if success else 'failed',
                'answers': answers,
                'final_url': page.url if success else None
            }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

        finally:
            await page.close()

    async def _fill_questionnaire(self, page: Page, answers: dict):
        """填写问卷 - 模拟真实用户行为"""
        timing = answers.pop('_timing')

        # 初始停留
        await asyncio.sleep(timing['start_time'])

        for q_id, answer in answers.items():
            # 滚动到题目位置
            await page.evaluate(f'window.scrollBy(0, {random.randint(50, 150)})')
            await asyncio.sleep(random.uniform(0.3, 0.8))

            # 根据题型填写
            await self._fill_by_type(page, q_id, answer)

            # 停留时间
            await asyncio.sleep(timing['answer_times'].get(q_id, 2))

    async def _fill_by_type(self, page: Page, q_id: str, answer):
        """根据题型填写答案 - 移动版选择器"""
        try:
            # Q1: 性别（单选）- 点击label元素
            if q_id == 'q1':
                await page.click(f'.label[for="q1_{answer}"]')

            # Q2: 年龄（下拉选择）- 保持不变
            elif q_id == 'q2':
                await page.select_option('select[name="q2"]', str(answer))

            # Q3: 城市（文本输入）- 使用JavaScript绕过readonly限制
            elif q_id == 'q3':
                await page.evaluate(f'document.getElementById("q3").value = "{answer}"')

            # Q4: 学历（单选）- 点击label元素
            elif q_id == 'q4':
                await page.click(f'.label[for="q4_{answer}"]')

            # Q5: 收入（单选）- 点击label元素
            elif q_id == 'q5':
                await page.click(f'.label[for="q5_{answer}"]')

            # Q6: 信息渠道（多选）- 点击label元素
            elif q_id == 'q6':
                if isinstance(answer, list):
                    for option in answer:
                        await page.click(f'.label[for="q6_{option}"]')

            # Q7: 购买因素矩阵（6个评分输入框）- 使用移动版选择器
            elif q_id.startswith('q7_'):
                # 提取行索引 (q7_0 -> 0, q7_1 -> 1, ...)
                row_index = q_id.split('_')[1]
                # 点击对应的评分元素
                await page.click(f'tr[fid="{q_id}"] a[dval="{answer}"]')

            # Q8: 购物频率（单选）- 点击label元素
            elif q_id == 'q8':
                await page.click(f'.label[for="q8_{answer}"]')

            # Q9: 购物平台（多选）- 点击label元素
            elif q_id == 'q9':
                if isinstance(answer, list):
                    for option in answer:
                        await page.click(f'.label[for="q9_{option}"]')

            # Q9-1: 其他平台文本框 - 使用ID选择器
            elif q_id == 'tqq9_8':
                await page.fill('#tqq9_8', answer)

            # Q10: 满意度评分（隐藏字段，需要点击UI评分元素）
            elif q_id == 'q10':
                await page.click(f'#div10 a.rate-off[val="{answer}"]')

            # Q11: NPS推荐度（隐藏字段，需要点击UI评分元素）
            # 注意：val属性从1-11对应分数0-10
            elif q_id == 'q11':
                await page.click(f'#div11 a.rate-off[val="{answer + 1}"]')

            # Q12: 排序题（需要按顺序点击UI元素）
            elif q_id == 'q12':
                # answer是一个包含6个元素的列表，如 [3, 1, 5, 2, 6, 4]
                # 表示点击顺序：第1次点击serial=3，第2次点击serial=1，依此类推
                # 必须确保点击所有6个选项
                if isinstance(answer, list) and len(answer) == 6:
                    for option_value in answer:
                        await page.click(f'#div12 li.ui-li-static[serial="{option_value}"]')
                        await asyncio.sleep(0.4)

            # Q13: 商品类别（文本输入）- 使用ID选择器
            elif q_id == 'q13':
                await page.fill('#q13', answer)

            # Q14: 改进建议（多行文本）- 使用ID选择器
            elif q_id == 'q14':
                if answer:  # 只在有内容时填写
                    await page.fill('textarea#q14', answer)

        except Exception as e:
            print(f"填写问题 {q_id} 时出错: {e}")

    async def _check_submit_success(self, page: Page) -> bool:
        """检查提交是否成功 - 检查是否跳转到完成页面"""
        try:
            # 等待跳转到完成页面
            await page.wait_for_url('**/completemobile2.aspx*', timeout=10000)
            final_url = page.url
            # 验证URL中包含joinactivity参数（提交记录ID）
            return 'joinactivity=' in final_url
        except:
            # 如果没有跳转，尝试检查是否有"提交成功"文本
            try:
                success_msg = await page.wait_for_selector(
                    'text=提交成功',
                    timeout=3000
                )
                return success_msg is not None
            except:
                return False
