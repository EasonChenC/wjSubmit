"""
问卷星批量提交测试脚本

测试目标：
1. 测试连续多次提交的成功率
2. 统计成功/失败次数
3. 分析失败原因
4. 验证提交间隔是否合理
5. 测试浏览器资源管理
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import json

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.answer_generator import AnswerGenerator
from core.captcha_solver import CaptchaSolver
from core.browser_manager import BrowserManager
from core.submitter import QuestionnaireSubmitter


class BatchSubmissionTester:
    """批量提交测试器"""

    def __init__(self, url: str, total_count: int = 10):
        self.url = url
        self.total_count = total_count
        self.answer_generator = AnswerGenerator()
        self.captcha_solver = CaptchaSolver()
        self.browser_manager = BrowserManager(pool_size=1)

        # 统计数据
        self.results = []
        self.success_count = 0
        self.failed_count = 0
        self.error_count = 0
        self.failure_reasons = {}

    async def run_batch_test(self):
        """运行批量测试"""
        print("=" * 80)
        print("问卷星批量提交测试".center(80))
        print("=" * 80)
        print(f"\n📋 目标问卷: {self.url}")
        print(f"📊 测试数量: {self.total_count} 次")
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        submitter = QuestionnaireSubmitter(
            url=self.url,
            answer_generator=self.answer_generator,
            captcha_solver=self.captcha_solver,
            browser_manager=self.browser_manager
        )

        try:
            # 初始化浏览器
            await self.browser_manager.initialize()

            start_time = datetime.now()

            # 执行批量提交
            for i in range(1, self.total_count + 1):
                print(f"\n{'─' * 80}")
                print(f"📝 第 {i}/{self.total_count} 次提交")
                print(f"{'─' * 80}")

                submit_start = datetime.now()

                try:
                    result = await submitter.submit_one()
                    submit_end = datetime.now()
                    duration = (submit_end - submit_start).total_seconds()

                    # 记录结果
                    result_data = {
                        'index': i,
                        'status': result['status'],
                        'duration': duration,
                        'timestamp': submit_start.strftime('%Y-%m-%d %H:%M:%S'),
                        'final_url': result.get('final_url', ''),
                        'reason': result.get('reason', ''),
                        'error': result.get('error', '')
                    }
                    self.results.append(result_data)

                    # 统计
                    if result['status'] == 'success':
                        self.success_count += 1
                        print(f"✅ 成功 (耗时: {duration:.1f}秒)")
                    elif result['status'] == 'failed':
                        self.failed_count += 1
                        reason = result.get('reason', 'unknown')
                        self.failure_reasons[reason] = self.failure_reasons.get(reason, 0) + 1
                        print(f"❌ 失败: {reason} (耗时: {duration:.1f}秒)")
                    else:
                        self.error_count += 1
                        error = result.get('error', 'unknown')
                        self.failure_reasons[error] = self.failure_reasons.get(error, 0) + 1
                        print(f"⚠️  错误: {error} (耗时: {duration:.1f}秒)")

                    # 显示当前统计
                    print(f"📈 当前统计: 成功 {self.success_count}, 失败 {self.failed_count}, 错误 {self.error_count}")

                except Exception as e:
                    self.error_count += 1
                    error_msg = str(e)
                    self.failure_reasons[error_msg] = self.failure_reasons.get(error_msg, 0) + 1
                    print(f"⚠️  异常: {error_msg}")

                    self.results.append({
                        'index': i,
                        'status': 'error',
                        'duration': 0,
                        'timestamp': submit_start.strftime('%Y-%m-%d %H:%M:%S'),
                        'error': error_msg
                    })

                # 提交间隔（避免过于频繁）
                if i < self.total_count:
                    wait_time = 3  # 间隔3秒
                    print(f"⏳ 等待 {wait_time} 秒后进行下一次提交...")
                    await asyncio.sleep(wait_time)

            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()

            # 打印最终统计
            self._print_summary(total_duration)

            # 保存结果到文件
            self._save_results()

            return self.success_count == self.total_count

        except Exception as e:
            print(f"\n❌ 批量测试异常: {str(e)}")
            import traceback
            print("\n详细错误:")
            print(traceback.format_exc())
            return False
        finally:
            print("\n🔧 清理资源...")
            await self.browser_manager.cleanup()
            print("✅ 资源清理完成")

    def _print_summary(self, total_duration: float):
        """打印测试总结"""
        print("\n" + "=" * 80)
        print("📊 批量提交测试结果汇总".center(80))
        print("=" * 80)

        # 基础统计
        print(f"\n✅ 成功: {self.success_count}/{self.total_count} "
              f"({self.success_count/self.total_count*100:.1f}%)")
        print(f"❌ 失败: {self.failed_count}/{self.total_count} "
              f"({self.failed_count/self.total_count*100:.1f}%)")
        print(f"⚠️  错误: {self.error_count}/{self.total_count} "
              f"({self.error_count/self.total_count*100:.1f}%)")

        # 时间统计
        print(f"\n⏱️  总耗时: {total_duration:.1f} 秒")
        if self.total_count > 0:
            avg_time = total_duration / self.total_count
            print(f"⏱️  平均每次: {avg_time:.1f} 秒")

        # 失败原因统计
        if self.failure_reasons:
            print(f"\n📋 失败原因分析:")
            for reason, count in sorted(self.failure_reasons.items(),
                                       key=lambda x: x[1], reverse=True):
                print(f"  • {reason}: {count} 次")

        # 成功率评估
        success_rate = self.success_count / self.total_count * 100
        print(f"\n🎯 成功率评估:")
        if success_rate >= 90:
            print(f"  ✅ 优秀 ({success_rate:.1f}%) - 系统运行稳定")
        elif success_rate >= 70:
            print(f"  ⚠️  良好 ({success_rate:.1f}%) - 可以继续优化")
        elif success_rate >= 50:
            print(f"  ⚠️  一般 ({success_rate:.1f}%) - 需要排查问题")
        else:
            print(f"  ❌ 较差 ({success_rate:.1f}%) - 需要重点修复")

        # 下一步建议
        print(f"\n💡 下一步建议:")
        if success_rate >= 90:
            print("  1. ✅ 单次提交测试通过")
            print("  2. 📊 可以进行更大规模测试（50-100次）")
            print("  3. 🌐 实现代理池进行IP轮换")
            print("  4. 📈 优化提交间隔，提高效率")
        elif success_rate >= 70:
            print("  1. 🔍 分析失败原因，针对性优化")
            print("  2. 📊 增加重试机制")
            print("  3. ⏱️  调整提交间隔")
        else:
            print("  1. ❌ 重点排查失败原因")
            print("  2. 🔧 检查选择器和表单填写逻辑")
            print("  3. 🌐 检查网络连接")
            print("  4. 📋 确认问卷状态是否正常")

        print("\n" + "=" * 80)

    def _save_results(self):
        """保存测试结果到文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"batch_test_results_{timestamp}.json"
        filepath = Path(__file__).parent / filename

        summary = {
            'test_info': {
                'url': self.url,
                'total_count': self.total_count,
                'timestamp': timestamp
            },
            'statistics': {
                'success': self.success_count,
                'failed': self.failed_count,
                'error': self.error_count,
                'success_rate': self.success_count / self.total_count * 100
            },
            'failure_reasons': self.failure_reasons,
            'details': self.results
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n💾 详细结果已保存到: {filename}")


async def main():
    """主函数"""
    print("\n" + "🔬 问卷星批量提交测试工具".center(80))
    print()

    # 问卷URL
    questionnaire_url = 'https://v.wjx.cn/vm/rqKTYry.aspx'

    # 测试配置
    print("请选择测试规模:")
    print("  1. 小规模测试 (10次)")
    print("  2. 中等规模测试 (20次)")
    print("  3. 大规模测试 (50次)")
    print("  4. 自定义数量")
    print()

    # 默认使用小规模测试
    choice = input("请选择 (直接回车默认选择1): ").strip() or "1"

    if choice == "1":
        count = 10
    elif choice == "2":
        count = 20
    elif choice == "3":
        count = 50
    elif choice == "4":
        try:
            count = int(input("请输入测试次数: "))
            if count <= 0:
                print("❌ 无效的数量，使用默认值10")
                count = 10
        except ValueError:
            print("❌ 输入无效，使用默认值10")
            count = 10
    else:
        print("❌ 无效选择，使用默认值10")
        count = 10

    print(f"\n将执行 {count} 次提交测试\n")

    # 确认
    confirm = input("确认开始测试？(y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ 测试已取消")
        return 1

    # 运行批量测试
    tester = BatchSubmissionTester(questionnaire_url, total_count=count)
    success = await tester.run_batch_test()

    # 输出最终结果
    print()
    if success:
        print("🎉 所有提交均成功！")
        return 0
    else:
        print("⚠️  部分提交失败，请查看上述统计信息")
        return 1


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断测试")
        sys.exit(130)
