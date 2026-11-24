import time, urllib.request, json

for i in range(30):
    time.sleep(2)
    try:
        urllib.request.urlopen("http://localhost:8000/api/model/info", timeout=5)
        print(f"up after {(i+1)*2}s")
        break
    except:
        pass

payload = json.dumps({"query": "tenant not paying rent", "top_k": 5}).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/search", data=payload,
    headers={"Content-Type": "application/json"}, method="POST"
)
t0 = time.time()
r = urllib.request.urlopen(req, timeout=20)
body = json.loads(r.read())
elapsed = time.time() - t0
n = len(body["results"])
print(f"round-trip: {elapsed:.3f}s  results={n}")
