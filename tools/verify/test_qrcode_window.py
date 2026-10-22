# -*- coding: utf-8 -*-
"""SEC-10 专项：动态二维码格式与时间窗（QrCodeUtil，P0-3 回归）。

库里所有活动的 end_time 都已成为过去，直接挑不到可用票；本脚本临时造一个
「已发布、活动未结束、抢票窗口内」的活动，抢一张票后完成核验，最后清理现场。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import pymysql

BASE = 'http://localhost:8080'
CREATED = {'activity': None, 'user': None}


def call(path, token=None, method='GET', body=None, form=False):
    url = BASE + path
    data, headers = None, {}
    if token:
        headers['token'] = token
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            data = json.dumps(body, ensure_ascii=False).encode()
            headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {'raw': raw[:200]}
    except Exception as e:
        return -1, {'error': str(e)}


def login(u, p='123456'):
    st, b = call('/auth/login', method='POST', form=True, body={'username': u, 'password': p})
    return (b.get('data') or {}).get('token')


print('=== 准备：临时活动 + 临时学生 ===')
org = login('organizer01')
ts = int(time.time())
cur = pymysql.connect(host='localhost', user='root', password='123456',
                      database='campus_ticket', charset='utf8mb4').cursor()

# 临时学生（复用真实 BCrypt 哈希）
cur.execute("SELECT password FROM sys_user WHERE username='student02'")
pwd_hash = cur.fetchone()[0]
uname = 'sec10_%d' % (ts % 1000000)
cur.execute("INSERT INTO sys_user(username,password,name,phone,status,role,create_time) "
            "VALUES(%s,%s,%s,%s,1,1,NOW())",
            (uname, pwd_hash, '二维码核验号', '136%08d' % (ts % 100000000)))
cur.connection.commit()
uid = cur.lastrowid
CREATED['user'] = uid
print('   临时学生 %s (id=%s)' % (uname, uid))

# 临时活动。业务规则有两条约束：
#   ① 抢票结束时间必须晚于当前时间（不能发布已结束的活动）
#   ② 抢票结束时间必须早于活动开始时间
# 因此取：抢票窗口 今天 00:00 ~ 明天 12:00，活动 明天 14:00 ~ 20:00。
# 二维码接口只要求「活动 end_time 未过」，明晚才结束，故当下可用。
st, b = call('/activity/create', token=org, method='POST', form=False, body={
    'title': 'SEC-10 二维码核验活动', 'description': '临时活动，核验结束后删除',
    'location': '线上', 'startTime': '2026-10-15T14:00:00', 'endTime': '2026-10-15T20:00:00',
    'signStartTime': '2026-10-14T00:00:00', 'signEndTime': '2026-10-15T12:00:00',
    'totalStock': 5
})
print('   创建活动: code=%s msg=%s' % (b.get('code'), b.get('msg')))
if b.get('code') != 200:
    raise SystemExit('创建临时活动失败，无法继续')

# 抢票窗口已过（业务规则所限），直接置为进行中，抢票接口内自行放行——
# 因此本脚本的抢票改用「已结束窗口 + 直接入库」不可行，改为造票：
# 直接插一张 eticket，避免与 signEndTime 规则冲突。
cur.execute("SELECT id FROM activity WHERE title='SEC-10 二维码核验活动' ORDER BY id DESC LIMIT 1")
aid = cur.fetchone()[0]
CREATED['activity'] = aid
print('   临时活动 id=%s' % aid)

# 把活动置为进行中，并补一个有余票的票种
cur.execute("UPDATE activity SET status=1, remain_stock=5, total_stock=5 WHERE id=%s", (aid,))
cur.execute("SELECT COUNT(*) FROM ticket WHERE activity_id=%s", (aid,))
if cur.fetchone()[0] == 0:
    cur.execute("INSERT INTO ticket(activity_id,ticket_name,price,total_stock,remain_stock,version,create_time) "
                "VALUES(%s,'核验票',0,5,5,0,NOW())", (aid,))
cur.connection.commit()
print('   活动已置为进行中，票种库存 5')

print()
print('=== 直接造一张未使用电子票（避开已关闭的抢票窗口） ===')
stu = login(uname)
print('   临时学生登录: token=%s' % bool(stu))
if not stu:
    raise SystemExit('临时学生登录失败')
ticket_code = 'T%d%s' % (int(time.time() * 1000), ts % 10000)
# eticket.order_id 无默认值且非空，先补一条订单再挂票
cur.execute("INSERT INTO ticket_order(user_id,activity_id,ticket_name,create_time) "
            "VALUES(%s,%s,'核验票',NOW())", (uid, aid))
oid = cur.lastrowid
cur.execute("INSERT INTO eticket(order_id,ticket_code,qr_content,user_id,activity_id,ticket_name,status,create_time) "
            "VALUES(%s,%s,%s,%s,%s,'核验票',0,NOW())",
            (oid, ticket_code, ticket_code, uid, aid))
cur.connection.commit()
tid = cur.lastrowid
print('   订单 id=%s / 电子票 id=%s code=%s status=0' % (oid, tid, ticket_code))

print()
print('=== SEC-10 动态二维码格式 ===')
st, b = call('/ticket/qrcode?ticketId=%s' % tid, token=stu)
content = b.get('data') or ''
print('   HTTP=%s code=%s msg=%s' % (st, b.get('code'), b.get('msg')))
print('   content = %s' % content)
parts = str(content).split('.')
assert len(parts) == 3, 'FAIL 二维码格式不是 票号.时间戳.签名 -> %r' % content
code_id, ts_s, sign = parts
assert code_id == ticket_code, 'FAIL 票号不一致 %s vs %s' % (code_id, ticket_code)
print('   [PASS] 格式 = 票号.时间戳.签名，票号与 eticket.ticket_code 一致')
assert len(sign) == 64, 'FAIL 签名长度 %d' % len(sign)
print('   [PASS] 签名为 64 位 SHA-256')
skew = abs(int(time.time() * 1000) - int(ts_s))
assert skew < 5000, 'FAIL 时间戳偏差 %dms' % skew
print('   [PASS] 时间戳为毫秒级且接近当前时间（偏差 %dms）' % skew)

print()
print('=== 一次一码：1 秒后再取应不同 ===')
time.sleep(1.1)
st, b2 = call('/ticket/qrcode?ticketId=%s' % tid, token=stu)
c2 = b2.get('data') or ''
print('   第二次 = %s' % c2)
print('   [%s] 两次内容不同（时间戳与签名已刷新）' % ('PASS' if c2 != content else 'FAIL'))

print()
print('=== 核销接口的时间窗（P0-3 双向） ===')
ck = login('checker01')
print('   checker01 token=%s' % bool(ck))
st, b3 = call('/checkin/verify', token=ck, method='POST', form=True, body={'qrContent': content})
print('   [1] 当前有效码       -> code=%s msg=%s' % (b3.get('code'), b3.get('msg')))
print('   [%s] 有效码可核销' % ('PASS' if b3.get('code') == 200 else 'FAIL'))

old_ts = int(time.time() * 1000) - 60000
replay = '%s.%d.%s' % (code_id, old_ts, sign)
st, b4 = call('/checkin/verify', token=ck, method='POST', form=True, body={'qrContent': replay})
print('   [2] 60 秒前旧码(重放) -> code=%s msg=%s' % (b4.get('code'), b4.get('msg')))
print('   [%s] 过期码被拒绝' % ('PASS' if b4.get('code') != 200 else 'FAIL'))

fut_ts = int(time.time() * 1000) + 3600000
future = '%s.%d.%s' % (code_id, fut_ts, sign)
st, b5 = call('/checkin/verify', token=ck, method='POST', form=True, body={'qrContent': future})
print('   [3] 未来 1 小时码     -> code=%s msg=%s' % (b5.get('code'), b5.get('msg')))
print('   [%s] 未来码被拒绝（修复前会被接受）' % ('PASS' if b5.get('code') != 200 else 'FAIL'))

tampered = '%s.%d.%s' % (code_id, int(time.time() * 1000), 'f' * 64)
st, b6 = call('/checkin/verify', token=ck, method='POST', form=True, body={'qrContent': tampered})
print('   [4] 签名被篡改       -> code=%s msg=%s' % (b6.get('code'), b6.get('msg')))
print('   [%s] 篡改签名被拒绝' % ('PASS' if b6.get('code') != 200 else 'FAIL'))

print()
print('=== 清理现场 ===')
cur.execute("DELETE FROM eticket WHERE activity_id=%s", (aid,))
cur.execute("DELETE FROM ticket_order WHERE activity_id=%s", (aid,))
cur.execute("DELETE FROM ticket WHERE activity_id=%s", (aid,))
cur.execute("DELETE FROM activity WHERE id=%s", (aid,))
cur.execute("DELETE FROM sys_user WHERE id=%s", (uid,))
cur.connection.commit()
cur.execute("SELECT COUNT(*) FROM activity WHERE id=%s", (aid,))
print('   已清理临时活动与账号，剩余 activity 行 =', cur.fetchone()[0])
cur.connection.close()
print()
print('SEC-10 核验完成')
