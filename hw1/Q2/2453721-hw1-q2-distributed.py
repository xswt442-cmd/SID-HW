#!/usr/bin/env python3
"""通过 SCP/SSH 分发分组文件；Docker Worker 的目标格式为 user@host::container。"""
import argparse
import concurrent.futures
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path


def run(cmd):
    subprocess.run(cmd, check=True)


def parse_worker(spec):
    target, sep, container = spec.partition('::')
    if sep and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}', container):
        raise ValueError(f'Worker 配置中的 Docker 容器名无效：{spec}')
    return {'spec': spec, 'target': target, 'container': container if sep else None}


def ensure_docker_worker(worker, workdir):
    name = worker['container']
    if not name:
        return
    base = workdir.rstrip('/')
    command = ' '.join([
        'set -eu;',
        'name=' + shlex.quote(name) + ';',
        'base=' + shlex.quote(base) + ';',
        'mkdir -p "$base";',
        'docker image inspect python:3.12-slim >/dev/null 2>&1 || docker pull python:3.12-slim;',
        'if docker container inspect "$name" >/dev/null 2>&1; then',
        '  mounted=$(docker inspect --format ' + shlex.quote(
            '{{range .Mounts}}{{if eq .Destination "/work"}}{{.Source}}{{end}}{{end}}'
        ) + ' "$name");',
        '  if [ "$mounted" != "$base" ]; then echo "existing container has an unexpected /work mount" >&2; exit 2; fi;',
        '  running=$(docker inspect --format ' + shlex.quote('{{.State.Running}}') + ' "$name");',
        '  if [ "$running" != true ]; then docker start "$name" >/dev/null; fi;',
        'else',
        '  docker run -d --name "$name" --cpus=1 --memory=384m --pids-limit=128 --mount "type=bind,source=$base,target=/work" --workdir /work python:3.12-slim sleep infinity >/dev/null;',
        'fi;',
        'docker exec "$name" python3 --version',
    ])
    run(['ssh', worker['target'], command])


def task(worker, files, quicksort, workdir, local_out):
    target, container = worker['target'], worker['container']
    timings = {}
    remote = f'{workdir.rstrip("/")}/hw1-{os.getpid()}-{time.time_ns()}'
    run(['ssh', target, 'mkdir', '-p', remote])
    start = time.monotonic()
    run(['scp', '-q', str(quicksort), f'{target}:{remote}/qsort.py'])
    for f in files:
        run(['scp', '-q', str(f), f'{target}:{remote}/{f.name}'])
    timings['upload'] = time.monotonic() - start
    start = time.monotonic()
    for f in files:
        group = f.stem.rsplit('-', 1)[-1]
        out = f'{f.stem.split("-hw1-q1-")[0]}-hw1-q2-{group}-qs.txt'
        command = ' && '.join([
            f'cd {shlex.quote(remote)}',
            f'python3 qsort.py {shlex.quote(f.name)} {shlex.quote(out)}',
        ])
        if container:
            base = workdir.rstrip('/')
            if not remote.startswith(base + '/'):
                raise ValueError('Docker Worker 的远程工作目录必须位于 --remote-dir 下')
            in_container = '/work' + remote[len(base):]
            command = (
                f'docker exec {shlex.quote(container)} python3 '
                f'{shlex.quote(in_container + "/qsort.py")} '
                f'{shlex.quote(in_container + "/" + f.name)} '
                f'{shlex.quote(in_container + "/" + out)}'
            )
        run(['ssh', target, command])
    timings['sort'] = time.monotonic() - start
    start = time.monotonic()
    for f in files:
        group = f.stem.rsplit('-', 1)[-1]
        out = f'{f.stem.split("-hw1-q1-")[0]}-hw1-q2-{group}-qs.txt'
        remote_file = f'{remote}/{out}'
        run(['scp', '-q', f'{target}:{remote_file}', str(local_out / out)])
    timings['download'] = time.monotonic() - start
    run(['ssh', target, 'rm', '-rf', remote])
    return timings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sid', default=os.environ.get('SID', '2453721'))
    p.add_argument('--k', type=int, choices=(2, 4), required=True)
    p.add_argument('--workers', default=os.environ.get('WORKERS', ''),
                   help='以逗号分隔的 SSH 目标；Docker Worker 使用 user@host::container 格式')
    repo = Path(__file__).resolve().parents[1]
    p.add_argument('--data-dir', type=Path, default=repo / 'Q1' / 'output')
    p.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent / 'output')
    p.add_argument('--remote-dir', default='/tmp/sid-hw1')
    args = p.parse_args()
    specs = [x.strip() for x in args.workers.split(',') if x.strip()]
    if len(specs) != args.k:
        p.error(f'--workers 必须恰好列出 K={args.k} 个 SSH 目标')
    try:
        workers = [parse_worker(spec) for spec in specs]
    except ValueError as exc:
        p.error(str(exc))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    groups = [[args.data_dir / f'{args.sid}-hw1-q1-{i}.txt'
               for i in range(16) if i % args.k == worker] for worker in range(args.k)]
    for group in sum(groups, []):
        if not group.is_file():
            p.error(f'missing input: {group}')
    for worker in workers:
        ensure_docker_worker(worker, args.remote_dir)
    quicksort = Path(__file__).resolve().parent / '2453721-hw1-q2-qs.py'
    wall_start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.k) as pool:
        jobs = [pool.submit(task, worker, group, quicksort, args.remote_dir, args.output_dir)
                for worker, group in zip(workers, groups)]
        results = [job.result() for job in jobs]
    ms = Path(__file__).resolve().parent / '2453721-hw1-q2-ms.py'
    sorted_parts = [args.output_dir / f'{args.sid}-hw1-q2-{i}-qs.txt' for i in range(16)]
    start = time.monotonic()
    # 将有序分组文件传给多路归并模式。
    cmd = ['python3', str(ms), '--merge', str(sorted_parts[0]),
           str(args.output_dir / f'{args.sid}-hw1-q2-qs.txt'), *map(str, sorted_parts[1:])]
    run(cmd)
    merge_seconds = time.monotonic() - start
    time_a = time.monotonic() - wall_start
    merged_input = args.data_dir / f'{args.sid}-hw1-q1.txt'
    ms_output = args.output_dir / f'{args.sid}-hw1-q2-ms.txt'
    start = time.monotonic()
    run(['python3', str(ms), str(merged_input), str(ms_output)])
    time_b = time.monotonic() - start
    print(f'upload max: {max(r["upload"] for r in results):.3f}s')
    print(f'remote quicksort max: {max(r["sort"] for r in results):.3f}s')
    print(f'download max: {max(r["download"] for r in results):.3f}s')
    print(f'local final merge: {merge_seconds:.3f}s')
    print(f'time-A (parallel SCP/SSH plus final merge): {time_a:.3f}s')
    print(f'time-B (local merge sort): {time_b:.3f}s')
    print(f'speedup ratio time-A/time-B: {time_a / time_b:.3f}')
    timing_data = {
        'sid': args.sid,
        'k': args.k,
        'workers': [
            {'ssh_target': worker['target'], 'docker_container': worker['container'], **timings}
            for worker, timings in zip(workers, results)
        ],
        'upload_max_seconds': max(r['upload'] for r in results),
        'remote_quicksort_max_seconds': max(r['sort'] for r in results),
        'download_max_seconds': max(r['download'] for r in results),
        'final_merge_seconds': merge_seconds,
        'time_a_seconds': time_a,
        'time_b_seconds': time_b,
        'time_a_over_time_b': time_a / time_b if time_b else None,
    }
    (args.output_dir / 'timings.json').write_text(
        json.dumps(timing_data, indent=2) + '\n', encoding='utf-8'
    )


if __name__ == '__main__':
    main()
