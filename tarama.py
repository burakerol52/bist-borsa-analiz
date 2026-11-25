import sqlite3
import pandas as pd

# Pandas konsol çıktısının tam ve okunaklı görünmesi için ayarlar
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

conn = sqlite3.connect("borsa.db")

query = """
SELECT 
    c.ticker AS Sembol,
    c.name AS Sirket,
    v.price AS Fiyat,
    ROUND(v.graham_value, 2) AS Graham_Degeri,
    ROUND(v.discount_pct, 1) AS Iskonto_Yuzdesi,
    v.pe_ratio AS FK,
    v.pb_ratio AS PDDD
FROM valuations v
JOIN companies c ON v.ticker = c.ticker
WHERE v.date = (SELECT MAX(date) FROM valuations)
ORDER BY v.discount_pct DESC;
"""

df = pd.read_sql_query(query, conn)
conn.close()

print("\n==================== DEĞER YATIRIMI TARAMA TABLOSU ====================")
if not df.empty:
    print(df.to_string(index=False))
else:
    print("Veritabanında henüz gösterilecek kayıt bulunamadı.")
print("=======================================================================\n")