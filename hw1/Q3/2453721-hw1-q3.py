#!/usr/bin/env python3
"""HW1 Q3 的 TCP 分布式快速排序程序。

worker：启动 TCP Worker 并等待排序请求。
master：启动 Coordinator，接收作业文件并向 Worker 分发分组。
submit：从本机打包并上传 Q1、Q2 所需文件，接收排序结果。
"""
import argparse
import concurrent.futures
import io
import json
import os
import re
import socket
import struct
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

MAX_JSON_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_INPUT_FILE_BYTES = 8 * 1024 * 1024


def read_exact(sock, length):
    parts = []
    while length:
        block = sock.recv(min(length, 1024 * 1024))
        if not block:
            raise EOFError('peer closed connection early')
        parts.append(block)
        length -= len(block)
    return b''.join(parts)


def send_json(sock, obj):
    data = json.dumps(obj, separators=(',', ':')).encode()
    sock.sendall(struct.pack('!Q', len(data)) + data)


def recv_json(sock):
    length = struct.unpack('!Q', read_exact(sock, 8))[0]
    if length > MAX_JSON_BYTES:
        raise ValueError('JSON frame exceeds size limit')
    return json.loads(read_exact(sock, length))


def send_blob(sock, data):
    sock.sendall(struct.pack('!Q', len(data)) + data)


def recv_blob(sock, limit=MAX_ARCHIVE_BYTES):
    length = struct.unpack('!Q', read_exact(sock, 8))[0]
    if length > limit:
        raise ValueError('binary frame exceeds size limit')
    return read_exact(sock, length)


def qs(values):
    """TCP Worker 使用的迭代式三路快速排序。"""
    if len(values) < 2:
        return values
    stack, lo, hi = [], 0, len(values) - 1
    while True:
        while lo < hi:
            pivot = values[(lo + hi) // 2]
            lt, i, gt = lo, lo, hi
            while i <= gt:
                if values[i] < pivot:
                    values[lt], values[i] = values[i], values[lt]
                    lt += 1; i += 1
                elif values[i] > pivot:
                    values[i], values[gt] = values[gt], values[i]
                    gt -= 1
                else:
                    i += 1
            if lt - lo < hi - gt:
                if gt + 1 < hi: stack.append((gt + 1, hi))
                hi = lt - 1
            else:
                if lo < lt - 1: stack.append((lo, lt - 1))
                lo = gt + 1
        if not stack:
            break
        lo, hi = stack.pop()
    return values


def worker_connection(conn):
    with conn:
        while True:
            try:
                header = recv_json(conn)
            except (EOFError, ConnectionResetError):
                return
            if header.get('op') == 'stop':
                return
            if header.get('op') != 'sort':
                send_json(conn, {'error': 'unknown operation'})
                return
            size = int(header.get('size', -1))
            if size < 0 or size > MAX_INPUT_FILE_BYTES:
                send_json(conn, {'error': 'input file size is outside the accepted range'})
                return
            source = read_exact(conn, size)
            started = time.monotonic()
            values = [int(x) for x in source.splitlines() if x]
            qs(values)
            result = ''.join(f'{x}\n' for x in values).encode()
            elapsed = time.monotonic() - started
            send_json(conn, {'size': len(result), 'sort_seconds': elapsed})
            conn.sendall(result)


def serve_worker(address):
    host, port = address
    with socket.create_server((host, port), reuse_port=True) as server:
        print(f'worker listening on {host}:{port}', flush=True)
        while True:
            conn, peer = server.accept()
            print(f'worker accepted {peer}', flush=True)
            worker_connection(conn)


def parse_endpoint(value):
    host, sep, port = value.rpartition(':')
    if not sep:
        raise argparse.ArgumentTypeError('endpoint must be HOST:PORT')
    return host, int(port)


def dispatch(endpoint, files, workdir):
    host, port = endpoint
    details = {'upload_seconds': 0.0, 'sort_seconds': 0.0, 'download_seconds': 0.0}
    outputs = []
    with socket.create_connection((host, port), timeout=120) as sock:
        sock.settimeout(1200)
        for path in files:
            data = path.read_bytes()
            started = time.monotonic()
            send_json(sock, {'op': 'sort', 'name': path.name, 'size': len(data)})
            sock.sendall(data)
            details['upload_seconds'] += time.monotonic() - started
            header = recv_json(sock)
            if 'error' in header:
                raise RuntimeError(header['error'])
            started = time.monotonic()
            sorted_data = read_exact(sock, int(header['size']))
            details['download_seconds'] += time.monotonic() - started
            details['sort_seconds'] += float(header['sort_seconds'])
            sid = path.name.split('-hw1-q1-', 1)[0]
            group = path.stem.rsplit('-', 1)[-1]
            output = workdir / f'{sid}-hw1-q2-{group}-qs.txt'
            output.write_bytes(sorted_data)
            outputs.append(output)
    return outputs, details


def handle_submission(conn, workers, scratch):
    meta = recv_json(conn)
    archive = recv_blob(conn, MAX_ARCHIVE_BYTES)
    sid = str(meta.get('sid', ''))
    if not re.fullmatch(r'[0-9]{1,20}', sid):
        raise ValueError('SID must contain 1 to 20 decimal digits')
    unpack_started = time.monotonic()
    folder = Path(tempfile.mkdtemp(prefix='hw1-q3-', dir=scratch))
    (folder / 'upload.zip').write_bytes(archive)
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        members = zf.infolist()
        if len(members) > 32 or sum(member.file_size for member in members) > MAX_ARCHIVE_BYTES:
            raise ValueError('archive contents exceed the accepted limits')
        for member in members:
            target = (folder / member.filename).resolve()
            if folder.resolve() not in target.parents:
                raise ValueError('unsafe archive path')
        zf.extractall(folder)
    data_dir = folder / 'input'
    parts = [data_dir / f'{sid}-hw1-q1-{i}.txt' for i in range(16)]
    missing = [str(p) for p in parts if not p.is_file()]
    if missing:
        raise FileNotFoundError(', '.join(missing))
    archive_unpack_seconds = time.monotonic() - unpack_started
    started = time.monotonic()
    all_outputs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(workers)) as pool:
        jobs = [pool.submit(dispatch, endpoint, parts[i::len(workers)], folder)
                for i, endpoint in enumerate(workers)]
        worker_stats = [job.result() for job in jobs]
    for outputs, _ in worker_stats:
        all_outputs.extend(outputs)
    all_outputs.sort(key=lambda p: int(p.stem.rsplit('-', 2)[-2]))
    sorted_final = folder / f'{sid}-hw1-q2-qs.txt'
    merge_started = time.monotonic()
    merge_sorted_files(all_outputs, sorted_final)
    final_merge_seconds = time.monotonic() - merge_started
    total_distributed = time.monotonic() - started

    ms_started = time.monotonic()
    source = data_dir / f'{sid}-hw1-q1.txt'
    ms_final = folder / f'{sid}-hw1-q2-ms.txt'
    sorter = folder / 'scripts' / '2453721-hw1-q2-ms.py'
    subprocess.run(['python3', str(sorter), str(source), str(ms_final)], check=True)
    time_b = time.monotonic() - ms_started

    packaging_started = time.monotonic()
    results = io.BytesIO()
    with zipfile.ZipFile(results, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in all_outputs + [sorted_final, ms_final]:
                zf.write(path, arcname=path.name)
    result_packaging_seconds = time.monotonic() - packaging_started
    stats = {
        'workers': len(workers),
        'distributed_wall_seconds': total_distributed,
        'final_merge_seconds': final_merge_seconds,
        'time_b_seconds': time_b,
        'archive_unpack_seconds': archive_unpack_seconds,
        'result_packaging_seconds': result_packaging_seconds,
        'worker_compute_max_seconds': max(item[1]['sort_seconds'] for item in worker_stats),
        'worker_timings': [
            {'endpoint': f'{endpoint[0]}:{endpoint[1]}', **stats}
            for endpoint, (_, stats) in zip(workers, worker_stats)
        ],
        'worker_phase_sums': {
            key: max(item[1][key] for item in worker_stats)
            for key in ('upload_seconds', 'sort_seconds', 'download_seconds')
        },
        'result_archive_bytes': results.tell(),
    }
    send_json(conn, stats)
    send_blob(conn, results.getvalue())
    print(json.dumps(stats, indent=2), flush=True)


def merge_sorted_files(inputs, output):
    import heapq
    streams = [open(p, encoding='ascii') for p in inputs]
    try:
        with open(output, 'w', encoding='ascii', buffering=1024 * 1024) as out:
            for value in heapq.merge(*(map(int, f) for f in streams)):
                out.write(f'{value}\n')
    finally:
        for f in streams:
            f.close()


def external_merge_sort(source, output, chunk_size=200000):
    import heapq
    chunks = []
    with tempfile.TemporaryDirectory(prefix='hw1-q3-ms-') as tmp:
        with open(source, encoding='ascii') as f:
            while True:
                values = []
                for _ in range(chunk_size):
                    line = f.readline()
                    if not line: break
                    if line.strip(): values.append(int(line))
                if not values: break
                merge_sort(values)
                path = Path(tmp) / f'{len(chunks)}.txt'
                path.write_text(''.join(f'{x}\n' for x in values), encoding='ascii')
                chunks.append(path)
        merge_sorted_files(chunks, output)


def merge_sort(values):
    """对一个有界内存分块执行稳定的自底向上归并排序。"""
    n = len(values)
    if n < 2:
        return values
    src, dst, width = values, [0] * n, 1
    while width < n:
        for left in range(0, n, 2 * width):
            mid, right = min(left + width, n), min(left + 2 * width, n)
            i, j, k = left, mid, left
            while i < mid and j < right:
                if src[i] <= src[j]:
                    dst[k] = src[i]; i += 1
                else:
                    dst[k] = src[j]; j += 1
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


def master_connection(conn, workers, scratch):
    with conn:
        try:
            handle_submission(conn, workers, scratch)
        except Exception as exc:
            try:
                send_json(conn, {'error': 'request failed; consult the server log'})
            except Exception:
                pass
            print(f'submission failed: {exc}', flush=True)


def serve_master(address, workers, scratch):
    Path(scratch).mkdir(parents=True, exist_ok=True)
    with socket.create_server(address, reuse_port=True) as server:
        print(f'master listening on {address[0]}:{address[1]}', flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            while True:
                conn, peer = server.accept()
                print(f'submission from {peer}', flush=True)
                pool.submit(master_connection, conn, workers, scratch)


def submit(server, sid, root, output):
    host, port = server
    start = time.monotonic()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
        inp = root / 'Q1' / 'output'
        for i in range(16):
            zf.write(inp / f'{sid}-hw1-q1-{i}.txt', f'input/{sid}-hw1-q1-{i}.txt')
        zf.write(inp / f'{sid}-hw1-q1.txt', f'input/{sid}-hw1-q1.txt')
        for script in ('2453721-hw1-q2-qs.py', '2453721-hw1-q2-ms.py'):
            zf.write(root / 'Q2' / script, f'scripts/{script}')
    archive_data = archive.getvalue()
    input_packaging_seconds = time.monotonic() - start
    with socket.create_connection((host, port), timeout=120) as sock:
        sock.settimeout(1200)
        send_json(sock, {'sid': sid})
        upload_started = time.monotonic()
        send_blob(sock, archive_data)
        upload_seconds = time.monotonic() - upload_started
        stats = recv_json(sock)
        if 'error' in stats:
            raise RuntimeError(stats['error'])
        download_started = time.monotonic()
        result = recv_blob(sock)
        download_seconds = time.monotonic() - download_started
    output.mkdir(parents=True, exist_ok=True)
    extract_started = time.monotonic()
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        zf.extractall(output)
    extract_seconds = time.monotonic() - extract_started
    stats['client_upload_bytes'] = len(archive_data)
    stats['input_packaging_seconds'] = input_packaging_seconds
    stats['client_upload_seconds'] = upload_seconds
    stats['client_download_seconds'] = download_seconds
    stats['client_extract_seconds'] = extract_seconds
    stats['client_roundtrip_seconds'] = time.monotonic() - start
    stats['time_a_seconds'] = sum((
        input_packaging_seconds,
        upload_seconds,
        stats['archive_unpack_seconds'],
        stats['distributed_wall_seconds'],
        stats['result_packaging_seconds'],
        download_seconds,
        extract_seconds,
    ))
    stats['speedup_ratio_time_a_over_b'] = (
        stats['time_a_seconds'] / stats['time_b_seconds'] if stats['time_b_seconds'] else None
    )
    (output / 'timings.json').write_text(json.dumps(stats, indent=2) + '\n')
    print(json.dumps(stats, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    w = sub.add_parser('worker')
    w.add_argument('--listen', type=parse_endpoint, default=('0.0.0.0', 9700))
    m = sub.add_parser('master')
    m.add_argument('--listen', type=parse_endpoint, default=('0.0.0.0', 9701))
    m.add_argument('--workers', required=True, help='以逗号分隔的 HOST:PORT Worker 地址')
    m.add_argument('--workdir', type=Path, default=Path('/tmp/hw1-q3'))
    c = sub.add_parser('submit')
    c.add_argument('--server', required=True, type=parse_endpoint)
    c.add_argument('--sid', default=os.environ.get('SID', '2453721'))
    c.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    c.add_argument('--output', type=Path, default=Path('output'))
    a = p.parse_args()
    if a.mode == 'worker':
        serve_worker(a.listen)
    elif a.mode == 'master':
        workers = [parse_endpoint(x) for x in a.workers.split(',')]
        if not workers:
            p.error('master requires at least one HOST:PORT worker')
        serve_master(a.listen, workers, a.workdir)
    else:
        submit(a.server, a.sid, a.root.resolve(), a.output.resolve())


if __name__ == '__main__':
    main()
