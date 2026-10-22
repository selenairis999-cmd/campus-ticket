# -*- coding: utf-8 -*-
"""SEC-05 专项：封禁是否即时生效（P0-2 回归）。

要点：封禁后必须**立刻**用【未解封时】的旧 token 校验，中间不能插别的调用，
因为 AuthInterceptor 每次请求都会重查 sys_user.status。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://localhost:8080'


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


def show(label, st, body):
    print('   %-34s HTTP=%-4s code=%-4s msg=%s'
          % (label, st, body.get('code'), (body.get('msg') or '')[:46]))
    return st, body


print('=== 准备 ===')
st, b = call('/auth/login', method='POST', form=True,
             body={'username': 'student01', 'password': '123456'})
stu_token = (b.get('data') or {}).get('token')
stu_uid = (b.get('data') or {}).get('userId')
print('   student01 登录: token=%s uid=%s' % (bool(stu_token), stu_uid))
st, b = call('/auth/login', method='POST', form=True,
             body={'username': 'admin', 'password': '123456'})
admin_token = (b.get('data') or {}).get('token')
print('   admin 登录: token=%s' % bool(admin_token))

print()
print('=== 封禁前：旧 token 应正常工作（基线） ===')
show('封禁前 /activity/list', *call('/activity/list', token=stu_token))

print()
print('=== 执行封禁（1 天） ===')
show('POST /risk/ban', *call('/risk/ban', token=admin_token, method='POST', form=True,
                            body={'userId': stu_uid, 'days': 1, 'reason': 'SEC-05 核验'}))

print()
print('=== 封禁后：立刻用同一旧 token 访问（不做任何其他调用） ===')
for p in ('/activity/list', '/ticket/myList', '/activity/page?current=1&size=5'):
    show('封禁后 %s' % p.split('?')[0], *call(p, token=stu_token))

print()
print('=== 封禁后：重新登录应被拒（R0 黑名单） ===')
show('封禁后重新登录 /auth/login',
     *call('/auth/login', method='POST', form=True,
           body={'username': 'student01', 'password': '123456'}))

print()
print('=== 封禁后：token 续期应被拒 ===')
show('封禁后 /auth/refresh', *call('/auth/refresh', token=stu_token, method='POST'))

print()
print('=== 解封，验证恢复 ===')
show('POST /risk/unban', *call('/risk/unban', token=admin_token, method='POST', form=True,
                               body={'userId': stu_uid}))
show('解封后 /activity/list', *call('/activity/list', token=stu_token))
show('解封后重新登录',
     *call('/auth/login', method='POST', form=True,
           body={'username': 'student01', 'password': '123456'}))
