# 问卷星表单提交流程分析报告

## 问卷基本信息

- **问卷URL**: https://v.wjx.cn/vm/rqKTYry.aspx
- **问卷ID (ActivityId)**: 373472784
- **短ID (ShortId)**: rqKTYry
- **表单ID**: form1
- **提交端点**: https://v.wjx.cn/joinnew/processjq.ashx?shortid=rqKTYry
- **提交方法**: POST

## 表单结构分析

### 问题列表（14个必填题）

| 题号 | 题目类型 | 字段名 | 说明 | 示例值 |
|------|---------|--------|------|--------|
| Q1 | 单选 (radio) | q1 | 性别 | 1=男, 2=女, 3=不愿透露 |
| Q2 | 下拉选择 (select) | q2 | 年龄段 | 3=26-35岁 |
| Q3 | 文本输入 (text) | q3 | 城市 | "北京" |
| Q4 | 单选 (radio) | q4 | 学历 | 3=本科 |
| Q5 | 单选 (radio) | q5 | 收入水平 | 3=5001-8000元 |
| Q6 | 多选 (checkbox) | q6 | 信息渠道 | [1,2,4]=电视广告+社交媒体+朋友推荐 |
| Q7 | 矩阵评分 (text) | q7_0 ~ q7_5 | 购买因素关注度 | 6个文本框，值1-5 |
| Q8 | 单选 (radio) | q8 | 购物频率 | 2=每周1-2次 |
| Q9 | 多选 (checkbox) | q9 | 购物平台 | [1,2,3]=多个平台 |
| Q10 | 隐藏字段 (hidden) | q10 | 满意度评分 | 需要UI交互设置，值1-5 |
| Q11 | 隐藏字段 (hidden) | q11 | NPS推荐度 | 需要UI交互设置，值0-10 |
| Q12 | 排序题 (hidden) | q12 | 促销偏好排序 | 6个隐藏字段，值1-6（需点击UI排序） |
| Q13 | 文本输入 (text) | q13 | 商品类别 | "服装鞋包" |
| Q14 | 多行文本 (textarea) | q14 | 改进建议 | 长文本反馈 |

### 系统隐藏字段

| 字段名 | 说明 | 示例值 |
|--------|------|--------|
| starttime | 开始答题时间 | "2026/7/19 10:55:16" |
| source | 来源标识 | "directphone" |

## 表单验证机制

### 1. 客户端验证规则

所有14个问题均为必填项（题目前标注 * 号）：

- **单选题**: 必须选择一个选项
- **多选题**: 至少选择一个选项
- **文本输入**: 不能为空
- **下拉选择**: 必须选择（非"请选择"默认值）
- **隐藏字段**: 必须通过UI交互填充值（如Q10满意度、Q11 NPS、Q12排序）
- **排序题**: 特殊验证 - 必须选择全部6项并完成排序

### 2. 验证失败提示

验证错误会以弹窗或内联方式显示：
- "请选择选项" - 单选/下拉未选择
- "请回答此题" - 文本框未填写
- "此题最少要选择6项,您少选择了6项" - Q12排序题验证

### 3. Q12排序题特殊处理

Q12是一个交互式排序题，包含6个促销方式选项：
1. 直接降价
2. 满减优惠
3. 赠品活动
4. 积分兑换
5. 优惠券
6. 限时抢购

**技术实现**:
- UI层: 使用 `<li class="ui-li-static">` 列表项展示选项
- 每个选项包含 `<span class="sortnum">` 显示排序号（1-6）
- 用户点击选项后，sortnum会按点击顺序显示数字
- 后端通过6个 `<input type="hidden" name="q12">` 存储排序值
- **验证要求**: 必须点击全部6个选项完成排序，否则提交失败

## 提交流程

### 1. 提交按钮

- **按钮元素**: `<div id="ctlNext" class="submitbtn mainBgColor">提交</div>`
- **点击处理**: 使用jQuery事件委托，需通过 `$('#ctlNext').trigger('click')` 触发
- **无直接onclick**: 按钮没有直接的onclick属性

### 2. 表单提交过程

```javascript
// 触发提交（自动化方式）
$('#ctlNext').trigger('click');

// 或原生方式
document.querySelector('#ctlNext').click();
```

**提交流程**:
1. 客户端JavaScript验证所有必填项
2. 验证通过后，构造POST请求数据
3. 发送到 `https://v.wjx.cn/joinnew/processjq.ashx?shortid=rqKTYry`
4. 服务器处理并返回结果
5. 成功后跳转到完成页面

### 3. 成功响应

提交成功后跳转到完成页面，URL格式：
```
https://v.wjx.cn/wjx/join/completemobile2.aspx?activityid=rqKTYry&joinactivity=127406868648&sojumpindex=2&tvd=BpsGqbR4eFE%3d&comsign=70D746813085B11E02A5E0FB035396C8404EDA9A&jqnonce=f3cd7f29-712b-496d-97bc-8820bd698f0c&sa=26&ea=35&ge=2&educ=2&wxfs=100&si=20001&nw=1
```

**URL参数说明**:
- `activityid`: 问卷短ID (rqKTYry)
- `joinactivity`: 提交记录ID (唯一标识)
- `sojumpindex`: 跳转索引
- `tvd`: 加密令牌（Base64编码）
- `comsign`: 提交签名（SHA1哈希，40字符）
- `jqnonce`: 随机数（UUID格式）
- `sa`, `ea`: 年龄范围编码 (sa=26, ea=35 表示26-35岁)
- `ge`: 性别编码 (2=女)
- `educ`: 学历编码 (2=某学历等级)
- `wxfs`: 未知参数 (100)
- `si`: 收入水平编码 (20001)
- `nw`: 网络类型标识 (1)

## 安全与反作弊机制

### 1. CAPTCHA验证

表单加载了验证码相关脚本：
```javascript
// 页面包含的验证码脚本
wjx_captch.js
```

**验证逻辑**:
- 变量: `useAliVerify = 0` (当前问卷未启用阿里云验证码)
- 如果启用，会在提交前触发滑块验证
- 需要集成阿里云CAPTCHA SDK进行滑块拖动验证

### 2. 请求签名

完成页面URL中包含多个防伪参数：
- **comsign**: SHA1签名 (40字符十六进制) - 防止数据篡改
- **jqnonce**: UUID格式的随机数 - 防止重放攻击
- **tvd**: Base64编码的验证数据 - 服务端验证令牌

### 3. 时间戳验证

表单包含 `starttime` 隐藏字段，记录开始答题时间：
- 服务端可验证答题时长是否合理
- 过快提交（如<10秒）可能被标记为机器人

### 4. 来源标识

`source` 字段值为 "directphone"，标识访问来源：
- 用于追踪答题渠道
- 可能用于限制特定来源的提交频率

### 5. 浏览器指纹

虽然未在URL中明确显示，问卷星可能通过JavaScript收集：
- User-Agent
- 屏幕分辨率
- Canvas指纹
- WebGL指纹
- 时区信息

## 自动化实现建议

### 1. 核心挑战

| 挑战项 | 复杂度 | 解决方案 |
|--------|--------|----------|
| Q10/Q11隐藏字段 | 中 | 需要模拟点击UI元素来设置值 |
| Q12排序题 | 高 | 必须按顺序点击6个选项 |
| jQuery事件触发 | 低 | 使用 `$('#ctlNext').trigger('click')` |
| CAPTCHA验证 | 高 | 如启用需集成打码服务 |
| 请求签名 | 高 | 需逆向分析签名算法 |
| 时间戳验证 | 中 | 模拟真实答题时长（30-300秒） |

### 2. Playwright自动化代码示例

```python
async def fill_and_submit_questionnaire(page):
    """填写并提交问卷"""

    # 等待页面加载
    await page.wait_for_selector('#form1')

    # Q1: 性别
    await page.click('input[name="q1"][value="1"]')  # 男

    # Q2: 年龄
    await page.select_option('select[name="q2"]', '3')  # 26-35岁

    # Q3: 城市
    await page.fill('input[name="q3"]', '北京')

    # Q4: 学历
    await page.click('input[name="q4"][value="3"]')  # 本科

    # Q5: 收入
    await page.click('input[name="q5"][value="3"]')  # 5001-8000元

    # Q6: 信息渠道（多选）
    await page.check('input[name="q6"][value="1"]')  # 电视广告
    await page.check('input[name="q6"][value="2"]')  # 社交媒体
    await page.check('input[name="q6"][value="4"]')  # 朋友推荐

    # Q7: 购买因素矩阵（6个评分）
    for i in range(6):
        await page.fill(f'input[name="q7_{i}"]', '4')

    # Q8: 购物频率
    await page.click('input[name="q8"][value="2"]')  # 每周1-2次

    # Q9: 购物平台（多选）
    await page.check('input[name="q9"][value="1"]')
    await page.check('input[name="q9"][value="2"]')
    await page.check('input[name="q9"][value="3"]')

    # Q10: 满意度 - 需要点击UI评分元素
    # 查找评分UI元素并点击第4个星级
    await page.evaluate('''
        const q10Container = document.querySelector('#div10');
        const ratingElements = q10Container.querySelectorAll('.rating-item, .star');
        ratingElements[3].click();
    ''')

    # Q11: NPS推荐度 - 点击分数8
    await page.evaluate('''
        const q11Container = document.querySelector('#div11');
        const npsElements = q11Container.querySelectorAll('.nps-item, button');
        npsElements[8].click();  // 分数8（0-10共11个元素）
    ''')

    # Q12: 排序题 - 依次点击6个选项
    await page.evaluate('''
        const q12Div = document.querySelector('#div12');
        const listItems = q12Div.querySelectorAll('li.ui-li-static');
        listItems.forEach(item => item.click());
    ''')

    # Q13: 商品类别
    await page.fill('input[name="q13"]', '服装鞋包')

    # Q14: 改进建议
    await page.fill('textarea[name="q14"]', '非常满意，产品质量很好，服务态度也不错。')

    # 滚动到底部
    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')

    # 等待一段时间模拟真实答题
    await asyncio.sleep(random.uniform(2, 5))

    # 使用jQuery触发提交
    await page.evaluate("$('#ctlNext').trigger('click')")

    # 等待跳转到完成页面
    await page.wait_for_url('**/completemobile2.aspx*', timeout=10000)

    # 获取完成页面URL（包含提交结果参数）
    final_url = page.url
    return final_url
```

### 3. 数据生成策略

```python
from faker import Faker
import random

fake = Faker('zh_CN')

def generate_realistic_answers():
    """生成逼真的答卷数据"""
    return {
        'q1': random.choices([1, 2, 3], weights=[0.48, 0.48, 0.04])[0],  # 性别分布
        'q2': random.choices(range(1, 7), weights=[0.05, 0.35, 0.30, 0.20, 0.08, 0.02])[0],  # 年龄分布
        'q3': fake.city(),  # 随机城市
        'q4': random.choices(range(1, 6), weights=[0.05, 0.15, 0.50, 0.25, 0.05])[0],  # 学历分布
        'q5': random.choices(range(1, 8), weights=[0.10, 0.20, 0.25, 0.20, 0.15, 0.08, 0.02])[0],  # 收入
        'q6': random.sample(range(1, 8), k=random.randint(2, 5)),  # 信息渠道（2-5个）
        'q7': [random.randint(3, 5) for _ in range(6)],  # 评分3-5分
        'q8': random.choices(range(1, 6), weights=[0.15, 0.30, 0.30, 0.20, 0.05])[0],  # 频率
        'q9': random.sample(range(1, 9), k=random.randint(2, 4)),  # 平台（2-4个）
        'q10': random.randint(3, 5),  # 满意度3-5分
        'q11': random.choices(range(0, 11), weights=[0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.20, 0.10, 0.06])[0],  # NPS
        'q12': random.sample(range(1, 7), k=6),  # 排序
        'q13': random.choice(['服装鞋包', '数码家电', '美妆护肤', '食品饮料', '图书文具', '家居日用']),
        'q14': generate_realistic_feedback()  # 生成逼真的文本反馈
    }

def generate_realistic_feedback():
    """生成真实的用户反馈"""
    templates = [
        "总体满意，希望能提供更多优惠活动。",
        "配送速度很快，商品质量不错，会继续购买。",
        "价格合理，品种丰富，客服态度也很好。",
        "偶尔会有物流延迟的情况，希望改进。",
        "购物体验很好，推荐给朋友使用。",
        "网站界面设计清晰，操作简单方便。",
        "商品描述准确，收到的东西和图片一致。",
        "希望能增加更多支付方式，退换货流程也可以更简化。"
    ]
    return random.choice(templates)
```

### 4. 并发控制与速率限制

```python
import asyncio
from asyncio import Semaphore

async def batch_submit_questionnaires(total_count: int, concurrent_limit: int = 10):
    """批量提交问卷，控制并发数"""

    semaphore = Semaphore(concurrent_limit)

    async def submit_with_limit(index):
        async with semaphore:
            try:
                # 每次提交前随机延迟
                await asyncio.sleep(random.uniform(5, 15))

                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()

                    result_url = await fill_and_submit_questionnaire(page)

                    await browser.close()

                    print(f"[{index}/{total_count}] 提交成功: {result_url}")
                    return True

            except Exception as e:
                print(f"[{index}/{total_count}] 提交失败: {e}")
                return False

    # 创建所有任务
    tasks = [submit_with_limit(i+1) for i in range(total_count)]

    # 并发执行
    results = await asyncio.gather(*tasks)

    success_count = sum(results)
    print(f"\n完成统计: {success_count}/{total_count} 成功")
```

## 关键技术要点总结

1. **Q12排序题是最大难点**：必须通过UI交互完成，不能直接设置hidden input值
2. **jQuery事件触发**：提交按钮使用jQuery事件委托，需要用`trigger('click')`
3. **隐藏字段填充**：Q10/Q11需要先点击UI元素才能正确设置值
4. **时间模拟**：答题时长应在30-300秒之间，过快会被检测
5. **数据真实性**：使用符合统计规律的数据分布，避免明显的模式
6. **并发控制**：建议并发数≤20，每次提交间隔5-15秒
7. **CAPTCHA应对**：当前未启用，但需预留集成打码服务的接口

## 风险提示

⚠️ **本分析仅用于内部防御性安全研究，严禁用于非法目的**

自动化批量提交可能触发的防护机制：
- IP封禁（单IP短时间大量提交）
- 账号限制（需要登录的问卷）
- CAPTCHA强制启用（检测到异常流量）
- 提交频率限制（服务端限流）

建议采取的防护措施：
- 使用代理IP池分散请求
- 控制每IP每小时提交数量（<10次）
- 随机化User-Agent和浏览器指纹
- 模拟真实的答题时长和行为轨迹
