#!/usr/bin/env python3
"""
播客文稿质检脚本

检查：
1. 正文字数（亲子播客标准 2000~2300 字 ≈ 10 分钟）
2. 半角标点混入（应统一全角）
3. 多音字风险词（播讲易读错）

用法:
    python quality_check.py 文稿.md
    python quality_check.py 文稿.md --target-min 2000 --target-max 2300
"""

import argparse
import re
import sys


def count_chars(text):
    """统计正文字符数（含标点）。"""
    return len(text.strip())


def find_halfwidth_punctuation(text):
    """查找半角标点。"""
    halfwidth = re.findall(r'[,;:!?()"\'\.<>]', text)
    return halfwidth


def find_polyphone_risks(text):
    """查找多音字风险词。"""
    risks = []
    polyphone_words = [
        "港乐", "乐坛", "香港乐坛",
        "长得", "长大", "音乐", "快乐", "娱乐",
    ]
    # 更精确的规则：仅列出明确需要替换的
    specific_risks = {
        "港乐": "「乐」易读成 lè，应读 yuè，建议替换为「香港歌坛」",
        "乐坛": "「乐」易读成 lè，应读 yuè，建议替换为「歌坛」",
        "香港乐坛": "建议替换为「香港歌坛」",
    }
    for word, tip in specific_risks.items():
        if word in text:
            count = text.count(word)
            risks.append(f"{word} × {count} → {tip}")
    return risks


def main():
    parser = argparse.ArgumentParser(description="播客文稿质检")
    parser.add_argument("file", help="文稿文件路径")
    parser.add_argument("--target-min", type=int, default=2000, help="目标字数下限")
    parser.add_argument("--target-max", type=int, default=2300, help="目标字数上限")
    args = parser.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        text = f.read()

    print(f"=== 质检报告: {args.file} ===")

    # 1. 字数
    n = count_chars(text)
    status = "✅" if args.target_min <= n <= args.target_max else "⚠️"
    print(f"{status} 正文字数: {n} (目标 {args.target_min}~{args.target_max})")
    if n < args.target_min:
        print(f"   → 偏短，需扩写约 {args.target_min - n} 字")
    elif n > args.target_max:
        print(f"   → 偏长，需精简约 {n - args.target_max} 字")

    # 2. 半角标点
    half = find_halfwidth_punctuation(text)
    if half:
        print(f"⚠️ 检测到 {len(half)} 个半角标点: {half[:20]}")
    else:
        print("✅ 无半角标点混入")

    # 3. 多音字
    risks = find_polyphone_risks(text)
    if risks:
        print("⚠️ 多音字风险词:")
        for r in risks:
            print(f"   - {r}")
    else:
        print("✅ 无多音字风险词")

    print("=== 质检结束 ===")


if __name__ == "__main__":
    main()
