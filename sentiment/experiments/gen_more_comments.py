# gen_more_comments.py —— 生成多样化评论（主题相关、情感多样、真实有票用户、带真实标签）
# 说明：有效评论 sentiment = sentiment_label = 真实标签（已分析状态，定时任务不会重复处理）；
#       少量"无意义"评论（纯标点/超短）sentiment=9、sentiment_label=NULL（不进训练，防类别失衡）
# 用法：python gen_more_comments.py
import random
import pymysql
from datetime import datetime, timedelta

random.seed(42)
DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

conn = pymysql.connect(**DB)
cur = conn.cursor()

cur.execute("SELECT id, username FROM sys_user")
user_map = dict(cur.fetchall())

# 每活动：主题词池（好评亮点 / 差评槽点 / 中评中性点）
THEMES = {
    5:  {'name': '迎新晚会', 'pos': ['节目很精彩', '舞台效果超棒', '主持人很幽默', '现场气氛特别high', '舞蹈表演很有感染力', '音响效果震撼', '整场节奏很紧凑', '灯光舞美都到位'],
             'neg': ['音响一直有杂音', '现场太吵了', '节目有点拖沓', '后半场明显冷场', '座位安排不合理', '等待入场时间太长'],
             'neu': ['节目中规中矩', '现场氛围一般', '有几个节目还不错', '音响效果普通', '组织还算有序']},
    1:  {'name': '校园音乐节', 'pos': ['乐队演出超燃', '现场气氛炸裂', '歌单选得太好了', '主唱嗓音很有感染力', '灯光配合完美', '互动环节很嗨'],
             'neg': ['音响声音太刺耳', '排队进场等太久', '节目单临时改动', '场地太挤了', '后面几组乐队一般'],
             'neu': ['有几首歌不错', '气氛还行', '乐队水平参差不齐', '现场秩序还可以']},
    13: {'name': 'KPL比赛', 'pos': ['比赛看得太过瘾了', '选手操作太秀了', '解说很专业', '现场氛围拉满', '这波团战绝了', '观赛体验很好'],
             'neg': ['导播镜头切得太乱', '现场网络卡顿', '座位看屏幕不清楚', '比赛悬念不大', '中途休息时间太长'],
             'neu': ['比赛还可以', '有几局挺精彩', '解说中规中矩', '整体体验一般']},
}
DEFAULT_THEME = {'name': '活动', 'pos': ['活动内容很丰富', '组织得很用心', '流程安排很顺畅', '工作人员很热情', '整体体验不错', '签到入场很快'],
                 'neg': ['流程有点混乱', '等待时间太长', '现场指引不清楚', '活动内容比较单调', '音响设备有问题'],
                 'neu': ['活动还可以', '流程一般', '内容中规中矩', '现场秩序还行']}

POS_TMPL = [
    '这个{name}{point}，{feeling}，下次一定还来',
    '{point}，非常满意这次{name}！{feeling}',
    '太赞了，{point}，给主办方点赞',
    '{point}，{name}办得超出预期，{feeling}',
    '强烈推荐！{point}，{feeling}',
    '第一次参加{name}，{point}，体验很棒',
    '{point}，整场下来很开心，{feeling}',
    '非常棒的{name}，{point}，明年还要来',
]
NEG_TMPL = [
    '这次{name}体验很差，{point}，不会再来了',
    '{point}，太失望了，希望下次改进',
    '不太满意，{point}，整体拉胯',
    '{point}，{name}体验很一般，不推荐',
    '差评，{point}，浪费了我的时间',
    '{point}，现场管理太乱了，体验不好',
    '很遗憾，{point}，感觉这次{name}没准备好',
]
NEU_TMPL = [
    '{point}，整体还行吧',
    '中规中矩的一次{name}，{point}',
    '{point}，其他方面还可以接受',
    '不算差也不算好，{point}',
    '{point}，凑合吧，没有太大惊喜',
    '整体一般，{point}，但也不算太糟',
    '{point}，希望以后能更好',
]
FEEL_POS = ['心情超好', '非常满意', '玩得很开心', '值回票价', '印象深刻', '不虚此行']
FEEL_NEG = ['心情很差', '非常失望', '浪费时间', '体验糟糕', '再也不来了']
INVALID = ['！！！', '。。。。。', '？？？', '哈哈', '。。', '6666', '？？？？？？', '！', '…', '。。。']


def pick(tmpls, theme, label):
    t = random.choice(tmpls)
    points = theme['pos'] if label == 2 else theme['neg'] if label == 0 else theme['neu']
    point = random.choice(points)
    feeling = random.choice(FEEL_POS) if label == 2 else (random.choice(FEEL_NEG) if label == 0 else '')
    s = t.format(name=theme['name'], point=point, feeling=feeling)
    # 偶发加语气词/标点，增加多样性
    if label != 9 and random.random() < 0.3:
        s += random.choice(['！', '～', '，', '！'])
    return s[:200]

# 生成量：按活动规模分配
PLAN = {5: 60, 1: 20, 13: 20, 7: 40, 8: 40, 9: 40, 11: 100, 12: 40}

rows = []
for act_id, n in PLAN.items():
    theme = THEMES.get(act_id, DEFAULT_THEME)
    cur.execute("SELECT DISTINCT user_id FROM eticket WHERE activity_id=%s", (act_id,))
    uids = [r[0] for r in cur.fetchall()]
    if not uids:
        print('活动 %s 无持票用户，跳过' % act_id)
        continue
    now = datetime.now()
    for i in range(n):
        uid = uids[i % len(uids)]
        username = user_map.get(uid, 'u%s' % uid)
        r = random.random()
        if r < 0.40:
            label = 2
        elif r < 0.70:
            label = 1
        elif r < 0.95:
            label = 0
        else:
            label = 9
        if label == 9:
            content = random.choice(INVALID)
            sentiment = 9
            s_label = None
        else:
            content = pick(POS_TMPL if label == 2 else NEG_TMPL if label == 0 else NEU_TMPL, theme, label)
            sentiment = label
            s_label = label
        create_time = now - timedelta(days=random.randint(0, 5), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        rows.append((act_id, uid, username, content, sentiment, s_label, create_time))

cur.executemany(
    "INSERT INTO activity_comment (activity_id, user_id, username, content, sentiment, sentiment_label, create_time) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)", rows)
conn.commit()

cur.execute("SELECT sentiment, COUNT(*) FROM activity_comment WHERE sentiment IS NOT NULL GROUP BY sentiment ORDER BY sentiment")
print('新增评论 %d 条，库中情感分布:' % len(rows))
for r in cur.fetchall():
    name = {0: '差评', 1: '中评', 2: '好评', 9: '无意义'}.get(r[0], r[0])
    print('  %s = %d' % (name, r[1]))
cur.execute("SELECT sentiment_label, COUNT(*) FROM activity_comment WHERE sentiment_label IS NOT NULL GROUP BY sentiment_label ORDER BY sentiment_label")
print('训练标签分布:')
for r in cur.fetchall():
    name = {0: '差评', 1: '中评', 2: '好评'}.get(r[0], r[0])
    print('  %s = %d' % (name, r[1]))
cur.execute("SELECT activity_id, COUNT(*) FROM activity_comment GROUP BY activity_id ORDER BY activity_id")
print('按活动分布:', cur.fetchall())
cur.close(); conn.close()
print('完成')
