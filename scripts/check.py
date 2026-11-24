"""
CaseLens acceptance checks.
"""
import http.client, json, time
from collections import Counter

conn = http.client.HTTPConnection("127.0.0.1", 8000)

def get(path):
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read()
    if r.status >= 400:
        raise AssertionError(f"GET {path} => HTTP {r.status}: {body[:200]}")
    return json.loads(body)

def post(path, data):
    payload = json.dumps(data).encode()
    conn.request("POST", path, body=payload, headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    body = r.read()
    if r.status >= 400:
        raise AssertionError(f"POST {path} => HTTP {r.status}: {body[:200]}")
    return json.loads(body)

failures = []

# ── CHECK 1: /api/overview ────────────────────────────────────────────────────
print("CHECK 1  /api/overview")
ov = get("/api/overview")
print(f"  total_active={ov.get('total_active')}")
print(f"  by_bucket={ov.get('by_bucket')}")
print(f"  top_queue={len(ov.get('top_queue', []))} rows")

if ov.get("total_active") != 150:
    failures.append(f"total_active={ov.get('total_active')} (expected 150)")
bk = ov.get("by_bucket", {})
bk_sum = sum(bk.values())
if bk_sum != 150:
    failures.append(f"bucket counts sum={bk_sum} (expected 150)")
if len(bk) < 3 or any(v == 0 for v in bk.values()):
    failures.append(f"not all 3 buckets non-empty: {bk}")
queue = ov.get("top_queue", [])
if len(queue) < 10:
    failures.append(f"top_queue only {len(queue)} rows (expected 10)")
scores = [q.get("priority_score", 0) for q in queue]
if len(set(scores)) < 5:
    failures.append(f"priority scores not distinct enough: {scores}")
print("  PASS" if not failures else f"  ISSUES: {failures[-len([f for f in failures if 'total' in f or 'bucket' in f or 'queue' in f or 'score' in f]):]}")

# ── CHECK 2: /api/search timing ───────────────────────────────────────────────
print("\nCHECK 2  /api/search speed & relevance")
queries = [
    "tenant not paying rent landlord eviction",
    "cheque bounce section 138",
    "bail NDPS commercial quantity",
]
for q in queries:
    t0 = time.perf_counter()
    res = post("/api/search", {"query": q, "top_k": 8})
    elapsed = time.perf_counter() - t0
    results = res.get("results", [])
    print(f"  '{q[:40]}' => {len(results)} results in {elapsed:.3f}s  backend={res.get('backend','?')}")
    if len(results) < 8:
        failures.append(f"search '{q[:30]}' returned {len(results)} (expected 8)")
    if elapsed >= 1.0:
        failures.append(f"search '{q[:30]}' took {elapsed:.3f}s (must be <1s on warm server)")

# ── CHECK 3: /api/cases pagination and /api/cases/{id} ───────────────────────
print("\nCHECK 3  /api/cases pagination + case detail")
page1 = get("/api/cases?page=1")
rows = page1.get("cases", [])
total = page1.get("total", 0)
print(f"  page1 rows={len(rows)}, total={total}")
if len(rows) != 25:
    failures.append(f"/api/cases page1 returned {len(rows)} rows (expected 25)")
if total != 150:
    failures.append(f"/api/cases total={total} (expected 150)")

case_id = rows[0]["id"] if rows else 1
detail = get(f"/api/cases/{case_id}")
precs = detail.get("precedents", [])
print(f"  /api/cases/{case_id}: precedents={len(precs)}")
if len(precs) < 5:
    failures.append(f"/api/cases/{case_id} returned {len(precs)} precedents (expected 5)")

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print()
conn.close()
if failures:
    print(f"FAILED — {len(failures)} issue(s):")
    for f in failures:
        print(f"  ✗ {f}")
    raise SystemExit(1)
else:
    print("All acceptance checks PASSED.")
