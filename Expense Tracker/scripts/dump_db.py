import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

for t in ('sales', 'expenses'):
    print('\n----', t, '----')
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [r[1] for r in cur.fetchall()]
        print('columns:', cols)
        cur.execute(f"SELECT * FROM {t} ORDER BY date")
        rows = cur.fetchall()
        if not rows:
            print('(no rows)')
        for r in rows:
            print(r)
    except Exception as e:
        print('error reading table', t, e)

conn.close()
