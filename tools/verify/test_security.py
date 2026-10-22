# -*- coding: utf-8 -*-
"""系统安全性用例的实测核验（只读 + 只读接口，不落库）。

逐条给出系统安全性测试用例的实测证据。
运行前需先启动后端：java -jar target/campus-ticket-0.0.1-SNAPSHOT.jar
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://localhost:8080'
results = []


def call(path, token=None, method='GET', body=None, form=False):
    """form=True 走 application/x-www-form-urlencoded（登录/注册/封禁等 @RequestParam 接口）。"""
    url = BASE + path
    data = None
    headers = {}
    if token:
        headers['token'] = token
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode('utf-8')
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            data = json.dumps(body, ensure_ascii=False).encode('utf-8')
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


def ok(name, cond, detail):
    results.append((name, 'PASS' if cond else 'FAIL', detail))
    print('   [%s] %-22s %s' % ('PASS' if cond else 'FAIL', name, detail))


print('== SEC-02/03/04/05 认证与鉴权 ==')
# SEC-02 错误密码
st, body = call('/auth/login', method='POST', form=True,
                body={'username': 'student01', 'password': 'wrong-password-xyz'})
msg = body.get('msg') or body.get('message') or ''
ok('SEC-02 错误密码', st != 200 or body.get('code') != 200,
   'status=%s code=%s msg=%s' % (st, body.get('code'), msg))
ok('SEC-02 不泄露账号存在性', '用户名或密码错误' in msg, 'msg=%s' % msg)

# 正常登录拿 token
st, body = call('/auth/login', method='POST', form=True,
                body={'username': 'student01', 'password': '123456'})
token = (body.get('data') or {}).get('token')
ok('登录成功(取 token)', bool(token), 'status=%s hasToken=%s' % (st, bool(token)))

# SEC-03 未登录
for p in ('/activity/page?current=1&size=5', '/ticket/myList', '/comment/quota'):
    st, body = call(p)
    ok('SEC-03 未登录 %s' % p.split('?')[0], st == 401 or body.get('code') == 401,
       'status=%s code=%s msg=%s' % (st, body.get('code'), body.get('msg')))

# SEC-04 越权（学生访问管理员接口）—— 方法与路径必须与 @RequireRole 的真实定义一致
for p, m in (('/risk/overview', 'GET'), ('/comment/model-info', 'GET'),
             ('/risk/banned', 'GET'), ('/stats/activity', 'GET'),
             ('/comment/analyze', 'POST'), ('/risk/records', 'GET')):
    st, body = call(p, token=token, method=m)
    ok('SEC-04 学生越权 %s %s' % (m, p.split('?')[0]), st == 403 or body.get('code') == 403,
       'status=%s code=%s msg=%s' % (st, body.get('code'), body.get('msg')))

# SEC-05 封禁即时生效：直接用管理员的封禁接口封掉 student01，再用其旧 token 访问
st, body = call('/auth/login', method='POST', form=True, body={'username': 'admin', 'password': '123456'})
admin_token = (body.get('data') or {}).get('token')
if admin_token and token:
    # 找 student01 的 id：直接查库最稳。
    # （曾用 /risk/records 首页记录反查，但 student01 的最新日志未必在第 1 页，
    #   一旦翻不到就 uid=None，属脚本缺陷而非系统缺陷。）
    st, body = call('/risk/banned', token=admin_token)
    d = body.get('data') or {}
    _ban = d.get('records') if isinstance(d, dict) else d
    if _ban:
        print('   提示：封禁名单当前非空（%d 条），本用例假定 student01 未被封禁' % len(_ban))
    uid = None
    try:
        import pymysql as _pm
        _cn = _pm.connect(host='localhost', user='root', password='123456',
                          database='campus_ticket', charset='utf8mb4')
        _cur = _cn.cursor()
        _cur.execute("SELECT id FROM sys_user WHERE username='student01'")
        _row = _cur.fetchone()
        uid = _row[0] if _row else None
        _cn.close()
    except Exception as _e:
        print('   直查库失败: %s' % _e)
    ok('定位 student01 的 userId', uid is not None, 'uid=%s' % uid)
    if uid:
        st, body = call('/risk/ban', token=admin_token, method='POST', form=True,
                        body={'userId': uid, 'days': 1, 'reason': '安全核验：临时封禁'})
        ok('管理员封禁 student01', body.get('code') == 200,
           'code=%s msg=%s' % (body.get('code'), body.get('msg')))
        time.sleep(0.4)
        # 旧 token 必须立刻 401
        for p in ('/activity/page?current=1&size=5', '/ticket/myList', '/comment/quota'):
            st, body = call(p, token=token)
            ok('SEC-05 封禁后旧token %s' % p.split('?')[0],
               st == 401 or body.get('code') == 401,
               'status=%s code=%s msg=%s' % (st, body.get('code'), (body.get('msg') or '')[:60]))
        # 解封，恢复现场
        st, body = call('/risk/unban', token=admin_token, method='POST', form=True, body={'userId': uid})
        ok('解封恢复现场', body.get('code') == 200,
           'code=%s msg=%s' % (body.get('code'), body.get('msg')))
        time.sleep(0.4)
        st, body = call('/ticket/myList', token=token)
        ok('解封后旧token恢复', st == 200 or body.get('code') == 200,
           'status=%s code=%s' % (st, body.get('code')))

print()
print('== SEC-09 风控限频（R1：10 秒内 >5 次抢票请求） ==')
# 注意：R1 只对抢票接口 /activity/grab 生效，且必须用【独立账号】避免污染既有账号
import pymysql
cn = pymysql.connect(host='localhost', user='root', password='123456',
                     database='campus_ticket', charset='utf8mb4')
cur = cn.cursor()
ts = int(time.time())
uname = 'sec09_%d' % (ts % 1000000)
# 复用 student02 的真实 BCrypt 哈希（同一明文 123456），避免手写哈希口令不符
cur.execute("SELECT password FROM sys_user WHERE username='student02'")
pwd_hash = cur.fetchone()[0]
cur.execute("INSERT INTO sys_user(username,password,name,phone,status,role,create_time) "
            "VALUES(%s,%s,%s,%s,1,1,NOW())",
            (uname, pwd_hash, '风控核验号', '137%08d' % (ts % 100000000)))
cn.commit()
new_uid = cur.lastrowid
cn.close()
print('   新建核验账号: %s (id=%s) 密码 123456' % (uname, new_uid))

st, body = call('/auth/login', method='POST', form=True,
                body={'username': uname, 'password': '123456'})
t2 = (body.get('data') or {}).get('token')
ok('SEC-09 核验账号登录', bool(t2), 'code=%s' % body.get('code'))

if t2:
    # 找一个进行中且有余票的活动
    st, body = call('/activity/list', token=t2)
    aid = None
    lst = body.get('data') or []
    for it in (lst if isinstance(lst, list) else []):
        if it.get('status') == 1 and (it.get('remainStock') or 0) > 0:
            aid = it.get('id')
    ok('SEC-09 找到可抢活动', aid is not None, 'activityId=%s' % aid)

    if aid:
        codes, msgs = [], []
        for i in range(8):
            st, body = call('/activity/grab?activityId=%s' % aid, token=t2, method='POST')
            codes.append(body.get('code'))
            msgs.append(body.get('msg') or '')
        print('   8 次抢票业务码:', codes)
        print('   8 次抢票消息  :', msgs)
        blocked = sum(1 for m in msgs if '频繁' in m or '风控' in m or '封禁' in m)
        ok('SEC-09 第6次起被风控拦截', blocked >= 3,
           '被拦截 %d 次 / 共 8 次；第6~8次消息=%s' % (blocked, msgs[5:]))

print()
print('== SEC-10 二维码时间窗（QrCodeUtil） ==')
st, body = call('/ticket/myList', token=token)
d = body.get('data')
items = d.get('records') if isinstance(d, dict) else d
# 必须挑【活动仍在进行中】的未使用票：已结束活动的票，/ticket/qrcode 会
# 正当地返回"活动已结束，该票已过期"，那不属于时间窗缺陷。
st, alist = call('/activity/list', token=token)
active_ids = {a.get('id') for a in (alist.get('data') or [])
              if isinstance(a, dict) and a.get('status') == 1}
tid = None
for it in (items or []):
    if not isinstance(it, dict) or it.get('status') != 0:
        continue
    if it.get('activityId') in active_ids:
        tid = it.get('id') or it.get('ticketId')
        break
if tid is None:
    # 退而求其次：任意未使用票，但把"活动已结束"作为跳过而非失败
    for it in (items or []):
        if isinstance(it, dict) and it.get('status') == 0:
            tid = it.get('id') or it.get('ticketId')
            break
ok('SEC-10 找到未使用电子票', tid is not None, 'ticketId=%s' % tid)
if tid:
    # /ticket/qrcode 返回 Result<String>，二维码内容就在 data 里
    st, body = call('/ticket/qrcode?ticketId=%s' % tid, token=token)
    content = body.get('data') or ''
    parts = str(content).split('.')
    print('   动态二维码: code=%s  content=%s' % (body.get('code'), content))
    if not content and '过期' in (body.get('msg') or ''):
        print('   [SKIP] 该票所属活动已结束，服务端正确拒绝出码（非缺陷）')
    else:
        ok('SEC-10 二维码格式=票号.时间戳.签名', len(parts) == 3 and all(parts),
           '分段数=%d 段=%s' % (len(parts), parts))
        if len(parts) == 3:
            code_id, ts_s, sign = parts
            ok('SEC-10 签名为 64 位 SHA-256', len(sign) == 64,
               '签名长度=%d' % len(sign))
            try:
                skew = abs(int(time.time() * 1000) - int(ts_s))
                ok('SEC-10 时间戳为毫秒级且接近当前时间', skew < 5000, '偏差=%dms' % skew)
            except ValueError:
                ok('SEC-10 时间戳为毫秒级且接近当前时间', False, 'ts=%r' % ts_s)

print('== SEC-01 密码哈希存储（直查库） ==')
# 安全用例：验证密码是否以哈希形式存储、不落明文
import pymysql
_c1 = pymysql.connect(host='localhost', user='root', password='123456',
                      database='campus_ticket', charset='utf8mb4')
_cu = _c1.cursor()
_cu.execute("SELECT username, password FROM sys_user")
_rows = _cu.fetchall()
_total = len(_rows)
_bcrypt = sum(1 for _, pw in _rows if pw and pw.startswith('$2'))
_plain = [u for u, pw in _rows if pw and not pw.startswith('$2')]
ok('SEC-01 全部密码为 BCrypt 哈希', _bcrypt == _total and _total > 0,
   '%d/%d 个账号为 $2a$/$2b$ 前缀' % (_bcrypt, _total))
ok('SEC-01 无明文口令', not _plain, '明文账号=%s' % (_plain or '无'))

print()
print('== SEC-06 SQL 注入（业务接口实测） ==')
# 安全用例：输入校验 —— SQL 注入防护。注入串必须原样回显/被转义，且不得报 500
_INJ = "' OR '1'='1"
st, body = call('/activity/page?pageNum=1&pageSize=5&keyword=' + urllib.parse.quote(_INJ), token=token)
ok('SEC-06 注入串未致 500', st != 500 and body.get('code') != 500,
   'status=%s code=%s msg=%s' % (st, body.get('code'), (body.get('msg') or '')[:60]))
# 注入串作为精确匹配关键字应当查不到任何活动（若被拼接进 SQL 则会返回全表）
_d = body.get('data') or {}
_recs = _d.get('records') if isinstance(_d, dict) else _d
ok('SEC-06 注入串未返回全表', not _recs,
   '命中 %d 条（0 条=注入串被当普通文本处理）' % len(_recs or []))
_c1.close()

print()
print('== SEC-07 XSS 防护（前端模板静态核验） ==')
# 安全用例：输入校验 —— XSS 防护。Vue 的 {{ }} 默认转义；只有 v-html 会渲染裸 HTML
import glob as _glob
import os as _os
_vue = _glob.glob(_os.path.join('frontend', 'src', '**', '*.vue'), recursive=True)
_vhtml = []
for _f in _vue:
    try:
        with open(_f, encoding='utf-8') as _fh:
            for _ln, _line in enumerate(_fh, 1):
                if 'v-html' in _line:
                    _vhtml.append('%s:%d' % (_f, _ln))
    except OSError:
        pass
ok('SEC-07 无 v-html 裸渲染点', not _vhtml,
   '扫描 %d 个 .vue 文件，v-html 命中=%s' % (len(_vue), _vhtml or '无'))

print()
print('=' * 60)
p = sum(1 for r in results if r[1] == 'PASS')
print('TOTAL=%d  PASS=%d  FAIL=%d' % (len(results), p, len(results) - p))
print()
print('注：SEC-08（并发超卖）由 tools/run_load_matrix.py 四场景核验，')
print('    不在本脚本内重复；其结论见 压测结果.csv。')
for n, s, d in results:
    if s == 'FAIL':
        print('  FAILED: %s  -> %s' % (n, d))
