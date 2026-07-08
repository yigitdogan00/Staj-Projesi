import polib

po = polib.pofile('app/translations/en/LC_MESSAGES/messages.po')

new_translations = {
    'Kapsamlı Admin Paneli': 'Comprehensive Admin Panel',
    'Toplam Kullanıcı': 'Total Users',
    'Toplam Oda': 'Total Rooms',
    'Tüm Rezervasyonlar': 'All Reservations',
    'Bugünkü Rezervasyonlar': "Today's Reservations",
    'Kullanıcı': 'User',
    'Oda': 'Room',
    'Tarih': 'Date',
    'Saat': 'Time',
    'Oluşturulma': 'Created At',
    'İşlem': 'Action',
    'Sistemde henüz hiçbir rezervasyon bulunmuyor.': 'No reservations exist in the system yet.',
    'Kullanıcı Yönetimi': 'User Management',
    'Kullanıcı Adı': 'Username',
    'E-Posta': 'Email',
    'Rol': 'Role',
    'Admin': 'Admin',
    'User': 'User',
    'Kullanıcıyı Sil': 'Delete User',
    'Kendiniz': 'Yourself',
    'Oda Yönetimi': 'Room Management',
    'Oda Adı': 'Room Name',
    'Açıklama': 'Description',
    'Odayı Sil': 'Delete Room',
    'Sistem Logları (Son 50 İşlem)': 'System Logs (Last 50 Actions)',
    'Logları Temizle': 'Clear Logs',
    'Tarih / Saat': 'Date / Time',
    'İşlem Türü': 'Action Type',
    'Detaylar': 'Details',
    'GİRİŞ': 'LOGIN',
    'REZERVASYON': 'RESERVATION',
    'İPTAL/SİLME': 'CANCEL/DELETE',
    'Henüz log kaydı yok.': 'No log records yet.',
    'Not: Hızlı iptal işlemleri için "Günlük Durum" sekmesine gidip kırmızı kutulara tıklayabilirsiniz.': 'Note: For quick cancellations, you can go to the "Daily Overview" tab and click on the red boxes.',
    'Birden fazla kişi seçmek için isimlerin üzerine tıklamanız yeterlidir.': 'Simply click on names to select multiple people.'
}

for entry in po:
    if entry.msgid in new_translations:
        entry.msgstr = new_translations[entry.msgid]

po.save()
print("PO updated.")
