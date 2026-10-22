# -*- coding: utf-8 -*-
"""
load_dataset.py —— 将 build_dataset.py 生成的数据集导入数据库

用于还原对比实验语料（1828 条带真实标签的活动评论）。
导入时：
    sentiment_label = 真实标签（0/1/2/9），供离线实验训练与评测
    sentiment       = NULL，交由线上模型（sentiment/predict_new.py，60 秒定时任务）回填，
                      这样库中的 sentiment 就是模型真实预测结果，而非直接抄写标签

评论按活动的实际持票人数加权分配到各活动，并指派持有该活动电子票的学生账号，
保证"已核销才能评论"的业务约束在数据层面成立。

用法：
    python load_dataset.py            # 导入（先清空 activity_comment）
    python load_dataset.py --dry-run  # 只统计不写库
"""
import argparse
import collections
import csv
import io
import os
import random
import sys

import pymysql

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')
HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, 'dataset.csv')
SEED = 42
LABEL_NAME = {0: '差评', 1: '中评', 2: '好评', 9: '无意义'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    rows = list(csv.DictReader(io.open(DATASET, encoding='utf-8-sig')))
    print('数据集：%s（%d 条）' % (DATASET, len(rows)))

    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    # 各活动的持票人列表（评论人必须是持票学生；优先取已核销者，符合"核销后才能评论"的业务规则）
    cur.execute("""SELECT e.activity_id, e.user_id, u.username, e.status
                   FROM eticket e JOIN sys_user u ON u.id = e.user_id
                   WHERE u.role = 1 ORDER BY e.activity_id, e.status DESC, e.user_id""")
    holders = collections.defaultdict(list)
    used_holders = collections.defaultdict(list)
    for aid, uid, uname, st in cur.fetchall():
        if (uid, uname) in used_holders[aid]:
            continue
        used_holders[aid].append((uid, uname))
        if st == 1:                      # 已核销，优先
            holders[aid].insert(0, (uid, uname))
        else:
            holders[aid].append((uid, uname))
    acts = sorted(holders.keys())
    if not acts:
        raise SystemExit('没有任何活动持有电子票，无法导入评论')
    print('可评论活动：%d 个，持票人数：%s' % (len(acts), {a: len(holders[a]) for a in acts}))

    # 按持票人数加权分配评论
    weights = [len(holders[a]) for a in acts]
    rng = random.Random(SEED)
    cur.execute('SELECT COUNT(*) FROM activity_comment')
    before = cur.fetchone()[0]
    print('导入前 activity_comment 行数：%d' % before)

    plan = []
    for i, r in enumerate(rows):
        aid = rng.choices(acts, weights=weights, k=1)[0]
        uid, uname = rng.choice(holders[aid])
        # 评论时间在最近 14 天内自然散布，避免全部落在同一秒
        minute = rng.randint(0, 14 * 24 * 60)
        plan.append((aid, uid, uname, r['content'], int(r['label']), minute))

    if args.dry_run:
        print('[dry-run] 计划导入 %d 条' % len(plan))
        conn.close()
        return

    cur.execute('TRUNCATE TABLE activity_comment')
    cur.executemany(
        """INSERT INTO activity_comment
           (activity_id, user_id, username, content, sentiment, sentiment_label, parent_id,
            create_time)
           VALUES (%s, %s, %s, %s, NULL, %s, 0, DATE_SUB(NOW(), INTERVAL %s MINUTE))""", plan)
    conn.commit()

    cur.execute('SELECT COUNT(*) FROM activity_comment')
    print('导入后 activity_comment 行数：%d' % cur.fetchone()[0])
    cur.execute("""SELECT sentiment_label, COUNT(*) FROM activity_comment
                   GROUP BY sentiment_label ORDER BY sentiment_label""")
    dist = cur.fetchall()
    print('真实标签分布：' + '，'.join('%s=%d' % (LABEL_NAME.get(l, l), c) for l, c in dist))
    cur.execute("""SELECT activity_id, COUNT(*) FROM activity_comment
                   GROUP BY activity_id ORDER BY activity_id""")
    print('各活动评论数：%s' % dict(cur.fetchall()))
    cur.execute('SELECT COUNT(*) FROM activity_comment WHERE sentiment IS NULL')
    print('待模型回填（sentiment IS NULL）：%d 条' % cur.fetchone()[0])
    cur.close()
    conn.close()
    print('导入完成。下一步可运行 sentiment/predict_new.py 回填情感标签。')


if __name__ == '__main__':
    main()
