import sqlite3, sys
c = sqlite3.connect("flask_app/database/resume.db")
cur = c.execute(" ".join(sys.argv[1:]))
c.commit()
for row in cur.fetchall():
    print(row)
