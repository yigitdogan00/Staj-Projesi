import re
import os

file_path = r"c:\Users\Stajyer\Desktop\Staj Uygulaması\app\templates\base.html"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'\{\s*%\s*(if.*?)\s*%\s*\}', r'{% \1 %}', content)
content = re.sub(r'\{\s*%\s*else\s*%\s*\}', r'{% else %}', content)
content = re.sub(r'\{\s*%\s*endif\s*%\s*\}', r'{% endif %}', content)

content = content.replace("{% if request.endpoint=='main.index' %}", "{% if request.endpoint in ('main.index', 'auth.login', 'auth.register') %}")
content = content.replace("{% if request.endpoint == 'main.index' %}", "{% if request.endpoint in ('main.index', 'auth.login', 'auth.register') %}")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
