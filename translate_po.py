import polib

po = polib.pofile('app/translations/en/LC_MESSAGES/messages.po')

translations = {
    'Odalar': 'Rooms',
    'Dashboard': 'Dashboard',
    'Admin Panel': 'Admin Panel',
    'Çıkış Yap': 'Logout',
    'Giriş Yap': 'Login',
    'Kayıt Ol': 'Sign Up',
    'Günlük Durum': 'Daily Overview',
    'Toplantı Odası Rezervasyon Sistemine Hoş Geldiniz': 'Welcome to the Meeting Room Reservation System',
    'Lütfen rezervasyon yapmak veya mevcut odaları görüntülemek için giriş yapın.': 'Please log in to make a reservation or view available rooms.',
    'Kapasite': 'Capacity',
    'Kişi': 'People',
    'Rezervasyon Tarihi': 'Reservation Date',
    'Kişileri Davet Et (Opsiyonel)': 'Invite People (Optional)',
    'Birden fazla kişi seçmek için Ctrl (veya Cmd) tuşuna basılı tutarak tıklayın.': 'Hold Ctrl (or Cmd) to select multiple people.',
    'Lütfen Saat Seçin': 'Please Select Time',
    'Uygun Saatler': 'Available Times',
    'Yeşil renkli boş saatlere tıklayarak seçiminizi yapabilirsiniz.': 'You can make your selection by clicking on the green empty times.',
    'Saatler yükleniyor...': 'Loading times...',
    'Bu saat dolu': 'This time is booked',
    'Seçimi Onayla': 'Confirm Selection',
    'Üzgünüz, az önce seçtiğiniz saat dilimi başka bir kullanıcı tarafından rezerve edildi.': 'Sorry, the time slot you just selected was reserved by another user.',
    'Toplantı Odaları': 'Meeting Rooms',
    'Lütfen rezervasyon yapmak istediğiniz odayı seçin.': 'Please select the room you want to book.',
    'Takvimi Görüntüle': 'View Calendar',
    'Rezervasyonlarım': 'My Reservations',
    'Yeni Rezervasyon': 'New Reservation',
    'Odası': 'Room',
    'Davetliler': 'Attendees',
    'Takvime Ekle': 'Add to Calendar',
    'Bu rezervasyonu iptal etmek istediğinize emin misiniz?': 'Are you sure you want to cancel this reservation?',
    'İptal Et': 'Cancel',
    'Henüz bir rezervasyonunuz bulunmuyor.': 'You have no reservations yet.',
    'Hemen Oda Rezervasyonu Yap': 'Book a Room Now',
    'Davet Edildiğim Toplantılar': 'Meetings I Am Invited To',
    'Oluşturan': 'Created By',
    'Şu an için davet edildiğiniz bir toplantı bulunmuyor.': 'You are currently not invited to any meetings.',
    'Beni Hatırla': 'Remember Me',
    'Şifremi Unuttum': 'Forgot Password',
    'Hesabınız yok mu?': "Don't have an account?",
    'Hemen Kayıt Olun': 'Sign Up Now',
    'Zaten hesabınız var mı?': 'Already have an account?',
    'Giriş Yapın': 'Log In',
    'Bildirimler': 'Notifications',
    'Onayla': 'Accept',
    'Reddet': 'Reject',
    'Okundu İşaretle': 'Mark as Read',
    'Yeni bildiriminiz yok.': 'You have no new notifications.',
    'Daveti kabul ettiniz.': 'You have accepted the invitation.',
    'Daveti reddettiniz.': 'You have rejected the invitation.',
    'Bu işlemi yapmaya yetkiniz yok.': 'You are not authorized to perform this action.',
    'Şu an Toplantıdasınız': 'You are currently in a meeting',
    'Kabul Edilen Toplantılar': 'Accepted Meetings',
    'Yaklaşan Toplantılar': 'Upcoming Meetings',
    'Takvime Ekle': 'Add to Calendar',
}

for entry in po:
    if entry.msgid in translations:
        entry.msgstr = translations[entry.msgid]

po.save()
print("PO file updated successfully.")
