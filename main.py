# main.py
"""
问卷星自动填写系统 - 主入口
用途：防御性安全研究，分析自动化攻击手段以设计防护措施
"""
import asyncio
import sys
from scheduler.task_scheduler import TaskScheduler
from config import QUESTIONNAIRE_URL, PERFORMANCE_CONFIGS

def print_banner():
    """打印横幅"""
    banner = """
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║          问卷星自动化系统 - 防御性安全研究              ║
    ║                                                          ║
    ║     用途：研究自动化攻击手段以开发防护机制              ║
    ║     警告：仅用于授权的安全测试和研究                    ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """
    print(banner)

def print_config_info(config_name: str, config: dict):
    """打印配置信息"""
    print(f"\n选择的配置: {config_name}")
    print(f"  - 并发工作器: {config['concurrent_workers']}")
    print(f"  - 浏览器池大小: {config['browser_pool_size']}")
    print(f"  - 限流速率: {config['rate_limit_per_minute']} 份/分钟")
    print(f"  - 预计耗时: ~{config['estimated_time_minutes']} 分钟")
    if config.get('proxy_required'):
        print(f"  - 需要代理: 是")
    print()

async def main():
    """主函数"""
    print_banner()

    # 获取用户输入
    print("请选择任务规模:")
    print("1. 小规模测试 (5-10份)")
    print("2. 中等规模 (50-100份)")
    print("3. 大规模 (500-1000份)")
    print("4. 自定义")

    choice = input("\n请输入选项 (1-4): ").strip()

    if choice == '1':
        config_name = 'small'
        target_count = 10
    elif choice == '2':
        config_name = 'medium'
        target_count = 100
    elif choice == '3':
        config_name = 'large'
        target_count = 1000
    elif choice == '4':
        target_count = int(input("请输入目标数量: "))
        # 根据数量选择合适的配置
        if target_count < 100:
            config_name = 'small'
        elif target_count < 1000:
            config_name = 'medium'
        else:
            config_name = 'large'
    else:
        print("无效选项，使用小规模测试配置")
        config_name = 'small'
        target_count = 10

    config = PERFORMANCE_CONFIGS[config_name]
    print_config_info(config_name, config)

    # 确认执行
    confirm = input(f"确认要提交 {target_count} 份问卷吗? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    print(f"\n开始任务...")
    print(f"目标问卷: {QUESTIONNAIRE_URL}")
    print(f"目标数量: {target_count} 份\n")

    # 创建调度器并运行
    scheduler = TaskScheduler(
        target_count=target_count,
        concurrent_workers=config['concurrent_workers'],
        rate_limit_per_minute=config['rate_limit_per_minute']
    )

    try:
        await scheduler.run(QUESTIONNAIRE_URL)
    except KeyboardInterrupt:
        print("\n\n用户中断任务")
    except Exception as e:
        print(f"\n\n任务执行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # 检查Python版本
    if sys.version_info < (3, 10):
        print("错误: 需要 Python 3.10 或更高版本")
        sys.exit(1)

    # 运行主函数
    asyncio.run(main())
