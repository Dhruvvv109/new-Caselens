import time, urllib.request, json
time.sleep(20)
payload = json.dumps({"query": "tenant not paying rent, landlord seeks eviction", "top_k": 5}).encode()
headers = {"Content-Type": "application/json"}

def call():
    req = urllib.request.Request("http://localhost:8000/api/search", data=payload, headers=headers, method="POST")
    t0 = time.time()
    r = urllib.request.urlopen(req, timeout=20)
    body = json.loads(r.read())
    return time.time() - t0, len(body.get("results", []))

t1, n1 = call()
print(f"1st call: {t1:.3f}s  results={n1}")
t2, n2 = call()
print(f"2nd call: {t2:.3f}s  results={n2}")
