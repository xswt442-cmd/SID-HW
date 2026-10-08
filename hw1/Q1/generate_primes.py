#!/usr/bin/env python3
"""Generate deterministic, uniformly sampled 32-bit primes for HW1 Q1."""
import argparse
import random
from pathlib import Path

LIMIT = 1 << 32
# Deterministic Miller-Rabin bases for unsigned 32-bit integers.
BASES = (2, 3, 5, 7, 11, 13)


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for p in small:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in BASES:
        if a >= n:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--sid', required=True, help='seed; a numeric SID is used as an integer')
    p.add_argument('--count', type=int, default=131072)
    p.add_argument('--groups', type=int, default=16)
    p.add_argument('--output-dir', type=Path, default=Path('output'))
    args = p.parse_args()
    if args.count < 0 or args.groups < 1:
        p.error('count must be nonnegative and groups must be positive')
    try:
        seed = int(args.sid)
    except ValueError:
        seed = args.sid
    rng = random.Random(seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for group in range(args.groups):
        path = args.output_dir / f'{args.sid}-hw1-q1-{group}.txt'
        with path.open('w', encoding='ascii', buffering=1024 * 1024) as f:
            for _ in range(args.count):
                # Rejection sampling over the required interval gives uniform primes.
                while True:
                    candidate = rng.randrange(2, LIMIT)
                    if is_prime(candidate):
                        f.write(f'{candidate}\n')
                        break
        print(f'generated {path} ({args.count} primes)')


if __name__ == '__main__':
    main()
