# predict_new.py —— 增量分析：只对"待分析"(sentiment IS NULL) 的评论跑模型回填
# 用法：python predict_new.py
# 说明：用全部带真实标签的数据重训一次（秒级），预测新评论并回填情感
# 9/17 升级：无效评论识别 —— 纯标点/超短（无有效字符）评论不喂模型，直接标 9（无意义），不参与任何统计
import re
import pymysql
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

def is_valid_comment(text):
    """有效评论判定：去掉空白后至少 2 个字符，且包含中英文/数字等有效字符（纯标点/符号视为无效）"""
    t = re.sub(r'\s+', '', text or '')
    if len(t) < 2:
        return False
    rest = re.sub(r'[\u4e00-\u9fa5a-zA-Z0-9]', '', t)
    return rest != t

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    # 1. 训练数据：所有带真实标签的评论
    cur.execute("SELECT content, sentiment_label FROM activity_comment WHERE sentiment_label IS NOT NULL")
    train = cur.fetchall()
    X_train = [r[0] for r in train]
    y_train = [r[1] for r in train]

    # 2. 待分析评论（sentiment 为空）
    cur.execute("SELECT id, content FROM activity_comment WHERE sentiment IS NULL")
    pending = cur.fetchall()
    if not pending:
        print('没有待分析的评论')
        return

    # 3. 有效评论喂模型预测；无效评论（纯标点/超短）直接标 9（无意义）
    valid = [p for p in pending if is_valid_comment(p[1])]
    invalid = [p for p in pending if not is_valid_comment(p[1])]
    preds = {}
    if valid:
        vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(1, 2), max_features=10000)
        clf = LinearSVC(max_iter=5000, random_state=42)
        clf.fit(vectorizer.fit_transform(X_train), y_train)
        preds = dict(zip([p[0] for p in valid],
                         clf.predict(vectorizer.transform([p[1] for p in valid]))))
    for p in invalid:
        preds[p[0]] = 9

    # 4. 回填
    cnt = {0: 0, 1: 0, 2: 0, 9: 0}
    for pid, pred in preds.items():
        cur.execute("UPDATE activity_comment SET sentiment=%s WHERE id=%s", (int(pred), pid))
        cnt[int(pred)] += 1
    conn.commit()

    print('待分析评论 %d 条（有效 %d · 无效 %d），已全部回填' % (len(pending), len(valid), len(invalid)))
    print('分布：差评 %d · 中评 %d · 好评 %d · 无效 %d' % (cnt[0], cnt[1], cnt[2], cnt[9]))
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
