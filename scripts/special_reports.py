"""專題報告卡片（2026-10-28 新增，W43 起）。

`reports.json`（專案根目錄，key = 報告週起始日 YYYY-MM-DD）裡列的專題報告，會在週報
「Insight & Suggestion（媒體與整體狀況）」區塊下方產生一張卡片 `<section id="review">`，
附摘要與「查看完整報告」連結（url 可以是外部網址，或同資料夾的相對路徑，例：W43 的 hulken_week43_report-add.html），nav 也會多一個「專題檢討」連結。

每次建置都會先移除模板帶過來的舊卡片，所以專題只出現在指定的那一週。
單獨執行可以就地更新已建好的週報：
    python3 scripts/special_reports.py --html 2026W43/hulken_week43_report.html --week 2026-10-22
"""
import argparse, html as _h, json, os, re

BEGIN = '<!-- SPECIAL-REPORTS:BEGIN -->'
END = '<!-- SPECIAL-REPORTS:END -->'
NAV_RE = re.compile(r'\n\s*<a href="#review" data-sr-nav>[^<]*</a>')
CSS_MARK = '/* special-reports card */'
CSS = CSS_MARK + '''
  .sr-card{background:var(--card,#fff);border:1px solid var(--line);border-left:5px solid var(--brand-gold,#a9822e);border-radius:14px;padding:20px 22px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:12px;}
  .sr-meta{font-size:12.5px;color:var(--ink-soft);}
  .sr-card h3{margin:0;font-size:18px;font-weight:800;color:var(--brand-deep);}
  .sr-lead{margin:0;font-size:14px;line-height:1.75;}
  .sr-list{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:8px;}
  .sr-list li{display:grid;grid-template-columns:64px 1fr;gap:10px;align-items:start;font-size:13.5px;line-height:1.7;}
  .sr-chip{display:inline-block;text-align:center;font-size:11.5px;font-weight:800;padding:2px 0;border-radius:999px;white-space:nowrap;}
  .sr-chip.find{background:#f8e3dd;color:#b4442f;}
  .sr-chip.out{background:#e2f0e7;color:#2e7a55;}
  .sr-chip.open{background:#f6eedb;color:#9a6a12;}
  .sr-foot{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;}
  .sr-btn{display:inline-flex;align-items:center;gap:6px;padding:10px 18px;border-radius:10px;background:linear-gradient(135deg,var(--brand-gold,#a9822e),#c79b3f);color:#fff;font-size:13.5px;font-weight:700;text-decoration:none;box-shadow:0 3px 10px rgba(169,130,46,.3);}
  .sr-btn:hover{transform:translateY(-1px);}
  .sr-note{font-size:12px;color:var(--ink-soft);}
'''
LABEL = {'find': '確認', 'out': '已排除', 'open': '待確認'}


def _card(r):
    e = lambda s: _h.escape(str(s or ''))
    items = ''.join(
        f'<li><span class="sr-chip {e(i.get("status", "find"))}">{e(i.get("label") or LABEL.get(i.get("status", "find"), ""))}</span><span>{e(i["text"])}</span></li>'
        for i in r.get('items', []))
    meta = '・'.join(x for x in [r.get('date'), r.get('source')] if x)
    return (f'<div class="sr-card">'
            + (f'<div class="sr-meta">{e(meta)}</div>' if meta else '')
            + f'<h3>{e(r["title"])}</h3>'
            + (f'<p class="sr-lead">{e(r["lead"])}</p>' if r.get('lead') else '')
            + (f'<ul class="sr-list">{items}</ul>' if items else '')
            + f'<div class="sr-foot"><a class="sr-btn" href="{e(r["url"])}"' + (' target="_blank" rel="noopener"' if str(r['url']).startswith('http') else '') + f'>{e(r.get("cta") or "查看完整檢討報告")} {"↗" if str(r["url"]).startswith("http") else "→"}</a>'
            + (f'<span class="sr-note">{e(r["note"])}</span>' if r.get('note') else '')
            + '</div></div>')


def apply(html, reports):
    """Remove any previous card/nav link, then add this week's (idempotent)."""
    i, j = html.find(BEGIN), html.find(END)
    if i >= 0 and j > i:
        a = i - 3 if html[i - 3:i] == '\n  ' else i
        b = j + len(END)
        b += 1 if html[b:b + 1] == '\n' else 0
        html = html[:a] + html[b:]
    html = NAV_RE.sub('', html)
    if not reports:
        return html
    if CSS_MARK not in html:
        k = html.find('</style>')
        html = html[:k] + CSS + html[k:]
    s = html.find('<section id="insight"')
    if s < 0:
        raise SystemExit('special_reports: #insight section not found')
    e = html.find('</section>', s) + len('</section>')
    cards = '\n'.join('    ' + _card(r) for r in reports)
    block = (f'\n  {BEGIN}\n  <section id="review">\n'
             f'    <div class="sec-head"><h2>專題檢討</h2><span class="sec-tag">本週另行調查的報告</span></div>\n'
             f'{cards}\n  </section>\n  {END}\n')
    html = html[:e] + block + html[e:]
    nav = '<a href="#insight">Insight &amp; Suggestion</a>'
    if nav in html:
        html = html.replace(nav, nav + '\n    <a href="#review" data-sr-nav>專題檢討</a>', 1)
    return html


def load(path, week_key):
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f).get(week_key, [])
    return []


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True)
    ap.add_argument('--week', required=True, help='report week start YYYY-MM-DD')
    ap.add_argument('--reports-json', default='reports.json')
    a = ap.parse_args()
    with open(a.html, encoding='utf-8') as f:
        h = f.read()
    h = apply(h, load(a.reports_json, a.week))
    with open(a.html, 'w', encoding='utf-8') as f:
        f.write(h)
    print('updated', a.html)
