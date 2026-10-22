# model_metrics.py —— 情感分析模型指标计算
# 两种模式：
#  默认模式（无参数）：读取 sentiment/experiments/metrics.json —— 即 run_experiment.py 在
#    1828 条数据集（8:2 分层、字符级 1-2 元 TF-IDF）上的实测结果，即定稿实验口径。
#    指标全部来自实验产物，不再手工填写，避免"页面数字与实验脱节"。
#  --live 模式：基于当前数据库全量带标注样本重新训练评估（SVM / LR / NB + 手工命中率，
#    秒级完成，不含 SnowNLP 全量逐条，避免长阻塞），供"刷新"按钮展示实时评估结果。
# 用法：python model_metrics.py            # 定稿口径（读实验产物）
#       python model_metrics.py --live     # 当前样本实时评估
import json
import os
import sys
import pymysql
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

HERE = os.path.dirname(os.path.abspath(__file__))
METRICS_JSON = os.path.join(HERE, 'experiments', 'metrics.json')

# 手工真实评论（25 条泛化测试集）
REAL_TEXTS = [
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
]


def paper_metrics():
    """定稿口径：读取 run_experiment.py 生成的实测指标。"""
    if not os.path.isfile(METRICS_JSON):
        return {'error': '缺少实验产物 metrics.json，请先运行 sentiment/experiments/run_experiment.py'}
    with open(METRICS_JSON, encoding='utf-8') as f:
        data = json.load(f)
    models = data.get('models', {})
    out = {'sampleCount': data.get('sampleCount')}
    for key, field in (('SVM', 'svmAccuracy'), ('LR', 'lrAccuracy'), ('NB', 'nbAccuracy')):
        m = models.get(key)
        if m:
            out[field] = '%.2f%%' % (m['accuracy'] * 100)
    svm = models.get('SVM')
    if svm:
        out['svmRealHitRate'] = '%s（%d/%d）' % (svm['manualHitRate'], svm['manualHit'],
                                                svm['manualTotal'])
    snow = models.get('SnowNLP')
    if snow:
        out['snownlpAccuracy'] = '%.2f%%' % (snow['accuracy'] * 100)
        out['snownlpHitRate'] = '%s（%d/%d）' % (snow['manualHitRate'], snow['manualHit'],
                                                snow['manualTotal'])
    return out


def compute_live():
    """基于当前数据库全量带标注样本训练评估（SVM/LR/NB + 手工命中率）"""
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT content, sentiment_label FROM activity_comment WHERE sentiment_label IS NOT NULL")
    rows = cur.fetchall()
    cur.close(); conn.close()
    texts = [r[0] for r in rows]
    labels = [r[1] for r in rows]
    n = len(rows)
    if n < 50:
        return {'svmAccuracy': '-', 'lrAccuracy': '-', 'nbAccuracy': '-',
                'svmRealHitRate': '-', 'sampleCount': n}

    X_tr, X_te, y_tr, y_te = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels)
    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(1, 2), max_features=10000)
    X_tr_v, X_te_v = vec.fit_transform(X_tr), vec.transform(X_te)

    models = [('SVM', LinearSVC(max_iter=5000, random_state=42)),
              ('LR', LogisticRegression(max_iter=5000, random_state=42)),
              ('NB', MultinomialNB())]
    res = {}
    for name, clf in models:
        clf.fit(X_tr_v, y_tr)
        acc = accuracy_score(y_te, clf.predict(X_te_v))
        preds = clf.predict(vec.transform(texts))
        hit = sum(1 for t, p, l in zip(texts, preds, labels) if t in REAL_TEXTS and p == l)
        total = sum(1 for t in texts if t in REAL_TEXTS)
        key = {'SVM': 'svm', 'LR': 'lr', 'NB': 'nb'}[name]
        res[f'{key}Accuracy'] = '%.2f%%' % (acc * 100)
        if name == 'SVM':
            res['svmRealHitRate'] = '%d%%（%d/%d）' % (hit * 100 // total, hit, total)
    res['sampleCount'] = n
    return res


def main():
    if '--live' in sys.argv:
        out = compute_live()
    else:
        out = paper_metrics()
    print(json.dumps(out, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
