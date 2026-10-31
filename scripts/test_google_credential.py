"""測試新 Google OAuth 憑證能否存取 Hulken 的 GA4 / Search Console / Google Ads。
用法（在 Mac 終端機、專案資料夾內執行）：
  pip3 install google-auth-oauthlib requests
  GOOGLE_ADS_DEVELOPER_TOKEN=你的token python3 scripts/test_google_credential.py
第一次會開瀏覽器請你登入要授權的 Google 帳號。token 存在 google_token.json（已加入 .gitignore）。
"""
import glob, json, os, sys
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/adwords",
]
GA_PROPERTY = "518548798"          # HULKEN Japan Shopify
GSC_SITE = "https://hulken.co.jp/"
ADS_IDS = {"4550430444"}  # Hulken JP（MCC 9497270521 底下）
TOKEN = "google_token.json"

secret = glob.glob("client_secret_*.json")[0]
creds = Credentials.from_authorized_user_file(TOKEN, SCOPES) if os.path.exists(TOKEN) else None
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        creds = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
    open(TOKEN, "w").write(creds.to_json())
H = {"Authorization": f"Bearer {creds.token}"}

def show(name, ok, detail):
    print(f"{'✅' if ok else '❌'} {name}: {detail}")

# GA4
r = requests.get("https://analyticsadmin.googleapis.com/v1beta/accountSummaries?pageSize=200", headers=H)
props = [p["property"] for a in r.json().get("accountSummaries", []) for p in a.get("propertySummaries", [])] if r.ok else []
show("GA4 property 518548798", f"properties/{GA_PROPERTY}" in props,
     f"可見 {len(props)} 個 property" if r.ok else r.text[:300])

# Search Console
r = requests.get("https://www.googleapis.com/webmasters/v3/sites", headers=H)
sites = {s["siteUrl"]: s["permissionLevel"] for s in r.json().get("siteEntry", [])} if r.ok else {}
show("Search Console hulken.co.jp", GSC_SITE in sites or "sc-domain:hulken.co.jp" in sites,
     sites.get(GSC_SITE) or sites.get("sc-domain:hulken.co.jp") or (r.text[:300] if not r.ok else f"可見網站：{list(sites)}"))

# Google Ads
dev = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
if not dev:
    show("Google Ads", False, "未設定 GOOGLE_ADS_DEVELOPER_TOKEN，略過（API 一定要 developer token）")
else:
    for v in range(26, 19, -1):  # 自動找目前還在服務的 API 版本
        r = requests.get(f"https://googleads.googleapis.com/v{v}/customers:listAccessibleCustomers",
                         headers={**H, "developer-token": dev})
        if r.status_code != 404:
            break
    ids = {c.split("/")[1] for c in r.json().get("resourceNames", [])} if r.ok else set()
    hit = ids & ADS_IDS
    show("Google Ads", bool(hit), f"直接可存取的帳戶：{sorted(ids)}" if r.ok else r.text[:400])
    if r.ok and not hit:
        print("   ↳ 若 Hulken 帳戶在 MCC 底下，直接清單不會列出它；請告訴我 MCC ID 再測。")
