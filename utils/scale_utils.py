# scale_utils.py
"""
量表题积极/消极值推导工具

根据选项数值的大小顺序和题目是否为反向题，推导出哪些选项值代表积极态度、
哪些代表消极态度。用于关键字检测（无AI）和答案生成的回退逻辑，
保证两者行为一致。
"""

from typing import Any, List, Tuple


def extract_option_values(options: List[Any]) -> List[Any]:
    """从选项列表提取纯数值

    处理两种格式：
    - 新格式: [{"value": 1, "label": "..."}, ...]
    - 旧格式: [1, 2, 3, ...]
    """
    if not options:
        return []

    first = options[0]
    if isinstance(first, dict) and "value" in first:
        return [opt["value"] for opt in options]
    return list(options)


def split_scale_values(option_values: List[Any], is_reverse: bool = False) -> Tuple[List[Any], List[Any], List[Any]]:
    """根据选项数值和是否反向题，推导积极/消极/中性值

    正向题：数值越大越积极（如1-5分，5分最积极）
    反向题：数值越小越积极（如"我对产品很失望"，选1=很不同意=积极）

    奇数个选项时，中间值归为中性；偶数个选项时，均分为高低两半。

    Args:
        option_values: 选项数值列表，如 [1, 2, 3, 4, 5]
        is_reverse: 是否为反向题

    Returns:
        (positive_values, negative_values, neutral_values)
    """
    if not option_values:
        return [], [], []

    try:
        sorted_vals = sorted(option_values, key=lambda v: float(v))
    except (TypeError, ValueError):
        return [], [], []

    n = len(sorted_vals)
    if n == 1:
        return list(sorted_vals), [], []

    half = n // 2
    lower = sorted_vals[:half]
    upper = sorted_vals[n - half:]
    neutral = sorted_vals[half:n - half]  # 奇数时为中间一项，偶数时为空

    if is_reverse:
        positive, negative = lower, upper
    else:
        positive, negative = upper, lower

    return positive, negative, neutral
