#!/usr/bin/env python3
"""检查候选文件是否升序排列，并与基准文件逐行一致。"""
import argparse
from pathlib import Path


def verify_sorted(path: Path) -> int:
    count = 0
    previous = None
    with path.open(encoding='ascii') as f:
        for line_no, line in enumerate(f, 1):
            value = int(line)
            if previous is not None and value < previous:
                raise ValueError(f'{path}: descending pair at line {line_no}')
            previous = value
            count += 1
    return count


def verify_equal(reference: Path, candidate: Path) -> int:
    count = 0
    with reference.open(encoding='ascii') as left, candidate.open(encoding='ascii') as right:
        for count, (a, b) in enumerate(zip(left, right, strict=True), 1):
            if a != b:
                raise ValueError(f'{candidate}: differs from {reference} at line {count}')
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidates', nargs='+', type=Path)
    args = parser.parse_args()
    expected = verify_sorted(args.reference)
    print(f'OK sorted: {args.reference} ({expected} rows)')
    for candidate in args.candidates:
        actual = verify_sorted(candidate)
        if actual != expected:
            raise ValueError(f'{candidate}: {actual} rows, expected {expected}')
        verify_equal(args.reference, candidate)
        print(f'OK sorted and identical: {candidate} ({actual} rows)')


if __name__ == '__main__':
    main()
