"""
调试脚本 - 分析问卷HTML结构

用于调试文本输入框找不到的问题。
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.rule_based_analyzer import RuleBasedAnalyzer


async def debug_text_inputs(url: str):
    """调试文本输入框"""
    print(f"🔍 调试问卷: {url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()

            # 保存HTML
            html_file = Path(__file__).parent / "debug_questionnaire.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✅ HTML已保存: {html_file.name}\n")

            # 分析问卷
            analyzer = RuleBasedAnalyzer()
            schema = analyzer.analyze(html, url)

            # 找出TEXT类型的题目
            text_questions = [q for q in schema.questions if q.type.value == 'text']
            print(f"📋 TEXT类型题目: {len(text_questions)}个\n")

            # 解析HTML
            soup = BeautifulSoup(html, 'html.parser')

            for question in text_questions[:3]:  # 只显示前3个
                print(f"{'='*60}")
                print(f"题目ID: {question.id}")
                print(f"题目标签: {question.label[:50]}")
                print(f"{'='*60}\n")

                # 查找这个题目的field div
                field_div = soup.find('div', id=question.id) or \
                           soup.find('div', attrs={'field': question.id})

                if not field_div:
                    # 尝试通过class查找
                    field_divs = soup.find_all('div', class_=re.compile(r'field'))
                    for div in field_divs:
                        if question.id in str(div.get('id', '')):
                            field_div = div
                            break

                if field_div:
                    print("找到field div:")
                    print(f"  id: {field_div.get('id')}")
                    print(f"  field: {field_div.get('field')}")
                    print(f"  class: {field_div.get('class')}\n")

                    # 查找所有input元素
                    inputs = field_div.find_all('input', attrs={'type': 'text'})
                    print(f"找到 {len(inputs)} 个text input:\n")

                    for i, inp in enumerate(inputs, 1):
                        print(f"  Input #{i}:")
                        print(f"    id: {inp.get('id')}")
                        print(f"    name: {inp.get('name')}")
                        print(f"    class: {inp.get('class')}")
                        print(f"    placeholder: {inp.get('placeholder', '')[:30]}")
                        print(f"    readonly: {inp.get('readonly')}")
                        print()

                    # 给出建议的选择器
                    print("💡 建议的选择器策略:")
                    if len(inputs) == 1:
                        inp = inputs[0]
                        if inp.get('id'):
                            print(f"  getElementById('{inp.get('id')}')")
                            print(f"  或 #{inp.get('id')}")
                        if inp.get('name'):
                            print(f"  input[name=\"{inp.get('name')}\"]")
                    else:
                        print(f"  这个题目有 {len(inputs)} 个输入框")
                        print(f"  可能需要识别为多个子题")
                        for i, inp in enumerate(inputs, 1):
                            if inp.get('id'):
                                print(f"    子题{i}: #{inp.get('id')}")

                else:
                    print("❌ 未找到field div")

                print()

        finally:
            await browser.close()


async def main():
    url = 'https://v.wjx.cn/vm/t3tsMH5.aspx'
    await debug_text_inputs(url)


if __name__ == '__main__':
    asyncio.run(main())
