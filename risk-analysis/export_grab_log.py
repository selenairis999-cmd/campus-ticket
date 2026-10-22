# -*- coding: utf-8 -*-
"""第1步：从 MySQL 导出 grab_log → output/grab_log.csv
用法：python export_grab_log.py [activity_id]
  带 activity_id：只导出该活动的日志（管理端"运行离线检测"按活动调用）
  不带参数：导出全部活动日志（兼容原命令行批处理流程）

注意：带活动参数的分析结果会另存为 output/grab_log_act<id>.csv，
不会覆盖不带参数导出的全量 output/grab_log.csv。
论文 6.5 节引用的基准数据集是"风控实验-混合流量"（activity_id=11）的 341 条，
重建方式：python export_grab_log.py 11（该活动即论文口径）。"""
import os
import sys
import pymysql
import pandas as pd

os.makedirs('output', exist_ok=True)

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='123456',
                       database='campus_ticket', charset='utf8mb4')
sql = ("SELECT id, user_id, username, activity_id, ip, user_agent, result, create_time "
       "FROM grab_log")
params = None
scoped = len(sys.argv) > 1
if scoped:
    sql += " WHERE activity_id=%s"
    params = (int(sys.argv[1]),)
sql += " ORDER BY user_id, create_time"
df = pd.read_sql(sql, conn, params=params)
conn.close()

scope = f"活动{sys.argv[1]}" if scoped else "全部活动"
df.to_csv('output/grab_log.csv', index=False, encoding='utf-8-sig')
# 按活动分析时额外留档，避免覆盖全量基准数据集
if scoped:
    df.to_csv(f'output/grab_log_act{sys.argv[1]}.csv', index=False, encoding='utf-8-sig')
print(f'已导出 {scope} {len(df)} 条 → output/grab_log.csv')
print('\nresult 分布:')
print(df['result'].value_counts().to_string())
print('\n用户分布:')
print(df.groupby('username')['id'].count().sort_values(ascending=False).to_string())
