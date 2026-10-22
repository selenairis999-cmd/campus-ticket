# sentiment_analysis.py —— TF-IDF + SVM 中文评论情感分类（第2步）
# 用法：python sentiment_analysis.py
# 流程：备份真实标签 → 8:2 训练/测试算准确率 → 预测全部回填 sentiment（前端展示预测值）
# 说明：用字符级 1-2 gram 做 TF-IDF（中文短文本无需分词器，零额外依赖），LinearSVC 分类
import pymysql
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

# 手工真实评论内容集合（add_real_comments.py 混入的 25 条，用于单独统计命中率）
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

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    # 1. 确保 sentiment_label 列存在（MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，用 information_schema 判断）
    cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='activity_comment' AND COLUMN_NAME='sentiment_label'", ('campus_ticket',))
    if cur.fetchone()[0] == 0:
        cur.execute("ALTER TABLE activity_comment ADD COLUMN sentiment_label TINYINT DEFAULT NULL COMMENT '真实标签'")
        conn.commit()
        print('已新增 sentiment_label 列')

    # 2. 首次运行时把当前 sentiment（还是真实标签）备份到 sentiment_label
    cur.execute("SELECT COUNT(*) FROM activity_comment WHERE sentiment_label IS NULL")
    if cur.fetchone()[0] > 0:
        cur.execute("UPDATE activity_comment SET sentiment_label = sentiment WHERE sentiment_label IS NULL")
        conn.commit()
        print('已备份真实标签到 sentiment_label 列')

    # 3. 取样本（用真实标签训练）
    cur.execute("SELECT id, content, sentiment_label FROM activity_comment WHERE sentiment_label IS NOT NULL")
    rows = cur.fetchall()
    ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    labels = [r[2] for r in rows]
    print('样本数：', len(rows))

    # 4. 8:2 分层划分（固定随机种子，可复现）
    X_train, X_test, y_train, y_test, _, _ = train_test_split(
        texts, labels, list(range(len(texts))), test_size=0.2,
        random_state=42, stratify=labels)

    # 5. TF-IDF（字符级 1-2 gram）
    vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(1, 2), max_features=10000)
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # 6. 线性 SVM 训练 + 测试
    clf = LinearSVC(max_iter=5000, random_state=42)
    clf.fit(X_train_vec, y_train)
    y_pred = clf.predict(X_test_vec)

    acc = accuracy_score(y_test, y_pred)
    print('=' * 50)
    print('测试集准确率：%.2f%%' % (acc * 100))
    # 9/18 升级：训练集含"无意义(9)"样本 → 4 分类报表
    cls = sorted(set(labels))
    names = {0: '差评(0)', 1: '中评(1)', 2: '好评(2)', 9: '无意义(9)'}
    target_names = [names[c] for c in cls]
    print(classification_report(y_test, y_pred, target_names=target_names))
    print('=' * 50)

    # 7. 预测全部并回填 sentiment（前端展示预测值），手工评论单独统计
    X_all_vec = vectorizer.transform(texts)
    all_pred = clf.predict(X_all_vec)
    real_hit = real_total = 0
    for i, pid in enumerate(ids):
        cur.execute("UPDATE activity_comment SET sentiment=%s WHERE id=%s", (int(all_pred[i]), pid))
        if texts[i] in REAL_TEXTS:
            real_total += 1
            if int(all_pred[i]) == labels[i]:
                real_hit += 1
    conn.commit()
    print('已回填全部预测值到 sentiment')
    if real_total:
        print('手工真实评论 %d 条，预测命中 %d 条，命中率 %.0f%%' % (real_total, real_hit, real_hit / real_total * 100))

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
