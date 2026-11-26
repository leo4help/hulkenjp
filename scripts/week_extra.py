"""週報最後的「本週專題」區塊（2026-11-25 新增，W47 起）。

`extra_sections.json`（專案根目錄，key = 報告週起始日 YYYY-MM-DD，值 = 區塊陣列）登錄的專題，
會插在 Part 3 Recap 之後、報告最末，nav 也加對應連結。沒登錄的週不出現。每次建置先清掉舊區塊。

區塊格式：
{"id": "edm", "nav": "專題 · 黑五 EDM", "title": str, "tag": str, "lead": str,
 "table": {"head": [...], "rows": [[...], ...], "note": str},
 "bullets": [str, ...],          # **粗體** → <b>
 "reco_title": str, "reco": [str, ...], "foot": str}

單獨執行：python3 scripts/week_extra.py --html 2026W47/hulken_week47_report.html --week 2026-11-19
"""
import argparse, html as _h, json, os, re

BEGIN, END = '<!-- WEEK-EXTRA:BEGIN -->', '<!-- WEEK-EXTRA:END -->'
NAV_RE = re.compile(r'\n\s*<a href="#[^"]+" data-extra-nav>[^<]*</a>')
CSS_MARK = '/* week-extra */'
CSS = CSS_MARK + '''
  .ex-card{background:#fff;border:1px solid var(--line);border-left:5px solid #3d6fb6;border-radius:14px;padding:20px 22px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:12px;margin-bottom:18px;}
  .ex-card h3{margin:0;font-size:19px;font-weight:800;color:var(--brand-deep);}
  .ex-tag{font-size:12px;font-weight:700;color:#3d6fb6;}
  .ex-lead{margin:0;font-size:14px;line-height:1.8;}
  .ex-tbl{overflow-x:auto;border:1px solid var(--line);border-radius:10px;}
  .ex-tbl table{border-collapse:collapse;width:100%;font-size:13px;}
  .ex-tbl th,.ex-tbl td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;}
  .ex-tbl th{background:#faf6ef;font-weight:700;color:var(--ink-soft);}
  .ex-tbl th:first-child,.ex-tbl td:first-child{text-align:left;}
  .ex-tbl tr:last-child td{border-bottom:0;}
  .ex-note{font-size:12px;color:var(--ink-soft);line-height:1.7;margin:0;}
  .ex-list{margin:0;padding-left:1.2em;display:flex;flex-direction:column;gap:6px;font-size:13.5px;line-height:1.75;}
  .ex-reco{background:#f3f7fd;border-radius:10px;padding:12px 16px;}
  .ex-reco b.t{display:block;margin-bottom:4px;color:#2b5592;}
/* week-extra end */
'''

def md(s):
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', _h.escape(str(s)))

def load(path, week):
    if not os.path.exists(path):
        return []
    return json.load(open(path, encoding='utf-8')).get(week, [])

def block(d):
    t = d.get('table')
    tbl = ''
    if t:
        tbl = ('<div class="ex-tbl"><table><thead><tr>' + ''.join(f'<th>{md(h)}</th>' for h in t['head']) +
               '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{md(c)}</td>' for c in r) + '</tr>' for r in t['rows']) +
               '</tbody></table></div>' + (f'<p class="ex-note">{md(t["note"])}</p>' if t.get('note') else ''))
    bl = ('<ul class="ex-list">' + ''.join(f'<li>{md(b)}</li>' for b in d.get('bullets', [])) + '</ul>') if d.get('bullets') else ''
    rc = ''
    if d.get('reco'):
        rc = (f'<div class="ex-reco"><b class="t">{md(d.get("reco_title","建議"))}</b><ol class="ex-list">' +
              ''.join(f'<li>{md(x)}</li>' for x in d['reco']) + '</ol></div>')
    foot = f'<p class="ex-note">{md(d["foot"])}</p>' if d.get('foot') else ''
    return (f'<section id="{d["id"]}"><div class="ex-card"><span class="ex-tag">{md(d.get("tag",""))}</span>'
            f'<h3>{md(d["title"])}</h3><p class="ex-lead">{md(d.get("lead",""))}</p>{tbl}{bl}{rc}{foot}</div></section>')

def apply(html, blocks):
    if BEGIN in html:
        html = html[:html.index(BEGIN)] + html[html.index(END) + len(END):]
    html = NAV_RE.sub('', html)
    if not blocks:
        return html
    if CSS_MARK not in html:
        html = html.replace('</style>', CSS + '</style>', 1)
    body = BEGIN + '\n  <div class="part-head" id="partX"><h2>本週專題</h2><span>額外分析與建議</span></div>\n  ' + \
           '\n  '.join(block(b) for b in blocks) + '\n' + END
    anchor = '\n</div>\n<div id="lightbox"'
    assert anchor in html, 'report end anchor not found'
    html = html.replace(anchor, '\n' + body + anchor, 1)
    nav = ''.join(f'\n  <a href="#{b["id"]}" data-extra-nav>{_h.escape(b.get("nav", b["title"]))}</a>' for b in blocks)
    html = html.replace('\n</div></nav>', nav + '\n</div></nav>', 1)
    return html

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--html', required=True); ap.add_argument('--week', required=True)
    a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    h = open(a.html, encoding='utf-8').read()
    h = apply(h, load(os.path.join(root, 'extra_sections.json'), a.week))
    open(a.html, 'w', encoding='utf-8').write(h); print('ok')
