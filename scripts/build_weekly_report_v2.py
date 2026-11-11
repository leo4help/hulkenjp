"""
Hulken JP 週報 v2（W45 起，2026-11-11 使用者指定的新格式）。

版面：
  Part 1 Overview：8 週平台營收堆疊長條（Shopify / Amazon / 樂天）＋廣告花費折線；
                   標準表格（三組可展開到渠道，Google 再展開品牌／非品牌）。
  Part 2：(C) Amazon → (B) 樂天 → (A) 官網，每組 6 張 8 週趨勢圖＋標準表格＋空白洞察表；
          C 另含 Amazon 品牌／非品牌與排除建議；A 另含 Meta 素材表（高於／低於平均、樣本不足、原廠標記篩選）。
  Part 3：Recap & Action Plan（空白，線上編輯）。

口徑：
  (A) Meta＋Google（品牌／非品牌）＋ChatGPT ｜ 平台 = Shopify（營收 total_sales、CVR = 訂單 / 工作階段）
      花費不含 KOL 授權金；含授權金的 ROAS 以小字顯示。
  (B) 樂天 RPP（720 小時歸因）＋樂天 TDA（照報表） ｜ 平台 = R-Karte 売上／アクセス人数／転換率
  (C) Amazon SP（搜尋字詞報表） ｜ 平台 = Seller Central 已訂購商品銷售額／工作階段
  平台指標只放在組別層級（平台營收是全店合計，各廣告平台的歸因互相重疊，無法拆到渠道）。

輸入（<week>/_data/）：groupA_weekly.json、groupBC_weekly.json、meta_creatives_w45.json（檔名依週次）
用法：python3 scripts/build_weekly_report_v2.py 2026W45 2026-11-05
"""
import json, sys, os, re, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import amazon_search_terms as amz
import insight_section as ins

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
folder, wstart = sys.argv[1], dt.date.fromisoformat(sys.argv[2])
wnum = int(folder[-2:]); wend = wstart + dt.timedelta(6)
D = os.path.join(ROOT, folder, '_data')
A = json.load(open(os.path.join(D, 'groupA_weekly.json'), encoding='utf-8'))
BC = json.load(open(os.path.join(D, 'groupBC_weekly.json'), encoding='utf-8'))
CR = json.load(open(os.path.join(D, f'meta_creatives_w{wnum}.json'), encoding='utf-8'))
LIC = json.load(open(os.path.join(D, 'kol_license_week.json'), encoding='utf-8'))
weeks = [a['week'] for a in A]
starts = [dt.date.fromisoformat(wstart.isoformat()) - dt.timedelta(7 * (len(A) - 1 - i)) for i in range(len(A))]
labels = [f"{w}\n{s.month}/{s.day}" for w, s in zip(weeks, starts)]

# ---------- Amazon 品牌 / 非品牌 ----------
hist = amz.history(os.path.join(ROOT, 'amazon_data'), wend.isoformat())
h8 = hist[hist['week'] >= pd.Timestamp(starts[0])]
amzSide = {}
for side in ['品牌', '非品牌']:
    s = h8[h8['side'] == side].groupby('week')[['cost', 'sales', 'impr', 'clicks', 'orders']].sum()
    amzSide[side] = [dict(cost=round(float(s.loc[pd.Timestamp(d), 'cost'])) if pd.Timestamp(d) in s.index else 0,
                          rev=round(float(s.loc[pd.Timestamp(d), 'sales'])) if pd.Timestamp(d) in s.index else 0,
                          imp=int(s.loc[pd.Timestamp(d), 'impr']) if pd.Timestamp(d) in s.index else 0,
                          clicks=int(s.loc[pd.Timestamp(d), 'clicks']) if pd.Timestamp(d) in s.index else 0,
                          conv=int(s.loc[pd.Timestamp(d), 'orders']) if pd.Timestamp(d) in s.index else 0) for d in starts]
ex = amz.exclusion_candidates(hist, wstart.isoformat())
amzEx = [dict(term=r.term, seg=r.seg, cost=round(r.cost), orders=int(r.orders), weeks=int(r.weeks),
              cur=round(r.curCost), action=r.action) for r in ex.itertuples()]

# ---------- creatives ----------
for c in CR:
    if not c.get('tag') and c['kol']:
        c['tag'] = 'KOL'
    c['nameRow'] = f"A:{c['name']}-{c['row']}"
    c['type'] = '再入荷 RT' if 'RT' in c['flags'] else ('TEST' if c['flags'] == ['T'] else ('General' if c['flags'] == ['G'] else '/'.join(c['flags'])))
metaW = A[-1]['channels']['Meta']
avgRoas = metaW['rev'] / metaW['cost']

data = dict(weeks=weeks, labels=labels, A=A, B=BC['B'], C=BC['C'], amzSide=amzSide, amzEx=amzEx,
            creatives=CR, avgRoas=avgRoas, minSpend=5000, lic=LIC,
            amzNote=BC['C'][-1]['platform'].get('note', ''))

# ---------- template pieces from the previous report ----------
prev = sorted(f for f in os.listdir(ROOT) if re.fullmatch(r'2026W\d\d', f) and f < folder)[-1]
prev_html = open(os.path.join(ROOT, prev, f'hulken_week{int(prev[-2:])}_report.html'), encoding='utf-8').read()
css = prev_html[prev_html.find('<style>') + 7: prev_html.find('</style>')]
title_range = f"{wstart:%Y/%m/%d} – {wend:%Y/%m/%d}"
today = dt.date.today()

CSS2 = r"""
  .part-head{margin:44px 0 0;padding:14px 18px;border-radius:12px;background:linear-gradient(135deg,var(--brand-deep),#5b4a2f);color:#fff;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;}
  .part-head h2{margin:0;font-size:20px;font-weight:800;color:#fff;}
  .part-head span{font-size:12.5px;color:rgba(255,255,255,.75);font-weight:600;}
  .grp-badge{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:7px;background:var(--brand-gold);color:#fff;font-weight:800;font-size:14px;margin-right:8px;vertical-align:2px;}
  .chart-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
  @media (max-width:980px){.chart-grid{grid-template-columns:repeat(2,1fr);}}
  @media (max-width:640px){.chart-grid{grid-template-columns:1fr;}}
  .mini{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 12px 6px;box-shadow:var(--shadow);}
  .mini h4{margin:0 0 2px;font-size:13px;color:var(--brand-deep);font-weight:800;}
  .mini .lg{font-size:11px;color:var(--ink-soft);display:flex;gap:10px;flex-wrap:wrap;min-height:16px;}
  .mini .lg i{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:4px;vertical-align:middle;}
  .mini svg,.big-chart svg{display:block;width:100%;height:auto;overflow:visible;}
  .big-chart{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:var(--shadow);}
  .big-chart .lg{font-size:12px;color:var(--ink-soft);display:flex;gap:14px;flex-wrap:wrap;margin-bottom:6px;}
  .big-chart .lg i{display:inline-block;width:12px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px;}
  table.std td .sub{display:block;font-size:10.5px;color:var(--ink-faint);font-weight:600;margin-top:1px;}
  table.std td .dl{display:block;font-size:10.5px;font-weight:700;margin-top:1px;}
  table.std td .dl.up{color:var(--good);} table.std td .dl.down{color:var(--bad);} table.std td .dl.flat{color:var(--ink-faint);}
  table.std tr.lvl1 td:first-child{padding-left:30px;} table.std tr.lvl2 td:first-child{padding-left:52px;}
  table.std tr.lvl1 td,table.std tr.lvl2 td{background:#fbf8f1;}
  table.std tr.grp td{font-weight:700;}
  table.std td.na{color:var(--ink-faint);}
  .sub-h{font-size:14.5px;font-weight:800;color:var(--brand-deep);margin:26px 0 10px;}
  .cr-cnt{font-size:12px;color:var(--ink-faint);font-weight:600;margin-left:6px;}
  .lic-s{display:block;font-size:10.5px;color:var(--ink-faint);font-weight:600;}
  .tf-box{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 10px;font-size:12px;}
  .tf-box .tf-label{font-weight:800;color:var(--brand-deep);margin-right:4px;}
  .tf-box label{border:1px solid var(--line);border-radius:999px;padding:3px 10px;background:#fff;cursor:pointer;color:var(--ink-soft);}
  .tf-box label.on{background:var(--tan-soft);border-color:var(--brand-gold);color:var(--brand-deep);font-weight:700;}
  .tf-box input{display:none;}
  .tf-box button{border:1px solid var(--line);background:#fff;border-radius:8px;padding:3px 10px;font:inherit;font-size:12px;cursor:pointer;}
  .pub-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-left:auto;margin-right:12px;}
  .pub-badge{font-size:12.5px;font-weight:800;color:#a3561c;background:#fff4e2;border:1px solid #e8c48a;border-radius:999px;padding:5px 12px;}
  .pub-badge.on{color:var(--good);background:#eaf6ef;border-color:#a9d8bd;}
  .pub-meta{font-size:11.5px;color:var(--ink-soft);}
  .beta-badge.arch{background:#fde3d7;color:#a3401c;border-color:#e9a98c;}
  .type-pill{display:inline-block;font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:6px;background:var(--tan-soft);color:var(--brand-deep);}
  .tag-pill{display:inline-block;font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:6px;border:1px solid var(--tan);color:var(--ink-soft);background:#fff;}
"""

def part(pid, title, tag):
    return f'<div class="part-head" id="{pid}"><h2>{title}</h2><span>{tag}</span></div>'

def ins_block(key, title, tag):
    return (f'<div class="ins-block" data-ins-block="{key}"><div class="ins-block-head"><h3>{title}</h3><span class="ins-tag">{tag}</span></div>'
            '<div class="ins-bar"><button class="ins-btn primary ins-edit" style="display:none">✎ 編輯</button><span class="ins-status"></span><span style="flex:1"></span></div>'
            f'<div class="card" style="padding:0;overflow:hidden;"><div class="table-scroll" style="border:none;border-radius:0;"><table class="ins-table" data-ins-table="{key}"></table></div></div></div>')

def group_section(g, badge, title, platform, extra=''):
    return f'''
  <section id="grp{g}">
    <div class="sec-head"><h2><span class="grp-badge">{badge}</span>{title}</h2><span class="sec-tag">平台：{platform} · 8 週趨勢（{weeks[0]}–{weeks[-1]}）</span></div>
    <div class="chart-grid" id="charts{g}"></div>
    <div class="sub-h">本週成效（WoW）</div>
    <div class="table-scroll"><table class="std" id="tbl{g}"></table></div>
    <div class="hint" id="hint{g}"></div>
    {extra}
    {ins_block('group' + g, '核心洞察 / 執行建議', f'({badge}) {title}')}
  </section>'''

extraC = '''
    <div class="sub-h">Amazon 品牌 / 非品牌（本週 vs 上週）</div>
    <div class="table-scroll"><table class="std" id="tblAmzSide"></table></div>
    <div class="hint">品牌 = 品牌字（hulken／ハルケン…）＋自家 ASIN；其餘為非品牌。資料為 SP 搜尋字詞報表（主控台匯出上限 300 列，極小字詞不在內）。</div>
    <div class="sub-h">建議排除清單（非品牌，累計花費 > ¥5,000 且 0 單，或 > ¥10,000 且 ≤ 1 單）</div>
    <div class="table-scroll"><table class="std" id="tblAmzEx"></table></div>'''

extraA = '''
    <div class="sub-h">Meta 素材表現（本週）<span class="cr-cnt" id="crAvgNote"></span></div>
    <div class="tf-box" id="crTagFilter"></div>
    <div class="sub-h" style="margin-top:12px">ROAS 高於平均<span class="cr-cnt" id="cntHi"></span></div>
    <div class="table-scroll"><table class="std" id="tblCrHi"></table></div>
    <div class="sub-h">ROAS 低於平均<span class="cr-cnt" id="cntLo"></span></div>
    <div class="table-scroll"><table class="std" id="tblCrLo"></table></div>
    <div class="sub-h">樣本不足（本週花費 &lt; ¥5,000）<span class="cr-cnt" id="cntSm"></span></div>
    <div class="table-scroll"><table class="std" id="tblCrSm"></table></div>
    <div class="hint">平均 = 本週 Meta 帳戶媒體 ROAS（不含 KOL 授權金）。ROAS 下方小字為含本週授權金攤提的 ROAS（僅有授權金的 KOL 素材）。WoW 以同一 Row 上週全部 Meta 媒體花費為基準。</div>'''

html = f'''<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HULKEN JP · Week {wnum} 廣告成效週報</title>
<style>{css}{CSS2}</style>
</head>
<body>
<div id="cursorGlow"></div>
<header class="top">
  <div class="header-inner">
    <div class="logo-row"><div class="logo-block">HULKEN<sup>®</sup></div><div class="logo-jp">JP</div></div>
    <div class="week-picker" id="weekPicker">
      <div class="meta-chip" id="weekPickerToggle">Week {wnum} · {title_range} <span class="caret">▼</span></div>
      <div class="week-menu" id="weekMenu"></div>
    </div>
  </div>
  <div class="header-inner" style="margin-top:6px;">
    <div class="title-block">
      <h1>廣告成效週報</h1>
      <div class="sub">整理人：Leo · 更新日期 {today:%Y/%m/%d} · 資料來源：Meta／Google／Shopify MCP、ChatGPT Ads API、樂天 RMS／R-Karte／RPP・TDA 報表、Amazon Seller Central／SP 搜尋字詞報表</div>
    </div>
    <div class="pub-bar" id="pubBar" hidden></div>
    <a class="kol-header-btn" href="https://hulkenjp.pages.dev/all" target="_blank" rel="noopener">完整成效 & KOL 授權計算機 ↗</a>
  </div>
</header>
<nav class="secnav"><div class="inner">
  <a href="#overview">Part 1 · Overview</a>
  <a href="#grpC">(C) Amazon</a>
  <a href="#grpB">(B) 樂天</a>
  <a href="#grpA">(A) 官網</a>
  <a href="#recap">Part 3 · Recap &amp; Action Plan</a>
</div></nav>
<div class="wrap">
  {part('part1', 'Part 1 · Overview', '三通路整體表現')}
  <section id="overview">
    <div class="sec-head"><h2>平台營收與廣告花費</h2><span class="sec-tag">8 週 · 每週四至週三</span></div>
    <div class="big-chart" id="ovChart"></div>
    <div class="sub-h">本週成效（WoW，點組別可展開）</div>
    <div class="table-scroll"><table class="std" id="ovTable"></table></div>
    <div class="hint">廣告 ROAS = 廣告平台歸因營收 ÷ 廣告花費；平台 ROAS = 平台營收 ÷ 該組廣告花費。平台營收與平台 CVR 只放在組別層級：平台營收是全店合計，各廣告平台的歸因互相重疊，拆到渠道會重複計算。(A) 花費不含 KOL 授權金，含授權金的 ROAS 以小字顯示。<span id="ovNote"></span></div>
  </section>
  {part('part2', 'Part 2 · 各通路', '(C) Amazon → (B) 樂天 → (A) 官網')}
  {group_section('C', 'C', 'Amazon', 'Amazon（Seller Central 已訂購商品銷售額）', extraC)}
  {group_section('B', 'B', '樂天', '樂天（R-Karte 売上）')}
  {group_section('A', 'A', '官網', 'Shopify（總銷售額）', extraA)}
  {part('part3', 'Part 3 · Recap &amp; Action Plan', '本週總結與下週行動')}
  <section id="recap" data-ins-v="2">
    {ins_block('recap', 'Recap', '本週總結')}
    <div class="ins-sub">下週 Action Plan</div>
    <div class="card" id="insActions"></div>
  </section>
</div>
<div id="lightbox" onclick="this.style.display='none'"><img id="lightboxImg" alt=""></div>
<script>
const THIS_REPORT_FILE = '{folder}/hulken_week{wnum}_report.html';
const R = {json.dumps(data, ensure_ascii=False)};
'''
html += open(os.path.join(ROOT, 'scripts', 'report_v2.js'), encoding='utf-8').read()
js = ins.JS.replace("KEYS=['overall','metaTest','metaCreative','kol','shopify']", "KEYS=['groupC','groupB','groupA','recap']")
js = js.replace("k==='overall'", "k==='recap'").replace("blocks.overall", "blocks.recap").replace("{overall:{rows:o.rows||[],actions:o.actions||[]}}", "{recap:{rows:o.rows||[],actions:o.actions||[]}}")
js = js.replace("k!=='overall'", "k!=='recap'").replace("全部五個", "全部")
js = js.replace("const INSIGHT_WEEK = '';", f"const INSIGHT_WEEK = '{wstart.isoformat()}';")
builtin = json.load(open(os.path.join(ROOT, 'insights.json'), encoding='utf-8')).get(wstart.isoformat(), {})
js = js.replace("const INSIGHTS_BUILTIN = {};", "const INSIGHTS_BUILTIN = " + json.dumps(builtin, ensure_ascii=False) + ";")
html += js + '\n</script>\n</body>\n</html>\n'
out = os.path.join(ROOT, folder, f'hulken_week{wnum}_report.html')
open(out, 'w', encoding='utf-8').write(html)
print('wrote', out, len(html))
