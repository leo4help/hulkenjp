#!/usr/bin/env python3
"""Amazon Ads API（JP＝Far East region）唯讀工具。金鑰在 .secrets/amazon_ads.env（gitignored，絕不印出、絕不 commit）。

.secrets/amazon_ads.env 由使用者自己填：
  AMAZON_ADS_CLIENT_ID=amzn1.application-oa2-client.xxxx
  AMAZON_ADS_CLIENT_SECRET=xxxx
  AMAZON_ADS_REDIRECT_URI=https://localhost
  （exchange 成功後腳本自動寫入 AMAZON_ADS_REFRESH_TOKEN、選定 profile 後寫入 AMAZON_ADS_PROFILE_ID）

用法
  python3 scripts/amazon_ads_api.py auth-url              # 印出授權網址（只含 client_id，不含密鑰）
  python3 scripts/amazon_ads_api.py exchange <code>       # 用授權碼換 refresh token，存進 .secrets（不印出）
  python3 scripts/amazon_ads_api.py profiles              # 列出廣告帳戶 profile（JP 店選一個存起來）
  python3 scripts/amazon_ads_api.py use-profile <id>
  python3 scripts/amazon_ads_api.py sp-searchterm 2026-11-19 2026-11-25 [--out file.json] [--csv amazon_data/Sponsored_Products_SearchTerm_<起>_<迄>.csv]
  python3 scripts/amazon_ads_api.py download <reportId> [--out ...] [--csv ...]
需要組織網路允許清單：api.amazon.co.jp、advertising-api-fe.amazon.com，以及報表下載用的 S3 網域。
"""
import json, os, sys, time, gzip, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(ROOT, '.secrets', 'amazon_ads.env')
AUTH = 'https://apac.account.amazon.com/ap/oa'
TOKEN = 'https://api.amazon.co.jp/auth/o2/token'
API = 'https://advertising-api-fe.amazon.com'
UA = {'User-Agent': 'hulken-weekly-report/1.0'}


def env():
    e = {}
    for l in open(ENV, encoding='utf-8'):
        if '=' in l and not l.strip().startswith('#'):
            k, v = l.strip().split('=', 1); e[k] = v
    return e


def set_env(key, val):
    lines = [l for l in open(ENV, encoding='utf-8').read().splitlines() if not l.startswith(key + '=')]
    lines.append(f'{key}={val}')
    open(ENV, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    os.chmod(ENV, 0o600)


def req(url, data=None, headers=None, method=None):
    h = dict(UA); h.update(headers or {})
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read()


def token_call(form):
    st, body = req(TOKEN, urllib.parse.urlencode(form).encode(), {'Content-Type': 'application/x-www-form-urlencoded'})
    j = json.loads(body or b'{}')
    if st != 200:
        sys.exit(f'token error {st}: {j.get("error")} {j.get("error_description","")}')
    return j


def access_token(e):
    return token_call(dict(grant_type='refresh_token', refresh_token=e['AMAZON_ADS_REFRESH_TOKEN'],
                           client_id=e['AMAZON_ADS_CLIENT_ID'], client_secret=e['AMAZON_ADS_CLIENT_SECRET']))['access_token']


def api(e, path, data=None, ctype='application/json', method=None, scope=True):
    h = {'Amazon-Advertising-API-ClientId': e['AMAZON_ADS_CLIENT_ID'], 'Authorization': 'Bearer ' + access_token(e)}
    if scope:
        h['Amazon-Advertising-API-Scope'] = e['AMAZON_ADS_PROFILE_ID']
    if data is not None:
        h['Content-Type'] = ctype
    st, body = req(API + path, None if data is None else json.dumps(data).encode(), h, method)
    return st, (json.loads(body) if body else None)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    e = env()
    if cmd == 'auth-url':
        q = dict(client_id=e['AMAZON_ADS_CLIENT_ID'], scope='advertising::campaign_management', response_type='code',
                 redirect_uri=e['AMAZON_ADS_REDIRECT_URI'])
        print(AUTH + '?' + urllib.parse.urlencode(q))
    elif cmd == 'exchange':
        j = token_call(dict(grant_type='authorization_code', code=sys.argv[2], redirect_uri=e['AMAZON_ADS_REDIRECT_URI'],
                            client_id=e['AMAZON_ADS_CLIENT_ID'], client_secret=e['AMAZON_ADS_CLIENT_SECRET']))
        set_env('AMAZON_ADS_REFRESH_TOKEN', j['refresh_token'])
        print('refresh token saved to .secrets/amazon_ads.env (not printed)')
    elif cmd == 'profiles':
        st, j = api(e, '/v2/profiles', scope=False)
        if st != 200:
            sys.exit(f'profiles error {st}: {j}')
        for p in j:
            a = p.get('accountInfo', {})
            print(p['profileId'], p.get('countryCode'), p.get('currencyCode'), a.get('type'), a.get('name'))
    elif cmd == 'use-profile':
        set_env('AMAZON_ADS_PROFILE_ID', sys.argv[2]); print('profile saved')
    elif cmd == 'sp-searchterm':
        d1, d2 = sys.argv[2], sys.argv[3]
        out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None
        body = {'name': f'SP searchterm {d1}~{d2}', 'startDate': d1, 'endDate': d2, 'configuration': {
            'adProduct': 'SPONSORED_PRODUCTS', 'groupBy': ['searchTerm'], 'reportTypeId': 'spSearchTerm',
            'timeUnit': 'SUMMARY', 'format': 'GZIP_JSON',
            'columns': ['campaignName', 'adGroupName', 'searchTerm', 'targeting', 'matchType', 'impressions', 'clicks',
                        'cost', 'purchases7d', 'sales7d', 'unitsSoldClicks7d']}}
        st, j = api(e, '/reporting/reports', body, 'application/vnd.createasyncreportrequest.v3+json', 'POST')
        if st not in (200, 202):
            sys.exit(f'create report error {st}: {j}')
        rid = j['reportId']
        print('reportId', rid, flush=True)
        fetch_report(e, rid, out)
    elif cmd == 'download':          # 重新下載既有報表：download <reportId> [--out file]
        out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None
        fetch_report(e, sys.argv[2], out)
    else:
        print(__doc__)


def to_csv(rows, path):
    """API 報表 → 與瀏覽器匯出同格式的 CSV（8 欄），讓 amazon_search_terms.py 照舊讀。依 (搜尋字詞, targeting) 加總。"""
    import csv
    agg = {}
    for r in rows:
        k = (r.get('searchTerm') or '', r.get('targeting') or '')
        a = agg.setdefault(k, [0, 0, 0.0, 0, 0.0])
        a[0] += int(r.get('impressions') or 0); a[1] += int(r.get('clicks') or 0); a[2] += float(r.get('cost') or 0)
        a[3] += int(r.get('purchases7d') or 0); a[4] += float(r.get('sales7d') or 0)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Customer search term', 'Keywords', 'Impressions', 'Clicks', 'Total cost (JPY)', 'Purchases', 'Sales (JPY)', 'ROAS'])
        for (term, tg), (im, cl, co, pu, sa) in sorted(agg.items(), key=lambda x: -x[1][2]):
            w.writerow([term, tg, im, cl, round(co, 2), pu, round(sa), round(sa / co, 2) if co else 0])


def fetch_report(e, rid, out):
    if True:
        for _ in range(60):
            time.sleep(10)
            st, j = api(e, f'/reporting/reports/{rid}')
            if j.get('status') == 'COMPLETED':
                break
            if j.get('status') == 'FAILED':
                sys.exit(f'report failed: {j.get("failureReason")}')
        else:
            sys.exit('report not ready after 10 min; reportId=' + rid)
        try:
            st, raw = req(j['url'])
        except urllib.error.URLError as ex:
            sys.exit(f'download blocked: host={urllib.parse.urlparse(j["url"]).hostname} ({ex.reason}); reportId={rid}')
        rows = json.loads(gzip.decompress(raw))
        if out:
            json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
        if '--csv' in sys.argv:
            to_csv(rows, sys.argv[sys.argv.index('--csv') + 1])
        tot = {k: sum(float(r.get(k) or 0) for r in rows) for k in ('impressions', 'clicks', 'cost', 'purchases7d', 'sales7d')}
        print(len(rows), 'rows', json.dumps(tot))


if __name__ == '__main__':
    main()
