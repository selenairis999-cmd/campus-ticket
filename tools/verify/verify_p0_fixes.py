# -*- coding: utf-8 -*-
"""P0 修复端到端验证：
P0-2 封禁账号的旧 token 是否被全站拦截
P0-3 二维码时间窗是否双向（伪造未来时间戳应被拒）
P0-1 抢票事务回滚（票种库存与活动库存是否守恒）
结果写入 _verify_out.txt（UTF-8），避免控制台编码问题。
"""
import io
import json
import os
import time
import hashlib
import threading
import urllib.parse
import urllib.request

import pymysql

BASE = 'http://127.0.0.1:8080'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '_verify_out.txt')
# 与运行时 application-local.yml 的 qrcode.secret 保持一致；密钥不入库，
# 从同名环境变量读取（本地跑：先 set QRCODE_SECRET=... 再执行本脚本）。
QR_SECRET = os.environ.get('QRCODE_SECRET', 'set-QRCODE_SECRET-env-var')

DB = dict(host=os.environ.get('MYSQL_HOST', 'localhost'), port=3306,
          user=os.environ.get('MYSQL_USER', 'root'),
          password=os.environ.get('MYSQL_PASSWORD', '123456'),
          database='campus_ticket', charset='utf8mb4')

buf = io.StringIO()


def log(*a):
    line = ' '.join(str(x) for x in a)
    buf.write(line + '\n')
    print(line.encode('ascii', 'replace').decode('ascii'))


def post(path, params, token=None):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(BASE + path, data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    if token:
        req.add_header('token', token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8'))


def get(path, params=None, token=None):
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    if token:
        req.add_header('token', token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8'))


def login(username, password='123456'):
    return post('/auth/login', {'username': username, 'password': password})


conn = pymysql.connect(**DB)
cur = conn.cursor()

# ============ 准备 token ============
log('=' * 60)
log('准备：登录各角色账号')
admin = login('admin')
log('admin      ->', admin.get('code'), admin.get('msg'))
admin_tok = admin['data']['token']

s01 = login('student01')
s02 = login('student02')
checker = login('checker01')
s01_tok, s02_tok, checker_tok = s01['data']['token'], s02['data']['token'], checker['data']['token']
log('student01  ->', s01.get('code'))
log('student02  ->', s02.get('code'))
log('checker01  ->', checker.get('code'))

# ============ P0-2 封禁旧 token 全站拦截 ============
log('')
log('=' * 60)
log('P0-2 封禁账号的旧 token 是否被全站拦截')
victim = login('student12')          # 用 student12 做实验对象
victim_tok = victim['data']['token']
victim_id = victim['data']['userId']
log('实验对象 student12 id=%s，先确认旧 token 可用：' % victim_id)
r = get('/activity/page', {'pageNum': 1, 'pageSize': 1}, token=victim_tok)
log('  封禁前 /activity/page ->', r.get('code'), r.get('msg'))

log('管理员封禁 student12（1天）：')
r = post('/risk/ban', {'userId': victim_id, 'days': 1, 'reason': 'P0-2 自动化验证'}, token=admin_tok)
log('  ban ->', r.get('code'), r.get('msg'))

for path, params in [('/activity/page', {'pageNum': 1, 'pageSize': 1}),
                     ('/ticket/myList', {}),
                     ('/comment/quota', {}),
                     ('/activity/list', {})]:
    r = get(path, params, token=victim_tok)
    log('  封禁后用旧 token 访问 %-18s -> %s %s' % (path, r.get('code'), r.get('msg')))

log('重新登录（登录入口也应拦截）：')
r = login('student12')
log('  login ->', r.get('code'), r.get('msg'))

log('管理员解封：')
r = post('/risk/unban', {'userId': victim_id}, token=admin_tok)
log('  unban ->', r.get('code'), r.get('msg'))
r = get('/activity/page', {'pageNum': 1, 'pageSize': 1}, token=victim_tok)
log('  解封后旧 token 访问 /activity/page ->', r.get('code'), r.get('msg'))

# ============ P0-3 二维码双向时间窗 ============
log('')
log('=' * 60)
log('P0-3 二维码时间窗是否双向（伪造未来时间戳）')

cur.execute("SELECT ticket_code FROM eticket WHERE status=0 AND user_id=%s LIMIT 1", (s01['data']['userId'],))
row = cur.fetchone()
code = row[0]
log('取一张 student01 的未核销票：', code)

r = get('/ticket/qrcode', {'ticketId': None}, token=s01_tok)  # 探测参数名
log('  /ticket/qrcode 探测 ->', r.get('code'), r.get('msg'))


def make_qr(ticket_code, ts):
    raw = '%s&%s&%s' % (ticket_code, ts, QR_SECRET)
    sig = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return '%s.%s.%s' % (ticket_code, ts, sig)


now_ms = int(time.time() * 1000)
cases = [
    ('正常（当前时间）', now_ms),
    ('未来 +1 小时（旧代码会永久有效）', now_ms + 3600 * 1000),
    ('未来 +10 秒（超出 5 秒容差）', now_ms + 10 * 1000),
    ('过期 -60 秒', now_ms - 60 * 1000),
]
for name, ts in cases:
    qr = make_qr(code, ts)
    r = post('/checkin/verify', {'qrContent': qr}, token=checker_tok)
    log('  %-32s -> %s %s' % (name, r.get('code'), r.get('msg')))

# ============ P0-1 抢票事务回滚 ============
log('')
log('=' * 60)
log('P0-1 抢票事务回滚：两个票种各 1 张、活动总库存 2，两人同时抢不同票种')

cur.execute("SELECT id FROM sys_user WHERE username='organizer01'")
org_id = cur.fetchone()[0]
now = time.strftime('%Y-%m-%d %H:%M:%S')
sign_start = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - 3600))
sign_end = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400))
act_start = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400 * 2))
act_end = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400 * 2 + 7200))

cur.execute(
    "INSERT INTO activity(title,description,location,sign_start_time,sign_end_time,start_time,end_time,"
    "organizer_id,status,total_stock,remain_stock,version,create_time) "
    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,1,2,2,0,NOW())",
    ('P0-1回滚验证', '自动化验证用，验证后删除', '测试地点',
     sign_start, sign_end, act_start, act_end, org_id))
act_id = cur.lastrowid
cur.execute("INSERT INTO ticket(activity_id,ticket_name,total_stock,remain_stock,version) VALUES(%s,%s,1,1,0)", (act_id, '票种A'))
t_a = cur.lastrowid
cur.execute("INSERT INTO ticket(activity_id,ticket_name,total_stock,remain_stock,version) VALUES(%s,%s,1,1,0)", (act_id, '票种B'))
t_b = cur.lastrowid
conn.commit()
log('创建测试活动 id=%s，票种A=%s 票种B=%s（各 1 张，活动总库存 2）' % (act_id, t_a, t_b))


def grab(tok, ticket_id, holder):
    holder.append(post('/activity/grab', {'activityId': act_id, 'ticketId': ticket_id}, token=tok))


# 先让 student01 抢票种A、student02 抢票种B，各自先完成一次「一人一票」之外的情况
# 为了制造并发，用两个线程同时发起
res = {}
barrier = threading.Barrier(2)


def worker(name, tok, tid):
    barrier.wait()
    res[name] = post('/activity/grab', {'activityId': act_id, 'ticketId': tid}, token=tok)


th1 = threading.Thread(target=worker, args=('A', s01_tok, t_a))
th2 = threading.Thread(target=worker, args=('B', s02_tok, t_b))
th1.start(); th2.start(); th1.join(); th2.join()

for k in ('A', 'B'):
    log('  线程%s -> %s %s' % (k, res[k].get('code'), res[k].get('msg')))

cur.execute("SELECT id,ticket_name,remain_stock,version FROM ticket WHERE activity_id=%s ORDER BY id", (act_id,))
types = cur.fetchall()
cur.execute("SELECT total_stock,remain_stock,version FROM activity WHERE id=%s", (act_id,))
act_row = cur.fetchone()
cur.execute("SELECT COUNT(*) FROM ticket_order WHERE activity_id=%s", (act_id,))
orders = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM eticket WHERE activity_id=%s", (act_id,))
tickets = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM grab_log WHERE activity_id=%s", (act_id,))
glogs = cur.fetchall()

type_remain_sum = sum(t[2] for t in types)
log('  票种剩余：', [(t[1], t[2], t[3]) for t in types], '合计=%s' % type_remain_sum)
log('  活动剩余：total=%s remain=%s version=%s' % (act_row[0], act_row[1], act_row[2]))
log('  订单数=%s 电子票数=%s' % (orders, tickets))
ok = (type_remain_sum == act_row[1]) and (orders == tickets) and (act_row[1] == act_row[0] - orders)
log('  >>> 守恒判定（票种剩余合计 == 活动剩余，且 订单数==电子票数，且 成功数==扣减数）：%s' % ('通过' if ok else '不通过'))

# 清理
cur.execute("DELETE FROM grab_log WHERE activity_id=%s", (act_id,))
cur.execute("DELETE FROM eticket WHERE activity_id=%s", (act_id,))
cur.execute("DELETE FROM ticket_order WHERE activity_id=%s", (act_id,))
cur.execute("DELETE FROM ticket WHERE activity_id=%s", (act_id,))
cur.execute("DELETE FROM activity WHERE id=%s", (act_id,))
conn.commit()
log('  测试数据已清理')

conn.close()
with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write(buf.getvalue())
print('written', OUT)
