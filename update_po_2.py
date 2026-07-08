import polib

po = polib.pofile('app/translations/en/LC_MESSAGES/messages.po')

new_translations = {
    'QR Göster': 'Show QR',
    'Oda Giriş QR Kodu': 'Room Entry QR Code',
    'Kapıdaki okuyucuya bu QR kodu okutarak odaya giriş yapabilirsiniz.': 'You can enter the room by scanning this QR code at the door reader.',
    'Kapat': 'Close'
}

for entry in po:
    if entry.msgid in new_translations:
        entry.msgstr = new_translations[entry.msgid]

po.save()
print("PO updated 2.")
