# -*- coding: utf-8 -*-
"""第3步：孤立森林检测 + 3-sigma 基线对比 → output/anomaly_report.csv / 对比表 / 图表"""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('output/features.csv', encoding='utf-8-sig')
feat_cols = ['req_count', 'success_rate', 'conflict_rate', 'interval_mean',
             'interval_std', 'interval_min', 'interval_cv', 'burst_count',
             'night_ratio', 'distinct_activity']
X = df[feat_cols].fillna(0)

# 真机器人（造数时定义的 ground truth）
true_bot = {'student01', 'student12'}

# ============ 1. 孤立森林 ============
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
model = IsolationForest(n_estimators=200, contamination=0.15, random_state=42)
pred = model.fit_predict(X_scaled)          # -1 异常 / 1 正常
scores = model.score_samples(X_scaled)      # 越负越异常
df['if_score'] = scores.round(4)
df['if_anomaly'] = (pred == -1)

# ============ 2. 3-sigma 基线（单特征独立判定） ============
def sigma_flags(s):
    mu, sd = s.mean(), s.std()
    return (s > mu + 3 * sd) | (s < mu - 3 * sd)

df['sig_anomaly'] = (sigma_flags(df['interval_mean'])
                     | sigma_flags(df['req_count'])
                     | sigma_flags(df['conflict_rate']))

# ============ 3. 报告（含特征贡献解释） ============
report = df.sort_values('if_score').reset_index(drop=True)
report['is_bot'] = report['username'].isin(true_bot)

# 每个被标记账号：相对全体中位数偏离最大的 3 个特征。
# 采用稳健偏离度 (x - median) / MAD（中位数绝对偏差），而非标准 z 值 (x - mean) / std。
# 原因是本数据中 2 个机器人账号的极值会把均值和标准差严重拉偏，
# 导致真正异常的特征反而拿不到高分；MAD 对离群点不敏感，更适合这种场景。
report['top3_features'] = ''
for idx, row in report.iterrows():
    dev = {}
    for c in feat_cols:
        med = df[c].median()
        mad = (df[c] - med).abs().median()
        dev[c] = (row[c] - med) / (mad if mad > 0 else 1)
    top3 = sorted(dev.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    report.at[idx, 'top3_features'] = '; '.join(f'{c}={row[c]} (偏离={v:.1f})' for c, v in top3)

report_cols = ['username', 'if_score', 'if_anomaly', 'sig_anomaly', 'is_bot',
               'req_count', 'interval_mean', 'interval_min', 'conflict_rate', 'top3_features']
report[report_cols].to_csv('output/anomaly_report.csv', index=False, encoding='utf-8-sig')

print('=== 异常分排序（越负越异常） ===')
print(report[['username', 'if_score', 'if_anomaly', 'sig_anomaly', 'is_bot']].to_string(index=False))

# ============ 4. 对比表（有 ground truth → 精确率/召回率） ============
def evaluate(col):
    tp = int((report[col] & report['is_bot']).sum())
    fp = int((report[col] & ~report['is_bot']).sum())
    fn = int((~report[col] & report['is_bot']).sum())
    p = tp / (tp + fp) if (tp + fp) else 0
    r = tp / (tp + fn) if (tp + fn) else 0
    return tp, fp, fn, p, r

print('\n=== 对比表（ground truth：student01/student12 为机器人） ===')
if report['is_bot'].any():
    print(f"{'方法':<8}{'标记数':<6}{'命中机器人':<8}{'误杀正常':<8}{'漏检':<6}{'精确率':<8}{'召回率'}")
    for name, col in [('3-sigma', 'sig_anomaly'), ('孤立森林', 'if_anomaly')]:
        tp, fp, fn, p, r = evaluate(col)
        print(f"{name:<8}{tp+fp:<6}{tp:<8}{fp:<8}{fn:<6}{p:.2f}{'':<4}{r:.2f}")
else:
    # 真实运行（非造数验证）时没有 ground truth，跳过评估表
    print('当前数据中无 ground truth 账号，跳过精确率/召回率评估（仅输出异常分排序）')

# ============ 5. 图表 ============
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
colors = ['red' if b else 'steelblue' for b in report['is_bot']]

ax = axes[0]
ax.scatter(report['interval_mean'], report['req_count'], c=colors, s=70)
for _, r in report.iterrows():
    ax.annotate(r['username'], (r['interval_mean'], r['req_count']),
                fontsize=9, xytext=(4, 4), textcoords='offset points')
ax.set_xlabel('interval_mean (ms)')
ax.set_ylabel('req_count')
ax.set_title('间隔均值 vs 请求数（红=真机器人）')
ax.grid(alpha=0.3)

axes[1].bar(report['username'], report['if_score'], color=colors)
axes[1].set_ylabel('Isolation Forest score')
axes[1].set_title('异常分（越负越异常）')
axes[1].tick_params(axis='x', rotation=30)

plt.tight_layout()
plt.savefig('output/anomaly_plot.png', dpi=150)
print('\n已生成 output/anomaly_plot.png')
