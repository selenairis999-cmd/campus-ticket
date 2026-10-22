# reset_pwd.py —— 重置任意账号密码（自动 BCrypt 加密）
# 用法：python reset_pwd.py 用户名 新密码
# 示例：python reset_pwd.py student01 123456
import sys
import pymysql
import bcrypt

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

if len(sys.argv) != 3:
    print('用法：python reset_pwd.py 用户名 新密码')
    sys.exit(1)

username, new_pwd = sys.argv[1], sys.argv[2]

conn = pymysql.connect(**DB)
cur = conn.cursor()
cur.execute("SELECT id, username FROM sys_user WHERE username=%s", (username,))
row = cur.fetchone()
if not row:
    print(f"账号 {username} 不存在")
    sys.exit(1)

new_hash = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt(prefix=b'2a')).decode()
cur.execute("UPDATE sys_user SET password=%s WHERE id=%s", (new_hash, row[0]))
conn.commit()
cur.close()
conn.close()
print(f"已重置 {username} 的密码为：{new_pwd}")
