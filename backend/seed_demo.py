"""Create a small, fictional SQLite database for a repeatable judge demo."""
import sqlite3
from pathlib import Path

path = Path(__file__).with_name("demo.db")
if path.exists():
    raise SystemExit("demo.db already exists; keeping its data intact.")
with sqlite3.connect(path) as conn:
    conn.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), total REAL NOT NULL, status TEXT NOT NULL);
        INSERT INTO customers VALUES (1,'Avery','Raleigh'),(2,'Jordan','Durham'),(3,'Sam',NULL);
        INSERT INTO orders VALUES (1,1,120,'paid'),(2,1,80,'paid'),(3,2,45,'pending'),(4,3,30,'paid');
    """)
print("Paste this connection string into onboarding:")
print("sqlite:///" + path.as_posix())
