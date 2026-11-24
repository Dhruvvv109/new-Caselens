import http.client, json
conn = http.client.HTTPConnection("127.0.0.1", 8000)
conn.request("GET", "/api/cases")
r = conn.getresponse()
body = json.loads(r.read())
for c in body["cases"]:
    pf = c["precedent_features"]
    p = c["prediction"]
    top1 = pf["top1_similarity"]
    mean5 = pf["mean_top5_similarity"]
    cnt = pf["count_matches_above_threshold"]
    days = p["predicted_days"]
    print(f"{c['case_no']}: top1={top1:.3f} mean5={mean5:.3f} cnt={cnt} pred={days}d")
conn.close()
