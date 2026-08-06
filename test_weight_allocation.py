#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试权重分配题的权重生成逻辑

分析问卷中的权重分配题，测试生成的权重是否正确
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
from core.schema import QuestionType


async def test_weight_allocation(url: str):
    """测试权重分配题

    Args:
        url: 问卷URL
    """
    print(f"{'='*100}")
    print(f"权重分配题测试".center(100))
    print(f"{'='*100}\n")

    # 1. 获取并分析问卷
    print(f"正在分析问卷: {url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()

            # 分析问卷
            analyzer = RuleBasedAnalyzer()
            schema = analyzer.analyze(html, url)

            print(f"✅ 分析完成")
            print(f"   - 活动ID: {schema.activity_id}")
            print(f"   - 题目数量: {len(schema.questions)}\n")

            # 2. 查找权重分配题
            weight_questions = [q for q in schema.questions
                              if q.type == QuestionType.WEIGHT_ALLOCATION]

            if not weight_questions:
                print("❌ 没有找到权重分配题")
                return

            print(f"找到 {len(weight_questions)} 个权重分配题:\n")

            for wq in weight_questions:
                print(f"{'='*100}")
                print(f"题目ID: {wq.id}")
                print(f"题目: {wq.label}")
                print(f"子项数量: {len(wq.options)}")
                print(f"{'='*100}\n")

                # 显示子项
                print("子项列表:")
                for i, item in enumerate(wq.options, 1):
                    print(f"  {i}. {item}")
                print()

                # 3. 生成权重测试
                print("生成权重测试（20次）:")
                print(f"{'次数':<6} {'权重分布':<50} {'总和':<8} {'状态'}")
                print("-" * 100)

                generator = DynamicAnswerGenerator(schema, high_reliability_mode=False)

                errors = []
                for i in range(20):
                    try:
                        # 生成答案
                        answers = generator.generate_answers()
                        weights = answers.get(wq.id)

                        if weights is None:
                            print(f"第{i+1}次  ❌ 未生成权重")
                            errors.append(f"第{i+1}次: 未生成权重")
                            continue

                        # 计算总和
                        total = sum(weights)

                        # 格式化显示权重
                        weights_str = str(weights)
                        if len(weights_str) > 45:
                            weights_str = weights_str[:42] + "..."

                        # 判断是否正确
                        if total == 100:
                            status = "✅"
                        else:
                            status = f"❌ (差值: {total-100:+d})"
                            errors.append(f"第{i+1}次: 总和={total}, 权重={weights}")

                        print(f"第{i+1}次   {weights_str:<50} {total:<8} {status}")

                    except Exception as e:
                        print(f"第{i+1}次  ❌ 异常: {str(e)}")
                        errors.append(f"第{i+1}次: {str(e)}")

                print()

                # 4. 汇总统计
                if errors:
                    print(f"❌ 发现 {len(errors)} 个错误:\n")
                    for err in errors:
                        print(f"   - {err}")
                else:
                    print("✅ 所有测试通过！所有权重总和都等于100")

                print()

        finally:
            await browser.close()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='权重分配题测试')
    parser.add_argument('url', type=str, nargs='?',
                       default='https://v.wjx.cn/vm/eLeS3jD.aspx',
                       help='问卷URL')

    args = parser.parse_args()

    print(f"测试问卷: {args.url}\n")

    try:
        await test_weight_allocation(args.url)
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        print(f"\n详细错误:\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
