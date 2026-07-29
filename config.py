# config.py
"""
项目配置文件
"""

# 问卷URL
QUESTIONNAIRE_URL = 'https://v.wjx.cn/vm/rqKTYry.aspx'

# 性能配置
PERFORMANCE_CONFIGS = {
    # 小规模（<100份）
    'small': {
        'concurrent_workers': 5,
        'browser_pool_size': 5,
        'rate_limit_per_minute': 30,
        'proxy_required': False,
        'estimated_time_minutes': 5,
    },

    # 中等规模（100-1000份）
    'medium': {
        'concurrent_workers': 20,
        'browser_pool_size': 20,
        'rate_limit_per_minute': 80,
        'proxy_required': True,
        'proxy_rotation_interval': 10,
        'estimated_time_minutes': 30,
    },

    # 大规模（1000-5000份）
    'large': {
        'concurrent_workers': 50,
        'browser_pool_size': 50,
        'rate_limit_per_minute': 150,
        'proxy_required': True,
        'proxy_rotation_interval': 5,
        'distributed': False,
        'estimated_time_minutes': 90,
    },

    # 超大规模（5000+份）
    'xlarge': {
        'concurrent_workers': 100,
        'browser_pool_size': 100,
        'rate_limit_per_minute': 300,
        'proxy_required': True,
        'proxy_rotation_interval': 3,
        'distributed': True,
        'worker_nodes': 5,
        'estimated_time_minutes': 120,
    }
}

# Redis配置（如果使用分布式）
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'password': None
}

# 浏览器配置
BROWSER_CONFIG = {
    'headless': False,  # 是否无头模式
    'slow_mo': 0,       # 放慢操作速度（毫秒）
    'devtools': False,  # 是否打开开发者工具
}

# 验证码配置
CAPTCHA_CONFIG = {
    'solver_type': 'behavioral',  # behavioral, manual, ai
    'retry_times': 3,             # 验证码失败重试次数
}

# 日志配置
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'questionnaire_automation.log'
}
