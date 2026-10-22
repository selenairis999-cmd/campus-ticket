# -*- coding: utf-8 -*-
"""
压测复现驱动：先预热，再对每个场景跑 N 轮，输出每轮原始值与中位数。

用法:
    python tools/run_load_matrix.py            # 默认 3 轮
    python tools/run_load_matrix.py --runs 5

前置条件：应用已启动，且 application.yml 中 risk.enabled=false（见 README 7.3）。
结果写入 压测结果.csv（项目根目录），中位数可直接填入论文表 13。
"""
import argparse
import csv
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'tools' / 'load_test.py'
SCENARIOS = [(50, 50), (100, 100), (200, 99), (200, 200)]

PATTERNS = {
    'success': r'成功抢票数\s*:\s*(\d+)',
    'fail': r'失败数\s*:\s*(\d+)',
    'avg': r'平均响应时间\s*:\s*([\d.]+)',
    'ok_avg': r'成功请求平均响应\s*:\s*([\d.]+)',
    'p99': r'P50 / P90 / P99\s*:\s*[\d.]+ / [\d.]+ / ([\d.]+)',
    'throughput': r'吞吐量:\s*([\d.]+)',
    'oversell': r'是否超卖\s*:\s*(\S+)',
}


def run_once(threads, stock):
    """跑一次压测，解析输出。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--threads', str(threads), '--stock', str(stock)],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd=str(ROOT),
    )
    out = proc.stdout + proc.stderr
    row = {'threads': threads, 'stock': stock}
    for key, pat in PATTERNS.items():
        m = re.search(pat, out)
        row[key] = m.group(1) if m else ''
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=3, help='每个场景的测量轮数（默认 3）')
    ap.add_argument('--warmup', type=int, default=2, help='预热轮数（丢弃，默认 2）')
    args = ap.parse_args()

    print('=' * 70)
    print(f'预热 {args.warmup} 轮（不计入统计）')
    print('=' * 70)
    for i in range(1, args.warmup + 1):
        r = run_once(200, 99)
        print(f'  预热 {i}: 平均 {r["avg"]} ms  成功 {r["success"]}')

    all_rows = []
    print()
    print('=' * 70)
    print(f'正式测量：每个场景 {args.runs} 轮')
    print('=' * 70)
    for threads, stock in SCENARIOS:
        rows = []
        for i in range(1, args.runs + 1):
            r = run_once(threads, stock)
            r['run'] = i
            rows.append(r)
            print(f'  {threads:>3}并发/{stock:>3}库存 第{i}轮: '
                  f'成功 {r["success"]:>3} 失败 {r["fail"]:>3} '
                  f'平均 {r["avg"]:>7} ms  成功均值 {r["ok_avg"]:>7} ms  '
                  f'P99 {r["p99"]:>7}  吞吐 {r["throughput"]:>6} req/s  超卖 {r["oversell"]}')
        all_rows.extend(rows)

    print()
    print('=' * 70)
    print('中位数汇总（可填入论文表 13）')
    print('=' * 70)
    print(f'{"并发":>5} {"库存":>5} {"成功":>5} {"售罄拒绝":>9} {"平均(ms)":>9} '
          f'{"成功均值(ms)":>13} {"P99(ms)":>9} {"吞吐(req/s)":>12} {"超卖":>5}')
    summary = []
    for threads, stock in SCENARIOS:
        rows = [r for r in all_rows if r['threads'] == threads and r['stock'] == stock]
        med = lambda k: statistics.median([float(r[k]) for r in rows if r[k] != ''])
        success = rows[0]['success']
        fail = rows[0]['fail']
        oversell = '否' if all(r['oversell'] == '否' for r in rows) else '是'
        summary.append({
            'threads': threads, 'stock': stock, 'success': success, 'fail': fail,
            'median_avg': med('avg'), 'median_ok_avg': med('ok_avg'),
            'median_p99': med('p99'), 'median_throughput': med('throughput'),
            'oversell': oversell,
        })
        print(f'{threads:>5} {stock:>5} {success:>5} {fail:>9} {med("avg"):>9.1f} '
              f'{med("ok_avg"):>13.1f} {med("p99"):>9.1f} {med("throughput"):>12.1f} {oversell:>5}')

    out_csv = ROOT / '压测结果.csv'
    with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['threads', 'stock', 'run', 'success', 'fail',
                                          'avg', 'ok_avg', 'p99', 'throughput', 'oversell'])
        w.writeheader()
        w.writerows(all_rows)
    print()
    print(f'原始数据已写入: {out_csv}')


if __name__ == '__main__':
    main()
