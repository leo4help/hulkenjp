"""列出新憑證可存取的 Google Ads 帳戶底下所有子帳戶，找出 Hulken。
用法：GOOGLE_ADS_DEVELOPER_TOKEN=xxx ~/.venvs/ce-ads/bin/python scripts/test_ads_hierarchy.py
（沿用 test_google_credential.py 產生的 google_token.json，不需再登入）
"""
import os, requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

creds = Credentials.from_authorized_user_file("google_token.json")
if not creds.valid:
    creds.refresh(Request())
dev = os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]
H = {"Authorization": f"Bearer {creds.token}", "developer-token": dev}
TARGETS = {"4550430444"}  # Hulken JP

for v in range(26, 19, -1):
    r = requests.get(f"https://googleads.googleapis.com/v{v}/customers:listAccessibleCustomers", headers=H)
    if r.status_code != 404:
        break
print(f"API v{v}")
roots = [c.split("/")[1] for c in r.json()["resourceNames"]]
Q = ("SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, "
     "customer_client.level, customer_client.status FROM customer_client")
found = set()
for root in roots:
    r = requests.post(f"https://googleads.googleapis.com/v{v}/customers/{root}/googleAds:search",
                      headers={**H, "login-customer-id": root}, json={"query": Q})
    print(f"\n== {root} ==")
    if not r.ok:
        print("  ❌", r.text[:400]); continue
    for row in r.json().get("results", []):
        c = row["customerClient"]; cid = str(c["id"])
        mark = "  ⭐" if cid in TARGETS else "   "
        if cid in TARGETS: found.add(cid)
        print(f"{mark} {'  '*int(c.get('level',0))}{cid}  {c.get('descriptiveName','')}  "
              f"{'[MCC]' if c.get('manager') else ''} {c.get('status','')}")
print("\n" + (f"✅ 找到 Hulken 目標帳戶：{sorted(found)}" if found else "❌ 沒找到 8275284618 / 7841130682"))
