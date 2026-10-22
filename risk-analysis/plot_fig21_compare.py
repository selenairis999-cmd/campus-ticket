# -*- coding: utf-8 -*-
"""
图21「抢票风控模型实验结果对比」绘图脚本。

背景：论文 6.5 节的正文用一整段对比了「孤立森林」与「传统 3σ 阈值方法」，
但原图只画了孤立森林的散点图与异常分柱状图，图题里的“对比”在图上没有落点。
本脚本在保留原有两幅子图的基础上，增加第三幅“两种方法检出结果对比”子图，
使图题与图内容一致。

数据与模型参数与 isolation_forest.py / plot_fig22_v2.py 完全一致：
- 特征：output/features.csv 的 10 维用户级特征
- 模型：StandardScaler + IsolationForest(n_estimators=200, contamination=0.15, random_state=42)
- 3σ 基线：与 isolation_forest.py 相同，仅对 interval_mean / req_count / conflict_rate
  三个单维特征做 |z| > 3 判定，任一维越界即标记为异常
- ground truth：student01、student12 为机器人账号（与原始实验一致）

输出：output/anomaly_plot_compare.png（可用第一个命令行参数覆盖输出路径）

用法：
    python plot_fig21_compare.py                    # 写入 output/anomaly_plot_compare.png
    python plot_fig21_compare.py D:/tmp/fig21.png   # 写入指定路径
"""
import sys
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

FEAT_COLS = ['req_count', 'success_rate', 'conflict_rate', 'interval_mean',
             'interval_std', 'interval_min', 'interval_cv', 'burst_count',
             'night_ratio', 'distinct_activity']
# 3σ 基线使用的单维特征（与 isolation_forest.py 保持一致）
SIGMA_COLS = ['interval_mean', 'req_count', 'conflict_rate']
TRUE_BOT = {'student01', 'student12'}          # ground truth（与原始实验一致）
RED, BLUE = '#d62728', '#4a72b0'


def main():
    df = pd.read_csv('output/features.csv', encoding='utf-8-sig')
    X = df[FEAT_COLS].fillna(0)

    # ---------- 孤立森林 ----------
    X_scaled = StandardScaler().fit_transform(X)
    model = IsolationForest(n_estimators=200, contamination=0.15, random_state=42)
    df['if_anomaly'] = model.fit_predict(X_scaled) == -1
    df['if_score'] = model.score_samples(X_scaled).round(4)

    # ---------- 传统 3σ 基线（单维阈值） ----------
    sig = np.zeros(len(df), dtype=bool)
    for col in SIGMA_COLS:
        s = df[col].astype(float)
        mu, sd = s.mean(), s.std(ddof=0)
        if sd > 0:
            sig |= (s > mu + 3 * sd) | (s < mu - 3 * sd)
    df['sig_anomaly'] = sig

    is_bot = df['username'].isin(TRUE_BOT)

    def prf(flag_col):
        """返回 (标记数, 命中机器人, 误杀正常, 漏检, 精确率, 召回率)"""
        flagged = df[flag_col]
        tp = int((flagged & is_bot).sum())
        fp = int((flagged & ~is_bot).sum())
        fn = int((~flagged & is_bot).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        return int(flagged.sum()), tp, fp, fn, prec, rec

    if_stats = prf('if_anomaly')
    sig_stats = prf('sig_anomaly')

    # ---------- 绘图 ----------
    # 宽高比取 2.44，与论文中该图的图片框（6.29in x 2.58in）一致，避免插图被拉伸变形
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 6.35))
    colors = [RED if b else BLUE for b in is_bot]

    # 子图1：间隔均值 vs 请求数（对数横轴）
    ax = axes[0]
    ax.scatter(df['interval_mean'], df['req_count'], c=colors,
               s=[95 if b else 60 for b in is_bot],
               edgecolors='white', linewidths=0.8, zorder=3)
    for _, r in df[is_bot].iterrows():
        dy = 4 if r['username'] == 'student01' else -14
        ax.annotate(r['username'], (r['interval_mean'], r['req_count']),
                    fontsize=10, fontweight='bold', color=RED,
                    xytext=(0, dy), textcoords='offset points',
                    ha='center', va='bottom')
    for name in ['student02', 'student08']:
        r = df[df['username'] == name].iloc[0]
        ax.annotate(name, (r['interval_mean'], r['req_count']),
                    fontsize=9, color=BLUE,
                    xytext=(0, 6), textcoords='offset points', ha='center')
    ax.set_xscale('log')
    ax.set_xlabel('interval_mean (ms，对数刻度)')
    ax.set_ylabel('req_count')
    ax.set_title('(a) 间隔均值 vs 请求数（红=真机器人）', fontsize=12)
    ax.grid(alpha=0.3, zorder=0)
    # 纵轴上界需容纳 student01 的 141 次请求，否则红点会被裁掉
    ax.set_ylim(-15, df['req_count'].max() * 1.18)
    ax.legend(handles=[mpatches.Patch(color=RED, label='真机器人（student01、student12）'),
                       mpatches.Patch(color=BLUE, label='正常账号（10个，特征集中）')],
              loc='lower right', fontsize=9, framealpha=0.9)

    # 子图2：孤立森林异常分
    ax2 = axes[1]
    ax2.bar(df['username'], df['if_score'], color=colors)
    ax2.set_ylabel('Isolation Forest score')
    ax2.set_title('(b) 孤立森林异常分（越负越异常）', fontsize=12)
    ax2.tick_params(axis='x', rotation=30)
    ax2.axhline(df['if_score'].min(), color='#888', ls=':', lw=1)

    # 子图3：两种方法检出结果对比（图题的“对比”落点）
    ax3 = axes[2]
    methods = ['3σ 单维阈值', '孤立森林']
    stats = [sig_stats, if_stats]
    x = np.arange(len(methods))
    w = 0.19
    series = [
        ('标记数', [s[0] for s in stats], '#8d99ae'),
        ('命中机器人', [s[1] for s in stats], '#2a9d8f'),
        ('误杀正常', [s[2] for s in stats], '#e76f51'),
        ('漏检', [s[3] for s in stats], '#b03a2e'),
    ]
    for i, (label, vals, color) in enumerate(series):
        bars = ax3.bar(x + (i - 1.5) * w, vals, w, label=label, color=color)
        for b, v in zip(bars, vals):
            ax3.text(b.get_x() + b.get_width() / 2, v + 0.04, str(v),
                     ha='center', va='bottom', fontsize=9.5)
    ax3.set_xticks(x)
    ax3.set_xticklabels([f'{m}\nP={s[4]:.2f}  R={s[5]:.2f}'
                         for m, s in zip(methods, stats)], fontsize=10)
    ax3.set_ylabel('账号数')
    ax3.set_title('(c) 两种方法检出结果对比（共12个账号，2个真机器人）', fontsize=12)
    ax3.set_ylim(0, max(max(s[0], s[3]) for s in stats) + 1.2)
    ax3.legend(fontsize=9, loc='upper left', ncol=2)
    ax3.grid(axis='y', alpha=0.3, zorder=0)

    plt.tight_layout()
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'output/anomaly_plot_compare.png'
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    print(f'已生成 {out_path}')

    # ---------- 一致性校验 ----------
    rep = pd.read_csv('output/anomaly_report.csv', encoding='utf-8-sig')
    merged = df.merge(rep[['username', 'if_score', 'if_anomaly', 'sig_anomaly']],
                      on='username', suffixes=('', '_ref'))
    assert np.allclose(merged['if_score'], merged['if_score_ref'], atol=1e-4), \
        'if_score 与原始实验报告不一致！'
    assert (merged['if_anomaly'] == merged['if_anomaly_ref']).all(), \
        'if_anomaly 与原始实验报告不一致！'
    assert (merged['sig_anomaly'] == merged['sig_anomaly_ref']).all(), \
        'sig_anomaly 与原始实验报告不一致！'
    # Windows 控制台默认 GBK，直接 print 勾号会抛 UnicodeEncodeError。
    # 统一把标准输出改成 UTF-8，脚本在 cmd / PowerShell / IDE 下都能正常收尾。
    print('与 anomaly_report.csv 完全一致')
    print(f'3σ 基线：标记 {sig_stats[0]}，命中 {sig_stats[1]}，误杀 {sig_stats[2]}，'
          f'漏检 {sig_stats[3]}，P={sig_stats[4]:.2f}，R={sig_stats[5]:.2f}')
    print(f'孤立森林：标记 {if_stats[0]}，命中 {if_stats[1]}，误杀 {if_stats[2]}，'
          f'漏检 {if_stats[3]}，P={if_stats[4]:.2f}，R={if_stats[5]:.2f}')


if __name__ == '__main__':
    main()
