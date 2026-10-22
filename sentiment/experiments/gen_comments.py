# gen_comments.py —— 生成 1200 条带情感标签的活动评论（一次性）
# 用法：python gen_comments.py
# 好评/中评/差评 ≈ 600/200/400，内容按词库随机拼接，sentiment 为真实标签（供第2步算准确率）
import random
import pymysql

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

POS = ['精彩', '棒极了', '特别开心', '难忘', '下次还来', '太赞了', '氛围超好', '收获满满',
       '五星好评', '意犹未尽', '非常值得', '组织得很好', '强烈推荐', '玩得很尽兴']
NEU = ['还行', '一般般', '凑合', '中规中矩', '没什么特别', '就这样吧', '不好不坏',
       '普通', '可以看看', '马马虎虎']
NEG = ['无聊', '很失望', '浪费时间', '太差了', '后悔来', '体验很差', '再也不来了',
       '没意思', '组织混乱', '糟糕透了', '不值票价']

TEMPLATES = [
    '今天参加了{act}，{w}。',
    '{act}这个活动{base}，{w}。',
    '朋友推荐来{act}，感觉{w}。',
    '{act}结束后，{w}，希望下次更好。',
]

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    # 取现有活动ID（评论必须挂真实活动）
    cur.execute("SELECT id, title FROM activity")
    acts = cur.fetchall()
    if not acts:
        print('活动表为空，请先建活动再跑')
        return
    # 取现有用户
    cur.execute("SELECT id, username FROM sys_user")
    users = cur.fetchall()

    random.seed(42)  # 固定种子，可复现
    # 先清空旧数据（脚本可重复跑）
    cur.execute("TRUNCATE activity_comment")

    rows = []
    for i in range(1200):
        act_id, act_title = random.choice(acts)
        u_id, u_name = random.choice(users)
        r = random.random()
        if r < 0.5:
            w = random.choice(POS); senti = 2
        elif r < 0.65:
            w = random.choice(NEU); senti = 1
        else:
            w = random.choice(NEG); senti = 0
        content = random.choice(TEMPLATES).format(act=act_title, w=w, base=random.choice(['安排','内容','效果']))
        rows.append((act_id, u_id, u_name, content, senti))

    cur.executemany(
        "INSERT INTO activity_comment(activity_id, user_id, username, content, sentiment) VALUES (%s,%s,%s,%s,%s)",
        rows
    )
    conn.commit()

    # 统计分布
    cur.execute("SELECT sentiment, COUNT(*) FROM activity_comment GROUP BY sentiment ORDER BY sentiment")
    dist = cur.fetchall()
    cur.close(); conn.close()
    print('已生成', len(rows), '条评论')
    print('情感分布（0差评/1中评/2好评）：', {s: c for s, c in dist})

if __name__ == '__main__':
    main()
