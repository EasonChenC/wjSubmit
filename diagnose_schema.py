"""
诊断脚本 - 检查schema是否正确识别多输入框题目
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
import sys
import json

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.rule_based_analyzer import RuleBasedAnalyzer


async def diagnose():
    url = 'https://v.wjx.cn/vm/t3tsMH5.aspx'

    print("="*80)
    print("Schema诊断")
    print("="*80)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()

            # 分析schema
            analyzer = RuleBasedAnalyzer()
            schema = analyzer.analyze(html, url)

            print(f"\n总题目数: {len(schema.questions)}")
            print(f"题型统计: {schema.metadata['identified_types']}\n")

            # 查找TEXT类型的题目
            text_questions = [q for q in schema.questions if q.type.value == 'text']
            print(f"TEXT类型题目数: {len(text_questions)}\n")

            # 显示前20个TEXT题目的详细信息
            print("前20个TEXT题目详情:")
            print("-"*80)
            for i, q in enumerate(text_questions[:20], 1):
                print(f"\n{i}. ID: {q.id}")
                print(f"   标签: {q.label[:50]}")
                print(f"   选择器: {q.selector.template if q.selector else 'None'}")
                print(f"   特殊处理: {q.selector.special_handling if q.selector else 'None'}")
                print(f"   元数据: {q.metadata}")

            # 检查是否有"其他"选项的文本框
            other_text_questions = [q for q in text_questions if q.metadata and q.metadata.get('other_option_text')]
            print(f"\n\n'其他'选项文本框数量: {len(other_text_questions)}")

            if other_text_questions:
                print("\n'其他'选项文本框详情:")
                for q in other_text_questions[:5]:
                    print(f"  - {q.id}: 父题={q.metadata.get('parent_question')}")

            # 保存完整schema到JSON文件
            schema_dict = {
                'url': schema.url,
                'total_questions': len(schema.questions),
                'questions': []
            }

            for q in schema.questions:
                schema_dict['questions'].append({
                    'id': q.id,
                    'type': q.type.value,
                    'label': q.label[:50],
                    'selector': q.selector.template if q.selector else None,
                    'special_handling': q.selector.special_handling if q.selector else None,
                    'metadata': q.metadata
                })

            with open('schema_diagnosis.json', 'w', encoding='utf-8') as f:
                json.dump(schema_dict, f, indent=2, ensure_ascii=False)

            print(f"\n\n完整schema已保存到: schema_diagnosis.json")

        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(diagnose())
