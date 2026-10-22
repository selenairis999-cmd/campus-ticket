# -*- coding: utf-8 -*-
# gen_virtual_data.py —— 虚拟活动 + 学生抢票 + 多样化评论（含无意义/乱码样本）+ 打真实标签
# 用法：python gen_virtual_data.py（需后端 8080 在跑 + MySQL 正常）
# 说明：活动/票种用 SQL 直插（快），抢票/评论走 HTTP API（真实业务链路），最后按内容池打 sentiment_label
import random, time, json
import urllib.request, urllib.parse
from datetime import datetime, timedelta
import pymysql

random.seed(2026)
DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')
API = 'http://localhost:8080/api'
STUDENTS = ['student%02d' % i for i in range(1, 13)]   # student01~12
PWD = '123456'

ACTIVITIES = [
    ('校园歌手大赛', '大学生活动中心', '十佳歌手决赛之夜，选手火力全开'),
    ('社团招新夜', '文化广场', '三十多个社团联合招新，好礼不断'),
    ('篮球友谊赛', '体育馆', '校篮球队 VS 校友队，巅峰对决'),
    ('脱口秀开放麦', '小礼堂', '校园脱口秀专场，全程高能'),
]

POS = [
    '这次活动组织得特别好，工作人员都很热情，体验满分',
    '氛围感太强了，全程沉浸，下次一定还来',
    '嘉宾和表演都很精彩，收获满满',
    '签到入场特别快，流程很顺畅，点赞',
    '现场布置很用心，看得出主办方花了心思',
    '音响灯光都很到位，视听体验拉满',
    '第一次参加就爱上这种活动了，强烈推荐',
    '内容很丰富，一点都不拖沓，全程无尿点',
    '互动环节设计得很好，大家都很投入',
    '现场秩序非常好，安排得明明白白',
    '超预期的体验，比宣传的还要好',
    '气氛超好，大家都很热情，意犹未尽',
]
NEU = [
    '整体还行吧，没有特别惊艳但也不差',
    '内容中规中矩，凑合看看',
    '还行，主要是陪朋友来的',
    '场地有点小，其他方面都还好',
    '流程一般般，等待时间稍微有点长',
    '有几段不错，有几段比较无聊',
    '普普通通的一次活动，没有太多惊喜',
    '感觉一般，不是我的菜，但组织没问题',
]
NEG = [
    '音响效果太差了，根本听不清台上在说什么',
    '现场管理有点乱，进场排队等了好久',
    '内容太水了，感觉浪费时间',
    '座位安排不合理，后排体验很差',
    '整体体验不好，下次不来了',
    '宣传和实际差距太大，有点失望',
]
INVALID = [
    '父亲9人923然后12有任何去和q',
    '孩子吃了感觉很好吃',
    'asdfghjkl',
    '6666666666',
    '哈哈哈哈哈哈哈哈哈',
    '？？？？？？',
    'ghjk4455',
    '。。。。。',
    '！@#￥%……&*',
    '不知道说啥反正就是随便打几个字',
]
# 每活动评论构成：好评12 / 中评8 / 差评6 / 无意义4
PER_ACT = {'pos': 12, 'neu': 8, 'neg': 6, 'invalid': 4}

def api_post(path, params, token=None):
    url = API + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method='POST')
    if token:
        req.add_header('token', token)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    now = datetime.now()

    # ---------- 1. 创建虚拟活动 + 票种（SQL 直插） ----------
    act_ids = []
    for title, loc, desc in ACTIVITIES:
        cur.execute(
            "INSERT INTO activity (title, location, description, organizer_id, status, "
            "start_time, end_time, sign_start_time, sign_end_time, total_stock, remain_stock) "
            "VALUES (%s, %s, %s, 4, 0, %s, %s, %s, %s, 100, 100)",
            (title, loc, desc,
             now + timedelta(days=3), now + timedelta(days=3, hours=2),
             now - timedelta(hours=1), now + timedelta(days=6)))
        aid = cur.lastrowid
        act_ids.append(aid)
        cur.execute("INSERT INTO ticket (activity_id, ticket_name, total_stock, remain_stock) VALUES (%s, '普通票', 100, 100)", (aid,))
    conn.commit()
    print('1) 已创建活动 %d 个：%s（票种：普通票×100）' % (len(act_ids), [a[0] for a in ACTIVITIES]))

    # ---------- 2. 学生抢票（HTTP API，真实链路 + 乐观锁） ----------
    tokens = {u: api_post('/auth/login', {'username': u, 'password': PWD})['data']['token'] for u in STUDENTS}
    ok = fail = 0
    for aid in act_ids:
        for u in STUDENTS:
            for k in range(3):
                try:
                    r = api_post('/activity/grab', {'activityId': aid}, tokens[u])
                    if r.get('code') == 200:
                        ok += 1
                    else:
                        fail += 1
                except Exception as e:
                    fail += 1
                time.sleep(random.uniform(0.6, 1.2))   # 间隔防风控误拦
    print('2) 抢票完成：成功 %d 张，失败 %d 张' % (ok, fail))

    # ---------- 3. 发评论（HTTP API，好/中/差/无意义 12:8:6:4） ----------
    cmt_ok = cmt_fail = 0
    for aid in act_ids:
        pool = random.sample(POS, PER_ACT['pos']) + random.sample(NEU, PER_ACT['neu']) \
             + random.sample(NEG, PER_ACT['neg']) + random.sample(INVALID, PER_ACT['invalid'])
        random.shuffle(pool)
        for i, content in enumerate(pool):
            user = STUDENTS[i % len(STUDENTS)]
            try:
                r = api_post('/comment/add', {'activityId': aid, 'content': content}, tokens[user])
                if r.get('code') == 200:
                    cmt_ok += 1
                else:
                    cmt_fail += 1
                    print('   评论失败[%s]: %s -> %s' % (user, content, r.get('msg')))
            except Exception as e:
                cmt_fail += 1
                print('   评论异常[%s]: %s -> %s' % (user, content, e))
            time.sleep(0.2)
    print('3) 评论完成：成功 %d 条，失败 %d 条' % (cmt_ok, cmt_fail))

    # ---------- 4. 打真实标签（好/中/差/无意义 → sentiment_label & sentiment） ----------
    label_map = {2: POS, 1: NEU, 0: NEG, 9: INVALID}
    total = 0
    for label, texts in label_map.items():
        if not texts:
            continue
        placeholders = ','.join(['%s'] * len(texts))
        sql = ("UPDATE activity_comment SET sentiment_label=%%s, sentiment=%%s "
               "WHERE content IN (%s) AND sentiment_label IS NULL" % (placeholders,))
        cur.execute(sql, tuple([label, label] + texts))
        total += cur.rowcount
    conn.commit()
    print('4) 已打真实标签 %d 条（含用户两条乱码句 → 无意义9）' % total)

    # ---------- 5. 汇总 ----------
    cur.execute("SELECT sentiment_label, COUNT(*) FROM activity_comment WHERE sentiment_label IS NOT NULL GROUP BY sentiment_label ORDER BY sentiment_label")
    print('5) 训练标签分布（sentiment_label）:')
    for r in cur.fetchall():
        name = {0: '差评', 1: '中评', 2: '好评', 9: '无意义'}.get(r[0], r[0])
        print('   %s = %d' % (name, r[1]))
    cur.execute("SELECT activity_id, title, total_stock-remain_stock AS sold FROM activity WHERE id IN (%s)" % ','.join(['%s'] * len(act_ids)), tuple(act_ids))
    print('   新活动售票情况:', cur.fetchall())
    cur.close(); conn.close()
    print('完成')

if __name__ == '__main__':
    main()
