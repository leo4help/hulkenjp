#!/usr/bin/env python3
"""build_shopify_section.py — 週報最後一段改放 Shopify 官網週數據（W39 起，2026-09-30 使用者要求）。

用法（在 build_weekly_report.py 之後跑，直接改寫當週 HTML）：
  python3 scripts/build_shopify_section.py \
    --html 2026W39/hulken_week39_report.html \
    --shopify-csv "2026W39/SP - 2026-01-01 - 2026-09-30.csv" \
    --cache _cache/ad_data_historical_cache.pkl.gz \
    --bridge 2026W39/Hulken_Claude_Bridge.xlsx --bridge-cutoff 2026-09-24 \
    --week-num 39

做的事：
  1. 移除「近期 KOL 表現討論」(#kol-discuss) 手動分析區塊（HTML section、nav 連結、
     KOL_CAT_ADS / KOL_MONTH_ADS 相關 JS）。若 HTML 裡已經有 Shopify 區塊（例如用本
     週當範本做下週），則改為整段替換成最新數字 —— 可重複執行。
  2. 插入 #shopify 區塊：當週 KPI tiles（WoW）、兩張週趨勢圖、全年週表。

方法論（使用者 2026-09-30 指定）：
  - Shopify 匯出為 Daily（欄位：日／工作階段數／訂單數／總銷售額），依報告週期
    「週四～週三」彙整成週：W1 = 2026-01-01(四)~01-07，週次 = (日期-2026-01-01)//7 + 1，
    與廣告週報的 Week_1st_day 完全對齊（W39 = 09-24~09-30）。
  - Shopify 銷售主要由 Meta 廣告帶動（其他渠道導去 Amazon／樂天等其他商城），
    所以 Shopify ROAS 只用 Meta 花費當分母：Shopify ROAS = Shopify 總銷售額 ÷ Meta 廣告花費。
  - Meta 廣告花費 = ad_data 中 AD_Channel=='Meta AD' 且 goal != '-'（含 CPC，不含 KOL
    授權金幽靈列），與 Weekly Report Manual 的 Meta 列口徑一致（W39 已核對 = 1,739,157）。
    另外附「含授權金」ROAS 小字 = 銷售額 ÷ (Meta 花費 + Meta 授權金幽靈列)。
  - Meta 後台回報 ROAS = 同範圍 購買轉換值 ÷ Meta 花費，僅作對照（歸因口徑不同）。
"""
import argparse
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_weekly_report import enrich, pct_delta, COST, REV, DATE  # noqa: E402

YEAR_START = pd.Timestamp('2026-01-01')  # Thursday — report weeks run Thu–Wed
# Weeks with (almost) no Meta spend get no ROAS — e.g. W1 had ¥289 of Meta spend, which
# would print a meaningless ROAS of ~1,600 and flatten the chart.
MIN_META_COST = 10000


def week_no(s):
    return (s - YEAR_START).dt.days // 7 + 1


def load_meta_weekly(cache, bridge, cutoff):
    c = pd.read_pickle(cache, compression='gzip')
    b = enrich(pd.read_excel(bridge, sheet_name='Claude_Analysis_Data'))
    b = b[b[DATE] >= cutoff]
    common = [x for x in c.columns if x in b.columns]
    ad = pd.concat([c[common], b[common]], ignore_index=True).drop_duplicates()
    ad[DATE] = pd.to_datetime(ad[DATE])
    ad = ad[(ad['AD_Channel'] == 'Meta AD') & (ad[DATE] >= YEAR_START)]
    ad['wk'] = week_no(ad[DATE])
    media = ad[ad['goal'] != '-'].groupby('wk').agg(metaCost=(COST, 'sum'), metaRev=(REV, 'sum'))
    lic = ad[ad['goal'] == '-'].groupby('wk').agg(metaLic=(COST, 'sum'))
    return media.join(lic, how='outer').fillna(0)


def load_shopify_weekly(path):
    s = pd.read_csv(path)
    s.columns = ['date', 'sessions', 'orders', 'sales']
    s['date'] = pd.to_datetime(s['date'])
    s['wk'] = week_no(s['date'])
    return s.groupby('wk').agg(sessions=('sessions', 'sum'), orders=('orders', 'sum'),
                               sales=('sales', 'sum'), days=('date', 'count'),
                               start=('date', 'min'))


def div(a, b):
    return None if not b else a / b


def r(x, nd=2):
    return None if x is None else round(float(x), nd)


def build_rows(shop, meta, last_wk):
    df = shop.join(meta, how='left').fillna({'metaCost': 0, 'metaRev': 0, 'metaLic': 0})
    df = df[df.index <= last_wk]
    rows, prev = [], None
    for wk, x in df.iterrows():
        start = YEAR_START + pd.Timedelta(days=7 * (wk - 1))
        end = start + pd.Timedelta(days=6)
        cur = {
            'wk': int(wk),
            'range': f"{start:%m/%d}–{end:%m/%d}",
            'days': int(x.days),
            'sessions': int(x.sessions), 'orders': int(x.orders), 'sales': float(x.sales),
            'aov': div(x.sales, x.orders), 'cvr': None if not x.sessions else x.orders / x.sessions * 100,
            'metaCost': float(x.metaCost), 'metaLic': float(x.metaLic),
            'roas': div(x.sales, x.metaCost),
            'roasLic': div(x.sales, x.metaCost + x.metaLic),
            'metaRoas': div(x.metaRev, x.metaCost),
        }
        if x.metaCost < MIN_META_COST:
            cur['roas'] = cur['roasLic'] = cur['metaRoas'] = None
        for k in ['sessions', 'orders', 'sales', 'aov', 'cvr', 'metaCost', 'roas', 'metaRoas']:
            cur[k + 'D'] = pct_delta(cur[k], prev[k]) if prev else None
        prev = cur
        rows.append(cur)
    for c in rows:
        for k in ['sales', 'aov', 'metaCost', 'metaLic']:
            c[k] = r(c[k], 0)
        for k in ['cvr', 'roas', 'roasLic', 'metaRoas']:
            c[k] = r(c[k], 2)
        for k in list(c):
            if k.endswith('D') and c[k] is not None:
                c[k] = r(c[k], 1)
    return rows


SECTION_TMPL = """  <!-- ================= SHOPIFY (weekly) =================
       W39 起取代原本的「近期 KOL 表現討論」手動區塊（使用者 2026-09-30 要求）。
       由 scripts/build_shopify_section.py 產生／更新，可重複執行。 -->
  <section id="shopify">
    <div class="sec-head"><h2>Shopify 官網成效（週）</h2><span class="sec-tag">Shopify 總銷售額 ÷ Meta 廣告花費 · W__FIRST__–W__LAST__（週四～週三）</span></div>
    <div class="kpi-grid" id="shopKpiGrid"></div>
    <div class="grid-2" style="margin-top:16px;">
      <div class="card shop-chart-card">
        <div class="shop-chart-title">每週 Shopify 總銷售額 vs. Meta 廣告花費（JPY）</div>
        <div class="shop-legend"><span><i class="sw bar" style="background:#a9822e"></i>Shopify 總銷售額</span><span><i class="sw line" style="background:#2a78b8"></i>Meta 廣告花費</span></div>
        <div class="shop-chart" id="shopChartSales"></div>
      </div>
      <div class="card shop-chart-card">
        <div class="shop-chart-title">每週 ROAS：Shopify 實際 vs. Meta 後台回報</div>
        <div class="shop-legend"><span><i class="sw line" style="background:#a9822e"></i>Shopify ROAS（銷售額 ÷ Meta 花費）</span><span><i class="sw line dash" style="border-color:#2a78b8"></i>Meta 後台回報 ROAS</span></div>
        <div class="shop-chart" id="shopChartRoas"></div>
      </div>
    </div>
    <div class="table-scroll table-scroll-v" style="margin-top:16px;">
      <table id="shopTable"></table>
    </div>
    <div class="hint">Shopify 後台匯出為每日數據，已依廣告週報相同的週期（週四～週三）彙整成週次；Shopify 流量主要來自 Meta 廣告（Google／Amazon／樂天廣告導向其他商城），故 <b>Shopify ROAS = Shopify 總銷售額 ÷ Meta 廣告花費</b>，Meta 花費口徑同全渠道表的 Meta 列（含 CPC、不含 KOL 授權金）；ROAS 下方金黃色小字為把 Meta KOL 攤提授權金也算進成本後的 ROAS。「Meta 後台回報 ROAS」為 Meta 自己歸因的購買轉換值 ÷ 同一筆花費，僅供對照兩者歸因落差。CVR = 訂單數 ÷ 工作階段數；%Δ 為對比前一週；點欄位標題可排序。W1 的 Meta 花費僅數百円，ROAS 不具參考性故不列。</div>
  </section>
"""

CSS = """
  /* ---------- Shopify weekly section (W39+) ---------- */
  .shop-chart-card{padding:16px 16px 10px;}
  .shop-chart-title{font-size:13.5px;font-weight:800;color:var(--brand-deep);margin-bottom:6px;}
  .shop-legend{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--ink-soft);margin-bottom:6px;}
  .shop-legend span{display:inline-flex;align-items:center;gap:6px;}
  .shop-legend .sw{display:inline-block;flex:0 0 auto;}
  .shop-legend .sw.bar{width:10px;height:10px;border-radius:2px;}
  .shop-legend .sw.line{width:16px;height:2px;border-radius:1px;}
  .shop-legend .sw.line.dash{height:0;background:none !important;border-top:2px dashed;}
  .shop-chart{position:relative;width:100%;}
  .shop-chart svg{display:block;width:100%;height:auto;overflow:visible;}
  .shop-chart .axis text{font-size:10px;fill:var(--ink-faint);}
  .shop-chart .grid line{stroke:var(--line);stroke-width:1;}
  .shop-tip{position:absolute;pointer-events:none;background:var(--brand-deep);color:#fff;font-size:11.5px;line-height:1.5;
    padding:7px 10px;border-radius:8px;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,0.18);opacity:0;transition:opacity .1s;z-index:5;}
  .shop-tip b{font-weight:800;}
  .shop-tip .sw{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:5px;vertical-align:middle;}
"""

JS_TMPL = r"""
/* ===== SHOPIFY START (scripts/build_shopify_section.py) ===== */
const shopWeeks = __ROWS__;
(function renderShopify(){
  const GOLD = '#a9822e', BLUE = '#2a78b8';
  const cur = shopWeeks[shopWeeks.length-1];
  const tiles = [
    {label:'Shopify 總銷售額', value:money(cur.sales), delta:cur.salesD},
    {label:'訂單數', value:fmtInt(cur.orders), delta:cur.ordersD},
    {label:'工作階段數', value:fmtInt(cur.sessions), delta:cur.sessionsD},
    {label:'CVR', value:fmtPct1(cur.cvr), delta:cur.cvrD},
    {label:'客單價', value:money(cur.aov), delta:cur.aovD},
    {label:'Shopify ROAS', value:fmt2(cur.roas), delta:cur.roasD, hero:true},
  ];
  document.getElementById('shopKpiGrid').innerHTML = tiles.map(k=>`
    <div class="kpi-card ${k.hero?'hero':''}">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value">${k.value}</div>
      ${deltaChip(k.delta)}
    </div>`).join('');

  const compactYen = v => v>=1e6 ? '¥'+(v/1e6).toFixed(1)+'M' : v>=1e3 ? '¥'+Math.round(v/1e3)+'K' : '¥'+Math.round(v);
  function niceMax(v){ if(v<=0) return 1; const p=Math.pow(10,Math.floor(Math.log10(v))); const n=v/p; return (n<=1?1:n<=2?2:n<=2.5?2.5:n<=5?5:10)*p; }

  function chart(elId, {series, yFmt, tipFn}){
    const el = document.getElementById(elId);
    const W=560, H=250, m={t:14,r:14,b:26,l:46};
    const iw=W-m.l-m.r, ih=H-m.t-m.b, n=shopWeeks.length, step=iw/n;
    const yMax = niceMax(Math.max(...series.flatMap(s=>shopWeeks.map(w=>w[s.key]||0))));
    const y = v => m.t + ih - (v/yMax)*ih;
    const xc = i => m.l + step*i + step/2;
    let g = '<g class="grid">';
    for(let k=0;k<=4;k++){ const v=yMax*k/4; g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${y(v)}" y2="${y(v)}"/>`; }
    g += '</g><g class="axis">';
    for(let k=0;k<=4;k++){ const v=yMax*k/4; g+=`<text x="${m.l-6}" y="${y(v)+3}" text-anchor="end">${yFmt(v)}</text>`; }
    shopWeeks.forEach((w,i)=>{ if(w.wk%4===1 || i===n-1) g+=`<text x="${xc(i)}" y="${H-8}" text-anchor="middle">W${w.wk}</text>`; });
    g += '</g>';
    let marks = '';
    series.forEach(s=>{
      if(s.type==='bar'){
        const bw = Math.max(2, step-2);
        shopWeeks.forEach((w,i)=>{ const v=w[s.key]||0; if(!v) return; const top=y(v), h=m.t+ih-top;
          marks += `<rect x="${xc(i)-bw/2}" y="${top}" width="${bw}" height="${h}" rx="${Math.min(2,bw/2)}" fill="${s.color}" opacity="${i===n-1?1:0.78}"/>`; });
      } else {
        const pts = shopWeeks.map((w,i)=> w[s.key]==null ? null : [xc(i), y(w[s.key])]);
        let d='', pen=false;
        pts.forEach(p=>{ if(!p){pen=false;return;} d += (pen?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1); pen=true; });
        marks += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" ${s.dash?'stroke-dasharray="5 4"':''}/>`;
        const last = pts[n-1];
        if(last) marks += `<circle cx="${last[0]}" cy="${last[1]}" r="4" fill="${s.color}" stroke="#fff" stroke-width="2"/>`;
      }
    });
    const hits = shopWeeks.map((w,i)=>`<rect class="hit" data-i="${i}" x="${m.l+step*i}" y="${m.t}" width="${step}" height="${ih}" fill="transparent"/>`).join('');
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img">${g}<line class="xh" x1="0" x2="0" y1="${m.t}" y2="${m.t+ih}" stroke="var(--ink-faint)" stroke-width="1" opacity="0"/>${marks}${hits}</svg><div class="shop-tip"></div>`;
    const svg = el.querySelector('svg'), tip = el.querySelector('.shop-tip'), xh = el.querySelector('.xh');
    svg.addEventListener('mousemove', e=>{
      const h = e.target.closest('.hit'); if(!h){ tip.style.opacity=0; xh.setAttribute('opacity',0); return; }
      const i = +h.dataset.i, w = shopWeeks[i];
      tip.innerHTML = tipFn(w); tip.style.opacity = 1;
      xh.setAttribute('x1', xc(i)); xh.setAttribute('x2', xc(i)); xh.setAttribute('opacity', 0.5);
      const box = el.getBoundingClientRect(), px = e.clientX-box.left, py = e.clientY-box.top;
      const tw = tip.offsetWidth;
      tip.style.left = (px+14+tw > box.width ? px-14-tw : px+14) + 'px';
      tip.style.top = Math.max(0, py-40) + 'px';
    });
    svg.addEventListener('mouseleave', ()=>{ tip.style.opacity=0; xh.setAttribute('opacity',0); });
  }

  chart('shopChartSales', {
    series:[{key:'sales', type:'bar', color:GOLD}, {key:'metaCost', type:'line', color:BLUE}],
    yFmt: compactYen,
    tipFn: w=>`<b>W${w.wk}</b>（${w.range}）<br><span class="sw" style="background:${GOLD}"></span>銷售額 ${money(w.sales)}<br><span class="sw" style="background:${BLUE}"></span>Meta 花費 ${money(w.metaCost)}`
  });
  chart('shopChartRoas', {
    series:[{key:'roas', type:'line', color:GOLD}, {key:'metaRoas', type:'line', color:BLUE, dash:true}],
    yFmt: v=>v.toFixed(1),
    tipFn: w=>`<b>W${w.wk}</b>（${w.range}）<br><span class="sw" style="background:${GOLD}"></span>Shopify ROAS ${fmt2(w.roas)}<br><span class="sw" style="background:${BLUE}"></span>Meta 回報 ROAS ${fmt2(w.metaRoas)}`
  });

  // 可排序週表 —— 沿用頁面共用的 sortRows / sortableHead / bindSortHandlers
  const cols = [
    {key:'wk', label:'週次'}, {key:'range', label:'期間'}, {key:'sessions', label:'工作階段數'},
    {key:'orders', label:'訂單數'}, {key:'sales', label:'Shopify 總銷售額'}, {key:'aov', label:'客單價'},
    {key:'cvr', label:'CVR'}, {key:'metaCost', label:'Meta 廣告花費'}, {key:'roas', label:'Shopify ROAS'},
    {key:'metaRoas', label:'Meta 回報 ROAS'},
  ];
  const cell = (v, d) => `<div class="stack-cell"><span>${v}</span>${deltaChip(d,{size:'sub'})}</div>`;
  const shopSort = {key:'wk', dir:'desc'};
  function renderShopTable(){
    const rows = sortRows(shopWeeks, shopSort);
    document.getElementById('shopTable').innerHTML = sortableHead(cols, shopSort) + `
    <tbody>${rows.map(w=>`
      <tr class="${w.wk===cur.wk?'highlight':''}">
        <td class="name-cell">W${w.wk}${w.days<7?` <span class="muted" style="font-weight:500;">(${w.days} 天)</span>`:''}</td>
        <td>${w.range}</td>
        <td>${cell(fmtInt(w.sessions), w.sessionsD)}</td>
        <td>${cell(fmtInt(w.orders), w.ordersD)}</td>
        <td>${cell(money(w.sales), w.salesD)}</td>
        <td>${cell(money(w.aov), w.aovD)}</td>
        <td>${cell(fmtPct1(w.cvr), w.cvrD)}</td>
        <td>${cell(money(w.metaCost), w.metaCostD)}</td>
        <td><div class="stack-cell"><b>${fmt2(w.roas)}</b>${deltaChip(w.roasD,{size:'sub'})}${w.metaLic>0?`<span class="lic-note">含授權金 ${fmt2(w.roasLic)}</span>`:''}</div></td>
        <td>${cell(fmt2(w.metaRoas), w.metaRoasD)}</td>
      </tr>`).join('')}</tbody>`;
    bindSortHandlers('shopTable', shopSort, renderShopTable);
  }
  renderShopTable();
})();
/* ===== SHOPIFY END ===== */
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True)
    ap.add_argument('--shopify-csv', required=True)
    ap.add_argument('--cache', required=True)
    ap.add_argument('--bridge', required=True)
    ap.add_argument('--bridge-cutoff', required=True)
    ap.add_argument('--week-num', type=int, required=True)
    a = ap.parse_args()

    rows = build_rows(load_shopify_weekly(a.shopify_csv),
                      load_meta_weekly(a.cache, a.bridge, pd.Timestamp(a.bridge_cutoff)),
                      a.week_num)
    if rows[-1]['wk'] != a.week_num:
        raise SystemExit(f"Shopify CSV has no data for W{a.week_num} (last week in CSV: W{rows[-1]['wk']})")

    html = open(a.html, encoding='utf-8').read()

    # --- nav ---
    html = html.replace('<a href="#kol-discuss">近期 KOL 表現討論</a>', '<a href="#shopify">Shopify 官網成效</a>')

    # --- section ---
    section = (SECTION_TMPL.replace('__FIRST__', str(rows[0]['wk']))
                           .replace('__LAST__', str(rows[-1]['wk'])))
    pat_old = re.compile(r'  <!-- ================= KOL DISCUSSION.*?</section>\n', re.S)
    pat_shop = re.compile(r'  <!-- ================= SHOPIFY \(weekly\).*?</section>\n', re.S)
    if pat_shop.search(html):
        html = pat_shop.sub(lambda _: section, html, count=1)
    elif pat_old.search(html):
        html = pat_old.sub(lambda _: section, html, count=1)
    else:
        raise SystemExit('Could not find #kol-discuss or #shopify section to replace')

    # --- CSS (once) ---
    if 'Shopify weekly section (W39+)' not in html:
        html = html.replace('</style>', CSS + '</style>', 1)

    # --- JS: drop the KOL-discussion scripts, then (re)insert Shopify block ---
    js = JS_TMPL.replace('__ROWS__', json.dumps(rows, ensure_ascii=False))
    html = re.sub(r'\n/\* ===== SHOPIFY START.*?/\* ===== SHOPIFY END ===== \*/\n', '\n', html, flags=re.S)
    html = re.sub(r'/\* ---------------- 依內容主題分類.*?(?=</script>)', '', html, count=1, flags=re.S)
    idx = html.rfind('</script>', 0, html.find('<div id="lightbox">'))
    html = html[:idx] + js + html[idx:]

    open(a.html, 'w', encoding='utf-8').write(html)
    c = rows[-1]
    print(f"W{c['wk']}: sales ¥{c['sales']:,.0f} ({c['salesD']}%), orders {c['orders']}, sessions {c['sessions']}, "
          f"Meta cost ¥{c['metaCost']:,.0f}, Shopify ROAS {c['roas']} ({c['roasD']}%), Meta-reported ROAS {c['metaRoas']}")


if __name__ == '__main__':
    main()
