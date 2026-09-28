import requests
import json
import time

time.sleep(1)
test_fir = (
    "The accused broke into the shop at night, assaulted the security guard with an iron rod "
    "causing head injuries, snatched the cash box with Rs 25,000, smashed the glass counters, "
    "and threatened to shoot anyone who tried to stop them."
)

print("=== 1. Direct Test (bns-backend :8001/predict) ===")
r1 = requests.post("http://localhost:8001/predict", json={"facts": test_fir, "threshold": 0.35}, timeout=10)
print("HTTP Status:", r1.status_code)
d1 = r1.json()
print("Crime Type:", d1.get("crime_type"))
print("Total Applicable Sections:", d1.get("total_sections"))
for s in d1.get("bns", [])[:6]:
    print(f" -> BNS {s['section_id']}: {s['title']} | Confidence: {s['confidence_percent']}")
    print(f"    Rationale: {s['explanation']}")

print("\n=== 2. Proxy Test (main backend :8000/bns/predict) ===")
try:
    r2 = requests.post("http://localhost:8000/bns/predict", json={"fir_text": test_fir, "threshold": 0.35}, timeout=10)
    print("HTTP Status:", r2.status_code)
    d2 = r2.json()
    print("Proxy Total Applicable Sections:", d2.get("total_sections"))
    for s in d2.get("bns", [])[:6]:
        print(f" -> BNS {s['section_id']}: {s['title']} | Confidence: {s['confidence_percent']}")
except Exception as e:
    print("Backend proxy error:", e)
