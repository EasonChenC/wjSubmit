"""
端到端测试 - 动态问卷系统

测试完整流程：
1. 规则引擎分析问卷
2. 动态生成答案
3. 动态填写表单
4. 提交问卷

验证系统对不同问卷的自动适配能力。
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright
import json
import time
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.dynamic_submitter import DynamicSubmitter


async def test_end_to_end(url: str, headless: bool = False):
    """端到端测试单个问卷

    Args:
        url: 问卷URL
        headless: 是否使用无头模式
    """
    print(f"\n{'=' * 80}")
    print(f"端到端测试".center(80))
    print(f"{'=' * 80}")
    print(f"📋 问卷URL: {url}")
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    start_time = time.time()

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()

        try:
            # ========== 步骤1: 获取HTML并分析问卷 ==========
            print(f"🔍 步骤1: 分析问卷结构...")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            html = await page.content()

            analyzer = RuleBasedAnalyzer()
            schema = analyzer.analyze(html, url)

            print(f"  ✅ 问卷分析完成")
            print(f"     - 活动ID: {schema.activity_id}")
            print(f"     - 题目数量: {len(schema.questions)}")
            print(f"     - 题型分布: {schema.metadata['identified_types']}")

            # 保存Schema
            schema_file = Path(__file__).parent / f"schema_{schema.activity_id}.json"
            with open(schema_file, 'w', encoding='utf-8') as f:
                json.dump(schema.to_dict(), f, ensure_ascii=False, indent=2)
            print(f"     - Schema已保存: {schema_file.name}")

            # ========== 步骤2: 动态生成答案 ==========
            print(f"\n🎲 步骤2: 动态生成答案...")
            generator = DynamicAnswerGenerator(schema)
            answers = generator.generate_answers()

            print(f"  ✅ 答案生成完成，共 {len(answers)} 题")

            # 显示部分答案（前5题）
            print(f"     答案示例（前5题）:")
            for i, (q_id, answer) in enumerate(list(answers.items())[:5], 1):
                # 跳过元数据
                if q_id.startswith('__'):
                    continue
                # 简化显示复杂答案
                if isinstance(answer, list) and len(str(answer)) > 50:
                    answer_str = f"[{len(answer)}项]"
                else:
                    answer_str = str(answer)
                print(f"     - {q_id}: {answer_str}")

            # 保存答案
            answers_file = Path(__file__).parent / f"answers_{schema.activity_id}.json"
            with open(answers_file, 'w', encoding='utf-8') as f:
                json.dump(answers, f, ensure_ascii=False, indent=2)
            print(f"     - 答案已保存: {answers_file.name}")

            # ========== 步骤3: 动态填写表单 ==========
            print(f"\n✍️  步骤3: 动态填写表单...")

            submitter = DynamicSubmitter(schema)

            fill_start = time.time()
            success = await submitter.fill_and_submit(page, answers)
            fill_duration = time.time() - fill_start

            if success:
                print(f"  ✅ 表单填写并提交成功 (耗时: {fill_duration:.1f}秒)")
            else:
                print(f"  ❌ 表单提交失败 (耗时: {fill_duration:.1f}秒)")

            # ========== 步骤4: 截图保存 ==========
            print(f"\n📸 步骤4: 保存截图...")
            screenshot_file = Path(__file__).parent / f"screenshot_{schema.activity_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=str(screenshot_file), full_page=True)
            print(f"  ✅ 截图已保存: {screenshot_file.name}")

            # ========== 汇总结果 ==========
            total_duration = time.time() - start_time

            print(f"\n{'=' * 80}")
            print(f"测试结果".center(80))
            print(f"{'=' * 80}")
            print(f"✅ 状态: {'成功' if success else '失败'}")
            print(f"⏱️  总耗时: {total_duration:.1f}秒")
            print(f"   - 分析问卷: ~{total_duration - fill_duration:.1f}秒")
            print(f"   - 填写提交: {fill_duration:.1f}秒")
            print(f"📋 题目数量: {len(schema.questions)}")
            print(f"🎯 识别覆盖率: {(len(schema.questions) - schema.metadata['identified_types'].get('unknown', 0)) / len(schema.questions) * 100:.1f}%")

            return success

        except Exception as e:
            print(f"\n❌ 测试失败: {str(e)}")
            import traceback
            print(f"\n详细错误:\n{traceback.format_exc()}")

            # 错误截图
            try:
                error_screenshot = Path(__file__).parent / f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=str(error_screenshot), full_page=True)
                print(f"📸 错误截图已保存: {error_screenshot.name}")
            except:
                pass

            return False

        finally:
            await browser.close()


async def test_multiple_questionnaires():
    """测试多个问卷的端到端流程"""
    print(f"{'#' * 80}")
    print(f"动态问卷系统 - 端到端测试套件".center(80))
    print(f"{'#' * 80}\n")

    # 测试问卷列表
    test_urls = [
        # 'https://v.wjx.cn/vm/rqKTYry.aspx',  # 原测试问卷（电商购物调查）
        # # 可以添加更多问卷URL
        # 'https://v.wjx.cn/vm/OttQbAd.aspx',
        # 'https://v.wjx.cn/vm/PAmhbrG.aspx?code=001KAR1w3dtos73VNy0w3QwzKg4KAR1S&state=sojump',
        # 'https://v.wjx.cn/vm/mbskTjX.aspx',
        # 'https://v.wjx.cn/vm/t0HAQeM.aspx',
        # 'https://v.wjx.cn/vm/t3tsMH5.aspx',
        # 'https://v.wjx.cn/vm/wt2CCPO.aspx',
        # 'https://v.wjx.cn/vm/euSY97y.aspx',
        # 'https://v.wjx.cn/vm/mBbgXsD.aspx?code=021MuD100x5aQW1PhT100qgMh90MuD1n&state=sojump',
        # 'https://v.wjx.cn/vm/mBbgXsD.aspx?code=021MuD100x5aQW1PhT100qgMh90MuD1n&state=sojump',
        # 'https://v.wjx.cn/vm/QmOx0wu.aspx',
        # 'https://v.wjx.cn/vm/OUt2yeM.aspx',
        'https://ks.wjx.com/vm/rsRj1YB.aspx',
    ]

    results = []

    for i, url in enumerate(test_urls, 1):
        print(f"\n{'#' * 80}")
        print(f"测试 {i}/{len(test_urls)}".center(80))
        print(f"{'#' * 80}")

        success = await test_end_to_end(url, headless=False)
        results.append({'url': url, 'success': success})

        # 每个问卷测试后暂停
        if i < len(test_urls):
            print(f"\n⏸️  暂停3秒后继续下一个问卷...\n")
            await asyncio.sleep(3)

    # 汇总统计
    print(f"\n\n{'=' * 80}")
    print(f"测试汇总".center(80))
    print(f"{'=' * 80}")

    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)

    print(f"\n📊 测试结果:")
    print(f"  总数: {total_count}")
    print(f"  成功: {success_count}")
    print(f"  失败: {total_count - success_count}")
    print(f"  成功率: {success_count/total_count*100:.1f}%")

    print(f"\n📋 详细结果:")
    for i, result in enumerate(results, 1):
        status = "✅ 成功" if result['success'] else "❌ 失败"
        print(f"  {i}. {status} - {result['url']}")

    if success_count == total_count:
        print(f"\n🎉 完美！所有问卷测试通过！")
        return True
    elif success_count >= total_count * 0.8:
        print(f"\n✅ 良好！大部分问卷测试通过。")
        return True
    else:
        print(f"\n⚠️  需要改进，部分问卷测试失败。")
        return False


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='动态问卷系统端到端测试')
    parser.add_argument('--url', type=str, help='单个问卷URL')
    parser.add_argument('--headless', action='store_true', help='使用无头模式')
    parser.add_argument('--batch', action='store_true', help='批量测试多个问卷')

    args = parser.parse_args()

    try:
        if args.batch:
            # 批量测试
            success = await test_multiple_questionnaires()
        elif args.url:
            # 单个测试
            success = await test_end_to_end(args.url, args.headless)
        else:
            # 默认：测试原问卷
            success = await test_end_to_end(
                'https://v.wjx.cn/vm/rqKTYry.aspx',
                headless=False
            )

        return 0 if success else 1

    except Exception as e:
        print(f"\n❌ 测试异常: {str(e)}")
        import traceback
        print(f"\n详细错误:\n{traceback.format_exc()}")
        return 1


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         动态问卷系统 - 端到端测试                              ║
║                                                                              ║
║  测试流程:                                                                    ║
║    1. 规则引擎分析问卷 → 生成Schema                                          ║
║    2. 动态答案生成器 → 生成答案                                              ║
║    3. 动态表单填写器 → 填写并提交                                            ║
║                                                                              ║
║  用法:                                                                       ║
║    python test_dynamic_system.py                    # 测试默认问卷            ║
║    python test_dynamic_system.py --url <URL>        # 测试指定问卷            ║
║    python test_dynamic_system.py --batch            # 批量测试                ║
║    python test_dynamic_system.py --headless         # 无头模式                ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
