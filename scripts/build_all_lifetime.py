"""
scripts/build_all_lifetime.py
==============================
Refreshes all.html's Step 6 (per CLAUDE.md's weekly workflow): the
`kolLifetimeRows` const plus the `lastUpdatedChip` / `calcAsofText` date
chips. This is the successor to the never-saved `compute_all_lifetime.py`
(see CLAUDE.md's "Open items" -- that script was written once in a prior
session, run from scratch memory, and lost; this file is the permanent
replacement so it never has to be reconstructed again).

`kolLifetimeRows` = full lifetime (no date window), Meta AD only, ALL
creatives (KOL + house/原廠), one row per NameRow, media spend and KOL
license spend tracked separately (`mediaCost` vs `lic`; `cost` = the sum).
`cpm` uses `mediaCost` only (matches the weekly report's per-row cpm, which
is also media-only by construction), NOT cost-incl-license.

USAGE

    python3 scripts/build_all_lifetime.py \\
        --cache _cache/ad_data_historical_cache.pkl.gz \\
        --bridge 2026W38/Hulken_Claude_Bridge.xlsx \\
        --bridge-cutoff 2026-09-17 \\
        --all-html all.html \\
        --updated-date 2026-09-23 --week-label W38

`--bridge-cutoff` should match the historical cache's current cutoff date
(check _cache/ad_data_cache_meta.json) -- only Bridge rows on/after that
date are appended, to avoid double-counting rows the cache already has.
Run scripts/update_cache_incremental.py FIRST so the cache is current
through last week; this script then adds just this week's window on top.

`--updated-date` drives both the "最後更新" chip and "本頁鎖定至...為止的
累積數據" text; it should be this week's Week_1st_day/end date, whichever
convention CLAUDE.md's Step 6 currently specifies (as of W37: the week-end
date, formatted YYYY/MM/DD).
"""
import argparse
import json
import re

import pandas as pd

NAME_ALIASES = {
    'A:原廠-Wakazo-25A:原廠-Wakazo': 'A:原廠-Wakazo-25',
    'A:KOL-marika.oka-154': 'A:KOL-marika-oka-154',
}

COST = '花費金額 (JPY)'
PURCH = '購買次數'
REV = '購買轉換值'
CLICKS = '連結點擊次數'
IMPR = '曝光次數'
CAMPAIGN = '行銷活動名稱'
ADNAME = '廣告名稱'
TAG = '原廠標記'
DATE = '分析報告開始'


def goal(campaign):
    if pd.isna(campaign):
        return '-'
    c = str(campaign).lower()
    if re.search(r'pmax|shopping-ad', c):
        return 'CPA'
    m = re.search(r'C:([^_]+)', str(campaign))
    return m.group(1) if m else '-'


def ad_channel(campaign):
    c = str(campaign).lower() if not pd.isna(campaign) else ''
    if re.search(r'pmax|search|shopping-ad', c):
        return 'Google AD'
    return 'Meta AD'


def name_row(name):
    if pd.isna(name):
        return None
    name = str(name)
    if 'R:' in name:
        a = re.search(r'(A:[^_]+)', name)
        r = re.search(r'R:([^_]+)', name)
        return (a.group(1) if a else '') + '-' + (r.group(1) if r else '')
    a = re.search(r'(A:[^_]+)', name)
    return a.group(1) if a else None


def is_kol(nr):
    return bool(re.match(r'(?i)^A:KOL[\s-]', str(nr))) if isinstance(nr, str) else False


def enrich(df):
    df = df.copy()
    df['goal'] = df[CAMPAIGN].apply(goal)
    df['AD_Channel'] = df[CAMPAIGN].apply(ad_channel)
    df['NameRow'] = df[ADNAME].apply(name_row)
    df['NameRow'] = df['NameRow'].replace(NAME_ALIASES)
    df['isKOL'] = df['NameRow'].apply(is_kol)
    return df


def safe_div(a, b):
    if b is None or b == 0 or pd.isna(b):
        return None
    return a / b


def r2(x, nd=2):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    return round(float(x), nd)


def compute_lifetime_rows(cache_path, bridge_path, bridge_cutoff):
    cache = pd.read_pickle(cache_path, compression='gzip')
    cache = cache.copy()
    cache['NameRow'] = cache['NameRow'].replace(NAME_ALIASES)

    frames = [cache]
    if bridge_path:
        bridge = pd.read_excel(bridge_path, sheet_name='Claude_Analysis_Data')
        bridge_enriched = enrich(bridge)
        bridge_slice = bridge_enriched[bridge_enriched[DATE] >= pd.Timestamp(bridge_cutoff)]
        common = [c for c in cache.columns if c in bridge_slice.columns]
        frames = [cache[common], bridge_slice[common]]

    ad = pd.concat(frames, ignore_index=True).drop_duplicates()

    meta = ad[ad['AD_Channel'] == 'Meta AD']
    media = meta[~meta['goal'].isin(['-', 'CPC'])]
    lic = meta[(meta['goal'] == '-') & (meta['isKOL'])]

    media_g = media.groupby('NameRow').agg(
        mediaCost=(COST, 'sum'), revenue=(REV, 'sum'), clicks=(CLICKS, 'sum'),
        impressions=(IMPR, 'sum'), purchases=(PURCH, 'sum'),
    )
    lic_g = lic.groupby('NameRow')[COST].sum()

    all_nr = sorted(set(media_g.index) | set(lic_g.index))
    rows = []
    for nr in all_nr:
        if nr is None or not isinstance(nr, str):
            continue
        m = media_g.loc[nr] if nr in media_g.index else None
        mediaCost = float(m['mediaCost']) if m is not None else 0.0
        revenue = float(m['revenue']) if m is not None else 0.0
        clicks = float(m['clicks']) if m is not None else 0.0
        impressions = float(m['impressions']) if m is not None else 0.0
        purchases = float(m['purchases']) if m is not None else 0.0
        licv = float(lic_g.get(nr, 0.0))
        cost = mediaCost + licv
        isKOL = is_kol(nr)
        sub_media = media[media['NameRow'] == nr]
        sub_lic = lic[lic['NameRow'] == nr]
        tag_vals = pd.concat([sub_media[TAG], sub_lic[TAG]]).dropna()
        tag = tag_vals.mode().iloc[0] if len(tag_vals) else None
        rows.append({
            'name': nr, 'isKOL': isKOL, 'tag': tag,
            'mediaCost': r2(mediaCost, 1), 'lic': r2(licv, 1), 'revenue': r2(revenue, 1),
            'clicks': r2(clicks, 1), 'impressions': r2(impressions, 1), 'purchases': r2(purchases, 1),
            'cost': r2(cost, 1),
            'cpa': r2(safe_div(cost, purchases)),
            'roas': r2(safe_div(revenue, cost)),
            'mediaRoas': r2(safe_div(revenue, mediaCost)),
            'ctr': r2(safe_div(clicks, impressions) * 100 if safe_div(clicks, impressions) is not None else None),
            'cvr': r2(safe_div(purchases, clicks) * 100 if safe_div(purchases, clicks) is not None else None),
            'cpm': r2(safe_div(mediaCost, impressions) * 1000 if safe_div(mediaCost, impressions) is not None else None),
        })
    return rows


def update_all_html(all_html_path, rows, updated_date, week_label, out_path):
    with open(all_html_path, encoding='utf-8') as f:
        html = f.read()

    pattern = re.compile(r"(const kolLifetimeRows = )(\[.*?\])(;)", re.S)
    new_html, n = pattern.subn(lambda m: m.group(1) + json.dumps(rows, ensure_ascii=False) + m.group(3), html, count=1)
    if n != 1:
        raise SystemExit(f"failed to substitute kolLifetimeRows (found {n} matches, expected 1)")
    html = new_html

    disp = updated_date.strftime('%Y/%m/%d')
    html, n1 = re.subn(
        r'(<div class="meta-chip" id="lastUpdatedChip">最後更新：)\d{4}/\d{2}/\d{2}（W\d+ 資料）(</div>)',
        lambda m: m.group(1) + f"{disp}（{week_label} 資料）" + m.group(2), html, count=1)
    if n1 != 1:
        raise SystemExit(f"lastUpdatedChip substitution matched {n1} times, expected 1")

    html, n2 = re.subn(
        r'(本頁鎖定至 <b id="calcAsofText">)\d{4}/\d{2}/\d{2}(</b> 為止的累積數據)',
        lambda m: m.group(1) + disp + m.group(2), html, count=1)
    if n2 != 1:
        raise SystemExit(f"calcAsofText substitution matched {n2} times, expected 1")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return len(html)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cache', default='_cache/ad_data_historical_cache.pkl.gz')
    ap.add_argument('--bridge', default=None, help="this week's Bridge xlsx, needed if the cache doesn't cover this week's window yet")
    ap.add_argument('--bridge-cutoff', default=None, help='only take Bridge rows on/after this date (should match the cache cutoff); required if --bridge is given')
    ap.add_argument('--all-html', default='all.html')
    ap.add_argument('--out', default=None, help='defaults to overwriting --all-html in place')
    ap.add_argument('--updated-date', required=True, help='YYYY-MM-DD, drives lastUpdatedChip / calcAsofText')
    ap.add_argument('--week-label', required=True, help='e.g. W38, shown in lastUpdatedChip')
    args = ap.parse_args()

    if args.bridge and not args.bridge_cutoff:
        raise SystemExit('--bridge-cutoff is required when --bridge is given')

    rows = compute_lifetime_rows(args.cache, args.bridge, args.bridge_cutoff)
    print('rows:', len(rows))
    print('KOL rows:', sum(1 for r in rows if r['isKOL']))
    print('non-KOL rows:', sum(1 for r in rows if not r['isKOL']))

    out_path = args.out or args.all_html
    n_bytes = update_all_html(args.all_html, rows, pd.Timestamp(args.updated_date), args.week_label, out_path)
    print(f"wrote {out_path} ({n_bytes} bytes)")


if __name__ == '__main__':
    main()
