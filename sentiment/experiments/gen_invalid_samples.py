# -*- coding: utf-8 -*-
# gen_invalid_samples.py —— 补充"无意义/乱码"训练样本（标 9），解决乱码被归好评
# 用法：python gen_invalid_samples.py 然后 python sentiment_analysis.py
import random
from datetime import datetime, timedelta
import pymysql

random.seed(9)
DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

# 无意义/乱码样本池（覆盖数字字母乱码、纯字母、纯数字、灌水、仿用户句式）
INVALID = [
    # 仿用户乱码句式（中文+数字+字母混杂）
    '父亲9人923然后12有任何去和q',
    '今日9527然后79有昨天4和x',
    '上个月78号之后2然后3有天q',
    '周三12点然后4有9个人和k',
    '明天3号然后22有昨天8和f',
    '这5个然后9有3和j明天4',
    # 键盘乱码（纯字母）
    'asdfghjkl',
    'zxcvbnm',
    'qwertyuiop',
    'poiuytrewq',
    'asdfghjklqwerty',
    'zxcvbnmasdfgh',
    'qweasdzxc',
    'mnbvcxzlkjhgf',
    # 数字字母混合
    'ghjk4455',
    'dj38fks2ld',
    'md5a8f2j',
    '1093asdk',
    'q1w2e3r4t5y6',
    'k3j2h1g0f9',
    'ajsdo9f2j3k',
    '1234567890qwerty',
    'xiaoxiao1988',
    'test2025abc',
    # 纯数字串
    '8888888888',
    '6666666666',
    '12345678',
    '5201314',
    '23333333',
    '111111',
    '987654321',
    # 纯重复字母（感叹无意义）
    'hhhhhhhh',
    'eeeeeeee',
    'hahaha',
    'hehehe',
    'emmm',
    'aaaabbbb',
    # 灌水/占位
    '不知道说啥反正就是随便打几个字',
    '我来了我来了',
    '到此一游',
    '凑个字数',
    '随便看看',
    '路过路过',
    '打卡',
    '回复一下',
    '占个楼',
    '今天天气不错但是和我来的活动没什么关系',
    '老师布置的作业还没写就来看这个了',
]

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM activity ORDER BY id")
    act_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id, username FROM sys_user WHERE role=1")
    users = cur.fetchall()
    now = datetime.now()

    rows = []
    for content in INVALID:
        for _ in range(2):   # 每条插 2 次，分布在随机活动/用户
            aid = random.choice(act_ids)
            uid, uname = random.choice(users)
            rows.append((aid, uid, uname, content, 9, 9,
                         now - timedelta(days=random.randint(0, 3), hours=random.randint(0, 12))))
    cur.executemany(
        "INSERT INTO activity_comment (activity_id, user_id, username, content, sentiment, sentiment_label, create_time) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)", rows)
    conn.commit()
    cur.execute("SELECT sentiment_label, COUNT(*) FROM activity_comment WHERE sentiment_label IS NOT NULL GROUP BY sentiment_label ORDER BY sentiment_label")
    print('新增无意义样本 %d 条，当前训练标签分布:' % len(rows))
    for r in cur.fetchall():
        name = {0: '差评', 1: '中评', 2: '好评', 9: '无意义'}.get(r[0], r[0])
        print('  %s = %d' % (name, r[1]))
    cur.close(); conn.close()
    print('完成，请运行 sentiment_analysis.py 重新训练')

if __name__ == '__main__':
    main()
