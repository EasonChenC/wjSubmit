"""
简单测试脚本 - 测试 t3tsMH5.aspx 问卷
避免emoji编码问题
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright
import json
import time

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.dynamic_submitter import DynamicSubmitter


async def test_questionnaire():
    """测试 t3tsMH5.aspx 问卷"""
    url = 'https://v.wjx.cn/vm/t3tsMH5.aspx'

    print("\n" + "="*80)
    print("测试问卷: t3tsMH5.aspx")
    print("="*80)
    print(f"URL: {url}\n")

    start_time = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            # 步骤1: 加载问卷
            print("步骤1: 加载问卷...")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()
            print(f"  页面加载完成，HTML大小: {len(html)} bytes\n")

            # 步骤2: 分析问卷结构
            print("步骤2: 分析问卷结构...")
            analyzer = RuleBasedAnalyzer()
            schema = analyzer.analyze(html, url)
            print(f"  识别题目数量: {len(schema.questions)}")
            print(f"  题型统计: {schema.metadata['identified_types']}\n")

            # 显示前几个题目
            print("  前5个题目:")
            for i, q in enumerate(schema.questions[:5], 1):
                print(f"    {i}. {q.id} - {q.type.value} - {q.label[:40]}")
            print()

            # 步骤3: 生成答案
            print("步骤3: 生成答案...")
            generator = DynamicAnswerGenerator(schema)
            answers = generator.generate_answers()
            print(f"  生成答案数量: {len(answers)}")

            # 显示部分答案
            print("  部分答案示例:")
            for i, (qid, ans) in enumerate(list(answers.items())[:5], 1):
                print(f"    {qid}: {ans}")
            print()

            # 步骤4: 填写并提交表单
            print("步骤4: 填写并提交表单...")
            submitter = DynamicSubmitter(schema)

            success = await submitter.fill_and_submit(page, answers)

            end_time = time.time()
            duration = end_time - start_time

            print("\n" + "="*80)
            if success:
                print("测试结果: 成功")
            else:
                print("测试结果: 失败")
            print(f"总耗时: {duration:.2f}秒")
            print("="*80)

            # 等待一下以便查看结果
            await asyncio.sleep(3)

            return success

        except Exception as e:
            print(f"\n错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            await browser.close()


if __name__ == '__main__':
    success = asyncio.run(test_questionnaire())
    sys.exit(0 if success else 1)
