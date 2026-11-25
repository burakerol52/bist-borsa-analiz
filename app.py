import os
import sys
import math
import sqlite3
import threading
from datetime import datetime
import yfinance as yf
import customtkinter as ctk
from tkinter import ttk, messagebox

# Dizin ve DB Uyumluluğu
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "borsa.db")

SECTOR_MAP = {
    "ASELS": "Savunma Sanayii", "SDTTR": "Savunma Sanayii", "PAPIL": "Savunma Sanayii",
    "ASTOR": "Enerji & Trafo", "EUPWR": "Enerji & Trafo", "ALFAS": "Güneş & Enerji",
    "CWENE": "Güneş & Enerji", "TUPRS": "Enerji & Rafineri", "ENJSA": "Elektrik Dağıtım",
    "AKBNK": "Bankacılık", "GARAN": "Bankacılık", "ISCTR": "Bankacılık", "YKBNK": "Bankacılık",
    "THYAO": "Havacılık & Ulaşım", "PGSUS": "Havacılık & Ulaşım",
    "KCHOL": "Holding", "SAHOL": "Holding",
    "EREGL": "Sanayi & Demir-Çelik", "SISE": "Sanayi & Cam",
    "FROTO": "Otomotiv & Sanayi", "BIMAS": "Perakende & Tüketim",
}

DEFAULT_TICKERS = [
    "ASTOR.IS", "ASELS.IS", "THYAO.IS", "AKBNK.IS", 
    "GARAN.IS", "EREGL.IS", "SISE.IS", "KCHOL.IS", 
    "TUPRS.IS", "BIMAS.IS", "FROTO.IS"
]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class BorsaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BIST Kurumsal Analiz & Portföy Simülatörü")
        self.geometry("1320x760")
        self.configure(fg_color="#0d1117")

        self.live_prices = {}

        self.init_database()
        self.setup_custom_styles()

        # Üst Sekme Yapısı
        self.tabview = ctk.CTkTabview(
            self, 
            fg_color="#161b22", 
            segmented_button_selected_color="#1f6feb",
            segmented_button_selected_hover_color="#388bfd",
            segmented_button_unselected_color="#21262d"
        )
        self.tabview.pack(fill="both", expand=True, padx=15, pady=10)

        self.tab_radar = self.tabview.add("📊 Radar & Skorlama")
        self.tab_portfolio = self.tabview.add("💼 100.000 TL Portföy Simülasyonu")

        self.build_radar_tab()
        self.build_portfolio_tab()

        self.load_radar_from_db()
        self.load_portfolio_from_db()
        self.start_live_fetch_thread()

    def setup_custom_styles(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Custom.Treeview",
            background="#0d1117",
            foreground="#c9d1d9",
            fieldbackground="#0d1117",
            rowheight=32,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#21262d",
            foreground="#f0f6fc",
            font=("Segoe UI", 10, "bold"),
            relief="flat"
        )
        style.map("Custom.Treeview.Heading", background=[("active", "#30363d")])

    def init_database(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
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
            net_margin REAL,
            roe REAL,
            growth REAL,
            score INTEGER,
            signal TEXT,
            method TEXT,
            date TEXT,
            FOREIGN KEY (ticker) REFERENCES companies(ticker)
        );
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY,
            cash REAL
        );
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE,
            quantity INTEGER,
            avg_cost REAL
        );
        """)
        # Başlangıç bakiyesi 100.000 TL
        cursor.execute("INSERT OR IGNORE INTO account (id, cash) VALUES (1, 100000.0)")
        conn.commit()
        conn.close()

    # --- RADAR SEKMESİ ---
    def build_radar_tab(self):
        # KPI Kartları
        cards_frame = ctk.CTkFrame(self.tab_radar, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(5, 6))

        self.card_total = self.create_kpi_card(cards_frame, "TAKİP EDİLEN HİSSE", "0", "#58a6ff")
        self.card_buy = self.create_kpi_card(cards_frame, "AL SİNYALİ VERENLER", "0", "#3fb950")
        self.card_avg_pe = self.create_kpi_card(cards_frame, "ORTALAMA F/K", "0.0", "#bc8cff")

        # Araç Çubuğu
        toolbar = ctk.CTkFrame(self.tab_radar, fg_color="#161b22", corner_radius=8)
        toolbar.pack(fill="x", pady=6)

        self.refresh_btn = ctk.CTkButton(
            toolbar, text="⚡ Canlı Verileri Güncelle", font=ctk.CTkFont(weight="bold"),
            command=self.start_live_fetch_thread, width=180, height=34,
            fg_color="#238636", hover_color="#2ea043"
        )
        self.refresh_btn.pack(side="left", padx=10, pady=8)

        self.ticker_entry = ctk.CTkEntry(
            toolbar, placeholder_text="Hisse Kodu (Örn: ASELS)", font=ctk.CTkFont(size=13),
            width=170, height=34, fg_color="#0d1117", border_color="#30363d"
        )
        self.ticker_entry.pack(side="left", padx=5, pady=8)

        self.add_btn = ctk.CTkButton(
            toolbar, text="＋ Radar'a Ekle", font=ctk.CTkFont(weight="bold"),
            command=self.add_ticker_action, width=120, height=34,
            fg_color="#1f6feb", hover_color="#388bfd"
        )
        self.add_btn.pack(side="left", padx=5, pady=8)

        self.status_badge = ctk.CTkLabel(
            toolbar, text="● VERİLER ALINIYOR", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f2cc60", fg_color="#21262d", corner_radius=6, padx=10, pady=5
        )
        self.status_badge.pack(side="right", padx=10, pady=8)

        # Tablo
        table_container = ctk.CTkFrame(self.tab_radar, fg_color="#161b22", corner_radius=8)
        table_container.pack(fill="both", expand=True, pady=(4, 8))

        columns = ("ticker", "name", "sector", "price", "score", "signal", "net_margin", "roe", "growth", "pe", "pb", "method")
        self.radar_tree = ttk.Treeview(table_container, columns=columns, show="headings", style="Custom.Treeview")

        self.radar_tree.heading("ticker", text="Sembol")
        self.radar_tree.heading("name", text="Şirket Adı")
        self.radar_tree.heading("sector", text="Sektör")
        self.radar_tree.heading("price", text="Fiyat (TL)")
        self.radar_tree.heading("score", text="Skor")
        self.radar_tree.heading("signal", text="Sinyal")
        self.radar_tree.heading("net_margin", text="Net Kâr M.")
        self.radar_tree.heading("roe", text="Özkaynak K. (ROE)")
        self.radar_tree.heading("growth", text="Ciro Büyüme")
        self.radar_tree.heading("pe", text="F/K")
        self.radar_tree.heading("pb", text="PD/DD")
        self.radar_tree.heading("method", text="Ağırlıklı Analiz Modeli")

        self.radar_tree.column("ticker", width=75, anchor="center")
        self.radar_tree.column("name", width=140, anchor="w")
        self.radar_tree.column("sector", width=135, anchor="center")
        self.radar_tree.column("price", width=85, anchor="center")
        self.radar_tree.column("score", width=75, anchor="center")
        self.radar_tree.column("signal", width=120, anchor="center")
        self.radar_tree.column("net_margin", width=95, anchor="center")
        self.radar_tree.column("roe", width=115, anchor="center")
        self.radar_tree.column("growth", width=95, anchor="center")
        self.radar_tree.column("pe", width=65, anchor="center")
        self.radar_tree.column("pb", width=65, anchor="center")
        self.radar_tree.column("method", width=175, anchor="w")

        self.radar_tree.tag_configure("strong_buy", background="#102a1d", foreground="#3fb950")
        self.radar_tree.tag_configure("buy", background="#15261d", foreground="#56d364")
        self.radar_tree.tag_configure("neutral", background="#242116", foreground="#e3b341")
        self.radar_tree.tag_configure("expensive", background="#2d1519", foreground="#f85149")

        sb = ttk.Scrollbar(table_container, orient="vertical", command=self.radar_tree.yview)
        self.radar_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.radar_tree.pack(fill="both", expand=True, padx=4, pady=4)

    # --- PORTFÖY SEKMESİ ---
    def build_portfolio_tab(self):
        # Portföy KPI Kartları
        pf_cards = ctk.CTkFrame(self.tab_portfolio, fg_color="transparent")
        pf_cards.pack(fill="x", pady=(5, 6))

        self.card_cash = self.create_kpi_card(pf_cards, "KULLANILABİLİR NAKİT", "100.000,00 TL", "#58a6ff")
        self.card_stock_val = self.create_kpi_card(pf_cards, "HİSSE DEĞERİ", "0,00 TL", "#bc8cff")
        self.card_total_wealth = self.create_kpi_card(pf_cards, "TOPLAM VARLIK", "100.000,00 TL", "#f0f6fc")
        self.card_pnl = self.create_kpi_card(pf_cards, "TOPLAM KÂR / ZARAR", "0,00 TL (%0.0)", "#8b949e")

        # Alım / Satım İşlem Paneli
        trade_frame = ctk.CTkFrame(self.tab_portfolio, fg_color="#161b22", corner_radius=8)
        trade_frame.pack(fill="x", pady=6)

        trade_title = ctk.CTkLabel(trade_frame, text="⚡ Hızlı Al / Sat:", font=ctk.CTkFont(weight="bold"), text_color="#c9d1d9")
        trade_title.pack(side="left", padx=12, pady=8)

        self.trade_ticker = ctk.CTkEntry(trade_frame, placeholder_text="Sembol (Örn: ASTOR)", width=140, height=34, fg_color="#0d1117")
        self.trade_ticker.pack(side="left", padx=5, pady=8)

        self.trade_qty = ctk.CTkEntry(trade_frame, placeholder_text="Lot Adedi", width=100, height=34, fg_color="#0d1117")
        self.trade_qty.pack(side="left", padx=5, pady=8)

        buy_btn = ctk.CTkButton(
            trade_frame, text="🟢 HİSSE AL", font=ctk.CTkFont(weight="bold"),
            command=self.buy_stock_action, width=110, height=34,
            fg_color="#238636", hover_color="#2ea043"
        )
        buy_btn.pack(side="left", padx=5, pady=8)

        sell_btn = ctk.CTkButton(
            trade_frame, text="🔴 HİSSE SAT", font=ctk.CTkFont(weight="bold"),
            command=self.sell_stock_action, width=110, height=34,
            fg_color="#da3633", hover_color="#f85149"
        )
        sell_btn.pack(side="left", padx=5, pady=8)

        reset_btn = ctk.CTkButton(
            trade_frame, text="↺ Bakiyeyi Sıfırla (100k)", font=ctk.CTkFont(size=11),
            command=self.reset_account_action, width=140, height=34,
            fg_color="#21262d", hover_color="#30363d"
        )
        reset_btn.pack(side="right", padx=12, pady=8)

        # Portföy Tablosu
        pf_table_container = ctk.CTkFrame(self.tab_portfolio, fg_color="#161b22", corner_radius=8)
        pf_table_container.pack(fill="both", expand=True, pady=(4, 8))

        columns = ("ticker", "qty", "avg_cost", "current_price", "total_cost", "market_value", "pnl_tl", "pnl_pct")
        self.pf_tree = ttk.Treeview(pf_table_container, columns=columns, show="headings", style="Custom.Treeview")

        self.pf_tree.heading("ticker", text="Sembol")
        self.pf_tree.heading("qty", text="Lot Adedi")
        self.pf_tree.heading("avg_cost", text="Maliyet (TL)")
        self.pf_tree.heading("current_price", text="Canlı Fiyat (TL)")
        self.pf_tree.heading("total_cost", text="Toplam Maliyet (TL)")
        self.pf_tree.heading("market_value", text="Güncel Değer (TL)")
        self.pf_tree.heading("pnl_tl", text="Kâr / Zarar (TL)")
        self.pf_tree.heading("pnl_pct", text="Kâr / Zarar (%)")

        self.pf_tree.column("ticker", width=100, anchor="center")
        self.pf_tree.column("qty", width=100, anchor="center")
        self.pf_tree.column("avg_cost", width=120, anchor="center")
        self.pf_tree.column("current_price", width=120, anchor="center")
        self.pf_tree.column("total_cost", width=140, anchor="center")
        self.pf_tree.column("market_value", width=140, anchor="center")
        self.pf_tree.column("pnl_tl", width=140, anchor="center")
        self.pf_tree.column("pnl_pct", width=120, anchor="center")

        self.pf_tree.tag_configure("profit", background="#102a1d", foreground="#3fb950")
        self.pf_tree.tag_configure("loss", background="#2d1519", foreground="#f85149")
        self.pf_tree.tag_configure("even", background="#242116", foreground="#e3b341")

        sb_pf = ttk.Scrollbar(pf_table_container, orient="vertical", command=self.pf_tree.yview)
        self.pf_tree.configure(yscrollcommand=sb_pf.set)
        sb_pf.pack(side="right", fill="y")
        self.pf_tree.pack(fill="both", expand=True, padx=4, pady=4)

    def create_kpi_card(self, parent, title, initial_val, color):
        card = ctk.CTkFrame(parent, fg_color="#161b22", corner_radius=8, height=65)
        card.pack(side="left", padx=(0, 10), fill="both", expand=True)

        lbl = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="#8b949e")
        lbl.pack(anchor="w", padx=12, pady=(6, 0))

        val_lbl = ctk.CTkLabel(card, text=initial_val, font=ctk.CTkFont(size=17, weight="bold"), text_color=color)
        val_lbl.pack(anchor="w", padx=12, pady=(0, 6))
        return val_lbl

    # --- PORTFÖY İŞLEMLERİ (AL / SAT / SIFIRLA) ---
    def get_live_price(self, ticker):
        if ticker in self.live_prices and self.live_prices[ticker] > 0:
            return self.live_prices[ticker]
        try:
            stock = yf.Ticker(f"{ticker}.IS")
            info = stock.info
            p = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            if p:
                self.live_prices[ticker] = p
                return p
        except Exception:
            pass
        return None

    def buy_stock_action(self):
        ticker = self.trade_ticker.get().strip().upper()
        qty_str = self.trade_qty.get().strip()

        if not ticker or not qty_str.isdigit() or int(qty_str) <= 0:
            messagebox.showwarning("Uyarı", "Lütfen geçerli bir hisse kodu ve pozitif lot adedi girin.")
            return

        qty = int(qty_str)
        price = self.get_live_price(ticker)

        if not price:
            messagebox.showerror("Hata", f"[{ticker}] için canlı fiyat alınamadı!")
            return

        total_cost = price * qty

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT cash FROM account WHERE id = 1")
        cash = cursor.fetchone()[0]

        if cash < total_cost:
            conn.close()
            messagebox.showerror("Yetersiz Bakiye", f"Yetersiz Bakiye!\nGereken: {total_cost:,.2f} TL\nMevcut Nakit: {cash:,.2f} TL")
            return

        # Nakit düş
        new_cash = cash - total_cost
        cursor.execute("UPDATE account SET cash = ? WHERE id = 1", (new_cash,))

        # Portföy güncelle (Ağırlıklı ortalama maliyet)
        cursor.execute("SELECT quantity, avg_cost FROM portfolio WHERE ticker = ?", (ticker,))
        row = cursor.fetchone()
        if row:
            curr_qty, curr_cost = row
            new_qty = curr_qty + qty
            new_avg_cost = ((curr_qty * curr_cost) + (qty * price)) / new_qty
            cursor.execute("UPDATE portfolio SET quantity = ?, avg_cost = ? WHERE ticker = ?", (new_qty, new_avg_cost, ticker))
        else:
            cursor.execute("INSERT INTO portfolio (ticker, quantity, avg_cost) VALUES (?, ?, ?)", (ticker, qty, price))

        conn.commit()
        conn.close()

        self.trade_ticker.delete(0, 'end')
        self.trade_qty.delete(0, 'end')
        self.load_portfolio_from_db()
        messagebox.showinfo("Başarılı", f"{qty} Lot {ticker} @ {price:.2f} TL fiyatından alındı.\nKalan Nakit: {new_cash:,.2f} TL")

    def sell_stock_action(self):
        ticker = self.trade_ticker.get().strip().upper()
        qty_str = self.trade_qty.get().strip()

        if not ticker or not qty_str.isdigit() or int(qty_str) <= 0:
            messagebox.showwarning("Uyarı", "Lütfen geçerli bir hisse kodu ve pozitif lot adedi girin.")
            return

        qty = int(qty_str)
        price = self.get_live_price(ticker)

        if not price:
            messagebox.showerror("Hata", f"[{ticker}] için canlı fiyat alınamadı!")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT quantity, avg_cost FROM portfolio WHERE ticker = ?", (ticker,))
        row = cursor.fetchone()

        if not row or row[0] < qty:
            conn.close()
            curr = row[0] if row else 0
            messagebox.showerror("Hata", f"Portföyünüzde yeterli hisse yok!\nMevcut Lot: {curr}")
            return

        curr_qty, avg_cost = row
        income = price * qty

        cursor.execute("SELECT cash FROM account WHERE id = 1")
        cash = cursor.fetchone()[0]
        new_cash = cash + income
        cursor.execute("UPDATE account SET cash = ? WHERE id = 1", (new_cash,))

        if curr_qty == qty:
            cursor.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker,))
        else:
            cursor.execute("UPDATE portfolio SET quantity = ? WHERE ticker = ?", (curr_qty - qty, ticker))

        conn.commit()
        conn.close()

        self.trade_ticker.delete(0, 'end')
        self.trade_qty.delete(0, 'end')
        self.load_portfolio_from_db()
        messagebox.showinfo("Başarılı", f"{qty} Lot {ticker} @ {price:.2f} TL fiyatından satıldı.\nYeni Nakit: {new_cash:,.2f} TL")

    def reset_account_action(self):
        if messagebox.askyesno("Sıfırla", "Portföyü sıfırlayıp bakiyeyi tekrar 100.000 TL yapmak istiyor musunuz?"):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE account SET cash = 100000.0 WHERE id = 1")
            cursor.execute("DELETE FROM portfolio")
            conn.commit()
            conn.close()
            self.load_portfolio_from_db()

    def load_portfolio_from_db(self):
        for row in self.pf_tree.get_children():
            self.pf_tree.delete(row)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT cash FROM account WHERE id = 1")
        cash = cursor.fetchone()[0]

        cursor.execute("SELECT ticker, quantity, avg_cost FROM portfolio")
        items = cursor.fetchall()
        conn.close()

        total_stock_val = 0.0
        total_initial_cost = 0.0

        for ticker, qty, avg_cost in items:
            cur_price = self.get_live_price(ticker) or avg_cost
            tot_cost = qty * avg_cost
            cur_val = qty * cur_price
            pnl_tl = cur_val - tot_cost
            pnl_pct = ((cur_val - tot_cost) / tot_cost) * 100 if tot_cost > 0 else 0.0

            total_stock_val += cur_val
            total_initial_cost += tot_cost

            tag = "profit" if pnl_tl > 0 else ("loss" if pnl_tl < 0 else "even")

            self.pf_tree.insert("", "end", values=(
                ticker,
                f"{qty:,}",
                f"{avg_cost:.2f}",
                f"{cur_price:.2f}",
                f"{tot_cost:,.2f}",
                f"{cur_val:,.2f}",
                f"{pnl_tl:+,.2f} TL",
                f"%{pnl_pct:+.2f}"
            ), tags=(tag,))

        total_wealth = cash + total_stock_val
        overall_pnl_tl = total_wealth - 100000.0
        overall_pnl_pct = (overall_pnl_tl / 100000.0) * 100

        self.card_cash.configure(text=f"{cash:,.2f} TL")
        self.card_stock_val.configure(text=f"{total_stock_val:,.2f} TL")
        self.card_total_wealth.configure(text=f"{total_wealth:,.2f} TL")

        pnl_color = "#3fb950" if overall_pnl_tl >= 0 else "#f85149"
        self.card_pnl.configure(
            text=f"{overall_pnl_tl:+,.2f} TL (%{overall_pnl_pct:+.2f})",
            text_color=pnl_color
        )

    # --- RADAR VERİ YÜKLEME & CANLI MOTOR ---
    def detect_sector(self, ticker, yf_sec, yf_ind):
        if ticker in SECTOR_MAP:
            return SECTOR_MAP[ticker]
        combined = f"{yf_sec} {yf_ind}".lower()
        if "defense" in combined or "aerospace" in combined:
            return "Savunma Sanayii"
        elif "electrical equipment" in combined or "solar" in combined:
            return "Enerji & Trafo"
        elif "utilities" in combined or "energy" in combined:
            return "Elektrik Üretim & Enerji"
        elif "bank" in combined or "financial" in combined:
            return "Bankacılık"
        elif "holding" in combined or "conglomerate" in combined:
            return "Holding"
        elif "airline" in combined or "transport" in combined:
            return "Havacılık & Ulaşım"
        elif "steel" in combined or "basic materials" in combined:
            return "Sanayi & İmalat"
        elif "retail" in combined or "consumer" in combined:
            return "Perakende & Tüketim"
        else:
            return yf_sec if yf_sec else "Genel Sanayi"

    def compute_multi_factor_score(self, sector, price, pe, pb, eps, bvps, ev_ebitda, peg, net_margin, roe, rev_growth):
        score = 0
        sec = sector.lower()

        if net_margin is not None:
            if net_margin >= 0.20: score += 15
            elif net_margin >= 0.10: score += 10
            elif net_margin > 0: score += 5

        if roe is not None:
            if roe >= 0.35: score += 15
            elif roe >= 0.20: score += 10
            elif roe > 0: score += 5

        if rev_growth is not None:
            if rev_growth >= 0.35: score += 25
            elif rev_growth >= 0.15: score += 18
            elif rev_growth > 0: score += 10

        method = "Genel Çok Faktörlü Model"

        if any(w in sec for w in ["savunma", "trafo", "ekipman", "yazılım", "teknoloji", "güneş"]):
            method = "FD/FAVÖK & Büyüme"
            if ev_ebitda and ev_ebitda > 0:
                if ev_ebitda <= 11.0: score += 30
                elif ev_ebitda <= 15.0: score += 20
                elif ev_ebitda <= 20.0: score += 10
            if peg and 0 < peg <= 1.2:
                score += 15

        elif "bank" in sec or "finans" in sec:
            method = "PD/DD & ROE İskontosu"
            if pb and pb > 0:
                if pb <= 0.90: score += 25
                elif pb <= 1.20: score += 15
            if pe and pe > 0:
                if pe <= 5.0: score += 20
                elif pe <= 7.5: score += 10

        elif "holding" in sec:
            method = "NAD İskonto & Portföy"
            if pb and pb > 0 and pb <= 1.10: score += 25
            elif pb and pb <= 1.40: score += 15
            if pe and pe > 0 and pe <= 8.0: score += 20

        elif "havacılık" in sec or "ulaşım" in sec:
            method = "Operasyonel FAVÖK"
            if ev_ebitda and ev_ebitda > 0 and ev_ebitda <= 7.0: score += 25
            elif ev_ebitda and ev_ebitda <= 9.5: score += 15
            if pe and pe > 0 and pe <= 7.0: score += 20

        else:
            method = "Graham & Kâr Kalitesi"
            if eps and bvps and eps > 0 and bvps > 0:
                graham_val = math.sqrt(22.5 * eps * bvps)
                if price < graham_val: score += 30
                elif price < (graham_val * 1.15): score += 15
            if pe and pe > 0 and pe <= 10.0: score += 15

        if score >= 75:
            signal = "▲ GÜÇLÜ AL"
        elif score >= 60:
            signal = "▲ AL (UCUZ)"
        elif score >= 45:
            signal = "■ TUT / NÖTR"
        else:
            signal = "▼ PAHALI"

        return score, signal, method

    def load_radar_from_db(self):
        for row in self.radar_tree.get_children():
            self.radar_tree.delete(row)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        query = """
        SELECT 
            c.ticker, c.name, c.sector, v.price, v.score, 
            v.signal, v.net_margin, v.roe, v.growth, v.pe_ratio, v.pb_ratio, v.method
        FROM valuations v
        JOIN companies c ON v.ticker = c.ticker
        WHERE v.id IN (
            SELECT MAX(id) FROM valuations GROUP BY ticker
        )
        ORDER BY v.score DESC;
        """
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            
            total_count = len(rows)
            buy_count = 0
            pe_list = []

            for r in rows:
                ticker, name, sector, price, score, sig, net_m, roe, growth, pe, pb, method = r
                
                if price:
                    self.live_prices[ticker] = price

                if "AL" in str(sig):
                    buy_count += 1
                if pe and pe > 0:
                    pe_list.append(pe)

                net_m_str = f"%{net_m * 100:.1f}" if net_m is not None else "-"
                roe_str = f"%{roe * 100:.1f}" if roe is not None else "-"
                growth_str = f"%{growth * 100:.1f}" if growth is not None else "-"

                tag = "neutral"
                if "GÜÇLÜ AL" in str(sig): tag = "strong_buy"
                elif "AL" in str(sig): tag = "buy"
                elif "PAHALI" in str(sig): tag = "expensive"

                self.radar_tree.insert("", "end", values=(
                    ticker, name, sector if sector else "-",
                    f"{price:.2f}" if price else "-",
                    f"{score} / 100",
                    sig if sig else "-",
                    net_m_str,
                    roe_str,
                    growth_str,
                    f"{pe:.2f}" if pe and pe > 0 else "-",
                    f"{pb:.2f}" if pb and pb > 0 else "-",
                    method if method else "-"
                ), tags=(tag,))

            self.card_total.configure(text=str(total_count))
            self.card_buy.configure(text=f"{buy_count} Hisse")
            avg_pe = sum(pe_list) / len(pe_list) if pe_list else 0.0
            self.card_avg_pe.configure(text=f"{avg_pe:.2f}")

        except Exception as e:
            print("DB Hatası:", e)
        finally:
            conn.close()

    def start_live_fetch_thread(self, specific_ticker=None):
        self.refresh_btn.configure(state="disabled")
        self.add_btn.configure(state="disabled")
        self.status_badge.configure(text="● VERİLER ALINIYOR...", text_color="#f2cc60")
        threading.Thread(target=self._fetch_live_data_worker, args=(specific_ticker,), daemon=True).start()

    def _fetch_live_data_worker(self, specific_ticker=None):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Portföydeki hisseleri de canlı veri havuzuna dahil et
        cursor.execute("SELECT ticker FROM portfolio")
        pf_tickers = [row[0] + ".IS" for row in cursor.fetchall()]

        if specific_ticker:
            tickers_to_process = list(set([specific_ticker] + pf_tickers))
        else:
            cursor.execute("SELECT ticker FROM companies")
            db_tickers = [row[0] + ".IS" for row in cursor.fetchall()]
            all_list = db_tickers if db_tickers else DEFAULT_TICKERS
            tickers_to_process = list(set(all_list + pf_tickers))

        today = datetime.now().strftime("%Y-%m-%d")

        for sym in tickers_to_process:
            clean_ticker = sym.replace(".IS", "").upper()
            full_symbol = clean_ticker + ".IS"
            try:
                stock = yf.Ticker(full_symbol)
                info = stock.info

                price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
                eps = info.get("trailingEps")
                bvps = info.get("bookValue")
                pe = info.get("trailingPE", 0)
                pb = info.get("priceToBook", 0)
                ev_ebitda = info.get("enterpriseToEbitda", 0)
                peg = info.get("pegRatio", 0)
                
                net_margin = info.get("profitMargins")
                roe = info.get("returnOnEquity")
                rev_growth = info.get("revenueGrowth")

                name = info.get("shortName", clean_ticker)
                yf_sec = info.get("sector", "")
                yf_ind = info.get("industry", "")

                if price is None:
                    continue

                self.live_prices[clean_ticker] = price
                sector = self.detect_sector(clean_ticker, yf_sec, yf_ind)

                cursor.execute(
                    "INSERT OR IGNORE INTO companies (ticker, name, sector) VALUES (?, ?, ?)",
                    (clean_ticker, name, sector)
                )
                cursor.execute(
                    "UPDATE companies SET sector = ?, name = ? WHERE ticker = ?",
                    (sector, name, clean_ticker)
                )

                score, signal, method = self.compute_multi_factor_score(
                    sector, price, pe, pb, eps, bvps, ev_ebitda, peg, net_margin, roe, rev_growth
                )

                cursor.execute("""
                    INSERT INTO valuations (ticker, price, pe_ratio, pb_ratio, net_margin, roe, growth, score, signal, method, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (clean_ticker, price, pe, pb, net_margin, roe, rev_growth, score, signal, method, today))

            except Exception as e:
                print(f"Hata [{clean_ticker}]: {e}")

        conn.commit()
        conn.close()
        self.after(0, self._on_fetch_complete)

    def _on_fetch_complete(self):
        self.load_radar_from_db()
        self.load_portfolio_from_db()
        self.refresh_btn.configure(state="normal")
        self.add_btn.configure(state="normal")
        self.status_badge.configure(text="● CANLI VERİ AKTİF", text_color="#3fb950")

    def add_ticker_action(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showwarning("Uyarı", "Lütfen bir hisse kodu girin (örn: ASELS).")
            return
        self.ticker_entry.delete(0, 'end')
        self.start_live_fetch_thread(specific_ticker=ticker + ".IS")


if __name__ == "__main__":
    app = BorsaApp()
    app.mainloop()