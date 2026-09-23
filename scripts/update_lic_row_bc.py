"""
scripts/update_lic_row_bc.py
============================
Refreshes all.html's `LIC_ROW_DATA` spend-derived fields for the KOL
license-fee negotiation calculator (CLAUDE.md Step 6.2):

    B, C, activeDays, windowCost, windowRev, firstActive, lastActive,
    usedAllTime  (+ name / isKOL for newly-added Rows)

`firstWave` is NOT touched here -- that comes from the KOL授權金 Bridge tab
via scripts/update_kol_license_calc.py. Run THIS script first, then
update_kol_license_calc.py, so newly-added Rows also get their firstWave.

Added 2026-09-23 (W38). Before this, B/C had never been scripted and had
silently stayed frozen at the W33 build (lastActive 2026-08-19 everywhere).

METHODOLOGY (window definition confirmed by the user 2026-09-23 -- the Row's
LAST 14 SPEND DAYS; revised the same day from a 28-day draft, then lifetime):

- DEFAULT window = per Row, the most recent 14 days WITH SPEND > 0 up to
  --end-date (not 14 calendar days). The window therefore stretches back
  as far as needed for each Row, so a Row that paused recently still gets
  B/C from its last 14 active days instead of coming up empty. A Row with
  fewer than 14 spend days in total uses all of them (usedAllTime = True).
  Controlled by --last-spend-days N (default 14; 0 disables it).

Alternative modes kept as options (not the default):
- Scope: Meta AD media rows (goal not in ['-','CPC']) with a numeric Row,
  over the combined historical cache + this week's Bridge slice (same
  combine logic as build_weekly_report.py). All Meta creative Rows are kept
  (KOL and 原廠) -- the calculator itself rejects isKOL == False lookups.
- --last-spend-days 0 --window-days 0 = LIFETIME: every day from the Row's first spend up to
  --end-date (the report week's end date), inclusive. The historical cache
  + Bridge together cover the full history, so no full Mastersheet needed.
  (Optional --window-days N switches to "last N calendar days ending on
  --end-date" instead, with the lifetime fallback below.)
- activeDays = number of days inside the window with spend > 0.
- windowCost / windowRev = media spend / purchase value summed inside the
  window (media only, no license fee).
- B = windowCost / activeDays  (日均花費, rounded to int)
- C = windowRev / windowCost   (媒體單獨 ROAS, 2 dp)
- firstActive / lastActive = first / last spend day inside the window.
- usedAllTime = True for lifetime (the calculator shows a 全期間數據
  badge). With --window-days N, a Row with no spend inside the window falls
  back to lifetime (usedAllTime = True). No spend at all -> B/C = null.

USAGE
    python3 scripts/update_lic_row_bc.py \
        --cache _cache/ad_data_historical_cache.pkl.gz \
        --bridge 2026W38/Hulken_Claude_Bridge.xlsx --bridge-cutoff 2026-09-17 \
        --end-date 2026-09-23 --all-html all.html --out all.html
"""
import argparse, json, re, sys, os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_weekly_report import enrich, NAME_ALIASES, DATE, COST, REV  # noqa: E402


def load_ad(cache_path, bridge_path, bridge_cutoff):
    cache = pd.read_pickle(cache_path, compression='gzip')
    cache['NameRow'] = cache['NameRow'].replace(NAME_ALIASES)
    frames = [cache]
    if bridge_path:
        b = enrich(pd.read_excel(bridge_path, sheet_name='Claude_Analysis_Data'))
        b = b[b[DATE] >= pd.Timestamp(bridge_cutoff)]
        common = [c for c in cache.columns if c in b.columns]
        frames = [cache[common], b[common]]
    ad = pd.concat(frames, ignore_index=True).drop_duplicates()
    ad[DATE] = pd.to_datetime(ad[DATE])
    return ad


def display_name(namerow):
    s = re.sub(r'-\d+$', '', str(namerow))
    s = re.sub(r'(?i)^A:KOL[\s-]', '', s)
    s = re.sub(r'^A:', '', s)
    return s.strip('-').strip()


def stats(sub, last_n=0):
    daily = sub.groupby(sub[DATE].dt.normalize()).agg(cost=(COST, 'sum'), rev=(REV, 'sum'))
    daily = daily[daily['cost'] > 0].sort_index()
    if last_n > 0:
        daily = daily.tail(last_n)
    if daily.empty:
        return None
    cost, rev, days = float(daily['cost'].sum()), float(daily['rev'].sum()), int(len(daily))
    return dict(B=int(round(cost / days)), C=round(rev / cost, 2), activeDays=days,
                windowCost=round(cost, 1), windowRev=round(rev, 1),
                firstActive=str(daily.index.min().date()), lastActive=str(daily.index.max().date()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True)
    ap.add_argument('--bridge')
    ap.add_argument('--bridge-cutoff')
    ap.add_argument('--end-date', required=True)
    ap.add_argument('--last-spend-days', type=int, default=14,
                    help='per Row, use its most recent N days with spend (default 14; 0 = off)')
    ap.add_argument('--window-days', type=int, default=0,
                    help='0 (default) = lifetime up to --end-date; N = last N days')
    ap.add_argument('--all-html', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    end = pd.Timestamp(a.end_date)
    start = end - pd.Timedelta(days=a.window_days - 1) if a.window_days > 0 else None
    ad = load_ad(a.cache, a.bridge, a.bridge_cutoff)
    med = ad[(ad['AD_Channel'] == 'Meta AD') & (~ad['goal'].isin(['-', 'CPC'])) & (ad[DATE] <= end)].copy()
    med['RowS'] = pd.to_numeric(med['Row'], errors='coerce')
    med = med[med['RowS'].notna()]
    med['RowS'] = med['RowS'].astype(int).astype(str)

    html = open(a.all_html, encoding='utf-8').read()
    m = re.search(r'const LIC_ROW_DATA = (\{.*?\});\n', html, re.S)
    if not m:
        raise SystemExit('LIC_ROW_DATA not found in ' + a.all_html)
    L = json.loads(m.group(1))

    added, recent, alltime, nodata = [], 0, 0, 0
    for r, sub in med.groupby('RowS'):
        entry = L.get(r)
        if entry is None:
            if sub[COST].sum() <= 0:
                continue
            nr = sub['NameRow'].mode().iloc[0]
            entry = dict(name=display_name(nr), isKOL=bool(sub['isKOL'].mode().iloc[0]))
            L[r] = entry
            added.append(r)
        if a.last_spend_days > 0:
            st = stats(sub, a.last_spend_days)
            if st is None:
                entry.update(B=None, C=None, activeDays=0, windowCost=0.0, windowRev=0.0, usedAllTime=True)
                nodata += 1
                continue
            used_all = st['activeDays'] < a.last_spend_days
            entry.update(st, usedAllTime=used_all)
            alltime += used_all
            recent += not used_all
            continue
        st = stats(sub[sub[DATE] >= start]) if start is not None else None
        used_all = False
        if st is None:
            st = stats(sub)
            used_all = True
        if st is None:
            entry.update(B=None, C=None, activeDays=0, windowCost=0.0, windowRev=0.0, usedAllTime=True)
            nodata += 1
            continue
        entry.update(st, usedAllTime=used_all)
        alltime += used_all
        recent += not used_all

    L = {k: L[k] for k in sorted(L, key=lambda k: int(k))}
    html = html[:m.start(1)] + json.dumps(L, ensure_ascii=False) + html[m.end(1):]
    # keep the badge label in sync with the window length
    if a.last_spend_days > 0:
        html = re.sub(r'近\d+(?:天|個投放日)數據', f'近{a.last_spend_days}個投放日數據', html)
    elif a.window_days > 0:
        html = re.sub(r'近\d+(?:天|個投放日)數據', f'近{a.window_days}天數據', html)
    open(a.out, 'w', encoding='utf-8').write(html)
    win = (f'last {a.last_spend_days} spend days per Row, up to {end.date()}' if a.last_spend_days > 0 else
           f'{start.date()} ~ {end.date()} ({a.window_days}d)' if start is not None else f'lifetime ~ {end.date()}')
    print(f'window {win}: {recent} Rows full window, '
          f'{alltime} used all-time (short history / fallback), {nodata} with no spend; added {len(added)} new Rows: {added}')


if __name__ == '__main__':
    main()
