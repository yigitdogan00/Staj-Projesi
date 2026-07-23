import os

po_path = r'c:\Users\Stajyer\Desktop\Staj Uygulaması\app\translations\en\LC_MESSAGES\messages.po'

translations = [
    ("Rezervasyon başarıyla iptal edildi.", "Reservation successfully cancelled.")
]

with open(po_path, 'a', encoding='utf-8') as f:
    for tr_id, tr_str in translations:
        f.write(f'\n\nmsgid "{tr_id}"\nmsgstr "{tr_str}"\n')
