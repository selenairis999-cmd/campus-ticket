# add_real_comments.py —— 混入 25 条手工真实评论（不按词库出牌，测试模型鲁棒性）
# 用法：python add_real_comments.py
# 特点：含矛盾句、口语、反话、无特征词好评等——SVM 靠词库特征会在这里翻车或半翻车，真实感强
import random
import pymysql

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

# (评论内容, 情感)  —— 0差评 1中评 2好评；故意设计成"不按词库出牌"
REAL = [
    ('散场的时候人特别多，挤了半小时才出来，不过整体还是玩得挺开心', 2),
    ('场地布置很漂亮，可惜音响太拉胯了，前几排根本听不清', 1),
    ('真滴不错，爱了爱了，下次还来', 2),
    ('呵呵，下次别叫我了', 0),
    ('还行吧，主要是陪室友来的，自己没什么感觉', 1),
    ('嘉宾讲得挺好，就是时间太长了，后半段我直接睡着了', 1),
    ('签到很快，组织得井井有条，志愿者也很热情', 2),
    ('希望下次时间安排能更合理一点，别让大家饿着肚子等', 0),
    ('说实话期待了很久，结果有点落差，但也不是完全没收获', 1),
    ('救命，这也太好笑了吧，全程没停过', 2),
    ('价格不贵，内容也就那样，一分钱一分货', 1),
    ('怎么会有这么无聊的活动，我居然坚持到了最后', 0),
    ('虽然下雨了，但主办方发了雨衣，细节拉满', 2),
    ('没什么亮点，也没什么槽点，就这样吧', 1),
    ('一进场就后悔了，人挤人，空气都不流通', 0),
    ('小朋友玩得很开心，大人就…你们懂的', 1),
    ('说实话我是被名字骗来的，跟描述完全不符', 0),
    ('氛围感绝了，灯光一打瞬间就有那味了', 2),
    ('第一次参加这种活动，感觉还不错，下次多带几个朋友', 2),
    ('流程有点乱，后半段全靠工作人员吼', 1),
    ('笑死，抽奖环节奖品都没发完就结束了', 0),
    ('干货很多，笔记记了两页纸，值了', 2),
    ('一般般吧，没有宣传的那么好', 1),
    ('别的不说，现场秩序是真的好，很专业', 2),
    ('凑个热闹来的，看完只想说：就这？', 0),
]

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM activity")
    act_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id, username FROM sys_user")
    users = cur.fetchall()
    if not act_ids or not users:
        print('活动或用户为空')
        return

    random.seed(7)
    rows = [(random.choice(act_ids), u[0], u[1], content, senti) for content, senti in REAL for u in [random.choice(users)]]
    cur.executemany(
        "INSERT INTO activity_comment(activity_id, user_id, username, content, sentiment) VALUES (%s,%s,%s,%s,%s)",
        rows
    )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM activity_comment")
    total = cur.fetchone()[0]
    cur.close(); conn.close()
    print('已追加', len(rows), '条真实评论，表内总数', total)

if __name__ == '__main__':
    main()
