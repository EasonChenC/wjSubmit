#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本：查看画像驱动生成的答案分布
"""
import sys
import io
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.persona_generator import PersonaGenerator


async def debug_questionnaire(url: str):
    """调试问卷答案生成"""

    # 1. 获取问卷Schema
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30000)
        html = await page.content()
        await browser.close()

    analyzer = RuleBasedAnalyzer()
    schema = analyzer.analyze(html, url)

    print(f"问卷: {schema.activity_id}")
    print(f"量表题数量: {sum(1 for q in schema.questions if q.type.value in ['rating', 'nps', 'matrix'])}")
    print(f"反向题: {schema.metadata.get('reverse_items', [])}")
    print(f"维度: {schema.metadata.get('dimensions', {})}")
    print()

    # 2. 生成画像
    persona_gen = PersonaGenerator(seed=42)
    personas = persona_gen.generate_batch(schema, count=1, id_prefix="debug")
    persona = personas[0]

    print(f"画像ID: {persona.persona_id}")
    print(f"维度倾向:")
    for dim_name, tendency in persona.dimension_tendencies.items():
        print(f"  - {dim_name}: base_score={tendency.base_score:.2f}, scale={tendency.scale_min}-{tendency.scale_max}")
    print()

    # 创建生成器
    generator = DynamicAnswerGenerator(schema, persona=persona)

    # 3. 测试单个反向题的生成过程
    print("详细测试反向题 q5 的生成过程:")
    print("-" * 100)

    q5 = next(q for q in schema.questions if q.id == 'q5')
    print(f"题目: {q5.label}")
    print(f"是否反向题: {q5.metadata.get('is_reverse', False)}")
    print(f"题目选项: {q5.options}")
    print()

    # 手动模拟生成过程
    tendency = persona.dimension_tendencies['整体态度']
    print(f"维度倾向: base_score={tendency.base_score:.2f}, range={tendency.scale_min}-{tendency.scale_max}")
    print()

    print("生成10次答案，观察每次的结果:")
    for i in range(10):
        answer = generator.generate_answers()['q5']
        print(f"第{i+1}次: {answer}")

    print()
    print("期望: 反向题应该得到低分（1-2分），因为base_score=4.6很高")
    print("      如果得到高分（4-5分），说明反向处理失败！")
    print()

    # 4. 生成10份完整答案
    print("生成10份完整答案（只显示量表题）:")
    print("-" * 100)

    scale_questions = [q for q in schema.questions if q.type.value in ['rating', 'nps', 'matrix']]

    # 打印表头
    header = "次数    "
    for q in scale_questions[:10]:  # 最多显示10题
        is_reverse = "🔴" if q.metadata.get('is_reverse', False) else "🟢"
        header += f"{q.id}({is_reverse})".ljust(8)
    print(header)
    print("-" * 100)

    for i in range(10):
        answers = generator.generate_answers()

        row = f"第{i+1}次   "
        for q in scale_questions[:10]:
            ans = answers.get(q.id, 'N/A')
            row += str(ans).ljust(8)
        print(row)

    print()
    print("说明：")
    print("  🟢 = 正向题（分数应该偏高，如4-5分）")
    print("  🔴 = 反向题（分数应该偏低，如1-2分）")
    print()
    print("如果看到反向题分数也很高，说明反向处理有问题！")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://v.wjx.cn/vm/heiw7uL.aspx"
    asyncio.run(debug_questionnaire(url))
