import math
import sqlite3
from datetime import datetime
import yfinance as yf

# Takip edilecek örnek hisseler
tickers = ["THYAO.IS", "EREGL.IS", "SISE.IS", "KCHOL.IS", "ASELS.IS", "TUPRS.IS"]

conn = sqlite3.connect("borsa.db")
cursor = conn.cursor()

print("Veriler çekiliyor ve değerleme hesaplanıyor...\n")

for sym in tickers:
    clean_ticker = sym.replace(".IS", "")
    try:
        stock = yf.Ticker(sym)
        info = stock.info

        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        eps = info.get("trailingEps")
        bvps = info.get("bookValue")
        pe = info.get("trailingPE", 0)
        pb = info.get("priceToBook", 0)
        name = info.get("shortName", clean_ticker)
        sector = info.get("sector", "Genel")

        # Şirketi kaydet
        cursor.execute(
            "INSERT OR IGNORE INTO companies (ticker, name, sector) VALUES (?, ?, ?)",
            (clean_ticker, name, sector)
        )

        # Graham Adil Değeri: sqrt(22.5 * EPS * BVPS)
        if eps and bvps and eps > 0 and bvps > 0 and price:
            graham_value = math.sqrt(22.5 * eps * bvps)
            discount_pct = ((graham_value - price) / graham_value) * 100
        else:
            graham_value, discount_pct = 0, 0

        # Veritabanına kaydet
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO valuations (ticker, price, pe_ratio, pb_ratio, graham_value, discount_pct, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (clean_ticker, price, pe, pb, graham_value, discount_pct, today))

        print(f"[{clean_ticker}] Fiyat: {price} TL | Graham Değeri: {graham_value:.2f} TL | İskonto: %{discount_pct:.1f}")

    except Exception as e:
        print(f"[{clean_ticker}] Veri alınırken hata: {e}")

conn.commit()
conn.close()
print("\nİşlem tamamlandı, veriler borsa.db dosyasına işlendi.")