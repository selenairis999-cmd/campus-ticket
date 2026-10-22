# checkin_all_tickets.py —— 批量核销所有未核销电子票（模拟现场入场）
# 逻辑：eticket status 0->1 + used_time=now，并为每张票写一条 checkin_record（核销员 checker01 id=5）
import pymysql
from datetime import datetime

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

conn = pymysql.connect(**DB)
cur = conn.cursor()

cur.execute("SELECT id, order_id, user_id, activity_id, ticket_code, ticket_name FROM eticket WHERE status=0")
tickets = cur.fetchall()
print('待核销票数:', len(tickets))
if not tickets:
    print('没有未核销的票')
    cur.close(); conn.close()
    raise SystemExit

now = datetime.now()
# 批量核销
cur.execute("UPDATE eticket SET status=1, used_time=%s WHERE status=0", (now,))
# 批量写核销记录
records = [(t[0], t[3], t[2], t[4], 5, now, t[5]) for t in tickets]
cur.executemany(
    "INSERT INTO checkin_record (ticket_id, activity_id, user_id, ticket_code, checker_id, create_time, ticket_name) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)", records)
conn.commit()

cur.execute("SELECT status, COUNT(*) FROM eticket GROUP BY status")
print('核销后 eticket 分布:', cur.fetchall())
cur.execute("SELECT COUNT(*) FROM checkin_record")
print('核销记录总数:', cur.fetchone()[0])
cur.close(); conn.close()
print('完成')
