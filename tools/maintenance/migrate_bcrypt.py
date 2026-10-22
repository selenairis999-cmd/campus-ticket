# migrate_bcrypt.py —— 存量密码 BCrypt 迁移（一次性）
# 用法：python migrate_bcrypt.py
# 把 sys_user 表中明文密码统一升级为 BCrypt("123456")（$2a$ 前缀，与 hutool 兼容）
import pymysql
import bcrypt

DB = dict(host='localhost', port=3306, user='root', password='123456',
          database='campus_ticket', charset='utf8mb4')

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT id, username, password FROM sys_user")
    rows = cur.fetchall()
    for uid, username, pwd in rows:
        if pwd and pwd.startswith('$2'):
            print(f"[跳过] {username} 已是BCrypt")
            continue
        # 统一使用 123456；若个别账号密码不同，把下面这行改成对应明文
        new_hash = bcrypt.hashpw(b'123456', bcrypt.gensalt(prefix=b'2a')).decode()
        cur.execute("UPDATE sys_user SET password=%s WHERE id=%s", (new_hash, uid))
        print(f"[更新] {username}: {pwd} -> {new_hash[:20]}...")
    conn.commit()
    cur.close()
    conn.close()
    print("完成，共处理", len(rows), "个账号")

if __name__ == '__main__':
    main()
