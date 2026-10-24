import urllib.request
import re

# Check the Zetaris UI for API calls
try:
    req = urllib.request.Request('http://localhost:3000')
    resp = urllib.request.urlopen(req, timeout=5)
    content = resp.read().decode('utf-8', errors='ignore')
    
    # Find JS files
    for match in re.finditer(r'src=["\']([^"\']*\.js)["\']', content):
        print('JS:', match.group(1))
    for match in re.finditer(r'chunk[^"\']*\.js', content):
        print('Chunk:', match.group(0))
except Exception as e:
    print('Error:', e)

# Also check the login page
try:
    req = urllib.request.Request('http://localhost:3000/login')
    resp = urllib.request.urlopen(req, timeout=5)
    content = resp.read().decode('utf-8', errors='ignore')
    for match in re.finditer(r'fetch\([^)]+\)', content):
        print('Fetch:', match.group(0)[:200])
    for match in re.finditer(r'axios\.[a-z]+\([^)]+\)', content):
        print('Axios:', match.group(0)[:200])
except Exception as e:
    print('Login page error:', e)