import sqlite3

# Veritabanına bağlan (borsa.db yoksa otomatik oluşturulur)
conn = sqlite3.connect("borsa.db")
cursor = conn.cursor()

# Tabloları oluştur
cursor.executescript("""
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT UNIQUE,
    name TEXT,
    sector TEXT
);

CREATE TABLE IF NOT EXISTS valuations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    price REAL,
    pe_ratio REAL,
    pb_ratio REAL,
    graham_value REAL,
    discount_pct REAL,
    date TEXT,
    FOREIGN KEY (ticker) REFERENCES companies(ticker)
);
""")

conn.commit()
conn.close()
print("Veritabanı hazır: borsa.db oluşturuldu.")