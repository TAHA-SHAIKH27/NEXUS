import urllib.request
import re

# Check the login page JS
try:
    req = urllib.request.Request('http://localhost:3000/_next/static/chunks/app/login/page-ec8beda86f37de64.js')
    resp = urllib.request.urlopen(req, timeout=5)
    content = resp.read().decode('utf-8', errors='ignore')
    
    for match in re.finditer(r'fetch\([^)]+\)', content):
        print('Fetch:', match.group(0)[:200])
    for match in re.finditer(r'axios\.[a-z]+\([^)]+\)', content):
        print('Axios:', match.group(0)[:200])
    for match in re.finditer(r'/api/v1\.0/[^"\'\s]+', content):
        print('API v1.0:', match.group(0))
    for match in re.finditer(r'/api/[^"\'\s]+', content):
        print('API:', match.group(0))
except Exception as e:
    print('Error:', e)