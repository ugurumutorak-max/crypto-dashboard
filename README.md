# 🚀 Crypto Listings Dashboard

Web üzerinden MEXC, Binance ve Bybit vadeli işlem coinlerini karşılaştıran canlı dashboard.

## 📋 Özellikler

- 📊 MEXC vadeli işlem coinlerinin tümü (max pozisyon + market cap)
- 🔴 MEXC'de olup Binance'de olmayan coinler
- 🟡 MEXC'de olup Bybit'te olmayan coinler
- ⏱️ Saatlik otomatik güncelleme
- 📱 Responsive (mobil uyumlu) tasarım
- 🎨 Modern gradient tema

## 🌐 Canlı Demo

[Buraya deploy sonrası URL gelecek]

## 🚀 Yerel Kurulum

### Gereksinimler
- Python 3.9+
- pip

### Adımlar

1. Repository'yi klonlayın:
```bash
git clone https://github.com/KULLANICI_ADINIZ/crypto-dashboard.git
cd crypto-dashboard
```

2. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

3. Uygulamayı çalıştırın:
```bash
python3 crypto_web_dashboard.py
```

4. Tarayıcınızda açın:
```
http://127.0.0.1:5000
```

## 📦 Deployment (Render.com)

### 1. GitHub'a Yükleme

```bash
# Git repository oluştur
git init
git add .
git commit -m "Initial commit"

# GitHub'a push
git remote add origin https://github.com/KULLANICI_ADINIZ/crypto-dashboard.git
git branch -M main
git push -u origin main
```

### 2. Render.com'da Deploy

1. [Render.com](https://render.com) hesabı oluşturun (ücretsiz)
2. "New +" → "Web Service" seçin
3. GitHub repository'nizi bağlayın
4. Ayarlar:
   - **Name:** crypto-dashboard (veya istediğiniz isim)
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn crypto_web_dashboard:app`
   - **Plan:** Free
5. "Create Web Service" butonuna tıklayın

Deploy işlemi 5-10 dakika sürer. Tamamlandığında size bir URL verilir (örn: `https://crypto-dashboard.onrender.com`)

## 📁 Proje Yapısı

```
crypto-dashboard/
├── crypto_web_dashboard.py    # Ana Flask uygulaması
├── templates/
│   └── dashboard.html          # Web arayüzü
├── requirements.txt            # Python bağımlılıkları
├── runtime.txt                 # Python versiyonu
├── Procfile                    # Deployment komutu
├── render.yaml                 # Render.com yapılandırması
└── README.md                   # Bu dosya
```

## 🔧 Teknolojiler

- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, JavaScript
- **API'ler:** MEXC, Binance, Bybit, CoinMarketCap
- **Deployment:** Render.com / Railway / PythonAnywhere

## 📊 API Endpoints

- `GET /` - Ana dashboard sayfası
- `GET /api/data` - Tüm veriler (JSON)
- `GET /api/mexc` - MEXC vadeli listesi (JSON)
- `GET /api/binance` - Binance karşılaştırması (JSON)
- `GET /api/bybit` - Bybit karşılaştırması (JSON)

## ⚙️ Güncelleme Sıklığı

Veriler **her saat** otomatik olarak güncellenir. Değiştirmek için:

**Python dosyasında (crypto_web_dashboard.py):**
```python
time.sleep(3600)  # 3600 saniye = 1 saat
```

**HTML dosyasında (templates/dashboard.html):**
```javascript
setInterval(updateData, 3600000);  // 3600000 ms = 1 saat
```

## 🔑 API Anahtarı

CoinMarketCap API anahtarını güncellemek için `crypto_web_dashboard.py` dosyasında:

```python
CMC_API_KEY = "BURAYA_API_KEYINIZI_GIRIN"
```

Ücretsiz API anahtarı için: https://coinmarketcap.com/api/

## 📝 Lisans

MIT License

## 🤝 Katkıda Bulunma

Pull request'ler kabul edilir. Büyük değişiklikler için lütfen önce bir issue açın.

## 📧 İletişim

Sorularınız için issue açabilirsiniz.

---

⭐ Projeyi beğendiyseniz yıldız vermeyi unutmayın!
