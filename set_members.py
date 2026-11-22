"""Sets the household members shown on the dashboard. Usage: python set_members.py"""
import sqlite3
from app import DATABASE

MEMBERS = ["Qmasha Almansoori", "Shama Alketbi", "Anoud Alaleeli"]
c = sqlite3.connect(DATABASE)
c.execute("DELETE FROM members")
c.executemany("INSERT INTO members (name, initial) VALUES (?, ?)", [(m, m[0]) for m in MEMBERS])
c.commit(); c.close()
print("Members updated:", ", ".join(MEMBERS))
