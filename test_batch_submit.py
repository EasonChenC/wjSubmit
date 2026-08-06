#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量提交测试脚本（简化版）

测试真实问卷的批量提交，验证高信度模式的量表题得分逻辑：
- 模式1：随机模式
- 模式2：高信度模式（积极态度） - 正向题高分，反向题低分
- 模式3：高信度模式（消极态度） - 正向题低分，反向题高分
"""
import sys
import io
import asyncio
import random
from pathlib import Path
from datetime import datetime

# 设置stdout为UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.dynamic_submitter import DynamicSubmitter


async def fetch_and_analyze(url: str):
    """获取并分析问卷

    Args:
        url: 问卷URL

    Returns:
        schema对象
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

            # 统计量表题
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


def preview_answers(schema, generator, count: int = 3):
    """预览生成的答案

    Args:
        schema: 问卷Schema
        generator: 答案生成器
        count: 预览数量
    """
    print(f"\n  预览前{count}份答案的量表题分布:")

    # 获取量表题
    scale_questions = [q for q in schema.questions
                      if q.type.value in ['rating', 'nps', 'matrix']]

    if not scale_questions:
        print("    ⚠️ 没有量表题")
        return

    # 打印表头
    header = "  份数    "
    for q in scale_questions[:10]:  # 只显示前10个
        is_reverse = "🔴" if q.metadata.get('is_reverse', False) else "🟢"
        header += f"{q.id}({is_reverse})".ljust(8)
    print(header)
    print("  " + "-" * 90)

    # 生成并打印答案
    for i in range(count):
        answers = generator.generate_answers()
        row = f"  第{i+1}份   "
        for q in scale_questions[:10]:
            ans = answers.get(q.id, 'N/A')
            row += str(ans).ljust(8)
        print(row)

    print("\n  说明: 🟢=正向题  🔴=反向题")


async def submit_one_questionnaire(url: str, schema, answers: dict):
    """提交一份问卷

    Args:
        url: 问卷URL
        schema: 问卷Schema
        answers: 答案字典

    Returns:
        {'success': True/False, 'error': '错误信息'}
    """
    async with async_playwright() as p:
        # 显示浏览器窗口，并使用慢速模式
        browser = await p.chromium.launch(
            headless=True,
            slow_mo=1  # 每个操作延迟300ms，方便观察
        )
        page = await browser.new_page()

        try:
            # 1. 访问问卷页面
            print(f"    - 正在访问问卷页面...")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(1, 2))

            # 2. 使用DynamicSubmitter填写和提交
            print(f"    - 正在填写表单...")
            submitter = DynamicSubmitter(schema)
            success = await submitter.fill_and_submit(page, answers)

            if success:
                print(f"    - 表单提交成功！")
                return {'success': True}
            else:
                print(f"    - 表单提交失败")
                return {'success': False, 'error': '提交未成功'}

        except Exception as e:
            print(f"    - 发生异常: {str(e)}")
            return {'success': False, 'error': str(e)}

        finally:
            await asyncio.sleep(1)  # 提交后等待1秒再关闭浏览器
            await browser.close()


async def batch_submit(url: str, schema, mode_name: str,
                       high_reliability_mode: bool, attitude: str, count: int, add_variation: bool = False):
    """批量提交问卷

    Args:
        url: 问卷URL
        schema: 问卷Schema
        mode_name: 模式名称
        high_reliability_mode: 是否高信度模式
        attitude: 回答态度
        count: 提交数量
        add_variation: 是否穿插部分不同趋势的回答
    """
    print(f"\n{'='*100}")
    print(f"{mode_name}".center(100))
    print(f"{'='*100}")

    if high_reliability_mode:
        print(f"模式: 高信度模式")
        print(f"态度: {attitude}")
        print(f"穿插变化: {'是' if add_variation else '否'}")
        if add_variation:
            print(f"  → 约10%的量表题会选择中立分数")
            print(f"  → 约5%的量表题会选择相反趋势")
    else:
        print(f"模式: 随机模式")

    # 创建生成器
    generator = DynamicAnswerGenerator(
        schema,
        high_reliability_mode=high_reliability_mode,
        attitude=attitude,
        add_variation=add_variation
    )

    # 预览答案
    preview_answers(schema, generator, count=min(3, count))

    # 询问是否继续提交
    print(f"\n准备提交 {count} 份问卷...")
    user_input = input(f"确认提交？(y/n): ").strip().lower()

    if user_input != 'y':
        print("  ⚠️ 跳过提交")
        return

    print(f"\n开始批量提交...")
    success_count = 0
    fail_count = 0

    for i in range(count):
        print(f"\n  {'='*90}")
        print(f"  正在处理第 {i+1}/{count} 份问卷")
        print(f"  {'='*90}")

        try:
            # 生成答案
            print(f"  [1/3] 生成答案...")
            answers = generator.generate_answers()

            # 提交问卷
            print(f"  [2/3] 启动浏览器并提交问卷...")
            result = await submit_one_questionnaire(url, schema, answers)

            print(f"  [3/3] 检查提交结果...")
            if result.get('success'):
                success_count += 1
                print(f"  ✅ 第 {i+1}/{count} 份提交成功！")
            else:
                fail_count += 1
                error_msg = result.get('error', '未知错误')
                print(f"  ❌ 第 {i+1}/{count} 份提交失败: {error_msg}")

            # 添加延迟，避免请求过快
            if i < count - 1:
                delay = random.uniform(3, 5)
                print(f"\n  ⏳ 等待 {delay:.1f} 秒后继续下一份...")
                await asyncio.sleep(delay)

        except Exception as e:
            fail_count += 1
            print(f"  ❌ 第 {i+1}/{count} 份提交异常: {str(e)}")
            import traceback
            print(f"\n  详细错误:")
            print(traceback.format_exc())

    print(f"\n提交完成:")
    print(f"  ✅ 成功: {success_count}/{count}")
    print(f"  ❌ 失败: {fail_count}/{count}")


async def main(url: str, count: int, mode: str, add_variation: bool = False):
    """主测试流程

    Args:
        url: 问卷URL
        count: 每种模式提交的数量
        mode: 测试模式
            - "all": 测试所有模式
            - "random": 只测试随机模式
            - "positive": 只测试积极态度
            - "negative": 只测试消极态度
        add_variation: 是否启用穿插变化
    """
    print("""
╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    批量提交测试脚本                                                ║
║                                                                                                  ║
║  测试目的: 验证真实问卷提交是否遵循高信度模式的量表题得分逻辑                                        ║
║                                                                                                  ║
║  模式说明:                                                                                        ║
║    - 随机模式: 所有题目随机生成                                                                   ║
║    - 积极态度: 正向题高分(4-5)，反向题低分(1-2)                                                    ║
║    - 消极态度: 正向题低分(1-2)，反向题高分(4-5)                                                    ║
║    - 穿插变化: 约3%选择中立，约2%选择相反趋势                                                      ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        # 步骤1: 获取并分析问卷
        schema = await fetch_and_analyze(url)

        # 步骤2: 根据mode参数选择测试模式
        if mode in ["all", "random"]:
            await batch_submit(
                url, schema,
                mode_name="模式1: 随机模式",
                high_reliability_mode=False,
                attitude="positive",  # 随机模式下attitude无效
                count=count,
                add_variation=False  # 随机模式下不需要变化
            )

        if mode in ["all", "positive"]:
            await batch_submit(
                url, schema,
                mode_name="模式2: 高信度模式（积极态度）",
                high_reliability_mode=True,
                attitude="positive",
                count=count,
                add_variation=add_variation
            )

        if mode in ["all", "negative"]:
            await batch_submit(
                url, schema,
                mode_name="模式3: 高信度模式（消极态度）",
                high_reliability_mode=True,
                attitude="negative",
                count=count,
                add_variation=add_variation
            )

        print(f"\n{'='*100}")
        print("所有测试完成".center(100))
        print(f"{'='*100}\n")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        print(f"\n详细错误:\n{traceback.format_exc()}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='批量提交测试脚本')
    parser.add_argument('url', type=str, nargs='?',
                       default='https://v.wjx.cn/vm/heiw7uL.aspx',
                       help='问卷URL（默认使用测试问卷）')
    parser.add_argument('-c', '--count', type=int, default=5,
                       help='每种模式提交的问卷数量（默认5份）')
    parser.add_argument('-m', '--mode', type=str, default='all',
                       choices=['all', 'random', 'positive', 'negative'],
                       help='测试模式: all(全部), random(随机), positive(积极), negative(消极)')
    parser.add_argument('-v', '--variation', action='store_true',
                       help='启用穿插变化（仅高信度模式有效）：约3%%题目选择中立，约2%%选择相反趋势')

    args = parser.parse_args()

    print(f"测试问卷: {args.url}")
    print(f"提交数量: 每种模式 {args.count} 份")
    print(f"测试模式: {args.mode}")
    if args.variation:
        print(f"穿插变化: 是（约5%的量表题会有变化）")
    print()

    success = asyncio.run(main(args.url, args.count, args.mode, args.variation))
    sys.exit(0 if success else 1)
