import requests

url_web = 'https://github.com/Wynterrrrr/ObsdianDrive/blob/main/Todo/Personal%20To-Do.md'
url_raw = 'https://raw.githubusercontent.com/Wynterrrrr/ObsdianDrive/main/Todo/Personal%20To-Do.md'

r1 = requests.get(url_web)
r2 = requests.get(url_raw)

print('web', r1.status_code)
print('raw', r2.status_code)
if r1.status_code == 200:
    print('web len', len(r1.text))
    import re
    m = re.search(r'<title>(.*?)</title>', r1.text, re.S)
    if m:
        print('title:', m.group(1).strip())
