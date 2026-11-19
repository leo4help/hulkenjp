"""週報 v2：把上一週的 <週>/_data/ 推進一週（W46 起，2026-11-19 建立；W45 時這些 JSON 是臨時算的，沒有存腳本）。

輸入：
  <本週>/Hulken_Claude_Bridge_mcp.xlsx   build_mcp_bridge.py 的輸出（Meta／Google 媒體列＋KOL 授權金攤提列＋原廠標記）
  <本週>/_data/manual_inputs.json        非 MCP 來源：chatgpt、shopify（MCP 週加總）、funnel、rakuten_ads、
                                          rakuten_platform、amazon_platform、license_row_fix、name_alias
  amazon_data/Sponsored_Products_SearchTerm_<起>_<迄>.csv
  <上週>/_data/*.json                     8 週表、YTD、funnel、上週素材（當 WoW 基準）
輸出（<本週>/_data/）：groupA_weekly.json、groupBC_weekly.json、meta_creatives_w<NN>.json、kol_license_week.json、
  overview_ytd.json、groups_ytd.json、funnel_by_source.json、meta_ads_w<NN>.txt，並複製 early_metrics／amazon_platform_daily 等。
用法：python3 scripts/build_v2_week_data.py 2026W46 2026-11-12 2026W45
"""
import json, os, re, shutil, sys, datetime as dt
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from update_cache_incremental import enrich
import amazon_search_terms as amz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
folder, ws, prev = sys.argv[1], sys.argv[2], sys.argv[3]
wnum = int(folder[-2:]); W = f'W{wnum}'
we = (dt.date.fromisoformat(ws) + dt.timedelta(6)).isoformat()
D = os.path.join(ROOT, folder, '_data'); P = os.path.join(ROOT, prev, '_data')
M = json.load(open(os.path.join(D, 'manual_inputs.json'), encoding='utf-8'))
J = lambda p: json.load(open(p, encoding='utf-8'))
def dump(name, obj):
    json.dump(obj, open(os.path.join(D, name), 'w', encoding='utf-8'), ensure_ascii=False)

for f in os.listdir(P):  # 不變的原始檔照抄
    if f in ('early_metrics_w1_w37.json', 'rakuten_access_0413_0916.txt', 'amazon_platform_daily.json',
             'rakuten_rkarte_daily.txt', 'rakuten_ads_daily.json') and not os.path.exists(os.path.join(D, f)):
        shutil.copy(os.path.join(P, f), os.path.join(D, f))

d = pd.read_excel(os.path.join(ROOT, folder, 'Hulken_Claude_Bridge_mcp.xlsx'), sheet_name='Claude_Analysis_Data')
d = d[(d['分析報告開始'].astype(str) >= ws) & (d['分析報告開始'].astype(str) <= we)]
d = enrich(d)
num = lambda s: pd.to_numeric(s, errors='coerce').fillna(0)
for c in ['花費金額 (JPY)', '曝光次數', '連結點擊次數', '購買次數', '購買轉換值']:
    d[c] = num(d[c])
media = d[d.goal != '-']; lic = d[d.goal == '-']
def agg(x):
    return dict(cost=round(x['花費金額 (JPY)'].sum()), imp=int(x['曝光次數'].sum()), clicks=int(x['連結點擊次數'].sum()),
                conv=round(float(x['購買次數'].sum()), 2), rev=round(x['購買轉換值'].sum()))
meta = media[media.AD_Channel == 'Meta AD']; goog = media[media.AD_Channel == 'Google AD']
brand = goog['行銷活動名稱'].str.contains('包含品牌')
chA = {'Meta': agg(meta), 'Google 非品牌': agg(goog[~brand]), 'Google 品牌': agg(goog[brand]), 'ChatGPT': M['chatgpt']}
sh = M['shopify']
weekA = dict(week=W, start=ws, channels=chA, platform=dict(sales=sh['sales'], orders=sh['orders'], sessions=sh['sessions']))

# ---- KOL 授權金 ----
fix = M.get('license_row_fix', {})
def lic_row(n):
    n = str(n).rstrip('_')
    if n in fix: return fix[n]
    m = re.search(r'(\d+)$', n); return m.group(1) if m else None
lic = lic.assign(R=lic['廣告名稱'].apply(lic_row))
byRow = {str(k): round(v) for k, v in lic.groupby('R')['花費金額 (JPY)'].sum().items() if round(v)}
LIC = dict(total=round(lic['花費金額 (JPY)'].sum()), byRow=dict(sorted(byRow.items(), key=lambda kv: int(kv[0]))))

# ---- 素材 ----
alias = M.get('name_alias', {})
prevC = {c['row']: c for c in J(os.path.join(P, f'meta_creatives_w{int(prev[-2:])}.json'))}
mm = meta[meta.Row.notna()].copy()
mm['flag'] = mm.apply(lambda r: 'RT' if ('再入荷' in str(r['行銷活動名稱']) or '_D:RT' in str(r['行銷活動名稱'])) else ('T' if r.testFlag == 'TEST' else 'G'), axis=1)
mm['nm'] = mm['NameRow'].str.replace(r'^A:', '', regex=True).str.replace(r'-\d+$', '', regex=True)
CR, lines = [], []
for row, g in mm.groupby('Row'):
    a = agg(g); row = int(row)
    if not a['cost']: continue
    nm = g['nm'].mode()[0]; nm = alias.get(nm, nm)
    tags = g['原廠標記'].dropna(); tag = tags.mode()[0] if len(tags) else None
    if tag == 'KOL': tag = None
    pc = prevC.get(row)
    c = dict(row=row, name=nm, flags=sorted(g['flag'].unique().tolist()), cost=a['cost'], imp=a['imp'], clicks=a['clicks'],
             pur=int(round(a['conv'])), rev=a['rev'], kol=bool(g['isKOL'].any()), tag=tag, lic=byRow.get(str(row), 0),
             prev_cost=pc['cost'] if pc else None, prev_rev=pc['rev'] if pc else None, prev_imp=pc['imp'] if pc else None,
             prev_clicks=pc['clicks'] if pc else None, prev_pur=pc['pur'] if pc else None)
    CR.append(c)
    for _, r in g.groupby('廣告名稱'):
        x = agg(r); lines.append(f"{row}|{nm}|{c['flags'][0]}|{x['cost']}|{x['imp']}|{x['clicks']}|{int(round(x['conv']))}|{x['rev']}")
CR.sort(key=lambda c: -c['cost'])
dump(f'meta_creatives_w{wnum}.json', CR); dump('kol_license_week.json', LIC)
open(os.path.join(D, f'meta_ads_w{wnum}.txt'), 'w', encoding='utf-8').write('\n'.join(lines))

# ---- Amazon AD ----
t = amz.load(os.path.join(ROOT, 'amazon_data', f'Sponsored_Products_SearchTerm_{ws}_{we}.csv'))
amzAd = dict(cost=round(t.cost.sum()), imp=int(t.impr.sum()), clicks=int(t.clicks.sum()), conv=int(t.orders.sum()), rev=round(t.sales.sum()))
weekB = dict(week=W, channels=M['rakuten_ads'], platform=M['rakuten_platform'])
weekC = dict(week=W, channels={'Amazon AD': amzAd}, platform=M['amazon_platform'])

A8 = J(os.path.join(P, 'groupA_weekly.json'))[1:] + [weekA]
# ---- ChatGPT 廣告群組（W46 起）：本週＋上週重抓，上週 ChatGPT 渠道也改用重抓值（轉換會回補），表格才能展開且加總一致 ----
G_PREV_FIX = None
try:
    import openai_ads as oa
    ps = (dt.date.fromisoformat(ws) - dt.timedelta(7)).isoformat(); pe = (dt.date.fromisoformat(ws) - dt.timedelta(1)).isoformat()
    agc, agp = oa.ad_groups(ws, we), oa.ad_groups(ps, pe)
    if isinstance(agc, list) and isinstance(agp, list):
        dump('chatgpt_adgroups.json', dict(cur=agc, prv=agp))
        tot = lambda L: dict(cost=sum(x['cost'] for x in L), imp=sum(x['imp'] for x in L), clicks=sum(x['clicks'] for x in L), conv=sum(x['conv'] for x in L), rev=sum(x['rev'] for x in L))
        if agp:
            G_PREV_FIX = tot(agp); A8[-2]['channels']['ChatGPT'] = G_PREV_FIX
except Exception as e:
    print('ChatGPT ad groups skipped:', e)
BC = J(os.path.join(P, 'groupBC_weekly.json')); BC = dict(B=BC['B'][1:] + [weekB], C=BC['C'][1:] + [weekC])
dump('groupA_weekly.json', A8); dump('groupBC_weekly.json', BC)
spend = lambda ch: sum(v['cost'] for v in ch.values())
Y = [y for y in J(os.path.join(P, 'overview_ytd.json')) if y['week'] != W] + [dict(
    week=W, start=ws, shopify=sh['sales'], amazon=M['amazon_platform']['sales'], rakuten=M['rakuten_platform']['sales'],
    spendA=spend(chA), spendB=spend(M['rakuten_ads']), spendC=amzAd['cost'])]
dump('overview_ytd.json', Y)
G = J(os.path.join(P, 'groups_ytd.json'))
gA = dict(weekA, platform=dict(weekA['platform'], cart=sh['cart'], reach=sh['reach'], comp=sh['comp']))
if G_PREV_FIX:
    for x in G['A']:
        if x.get('start') == ps: x['channels']['ChatGPT'] = G_PREV_FIX
    for y in Y:
        if y['start'] == ps: y['spendA'] = sum(v['cost'] for v in A8[-2]['channels'].values())
    dump('overview_ytd.json', Y)
for k, v in (('A', gA), ('B', weekB), ('C', weekC)):
    G[k] = [x for x in G[k] if x.get('week') != W] + [v]
dump('groups_ytd.json', G)
F = J(os.path.join(P, 'funnel_by_source.json'))
for k in F: F[k] = F[k][:len(G['A']) - 1] + [M['funnel'][k]]
dump('funnel_by_source.json', F)
print('A', json.dumps(chA, ensure_ascii=False)); print('C', amzAd); print('LIC', LIC)
print('creatives', len(CR), 'sum', sum(c['cost'] for c in CR), 'meta', chA['Meta']['cost'])
print('YTD', Y[-1])
