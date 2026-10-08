#!/usr/bin/env python3
"""In-place three-way quicksort for one integer file (HW1 Q2)."""
import argparse
import random
from pathlib import Path


def quicksort(values):
    """Iterative randomized three-way quicksort; duplicates are handled in one pass."""
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
            # Process the smaller partition immediately to bound stack growth.
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
