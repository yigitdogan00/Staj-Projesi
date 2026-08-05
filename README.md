# Staj Uygulaması - Kurulum ve Kullanım Kılavuzu

Bu proje, toplantı odası rezervasyonu ve yönetimi yapılabilen bir web uygulamasıdır. Projeyi bilgisayarınıza indirip yerel geliştirme ortamınızda çalıştırmak için aşağıdaki adımları takip edebilirsiniz.

## Gereksinimler

Projenin çalışması için bilgisayarınızda aşağıdakilerin kurulu olması gerekir:
- **Python 3.10** veya daha güncel bir sürüm
- **pip** (Python paket yöneticisi)
- **Git** (Opsiyonel, projeyi klonlamak için)

## Kurulum Adımları

### 1. Projeyi İndirin

Projeyi Git kullanarak klonlayın veya `.zip` dosyası olarak indirip bir klasöre çıkartın:

```bash
# Git kullanarak klonlamak için
git clone <proje-git-adresi>
cd "Staj Uygulamasi"
```

### 2. Sanal Ortam (Virtual Environment) Oluşturun

Bağımlılıkların sistemdeki diğer projelerle çakışmaması için bir sanal ortam oluşturun:

**Windows için:**
```cmd
python -m venv venv
.\venv\Scripts\activate
```

**macOS ve Linux için:**
```bash
python3 -m venv venv
source venv/bin/activate
```

*(Sanal ortam aktif olduğunda komut satırınızın başında `(venv)` ibaresini görmelisiniz.)*

### 3. Gerekli Paketleri (Bağımlılıkları) Kurun

Sanal ortam aktifken, projenin çalışması için gerekli kütüphaneleri `requirements.txt` dosyasından yükleyin:

```bash
pip install -r requirements.txt
```

### 4. Çevre Değişkenlerini (Environment Variables) Ayarlayın

Projenin ana dizininde (klasörde) bir `.env` dosyası oluşturun. Uygulamanın Google OAuth girişi, e-posta gönderimi ve bildirim servisi (VAPID) için aşağıdaki değişkenleri doldurmanız gerekecektir.

`.env` dosyasının içine aşağıdaki şablonu kopyalayabilirsiniz:

```env
# Push Notification (VAPID) Ayarları
VAPID_PUBLIC_KEY=sizin_vapid_public_keyiniz
VAPID_PRIVATE_KEY=private_key.pem
VAPID_CLAIM_EMAIL=mailto:admin@example.com

# Google OAuth Ayarları (Google ile Giriş Yap için)
GOOGLE_CLIENT_ID=sizin_google_client_id_niz
GOOGLE_CLIENT_SECRET=sizin_google_client_secret_niz

# E-posta SMTP Ayarları
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=sizin_mail_adresiniz@gmail.com
MAIL_PASSWORD=sizin_mail_uygulama_sifreniz
MAIL_DEFAULT_SENDER=sizin_mail_adresiniz@gmail.com
```

### 5. Veritabanını Oluşturun ve Başlangıç Verilerini Yükleyin

Proje SQLite veritabanı kullanmaktadır. Veritabanı tablolarını oluşturmak, toplantı odalarını eklemek ve varsayılan yönetici (admin) hesabını oluşturmak için başlangıç (seed) dosyasını çalıştırın:

```bash
python seed.py
```

Bu işlemi yaptıktan sonra sistem size "Database seeding completed." mesajını verecek ve uygulamayı deneyimleyebilmeniz için varsayılan bir test hesabı oluşturacaktır:
- **Email:** `test@sirket.com`
- **Şifre:** `test1234`

### 6. Uygulamayı Başlatın

Tüm kurulumlar tamamlandı. Artık yerel sunucuyu ayağa kaldırabilirsiniz:

```bash
python run.py
```

Tarayıcınızdan aşağıdaki adreslere giderek uygulamaya erişebilirsiniz:
- **Ana Uygulama:** `http://localhost:5000`

## Log Yönetimi ve Güvenli Saklama

Projede performans, sistem güvenliği ve veri saklama standartlarına uygun loglama mimarisi uygulanmıştır:

- **Asenkron Sistem Loglaması (Non-blocking Logging):** Uygulama istek yanıt sürelerini olumsuz etkilememek adına arka plan kuyruk mimarisi (`QueueHandler` / `QueueListener`) kullanılarak sistem logları asenkron şekilde saklanır.
- **Otomatik Log Rotasyonu:** Log dosyalarının sistem kaynağını aşırı tüketmesini önlemek amacıyla limitli döngüsel dosya rotasyonu (Log Rotation) uygulanmaktadır.
- **Hassas Veri Maskeleme (Log Anonymization):** KVKK/GDPR uyumluluğu ve veri güvenliği ilkeleri doğrultusunda; şifreler, T.C. Kimlik Numaraları, kredi kartı bilgileri, doğrulama kodları ve erişim anahtarları log dosyalarına ve veritabanı kayıtlarına yazılmadan önce regex tabanlı filtreler (`SensitiveDataFilter` / `SensitiveDataFormatter`) tarafından otomatik olarak anonimleştirilir (`[MASKED]`).
- **Periyodik Otomatik Veri Temizliği (Retention Policy):** Arka planda çalışan zamanlanmış görevler (APScheduler Cron Job) aracılığıyla, belirlenen saklama süresini aşan sistem denetim kayıtları otomatik ve güvenli bir şekilde temizlenmektedir.

## Sık Karşılaşılan Sorunlar

- **"ModuleNotFoundError" Hatası:** Sanal ortamı (`venv`) aktifleştirmeyi unuttuğunuzda yaşanabilir. Komut satırında 2. adımdaki `activate` komutunu tekrar çalıştırın.
- **SQLite "no such table" Hatası:** `python seed.py` komutunu çalıştırmamış olabilirsiniz. Veritabanının oluşturulabilmesi için bu komutu mutlaka bir kez çalıştırın.
- **Port 5000 Hatası:** Bilgisayarınızda `5000` portunu kullanan başka bir uygulama varsa sunucu başlamaz. (Genellikle macOS Monterey ve sonrasında AirPlay Receiver portu kapatır). Bu durumda `run.py` içindeki port numarasını değiştirebilirsiniz.

*İyi çalışmalar!*
