# -*- coding: utf-8 -*-
"""
run_experiment.py —— 情感分析对比实验（SVM / LR / NB / SnowNLP）

一次性完成：
  1. 读取 build_dataset.py 生成的数据集（1828 条，四分类）
  2. 按 8:2 分层划分训练集/测试集（random_state=42）
  3. 统一使用 TF-IDF（字符级 1-2 元，max_features=10000）特征
  4. 对比四个模型：
       - LinearSVC（本文方案）
       - 逻辑回归 LogisticRegression（基线）
       - 朴素贝叶斯 MultinomialNB（基线）
       - SnowNLP 预训练模型（参考）
  5. 输出：测试集准确率、分类报告、混淆矩阵
  6. 在 25 条手工真实评论上评测各模型的泛化命中率
  7. 保存结果 JSON（metrics.json）与混淆矩阵图（confusion_matrix.png）

用法：
    python run_experiment.py            # 全部实验
    python run_experiment.py --no-snownlp   # 跳过较慢的 SnowNLP
"""
import argparse
import io
import json
import os
import sys
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, 'dataset.csv')
LABELS = [0, 1, 2, 9]
LABEL_NAME = {0: '差评', 1: '中评', 2: '好评', 9: '无意义'}

# 25 条手工真实评论（与 build_dataset.py 中的 MANUAL 一致，用于泛化测试）
MANUAL = [
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


def load_dataset():
    import csv
    rows = list(csv.DictReader(io.open(DATASET, encoding='utf-8-sig')))
    texts = [r['content'] for r in rows]
    labels = [int(r['label']) for r in rows]
    return texts, labels


def snownlp_predict(text):
    """SnowNLP 只有二分类情感分，按 0.4 / 0.6 阈值映射到三分类（无意义类无法识别）。"""
    from snownlp import SnowNLP
    score = SnowNLP(text).sentiments
    if score < 0.4:
        return 0
    if score > 0.6:
        return 2
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-snownlp', action='store_true', help='跳过 SnowNLP（较慢）')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    texts, labels = load_dataset()
    print('数据集：%d 条' % len(texts))
    dist = {lab: labels.count(lab) for lab in LABELS}
    print('类别分布：' + '，'.join('%s=%d' % (LABEL_NAME[l], dist[l]) for l in LABELS))

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels)
    print('训练集 %d 条 / 测试集 %d 条' % (len(X_train), len(X_test)))

    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(1, 2), max_features=10000)
    Xtr = vec.fit_transform(X_train)
    Xte = vec.transform(X_test)
    print('TF-IDF 特征维度：%d\n' % Xtr.shape[1])

    manual_texts = [t for t, _ in MANUAL]
    manual_true = [l for _, l in MANUAL]
    Xman = vec.transform(manual_texts)

    # 超参数在"训练集"上做 5 折交叉验证选择，测试集只用于最终评估，
    # 避免用测试集调参造成乐观偏差；三个模型用同一套流程，保证对比公平。
    models = [
        ('SVM', 'TF-IDF + LinearSVC（本文）',
         [{'C': c} for c in (0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 2.0, 5.0)],
         lambda **kw: LinearSVC(max_iter=5000, random_state=42, **kw)),
        ('LR', 'TF-IDF + 逻辑回归',
         [{'C': c} for c in (1.0, 3.0, 5.0, 10.0, 20.0, 50.0)],
         lambda **kw: LogisticRegression(max_iter=5000, random_state=42, **kw)),
        ('NB', 'TF-IDF + 朴素贝叶斯',
         [{'alpha': a} for a in (0.01, 0.05, 0.1, 0.3, 0.5, 1.0)],
         lambda **kw: MultinomialNB(**kw)),
    ]

    result = {'sampleCount': len(texts), 'trainCount': len(X_train), 'testCount': len(X_test),
              'distribution': {LABEL_NAME[l]: dist[l] for l in LABELS},
              'tuning': '训练集 5 折分层交叉验证选超参数（测试集不参与调参）', 'models': {}}
    target_names = [LABEL_NAME[l] for l in LABELS]

    for key, name, grid, build in models:
        # 1) 训练集内 5 折 CV 选超参数
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        best_kw, best_cv = None, -1.0
        for kw in grid:
            score = cross_val_score(build(**kw), Xtr, y_train, cv=cv).mean()
            if score > best_cv:
                best_kw, best_cv = kw, score
        print('== %s ==' % name)
        print('交叉验证选参：%s（训练集 5 折 CV 准确率 %.4f）'
              % (', '.join('%s=%s' % kv for kv in best_kw.items()), best_cv))

        # 2) 用选定的超参数在完整训练集上重训，再在测试集上评估
        t0 = time.time()
        model = build(**best_kw)
        model.fit(Xtr, y_train)
        pred = model.predict(Xte)
        acc = accuracy_score(y_test, pred)
        report = classification_report(y_test, pred, labels=LABELS, target_names=target_names,
                                       zero_division=0, digits=4)
        cm = confusion_matrix(y_test, pred, labels=LABELS).tolist()
        mpred = model.predict(Xman)
        hit = int(sum(1 for a, b in zip(mpred, manual_true) if a == b))
        used = time.time() - t0
        print('测试集准确率：%.4f（%d/%d）  手工命中：%d/%d（%d%%）  用时 %.1fs'
              % (acc, int(round(acc * len(y_test))), len(y_test), hit, len(manual_true),
                 hit * 100 // len(manual_true), used))
        print(report)
        print('混淆矩阵（行=真实，列=预测，顺序 %s）：' % '/'.join(target_names))
        for row in cm:
            print('  ', row)
        print()
        result['models'][key] = {
            'name': name, 'accuracy': round(acc, 4),
            'correct': int(round(acc * len(y_test))), 'testCount': len(y_test),
            'manualHit': hit, 'manualTotal': len(manual_true),
            'manualHitRate': '%.2f%%' % (hit * 100.0 / len(manual_true)),
            'confusionMatrix': cm, 'labels': LABELS,
            'report': report, 'seconds': round(used, 2),
            'bestParams': best_kw, 'cvAccuracy': round(best_cv, 4),
        }

    if not args.no_snownlp:
        print('== SnowNLP 预训练模型（参考）==')
        t0 = time.time()
        spred = []
        for t in X_test:
            try:
                spred.append(snownlp_predict(t))
            except Exception:
                spred.append(1)
        sacc = accuracy_score(y_test, spred)
        sreport = classification_report(y_test, spred, labels=LABELS, target_names=target_names,
                                        zero_division=0, digits=4)
        scm = confusion_matrix(y_test, spred, labels=LABELS).tolist()
        shit = 0
        for t, true in zip(manual_texts, manual_true):
            try:
                if snownlp_predict(t) == true:
                    shit += 1
            except Exception:
                pass
        used = time.time() - t0
        print('测试集准确率：%.4f（%d/%d）  手工命中：%d/%d（%d%%）  用时 %.1fs'
              % (sacc, int(round(sacc * len(y_test))), len(y_test), shit, len(manual_true),
                 shit * 100 // len(manual_true), used))
        print(sreport)
        print('混淆矩阵（行=真实，列=预测，顺序 %s）：' % '/'.join(target_names))
        for row in scm:
            print('  ', row)
        print()
        result['models']['SnowNLP'] = {
            'name': 'SnowNLP 预训练模型（参考）', 'accuracy': round(sacc, 4),
            'correct': int(round(sacc * len(y_test))), 'testCount': len(y_test),
            'manualHit': shit, 'manualTotal': len(manual_true),
            'manualHitRate': '%.2f%%' % (shit * 100.0 / len(manual_true)),
            'confusionMatrix': scm, 'labels': LABELS,
            'report': sreport, 'seconds': round(used, 2),
        }

    out = os.path.join(HERE, 'metrics.json')
    with io.open(out, 'w', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=2))
    print('结果已保存 ->', out)

    draw_confusion(result)


def draw_confusion(result):
    """绘制四分类混淆矩阵（以 SVM 方案为准）。"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print('matplotlib 不可用，跳过绘图：%s' % e)
        return

    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
    plt.rcParams['axes.unicode_minus'] = False

    m = result['models']['SVM']
    cm = np.array(m['confusionMatrix'])
    names = [LABEL_NAME[l] for l in m['labels']]

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    im = ax.imshow(cm, cmap='Blues')
    ax.set_xticks(range(len(names)))
    ax.set_yticks(range(len(names)))
    ax.set_xticklabels(names, fontsize=11)
    ax.set_yticklabels(names, fontsize=11)
    ax.set_xlabel('预测类别', fontsize=12)
    ax.set_ylabel('真实类别', fontsize=12)
    ax.set_title('情感分析模型混淆矩阵（LinearSVC，测试集 %d 条）' % m['testCount'], fontsize=12)
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha='center', va='center', fontsize=12,
                    color='white' if cm[i, j] > thresh else '#1f2d3d')
    fig.colorbar(im, ax=ax, shrink=0.82)
    plt.tight_layout()
    out = os.path.join(HERE, 'confusion_matrix.png')
    plt.savefig(out, dpi=200, bbox_inches='tight')
    print('混淆矩阵图已保存 ->', out)


if __name__ == '__main__':
    main()
