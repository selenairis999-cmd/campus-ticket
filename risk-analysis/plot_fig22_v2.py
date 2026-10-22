# -*- coding: utf-8 -*-
"""
图22 重绘（仅可视化改进，数据与模型参数与 isolation_forest.py 完全一致）：
1. 散点图横轴改为对数刻度（interval_mean 跨 48~15040ms 两个数量级，线性轴会挤压）
2. 标注防重叠：红点 student01/student12 上下错开；蓝点只标注 2 个代表点，其余正常账号集中为点群
3. 柱状图保持原样（数据按 if_score 排序）
"""
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

# 真机器人（与 isolation_forest.py 一致）
true_bot = {'student01', 'student12'}

# 模型：参数与原始脚本一致，结果可复现
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
model = IsolationForest(n_estimators=200, contamination=0.15, random_state=42)
pred = model.fit_predict(X_scaled)
scores = model.score_samples(X_scaled)
df['if_score'] = scores.round(4)

is_bot = df['username'].isin(true_bot)
colors = ['#d62728' if b else '#4a72b0' for b in is_bot]

fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))

# ============ 左图：间隔均值 vs 请求数（对数横轴） ============
ax = axes[0]
ax.scatter(df['interval_mean'], df['req_count'], c=colors, s=[95 if b else 60 for b in is_bot],
           edgecolors='white', linewidths=0.8, zorder=3)

# 红点标注：student01 / student12（两点坐标几乎重合，上下错开）
for _, r in df[is_bot].iterrows():
    dy = 4 if r['username'] == 'student01' else -14
    ax.annotate(r['username'], (r['interval_mean'], r['req_count']),
                fontsize=10, fontweight='bold', color='#d62728',
                xytext=(0, dy), textcoords='offset points',
                ha='center', va='bottom')

# 蓝点只标注 2 个代表（其余正常账号间隔≈15s、请求10次，集中为点群）
for name in ['student02', 'student08']:
    r = df[df['username'] == name].iloc[0]
    ax.annotate(name, (r['interval_mean'], r['req_count']),
                fontsize=9, color='#4a72b0',
                xytext=(0, 6), textcoords='offset points', ha='center')

ax.set_xscale('log')
ax.set_xlabel('interval_mean (ms，对数刻度)')
ax.set_ylabel('req_count')
ax.set_title('间隔均值 vs 请求数（红=真机器人）', fontsize=12)
ax.grid(alpha=0.3, zorder=0)
ax.set_ylim(-15, 130)
# 图例
import matplotlib.patches as mpatches
ax.legend(handles=[mpatches.Patch(color='#d62728', label='真机器人（student01、student12）'),
                   mpatches.Patch(color='#4a72b0', label='正常账号（10个，特征集中）')],
          loc='lower right', fontsize=9, framealpha=0.9)

# ============ 右图：异常分柱状图（保持原样） ============
ax2 = axes[1]
ax2.bar(df['username'], df['if_score'], color=colors)
ax2.set_ylabel('Isolation Forest score')
ax2.set_title('异常分（越负越异常）', fontsize=12)
ax2.tick_params(axis='x', rotation=30)

plt.tight_layout()
plt.savefig('output/anomaly_plot_v2.png', dpi=200, bbox_inches='tight')
print('已生成 output/anomaly_plot_v2.png')

# 校验：与 anomaly_report.csv 的 if_score 是否一致
rep = pd.read_csv('output/anomaly_report.csv', encoding='utf-8-sig')
merged = df.merge(rep[['username', 'if_score']], on='username', suffixes=('', '_old'))
assert (merged['if_score'] == merged['if_score_old']).all(), 'if_score 与原始结果不一致！'
print('if_score 与原始实验报告完全一致 ✓')
