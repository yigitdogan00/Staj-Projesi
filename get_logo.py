import urllib.request
import re
try:
    html = urllib.request.urlopen('https://www.rndecommerce.com/').read().decode('utf-8')
    urls = re.findall(r'src="([^"]+)"', html)
    logos = [u for u in urls if 'logo' in u.lower()]
    print("LOGOS:", logos)
except Exception as e:
    print(e)
