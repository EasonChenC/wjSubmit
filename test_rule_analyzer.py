"""
测试规则引擎分析器

验证schema和rule_based_analyzer模块的功能：
1. 能否正确解析问卷HTML
2. 能否识别9种题型
3. 能否生成正确的选择器和答案策略
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright
import json

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.rule_based_analyzer import RuleBasedAnalyzer
from core.schema import QuestionType


async def fetch_questionnaire_html(url: str) -> str:
    """获取问卷HTML"""
    print(f"📥 正在获取问卷HTML: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()
            print(f"✅ HTML获取成功，长度: {len(html)} 字符")
            return html
        finally:
            await browser.close()


async def test_analyzer():
    """测试分析器"""
    print("=" * 80)
    print("规则引擎分析器测试".center(80))
    print("=" * 80)

    # 测试问卷URL
    url = 'https://v.wjx.cn/vm/mbskTjX.aspx'

    # 1. 获取HTML
    html = await fetch_questionnaire_html(url)

    # 2. 创建分析器
    analyzer = RuleBasedAnalyzer()

    # 3. 分析问卷
    print(f"\n🔍 开始分析问卷...")
    schema = analyzer.analyze(html, url)

    # 4. 输出结果
    print(f"\n" + "=" * 80)
    print("分析结果".center(80))
    print("=" * 80)

    print(f"\n📋 问卷信息:")
    print(f"  URL: {schema.url}")
    print(f"  活动ID: {schema.activity_id}")
    print(f"  平台: {schema.platform}")
    print(f"  题目数量: {len(schema.questions)}")

    print(f"\n📊 题型统计:")
    type_counts = schema.metadata['identified_types']
    for type_name, count in sorted(type_counts.items()):
        print(f"  {type_name:15s}: {count:2d}")

    print(f"\n📝 题目详情:")
    print("-" * 80)

    for i, question in enumerate(schema.questions, 1):
        print(f"\n[{i}] {question.id} - {question.type.value}")
        print(f"    标签: {question.label[:50]}{'...' if len(question.label) > 50 else ''}")
        print(f"    选项: {question.options}")
        print(f"    必填: {'是' if question.required else '否'}")

        # 选择器
        if question.selector.container:
            print(f"    选择器: {question.selector.container} {question.selector.template}")
        else:
            print(f"    选择器: {question.selector.template}")

        if question.selector.special_handling:
            print(f"    特殊处理: {question.selector.special_handling}")

        # 策略
        print(f"    策略类型: {question.strategy.type}")
        if question.strategy.params:
            params_str = str(question.strategy.params)
            if len(params_str) > 60:
                params_str = params_str[:60] + "..."
            print(f"    策略参数: {params_str}")

        # 元数据
        if question.metadata:
            print(f"    元数据: {question.metadata}")

    # 5. 验证关键题型
    print(f"\n" + "=" * 80)
    print("题型验证".center(80))
    print("=" * 80)

    # 预期的题型
    expected_types = {
        'q1': QuestionType.RADIO,     # 性别
        'q2': QuestionType.SELECT,    # 年龄
        'q3': QuestionType.TEXT,      # 城市
        'q4': QuestionType.RADIO,     # 教育程度
        'q5': QuestionType.RADIO,     # 月收入
        'q6': QuestionType.CHECKBOX,  # 信息来源
        'q7_0': QuestionType.MATRIX,  # 购买因素矩阵（第1行）
        'q8': QuestionType.RADIO,     # 购物频率
        'q9': QuestionType.CHECKBOX,  # 常用平台
        'q10': QuestionType.RATING,   # 满意度
        'q11': QuestionType.NPS,      # NPS推荐度
        'q12': QuestionType.SORT,     # 促销方式排序
        'q13': QuestionType.TEXT,     # 商品类别
        'q14': QuestionType.TEXTAREA, # 问题与建议
    }

    correct = 0
    total = len(expected_types)

    for q_id, expected_type in expected_types.items():
        question = schema.get_question_by_id(q_id)
        if question:
            if question.type == expected_type:
                print(f"✅ {q_id:6s} - {expected_type.value:10s} - 正确")
                correct += 1
            else:
                print(f"❌ {q_id:6s} - 预期: {expected_type.value:10s}, 实际: {question.type.value:10s} - 错误")
        else:
            print(f"❌ {q_id:6s} - 未找到该题目")

    print(f"\n准确率: {correct}/{total} ({correct/total*100:.1f}%)")

    # 6. 保存Schema到JSON文件
    output_file = Path(__file__).parent / "schema_output.json"
    schema_dict = schema.to_dict()
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schema_dict, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Schema已保存到: {output_file.name}")

    # 7. 评估
    print(f"\n" + "=" * 80)
    print("评估".center(80))
    print("=" * 80)

    if correct == total:
        print("🎉 完美！所有题型识别正确！")
        return True
    elif correct >= total * 0.9:
        print(f"✅ 优秀！识别准确率达到 {correct/total*100:.1f}%")
        return True
    elif correct >= total * 0.7:
        print(f"⚠️  良好，识别准确率为 {correct/total*100:.1f}%，仍需优化")
        return False
    else:
        print(f"❌ 识别准确率较低 ({correct/total*100:.1f}%)，需要重点修复")
        return False


async def main():
    """主函数"""
    try:
        success = await test_analyzer()
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        print("\n详细错误:")
        print(traceback.format_exc())
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
