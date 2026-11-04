"""本週 Highlight（2026-11-04 新增，W44 起）。

`highlights.json`（專案根目錄，key = 報告週起始日 YYYY-MM-DD）登錄的重點，會在週報最上方
「廣告成效討論 — Overview」之前產生 `<section id="highlight">`：標題、導言、一張線圖（inline SVG，
不靠外部套件）、幾條重點。nav 也會多一個「本週 Highlight」。每次建置先移除模板帶來的舊區塊，
所以只出現在登錄的那一週。

highlights.json 每週格式：
{"title": str, "lead": str,
 "chart": {"title": str, "unit": "萬円", "labels": [x 軸標籤...], "sublabels": [第二行標籤...],
           "series": [{"name": str, "values": [...], "main": true}, {"name": str, "values": [...]}],
           "band": [起 index, 迄 index], "bandLabel": str},
 "bullets": [str, ...]}     # 文字中 **粗體** 會轉成 <b>

單獨執行可就地更新已建好的週報：
    python3 scripts/week_highlight.py --html 2026W44/hulken_week44_report.html --week 2026-10-29
"""
import argparse, html as _h, json, os, re

BEGIN = '<!-- WEEK-HIGHLIGHT:BEGIN -->'
END = '<!-- WEEK-HIGHLIGHT:END -->'
NAV_RE = re.compile(r'\n\s*<a href="#highlight" data-hl-nav>[^<]*</a>')
CSS_MARK = '/* week-highlight */'
CSS = CSS_MARK + '''
  .hl-card{background:#fff;border:1px solid var(--line);border-left:5px solid var(--brand-gold,#a9822e);border-radius:14px;padding:20px 22px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:14px;}
  .hl-card h3{margin:0;font-size:19px;font-weight:800;color:var(--brand-deep);}
  .hl-lead{margin:0;font-size:14px;line-height:1.8;}
  .hl-chart{border:1px solid var(--line);border-radius:10px;padding:12px 10px 4px;background:#fffdf9;}
  .hl-chart-title{font-size:13px;font-weight:700;color:var(--ink-soft);margin:0 4px 6px;}
  .hl-legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--ink-soft);margin:0 4px 4px;}
  .hl-legend i{display:inline-block;width:22px;height:0;border-top:3px solid;vertical-align:middle;margin-right:6px;}
  .hl-chart{overflow-x:auto;}
  .hl-chart svg{width:100%;min-width:560px;height:auto;display:block;}
  .hl-list{margin:0;padding-left:1.2em;display:flex;flex-direction:column;gap:6px;font-size:13.5px;line-height:1.75;}
'''
COLORS = ['#a9822e', '#9a9184', '#63785a', '#b4442f']


def _e(s):
    return _h.escape(str(s if s is not None else ''))


def _md(s):
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', _e(s))


def _svg(ch):
    labels, subs = ch['labels'], ch.get('sublabels') or [''] * len(ch['labels'])
    series = ch['series']
    W, H, L, R, T, B = 760, 300, 56, 20, 24, 52
    pw, ph = W - L - R, H - T - B
    vals = [v for s in series for v in s['values'] if v is not None]
    hi = max(vals) * 1.12
    step = 10 ** max(0, len(str(int(hi))) - 2)
    for m in (1, 2, 2.5, 5, 10):
        if hi / (step * m) <= 5:
            step *= m
            break
    ymax = step * (int(hi / step) + 1)
    x = lambda i: L + (pw * i / (len(labels) - 1) if len(labels) > 1 else pw / 2)
    y = lambda v: T + ph - ph * v / ymax
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{_e(ch.get("title", ""))}">']
    if ch.get('band'):
        a, b = ch['band']
        x0, x1 = x(a) - pw / (len(labels) - 1) / 2.4, x(b) + pw / (len(labels) - 1) / 2.4
        out.append(f'<rect x="{x0:.1f}" y="{T}" width="{x1 - x0:.1f}" height="{ph}" fill="#b4442f" fill-opacity="0.07" rx="6"/>')
        if ch.get('bandLabel'):
            out.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{T + 14}" text-anchor="middle" font-size="12" font-weight="700" fill="#b4442f">{_e(ch["bandLabel"])}</text>')
    v = 0
    while v <= ymax + 1e-9:
        yy = y(v)
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#e7ded0"/>')
        out.append(f'<text x="{L - 8}" y="{yy + 4:.1f}" text-anchor="end" font-size="11" fill="#6b6255">{v:g}</text>')
        v += step
    out.append(f'<text x="{L - 8}" y="{T - 8}" text-anchor="end" font-size="11" fill="#6b6255">{_e(ch.get("unit", ""))}</text>')
    for i, (lb, sb) in enumerate(zip(labels, subs)):
        out.append(f'<text x="{x(i):.1f}" y="{H - 30}" text-anchor="middle" font-size="12" font-weight="700" fill="#2b2620">{_e(lb)}</text>')
        if sb:
            out.append(f'<text x="{x(i):.1f}" y="{H - 14}" text-anchor="middle" font-size="10.5" fill="#6b6255">{_e(sb)}</text>')
    for k, s in enumerate(series):
        col = s.get('color') or COLORS[k % len(COLORS)]
        main = s.get('main')
        pts = [(x(i), y(val)) for i, val in enumerate(s['values']) if val is not None]
        d = 'M' + ' L'.join(f'{px:.1f},{py:.1f}' for px, py in pts)
        dash = '' if main else ' stroke-dasharray="6 5"'
        out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{3 if main else 2.2}" stroke-linejoin="round"{dash}/>')
        for i, val in enumerate(s['values']):
            if val is None:
                continue
            out.append(f'<circle cx="{x(i):.1f}" cy="{y(val):.1f}" r="{4.5 if main else 3.2}" fill="{col}"/>')
            if main or s.get('labels'):
                out.append(f'<text x="{x(i):.1f}" y="{y(val) - 10:.1f}" text-anchor="middle" font-size="11.5" font-weight="{700 if main else 400}" fill="{col}">{val:g}</text>')
    out.append('</svg>')
    legend = ''.join(f'<span><i style="border-top-color:{s.get("color") or COLORS[k % len(COLORS)]};{"" if s.get("main") else "border-top-style:dashed;"}"></i>{_e(s["name"])}</span>'
                     for k, s in enumerate(series))
    return (f'<div class="hl-chart"><div class="hl-chart-title">{_e(ch.get("title", ""))}</div>'
            f'<div class="hl-legend">{legend}</div>{"".join(out)}</div>')


def _section(hl):
    parts = [f'<h3>{_e(hl["title"])}</h3>']
    if hl.get('lead'):
        parts.append(f'<p class="hl-lead">{_md(hl["lead"])}</p>')
    if hl.get('chart'):
        parts.append(_svg(hl['chart']))
    if hl.get('bullets'):
        parts.append('<ul class="hl-list">' + ''.join(f'<li>{_md(b)}</li>' for b in hl['bullets']) + '</ul>')
    return ('  <section id="highlight">\n'
            '    <div class="sec-head"><h2>本週 Highlight</h2><span class="sec-tag">本週最需要先知道的事</span></div>\n'
            f'    <div class="hl-card">{"".join(parts)}</div>\n  </section>')


def apply(html, hl):
    i, j = html.find(BEGIN), html.find(END)
    if i >= 0 and j > i:
        a = i - 2 if html[i - 2:i] == '  ' else i
        b = j + len(END)
        b += 1 if html[b:b + 1] == '\n' else 0
        html = html[:a] + html[b:]
    html = NAV_RE.sub('', html)
    if not hl:
        return html
    if CSS_MARK not in html:
        k = html.find('</style>')
        html = html[:k] + CSS + html[k:]
    s = html.find('<section id="overview"')
    if s < 0:
        raise SystemExit('week_highlight: #overview section not found')
    ls = html.rfind('\n', 0, s) + 1
    block = f'  {BEGIN}\n{_section(hl)}\n  {END}\n'
    html = html[:ls] + block + html[ls:]
    nav = '<a href="#overview">Overview 總覽</a>'
    if nav in html:
        html = html.replace(nav, '<a href="#highlight" data-hl-nav>本週 Highlight</a>\n    ' + nav, 1)
    return html


def load(path, week_key):
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f).get(week_key)
    return None


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True)
    ap.add_argument('--week', required=True)
    ap.add_argument('--highlights-json', default='highlights.json')
    a = ap.parse_args()
    with open(a.html, encoding='utf-8') as f:
        h = f.read()
    h = apply(h, load(a.highlights_json, a.week))
    with open(a.html, 'w', encoding='utf-8') as f:
        f.write(h)
    print('updated', a.html)
