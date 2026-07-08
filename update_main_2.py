with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'google_qr_url = f"https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl={quote(token)}&choe=UTF-8"',
    'google_qr_url = f"https://quickchart.io/qr?text={quote(token)}&size=300"'
)

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("URL updated")
