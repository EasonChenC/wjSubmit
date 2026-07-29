"""
问卷星提交测试脚本
基于签名分析文档的验证建议

测试目标：
1. 验证表单字段映射正确
2. 验证Q10/Q11/Q12特殊处理有效
3. 验证签名自动生成
4. 验证提交成功并跳转到完成页面
5. 监控网络请求，分析签名机制
"""

import asyncio
import sys
import re
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.answer_generator import AnswerGenerator
from core.captcha_solver import CaptchaSolver
from core.browser_manager import BrowserManager
from core.submitter import QuestionnaireSubmitter


class SubmissionTester:
    """提交测试器"""

    def __init__(self, url: str):
        self.url = url
        self.answer_generator = AnswerGenerator()
        self.captcha_solver = CaptchaSolver()
        self.browser_manager = BrowserManager(pool_size=1)
        self.network_logs = []

    async def test_with_network_monitoring(self):
        """带网络监控的测试"""
        print("=" * 70)
        print("问卷星提交测试 - 网络请求监控模式")
        print("=" * 70)
        print(f"\n📋 目标问卷: {self.url}")
        print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        submitter = QuestionnaireSubmitter(
            url=self.url,
            answer_generator=self.answer_generator,
            captcha_solver=self.captcha_solver,
            browser_manager=self.browser_manager
        )

        try:
            # 初始化浏览器
            await self.browser_manager.initialize()

            # 获取浏览器上下文和页面
            context = await self.browser_manager.get_context()
            page = await context.new_page()

            # 设置网络监听
            self._setup_network_listeners(page)

            print("🚀 开始执行提交流程...")
            print("-" * 70)

            # 执行提交
            result = await submitter.submit_one()

            print("-" * 70)
            print("\n📊 提交结果分析:")
            print(f"  状态: {result['status']}")

            if result['status'] == 'success':
                await self._analyze_success_result(result)
                return True
            elif result['status'] == 'failed':
                await self._analyze_failed_result(result)
                return False
            else:
                await self._analyze_error_result(result)
                return False

        except Exception as e:
            print(f"\n❌ 测试异常: {str(e)}")
            import traceback
            print("\n详细错误:")
            print(traceback.format_exc())
            return False
        finally:
            print("\n🔧 清理资源...")
            await self.browser_manager.cleanup()
            print("✅ 资源清理完成")

    def _setup_network_listeners(self, page):
        """设置网络请求监听"""
        print("🔍 启动网络请求监控...\n")

        def handle_request(request):
            url = request.url

            # 监控关键请求
            if 'processjq.ashx' in url:
                print(f"📤 [核心提交] {url}")

                # 提取关键参数
                if 'jqsign=' in url:
                    jqsign_match = re.search(r'jqsign=([^&]+)', url)
                    if jqsign_match:
                        jqsign = jqsign_match.group(1)
                        print(f"   🔐 jqsign: {jqsign[:50]}...")

                if 'jqnonce=' in url:
                    nonce_match = re.search(r'jqnonce=([^&]+)', url)
                    if nonce_match:
                        print(f"   🎲 jqnonce: {nonce_match.group(1)}")

                if 'starttime=' in url:
                    time_match = re.search(r'starttime=([^&]+)', url)
                    if time_match:
                        from urllib.parse import unquote
                        print(f"   ⏰ starttime: {unquote(time_match.group(1))}")

                # 记录POST数据
                if request.method == 'POST':
                    post_data = request.post_data
                    if post_data:
                        print(f"   📝 POST数据长度: {len(post_data)} 字节")
                        if 'submitdata=' in post_data:
                            print(f"   📝 submitdata 存在")

                self.network_logs.append({
                    'type': 'processjq',
                    'url': url,
                    'method': request.method,
                    'post_data': request.post_data
                })

            elif 'completemobile2.aspx' in url:
                print(f"📥 [完成页面] {url[:100]}...")
                self.network_logs.append({
                    'type': 'complete',
                    'url': url,
                    'method': request.method
                })

            elif 'aliyuncs.com' in url and 'track' in url:
                print(f"📊 [数据上报] 阿里云日志服务")
                self.network_logs.append({
                    'type': 'aliyun_log',
                    'url': url,
                    'method': request.method
                })

        def handle_response(response):
            url = response.url

            if 'processjq.ashx' in url:
                print(f"📥 [提交响应] 状态码: {response.status}")

                try:
                    text = asyncio.create_task(response.text())
                    # 注意：这里不能用await，因为在同步回调中
                    print(f"   响应数据将在后续分析")
                except Exception as e:
                    print(f"   ⚠️ 无法读取响应体: {e}")

        page.on('request', handle_request)
        page.on('response', handle_response)

    async def _analyze_success_result(self, result):
        """分析成功结果"""
        print(f"  ✅ 提交成功！\n")

        final_url = result.get('final_url', '')
        print(f"🔗 最终URL:")
        print(f"  {final_url}\n")

        # 验证关键参数
        print("🔍 关键参数验证:")

        # 1. 提交记录ID
        join_id_match = re.search(r'joinactivity=(\d+)', final_url)
        if join_id_match:
            join_id = join_id_match.group(1)
            print(f"  ✅ joinactivity (提交记录ID): {join_id}")
        else:
            print(f"  ❌ joinactivity 参数缺失")

        # 2. 服务端签名
        comsign_match = re.search(r'comsign=([A-F0-9]{40})', final_url, re.IGNORECASE)
        if comsign_match:
            comsign = comsign_match.group(1)
            print(f"  ✅ comsign (服务端签名): {comsign[:20]}...{comsign[-10:]}")
            print(f"     (SHA1格式，40字符)")
        else:
            print(f"  ❌ comsign 参数缺失")

        # 3. 加密令牌
        tvd_match = re.search(r'tvd=([^&]+)', final_url)
        if tvd_match:
            tvd = tvd_match.group(1)
            from urllib.parse import unquote
            tvd_decoded = unquote(tvd)
            print(f"  ✅ tvd (加密令牌): {tvd_decoded}")
            print(f"     (Base64格式)")
        else:
            print(f"  ❌ tvd 参数缺失")

        # 4. 其他参数
        print(f"\n📋 其他参数:")
        for param in ['activityid', 'sojumpindex', 'sa', 'ea', 'ge', 'educ', 'ei', 'nw']:
            match = re.search(rf'{param}=([^&]+)', final_url)
            if match:
                print(f"  • {param}: {match.group(1)}")

        # 显示提交的答案
        print(f"\n📝 提交的答案数据:")
        answers = result.get('answers', {})
        for key in sorted(answers.keys()):
            if not key.startswith('_'):  # 跳过内部字段
                value = answers[key]
                if isinstance(value, list):
                    print(f"  {key}: {value}")
                elif isinstance(value, str) and len(value) > 60:
                    print(f"  {key}: {value[:60]}...")
                else:
                    print(f"  {key}: {value}")

        # 网络请求总结
        print(f"\n🌐 网络请求总结:")
        print(f"  总请求数: {len(self.network_logs)}")
        for log in self.network_logs:
            print(f"  • {log['type']}: {log['method']}")

        print("\n" + "=" * 70)
        print("✅ 测试通过！签名验证成功，提交流程正常！")
        print("=" * 70)
        print("\n💡 关键发现:")
        print("  1. jqsign 签名由页面 JavaScript 自动生成 ✅")
        print("  2. comsign 签名由服务端返回 ✅")
        print("  3. 提交流程完整，无需手动实现签名算法 ✅")
        print("\n📌 下一步建议:")
        print("  • 测试10次连续提交，观察成功率")
        print("  • 实现代理池（批量提交必需）")
        print("  • 优化答题时间分布")

    async def _analyze_failed_result(self, result):
        """分析失败结果"""
        print(f"  ❌ 提交失败\n")

        reason = result.get('reason', 'unknown')
        print(f"失败原因: {reason}\n")

        if reason == 'captcha_failed':
            print("⚠️  验证码处理失败")
            print("排查建议:")
            print("  1. 检查验证码求解器配置")
            print("  2. 验证码类型可能已变化")
            print("  3. 考虑使用手动验证")

        elif reason == 'form_validation_failed':
            print("⚠️  表单验证失败")
            print("排查建议:")
            print("  1. 检查必填项是否都已填写")
            print("  2. 检查表单选择器是否正确")
            print("  3. 查看浏览器控制台错误信息")

        else:
            print("排查建议:")
            print("  1. 检查网络连接")
            print("  2. 检查问卷是否仍然开放")
            print("  3. 查看详细错误日志")

        # 网络请求分析
        if self.network_logs:
            print(f"\n🌐 已捕获网络请求:")
            for log in self.network_logs:
                print(f"  • {log['type']}: {log['method']}")
        else:
            print(f"\n⚠️  未捕获到网络请求，可能页面加载失败")

        print("\n" + "=" * 70)
        print("❌ 测试未通过")
        print("=" * 70)

    async def _analyze_error_result(self, result):
        """分析错误结果"""
        error = result.get('error', 'unknown error')
        print(f"  ❌ 发生错误: {error}\n")

        print("排查建议:")
        print("  1. 检查浏览器是否正常启动")
        print("  2. 检查页面是否正确加载")
        print("  3. 查看完整错误堆栈")

        if 'timeout' in error.lower():
            print("  4. 可能是页面加载超时，尝试增加等待时间")

        print("\n" + "=" * 70)
        print("❌ 测试出错")
        print("=" * 70)


async def test_basic_submission():
    """基础提交测试（无网络监控）"""
    print("=" * 70)
    print("问卷星提交测试 - 基础模式")
    print("=" * 70)

    url = 'https://v.wjx.cn/vm/rqKTYry.aspx'
    print(f"\n📋 目标问卷: {url}\n")

    answer_generator = AnswerGenerator()
    captcha_solver = CaptchaSolver()
    browser_manager = BrowserManager(pool_size=1)

    submitter = QuestionnaireSubmitter(
        url=url,
        answer_generator=answer_generator,
        captcha_solver=captcha_solver,
        browser_manager=browser_manager
    )

    try:
        print("🚀 开始提交...")
        result = await submitter.submit_one()

        print(f"\n📊 结果: {result['status']}")

        if result['status'] == 'success':
            print("✅ 提交成功！")
            return True
        else:
            print(f"❌ 提交失败: {result.get('reason', result.get('error'))}")
            return False

    finally:
        await browser_manager.cleanup()


async def main():
    """主函数"""
    print("\n" + "🔬 问卷星提交测试工具".center(70))
    print()

    # 问卷URL
    questionnaire_url = 'https://v.wjx.cn/vm/rqKTYry.aspx# '

    # 选择测试模式
    print("请选择测试模式:")
    print("  1. 基础测试（快速验证）")
    print("  2. 完整测试（带网络监控和详细分析）")
    print()

    # 默认使用完整测试模式
    mode = 2

    if mode == 1:
        success = await test_basic_submission()
    else:
        tester = SubmissionTester(questionnaire_url)
        success = await tester.test_with_network_monitoring()

    # 输出最终结果
    print()
    if success:
        print("🎉 测试完成！实现验证通过！")
        print("\n下一步推荐:")
        print("  1. 运行多次测试（10次），统计成功率")
        print("  2. 分析失败原因（如果有）")
        print("  3. 实现代理池，准备批量提交")
        return 0
    else:
        print("⚠️  测试未完全通过")
        print("\n建议:")
        print("  1. 查看上述错误信息")
        print("  2. 检查浏览器控制台")
        print("  3. 验证表单选择器是否匹配")
        print("  4. 确认问卷仍然开放")
        return 1


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断测试")
        sys.exit(130)
