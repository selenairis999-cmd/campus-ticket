# -*- coding: utf-8 -*-
"""
load_test.py —— 抢票接口并发压测（论文 6.3 节 / 表 13）

以 N 个独立学生账号（每线程一个账号，避免触发单用户限频规则）同时抢一张
库存为 M 的活动门票，统计：
    - 成功数 / 各类失败原因分布
    - 平均响应时间与 P50 / P90 / P99
    - 库存守恒校验：成功数 + 剩余库存 == 初始库存（验证无超卖）
    - 数据库订单数 / 电子票数（验证无脏数据）

测试结束后自动清理：测试活动、测试账号及其订单、电子票、抢票日志。

用法：
    python load_test.py --threads 200 --stock 99
    python load_test.py --threads 50 --stock 50 --keep   # 保留测试数据便于排查

注意：请先确认后端已启动（默认 http://localhost:8080），
      并将 application.yml 中 risk.enabled 置为 false，
      否则 R1/R2 规则会拦截部分压测流量（本脚本每线程使用独立账号，
      正常情况下不会触发 R1 单用户限频）。
"""
import argparse
import collections
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = os.environ.get('LOAD_TEST_BASE', 'http://localhost:8080')
PREFIX = 'lt_'


def post(path, data, token=None, timeout=30, json_body=False):
    """发送 POST 请求，返回 (耗时ms, HTTP状态, 响应JSON)。"""
    url = BASE + path
    if json_body:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        ctype = 'application/json;charset=UTF-8'
    else:
        body = urllib.parse.urlencode(data).encode()
        ctype = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', ctype)
    if token:
        req.add_header('token', token)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        status = e.code
    except Exception as e:
        return (time.perf_counter() - t0) * 1000, 0, {'message': 'request failed: %s' % e}
    ms = (time.perf_counter() - t0) * 1000
    try:
        return ms, status, json.loads(raw)
    except Exception:
        return ms, status, {'message': raw[:200]}


def get(path, token=None, timeout=30):
    url = BASE + path
    req = urllib.request.Request(url, method='GET')
    if token:
        req.add_header('token', token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8'))
    except Exception as e:
        return {'message': 'request failed: %s' % e}


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument('--threads', type=int, default=200, help='并发线程数（= 独立账号数）')
    ap.add_argument('--stock', type=int, default=99, help='活动初始库存')
    ap.add_argument('--base', default=BASE)
    ap.add_argument('--keep', action='store_true', help='保留测试数据')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    BASE = args.base
    N, M = args.threads, args.stock
    print('压测目标：%s' % BASE)
    print('并发线程数：%d    初始库存：%d\n' % (N, M))

    # ---------- 1. 组织者登录（创建测试活动需要组织者角色） ----------
    _, _, r = post('/auth/login', {'username': 'organizer01', 'password': '123456'})
    org_token = (r.get('data') or {}).get('token')
    if not org_token:
        raise SystemExit('组织者登录失败：%s' % r)

    # ---------- 2. 创建测试活动 ----------
    from datetime import datetime, timedelta
    fmt = '%Y-%m-%dT%H:%M:%S'
    now = datetime.now()
    act_title = '压测活动-%d并发-%s' % (N, now.strftime('%H%M%S'))
    _, _, r = post('/activity/create', {
        'title': act_title, 'description': '并发压测临时活动', 'location': '测试场地',
        'signStartTime': (now - timedelta(minutes=1)).strftime(fmt),
        'signEndTime': (now + timedelta(hours=1)).strftime(fmt),
        'startTime': (now + timedelta(hours=2)).strftime(fmt),
        'endTime': (now + timedelta(hours=4)).strftime(fmt),
        'totalStock': M,
    }, org_token, json_body=True)
    if r.get('code') != 200:
        raise SystemExit('创建测试活动失败：%s' % r)
    # 取最新创建的活动 id
    acts = get('/activity/page?pageNum=1&pageSize=5', org_token).get('data') or {}
    records = acts.get('records') or []
    activity = next((a for a in records if a.get('title') == act_title), None)
    if not activity:
        raise SystemExit('未能定位测试活动')
    aid = activity['id']
    print('测试活动 id=%d  标题=%s  库存=%d' % (aid, act_title, activity.get('totalStock')))

    # ---------- 3. 注册并登录 N 个独立账号 ----------
    print('注册 %d 个测试账号...' % N)
    accounts, lock, done = [], threading.Lock(), [0]

    # 手机号必须全局唯一（SysUserServiceImpl.register 会校验），
    # 用 137 段 + 运行序号，避免与演示账号的 138 段冲突，也避免多线程取时间导致重号。
    phone_base = int(time.time()) % 1000000

    def prepare(i):
        u = '%s%d_%d' % (PREFIX, int(time.time()) % 100000, i)
        phone = '137%08d' % ((phone_base * 1000 + i) % 100000000)
        post('/auth/register', {'username': u, 'password': '123456',
                                'name': '压测账号%d' % i, 'phone': phone})
        _, _, lr = post('/auth/login', {'username': u, 'password': '123456'})
        tok = (lr.get('data') or {}).get('token')
        if tok:
            with lock:
                accounts.append((u, tok))
                done[0] += 1
                if done[0] % 50 == 0:
                    print('  已就绪 %d/%d' % (done[0], N))

    ts = [threading.Thread(target=prepare, args=(i,)) for i in range(N)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print('账号就绪：%d/%d\n' % (len(accounts), N))
    if len(accounts) < N:
        print('警告：部分账号注册/登录失败，实际并发数为 %d' % len(accounts))

    # ---------- 4. 并发抢票 ----------
    print('开始并发抢票（%d 线程）...' % len(accounts))
    results, times = [], []
    rlock = threading.Lock()
    barrier = threading.Barrier(len(accounts))

    def grab(uname, tok):
        try:
            barrier.wait(timeout=60)
        except Exception:
            pass
        ms, status, r = post('/activity/grab', {'activityId': aid}, tok)
        with rlock:
            times.append(ms)
            results.append((uname, r.get('code'), r.get('msg') or r.get('message') or ''))

    ts = [threading.Thread(target=grab, args=a) for a in accounts]
    t0 = time.perf_counter()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    wall = time.perf_counter() - t0

    # ---------- 5. 统计 ----------
    ok = [r for r in results if r[1] == 200]
    fail = [r for r in results if r[1] != 200]
    reasons = collections.Counter(r[2] for r in fail)
    times.sort()

    def pct(p):
        if not times:
            return 0.0
        idx = min(len(times) - 1, int(round(p / 100.0 * len(times))) - 1)
        return times[max(0, idx)]

    print('\n' + '=' * 64)
    print('并发线程数        : %d' % len(accounts))
    print('初始库存          : %d' % M)
    print('成功抢票数        : %d' % len(ok))
    print('失败数            : %d' % len(fail))
    print('成功率            : %.1f%%' % (len(ok) * 100.0 / max(1, len(results))))
    print('总耗时            : %.2f s   吞吐量: %.1f req/s' % (wall, len(results) / max(wall, 1e-9)))
    print('平均响应时间      : %.1f ms' % statistics.mean(times))
    print('P50 / P90 / P99   : %.1f / %.1f / %.1f ms' % (pct(50), pct(90), pct(99)))
    print('最小 / 最大       : %.1f / %.1f ms' % (min(times), max(times)))
    ok_times = sorted(ms for ms, (_, c, _) in zip(times, results) if c == 200)
    if ok_times:
        print('成功请求平均响应  : %.1f ms' % statistics.mean(ok_times))
    print('\n失败原因分布：')
    for msg, cnt in reasons.most_common():
        print('  %-28s %d' % (msg, cnt))

    # ---------- 6. 库存守恒校验 ----------
    detail = get('/activity/detail?activityId=%d' % aid, org_token).get('data') or {}
    remain = detail.get('remainStock')
    print('\n库存守恒校验：成功 %d + 剩余 %s = %s （初始 %d）'
          % (len(ok), remain, (len(ok) + (remain or 0)), M))
    oversold = (len(ok) + (remain or 0)) > M
    print('是否超卖          : %s' % ('是（存在超卖！）' if oversold else '否'))

    # 数据库侧订单/电子票数
    try:
        import pymysql
        conn = pymysql.connect(host='localhost', port=3306, user='root', password='123456',
                               database='campus_ticket', charset='utf8mb4')
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM ticket_order WHERE activity_id=%s', (aid,))
        orders = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM eticket WHERE activity_id=%s', (aid,))
        etickets = cur.fetchone()[0]
        cur.execute("""SELECT result, COUNT(*) FROM grab_log WHERE activity_id=%s
                       GROUP BY result ORDER BY result""", (aid,))
        logs = dict(cur.fetchall())
        cur.execute('SELECT remain_stock, version FROM activity WHERE id=%s', (aid,))
        dbrow = cur.fetchone()
        print('数据库订单数      : %d' % orders)
        print('数据库电子票数    : %d' % etickets)
        print('数据库剩余库存    : %s  version=%s' % dbrow)
        print('抢票日志分布      : %s' % logs)
        if not args.keep:
            cur.execute('DELETE FROM eticket WHERE activity_id=%s', (aid,))
            cur.execute('DELETE FROM ticket_order WHERE activity_id=%s', (aid,))
            cur.execute('DELETE FROM grab_log WHERE activity_id=%s', (aid,))
            cur.execute('DELETE FROM ticket WHERE activity_id=%s', (aid,))
            cur.execute('DELETE FROM activity WHERE id=%s', (aid,))
            cur.execute("DELETE FROM sys_user WHERE username LIKE %s", (PREFIX + '%',))
            conn.commit()
            print('\n已清理测试活动、测试账号及其订单、电子票与抢票日志')
        cur.close(); conn.close()
    except ImportError:
        print('（未安装 pymysql，跳过数据库侧校验与清理）')

    print('=' * 64)


if __name__ == '__main__':
    import urllib.parse
    main()
