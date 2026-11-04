"""W44 起（2026-11-04）：Meta / Google 媒體數據改由 MCP 抓，Bridge 只提供授權金攤提列、
KOL授權金分頁、「Meta 素材表（查看標記用）」。本腳本把三者合成一份與舊 Bridge 同格式的 xlsx，
後面的 update_cache_incremental / build_weekly_report / build_all_lifetime 等腳本不用改。

輸入：
  --bridge       使用者給的 Bridge（Claude_Analysis_Data 只用到 week-start 之前的列＋本週的授權金列）
  --meta-csv     Meta MCP ads_get_ad_entities（level=ad, time_increment=1）整理後的 CSV
                 欄位：分析報告開始, 廣告名稱, 行銷活動名稱, 廣告組合名稱, 花費金額 (JPY), 曝光次數,
                       連結點擊次數, 購買次數, 購買轉換值, 加到購物車次數
                 （購買次數 = omni_purchase、購買轉換值 = offsite_conversion_fb_pixel_purchase_values；
                   W43 驗證與 Ads Manager 匯出逐日一致）
  --google-csv   Google Ads MCP campaign 層級、segments.date 逐日；購買次數 / 購買轉換值 必須用
                 metrics.conversions_by_conversion_date / conversions_value_by_conversion_date
                 （W43 驗證：這才與 Bridge 一致；metrics.conversions 對不上）
  --week-start   本週起始日；Bridge 中 >= 此日的「媒體列」會被丟掉（以 MCP 為準），授權金列（goal '-'）保留

原廠標記：依「Meta 素材表（查看標記用）」的後台名稱對照（去掉 ' - 1'、' - 複本' 等複製後綴，
再退而用 R:<Row>）；表上沒寫且廣告名稱是 A:KOL 開頭 → 'KOL'（與舊 Bridge 一致）；其餘留空（NULL）。
"""
import argparse, re
import pandas as pd

TAG_SHEET = 'Meta 素材表（查看標記用）'


def _clean(name):
    return re.sub(r'\s*-\s*(\d+|複本|コピー|copy)\s*$', '', str(name)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bridge', required=True)
    ap.add_argument('--meta-csv', required=True)
    ap.add_argument('--google-csv', required=True)
    ap.add_argument('--week-start', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    ws = pd.Timestamp(a.week_start)

    x = pd.ExcelFile(a.bridge)
    br = pd.read_excel(x, 'Claude_Analysis_Data')
    br['分析報告開始'] = pd.to_datetime(br['分析報告開始'])
    is_lic = br['行銷活動名稱'].isna() | (br['行銷活動名稱'].astype(str).str.strip() == '-')
    keep = br[(br['分析報告開始'] < ws) | is_lic]
    cols = list(br.columns)

    tags = pd.read_excel(x, TAG_SHEET) if TAG_SHEET in x.sheet_names else pd.DataFrame(columns=['後台名稱', '原廠標記'])
    tags = tags.dropna(subset=['後台名稱'])
    by_name = {_clean(n): t for n, t in zip(tags['後台名稱'], tags['原廠標記']) if pd.notna(t)}
    by_row = {}
    for n, t in zip(tags['後台名稱'], tags['原廠標記']):
        m = re.search(r'R:(\d+)', str(n))
        if m and pd.notna(t):
            by_row[m.group(1)] = t

    def tag_for(name):
        c = _clean(name)
        if c in by_name:
            return by_name[c]
        m = re.search(r'R:(\d+)', c)
        if m and m.group(1) in by_row:
            return by_row[m.group(1)]
        return 'KOL' if c.startswith('A:KOL') else None

    frames = []
    for path, is_meta in ((a.meta_csv, True), (a.google_csv, False)):
        d = pd.read_csv(path)
        d['分析報告開始'] = pd.to_datetime(d['分析報告開始'])
        d = d[d['分析報告開始'] >= ws].copy()
        out = pd.DataFrame({c: [None] * len(d) for c in cols})
        for c in ['分析報告開始', '廣告名稱', '行銷活動名稱', '廣告組合名稱', '花費金額 (JPY)', '曝光次數',
                  '連結點擊次數', '購買次數', '購買轉換值', '加到購物車次數']:
            out[c] = d[c].values
        out['分析報告結束'] = out['分析報告開始']
        for c in ['每次購買成本 (JPY)', '購買 ROAS（廣告投資報酬率）', 'CTR（連結點閱率）', 'CPC（單次點擊成本） (JPY)',
                  'CPM（每千次廣告曝光成本） (JPY)', '頻率', '成果', '成果指標', '每次成果成本', '每次加到購物車的成本 (JPY)',
                  '廣告組合預算類型']:
            out[c] = 0
        out['廣告投遞'] = '-'
        out['廣告組合預算'] = '-'
        out['歸因設定'] = 'MCP' if is_meta else '-'
        out['原廠標記'] = [tag_for(n) for n in d['廣告名稱']] if is_meta else None
        frames.append(out)

    res = pd.concat([keep] + frames, ignore_index=True)
    with pd.ExcelWriter(a.out) as w:
        res.to_excel(w, sheet_name='Claude_Analysis_Data', index=False)
        for s in x.sheet_names:
            if s != 'Claude_Analysis_Data':
                pd.read_excel(x, s).to_excel(w, sheet_name=s, index=False)
    wk = res[res['分析報告開始'] >= ws]
    print(f'wrote {a.out}: {len(res)} rows; week rows {len(wk)}; week cost {wk["花費金額 (JPY)"].sum():,.0f}')


if __name__ == '__main__':
    main()
