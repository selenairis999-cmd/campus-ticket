# -*- coding: utf-8 -*-
"""
验证 ① syncActivityStock 修复：组织者调整票种库存与学生抢票并发时，
活动级库存不会被陈旧聚合值覆盖。

场景设计：
  1. 造一个临时活动 + 两档票种（A 10 张、B 10 张），活动 total/remain = 20/20
  2. 并发执行：
       - 线程1：组织者把票种 A 的 total 从 10 改成 12（触发 syncActivityStock）
       - 线程2：多名学生抢票（扣减票种与活动库存）
  3. 结束后校验不变量：
       activity.remain_stock == sum(ticket.remain_stock)
       activity.total_stock  == sum(ticket.total_stock)
     且成功订单数 == (初始总库存 - 当前剩余总库存)

用法：python tools/verify_sync_stock_fix.py
"""
import io
import sys
import json
import time
import threading
import urllib.request
import urllib.parse

import pymysql

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "http://localhost:8080/api"
DB = dict(host="localhost", user="root", password="123456",
          database="campus_ticket", charset="utf8mb4")

ORGANIZER = ("organizer01", "123456")
STUDENT_PREFIX = "syncfix_"


def req(path, method="GET", body=None, token=None, form=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["token"] = token
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"code": e.code, "msg": "HTTP %d" % e.code}


def login(username, password):
    r = req("/auth/login", "POST", form={"username": username, "password": password})
    if r.get("code") != 200:
        raise SystemExit("登录失败 %s: %s" % (username, r))
    return r["data"]["token"], r["data"]["userId"]


def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    org_token, org_id = login(*ORGANIZER)
    print("组织者登录 ok, id=%s" % org_id)

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    # 校验规则：signStartTime < signEndTime < startTime <= endTime
    sign_end = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 3600))
    start = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 7200))
    end = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 172800))

    # 1. 建活动
    # 1. 建活动（标题带时间戳，便于回查且不与其他运行混淆）
    title = "syncfix-%d" % int(time.time() * 1000)
    r = req("/activity/create", "POST", body={
        "title": title,
        "description": "自动化验证用，结束后清理",
        "location": "测试场地",
        "totalStock": 20,
        "signStartTime": now,
        "signEndTime": sign_end,
        "startTime": start,
        "endTime": end,
    }, token=org_token)
    if r.get("code") != 200:
        raise SystemExit("建活动失败: %s" % r)
    # create 返回的是消息字符串，活动 id 需回查
    cur.execute("SELECT id FROM activity WHERE title=%s ORDER BY id DESC LIMIT 1", (title,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("未能回查到刚创建的活动")
    act_id = row[0]
    print("活动 id=%s" % act_id)
    # 2. 两档票种（@RequestParam 表单参数）
    type_ids = []
    for name, stock in (("A票", 10), ("B票", 10)):
        r = req("/activity/ticketType/create", "POST", form={
            "activityId": act_id, "ticketName": name, "totalStock": stock
        }, token=org_token)
        print("  建票种 %s -> %s" % (name, r.get("msg")))
    conn.commit()   # 让上面的插入对回查可见
    cur.execute("SELECT id, ticket_name FROM ticket WHERE activity_id=%s ORDER BY id", (act_id,))
    rows = cur.fetchall()
    type_ids = [x[0] for x in rows]
    print("  票种 ids=%s" % type_ids)
    if len(type_ids) < 2:
        raise SystemExit("票种创建不足 2 个（实际 %d），无法继续" % len(type_ids))

    # 3. 上架活动（status=1 进行中），否则抢票会被「活动未开始」挡住
    r = req("/activity/changeStatus?activityId=%d&status=1" % act_id, "POST", token=org_token)
    print("上架活动 -> %s" % r.get("msg"))
    if r.get("code") != 200:
        raise SystemExit("上架失败: %s" % r)

    conn.commit()   # 结束只读事务快照，否则下面的状态回查看到的是旧数据
    cur.execute("SELECT total_stock, remain_stock FROM activity WHERE id=%s", (act_id,))
    print("建票种后活动库存:", cur.fetchone())

    # 抢票前置检查：活动必须在抢票时间窗内
    cur.execute("SELECT status, sign_start_time, sign_end_time, NOW() FROM activity WHERE id=%s", (act_id,))
    st, ss, se, dbnow = cur.fetchone()
    print("活动状态=%s  抢票窗口 %s ~ %s  当前 %s" % (st, ss, se, dbnow))
    if st != 1 or not (ss <= dbnow <= se):
        raise SystemExit("活动不在可抢票状态，验证无法进行")

    # 3. 注册学生
    students = []
    ts_base = int(time.time() * 1000) % 1000000
    for i in range(12):
        uname = "%s%d_%d" % (STUDENT_PREFIX, i, ts_base)
        r = req("/auth/register", "POST", form={
            "username": uname, "password": "123456", "name": "并发验证%d" % i,
            "phone": "137%08d" % ((ts_base * 10 + i) % 100000000),
        })
        if r.get("code") != 200:
            print("  注册失败 %s: %s" % (uname, r.get("msg")))
            continue
        try:
            tk, uid = login(uname, "123456")
            students.append((uname, tk, uid))
        except SystemExit:
            pass
    print("可用学生账号 %d 个" % len(students))
    if not students:
        raise SystemExit("没有可用学生账号")

    # 4. 并发：一边抢票，一边改票种库存
    barrier = threading.Barrier(len(students) + 1)
    results = []
    errors = []
    grabbed = []
    lock = threading.Lock()

    def grab(stu):
        uname, tk, _ = stu
        try:
            barrier.wait(timeout=30)
            r = req("/activity/grab?activityId=%d" % act_id, "POST", token=tk)
            with lock:
                results.append(r.get("msg"))
                if r.get("code") == 200:
                    grabbed.append(uname)
        except Exception as e:
            with lock:
                errors.append("grab(%s): %r" % (uname, e))

    def resize():
        """在抢票风暴期间反复改票种库存。

        关键：必须密集重复，才能保证出现"聚合读到的 version 在写回前
        被抢票事务推进"的窗口。只调一次很可能恰好落在抢票全部提交之后，
        测不出快照固定导致的 CAS 失效。
        两次调整的 totalStock 之和保持 20（10+10 → 12+8），
        这样活动级 total 仍应是 20，便于事后校验聚合正确。
        """
        try:
            barrier.wait(timeout=30)
            ok = 0
            fail = 0
            for k in range(30):
                r = req("/activity/ticketType/update", "POST", form={
                    "ticketTypeId": type_ids[0], "ticketName": "A票",
                    "totalStock": 12 if k % 2 == 0 else 10
                }, token=org_token)
                if r.get("code") == 200:
                    ok += 1
                else:
                    fail += 1
            with lock:
                results.append("resize成功x%d/失败x%d" % (ok, fail))
        except Exception as e:
            with lock:
                errors.append("resize: %r" % (e,))

    threads = [threading.Thread(target=grab, args=(s,)) for s in students]
    threads.append(threading.Thread(target=resize))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        print("\n[!] 线程异常:")
        for e in errors:
            print("   ", e)

    print("\n结果分布:")
    from collections import Counter
    for msg, cnt in Counter(results).items():
        print("  %-40s x%d" % (msg, cnt))
    print("抢票成功账号数 = %d" % len(grabbed))

    # 5. 校验不变量（先结束本连接的只读事务快照，否则读到的是抢票/回写之前的数据）
    conn.commit()
    cur.execute("SELECT total_stock, remain_stock, version FROM activity WHERE id=%s", (act_id,))
    a_total, a_remain, a_ver = cur.fetchone()
    cur.execute("SELECT SUM(total_stock), SUM(remain_stock) FROM ticket WHERE activity_id=%s", (act_id,))
    t_total, t_remain = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM ticket_order WHERE activity_id=%s", (act_id,))
    orders = cur.fetchone()[0]

    print("\n=== 一致性校验 ===")
    print("activity  total=%s remain=%s version=%s" % (a_total, a_remain, a_ver))
    print("ticket 求和 total=%s remain=%s" % (t_total, t_remain))
    print("订单数=%s" % orders)

    ok = True
    if a_total != t_total:
        print("[FAIL] 活动总库存 != 票种总库存之和  (%s vs %s)" % (a_total, t_total))
        ok = False
    if a_remain != t_remain:
        print("[FAIL] 活动剩余库存 != 票种剩余之和  (%s vs %s)" % (a_remain, t_remain))
        ok = False
    if a_remain < 0:
        print("[FAIL] 活动剩余库存为负（超卖）: %s" % a_remain)
        ok = False
    # 订单数必须等于抢票成功数：多一张说明有扣减被并发回写抹掉后又被重试补上，
    # 少一张说明成功响应了但订单没落库
    if orders != len(grabbed):
        print("[FAIL] 订单数 %s != 抢票成功数 %s" % (orders, len(grabbed)))
        ok = False
    # 每个成功抢票的学生都必须恰好有一张票（一人一票不可被并发击穿）
    cur.execute("""SELECT user_id, COUNT(*) FROM ticket_order
                   WHERE activity_id=%s GROUP BY user_id HAVING COUNT(*) > 1""", (act_id,))
    dup = cur.fetchall()
    if dup:
        print("[FAIL] 同一用户对同一活动存在多张订单: %s" % (dup,))
        ok = False

    # 6. 清理
    print("\n=== 清理 ===")
    cur.execute("SELECT id FROM ticket WHERE activity_id=%s", (act_id,))
    tids = [x[0] for x in cur.fetchall()]
    cur.execute("DELETE FROM checkin_record WHERE activity_id=%s", (act_id,))
    cur.execute("DELETE FROM eticket WHERE activity_id=%s", (act_id,))
    cur.execute("DELETE FROM ticket_order WHERE activity_id=%s", (act_id,))
    cur.execute("DELETE FROM ticket WHERE activity_id=%s", (act_id,))
    cur.execute("DELETE FROM activity WHERE id=%s", (act_id,))
    print("活动及票种/订单/电子票已清理")

    conn.commit()
    cur.close()
    conn.close()

    print("\n" + ("=== PASS: 并发调整票种未破坏两层库存一致性 ===" if ok
                  else "=== FAIL: 发现库存不一致 ==="))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
