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
  .hl-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:-4px 0 8px;}
  .hl-status{font-size:12px;color:var(--ink-soft);}
  .hl-form{display:flex;flex-direction:column;gap:8px;}
  .hl-form label{font-size:12px;font-weight:700;color:var(--ink-soft);}
  .hl-form input,.hl-form textarea{width:100%;box-sizing:border-box;border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:inherit;font-size:13.5px;line-height:1.6;}
  .hl-form .hl-brow{display:flex;gap:6px;align-items:flex-start;}
  .hl-form .hl-note{font-size:12px;color:var(--ink-soft);}
/* week-highlight end */
'''
JS_MARK = '/* week-highlight editor */'
JS = """
/* week-highlight editor */
(function(){
  const sec=document.getElementById('highlight'); if(!sec) return;
  const WEEK=sec.dataset.week, API='/api/highlights';
  const $=id=>document.getElementById(id);
  const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const md=s=>esc(s).replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>');
  let BUILTIN={title:'',lead:'',bullets:[]}; try{BUILTIN=JSON.parse($('hlBuiltin').textContent)}catch(e){}
  let remote=null, canEdit=false, editing=false;
  const cur=()=>remote||BUILTIN;
  function show(){
    const d=cur();
    $('hlTitle').textContent=d.title||'';
    $('hlLead').innerHTML=md(d.lead||''); $('hlLead').hidden=!d.lead||editing;
    $('hlBullets').innerHTML=(d.bullets||[]).map(b=>'<li>'+md(b)+'</li>').join(''); $('hlBullets').hidden=editing;
    $('hlTitle').hidden=editing; $('hlForm').hidden=!editing;
    $('hlEditBtn').hidden=!canEdit; $('hlEditBtn').textContent=editing?'✓ 儲存':'✎ 編輯文字';
    $('hlRevertBtn').hidden=!(canEdit&&remote&&!editing);
    $('hlStatus').textContent=remote?('線上修改版本'+(remote._by?' · '+remote._by:'')+(remote._at?' · '+remote._at.replace('T',' ').replace('Z',' UTC'):'')):'';
  }
  function form(){
    const d=cur(), bs=(d.bullets||[]).slice(); if(!bs.length) bs.push('');
    $('hlForm').innerHTML='<label>標題</label><input id="hlFTitle" value="'+esc(d.title||'')+'">'
      +'<label>導言（**文字** = 粗體）</label><textarea id="hlFLead" rows="3">'+esc(d.lead||'')+'</textarea>'
      +'<label>重點（每格一條；清空即刪除）</label><div id="hlFBullets">'
      +bs.map(b=>'<div class="hl-brow"><textarea rows="2">'+esc(b)+'</textarea></div>').join('')+'</div>'
      +'<div><button class="ins-btn" id="hlAddB" type="button">＋ 新增一條</button> <button class="ins-btn" id="hlCancel" type="button">取消</button></div>'
      +'<div class="hl-note">圖表依數據產生，不開放編輯。</div>';
    $('hlAddB').onclick=()=>{const r=document.createElement('div');r.className='hl-brow';r.innerHTML='<textarea rows="2"></textarea>';$('hlFBullets').appendChild(r)};
    $('hlCancel').onclick=()=>{editing=false;show()};
  }
  async function save(){
    const data={title:$('hlFTitle').value,lead:$('hlFLead').value,bullets:[...$('hlFBullets').querySelectorAll('textarea')].map(t=>t.value).filter(v=>v.trim())};
    $('hlStatus').textContent='儲存中…';
    const r=await fetch(API,{method:'PUT',credentials:'same-origin',headers:{'content-type':'application/json'},body:JSON.stringify({week:WEEK,data})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok){$('hlStatus').textContent='儲存失敗：'+(j.error||r.status);return false}
    remote=j.item; return true;
  }
  $('hlEditBtn').onclick=async()=>{ if(editing){ if(await save()){editing=false;show()} } else {editing=true;form();show()} };
  $('hlRevertBtn').onclick=async()=>{
    if(!confirm('把本週 Highlight 文字還原成建置時的原始版本？（所有人都會看到還原後的內容）'))return;
    const r=await fetch(API+'?week='+encodeURIComponent(WEEK),{method:'DELETE',credentials:'same-origin'});
    if(r.ok){remote=null;show()}else alert('還原失敗：HTTP '+r.status);
  };
  show();
  if(location.protocol.startsWith('http')) fetch(API,{cache:'no-store',credentials:'same-origin'}).then(r=>r.ok?r.json():null).then(j=>{
    if(!j)return; canEdit=!!j.canEdit; remote=(j.highlights||{})[WEEK]||null; show();
  }).catch(()=>{});
})();
"""


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


def _section(hl, week=''):
    text = {'title': hl.get('title', ''), 'lead': hl.get('lead', ''), 'bullets': list(hl.get('bullets') or [])}
    parts = [f'<h3 id="hlTitle">{_e(text["title"])}</h3>',
             f'<p class="hl-lead" id="hlLead"{"" if text["lead"] else " hidden"}>{_md(text["lead"])}</p>',
             '<div class="hl-form" id="hlForm" hidden></div>']
    if hl.get('chart'):
        parts.append(_svg(hl['chart']))
    parts.append('<ul class="hl-list" id="hlBullets">' + ''.join(f'<li>{_md(b)}</li>' for b in text['bullets']) + '</ul>')
    builtin = json.dumps(text, ensure_ascii=False).replace('</', '<\\/')
    return (f'  <section id="highlight" data-week="{_e(week)}">\n'
            '    <div class="sec-head"><h2>本週 Highlight</h2><span class="sec-tag">本週最需要先知道的事</span></div>\n'
            '    <div class="hl-bar"><button class="ins-btn primary" id="hlEditBtn" hidden>✎ 編輯文字</button>'
            '<button class="ins-btn danger" id="hlRevertBtn" hidden>還原原始版本</button><span class="hl-status" id="hlStatus"></span></div>\n'
            f'    <div class="hl-card">{"".join(parts)}</div>\n'
            f'    <script type="application/json" id="hlBuiltin">{builtin}</script>\n  </section>')


def apply(html, hl, week=''):
    i, j = html.find(BEGIN), html.find(END)
    if i >= 0 and j > i:
        a = i - 2 if html[i - 2:i] == '  ' else i
        b = j + len(END)
        b += 1 if html[b:b + 1] == '\n' else 0
        html = html[:a] + html[b:]
    html = NAV_RE.sub('', html)
    if not hl:
        return html
    if CSS_MARK in html:  # 每次換成最新版 CSS（舊版沒有 end 標記時刪到 .hl-list 那行）
        c0 = html.find(CSS_MARK)
        c1 = html.find('/* week-highlight end */', c0)
        c1 = c1 + len('/* week-highlight end */\n') if c1 >= 0 else html.find('\n', html.find('.hl-list{', c0)) + 1
        html = html[:c0] + html[c1:]
    k = html.find('</style>')
    html = html[:k] + CSS + html[k:]
    s = html.find('<section id="overview"')
    if s < 0:
        raise SystemExit('week_highlight: #overview section not found')
    ls = html.rfind('\n', 0, s) + 1
    block = f'  {BEGIN}\n{_section(hl, week)}\n  {END}\n'
    html = html[:ls] + block + html[ls:]
    if JS_MARK not in html:
        j2 = html.rfind('</script>')
        html = html[:j2] + JS + html[j2:]
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
    h = apply(h, load(a.highlights_json, a.week), a.week)
    with open(a.html, 'w', encoding='utf-8') as f:
        f.write(h)
    print('updated', a.html)
