#!/usr/bin/env python3
"""External merge sort and k-way merge for HW1 Q2."""
import argparse
import heapq
import os
import tempfile
from pathlib import Path


def merge_sort(values):
    """Stable bottom-up merge sort, in O(n log n) time and O(n) extra space."""
    n = len(values)
    if n < 2:
        return values
    src = values
    dst = [0] * n
    width = 1
    while width < n:
        for left in range(0, n, 2 * width):
            mid = min(left + width, n)
            right = min(left + 2 * width, n)
            i, j, k = left, mid, left
            while i < mid and j < right:
                if src[i] <= src[j]:
                    dst[k] = src[i]
                    i += 1
                else:
                    dst[k] = src[j]
                    j += 1
                k += 1
            while i < mid:
                dst[k] = src[i]; i += 1; k += 1
            while j < right:
                dst[k] = src[j]; j += 1; k += 1
        src, dst = dst, src
        width *= 2
    if src is not values:
        values[:] = src
    return values


def write_merged(inputs, output):
    """Merge sorted text files and atomically replace output."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    streams = [open(path, encoding='ascii') for path in inputs]
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='ascii', dir=output.parent,
                                         delete=False, buffering=1024 * 1024) as f:
            tmp = f.name
            for value in heapq.merge(*(map(int, stream) for stream in streams)):
                f.write(f'{value}\n')
        os.replace(tmp, output)
    finally:
        for stream in streams:
            stream.close()
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def sort_file(source, output, chunk_size=200000):
    """External merge sort: sort bounded chunks, then k-way merge them."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    tmpdir = tempfile.TemporaryDirectory(dir=output.parent, prefix='.hw1-ms-')
    try:
        with open(source, encoding='ascii') as f:
            while True:
                values = []
                for _ in range(chunk_size):
                    line = f.readline()
                    if not line:
                        break
                    if line.strip():
                        values.append(int(line))
                if not values:
                    break
                merge_sort(values)
                path = Path(tmpdir.name) / f'chunk-{len(chunks)}.txt'
                with path.open('w', encoding='ascii', buffering=1024 * 1024) as chunk:
                    chunk.writelines(f'{n}\n' for n in values)
                chunks.append(path)
        write_merged(chunks, output)
    finally:
        tmpdir.cleanup()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--chunk-size', type=int, default=200000)
    p.add_argument('--merge', action='store_true', help='merge already sorted input files')
    p.add_argument('extra_inputs', nargs='*', type=Path)
    args = p.parse_args()
    if args.merge:
        write_merged([args.input, *args.extra_inputs], args.output)
    else:
        sort_file(args.input, args.output, args.chunk_size)


if __name__ == '__main__':
    main()
