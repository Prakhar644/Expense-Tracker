import sqlite3

# Connect to your database file
conn = sqlite3.connect("database.db")
cur = conn.cursor()

# Get all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur.fetchall()
print("Tables in the database:", tables)

# Show data from each table
for table in tables:
    table_name = table[0]
    print(f"\nData in table '{table_name}':")
    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()
    for row in rows:
        print(row)

conn.close()
