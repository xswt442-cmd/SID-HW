#!/usr/bin/env python3
"""对单个整数文件执行原地三路快速排序。"""
import argparse
import random
from pathlib import Path


def quicksort(values):
    """使用迭代式随机三路快排，一次处理与基准值相等的元素。"""
    if len(values) < 2:
        return values
    rng = random.Random(0)
    stack = [(0, len(values) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            pivot = values[rng.randrange(lo, hi + 1)]
            lt, i, gt = lo, lo, hi
            while i <= gt:
                if values[i] < pivot:
                    values[lt], values[i] = values[i], values[lt]
                    lt += 1
                    i += 1
                elif values[i] > pivot:
                    values[i], values[gt] = values[gt], values[i]
                    gt -= 1
                else:
                    i += 1
            # 优先处理较小区间，控制待处理区间栈的增长。
            if lt - lo < hi - gt:
                if gt + 1 < hi:
                    stack.append((gt + 1, hi))
                hi = lt - 1
            else:
                if lo < lt - 1:
                    stack.append((lo, lt - 1))
                lo = gt + 1
    return values


def main():
    p = argparse.ArgumentParser()
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    with args.input.open(encoding='ascii') as f:
        values = [int(line) for line in f if line.strip()]
    quicksort(values)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='ascii', buffering=1024 * 1024) as f:
        f.writelines(f'{n}\n' for n in values)


if __name__ == '__main__':
    main()
