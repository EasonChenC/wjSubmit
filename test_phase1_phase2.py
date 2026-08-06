#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Phase 1 和 Phase 2 功能

测试内容：
1. Phase 1: Schema扩展（DimensionType枚举、metadata字段）
2. Phase 2: 反向题自动识别和标注

用法：
    python test_phase1_phase2.py
    或
    python test_phase1_phase2.py <问卷URL>
"""
import sys
import io
import asyncio
from typing import List

# 设置stdout为UTF-8编码，避免Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.schema import Question, QuestionType


async def analyze_questionnaire(url: str):
    """分析问卷并展示反向题识别结果"""

    print("=" * 100)
    print("Phase 1 & Phase 2 功能测试".center(100))
    print("=" * 100)
    print()

    print(f"问卷URL: {url}")
    print()

    # 步骤1: 获取问卷HTML
    print("步骤1: 获取问卷HTML...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()
            print(f"  ✅ HTML获取成功 (长度: {len(html)} 字符)")
        except Exception as e:
            print(f"  ❌ HTML获取失败: {e}")
            await browser.close()
            return
        finally:
            await browser.close()

    print()

    # 步骤2: 分析问卷（自动触发反向题识别）
    print("步骤2: 分析问卷结构（自动识别反向题）...")
    analyzer = RuleBasedAnalyzer()
    schema = analyzer.analyze(html, url)

    print(f"  ✅ 问卷分析完成")
    print(f"     - 活动ID: {schema.activity_id}")
    print(f"     - 平台: {schema.platform}")
    print(f"     - 题目总数: {schema.metadata.get('total_questions', 0)}")
    print()

    # 步骤3: 展示题型统计
    print("步骤3: 题型统计")
    print("-" * 100)
    identified_types = schema.metadata.get('identified_types', {})
    for q_type, count in identified_types.items():
        print(f"  {q_type:<15} {count:>3} 题")
    print()

    # 步骤4: 展示量表题列表
    print("步骤4: 量表题列表（RATING, NPS, MATRIX, RADIO）")
    print("-" * 100)

    scale_types = [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX, QuestionType.RADIO]
    scale_questions = [q for q in schema.questions if q.type in scale_types]

    if not scale_questions:
        print("  ⚠️  未检测到量表题")
        print()
    else:
        print(f"  检测到 {len(scale_questions)} 个量表题:")
        print()

        for i, q in enumerate(scale_questions, 1):
            print(f"  [{i}] ID: {q.id}")
            print(f"      题型: {q.type.value}")
            print(f"      题目: {q.label[:80]}")
            print(f"      选项: {q.options}")

            # 显示metadata中的is_reverse字段
            is_reverse = q.metadata.get('is_reverse', False)
            if is_reverse:
                confidence = q.metadata.get('reverse_confidence', 0.0)
                keywords = q.metadata.get('reverse_keywords', [])
                print(f"      🔴 反向题 (置信度: {confidence:.2f}, 关键词: {', '.join(keywords[:3])})")
            else:
                print(f"      🟢 正向题")

            print()

    # 步骤5: 反向题检测报告
    print("步骤5: 反向题检测报告")
    print("=" * 100)

    reverse_items = schema.metadata.get('reverse_items', [])

    if not reverse_items:
        print("  ✅ 未检测到反向题")
        print()
    else:
        print(f"  检测到 {len(reverse_items)} 个反向题:")
        print()
        print(f"  {'题目ID':<12} {'题型':<12} {'置信度':<10} {'关键词':<30} {'题目内容'}")
        print("-" * 100)

        for q_id in reverse_items:
            q = schema.get_question_by_id(q_id)
            if q:
                confidence = q.metadata.get('reverse_confidence', 0.0)
                keywords = q.metadata.get('reverse_keywords', [])
                keywords_str = ', '.join(keywords[:3])
                label = q.label[:50] + "..." if len(q.label) > 50 else q.label

                print(f"  {q_id:<12} {q.type.value:<12} {confidence:<10.2f} {keywords_str:<30} {label}")

        print()

        # 计算反向题比例
        total_scale = len(scale_questions)
        if total_scale > 0:
            reverse_ratio = len(reverse_items) / total_scale * 100
            print(f"  反向题比例: {len(reverse_items)}/{total_scale} ({reverse_ratio:.1f}%)")
            print()

    # 步骤6: 验证Phase 1扩展的metadata字段
    print("步骤6: Schema Metadata验证 (Phase 1)")
    print("-" * 100)
    print(f"  schema.metadata 包含的字段:")
    for key, value in schema.metadata.items():
        if key == 'reverse_items':
            print(f"    ✅ {key}: {len(value)} 个反向题")
        elif key == 'identified_types':
            print(f"    ✅ {key}: {len(value)} 种题型")
        else:
            print(f"    ✅ {key}: {value}")
    print()

    # 步骤7: 验证Question.metadata字段
    print("步骤7: Question Metadata验证 (Phase 1)")
    print("-" * 100)

    # 随机检查几个量表题的metadata
    sample_questions = scale_questions[:3] if len(scale_questions) >= 3 else scale_questions

    if sample_questions:
        print(f"  随机抽样 {len(sample_questions)} 个量表题的metadata:")
        print()

        for q in sample_questions:
            print(f"  题目ID: {q.id}")
            print(f"    metadata字段:")
            for key, value in q.metadata.items():
                if key == 'reverse_keywords':
                    print(f"      - {key}: {', '.join(value[:3])}")
                else:
                    print(f"      - {key}: {value}")
            print()
    else:
        print("  ⚠️  没有量表题可供检查")
        print()

    # 总结
    print("=" * 100)
    print("测试总结".center(100))
    print("=" * 100)
    print()

    phase1_passed = True
    phase2_passed = True

    # Phase 1 验证
    print("Phase 1 验证 (Schema扩展):")
    if 'reverse_items' in schema.metadata:
        print("  ✅ schema.metadata['reverse_items'] 字段存在")
    else:
        print("  ❌ schema.metadata['reverse_items'] 字段缺失")
        phase1_passed = False

    if scale_questions:
        if 'is_reverse' in scale_questions[0].metadata:
            print("  ✅ Question.metadata['is_reverse'] 字段存在")
        else:
            print("  ❌ Question.metadata['is_reverse'] 字段缺失")
            phase1_passed = False

    print()

    # Phase 2 验证
    print("Phase 2 验证 (反向题识别):")
    if scale_questions:
        reverse_count = len([q for q in scale_questions if q.metadata.get('is_reverse', False)])
        print(f"  ✅ 反向题识别器已运行，检测到 {reverse_count} 个反向题")

        # 检查是否有置信度和关键词
        reverse_with_confidence = [q for q in scale_questions
                                   if q.metadata.get('is_reverse', False)
                                   and 'reverse_confidence' in q.metadata]
        if reverse_with_confidence:
            print(f"  ✅ 反向题包含置信度和关键词信息")
        else:
            if reverse_count > 0:
                print(f"  ⚠️  反向题缺少置信度信息")
    else:
        print("  ⚠️  没有量表题，无法验证反向题识别")
        phase2_passed = False

    print()
    print("-" * 100)

    if phase1_passed and phase2_passed:
        print("✅ Phase 1 和 Phase 2 功能正常！".center(100))
    else:
        print("⚠️  部分功能异常，请检查".center(100))

    print()

    return schema


async def main():
    """主函数"""

    print("""
╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   Phase 1 & Phase 2 功能测试                                      ║
║                                                                                                  ║
║  测试内容:                                                                                        ║
║    Phase 1: Schema扩展                                                                           ║
║      - DimensionType枚举                                                                         ║
║      - Question.metadata字段（dimension, is_reverse, reverse_confidence, etc.）                  ║
║      - QuestionnaireSchema.metadata字段（reverse_items, dimensions, etc.）                        ║
║                                                                                                  ║
║    Phase 2: 反向题识别                                                                            ║
║      - 自动识别反向题                                                                             ║
║      - 计算置信度                                                                                 ║
║      - 提取匹配关键词                                                                             ║
║      - 自动标注到Question.metadata                                                                ║
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
            url = "https://ks.wjx.com/vm/rsRj1YB.aspx"
            print(f"使用默认测试URL: {url}")

    print()

    try:
        schema = await analyze_questionnaire(url)
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
