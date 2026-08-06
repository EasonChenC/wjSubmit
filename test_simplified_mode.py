#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版测试脚本：测试两种模式

模式1：随机模式（high_reliability_mode=False）
模式2：高信度模式（high_reliability_mode=True）
    - attitude="positive": 正向题高分，反向题低分
    - attitude="negative": 正向题低分，反向题高分
"""
import sys
import io
import asyncio
from pathlib import Path

# 设置stdout为UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator


async def fetch_questionnaire_schema(url: str):
    """获取问卷并分析生成Schema

    Args:
        url: 问卷URL

    Returns:
        QuestionnaireSchema对象
    """
    print(f"📋 正在分析问卷: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()

            # 使用规则引擎分析
            analyzer = RuleBasedAnalyzer()
            schema = analyzer.analyze(html, url)

            print(f"  ✅ 分析完成")
            print(f"     - 活动ID: {schema.activity_id}")
            print(f"     - 题目数量: {len(schema.questions)}")

            # 统计量表题数量
            scale_questions = [q for q in schema.questions
                             if q.type.value in ['rating', 'nps', 'matrix']]
            print(f"     - 量表题数量: {len(scale_questions)}")

            # 统计反向题
            reverse_items = schema.metadata.get('reverse_items', [])
            print(f"     - 反向题数量: {len(reverse_items)}")
            if reverse_items:
                print(f"       反向题ID: {reverse_items}")

            return schema

        finally:
            await browser.close()


def test_mode(schema, mode_name: str, high_reliability_mode: bool, attitude: str = "positive", count: int = 10):
    """测试指定模式

    Args:
        schema: 问卷Schema
        mode_name: 模式名称
        high_reliability_mode: 是否高信度模式
        attitude: 回答态度（仅在high_reliability_mode=True时有效）
        count: 生成答案数量
    """
    print(f"\n{'='*100}")
    print(f"{mode_name}".center(100))
    print(f"{'='*100}")

    # 创建生成器
    generator = DynamicAnswerGenerator(
        schema,
        high_reliability_mode=high_reliability_mode,
        attitude=attitude
    )

    # 生成答案
    print(f"生成 {count} 份答案...")
    answers_list = [generator.generate_answers() for _ in range(count)]
    print(f"  ✅ 生成完成")

    # 只显示量表题的答案分布
    scale_questions = [q for q in schema.questions
                      if q.type.value in ['rating', 'nps', 'matrix']]

    if not scale_questions:
        print("  ⚠️ 没有量表题")
        return

    print(f"\n量表题答案分布（前10题）:")
    print("-" * 100)

    # 打印表头
    header = "次数    "
    for q in scale_questions[:10]:
        is_reverse = "🔴" if q.metadata.get('is_reverse', False) else "🟢"
        header += f"{q.id}({is_reverse})".ljust(8)
    print(header)
    print("-" * 100)

    # 打印每次的答案
    for i, answers in enumerate(answers_list):
        row = f"第{i+1}次   "
        for q in scale_questions[:10]:
            ans = answers.get(q.id, 'N/A')
            row += str(ans).ljust(8)
        print(row)

    print()
    print("说明：")
    print("  🟢 = 正向题")
    print("  🔴 = 反向题")

    # 统计分数分布
    print(f"\n分数统计:")
    for q in scale_questions[:10]:
        scores = [answers.get(q.id) for answers in answers_list if answers.get(q.id) is not None]
        if scores:
            # 转换为整数
            try:
                scores = [int(s) for s in scores]
                avg = sum(scores) / len(scores)
                min_score = min(scores)
                max_score = max(scores)
                is_reverse = "🔴" if q.metadata.get('is_reverse', False) else "🟢"
                print(f"  {q.id}({is_reverse}): 平均={avg:.2f}, 范围=[{min_score}, {max_score}]")
            except (ValueError, TypeError):
                pass


async def main(url: str):
    """主测试流程

    Args:
        url: 问卷URL
    """
    print("""
╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                  简化版答案生成测试                                                ║
║                                                                                                  ║
║  测试流程:                                                                                        ║
║    1. 分析问卷获取Schema                                                                          ║
║    2. 模式1：随机模式                                                                             ║
║    3. 模式2：高信度模式（积极态度）                                                                ║
║    4. 模式3：高信度模式（消极态度）                                                                ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        # 步骤1: 获取并分析问卷
        schema = await fetch_questionnaire_schema(url)

        # 步骤2: 测试随机模式
        test_mode(
            schema,
            mode_name="模式1: 随机模式（high_reliability_mode=False）",
            high_reliability_mode=False,
            count=10
        )

        # 步骤3: 测试高信度模式 - 积极态度
        test_mode(
            schema,
            mode_name="模式2: 高信度模式（attitude='positive'）",
            high_reliability_mode=True,
            attitude="positive",
            count=10
        )

        # 步骤4: 测试高信度模式 - 消极态度
        test_mode(
            schema,
            mode_name="模式3: 高信度模式（attitude='negative'）",
            high_reliability_mode=True,
            attitude="negative",
            count=10
        )

        print(f"\n{'='*100}")
        print("测试完成".center(100))
        print(f"{'='*100}\n")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        print(f"\n详细错误:\n{traceback.format_exc()}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='简化版答案生成测试')
    parser.add_argument('url', type=str, nargs='?',
                       default='https://v.wjx.cn/vm/heiw7uL.aspx',
                       help='问卷URL（默认使用测试问卷）')

    args = parser.parse_args()

    print(f"测试问卷: {args.url}\n")

    success = asyncio.run(main(args.url))
    sys.exit(0 if success else 1)
