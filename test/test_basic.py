# test_basic.py
"""
基础功能测试脚本
用于验证各个模块是否正常工作
"""
import asyncio
from core.answer_generator import AnswerGenerator
from core.browser_manager import BrowserManager

async def test_answer_generator():
    """测试答案生成器"""
    print("=" * 60)
    print("测试答案生成器")
    print("=" * 60)

    generator = AnswerGenerator()
    answers = generator.generate_answers({})
    answers = generator.add_timing_data(answers)

    print("\n生成的答案示例：")
    for key, value in answers.items():
        if key != '_timing':
            print(f"  {key}: {value}")

    print(f"\n答题时间数据：")
    print(f"  开始停留: {answers['_timing']['start_time']}秒")
    print(f"  题目数量: {len(answers['_timing']['answer_times'])}题")

    print("\n✓ 答案生成器测试通过\n")

async def test_browser_manager():
    """测试浏览器管理器"""
    print("=" * 60)
    print("测试浏览器管理器")
    print("=" * 60)

    print("\n正在初始化浏览器池（1个浏览器）...")
    manager = BrowserManager(pool_size=1)
    await manager.initialize()

    print("✓ 浏览器初始化成功")

    # 获取一个上下文并测试
    context = await manager.get_context()
    page = await context.new_page()

    print("正在访问测试页面...")
    await page.goto('https://www.baidu.com')
    title = await page.title()
    print(f"页面标题: {title}")

    await page.close()

    print("正在清理资源...")
    await manager.cleanup()

    print("\n✓ 浏览器管理器测试通过\n")

async def main():
    """运行所有测试"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                  基础功能测试                            ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    try:
        # 测试答案生成器
        await test_answer_generator()

        # 测试浏览器管理器
        await test_browser_manager()

        print("=" * 60)
        print("所有测试通过！ ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
