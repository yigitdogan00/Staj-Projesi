import polib

po = polib.pofile('app/translations/en/LC_MESSAGES/messages.po')

new_translations = {
    'Sanal Kapı Okuyucu': 'Virtual Door Scanner',
    'Kameraya QR kodu göstererek kapı girişini simüle edin.': 'Simulate door entry by showing a QR code to the camera.',
    'Yeniden Okut': 'Scan Again',
    'Doğrulanıyor...': 'Verifying...',
    'QR Kod sunucuya iletiliyor...': 'Sending QR code to the server...',
    'KAPI AÇILDI': 'DOOR OPENED',
    'ERİŞİM REDDEDİLDİ': 'ACCESS DENIED',
    'HATA': 'ERROR',
    'Sunucuyla bağlantı kurulamadı.': 'Could not connect to server.',
    'Sanal Kapı (Test)': 'Virtual Door (Test)'
}

for entry in po:
    if entry.msgid in new_translations:
        entry.msgstr = new_translations[entry.msgid]

po.save()
print("PO updated 3.")
