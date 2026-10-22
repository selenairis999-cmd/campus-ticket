# -*- coding: utf-8 -*-
"""第2步：用户级特征工程（10 维）→ output/features.csv"""
import pandas as pd
import numpy as np

df = pd.read_csv('output/grab_log.csv', encoding='utf-8-sig')
df['create_time'] = pd.to_datetime(df['create_time'])

rows = []
for username, g in df.groupby('username'):
    g = g.sort_values('create_time')
    intervals = g['create_time'].diff().dt.total_seconds().dropna() * 1000  # ms
    total = len(g)
    success = (g['result'] == 'SUCCESS').sum()
    conflict = (g['result'] == 'VERSION_CONFLICT').sum()
    interval_mean = float(intervals.mean()) if len(intervals) else 0.0
    interval_std = float(intervals.std()) if len(intervals) else 0.0
    interval_min = float(intervals.min()) if len(intervals) else 0.0
    interval_cv = interval_std / interval_mean if interval_mean > 0 else 0.0
    # 爆发窗口：1 秒滑窗内 >=3 次请求的行数
    burst = int((g.rolling('1s', on='create_time')['id'].count() >= 3).sum())
    night = int((g['create_time'].dt.hour < 6).sum())
    rows.append({
        'username': username,
        'req_count': total,
        'success_rate': round(success / total, 3),
        'conflict_rate': round(conflict / total, 3),
        'interval_mean': round(interval_mean, 1),
        'interval_std': round(interval_std, 1),
        'interval_min': round(interval_min, 1),
        'interval_cv': round(interval_cv, 3),
        'burst_count': burst,
        'night_ratio': round(night / total, 3),
        'distinct_activity': g['activity_id'].nunique(),
    })

features = pd.DataFrame(rows)
features.to_csv('output/features.csv', index=False, encoding='utf-8-sig')
print(f'特征表 {len(features)} 个用户 × {len(features.columns)-1} 维 → output/features.csv')
print(features.to_string(index=False))
