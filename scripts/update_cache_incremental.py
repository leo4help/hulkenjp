"""
Hulken Weekly Report — incremental historical-cache extension.

Run this every week (in the container, against staged copies of the files),
right after reading that week's Hulken_Claude_Bridge.xlsx, so the cache's
cutoff_date always advances in step with the report and the gap between
_cache/ad_data_historical_cache.pkl.gz and the Bridge's own trailing-28-day
window never reopens.

Usage:
    python3 update_cache_incremental.py \
        --bridge "2026W35/Hulken_Claude_Bridge.xlsx" \
        --cache-pkl "_cache/ad_data_historical_cache.pkl.gz" \
        --cache-meta "_cache/ad_data_cache_meta.json" \
        --new-cutoff 2026-08-27 \
        --out-pkl new_ad_data_historical_cache.pkl.gz \
        --out-meta new_ad_data_cache_meta.json

--new-cutoff should be the start date (Monday) of the week being built THIS
run — i.e. everything strictly before that date is now "confirmed history"
and safe to fold into the cache; everything >= that date is still "current
window" and must keep being re-read fresh from the Bridge each week.

Only pulls the slice [old_cutoff, new_cutoff) out of the Bridge's
Claude_Analysis_Data — that's normally ~7 days wide and always well inside
the Bridge's own 28-day trailing window, so this never needs the full
Halken JP_Mastersheet.xlsx as long as it's run every single week without a
gap. If a week gets skipped and the gap between old cutoff and new-cutoff
exceeds the Bridge's own 28-day coverage, this script will error out rather
than silently leaving a hole — at that point you need the full Mastersheet
again (see Mastersheet_Tab_Guide.md).

Writes the extended cache + updated meta to the two --out-* paths (does not
overwrite the input cache in place, so the caller can review/stage/commit
it deliberately, same pattern as everything else in this project).
"""
import argparse, re, json
import pandas as pd

NAME_ALIASES = {'A:原廠-Wakazo-25A:原廠-Wakazo': 'A:原廠-Wakazo-25'}


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
    df['goal'] = df['行銷活動名稱'].apply(goal)
    df['AD_Channel'] = df['行銷活動名稱'].apply(ad_channel)
    df['NameRow'] = df['廣告名稱'].apply(name_row)
    df['NameRow'] = df['NameRow'].replace(NAME_ALIASES)
    df['Row'] = df['NameRow'].apply(row_from_namerow)
    df['isKOL'] = df['NameRow'].apply(is_kol)
    df['testFlag'] = df['行銷活動名稱'].apply(test_flag)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bridge', required=True)
    ap.add_argument('--cache-pkl', required=True)
    ap.add_argument('--cache-meta', required=True)
    ap.add_argument('--new-cutoff', required=True, help='YYYY-MM-DD, this week\'s report window start date')
    ap.add_argument('--out-pkl', required=True)
    ap.add_argument('--out-meta', required=True)
    args = ap.parse_args()

    with open(args.cache_meta, encoding='utf-8') as f:
        meta = json.load(f)
    old_cutoff = pd.Timestamp(meta['cutoff_date'])
    new_cutoff = pd.Timestamp(args.new_cutoff)
    if new_cutoff <= old_cutoff:
        raise SystemExit(f"--new-cutoff {new_cutoff.date()} is not after the cache's current cutoff {old_cutoff.date()} — nothing to do.")

    bridge = pd.read_excel(args.bridge, sheet_name='Claude_Analysis_Data')
    bmin = bridge['分析報告開始'].min()
    if bmin > old_cutoff:
        raise SystemExit(
            f"Gap: Bridge's own window starts {bmin.date()}, which is AFTER the cache's cutoff "
            f"{old_cutoff.date()}. The incremental slice can't be filled from this Bridge file alone — "
            f"you need the full Halken JP_Mastersheet.xlsx to close this gap first (see "
            f"Mastersheet_Tab_Guide.md 快取增量重建 section)."
        )

    slice_df = bridge[(bridge['分析報告開始'] >= old_cutoff) & (bridge['分析報告開始'] < new_cutoff)]
    slice_df = enrich(slice_df)

    cache = pd.read_pickle(args.cache_pkl, compression='gzip')
    common_cols = [c for c in cache.columns if c in slice_df.columns]
    combined = pd.concat([cache[common_cols], slice_df[common_cols]], ignore_index=True)
    combined = combined.drop_duplicates()
    combined = combined.sort_values('分析報告開始').reset_index(drop=True)

    combined.to_pickle(args.out_pkl, compression='gzip')

    new_meta = dict(meta)
    new_meta.update({
        'cutoff_date': str(new_cutoff.date()),
        'historical_row_count': int(combined.shape[0]),
        'historical_date_min': str(combined['分析報告開始'].min().date()),
        'historical_date_max': str(combined['分析報告開始'].max().date()),
        'note': (
            f"Incrementally extended from cutoff {old_cutoff.date()} -> {new_cutoff.date()} using "
            f"{args.bridge}'s own Claude_Analysis_Data (no full Mastersheet needed). "
            "Run update_cache_incremental.py again next week with the next week's Bridge + "
            "that week's own report-window start date as --new-cutoff."
        ),
    })
    with open(args.out_meta, 'w', encoding='utf-8') as f:
        json.dump(new_meta, f, ensure_ascii=False, indent=2)

    print(f"Extended cache: {old_cutoff.date()} -> {new_cutoff.date()}  "
          f"({combined.shape[0]} rows, +{slice_df.shape[0]} new)")


if __name__ == '__main__':
    main()
