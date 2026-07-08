import os

file_path = 'app/templates/admin_panel.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'Kapsamlı Admin Paneli': '{{ trans(\'Kapsamlı Admin Paneli\') }}',
    '<div class="metric-title">Toplam Kullanıcı</div>': '<div class="metric-title">{{ trans(\'Toplam Kullanıcı\') }}</div>',
    '<div class="metric-title">Toplam Oda</div>': '<div class="metric-title">{{ trans(\'Toplam Oda\') }}</div>',
    '<div class="metric-title">Tüm Rezervasyonlar</div>': '<div class="metric-title">{{ trans(\'Tüm Rezervasyonlar\') }}</div>',
    '<div class="metric-title">Bugünkü Rezervasyonlar</div>': '<div class="metric-title">{{ trans(\'Bugünkü Rezervasyonlar\') }}</div>',
    '<h3 class="section-title">Tüm Rezervasyonlar</h3>': '<h3 class="section-title">{{ trans(\'Tüm Rezervasyonlar\') }}</h3>',
    '<th>Kullanıcı</th>': '<th>{{ trans(\'Kullanıcı\') }}</th>',
    '<th>Oda</th>': '<th>{{ trans(\'Oda\') }}</th>',
    '<th>Tarih</th>': '<th>{{ trans(\'Tarih\') }}</th>',
    '<th>Saat</th>': '<th>{{ trans(\'Saat\') }}</th>',
    '<th>Oluşturulma</th>': '<th>{{ trans(\'Oluşturulma\') }}</th>',
    '<th>İşlem</th>': '<th>{{ trans(\'İşlem\') }}</th>',
    '>İptal Et<': '>{{ trans(\'İptal Et\') }}<',
    'Sistemde henüz hiçbir rezervasyon bulunmuyor.': '{{ trans(\'Sistemde henüz hiçbir rezervasyon bulunmuyor.\') }}',
    'Kullanıcı Yönetimi': '{{ trans(\'Kullanıcı Yönetimi\') }}',
    'Kullanıcı Adı': '{{ trans(\'Kullanıcı Adı\') }}',
    '<th>E-Posta</th>': '<th>{{ trans(\'E-Posta\') }}</th>',
    '<th>Rol</th>': '<th>{{ trans(\'Rol\') }}</th>',
    '>Admin<': '>{{ trans(\'Admin\') }}<',
    '>User<': '>{{ trans(\'User\') }}<',
    '>Kullanıcıyı Sil<': '>{{ trans(\'Kullanıcıyı Sil\') }}<',
    '>Kendiniz<': '>{{ trans(\'Kendiniz\') }}<',
    '<h3 class="section-title">Oda Yönetimi</h3>': '<h3 class="section-title">{{ trans(\'Oda Yönetimi\') }}</h3>',
    '<th>Oda Adı</th>': '<th>{{ trans(\'Oda Adı\') }}</th>',
    '<th>Kapasite</th>': '<th>{{ trans(\'Kapasite\') }}</th>',
    '<th>Açıklama</th>': '<th>{{ trans(\'Açıklama\') }}</th>',
    '>Odayı Sil<': '>{{ trans(\'Odayı Sil\') }}<',
    'Sistem Logları (Son 50 İşlem)': '{{ trans(\'Sistem Logları (Son 50 İşlem)\') }}',
    '>Logları Temizle<': '>{{ trans(\'Logları Temizle\') }}<',
    'Tarih / Saat': '{{ trans(\'Tarih / Saat\') }}',
    'İşlem Türü': '{{ trans(\'İşlem Türü\') }}',
    '<th>Detaylar</th>': '<th>{{ trans(\'Detaylar\') }}</th>',
    '>GİRİŞ<': '>{{ trans(\'GİRİŞ\') }}<',
    '>REZERVASYON<': '>{{ trans(\'REZERVASYON\') }}<',
    '>İPTAL/SİLME<': '>{{ trans(\'İPTAL/SİLME\') }}<',
    'Henüz log kaydı yok.': '{{ trans(\'Henüz log kaydı yok.\') }}',
    'Not: Hızlı iptal işlemleri için "Günlük Durum" sekmesine gidip kırmızı kutulara tıklayabilirsiniz.': '{{ trans(\'Not: Hızlı iptal işlemleri için \"Günlük Durum\" sekmesine gidip kırmızı kutulara tıklayabilirsiniz.\') }}',
    '{{ room.capacity }} Kişi': '{{ room.capacity }} {{ trans(\'Kişi\') }}'
}

for k, v in replacements.items():
    content = content.replace(k, v)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
