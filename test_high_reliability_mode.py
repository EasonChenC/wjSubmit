#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 6 测试：高信度模式端到端测试

测试完整的高信度答案生成流程：
1. 分析问卷 → QuestionnaireSchema
2. 生成画像池 → 50个Persona
3. 画像驱动生成答案 → 高信度答案
4. 验证信度 → Cronbach's α ≥ 0.8

对比随机模式 vs 高信度模式的效果。
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
from core.persona_generator import PersonaGenerator
from core.reliability_validator import ReliabilityValidator


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
            print(f"     - 题型分布: {schema.metadata.get('identified_types', {})}")

            # 统计量表题数量
            scale_questions = [q for q in schema.questions
                             if q.type.value in ['rating', 'nps', 'matrix']]
            print(f"     - 量表题数量: {len(scale_questions)}")

            # 统计维度信息
            dimensions = schema.metadata.get('dimensions', {})
            print(f"     - 维度数量: {len(dimensions)}")
            if dimensions:
                for dim_name, q_ids in dimensions.items():
                    print(f"       • {dim_name}: {len(q_ids)}题")

            return schema

        finally:
            await browser.close()


def test_random_mode(schema, count=50):
    """测试随机模式

    Args:
        schema: 问卷Schema
        count: 生成答案数量

    Returns:
        answers_list, 信度结果字典
    """
    print(f"\n{'='*100}")
    print(f"模式1: 随机生成模式（旧系统）".center(100))
    print(f"{'='*100}")
    print(f"生成 {count} 份随机答案...")

    # 使用DynamicAnswerGenerator但不提供persona（随机模式）
    generator = DynamicAnswerGenerator(schema, persona=None)
    answers_list = [generator.generate_answers() for _ in range(count)]

    print(f"  ✅ 生成完成")

    # 计算信度
    validator = ReliabilityValidator(schema)
    dimensions = schema.metadata.get('dimensions', {})

    if not dimensions:
        print(f"  ⚠️ 问卷未检测到维度信息，跳过信度验证")
        return answers_list, {}

    print(f"\n信度分析:")
    alpha_header = "Cronbach's α"
    print(f"{'维度':<20} {'题目数':<10} {alpha_header:<15} {'评价':<15}")
    print("-" * 100)

    results = {}
    for dim_name in dimensions.keys():
        try:
            result = validator.validate(answers_list, dim_name)
            alpha = result.cronbach_alpha

            interpretation = "✅ 优秀" if alpha >= 0.9 else \
                           "✅ 良好" if alpha >= 0.8 else \
                           "⚠️ 可接受" if alpha >= 0.7 else \
                           "⚠️ 勉强" if alpha >= 0.6 else \
                           "❌ 不可接受"

            print(f"{dim_name:<20} {result.n_items:<10} {alpha:<15.4f} {interpretation:<15}")
            results[dim_name] = result

        except Exception as e:
            print(f"{dim_name:<20} {'N/A':<10} {'错误':<15} {str(e)[:20]:<15}")

    return answers_list, results


def test_high_reliability_mode(schema, count=50):
    """测试高信度模式

    Args:
        schema: 问卷Schema
        count: 生成答案数量

    Returns:
        answers_list, personas, 信度结果字典
    """
    print(f"\n{'='*100}")
    print(f"模式2: 高信度模式（画像驱动）".center(100))
    print(f"{'='*100}")

    # 步骤1: 生成画像池
    print(f"步骤1: 生成 {count} 个受访者画像...")
    persona_gen = PersonaGenerator(seed=42)
    personas = persona_gen.generate_batch(schema, count=count, id_prefix="hr")

    print(f"  ✅ 画像生成完成")
    print(f"     - 画像数量: {len(personas)}")

    # 显示第一个画像的维度倾向
    if personas:
        first_persona = personas[0]
        print(f"     - 示例画像 ({first_persona.persona_id}):")
        for dim_name, tendency in first_persona.dimension_tendencies.items():
            print(f"       • {dim_name}: base_score={tendency.base_score:.2f}")

    # 步骤2: 使用画像生成答案
    print(f"\n步骤2: 使用画像驱动生成答案...")
    answers_list = []
    for persona in personas:
        # 使用DynamicAnswerGenerator并提供persona（高信度模式）
        generator = DynamicAnswerGenerator(schema, persona=persona)
        answers = generator.generate_answers()
        answers_list.append(answers)

    print(f"  ✅ 答案生成完成")

    # 步骤3: 计算信度
    validator = ReliabilityValidator(schema)
    dimensions = schema.metadata.get('dimensions', {})

    if not dimensions:
        print(f"  ⚠️ 问卷未检测到维度信息，跳过信度验证")
        return answers_list, personas, {}

    print(f"\n信度分析:")
    alpha_header = "Cronbach's α"
    print(f"{'维度':<20} {'题目数':<10} {alpha_header:<15} {'评价':<15}")
    print("-" * 100)

    results = {}
    for dim_name in dimensions.keys():
        try:
            result = validator.validate(answers_list, dim_name)
            alpha = result.cronbach_alpha

            interpretation = "✅ 优秀" if alpha >= 0.9 else \
                           "✅ 良好" if alpha >= 0.8 else \
                           "⚠️ 可接受" if alpha >= 0.7 else \
                           "⚠️ 勉强" if alpha >= 0.6 else \
                           "❌ 不可接受"

            print(f"{dim_name:<20} {result.n_items:<10} {alpha:<15.4f} {interpretation:<15}")
            results[dim_name] = result

        except Exception as e:
            print(f"{dim_name:<20} {'N/A':<10} {'错误':<15} {str(e)[:20]:<15}")

    return answers_list, personas, results


def compare_results(random_results, hr_results):
    """对比两种模式的结果

    Args:
        random_results: 随机模式的信度结果
        hr_results: 高信度模式的信度结果
    """
    print(f"\n{'='*100}")
    print(f"对比分析".center(100))
    print(f"{'='*100}\n")

    if not random_results or not hr_results:
        print("  ⚠️ 缺少信度数据，无法对比")
        return

    print(f"{'维度':<20} {'随机模式 α':<15} {'高信度模式 α':<15} {'提升幅度':<15} {'评估':<20}")
    print("-" * 100)

    total_improvement = 0
    count = 0

    for dim_name in random_results.keys():
        if dim_name not in hr_results:
            continue

        random_alpha = random_results[dim_name].cronbach_alpha
        hr_alpha = hr_results[dim_name].cronbach_alpha

        improvement = hr_alpha - random_alpha
        relative_improvement = (hr_alpha / random_alpha - 1) * 100 if random_alpha > 0 else 0

        # 评估
        if hr_alpha >= 0.8 and random_alpha < 0.6:
            assessment = "🎉 显著提升"
        elif hr_alpha >= 0.8:
            assessment = "✅ 达标"
        elif improvement > 0.2:
            assessment = "📈 明显改善"
        else:
            assessment = "⚠️ 需要优化"

        print(f"{dim_name:<20} {random_alpha:<15.4f} {hr_alpha:<15.4f} "
              f"{improvement:>+6.4f} ({relative_improvement:>+6.1f}%)  {assessment:<20}")

        total_improvement += improvement
        count += 1

    if count > 0:
        avg_improvement = total_improvement / count
        print("-" * 100)
        print(f"{'平均':<20} {'':<15} {'':<15} {avg_improvement:>+6.4f}  ")
        print()

        # 总结
        print("【总结】")
        if avg_improvement >= 0.3:
            print("  ✅ 高信度模式显著提升了量表信度，达到学术研究标准（α ≥ 0.8）")
        elif avg_improvement >= 0.2:
            print("  ✅ 高信度模式明显改善了量表信度")
        else:
            print("  ⚠️ 提升有限，可能需要调整画像生成参数")


async def main(url: str):
    """主测试流程

    Args:
        url: 问卷URL
    """
    print("""
╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                  Phase 6: 高信度模式集成测试                                        ║
║                                                                                                  ║
║  测试流程:                                                                                        ║
║    1. 分析问卷获取Schema                                                                          ║
║    2. 测试随机生成模式（旧系统）                                                                  ║
║    3. 测试高信度模式（画像驱动）                                                                  ║
║    4. 对比两种模式的信效度                                                                        ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        # 步骤1: 获取并分析问卷
        schema = await fetch_questionnaire_schema(url)

        # 步骤2: 测试随机模式
        random_answers, random_results = test_random_mode(schema, count=50)

        # 步骤3: 测试高信度模式
        hr_answers, personas, hr_results = test_high_reliability_mode(schema, count=50)

        # 步骤4: 对比结果
        compare_results(random_results, hr_results)

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

    parser = argparse.ArgumentParser(description='Phase 6 高信度模式集成测试')
    parser.add_argument('url', type=str, nargs='?',
                       default='https://v.wjx.cn/vm/eLeS3jD.aspx',
                       help='问卷URL（默认使用测试问卷）')
    parser.add_argument('--count', type=int, default=50,
                       help='生成答案数量（默认50）')

    args = parser.parse_args()

    print(f"测试问卷: {args.url}")
    print(f"样本数量: {args.count}\n")

    success = asyncio.run(main(args.url))
    sys.exit(0 if success else 1)
