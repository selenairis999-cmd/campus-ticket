# -*- coding: utf-8 -*-
"""P3 验证：删除活动时级联清理票种/订单/电子票/核销记录/评论，grab_log 保留。
流程：造一个带完整下游数据的测试活动 → 调 /activity/delete → 断言各表该活动数据清零。
"""
import io
import json
import sys
import time
import urllib.request

import pymysql

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://localhost:8080'
DB = dict(host='127.0.0.1', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')


def post(path, data=None, token=None, json_body=False):
    url = BASE + path
    headers = {'Content-Type': 'application/json;charset=UTF-8'} if json_body else {}
    if token:
        headers['token'] = token
    body = json.dumps(data, ensure_ascii=False).encode('utf-8') if json_body else (
        urllib.parse.urlencode(data).encode('utf-8') if data else None)
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8'))


import urllib.parse  # noqa: E402

print('=== 1. 登录 organizer01 ===')
login = post('/auth/login', {'username': 'organizer01', 'password': '123456'})
print('  ', login.get('code'), login.get('msg'))
org_token = login['data']['token']
org_id = login['data']['userId']
print('   organizer01 id =', org_id)

print()
print('=== 2. 造测试活动（含票种/订单/电子票/核销记录/评论/grab_log）===')
conn = pymysql.connect(**DB)
cur = conn.cursor()
now = time.strftime('%Y-%m-%dT%H:%M:%S')
title = 'P3级联删除验证-' + time.strftime('%H%M%S')
create = post('/activity/create', {
    'title': title, 'description': '级联删除验证用', 'location': '测试地点',
    'signStartTime': time.strftime('%Y-%m-%dT%H:%M:%S',
                                   time.localtime(time.time() - 3600)),
    'signEndTime': time.strftime('%Y-%m-%dT%H:%M:%S',
                                 time.localtime(time.time() + 86400)),
    'startTime': time.strftime('%Y-%m-%dT%H:%M:%S',
                               time.localtime(time.time() + 90000)),
    'endTime': time.strftime('%Y-%m-%dT%H:%M:%S',
                             time.localtime(time.time() + 180000)),
    'totalStock': 5,
}, token=org_token, json_body=True)
print('   创建:', create.get('code'), create.get('msg'))

cur.execute('SELECT id FROM activity WHERE title=%s', (title,))
aid = cur.fetchone()[0]
print('   activity id =', aid)

# 下游数据：票种由 create 自动生成，这里再补一条；订单/电子票/核销/评论手工插入
cur.execute('INSERT INTO ticket(activity_id, ticket_name, total_stock, remain_stock, version, create_time)'
            ' VALUES(%s, %s, 3, 3, 0, NOW())', (aid, '测试票种'))
cur.execute('INSERT INTO ticket_order(user_id, activity_id, ticket_name, create_time) VALUES(3, %s, %s, NOW())',
            (aid, '普通票'))
oid = cur.lastrowid
cur.execute('INSERT INTO eticket(order_id, user_id, activity_id, ticket_name, ticket_code, qr_content, status, create_time)'
            ' VALUES(%s, 3, %s, %s, %s, %s, 0, NOW())',
            (oid, aid, '普通票', 'T9%08d' % (aid * 7919 % 10 ** 8), 'T9%08d' % (aid * 7919 % 10 ** 8)))
eid = cur.lastrowid
cur.execute('INSERT INTO checkin_record(ticket_id, activity_id, user_id, ticket_code, checker_id, ticket_name, create_time)'
            ' VALUES(%s, %s, 3, %s, 5, %s, NOW())', (eid, aid, 'T9%08d' % (aid * 7919 % 10 ** 8), '普通票'))
cur.execute('INSERT INTO activity_comment(activity_id, user_id, username, content, sentiment, parent_id, create_time)'
            ' VALUES(%s, 3, %s, %s, 2, 0, NOW())', (aid, 'student01', '级联删除验证评论'))
cur.execute('INSERT INTO grab_log(user_id, username, activity_id, ip, user_agent, result, create_time)'
            ' VALUES(3, %s, %s, %s, %s, %s, NOW(3))', ('student01', aid, '127.0.0.1', 'verify', 'SUCCESS'))
conn.commit()

counts = {}
for tbl in ('ticket', 'ticket_order', 'eticket', 'checkin_record', 'activity_comment', 'grab_log'):
    cur.execute('SELECT COUNT(*) FROM %s WHERE activity_id=%%s' % tbl, (aid,))
    counts[tbl] = cur.fetchone()[0]
print('   删除前各表行数:', counts)
assert all(v > 0 for v in counts.values()), '测试数据未造全'

print()
print('=== 3. 删除活动 ===')
res = post('/activity/delete', {'activityId': aid}, token=org_token)
print('  ', res.get('code'), res.get('msg'))
print('  data =', res.get('data'))

print()
print('=== 4. 断言级联清理 ===')
# 关键：必须结束上面 SELECT 开启的事务，否则 REPEATABLE READ 快照仍看到删除前的数据
conn.commit()
after = {}
for tbl in ('ticket', 'ticket_order', 'eticket', 'checkin_record', 'activity_comment', 'grab_log'):
    cur.execute('SELECT COUNT(*) FROM %s WHERE activity_id=%%s' % tbl, (aid,))
    after[tbl] = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM activity WHERE id=%s', (aid,))
after['activity'] = cur.fetchone()[0]
print('   删除后各表行数:', after)

ok = True
for tbl in ('activity', 'ticket', 'ticket_order', 'eticket', 'checkin_record', 'activity_comment'):
    if after[tbl] != 0:
        print('   ✗ %s 仍有 %d 行' % (tbl, after[tbl]))
        ok = False
if after['grab_log'] != 1:
    print('   ✗ grab_log 应保留 1 行（风控审计日志），实际 %d' % after['grab_log'])
    ok = False

print()
print('级联删除验证：', 'PASS ✓' if ok else 'FAIL ✗')

# 清理 grab_log 测试行
cur.execute('DELETE FROM grab_log WHERE activity_id=%s', (aid,))
conn.commit()
cur.close()
conn.close()
print('（已清理 grab_log 测试行）')
sys.exit(0 if ok else 1)
