"""
scripts/build_weekly_report.py
================================
Builds the HULKEN JP weekly ad-performance report end-to-end: computes every
data const the report HTML needs (kpis / channelRows / channelGrand /
brandSplit / testSplit / metaTestRows / metaTestKol / metaCreative /
metaCreativeTotal / kolRows / kolGrand) from the historical cache + this
week's Bridge file, then clones the previous week's report HTML and
substitutes in the new week's numbers and labels.

This replaces the "reverse-engineer everything from scratch, validate by
diffing against last week's HTML" process that ate ~30 min of the W37 build.
Run this script with next week's dates and it should be a 1-2 minute job
(plus a quick visual sanity check of the output).

--------------------------------------------------------------------------
METHODOLOGY (see CLAUDE.md for the full narrative write-up; this is the
condensed reference used by the code below):

- `ad_data` scope = Meta_data + Google_data(x2) + KOL_cost_data from the
  Bridge / historical cache. NEVER Amazon/Rakuten.
- Derived columns per row: goal, AD_Channel, NameRow, Row, isKOL, testFlag
  (see `enrich()` -- ported from scripts/update_cache_incremental.py, kept
  in sync with it deliberately; if that file's enrich() logic changes,
  mirror the change here).
- CPM is ALWAYS cost/impressions*1000 (JPY per 1000 impressions) -- easy to
  forget the x1000, double check any new metric that touches CPM.
- Two genuinely different KPI scopes in the report, do not conflate them:
    1. The 6 hero `kpis` tiles: ad_data (Meta+Google combined),
       goal not in ['-','CPC'].
    2. `channelRows` / `channelGrand` (Overview - all-channel table): the
       manually maintained "Weekly Report Manual" sheet, which is the ONLY
       place Amazon/Rakuten numbers come from.
- `metaTestKol` = ALL Meta creatives (KOL + house/原廠) with testFlag=='TEST'.
  Name is historical, it is NOT KOL-only.
- KOL "license ghost rows": rows with goal=='-' and NameRow matching the KOL
  regex represent amortized KOL license fees. These come ONLY from these
  ghost rows in ad_data, never from the separate `KOL授權金` Bridge tab
  (that tab feeds ONLY all.html's negotiation-calculator firstWave value).
- `kolRows` / `kolGrand`: grouped by isKOL only (not testFlag). Population =
  union(current-week media NameRows, previous-week media NameRows,
  current-week license NameRows, previous-week license NameRows) so a
  KOL who only has a license ghost row (no media spend yet) still appears.
  `costD` (and every other delta) must be None when there was no PREVIOUS
  MEDIA presence for that NameRow, even if a previous license-only presence
  existed -- a %Δ against "0 media spend, license fee only" is meaningless.
- All other WoW %Δ fields (metaTestKol / metaCreative / kolRows) are
  computed against the previous week's UNIFIED per-NameRow baseline across
  ALL buckets/testFlags -- never a bucket-scoped previous value.
- NAME_ALIASES: canonicalizes NameRow spellings that differ between a KOL's
  media-campaign ad name and their license ghost-row ad name (see the dict
  below). Add a new entry here (AND in scripts/update_cache_incremental.py's
  own alias table, if one exists, AND in scripts/build_all_lifetime.py) any
  time a similar duplicate NameRow is spotted for a new KOL.

--------------------------------------------------------------------------
USAGE

Real weekly build (this week's Bridge not in the cache yet):

    python3 scripts/build_weekly_report.py \\
        --cache _cache/ad_data_historical_cache.pkl.gz \\
        --bridge 2026W38/Hulken_Claude_Bridge.xlsx \\
        --week-num 38 --week-start 2026-09-17 --week-end 2026-09-23 \\
        --prev-week-num 37 --prev-start 2026-09-10 --prev-end 2026-09-16 \\
        --template 2026W37/hulken_week37_report.html \\
        --out 2026W38/hulken_week38_report.html \\
        --manual-week-1st-day 2026-09-17

Validation build (reconstruct a past week entirely from the cache, to sanity
check the script against an already-published report -- no --bridge needed
if the cache already covers the window):

    python3 scripts/build_weekly_report.py \\
        --cache _cache/ad_data_historical_cache.pkl.gz \\
        --week-num 36 --week-start 2026-09-03 --week-end 2026-09-09 \\
        --prev-week-num 35 --prev-start 2026-08-27 --prev-end 2026-09-02 \\
        --template 2026W35/hulken_week35_report.html \\
        --out /tmp/w36_check.html \\
        --manual-week-1st-day 2026-09-03 --dry-run-json /tmp/w36_data.json

If the "Weekly Report Manual" sheet ever has a duplicate/mislabeled
Week_1st_day again (as it did for W37 -- two different weeks tagged with the
same date), --manual-week-1st-day will raise a clear error; fall back to
--manual-cur-idx / --manual-prev-idx (0-based, half-open row ranges, 7 rows
per week) after inspecting the sheet by hand, and flag the bad label to
whoever maintains the Manual sheet.
"""
import argparse
import json
import re

import pandas as pd

NAME_ALIASES = {
    'A:原廠-Wakazo-25A:原廠-Wakazo': 'A:原廠-Wakazo-25',
    # KOL license-ghost rows for Row 154 use the ad name "A:KOL-marika-oka-154_"
    # (plain dash) while the real media campaign's ad name is
    # "A:KOL-marika.oka_..._R:154_Z:" (period in the KOL's own name) -> NameRow
    # "A:KOL-marika.oka-154". Same underlying creative; the published reports
    # use the plain-dash spelling as canonical, so merge the dot variant onto it.
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


# ---------------------------------------------------------------------------
# Derived-column logic (kept in sync with scripts/update_cache_incremental.py)
# ---------------------------------------------------------------------------

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


def row_from_namerow(nr):
    if not isinstance(nr, str):
        return None
    m = re.search(r'-(\d+)$', nr)
    return m.group(1) if m else None


def is_kol(nr):
    return bool(re.match(r'(?i)^A:KOL[\s-]', str(nr))) if isinstance(nr, str) else False


def test_flag(campaign):
    if pd.isna(campaign):
        return 'General'
    c = str(campaign).lower()
    if 'test' in c:
        return 'TEST'
    if 'c:cpc' in c:
        return 'CPC'
    return 'General'


def enrich(df):
    df = df.copy()
    df['goal'] = df[CAMPAIGN].apply(goal)
    df['AD_Channel'] = df[CAMPAIGN].apply(ad_channel)
    df['NameRow'] = df[ADNAME].apply(name_row)
    df['NameRow'] = df['NameRow'].replace(NAME_ALIASES)
    df['Row'] = df['NameRow'].apply(row_from_namerow)
    df['isKOL'] = df['NameRow'].apply(is_kol)
    df['testFlag'] = df[CAMPAIGN].apply(test_flag)
    return df


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------

def pct_delta(cur, prev):
    if prev is None or prev == 0 or pd.isna(prev):
        return None
    if cur is None or pd.isna(cur):
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


def safe_div(a, b):
    if b is None or b == 0 or pd.isna(b):
        return None
    return a / b


def r2(x, nd=2):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    return round(float(x), nd)


def agg_metrics(df):
    cost = df[COST].sum()
    rev = df[REV].sum()
    clicks = df[CLICKS].sum()
    impr = df[IMPR].sum()
    purch = df[PURCH].sum()
    roas = safe_div(rev, cost)
    ctr = safe_div(clicks, impr)
    cvr = safe_div(purch, clicks)
    cpm = safe_div(cost, impr)
    if cpm is not None:
        cpm = cpm * 1000
    cpa = safe_div(cost, purch)
    return dict(cost=cost, rev=rev, clicks=clicks, impr=impr, purch=purch,
                roas=roas, ctr=ctr, cvr=cvr, cpm=cpm, cpa=cpa)


# ---------------------------------------------------------------------------
# Data computation (PART 1)
# ---------------------------------------------------------------------------

def compute_report_data(cache_path, bridge_path, week_start, week_end,
                         prev_start, prev_end, manual_xlsx,
                         manual_week_1st_day=None,
                         manual_cur_idx=None, manual_prev_idx=None):
    cache = pd.read_pickle(cache_path, compression='gzip')
    if 'NameRow' in cache.columns:
        cache = cache.copy()
        cache['NameRow'] = cache['NameRow'].replace(NAME_ALIASES)

    frames = [cache]
    if bridge_path:
        bridge = pd.read_excel(bridge_path, sheet_name='Claude_Analysis_Data')
        bridge_enriched = enrich(bridge)
        # only take rows the cache doesn't already have (cache should cover
        # everything up to week_start - 1)
        bridge_slice = bridge_enriched[bridge_enriched[DATE] >= week_start]
        common = [c for c in cache.columns if c in bridge_slice.columns]
        frames = [cache[common], bridge_slice[common]]

    ad = pd.concat(frames, ignore_index=True).drop_duplicates()
    ad[DATE] = pd.to_datetime(ad[DATE])

    cur_win = ad[(ad[DATE] >= week_start) & (ad[DATE] <= week_end)]
    prev_win = ad[(ad[DATE] >= prev_start) & (ad[DATE] <= prev_end)]

    # ---- Meta scope for test/creative tables ----
    meta_cur = cur_win[(cur_win['AD_Channel'] == 'Meta AD') & (~cur_win['goal'].isin(['-', 'CPC']))]
    meta_prev = prev_win[(prev_win['AD_Channel'] == 'Meta AD') & (~prev_win['goal'].isin(['-', 'CPC']))]

    prev_by_nr = {}
    for nr, sub in meta_prev.groupby('NameRow'):
        prev_by_nr[nr] = agg_metrics(sub)

    def row_with_delta(nr, sub, extra=None):
        m = agg_metrics(sub)
        base = prev_by_nr.get(nr)
        out = {'name': nr}
        if extra:
            out.update(extra)
        out['cost'] = r2(m['cost'], 1) if m['cost'] else 0.0
        out['costD'] = pct_delta(m['cost'], base['cost'] if base else None)
        out['roas'] = r2(m['roas'])
        out['roasD'] = pct_delta(m['roas'], base['roas'] if base else None)
        out['ctr'] = r2(m['ctr'] * 100 if m['ctr'] is not None else None)
        out['ctrD'] = pct_delta(m['ctr'] * 100 if m['ctr'] is not None else None, base['ctr'] * 100 if base and base['ctr'] is not None else None)
        out['cvr'] = r2(m['cvr'] * 100 if m['cvr'] is not None else None)
        out['cvrD'] = pct_delta(m['cvr'] * 100 if m['cvr'] is not None else None, base['cvr'] * 100 if base and base['cvr'] is not None else None)
        out['cpm'] = r2(m['cpm'])
        out['cpmD'] = pct_delta(m['cpm'], base['cpm'] if base else None)
        return out

    # ---- metaTestRows: General vs TEST aggregate ----
    metaTestRows = []
    for flag in ['General', 'TEST']:
        cur_sub = meta_cur[meta_cur['testFlag'] == flag]
        prev_sub = meta_prev[meta_prev['testFlag'] == flag]
        m = agg_metrics(cur_sub)
        pm = agg_metrics(prev_sub)
        total_cost = meta_cur[COST].sum()
        metaTestRows.append({
            'label': flag,
            'cost': r2(m['cost'], 1),
            'costD': pct_delta(m['cost'], pm['cost']),
            'share': r2(m['cost'] / total_cost * 100, 2) if total_cost else None,
            'cpa': r2(m['cpa']),
            'cpaD': pct_delta(m['cpa'], pm['cpa']),
            'roas': r2(m['roas']),
            'roasD': pct_delta(m['roas'], pm['roas']),
            'ctr': r2(m['ctr'] * 100 if m['ctr'] is not None else None),
            'ctrD': pct_delta(m['ctr'] * 100 if m['ctr'] is not None else None, pm['ctr'] * 100 if pm['ctr'] is not None else None),
            'cvr': r2(m['cvr'] * 100 if m['cvr'] is not None else None),
            'cvrD': pct_delta(m['cvr'] * 100 if m['cvr'] is not None else None, pm['cvr'] * 100 if pm['cvr'] is not None else None),
            'cpm': r2(m['cpm']),
            'cpmD': pct_delta(m['cpm'], pm['cpm']),
        })

    # ---- metaTestKol: KOL + house TEST creatives; population = union(cur, prev) ----
    kol_cur_test = meta_cur[meta_cur['testFlag'] == 'TEST']
    kol_prev_test = meta_prev[meta_prev['testFlag'] == 'TEST']
    pop = sorted(set(kol_cur_test['NameRow'].dropna()) | set(kol_prev_test['NameRow'].dropna()))
    metaTestKol = []
    for nr in pop:
        sub = kol_cur_test[kol_cur_test['NameRow'] == nr]
        metaTestKol.append(row_with_delta(nr, sub))

    # ---- metaCreative: population = union(cur General namerows, prev General namerows) ----
    gen_cur = meta_cur[meta_cur['testFlag'] == 'General']
    gen_prev = meta_prev[meta_prev['testFlag'] == 'General']
    pop2 = sorted(set(gen_cur['NameRow'].dropna()) | set(gen_prev['NameRow'].dropna()))
    metaCreative = []
    for nr in pop2:
        sub = gen_cur[gen_cur['NameRow'] == nr]
        if len(sub):
            is_kol_row = bool(sub['isKOL'].iloc[0])
            tag_val = sub[TAG].dropna()
            tag = 'KOL' if is_kol_row else (tag_val.mode().iloc[0] if len(tag_val) else None)
        else:
            prev_sub = gen_prev[gen_prev['NameRow'] == nr]
            is_kol_row = bool(prev_sub['isKOL'].iloc[0]) if len(prev_sub) else is_kol(nr)
            tag_val = prev_sub[TAG].dropna() if len(prev_sub) else pd.Series(dtype=object)
            tag = 'KOL' if is_kol_row else (tag_val.mode().iloc[0] if len(tag_val) else None)
        metaCreative.append(row_with_delta(nr, sub, extra={'tag': tag}))
    # name, tag should lead the dict -> rebuild in that key order
    metaCreative = [{'name': r['name'], 'tag': r['tag'], **{k: v for k, v in r.items() if k not in ('name', 'tag')}} for r in metaCreative]

    gen_cur_total = agg_metrics(gen_cur)
    gen_prev_total = agg_metrics(gen_prev)
    metaCreativeTotal = {
        'cost': r2(gen_cur_total['cost'], 1),
        'costD': pct_delta(gen_cur_total['cost'], gen_prev_total['cost']),
        'roas': r2(gen_cur_total['roas']),
        'roasD': pct_delta(gen_cur_total['roas'], gen_prev_total['roas']),
    }

    # ---- kolRows / kolGrand: group by isKOL only (not testFlag) ----
    kol_cur = meta_cur[meta_cur['isKOL']]
    kol_prev = meta_prev[meta_prev['isKOL']]

    meta_all_cur = cur_win[cur_win['AD_Channel'] == 'Meta AD']
    meta_all_prev = prev_win[prev_win['AD_Channel'] == 'Meta AD']
    lic_cur = meta_all_cur[(meta_all_cur['isKOL']) & (meta_all_cur['goal'] == '-')]
    lic_prev = meta_all_prev[(meta_all_prev['isKOL']) & (meta_all_prev['goal'] == '-')]
    lic_cur_by_nr = lic_cur.groupby('NameRow')[COST].sum()
    lic_prev_by_nr = lic_prev.groupby('NameRow')[COST].sum()

    kol_pop = sorted(
        set(kol_cur['NameRow'].dropna()) | set(kol_prev['NameRow'].dropna())
        | set(lic_cur_by_nr.index) | set(lic_prev_by_nr.index)
    )

    prev_by_nr_kolcost = {}
    for nr in kol_pop:
        media_prev = prev_by_nr.get(nr)
        prev_media_cost = media_prev['cost'] if media_prev else 0.0
        prev_lic = lic_prev_by_nr.get(nr, 0.0)
        prev_by_nr_kolcost[nr] = (prev_media_cost or 0.0) + (prev_lic or 0.0)

    kolRows = []
    for nr in kol_pop:
        sub = kol_cur[kol_cur['NameRow'] == nr]
        m = agg_metrics(sub)
        lic = lic_cur_by_nr.get(nr, 0.0)
        cost_incl = (m['cost'] or 0.0) + (lic or 0.0)
        prev_total = prev_by_nr_kolcost.get(nr)
        media_prev = prev_by_nr.get(nr)
        row = {
            'name': nr,
            'cost': r2(cost_incl, 1),
            'lic': r2(lic, 1),
            # None (not 0) when there was no PREVIOUS MEDIA presence, even if
            # a previous license-only presence existed -- a %Δ against
            # "license fee but zero media" is meaningless. See CLAUDE.md.
            'costD': pct_delta(cost_incl, prev_total) if media_prev is not None else None,
            'cpa': r2(safe_div(cost_incl, m['purch'])),
            'cpaD': None,
            'roas': r2(safe_div(m['rev'], cost_incl)),
            'mediaRoas': r2(m['roas']),
            'roasD': pct_delta(safe_div(m['rev'], cost_incl), safe_div(media_prev['rev'], prev_total) if media_prev and prev_total else None),
            'ctr': r2(m['ctr'] * 100 if m['ctr'] is not None else None),
            'ctrD': pct_delta(m['ctr'] * 100 if m['ctr'] is not None else None, media_prev['ctr'] * 100 if media_prev and media_prev['ctr'] is not None else None),
            'cvr': r2(m['cvr'] * 100 if m['cvr'] is not None else None),
            'cvrD': pct_delta(m['cvr'] * 100 if m['cvr'] is not None else None, media_prev['cvr'] * 100 if media_prev and media_prev['cvr'] is not None else None),
            'cpm': r2(m['cpm']),
            'cpmD': pct_delta(m['cpm'], media_prev['cpm'] if media_prev else None),
        }
        prev_cpa = safe_div(prev_total, media_prev['purch']) if media_prev and prev_total else None
        row['cpaD'] = pct_delta(row['cpa'], prev_cpa)
        kolRows.append(row)

    kol_cur_m = agg_metrics(kol_cur)
    kol_prev_m = agg_metrics(kol_prev)
    lic_cur_total = lic_cur[COST].sum()
    lic_prev_total = lic_prev[COST].sum()
    cur_cost_incl = kol_cur_m['cost'] + lic_cur_total
    prev_cost_incl = kol_prev_m['cost'] + lic_prev_total
    kolGrand = {
        'cost': r2(cur_cost_incl, 1),
        'lic': r2(lic_cur_total, 1),
        'costD': pct_delta(cur_cost_incl, prev_cost_incl),
        'cpa': r2(safe_div(cur_cost_incl, kol_cur_m['purch'])),
        'cpaD': pct_delta(safe_div(cur_cost_incl, kol_cur_m['purch']), safe_div(prev_cost_incl, kol_prev_m['purch'])),
        'roas': r2(safe_div(kol_cur_m['rev'], cur_cost_incl)),
        'mediaRoas': r2(kol_cur_m['roas']),
        'roasD': pct_delta(safe_div(kol_cur_m['rev'], cur_cost_incl), safe_div(kol_prev_m['rev'], prev_cost_incl)),
        'ctr': r2(kol_cur_m['ctr'] * 100 if kol_cur_m['ctr'] is not None else None),
        'ctrD': pct_delta(kol_cur_m['ctr'] * 100 if kol_cur_m['ctr'] is not None else None, kol_prev_m['ctr'] * 100 if kol_prev_m['ctr'] is not None else None),
        'cvr': r2(kol_cur_m['cvr'] * 100 if kol_cur_m['cvr'] is not None else None),
        'cvrD': pct_delta(kol_cur_m['cvr'] * 100 if kol_cur_m['cvr'] is not None else None, kol_prev_m['cvr'] * 100 if kol_prev_m['cvr'] is not None else None),
        'cpm': r2(kol_cur_m['cpm']),
        'cpmD': pct_delta(kol_cur_m['cpm'], kol_prev_m['cpm']),
    }

    # ---- Overview: channelRows / channelGrand from Weekly Report Manual ----
    wrm = pd.read_excel(manual_xlsx, sheet_name='Weekly Report Manual')
    if manual_week_1st_day:
        cur_manual = wrm[wrm['Week_1st_day'] == pd.Timestamp(manual_week_1st_day)].reset_index(drop=True)
        prev_manual = wrm[wrm['Week_1st_day'] == pd.Timestamp(prev_start)].reset_index(drop=True)
        # Only a row whose (Week_1st_day, Channel, AD Type) triple repeats is
        # ambiguous. A Channel alone legitimately repeats (Google/Amazon/Rakuten
        # each have 2 AD Type rows), so checking Channel alone always false-alarmed
        # (fixed 2026-09-23, W38).
        key = ['Week_1st_day', 'Channel', 'AD Type']
        dup_cur = cur_manual[cur_manual.duplicated(key, keep=False)]
        dup_prev = prev_manual[prev_manual.duplicated(key, keep=False)]
        if len(dup_cur) or len(dup_prev):
            dups = pd.concat([dup_cur, dup_prev])[key].drop_duplicates()
            raise SystemExit(
                "Weekly Report Manual has duplicate (Week_1st_day, Channel, AD Type) "
                f"rows for {manual_week_1st_day} or {prev_start}:\n"
                f"{dups.to_string(index=False)}\n"
                "Inspect the sheet by hand and pass --manual-cur-idx / "
                "--manual-prev-idx instead (see the W37 build for precedent)."
            )
    else:
        cs, ce = manual_cur_idx
        ps, pe = manual_prev_idx
        cur_manual = wrm.iloc[cs:ce].reset_index(drop=True)
        prev_manual = wrm.iloc[ps:pe].reset_index(drop=True)

    total_cost = cur_manual['Cost'].sum()
    channelRows = []
    for _, r in cur_manual.iterrows():
        prow = prev_manual[(prev_manual['Channel'] == r['Channel']) & (prev_manual['AD Type'] == r['AD Type'])]
        cost = r['Cost']; impr = r['Impression']; click = r['Click']; purch = r['Purchase']; rev = r['Purchase Value']
        roas = safe_div(rev, cost); ctr = safe_div(click, impr); cvr = safe_div(purch, click)
        cpm = safe_div(cost, impr); cpm = cpm * 1000 if cpm is not None else None
        if len(prow):
            pr = prow.iloc[0]
            pcost = pr['Cost']; pimpr = pr['Impression']; pclick = pr['Click']; ppurch = pr['Purchase']; prev_v = pr['Purchase Value']
            proas = safe_div(prev_v, pcost); pctr = safe_div(pclick, pimpr); pcvr = safe_div(ppurch, pclick)
            pcpm = safe_div(pcost, pimpr); pcpm = pcpm * 1000 if pcpm is not None else None
        else:
            pcost = None; proas = pctr = pcvr = pcpm = None
        channelRows.append({
            'channel': r['Channel'], 'type': r['AD Type'],
            'cost': r2(cost, 1),
            'costD': pct_delta(cost, pcost),
            'share': r2(cost / total_cost * 100, 2) if total_cost else None,
            'ctr': r2(ctr * 100 if ctr is not None else None),
            'ctrD': pct_delta(ctr * 100 if ctr is not None else None, pctr * 100 if pctr is not None else None),
            'cvr': r2(cvr * 100 if cvr is not None else None),
            'cvrD': pct_delta(cvr * 100 if cvr is not None else None, pcvr * 100 if pcvr is not None else None),
            'cpm': r2(cpm),
            'cpmD': pct_delta(cpm, pcpm),
            'roas': r2(roas),
            'roasD': pct_delta(roas, proas),
        })

    gt_cost = cur_manual['Cost'].sum(); gt_impr = cur_manual['Impression'].sum(); gt_click = cur_manual['Click'].sum()
    gt_purch = cur_manual['Purchase'].sum(); gt_rev = cur_manual['Purchase Value'].sum()
    pgt_cost = prev_manual['Cost'].sum(); pgt_impr = prev_manual['Impression'].sum(); pgt_click = prev_manual['Click'].sum()
    pgt_purch = prev_manual['Purchase'].sum(); pgt_rev = prev_manual['Purchase Value'].sum()
    gt_ctr = safe_div(gt_click, gt_impr); gt_cvr = safe_div(gt_purch, gt_click)
    gt_cpm = safe_div(gt_cost, gt_impr); gt_cpm = gt_cpm * 1000 if gt_cpm is not None else None
    gt_roas = safe_div(gt_rev, gt_cost)
    pgt_ctr = safe_div(pgt_click, pgt_impr); pgt_cvr = safe_div(pgt_purch, pgt_click)
    pgt_cpm = safe_div(pgt_cost, pgt_impr); pgt_cpm = pgt_cpm * 1000 if pgt_cpm is not None else None
    pgt_roas = safe_div(pgt_rev, pgt_cost)
    channelGrand = {
        'cost': r2(gt_cost, 0),
        'costD': pct_delta(gt_cost, pgt_cost),
        'ctr': r2(gt_ctr * 100 if gt_ctr is not None else None),
        'ctrD': pct_delta(gt_ctr * 100 if gt_ctr is not None else None, pgt_ctr * 100 if pgt_ctr is not None else None),
        'cvr': r2(gt_cvr * 100 if gt_cvr is not None else None),
        'cvrD': pct_delta(gt_cvr * 100 if gt_cvr is not None else None, pgt_cvr * 100 if pgt_cvr is not None else None),
        'cpm': r2(gt_cpm),
        'cpmD': pct_delta(gt_cpm, pgt_cpm),
        'roas': r2(gt_roas),
        'roasD': pct_delta(gt_roas, pgt_roas),
    }

    # KPI hero tiles come from ad_data itself (Meta+Google combined,
    # goal not in ['-','CPC']) -- NOT the Weekly Report Manual.
    overview_cur = cur_win[~cur_win['goal'].isin(['-', 'CPC'])]
    overview_prev = prev_win[~prev_win['goal'].isin(['-', 'CPC'])]
    tot_cost = overview_cur[COST].sum(); tot_impr = overview_cur[IMPR].sum(); tot_click = overview_cur[CLICKS].sum()
    tot_purch = overview_cur[PURCH].sum(); tot_rev = overview_cur[REV].sum()
    ptot_cost = overview_prev[COST].sum(); ptot_impr = overview_prev[IMPR].sum(); ptot_click = overview_prev[CLICKS].sum()
    ptot_purch = overview_prev[PURCH].sum(); ptot_rev = overview_prev[REV].sum()

    kpi_defs = [
        ('花費金額 (JPY)', tot_cost, ptot_cost, lambda v: f"¥{v:,.0f}"),
        ('CPA', safe_div(tot_cost, tot_purch), safe_div(ptot_cost, ptot_purch), lambda v: f"¥{v:,.2f}"),
        ('ROAS', safe_div(tot_rev, tot_cost), safe_div(ptot_rev, ptot_cost), lambda v: f"{v:.2f}"),
        ('CTR', safe_div(tot_click, tot_impr), safe_div(ptot_click, ptot_impr), lambda v: f"{v*100:.2f}%"),
        ('CVR', safe_div(tot_purch, tot_click), safe_div(ptot_purch, ptot_click), lambda v: f"{v*100:.2f}%"),
        ('CPM', safe_div(tot_cost, tot_impr) * 1000 if tot_impr else None, safe_div(ptot_cost, ptot_impr) * 1000 if ptot_impr else None, lambda v: f"¥{v:,.2f}"),
    ]
    kpis = []
    for label, cur_v, prev_v, fmt in kpi_defs:
        d = {'label': label, 'value': fmt(cur_v) if cur_v is not None else None, 'delta': pct_delta(cur_v, prev_v)}
        if label == 'ROAS':
            d['hero'] = True
        kpis.append(d)

    def split_rows(cur_df, prev_df, group_col_fn, labels):
        cur_df = cur_df.copy(); prev_df = prev_df.copy()
        cur_df['_grp'] = group_col_fn(cur_df)
        prev_df['_grp'] = group_col_fn(prev_df)
        total_cost_local = cur_df[COST].sum()
        rows = []
        for lab in labels:
            csub = cur_df[cur_df['_grp'] == lab]
            psub = prev_df[prev_df['_grp'] == lab]
            m = agg_metrics(csub); pm = agg_metrics(psub)
            rows.append({
                'label': lab,
                'cost': r2(m['cost'], 1),
                'costD': pct_delta(m['cost'], pm['cost']),
                'share': r2(m['cost'] / total_cost_local * 100, 2) if total_cost_local else None,
                'cpa': r2(m['cpa']),
                'roas': r2(m['roas']),
                'roasD': pct_delta(m['roas'], pm['roas']),
                'ctr': r2(m['ctr'] * 100 if m['ctr'] is not None else None),
                'cvr': r2(m['cvr'] * 100 if m['cvr'] is not None else None),
            })
        return rows

    brandSplit = split_rows(
        overview_cur, overview_prev,
        lambda df: df[CAMPAIGN].str.contains('包含品牌字', na=False).map({True: '是', False: '否'}),
        ['否', '是'],
    )
    testSplit = split_rows(
        overview_cur, overview_prev,
        lambda df: df['testFlag'],
        ['General', 'TEST'],
    )
    overviewGrandRef = {'cost': r2(tot_cost, 1), 'roas': r2(safe_div(tot_rev, tot_cost))}

    return {
        'kpis': kpis, 'channelRows': channelRows, 'channelGrand': channelGrand,
        'brandSplit': brandSplit, 'testSplit': testSplit, 'overviewGrandRef': overviewGrandRef,
        'metaTestRows': metaTestRows, 'metaTestKol': metaTestKol,
        'metaCreative': metaCreative, 'metaCreativeTotal': metaCreativeTotal,
        'kolRows': kolRows, 'kolGrand': kolGrand,
    }


# ---------------------------------------------------------------------------
# HTML templating (PART 2)
# ---------------------------------------------------------------------------

def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


def sub_const(html, name, value):
    pattern = re.compile(r"(const " + name + r" ?= ?)(\[.*?\]|\{.*?\})(;)", re.S)
    new_html, n = pattern.subn(lambda m: m.group(1) + dumps(value) + m.group(3), html, count=1)
    if n != 1:
        raise SystemExit(f"failed to substitute const {name} (found {n} matches, expected 1)")
    return new_html


def sub_render_split(html, card_id, rows, ref):
    pattern = re.compile(r"(renderSplit\('" + card_id + r"', )(\[.*?\])(, )(\{[^}]*\})(\);)", re.S)
    replacement = (
        r"\g<1>" + dumps(rows).replace("\\", "\\\\") + r"\g<3>"
        + ("{cost:%r, roas:%r}" % (ref["cost"], ref["roas"])) + r"\g<5>"
    )
    new_html, n = pattern.subn(replacement, html, count=1)
    if n != 1:
        raise SystemExit(f"failed to substitute renderSplit({card_id}) (found {n} matches, expected 1)")
    return new_html


_DIV_TAG_RE = re.compile(r'<div\b[^>]*>|</div>')


def _remove_balanced_div(html, css_class):
    """Remove exactly one <div class="{css_class}">...</div> block, correctly
    matching its true closing tag even when it contains nested <div>s (a plain
    non-greedy regex stops at the FIRST nested </div> and silently truncates
    the block -- see the caller's comment for the real bug this caused)."""
    open_tag_re = re.compile(r'<div class="' + re.escape(css_class) + r'"[^>]*>')
    m = open_tag_re.search(html)
    if not m:
        return html  # nothing to remove, e.g. template already had none
    start = m.start()
    depth = 0
    pos = m.start()
    end = None
    for tm in _DIV_TAG_RE.finditer(html, m.start()):
        if tm.group(0).startswith('</div'):
            depth -= 1
            if depth == 0:
                end = tm.end()
                break
        else:
            depth += 1
    if end is None:
        raise SystemExit(f'unbalanced <div class="{css_class}"> block, could not find its matching close tag')
    if open_tag_re.search(html, end):
        raise SystemExit(f'found more than one <div class="{css_class}"> block -- inspect the template by hand')
    # tidy up so we don't leave a blank/whitespace-only line where the block was
    pre = html[:start]
    post = html[end:]
    pre = re.sub(r'[ \t]+\Z', '', pre)
    post = re.sub(r'\A(?:[ \t]*\n)+', '', post)
    return pre + post


def build_html(template_path, out_path, data, week_num, prev_week_num,
                week_start, week_end, prev_start, out_report_path):
    with open(template_path, encoding='utf-8') as f:
        html = f.read()

    ws_disp = week_start.strftime('%Y/%m/%d')
    we_disp = week_end.strftime('%Y/%m/%d')
    we_short = week_end.strftime('%m/%d')
    ws_short = week_start.strftime('%m/%d')

    # 1. <title>
    html, n = re.subn(
        r'(<title>HULKEN JP · Week )\d+( 廣告成效週報</title>)',
        lambda m: m.group(1) + str(week_num) + m.group(2), html, count=1)
    if n != 1:
        raise SystemExit(f"title substitution matched {n} times, expected 1")

    # 2. weekPickerToggle chip
    html, n = re.subn(
        r'(<div class="meta-chip" id="weekPickerToggle">)Week \d+ · [\d/]+ – [\d/]+(\s*<span class="caret">▼</span></div>)',
        lambda m: m.group(1) + f"Week {week_num} · {ws_disp} – {we_disp}" + m.group(2),
        html, count=1)
    if n != 1:
        raise SystemExit(f"weekPickerToggle substitution matched {n} times, expected 1")

    # 3. sub line (updater / update date -- update date = this week's end date)
    html, n = re.subn(
        r'(整理人：Leo · 更新日期 )\d{4}/\d{2}/\d{2}( · 資料來源：Hulken JP_Mastersheet（Meta / Google / Amazon / Rakuten / KOL）)',
        lambda m: m.group(1) + we_disp + m.group(2), html, count=1)
    if n != 1:
        raise SystemExit(f"sub-line date substitution matched {n} times, expected 1")

    # 4. channels section tag (week start, English month/day/year, no leading zero on day)
    week_start_en = f"{week_start.strftime('%b')} {week_start.day}, {week_start.year}"
    html, n = re.subn(
        r'(<span class="sec-tag">依渠道 / 廣告類型拆解 · Week: )[A-Za-z]+ \d+, \d{4}(</span>)',
        lambda m: m.group(1) + week_start_en + m.group(2), html, count=1)
    if n != 1:
        raise SystemExit(f"sec-tag substitution matched {n} times, expected 1")

    # 5. channels hint (references PREVIOUS week's Week_1st_day, i.e. prev_start)
    html, n = re.subn(
        r'(<div class="hint">%Δ 為對比上週（Week_1st_day )\d{4}-\d{2}-\d{2}(）之週增減。</div>)',
        lambda m: m.group(1) + prev_start.strftime('%Y-%m-%d') + m.group(2),
        html, count=1)
    if n != 1:
        raise SystemExit(f"hint substitution matched {n} times, expected 1")

    # 6. remove the previous week's insight callout block, if present (we
    #    don't carry last week's narrative forward, and don't fabricate a
    #    new one without a Weekly Insight source for this week).
    #
    #    IMPORTANT: the callout div nests one <div class="row">...</div>
    #    per insight line, so a naive non-greedy regex
    #    (r'<div class="callout">.*?</div>') only matches up to the FIRST
    #    inner </div> -- it silently truncates the block, stripping the
    #    opening tag + first row but leaving every other row (and the
    #    outer closing </div>) dangling as unwrapped, visibly-rendered
    #    plain text. This is exactly what happened on the live W37 report
    #    (caught by the user 2026-09-16, after this same bug had already
    #    slipped through the ad-hoc script this permanent version replaced)
    #    -- do NOT revert to a simple regex here. Find the matching close
    #    tag by counting nested <div> opens/closes instead.
    html = _remove_balanced_div(html, 'callout')

    # 7. footer
    html, n = re.subn(
        r'本頁為 Week \d+（[\d/]+–[\d/]+）週報。',
        f"本頁為 Week {week_num}（{ws_disp}–{we_short}）週報。", html, count=1)
    if n != 1:
        raise SystemExit(f"footer substitution matched {n} times, expected 1")

    # 8. THIS_REPORT_FILE const
    html, n = re.subn(
        r"const THIS_REPORT_FILE = '2026W\d+/hulken_week\d+_report\.html';",
        f"const THIS_REPORT_FILE = '{out_report_path}';", html, count=1)
    if n != 1:
        raise SystemExit(f"THIS_REPORT_FILE substitution matched {n} times, expected 1")

    # 9. WoW-deltas source comment (cosmetic, doesn't affect rendering, but
    #    keep it truthful -- carried-over stale dates were spotted once already)
    html, n = re.subn(
        r'(// WoW deltas computed from Weekly Report Manual \(Week_1st_day )\d{4}-\d{2}-\d{2}( vs )\d{4}-\d{2}-\d{2}(\)\.)',
        lambda m: m.group(1) + prev_start.strftime('%Y-%m-%d') + m.group(2) + week_start.strftime('%Y-%m-%d') + m.group(3),
        html, count=1)
    if n != 1:
        raise SystemExit(f"WoW-deltas comment substitution matched {n} times, expected 1")

    # 10. data consts
    for name in ['kpis', 'channelRows', 'channelGrand', 'metaTestRows',
                 'metaTestKol', 'metaCreative', 'metaCreativeTotal',
                 'kolRows', 'kolGrand']:
        html = sub_const(html, name, data[name])

    # 11. renderSplit(...) calls
    html = sub_render_split(html, 'brandSplitCard', data['brandSplit'], data['overviewGrandRef'])
    html = sub_render_split(html, 'testSplitCard', data['testSplit'], data['overviewGrandRef'])

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return len(html)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cache', default='_cache/ad_data_historical_cache.pkl.gz')
    ap.add_argument('--bridge', default=None, help="this week's Bridge xlsx (needed unless the cache already covers week-end)")
    ap.add_argument('--week-num', type=int, required=True)
    ap.add_argument('--week-start', required=True)
    ap.add_argument('--week-end', required=True)
    ap.add_argument('--prev-week-num', type=int, required=True)
    ap.add_argument('--prev-start', required=True)
    ap.add_argument('--prev-end', required=True)
    ap.add_argument('--template', required=True, help="previous week's report HTML, used as the base to clone")
    ap.add_argument('--out', required=True, help='output report HTML path, e.g. 2026W38/hulken_week38_report.html')
    ap.add_argument('--manual-xlsx', default=None, help="defaults to --bridge (Weekly Report Manual sheet lives in this week's Bridge file)")
    ap.add_argument('--manual-week-1st-day', default=None, help='preferred: filters Weekly Report Manual by this Week_1st_day value')
    ap.add_argument('--manual-cur-idx', type=int, nargs=2, default=None, help='fallback: 0-based half-open row range for this week, use only if --manual-week-1st-day errors out on a duplicate label')
    ap.add_argument('--manual-prev-idx', type=int, nargs=2, default=None, help='fallback: 0-based half-open row range for previous week')
    ap.add_argument('--dry-run-json', default=None, help='also dump the computed data dict to this path, for inspection/diffing')
    args = ap.parse_args()

    week_start = pd.Timestamp(args.week_start)
    week_end = pd.Timestamp(args.week_end)
    prev_start = pd.Timestamp(args.prev_start)
    prev_end = pd.Timestamp(args.prev_end)
    manual_xlsx = args.manual_xlsx or args.bridge
    if not manual_xlsx:
        raise SystemExit("need --manual-xlsx or --bridge to locate the Weekly Report Manual sheet")

    data = compute_report_data(
        args.cache, args.bridge, week_start, week_end, prev_start, prev_end,
        manual_xlsx, manual_week_1st_day=args.manual_week_1st_day,
        manual_cur_idx=args.manual_cur_idx, manual_prev_idx=args.manual_prev_idx,
    )

    if args.dry_run_json:
        with open(args.dry_run_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=None)
        print('wrote', args.dry_run_json)

    n_bytes = build_html(
        args.template, args.out, data, args.week_num, args.prev_week_num,
        week_start, week_end, prev_start, args.out,
    )
    print(f"wrote {args.out} ({n_bytes} bytes)")
    print("Next: eyeball the report in a browser, then follow CLAUDE.md's git push checklist.")


if __name__ == '__main__':
    main()
