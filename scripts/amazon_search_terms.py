"""
Hulken JP — Amazon Sponsored Products search-term report helpers (added 2026-10-14, W41).

From W41 on the Weekly Report Manual sheet is no longer maintained; the Amazon
rows of the Overview·全渠道 table come straight from the weekly
"Sponsored_Products_SearchTerm_<start>_<end>.csv" export (one file per report
week, kept in amazon_data/ — gitignored raw data).

Classification (user's standing rules, don't re-ask):
  * ASIN target  = search term matches ^b0[a-z0-9]{8}$ (case-insensitive)
  * 品牌字        = non-ASIN term containing hulken / ハルケン / はるけん / フルケン / halken / 浩肯
  * 品牌ASIN      = ASIN in scripts/amazon_own_asins.json (case-insensitive)
  * 品牌 = 品牌字 + 品牌ASIN; 非品牌 = 非品牌字 + 非品牌ASIN (everything else)
Exclusion rule: cumulative cost > ¥5,000 with 0 orders, or > ¥10,000 with <= 1 order.

Known limitation: the console export is capped at the top 300 rows by cost, so
very small terms are missing (W41's 300th row is ~¥75). Totals matched the
old Weekly Report Manual Amazon rows exactly (W40 ¥17,932 / ¥116,401), so this
is the same basis the manual sheet always used.
"""
import glob, json, os, re
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND_RE = re.compile(r'(?i)hulken|ハルケン|はるけん|フルケン|halken|浩肯')
ASIN_RE = r'(?i)^b0[a-z0-9]{8}$'
COLS = ['term', 'match', 'impr', 'clicks', 'cost', 'orders', 'sales', 'roas']
FNAME_RE = re.compile(r'Sponsored_Products_SearchTerm_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.csv$')


def own_asins():
    with open(os.path.join(HERE, 'amazon_own_asins.json'), encoding='utf-8') as f:
        return {a.upper() for a in json.load(f)['asins']}


def load(path):
    a = pd.read_csv(path)
    if len(a.columns) != len(COLS):
        raise SystemExit(f"{path}: expected {len(COLS)} columns, got {list(a.columns)}")
    a.columns = COLS
    a['term'] = a['term'].astype(str)
    own = own_asins()
    is_asin = a['term'].str.match(ASIN_RE)
    is_own = a['term'].str.upper().isin(own)
    has_brand = a['term'].str.contains(BRAND_RE)
    a['seg'] = '非品牌字'
    a.loc[~is_asin & has_brand, 'seg'] = '品牌字'
    a.loc[is_asin & is_own, 'seg'] = '品牌ASIN'
    a.loc[is_asin & ~is_own, 'seg'] = '非品牌ASIN'
    a['side'] = a['seg'].map(lambda s: '品牌' if s.startswith('品牌') else '非品牌')
    a['isAsin'] = is_asin
    return a


def find_week_file(folder, start, end):
    p = os.path.join(folder, f'Sponsored_Products_SearchTerm_{start:%Y-%m-%d}_{end:%Y-%m-%d}.csv')
    return p if os.path.exists(p) else None


def manual_rows(path, week_start):
    """Two Weekly-Report-Manual-shaped rows (品牌 / 非品牌) for one week's file."""
    a = load(path)
    out = []
    for side in ['非品牌', '品牌']:
        s = a[a['side'] == side]
        out.append({'Week_1st_day': pd.Timestamp(week_start), 'Channel': 'Amazon', 'AD Type': side,
                    'Cost': s['cost'].sum(), 'Impression': s['impr'].sum(), 'Click': s['clicks'].sum(),
                    'Purchase': s['orders'].sum(), 'Purchase Value': s['sales'].sum()})
    return out


def history(folder, upto_end=None):
    """All weekly files in folder (optionally only weeks ending <= upto_end), tagged with week start."""
    frames = []
    for p in sorted(glob.glob(os.path.join(folder, 'Sponsored_Products_SearchTerm_*.csv'))):
        m = FNAME_RE.search(os.path.basename(p))
        if not m:
            continue
        s, e = pd.Timestamp(m.group(1)), pd.Timestamp(m.group(2))
        if upto_end is not None and e > pd.Timestamp(upto_end):
            continue
        a = load(p)
        a['week'] = s
        frames.append(a)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def exclusion_candidates(hist, cur_week):
    """Cumulative (all weeks in hist) per term; flag per the standing rule and
    say whether spend is still growing this week."""
    g = hist.groupby(['term', 'seg', 'isAsin']).agg(cost=('cost', 'sum'), orders=('orders', 'sum'),
                                                       weeks=('week', 'nunique')).reset_index()
    cur = hist[hist['week'] == pd.Timestamp(cur_week)].groupby('term')['cost'].sum()
    g['curCost'] = g['term'].map(cur).fillna(0)
    flag = ((g['cost'] > 5000) & (g['orders'] == 0)) | ((g['cost'] > 10000) & (g['orders'] <= 1))
    g = g[flag & g['seg'].str.startswith('非品牌')].copy()
    g['action'] = g['isAsin'].map({True: '排除產品', False: '排除關鍵字'})
    return g.sort_values('cost', ascending=False)
