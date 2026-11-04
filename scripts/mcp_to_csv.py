"""把 Meta / Google MCP 的查詢結果轉成 build_mcp_bridge.py 要的 CSV（W44 起，2026-11-04）。

Meta：ads_get_ad_entities（level=ad, time_increment="1", fields 見 CLAUDE.md）的結果。
      結果通常太大，Claude 會被存成 tool-results/*.txt（JSON：{"ad_entities": "<json 字串>"}），
      這個檔案只存在雲端，所以本腳本要在雲端跑（先用 device_stage_files 把本檔拿到雲端），
      輸出的 CSV 再用 device_commit_files 寫回週資料夾。
    python3 mcp_to_csv.py meta <tool-result.txt 或 .json> <out.csv>

Google：google-ads MCP search_search（resource=campaign, segments.date）的結果 JSON（{"result":[...]}）。
      欄位必須含 campaign.name, segments.date, metrics.cost_micros, metrics.impressions, metrics.clicks,
      metrics.conversions_by_conversion_date, metrics.conversions_value_by_conversion_date。
    python3 mcp_to_csv.py google <result.json> <out.csv>
"""
import json, sys
import pandas as pd


def _val(x):
    if isinstance(x, dict):
        x = x.get('value')
    return float(x) if x not in (None, '') else 0.0


def meta(path):
    d = json.load(open(path, encoding='utf-8'))
    e = d.get('ad_entities', d) if isinstance(d, dict) else d
    e = json.loads(e) if isinstance(e, str) else e
    if isinstance(e, dict):
        e = e.get('ad_entities', e)
    rows = [{
        '分析報告開始': r['date_start'], '廣告名稱': r['name'], '行銷活動名稱': r['campaign_name'],
        '廣告組合名稱': r.get('adset_name'), 'ad_id': r.get('id'),
        '花費金額 (JPY)': _val(r.get('amount_spent')), '曝光次數': _val(r.get('impressions')),
        '連結點擊次數': _val(r.get('link_click')), '購買次數': _val(r.get('omni_purchase')),
        '購買轉換值': _val(r.get('offsite_conversion_fb_pixel_purchase_values')),
        '加到購物車次數': _val(r.get('omni_add_to_cart')),
    } for r in e]
    return pd.DataFrame(rows)


def google(path):
    d = json.load(open(path, encoding='utf-8'))
    rows = [{
        '分析報告開始': r['segments.date'], '廣告名稱': r['campaign.name'], '行銷活動名稱': r['campaign.name'],
        '廣告組合名稱': '-', '花費金額 (JPY)': r['metrics.cost_micros'] / 1e6,
        '曝光次數': r['metrics.impressions'], '連結點擊次數': r['metrics.clicks'],
        '購買次數': r['metrics.conversions_by_conversion_date'],
        '購買轉換值': r['metrics.conversions_value_by_conversion_date'], '加到購物車次數': 0,
    } for r in d.get('result', d)]
    return pd.DataFrame(rows)


if __name__ == '__main__':
    kind, src, out = sys.argv[1:4]
    df = meta(src) if kind == 'meta' else google(src)
    df.to_csv(out, index=False, encoding='utf-8')
    print(len(df), 'rows')
    print(df.groupby('分析報告開始')[['花費金額 (JPY)', '購買次數', '購買轉換值']].sum().round(0).to_string())
