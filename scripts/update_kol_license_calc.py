"""
Hulken Weekly Report -- refresh the KOL negotiation calculator's license-fee
reference data ("第一波授權金參考") on all.html from the Bridge file's
"KOL授權金" tab.

Why this exists: the calculator on all.html (KOL 第二波授權金談判計算機) shows,
for a given Row Number, the actual fee/period of the *previous* negotiated
license wave as a benchmark when estimating what the *next* wave could bear.
That reference used to be guessed/derived from raw ad-spend data with an
undocumented formula. As of 2026-08-27 the user maintains an authoritative
"KOL授權金" tab in each week's Hulken_Claude_Bridge.xlsx listing every KOL's
real, actually-negotiated license fee and period -- this script reads that
tab and uses it as the *only* source for the calculator's firstWave reference.

IMPORTANT -- scope: this ONLY touches the calculator's display data
(LIC_ROW_DATA[*].firstWave on all.html). It must NEVER be used to change the
weekly report's own KOL 表現＋授權金 table (kolRows/kolGrand's `lic` field) --
that stays sourced from the raw Mastersheet/Bridge ghost rows (行銷活動名稱='-'),
which amortizes each license fee evenly across its license window so the
week-by-week ROAS stays accurate. The "KOL授權金" tab's per-episode totals are
for the negotiation calculator's reference display only, per the user's
explicit instruction (2026-08-27).

Usage:
    python3 update_kol_license_calc.py \
        --bridge "2026W34/Hulken_Claude_Bridge.xlsx" \
        --all-html all.html \
        --out out_all.html

Merge policy (conservative -- only ever replaces what the new tab can prove):
  - For every Row Number that appears in BOTH the tab (with an "R<n>" prefix
    on 廣告名稱/KOL 名稱) AND already exists in all.html's LIC_ROW_DATA:
    - If the tab gives a usable fee (>0) and a fully-dated period (every
      \\n-separated date range in 授權期間 has both a start and end date):
      overwrite firstWave = {fee, days, start, end}. `days` sums the actual
      length of every listed range (handles a KOL with a free extension
      logged as a second \\n-separated range, e.g. R97 hadamegu); `start`/
      `end` are the earliest start and latest end across all ranges.
    - If the tab's fee is 0 (fee-free arrangement) or a range has no end
      date yet: DELETE any existing firstWave key -- a confirmed ¥0 or
      undated deal is not a usable negotiation benchmark, and we know for a
      fact the guessed value that might have been there before is now
      superseded.
  - Row Numbers in the tab but absent from LIC_ROW_DATA (i.e. no recent ad
    spend on record for that row, usually a brand-new creative) are left
    alone -- the calculator's Row lookup requires B/C from spend data first,
    so adding a firstWave-only stub wouldn't be reachable through the UI.
  - Row Numbers in LIC_ROW_DATA NOT covered by the tab (pre-Row-number-era
    KOLs, roughly anything from before ~2026-07) are left untouched --
    there's no new information to act on for those.

Run this every week right after the new week's Bridge file (with its
KOL授權金 tab) is available -- see Mastersheet_Tab_Guide.md and CLAUDE.md's
Step 6 for the full weekly checklist.
"""
import argparse, re, json
import pandas as pd

YEAR_DEFAULT = 2026


def parse_fee(v):
    if pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).replace('¥', '').replace(',', '').strip()
    if s in ('', '-'):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_ranges(period_str, year):
    """Parse a (possibly multi-line) 授權期間 string into [(start, end, days), ...].
    Each line may carry leading descriptive text (e.g. '廣告延長：6/30〜7/29') --
    the date pattern is searched for, not anchored, to tolerate that."""
    if pd.isna(period_str):
        return []
    segs = [s.strip() for s in str(period_str).split('\n') if s.strip()]
    out = []
    for seg in segs:
        seg = seg.replace(' ', '').replace('〜', '~').replace('～', '~')
        parts = seg.split('~')

        def to_date(md):
            if not md:
                return None
            m = re.search(r'(\d{1,2})/(\d{1,2})', md)
            if not m:
                return None
            return pd.Timestamp(year=year, month=int(m.group(1)), day=int(m.group(2)))

        sd = to_date(parts[0]) if len(parts) > 0 else None
        ed = to_date(parts[1]) if len(parts) > 1 else None
        days = (ed - sd).days + 1 if (sd is not None and ed is not None) else None
        out.append((sd, ed, days))
    return out


def extract_row(name):
    m = re.match(r'R(\d+)', str(name).strip())
    return m.group(1) if m else None


def build_records(bridge_path, year):
    df = pd.read_excel(bridge_path, sheet_name='KOL授權金')
    valid, zero_or_undated = {}, []
    for _, row in df.iterrows():
        rownum = extract_row(row['KOL 名稱'])
        if not rownum:
            continue
        fee = parse_fee(row['費用'])
        ranges = parse_ranges(row['授權期間'], year)
        total_days = sum(r[2] for r in ranges) if ranges and all(r[2] is not None for r in ranges) else None
        start = min((r[0] for r in ranges if r[0] is not None), default=None)
        end = max((r[1] for r in ranges if r[1] is not None), default=None)
        if fee is not None and fee > 0 and total_days is not None and total_days > 0:
            valid[rownum] = {
                'fee': fee, 'days': total_days,
                'start': start.strftime('%Y-%m-%d'), 'end': end.strftime('%Y-%m-%d'),
            }
        else:
            zero_or_undated.append(rownum)
    return valid, zero_or_undated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bridge', required=True, help="This week's Hulken_Claude_Bridge.xlsx (must have a KOL授權金 tab)")
    ap.add_argument('--all-html', required=True, help='Current all.html to update')
    ap.add_argument('--out', required=True, help='Path to write the updated all.html to')
    ap.add_argument('--year', type=int, default=YEAR_DEFAULT, help='Year to assume for bare M/D dates in 授權期間')
    args = ap.parse_args()

    valid, zero_or_undated = build_records(args.bridge, args.year)

    html = open(args.all_html, encoding='utf-8').read()
    m = re.search(r'const LIC_ROW_DATA = (\{.*?\});\n', html, re.S)
    if not m:
        raise SystemExit("const LIC_ROW_DATA = {...}; not found in " + args.all_html)
    lic_data = json.loads(m.group(1))

    updated, cleared, skipped_no_licdata = 0, 0, []
    for rownum, rec in valid.items():
        if rownum in lic_data:
            lic_data[rownum]['firstWave'] = {'fee': rec['fee'], 'days': rec['days'], 'start': rec['start'], 'end': rec['end']}
            updated += 1
        else:
            skipped_no_licdata.append(rownum)
    for rownum in zero_or_undated:
        if rownum in lic_data and 'firstWave' in lic_data[rownum]:
            del lic_data[rownum]['firstWave']
            cleared += 1

    new_json = json.dumps(lic_data, ensure_ascii=False)
    html = html[:m.start()] + f'const LIC_ROW_DATA = {new_json};\n' + html[m.end():]
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Updated firstWave for {updated} Row(s) already tracked in LIC_ROW_DATA.")
    print(f"Cleared stale/incorrect firstWave for {cleared} Row(s) now confirmed fee=0 or undated.")
    if skipped_no_licdata:
        print(f"Tab has fee data for {len(skipped_no_licdata)} Row(s) with no B/C spend data yet (not added, unreachable via calculator UI): {skipped_no_licdata}")
    print(f"Wrote {args.out}")


if __name__ == '__main__':
    main()
