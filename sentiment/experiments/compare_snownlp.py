# compare_snownlp.py —— SVM vs SnowNLP 基线对比实验（第3步）
# 用法：python compare_snownlp.py
# 说明：SnowNLP 是现成中文情感分析库（0~1 情感分），映射为三分类当基线；
#       与第2步 SVM（98.78%）同数据、同标签对比。跑 1225 条约 1~2 分钟，属正常
import pymysql
from snownlp import SnowNLP
from sklearn.metrics import accuracy_score, classification_report

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

REAL_TEXTS = {
    '散场的时候人特别多，挤了半小时才出来，不过整体还是玩得挺开心',
    '场地布置很漂亮，可惜音响太拉胯了，前几排根本听不清',
    '真滴不错，爱了爱了，下次还来',
    '呵呵，下次别叫我了',
    '还行吧，主要是陪室友来的，自己没什么感觉',
    '嘉宾讲得挺好，就是时间太长了，后半段我直接睡着了',
    '签到很快，组织得井井有条，志愿者也很热情',
    '希望下次时间安排能更合理一点，别让大家饿着肚子等',
    '说实话期待了很久，结果有点落差，但也不是完全没收获',
    '救命，这也太好笑了吧，全程没停过',
    '价格不贵，内容也就那样，一分钱一分货',
    '怎么会有这么无聊的活动，我居然坚持到了最后',
    '虽然下雨了，但主办方发了雨衣，细节拉满',
    '没什么亮点，也没什么槽点，就这样吧',
    '一进场就后悔了，人挤人，空气都不流通',
    '小朋友玩得很开心，大人就…你们懂的',
    '说实话我是被名字骗来的，跟描述完全不符',
    '氛围感绝了，灯光一打瞬间就有那味了',
    '第一次参加这种活动，感觉还不错，下次多带几个朋友',
    '流程有点乱，后半段全靠工作人员吼',
    '笑死，抽奖环节奖品都没发完就结束了',
    '干货很多，笔记记了两页纸，值了',
    '一般般吧，没有宣传的那么好',
    '别的不说，现场秩序是真的好，很专业',
    '凑个热闹来的，看完只想说：就这？',
}

def snownlp_predict(text):
    """SnowNLP 情感分 0~1 → 三分类：<0.4 差评 / 0.4~0.6 中评 / >0.6 好评"""
    score = SnowNLP(text).sentiments
    if score < 0.4:
        return 0
    if score > 0.6:
        return 2
    return 1

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT id, content, sentiment_label FROM activity_comment WHERE sentiment_label IS NOT NULL")
    rows = cur.fetchall()
    texts = [r[1] for r in rows]
    labels = [r[2] for r in rows]
    print('样本数：', len(rows), '（SnowNLP 逐条计算中，约 1~2 分钟…）')

    preds = [snownlp_predict(t) for t in texts]

    acc = accuracy_score(labels, preds)
    print('=' * 50)
    print('SnowNLP 基线准确率：%.2f%%' % (acc * 100))
    print(classification_report(labels, preds, target_names=['差评(0)', '中评(1)', '好评(2)']))
    print('=' * 50)

    real_hit = real_total = 0
    for i, t in enumerate(texts):
        if t in REAL_TEXTS:
            real_total += 1
            if preds[i] == labels[i]:
                real_hit += 1
    if real_total:
        print('手工真实评论 %d 条，SnowNLP 命中 %d 条，命中率 %.0f%%' % (real_total, real_hit, real_hit / real_total * 100))

    print()
    print('对比结论（写简历用）')
    print('  SVM（TF-IDF+LinearSVC）：98.78% | 手工评论命中率 88%')
    print('  SnowNLP 基线：%.2f%% | 手工评论命中率 %.0f%%' % (acc * 100, real_hit / real_total * 100 if real_total else 0))

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
