# BIST Hisse Analiz ve Sanal Portföy Uygulaması

Python ve SQLite kullanılarak geliştirilmiş, Borsa İstanbul (BIST) hisseleri için temel değerleme analizi ve sanal portföy takibi sunan masaüstü uygulaması.

## Öne Çıkan Özellikler
* **Sektörel Değerleme Motoru (`analiz_motoru.py`):** Şirketlerin finansal çarpanlarına ve sektör dinamiklerine göre temel analiz hesaplamaları.
* **Piyasa Tarama (`tarama.py`):** Güncel piyasa verilerini çekerek belirlenen kriterlere uygun hisselerin taranması.
* **Sanal Portföy Takibi (`app.py` & `init_db.py`):** SQLite veritabanı altyapısı ile kalıcı portföy oluşturma, alım-satım simülasyonu ve getiri takibi.

## Kurulum ve Çalıştırma
```bash
git clone [https://github.com/burakerol52/bist-borsa-analiz.git](https://github.com/burakerol52/bist-borsa-analiz.git)
cd bist-borsa-analiz
python init_db.py
python app.py
