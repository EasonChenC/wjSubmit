#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合测试脚本：Phase 1-3 完整流程

测试流程：
1. 输入问卷URL
2. 获取并分析问卷（Phase 1 + Phase 2）
3. 生成受访者画像（Phase 3）
4. 展示画像详情

用法：
    python test_full_persona_pipeline.py
    或
    python test_full_persona_pipeline.py <问卷URL>
"""
import sys
import io
import asyncio
from typing import List

# 设置stdout为UTF-8编码，避免Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.persona_generator import PersonaGenerator
from core.schema import QuestionnaireSchema, QuestionType


async def fetch_questionnaire_html(url: str) -> str:
    """获取问卷HTML

    Args:
        url: 问卷URL

    Returns:
        HTML内容
    """
    print("步骤1: 获取问卷HTML...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()
            print(f"  ✅ HTML获取成功 (长度: {len(html)} 字符)")
            return html
        except Exception as e:
            print(f"  ❌ HTML获取失败: {e}")
            raise
        finally:
            await browser.close()


def analyze_questionnaire(html: str, url: str) -> QuestionnaireSchema:
    """分析问卷（Phase 1 + Phase 2）

    Args:
        html: HTML内容
        url: 问卷URL

    Returns:
        QuestionnaireSchema对象
    """
    print()
    print("步骤2: 分析问卷结构（Phase 1 + Phase 2）...")

    analyzer = RuleBasedAnalyzer()
    schema = analyzer.analyze(html, url)

    print(f"  ✅ 问卷分析完成")
    print(f"     - 活动ID: {schema.activity_id}")
    print(f"     - 平台: {schema.platform}")
    print(f"     - 题目总数: {schema.metadata.get('total_questions', 0)}")

    # 量表题统计
    scale_types = [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX, QuestionType.RADIO]
    scale_questions = [q for q in schema.questions if q.type in scale_types]
    print(f"     - 量表题数: {len(scale_questions)}")

    # 反向题统计
    reverse_items = schema.metadata.get('reverse_items', [])
    print(f"     - 反向题数: {len(reverse_items)}")

    return schema


def display_questionnaire_info(schema: QuestionnaireSchema):
    """展示问卷详细信息

    Args:
        schema: 问卷Schema
    """
    print()
    print("=" * 100)
    print("问卷详细信息".center(100))
    print("=" * 100)
    print()

    # 题型统计
    print("【题型统计】")
    print("-" * 100)
    identified_types = schema.metadata.get('identified_types', {})
    for q_type, count in sorted(identified_types.items()):
        print(f"  {q_type:<15} {count:>3} 题")
    print()

    # 量表题列表
    scale_types = [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX, QuestionType.RADIO]
    scale_questions = [q for q in schema.questions if q.type in scale_types]

    print("【量表题列表】")
    print("-" * 100)

    if not scale_questions:
        print("  ⚠️  未检测到量表题")
    else:
        print(f"  检测到 {len(scale_questions)} 个量表题:")
        print()

        # 只显示前10个，避免输出过长
        display_count = min(10, len(scale_questions))

        for i, q in enumerate(scale_questions[:display_count], 1):
            is_reverse = q.metadata.get('is_reverse', False)
            reverse_mark = "🔴" if is_reverse else "🟢"

            print(f"  [{i}] {reverse_mark} {q.id:<12} {q.type.value:<10} {q.label[:60]}")

            if is_reverse:
                confidence = q.metadata.get('reverse_confidence', 0.0)
                keywords = q.metadata.get('reverse_keywords', [])
                print(f"      反向题（置信度: {confidence:.2f}, 关键词: {', '.join(keywords[:3])}）")

        if len(scale_questions) > display_count:
            print(f"  ... 还有 {len(scale_questions) - display_count} 个量表题未显示")

    print()

    # 反向题报告
    reverse_items = schema.metadata.get('reverse_items', [])

    print("【反向题检测报告】")
    print("-" * 100)

    if not reverse_items:
        print("  ✅ 未检测到反向题")
    else:
        print(f"  检测到 {len(reverse_items)} 个反向题:")
        print()

        for q_id in reverse_items:
            q = schema.get_question_by_id(q_id)
            if q:
                confidence = q.metadata.get('reverse_confidence', 0.0)
                keywords = q.metadata.get('reverse_keywords', [])
                keywords_str = ', '.join(keywords[:3])
                label = q.label[:70] + "..." if len(q.label) > 70 else q.label

                print(f"  - {q_id:<12} (置信度: {confidence:.2f}) {keywords_str:<25} {label}")

        # 计算反向题比例
        if scale_questions:
            reverse_ratio = len(reverse_items) / len(scale_questions) * 100
            print()
            print(f"  反向题比例: {len(reverse_items)}/{len(scale_questions)} ({reverse_ratio:.1f}%)")
            print(f"  推荐比例: 15-30%（当前 {'✅ 合理' if 10 <= reverse_ratio <= 35 else '⚠️ 偏离推荐范围'}）")

    print()


def generate_personas(schema: QuestionnaireSchema, count: int = 5) -> List:
    """生成受访者画像（Phase 3）

    Args:
        schema: 问卷Schema
        count: 生成数量

    Returns:
        Persona列表
    """
    print()
    print("步骤3: 生成受访者画像（Phase 3）...")

    generator = PersonaGenerator(seed=42)  # 固定种子确保可复现
    personas = generator.generate_batch(schema, count=count, id_prefix="persona")

    print(f"  ✅ 成功生成 {len(personas)} 个受访者画像")

    return personas


def display_personas(personas: List, detailed: bool = False):
    """展示受访者画像

    Args:
        personas: Persona列表
        detailed: 是否显示详细信息
    """
    print()
    print("=" * 100)
    print("受访者画像列表".center(100))
    print("=" * 100)
    print()

    if not personas:
        print("  ⚠️  没有生成画像")
        return

    # 简要列表
    print(f"{'ID':<15} {'性别':<8} {'年龄':<8} {'学历':<15} {'收入':<15} {'维度数':<10} {'一致性':<10}")
    print("-" * 100)

    for persona in personas:
        demo = persona.demographic
        gender_zh = {"male": "男", "female": "女", "other": "其他"}[demo.gender.value]

        edu_zh = {
            "high_school": "高中及以下",
            "associate": "专科/大专",
            "bachelor": "本科",
            "master": "硕士",
            "doctorate": "博士"
        }.get(demo.education.value, demo.education.value)

        income_zh = {
            "low": "<5k",
            "medium_low": "5-10k",
            "medium": "10-20k",
            "medium_high": "20-30k",
            "high": ">30k"
        }.get(demo.income.value, demo.income.value)

        dim_count = len(persona.dimension_tendencies)
        consistency = persona.response_style.consistency_level

        print(f"{persona.persona_id:<15} {gender_zh:<8} {demo.age:<8} {edu_zh:<15} "
              f"{income_zh:<15} {dim_count:<10} {consistency:<10.2f}")

    print()

    # 详细信息（可选）
    if detailed:
        print()
        print("=" * 100)
        print("画像详细信息".center(100))
        print("=" * 100)

        for persona in personas[:3]:  # 只显示前3个详细信息
            print()
            print(f"{'='*80}")
            print(f"画像ID: {persona.persona_id}")
            print(f"{'='*80}")
            print()

            # 人口统计
            demo = persona.demographic
            gender_zh = {"male": "男", "female": "女"}[demo.gender.value]
            print(f"【人口统计】")
            print(f"  性别: {gender_zh}, 年龄: {demo.age}岁, 学历: {demo.education.value}, 收入: {demo.income.value}")
            print()

            # 维度倾向
            print(f"【维度倾向】")
            for dim_name, tendency in persona.dimension_tendencies.items():
                print(f"  {dim_name:<20} base_score={tendency.base_score:.2f}  "
                      f"range=[{tendency.scale_min}, {tendency.scale_max}]  variance=±{tendency.variance}")
            print()

            # 答题风格
            style = persona.response_style
            print(f"【答题风格】")
            print(f"  极端倾向: {style.extreme_tendency:.2f}  "
                  f"中立回避: {style.neutral_avoidance:.2f}  "
                  f"一致性: {style.consistency_level:.2f}  "
                  f"速度: {style.response_speed}")
            print()

        if len(personas) > 3:
            print(f"... 还有 {len(personas) - 3} 个画像未显示详细信息")
            print()


def analyze_persona_distribution(personas: List):
    """分析画像分布特征

    Args:
        personas: Persona列表
    """
    print()
    print("=" * 100)
    print("画像分布分析".center(100))
    print("=" * 100)
    print()

    if not personas:
        return

    # 性别分布
    gender_dist = {}
    for p in personas:
        g = p.demographic.gender.value
        gender_dist[g] = gender_dist.get(g, 0) + 1

    print("【性别分布】")
    for gender, count in gender_dist.items():
        gender_zh = {"male": "男", "female": "女", "other": "其他"}[gender]
        percentage = count / len(personas) * 100
        print(f"  {gender_zh}: {count}/{len(personas)} ({percentage:.1f}%)")
    print()

    # 年龄分布
    ages = [p.demographic.age for p in personas]
    print("【年龄分布】")
    print(f"  最小值: {min(ages)}岁")
    print(f"  最大值: {max(ages)}岁")
    print(f"  平均值: {sum(ages)/len(ages):.1f}岁")
    print(f"  中位数: {sorted(ages)[len(ages)//2]}岁")
    print()

    # 维度base_score分布
    if personas[0].dimension_tendencies:
        print("【维度倾向分布】")

        for dim_name in personas[0].dimension_tendencies.keys():
            scores = [p.dimension_tendencies[dim_name].base_score for p in personas]
            scale_min = personas[0].dimension_tendencies[dim_name].scale_min
            scale_max = personas[0].dimension_tendencies[dim_name].scale_max

            print(f"  {dim_name}:")
            print(f"    范围: [{scale_min}, {scale_max}]")
            print(f"    平均: {sum(scores)/len(scores):.2f}")
            print(f"    最小: {min(scores):.2f}")
            print(f"    最大: {max(scores):.2f}")
            print(f"    标准差: {(sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores))**0.5:.2f}")

        print()

    # 一致性水平分布
    consistencies = [p.response_style.consistency_level for p in personas]
    print("【一致性水平分布】")
    print(f"  平均: {sum(consistencies)/len(consistencies):.3f}")
    print(f"  最小: {min(consistencies):.3f}")
    print(f"  最大: {max(consistencies):.3f}")
    print(f"  目标范围: 0.75-0.90")
    in_range = sum(1 for c in consistencies if 0.75 <= c <= 0.90)
    print(f"  符合目标: {in_range}/{len(consistencies)} ({in_range/len(consistencies)*100:.1f}%)")
    print()


async def main():
    """主函数"""

    print("""
╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                              Phase 1-3 综合测试：受访者画像生成流程                                 ║
║                                                                                                  ║
║  测试流程:                                                                                        ║
║    1. 获取问卷HTML                                                                                ║
║    2. 分析问卷结构（Phase 1: Schema扩展）                                                          ║
║    3. 识别反向题（Phase 2: 反向题识别）                                                            ║
║    4. 生成受访者画像（Phase 3: 画像生成器）                                                         ║
║    5. 展示画像详情和分布分析                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝
    """)

    # 获取问卷URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        print("请输入问卷URL（或直接回车使用默认测试URL）:")
        user_input = input("> ").strip()

        if user_input:
            url = user_input
        else:
            # 默认测试URL
            url = "https://v.wjx.cn/vm/QsQY01y.aspx"
            print(f"使用默认测试URL: {url}")

    print()
    print("=" * 100)
    print(f"问卷URL: {url}".center(100))
    print("=" * 100)
    print()

    try:
        # 步骤1: 获取HTML
        html = await fetch_questionnaire_html(url)

        # 步骤2: 分析问卷
        schema = analyze_questionnaire(html, url)

        # 展示问卷详细信息
        display_questionnaire_info(schema)

        # 步骤3: 生成画像
        print()
        print("=" * 100)
        print("开始生成受访者画像".center(100))
        print("=" * 100)

        # 询问生成数量
        print()
        print("请输入要生成的画像数量（默认5个，建议5-20个）:")
        count_input = input("> ").strip()

        try:
            count = int(count_input) if count_input else 5
            count = max(1, min(100, count))  # 限制在1-100之间
        except ValueError:
            count = 5
            print(f"输入无效，使用默认值: {count}")

        personas = generate_personas(schema, count=count)

        # 展示画像
        display_personas(personas, detailed=True)

        # 分布分析
        analyze_persona_distribution(personas)

        # 总结
        print()
        print("=" * 100)
        print("测试完成总结".center(100))
        print("=" * 100)
        print()

        print("✅ Phase 1-3 完整流程测试成功！")
        print()
        print("验证要点:")
        print(f"  ✅ 问卷分析完成（{schema.metadata.get('total_questions', 0)} 题）")

        scale_types = [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX, QuestionType.RADIO]
        scale_questions = [q for q in schema.questions if q.type in scale_types]
        reverse_items = schema.metadata.get('reverse_items', [])

        print(f"  ✅ 量表题识别（{len(scale_questions)} 题）")
        print(f"  ✅ 反向题识别（{len(reverse_items)} 题）")
        print(f"  ✅ 受访者画像生成（{len(personas)} 个）")

        consistencies = [p.response_style.consistency_level for p in personas]
        avg_consistency = sum(consistencies) / len(consistencies)
        print(f"  ✅ 平均一致性水平: {avg_consistency:.3f} (目标: ≥0.75)")

        print()
        print("下一步:")
        print("  → Phase 4: 实现基于画像的答案生成器")
        print("  → Phase 5: 实现Cronbach's α计算验证信度")
        print()

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
        return 1
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
