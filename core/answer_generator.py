# answer_generator.py
import random
from faker import Faker
from typing import Dict, Any

fake = Faker('zh_CN')

class AnswerGenerator:
    """智能答案生成器 - 生成符合真实分布的答案"""

    def __init__(self):
        # 预设的答案权重分布
        self.gender_weights = [0.48, 0.48, 0.04]  # 男/女/不透露
        self.age_weights = [0.05, 0.35, 0.30, 0.20, 0.08, 0.02]
        self.education_weights = [0.05, 0.15, 0.20, 0.45, 0.15]
        self.income_weights = [0.10, 0.20, 0.25, 0.20, 0.15, 0.05, 0.05]

    def generate_answers(self, questionnaire_schema: Dict) -> Dict[str, Any]:
        """根据问卷结构生成答案"""
        answers = {}

        # 1. 性别（单选）- 使用数字ID: 1=男, 2=女, 3=不愿透露
        answers['q1'] = random.choices(
            [1, 2, 3],
            weights=self.gender_weights
        )[0]

        # 2. 年龄段（下拉）- 使用数字ID: 1=<18岁, 2=18-25岁, 3=26-35岁, 4=36-45岁, 5=46-55岁, 6=56+
        answers['q2'] = random.choices(
            list(range(1, 7)),
            weights=self.age_weights
        )[0]

        # 3. 城市（文本）
        answers['q3'] = fake.city()

        # 4. 教育程度（单选）- 使用数字ID: 1=初中及以下, 2=高中, 3=本科, 4=硕士, 5=博士
        answers['q4'] = random.choices(
            list(range(1, 6)),
            weights=self.education_weights
        )[0]

        # 5. 月收入（单选）- 使用数字ID: 1=<3000, 2=3001-5000, 3=5001-8000, 4=8001-12000, 5=12001-20000, 6=20001+, 7=不愿透露
        answers['q5'] = random.choices(
            list(range(1, 8)),
            weights=self.income_weights
        )[0]

        # 6. 信息来源（多选，2-4个选项）- 使用数字ID: 1-7
        answers['q6'] = random.sample(range(1, 8), k=random.randint(2, 4))

        # 7. 购买因素重要性（矩阵量表）- 使用独立字段 q7_0 到 q7_5，值为字符串'1'-'5'
        for i in range(6):
            answers[f'q7_{i}'] = str(random.randint(3, 5))  # 倾向于重要(3-5分)

        # 8. 购物频率（单选）- 使用数字ID: 1=每天, 2=每周1-2次, 3=每月1-2次, 4=偶尔, 5=很少
        answers['q8'] = random.choices(
            list(range(1, 6)),
            weights=[0.15, 0.30, 0.30, 0.20, 0.05]
        )[0]

        # 9. 常用平台（多选，2-4个）- 使用数字ID: 1-8
        num_platforms = random.randint(2, 4)
        answers['q9'] = random.sample(range(1, 9), k=num_platforms)

        # 9-1. 如果选择了选项8（其他），需要填写额外的文本框
        if 8 in answers['q9']:
            answers['tqq9_8'] = fake.company() + '商城'  # 生成其他平台名称

        # 10. 满意度（1-5分）- 隐藏字段，需要通过UI点击设置
        answers['q10'] = random.choices([3, 4, 5], weights=[0.2, 0.5, 0.3])[0]

        # 11. NPS推荐度（0-10分）- 隐藏字段，需要通过UI点击设置
        answers['q11'] = random.choices(
            list(range(11)),
            weights=[0.01, 0.01, 0.02, 0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.2, 0.15]
        )[0]

        # 12. 促销方式排序（拖拽排序）- 生成排序顺序，实际需要通过UI点击设置
        # 只生成一个排序数组作为点击顺序的参考
        answers['q12'] = list(range(1, 7))  # 6个选项的点击顺序
        random.shuffle(answers['q12'])

        # 13. 最近购买类别（文本）
        categories = ['服装鞋包', '数码家电', '美妆护肤', '食品饮料', '图书文具', '家居日用', '运动户外', '母婴用品']
        answers['q13'] = random.choice(categories)

        # 14. 问题和建议（文本，使用AI生成或模板）
        # 注意：如果问卷设置Q14为可选，可以加入空字符串；如果必填，则不应包含空字符串
        suggestions = [
            '总体满意，希望能提供更多优惠活动。',
            '配送速度很快，商品质量不错，会继续购买。',
            '价格合理，品种丰富，客服态度也很好。',
            '偶尔会有物流延迟的情况，希望改进。',
            '购物体验很好，推荐给朋友使用。',
            '网站界面设计清晰，操作简单方便。',
            '商品描述准确，收到的东西和图片一致。',
            '希望能增加更多支付方式，退换货流程也可以更简化。',
            '物流服务好，包装完整，商品质量有保障。',
            '平台活动丰富，经常有优惠券可以使用。'
        ]
        # 始终填写内容，避免因必填项为空导致提交失败
        answers['q14'] = random.choice(suggestions)

        return answers

    def add_timing_data(self, answers: Dict) -> Dict:
        """添加答题时间数据，模拟真实用户"""
        timing = {
            'start_time': random.randint(0, 5),  # 开始前停留0-5秒
            'answer_times': {}
        }

        # 每题的答题时间（正态分布）
        for q_id in answers.keys():
            if isinstance(answers[q_id], str) and len(answers[q_id]) > 20:
                # 文本题需要更多时间
                timing['answer_times'][q_id] = max(5, random.gauss(15, 5))
            else:
                # 选择题
                timing['answer_times'][q_id] = max(1, random.gauss(3, 1))

        answers['_timing'] = timing
        return answers
