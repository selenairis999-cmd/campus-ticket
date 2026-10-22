# fix_invalid_comments.py —— 存量修正：把已分析的纯标点/超短评论统一标为 9（无意义）
# 用法：python fix_invalid_comments.py
import re
import pymysql

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

def is_valid_comment(text):
    t = re.sub(r'\s+', '', text or '')
    if len(t) < 2:
        return False
    rest = re.sub(r'[\u4e00-\u9fa5a-zA-Z0-9]', '', t)
    return rest != t

conn = pymysql.connect(**DB)
cur = conn.cursor()
cur.execute("SELECT id, content, sentiment FROM activity_comment WHERE sentiment IS NOT NULL")
rows = cur.fetchall()
changed = 0
for pid, content, sentiment in rows:
    if not is_valid_comment(content) and sentiment != 9:
        cur.execute("UPDATE activity_comment SET sentiment=9 WHERE id=%s", (pid,))
        changed += 1
conn.commit()
print('已修正无效评论 %d 条（纯标点/超短 → sentiment=9）' % changed)
cur.execute("SELECT sentiment, COUNT(*) FROM activity_comment WHERE sentiment IS NOT NULL GROUP BY sentiment ORDER BY sentiment")
for r in cur.fetchall():
    name = {0: '差评', 1: '中评', 2: '好评', 9: '无意义'}.get(r[0], r[0])
    print('  %s = %d' % (name, r[1]))
cur.close()
conn.close()
