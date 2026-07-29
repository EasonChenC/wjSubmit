"""
调试脚本 - 全面分析问卷结构

检查单选题、多选题、文本题的实际HTML结构
"""

import asyncio
from pathlib import Path
from bs4 import BeautifulSoup
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def analyze_html():
    """分析已保存的HTML"""
    html_file = Path(__file__).parent / "debug_questionnaire.html"

    if not html_file.exists():
        print("❌ debug_questionnaire.html 不存在，请先运行 debug_text_inputs.py")
        return

    with open(html_file, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    print("="*80)
    print("问卷HTML结构分析".center(80))
    print("="*80)

    # 1. 分析第一个单选题 (应该是Q2)
    print("\n【单选题示例 - Q2】")
    print("-"*80)

    # 查找Q2相关的元素
    div2 = soup.find('div', id='div2')
    if div2:
        print("✅ 找到 div#div2")

        # 查找radio inputs
        radios = div2.find_all('input', attrs={'type': 'radio'})
        print(f"\n找到 {len(radios)} 个radio input:")

        for i, radio in enumerate(radios[:3], 1):
            print(f"\n  Radio #{i}:")
            print(f"    id: {radio.get('id')}")
            print(f"    name: {radio.get('name')}")
            print(f"    value: {radio.get('value')}")

            # 查找对应的label
            radio_id = radio.get('id')
            if radio_id:
                label = div2.find('label', attrs={'for': radio_id})
                if label:
                    print(f"    label[for]: {label.get('for')}")
                    print(f"    label class: {label.get('class')}")
                    print(f"    label text: {label.get_text(strip=True)[:30]}")
    else:
        print("❌ 未找到 div#div2")

    # 2. 分析第一个多选题
    print("\n\n【多选题示例】")
    print("-"*80)

    # 查找第一个包含checkbox的div
    divs = soup.find_all('div', class_='field')
    checkbox_div = None

    for div in divs:
        checkboxes = div.find_all('input', attrs={'type': 'checkbox'})
        if checkboxes:
            checkbox_div = div
            div_id = div.get('id')
            print(f"✅ 找到多选题: {div_id}")

            print(f"\n找到 {len(checkboxes)} 个checkbox:")

            for i, cb in enumerate(checkboxes[:3], 1):
                print(f"\n  Checkbox #{i}:")
                print(f"    id: {cb.get('id')}")
                print(f"    name: {cb.get('name')}")
                print(f"    value: {cb.get('value')}")

                # 查找对应的label
                cb_id = cb.get('id')
                if cb_id:
                    label = checkbox_div.find('label', attrs={'for': cb_id})
                    if label:
                        print(f"    label[for]: {label.get('for')}")
                        print(f"    label class: {label.get('class')}")

            break

    if not checkbox_div:
        print("❌ 未找到多选题")

    # 3. 分析TEXT输入框
    print("\n\n【文本输入框 - Q1】")
    print("-"*80)

    div1 = soup.find('div', id='div1')
    if div1:
        print("✅ 找到 div#div1")

        text_inputs = div1.find_all('input', attrs={'type': 'text'})
        print(f"\n找到 {len(text_inputs)} 个text input:")

        for i, inp in enumerate(text_inputs, 1):
            print(f"\n  Input #{i}:")
            print(f"    id: {inp.get('id')}")
            print(f"    name: {inp.get('name')}")
            print(f"    placeholder: {inp.get('placeholder', '')[:30]}")
            print(f"    class: {inp.get('class')}")
    else:
        print("❌ 未找到 div#div1")

    # 4. 给出建议
    print("\n\n" + "="*80)
    print("建议的选择器策略".center(80))
    print("="*80)

    print("\n单选题:")
    if div2 and radios:
        first_radio = radios[0]
        radio_id = first_radio.get('id')
        label = div2.find('label', attrs={'for': radio_id})
        if label:
            label_class = ' '.join(label.get('class', []))
            print(f"  当前使用: .label[for=\"q2_1\"]")
            print(f"  实际应该: .{label_class}[for=\"{radio_id}\"]" if label_class else f"  label[for=\"{radio_id}\"]")

    print("\n多选题:")
    if checkbox_div and checkboxes:
        first_cb = checkboxes[0]
        cb_id = first_cb.get('id')
        label = checkbox_div.find('label', attrs={'for': cb_id})
        if label:
            label_class = ' '.join(label.get('class', []))
            print(f"  当前使用: .label[for=\"q6_1\"]")
            print(f"  实际应该: .{label_class}[for=\"{cb_id}\"]" if label_class else f"  label[for=\"{cb_id}\"]")

    print("\n文本输入:")
    if div1 and text_inputs:
        print(f"  题目Q1有 {len(text_inputs)} 个输入框")
        print(f"  输入框ID: {[inp.get('id') for inp in text_inputs]}")
        print(f"  建议: 使用 getElementById('{text_inputs[0].get('id')}')")


if __name__ == '__main__':
    analyze_html()
