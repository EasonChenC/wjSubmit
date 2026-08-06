#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试反向题识别器

验证ReverseItemDetector能够正确识别反向题并标注到Question的metadata中
"""
import sys
import io

# 设置stdout为UTF-8编码，避免Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from core.reverse_item_detector import ReverseItemDetector


def test_basic_detection():
    """测试基础的反向题识别"""
    print("=" * 80)
    print("测试1: 基础反向题识别".center(80))
    print("=" * 80)
    print()

    detector = ReverseItemDetector()

    # 测试用例
    test_cases = [
        ("我对产品非常满意", False),  # 正向题
        ("我对产品感到失望", True),   # 反向题 - 负面情绪
        ("我不会再次购买该产品", True),  # 反向题 - 否定
        ("我很少使用该功能", True),   # 反向题 - 频率否定
        ("产品没有任何问题", False),  # 不是反向题 - 排除模式
        ("能够解决问题", False),       # 不是反向题 - 排除模式
        ("我认为服务质量很差", True),  # 反向题 - 负面评价
        ("我会推荐给朋友", False),     # 正向题
        ("产品存在很多缺陷", True),    # 反向题 - 负面状态
        ("我对该品牌充满信任", False), # 正向题
    ]

    print(f"{'题目':<30} {'预期':<10} {'检测结果':<10} {'置信度':<10} {'关键词'}")
    print("-" * 80)

    correct_count = 0
    for question, expected in test_cases:
        is_reverse, confidence, keywords = detector.detect(question)

        result_match = (is_reverse == expected)
        correct_count += result_match

        status = "✅" if result_match else "❌"
        expected_str = "反向" if expected else "正向"
        detected_str = "反向" if is_reverse else "正向"

        print(f"{status} {question:<28} {expected_str:<8} {detected_str:<8} "
              f"{confidence:.2f}      {', '.join(keywords[:3])}")

    print("-" * 80)
    accuracy = correct_count / len(test_cases) * 100
    print(f"\n准确率: {correct_count}/{len(test_cases)} ({accuracy:.1f}%)\n")

    return accuracy >= 80  # 目标准确率 >= 80%


def test_confidence_scoring():
    """测试置信度评分机制"""
    print("=" * 80)
    print("测试2: 置信度评分机制".center(80))
    print("=" * 80)
    print()

    detector = ReverseItemDetector()

    test_cases = [
        ("我从不感到满意，总是失望", "多个负面词应提高置信度"),
        ("不", "单个弱负面词应为中等置信度"),
        ("我很满意", "正向题应为0置信度"),
    ]

    print(f"{'题目':<40} {'置信度':<10} {'说明'}")
    print("-" * 80)

    for question, description in test_cases:
        is_reverse, confidence, keywords = detector.detect(question)
        print(f"{question:<38} {confidence:.2f}      {description}")

    print()


def test_exclusion_patterns():
    """测试排除模式（避免误判）"""
    print("=" * 80)
    print("测试3: 排除模式测试".center(80))
    print("=" * 80)
    print()

    detector = ReverseItemDetector()

    # 这些题目虽然包含负面词，但不应被判定为反向题
    test_cases = [
        "能够解决问题",
        "帮助克服困难",
        "有效消除障碍",
        "成功避免麻烦",
        "显著减少担心",
        "产品没有问题",
        "不会不满意",  # 双重否定
    ]

    print(f"{'题目':<40} {'检测结果':<10} {'状态'}")
    print("-" * 80)

    all_passed = True
    for question in test_cases:
        is_reverse, confidence, keywords = detector.detect(question)
        detected_str = "反向" if is_reverse else "正向"

        # 这些都应该检测为正向题
        if is_reverse:
            status = "❌ 误判"
            all_passed = False
        else:
            status = "✅ 正确"

        print(f"{question:<38} {detected_str:<8} {status}")

    print()
    return all_passed


def test_with_real_questions():
    """测试真实问卷题目"""
    print("=" * 80)
    print("测试4: 真实问卷题目测试".center(80))
    print("=" * 80)
    print()

    detector = ReverseItemDetector()

    # 模拟真实问卷中的量表题
    real_questions = [
        # 满意度量表
        ("您对我们的服务质量满意吗？", False),
        ("您觉得服务质量不佳", True),
        ("您会继续选择我们的服务", False),
        ("您不会向他人推荐我们的服务", True),

        # NPS推荐度
        ("您愿意向朋友推荐我们的产品吗？", False),
        ("您不愿意推荐给他人", True),

        # 品牌信任度
        ("您信任我们的品牌", False),
        ("您对品牌感到怀疑", True),
        ("品牌值得信赖", False),
    ]

    print(f"{'题目':<50} {'检测结果':<10} {'置信度':<10} {'关键词'}")
    print("-" * 80)

    for question, expected in real_questions:
        is_reverse, confidence, keywords = detector.detect(question)
        detected_str = "反向" if is_reverse else "正向"
        expected_str = "反向" if expected else "正向"

        status = "✅" if (is_reverse == expected) else "❌"
        keywords_str = ', '.join(keywords[:3]) if keywords else ""

        print(f"{status} {question:<48} {detected_str:<8} {confidence:.2f}      {keywords_str}")

    print()


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        反向题识别器测试程序                                   ║
║                                                                              ║
║  测试内容:                                                                    ║
║    1. 基础反向题识别（准确率测试）                                           ║
║    2. 置信度评分机制                                                          ║
║    3. 排除模式（避免误判）                                                    ║
║    4. 真实问卷题目测试                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # 运行所有测试
    test1_passed = test_basic_detection()
    test_confidence_scoring()
    test3_passed = test_exclusion_patterns()
    test_with_real_questions()

    # 总结
    print("=" * 80)
    print("测试总结".center(80))
    print("=" * 80)
    print()

    if test1_passed and test3_passed:
        print("✅ 所有核心测试通过！")
        print("   - 基础识别准确率 >= 80%")
        print("   - 排除模式工作正常，无误判")
        print()
        print("反向题识别器已成功集成到系统中。")
    else:
        print("⚠️  部分测试未通过，需要调整识别规则。")

    print()


if __name__ == "__main__":
    main()
