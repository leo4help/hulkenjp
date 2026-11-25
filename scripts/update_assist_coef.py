#!/usr/bin/env python3
"""Add / refresh the 「助攻係數參考表」 under the KOL license calculator in all.html.

助攻係數 = (Row 的 Shopify 首尾營收 ÷ Row 的 Meta 營收) ÷ 全帳戶平均比例
  首尾營收 = Shopify 首次點擊營收 × 50% + 最後點擊營收 × 50%（utm_content = Meta 廣告 ID）
  全帳戶平均比例 = 所有有 Row 編號素材的 首尾營收合計 ÷ Meta 營收合計（同一期間）

Inputs
  --shopify  ShopifyQL result JSON (FROM sales SHOW total_sales, orders GROUP BY utm_content
             WITH FIRST_CLICK_ATTRIBUTION, LAST_CLICK_ATTRIBUTION SINCE 2026-01-01 UNTIL <end>)
  --admap    {ad_id: ad_name} JSON (Meta MCP ads_get_ad_entities id,name), cumulative
  --cache / --bridge / --bridge-cutoff   same as build_all_lifetime.py (Meta spend / revenue per Row)

Usage
  python3 scripts/update_assist_coef.py --cache _cache/ad_data_historical_cache.pkl.gz \
    --bridge 2026W47/Hulken_Claude_Bridge_mcp.xlsx --bridge-cutoff 2026-11-19 \
    --shopify 2026W47/_data/shopify_first_last_click.json --admap _cache/meta_ad_names.json \
    --start-date 2026-01-01 --end-date 2026-11-25 --all-html all.html
"""
import argparse, json, re, sys, os
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from build_all_lifetime import enrich, NAME_ALIASES, COST, REV, DATE  # noqa

COEF_MIN, COEF_MAX = 0.6, 1.5      # 調整後 ROAS 用的係數上下限
MIN_ORDERS = 15                     # 首次＋最後點擊訂單合計門檻
MIN_DAYS = 21                       # 上線滿幾天才套用
ENTRY, HARVEST = 1.2, 0.8           # 入口型 / 收割型 門檻
TARGET = 4.0
MIN_SPEND = 30000                   # 表格只列累計媒體花費 ≥ 此值的 KOL 素材

START, END = '<!-- assist-coef start -->', '<!-- assist-coef end -->'
ANCHOR = '  </section>\n\n</div>\n\n<footer>'


def row_no(s):
    m = re.search(r'-(\d+)$', str(s or ''))
    return int(m.group(1)) if m else None


def load_meta(cache_path, bridge_path, cutoff, start, end):
    cache = pd.read_pickle(cache_path, compression='gzip').copy()
    cache['NameRow'] = cache['NameRow'].replace(NAME_ALIASES)
    frames = [cache]
    if bridge_path:
        b = enrich(pd.read_excel(bridge_path, sheet_name='Claude_Analysis_Data'))
        b = b[b[DATE] >= pd.Timestamp(cutoff)]
        common = [c for c in cache.columns if c in b.columns]
        frames = [cache[common], b[common]]
    ad = pd.concat(frames, ignore_index=True).drop_duplicates()
    ad = ad[(ad[DATE] >= pd.Timestamp(start)) & (ad[DATE] <= pd.Timestamp(end))]
    media = ad[(ad['AD_Channel'] == 'Meta AD') & (~ad['goal'].isin(['-', 'CPC']))].copy()
    media['row'] = media['NameRow'].apply(row_no)
    media = media[media['row'].notna()]
    lic = ad[(ad['AD_Channel'] == 'Meta AD') & (ad['goal'] == '-') & (ad['isKOL'])].copy()
    lic['row'] = lic['NameRow'].apply(row_no)
    lic_g = lic[lic['row'].notna()].groupby('row')[COST].sum()
    out = {}
    for r, g in media.groupby('row'):
        sp = g[g[COST] > 0]
        out[int(r)] = dict(
            name=g['NameRow'].mode().iloc[0], isKOL=bool(g['isKOL'].mode().iloc[0]),
            spend=float(g[COST].sum()), mrev=float(g[REV].sum()), lic=float(lic_g.get(r, 0.0)),
            first=sp[DATE].min().strftime('%Y-%m-%d') if len(sp) else None,
            last=sp[DATE].max().strftime('%Y-%m-%d') if len(sp) else None)
    return out


def load_shopify(shop_path, admap_path):
    s = json.load(open(shop_path))
    names = json.load(open(admap_path))
    cols = [c['name'] for c in s['columns']]
    ix = {c: i for i, c in enumerate(cols)}
    agg, unmapped = {}, []
    for r in s['rows']:
        aid = r[ix['utm_content']]
        if not aid.isdigit():
            continue
        nm = names.get(aid)
        if nm is None:
            if float(r[ix['total_sales__first_click']]) + float(r[ix['total_sales__last_click']]) > 0:
                unmapped.append(aid)
            continue
        m = re.search(r'R:(\d+)', nm)
        if not m:
            continue
        a = agg.setdefault(int(m.group(1)), dict(f=0.0, l=0.0, fo=0, lo=0))
        a['f'] += float(r[ix['total_sales__first_click']]); a['l'] += float(r[ix['total_sales__last_click']])
        a['fo'] += int(r[ix['orders__first_click']]); a['lo'] += int(r[ix['orders__last_click']])
    return agg, unmapped


def verdict(d):
    fo, lo = d['fo'], d['lo']
    cnt = f'首次 {fo} 筆 vs 最後 {lo} 筆'
    if d['days'] < MIN_DAYS:
        return 'na', f'上線未滿 3 週，首次點擊還在累積，先以 Meta 為準（{cnt}）'
    if fo + lo < MIN_ORDERS:
        return 'na', f'樣本不足，以 Meta 為準（{cnt}）'
    c, mr, adj = d['coef'], d['metaRoas'], d['adjRoas']
    if c >= ENTRY:
        extra = '只看 Meta 會被砍，調整後達標' if (mr < TARGET <= adj) else 'Meta 低估'
        return 'entry', f'入口型，{extra}（{cnt}）'
    if c <= HARVEST:
        extra = 'Meta 看起來比實際好，調整後未達標' if (mr >= TARGET > adj) else 'Meta 看起來比實際好'
        return 'harvest', f'偏收割，{extra}（{cnt}）'
    return 'mid', f'平衡，Meta ROAS 可直接參考（{cnt}）'


def build(meta, shop, end):
    rows_all = [r for r in meta if meta[r]['mrev'] > 0]
    W = sum(0.5 * shop.get(r, {}).get('f', 0) + 0.5 * shop.get(r, {}).get('l', 0) for r in rows_all)
    M = sum(meta[r]['mrev'] for r in rows_all)
    ratio = W / M if M else None
    endts = pd.Timestamp(end)
    out = []
    for r, m in meta.items():
        if not m['isKOL'] or m['spend'] < MIN_SPEND or m['mrev'] <= 0 or not m['first']:
            continue
        s = shop.get(r, dict(f=0.0, l=0.0, fo=0, lo=0))
        w = 0.5 * s['f'] + 0.5 * s['l']
        coef = (w / m['mrev']) / ratio
        metaRoas = m['mrev'] / (m['spend'] + m['lic'])   # 含授權金
        d = dict(row=r, name=re.sub(r'^A:', '', m['name']).rsplit('-', 1)[0], spend=round(m['spend']), lic=round(m['lic']),
                 metaRoas=round(metaRoas, 2), coef=round(coef, 2),
                 adjRoas=round(metaRoas * min(max(coef, COEF_MIN), COEF_MAX), 2),
                 fo=s['fo'], lo=s['lo'], first=m['first'], last=m['last'],
                 days=int((endts - pd.Timestamp(m['first'])).days) + 1)
        d['cls'], d['note'] = verdict(d)
        if d['cls'] == 'na':
            d['adjRoas'] = None
        out.append(d)
    out.sort(key=lambda x: (x['last'], x['spend']), reverse=True)
    return out, ratio


BLOCK = r'''<!-- assist-coef start -->
    <div class="card calc-card" id="assistCoefCard">
      <h3 class="calc-step-title"><span class="calc-num">＋</span> 參考：助攻係數（Shopify 首尾歸因）</h3>
      <p class="calc-desc">上方計算機的 C 用的是 Meta 後台 ROAS。Meta 容易低估「第一次把客人帶進官網」的素材，也容易高估「收割已經認識品牌的人」的素材。這張表用 Shopify 的首次／最後點擊紀錄做對照，談判時可一起參考，避免誤殺助攻表現好的 KOC。計算機本身的公式不變。</p>
      <div class="assist-def">
        <b>助攻係數定義</b>
        <ul>
          <li>首尾營收 ＝ Shopify 首次點擊營收 × 50% ＋ 最後點擊營收 × 50%（依 utm_content 的 Meta 廣告 ID 對回 Row）</li>
          <li>助攻係數 ＝（該素材的首尾營收 ÷ 該素材的 Meta 營收）÷ 全帳戶平均比例 <b>__RATIO__</b></li>
          <li>係數 &gt; 1：Shopify 給它的功勞比 Meta 平均多（偏「帶新人進站」）；&lt; 1：偏「收割」。全帳戶平均剛好是 1，不會讓所有素材一起灌水。</li>
          <li>本表的 ROAS 都含 KOL 授權金：Meta ROAS（含授權金）＝ Meta 營收 ÷（媒體花費 ＋ 期間內攤提的授權金）</li>
          <li>調整後 ROAS ＝ Meta ROAS（含授權金）× 助攻係數（係數限制在 __CMIN__～__CMAX__ 之間，避免單一素材過度拉高或壓低）</li>
          <li>判讀：係數 ≥ __ENTRY__ 為入口型、≤ __HARV__ 為偏收割、其餘為平衡。首次＋最後點擊訂單合計未滿 __MINO__ 筆，或上線未滿 3 週（首次點擊的訂單常隔幾天到幾週才進來），不計算調整後 ROAS，以 Meta 為準。</li>
          <li>期間：__START__ ～ __END__ 累計（不是計算機的近 14 個投放日）。只列累計媒體花費 ≥ ¥__MINS__ 的 KOL 素材。</li>
        </ul>
        <div class="calc-hint">限制：Meta 營收含「看過沒點」的瀏覽歸因，Shopify 只看得到點擊進站，所以只比相對比例；從 IG App 內瀏覽器跳出、跨裝置購買時首次點擊會遺失，入口型素材仍可能被低估。</div>
      </div>
      <div class="assist-tools">
        <input type="text" id="assistSearch" placeholder="搜尋 Row 或 KOL 名稱" autocomplete="off">
        <span class="assist-chips" id="assistChips">
          <button type="button" class="cat-filter-btn active" data-c="all">全部</button>
          <button type="button" class="cat-filter-btn" data-c="entry">入口型</button>
          <button type="button" class="cat-filter-btn" data-c="mid">平衡</button>
          <button type="button" class="cat-filter-btn" data-c="harvest">偏收割</button>
          <button type="button" class="cat-filter-btn" data-c="na">以 Meta 為準</button>
        </span>
      </div>
      <div class="assist-tools">
        <label>Meta ROAS（含授權金）<select id="asOpX"><option value="gt">大於</option><option value="lt">小於</option></select><input type="number" id="asValX" step="0.1" placeholder="X" class="as-num"></label>
        <label>調整後 ROAS <select id="asOpY"><option value="gt">大於</option><option value="lt">小於</option></select><input type="number" id="asValY" step="0.1" placeholder="Y" class="as-num"></label>
        <button type="button" class="cat-filter-btn" id="asClear">清除條件</button>
        <span class="calc-hint" id="asCount"></span>
      </div>
      <div class="table-scroll table-scroll-v" style="max-height:560px;">
        <table id="assistTable"></table>
      </div>
    </div>
<style>
.assist-def{background:rgba(127,127,127,.07);border-radius:10px;padding:12px 16px;margin:4px 0 14px;font-size:13.5px;line-height:1.7}
.assist-def ul{margin:6px 0 6px;padding-left:20px}
.assist-tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:10px}
.assist-tools input{font:inherit;font-size:13.5px;padding:6px 10px;border:1px solid rgba(127,127,127,.35);border-radius:8px;background:transparent;color:inherit;width:220px;max-width:100%}
.assist-tools label{display:inline-flex;gap:6px;align-items:center;font-size:13.5px}
.assist-tools select{font:inherit;font-size:13px;padding:5px 6px;border:1px solid rgba(127,127,127,.35);border-radius:8px;background:transparent;color:inherit}
.assist-tools input.as-num{width:80px}
.assist-chips{display:inline-flex;flex-wrap:wrap;gap:6px}
#assistTable td.l,#assistTable th.l{text-align:left}
#assistTable th{cursor:pointer;white-space:nowrap}
#assistTable td{white-space:nowrap}
#assistTable td.note{white-space:normal;min-width:260px;text-align:left}
.as-pill{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid currentColor}
.as-entry{color:#15803d}.as-harvest{color:#b45309}.as-mid{color:#64748b}.as-na{color:#94a3b8}
tr.assist-hit td{background:rgba(37,99,235,.12)}
</style>
<script>
const ASSIST_DATA = __DATA__;
(function(){
  const T=document.getElementById('assistTable'); if(!T) return;
  const lab={entry:'入口型',mid:'平衡',harvest:'偏收割',na:'以 Meta 為準'};
  const cols=[['row','Row',0],['name','KOL',1],['spend','累計媒體花費',0],['lic','授權金',0],['metaRoas','Meta ROAS（含授權金）',0],['coef','助攻係數',0],['adjRoas','調整後 ROAS',0],['fo','首次點擊訂單',0],['lo','最後點擊訂單',0],['last','最後投放日',1],['note','判讀',1]];
  let key='last',asc=false,cat='all',q='',hit=null;
  const f2=v=>v==null?'—':Number(v).toFixed(2), yen=v=>'¥'+Math.round(v).toLocaleString();
  function render(){
    const cmp=(v,op,x)=>x===''?true:(v==null?false:(op==='gt'?v>Number(x):v<Number(x)));
    const X=document.getElementById('asValX').value.trim(), Y=document.getElementById('asValY').value.trim();
    const oX=document.getElementById('asOpX').value, oY=document.getElementById('asOpY').value;
    let R=ASSIST_DATA.rows.filter(r=>(cat==='all'||r.cls===cat)&&(!q||String(r.row).includes(q)||r.name.toLowerCase().includes(q))&&cmp(r.metaRoas,oX,X)&&cmp(r.adjRoas,oY,Y));
    document.getElementById('asCount').textContent=`符合 ${R.length} 支`+(Y!==''?'（設定調整後 ROAS 條件時，「以 Meta 為準」的素材沒有調整後 ROAS，不會列出）':'');
    R.sort((a,b)=>{const x=a[key],y=b[key];if(x==null)return 1;if(y==null)return -1;return (x>y?1:x<y?-1:0)*(asc?1:-1)});
    T.innerHTML='<thead><tr>'+cols.map(c=>`<th class="${c[2]?'l':''}" data-k="${c[0]}">${c[1]}${key===c[0]?(asc?' ▲':' ▼'):''}</th>`).join('')+'</tr></thead><tbody>'+
      R.map(r=>`<tr class="${hit===r.row?'assist-hit':''}" data-row="${r.row}"><td>R${r.row}</td><td class="l">${r.name}</td><td>${yen(r.spend)}</td><td>${r.lic?yen(r.lic):'—'}</td><td>${f2(r.metaRoas)}</td><td>${r.cls==='na'?'<span style="opacity:.45">'+f2(r.coef)+'</span>':'<b>'+f2(r.coef)+'</b>'}</td><td>${f2(r.adjRoas)}</td><td>${r.fo}</td><td>${r.lo}</td><td class="l">${r.last||'—'}</td><td class="note"><span class="as-pill as-${r.cls}">${lab[r.cls]}</span> ${r.note}</td></tr>`).join('')+'</tbody>';
    T.querySelectorAll('th').forEach(th=>th.onclick=()=>{const k=th.dataset.k; if(key===k) asc=!asc; else {key=k; asc=(k==='name'||k==='note');} render();});
  }
  document.getElementById('assistSearch').addEventListener('input',e=>{q=e.target.value.trim().toLowerCase().replace(/^r/,'');render();});
  ['asOpX','asOpY','asValX','asValY'].forEach(id=>{const el=document.getElementById(id); el.addEventListener('input',render); el.addEventListener('change',render);});
  document.getElementById('asClear').onclick=()=>{document.getElementById('asValX').value='';document.getElementById('asValY').value='';render();};
  document.querySelectorAll('#assistChips button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#assistChips button').forEach(x=>x.classList.remove('active'));b.classList.add('active');cat=b.dataset.c;render();});
  const fb=document.getElementById('licFetchBtn'), inp=document.getElementById('licRowInput');
  if(fb&&inp) fb.addEventListener('click',()=>{const m=String(inp.value).match(/\d+/); hit=m?Number(m[0]):null; render(); const tr=T.querySelector('tr.assist-hit'); if(tr) tr.scrollIntoView({block:'nearest'});});
  render();
})();
</script>
<!-- assist-coef end -->
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default='_cache/ad_data_historical_cache.pkl.gz')
    ap.add_argument('--bridge'); ap.add_argument('--bridge-cutoff')
    ap.add_argument('--shopify', required=True); ap.add_argument('--admap', default='_cache/meta_ad_names.json')
    ap.add_argument('--start-date', default='2026-01-01'); ap.add_argument('--end-date', required=True)
    ap.add_argument('--all-html', default='all.html'); ap.add_argument('--out')
    a = ap.parse_args()
    meta = load_meta(a.cache, a.bridge, a.bridge_cutoff, a.start_date, a.end_date)
    shop, unmapped = load_shopify(a.shopify, a.admap)
    rows, ratio = build(meta, shop, a.end_date)
    data = dict(ratio=round(ratio, 3), start=a.start_date, end=a.end_date, rows=rows)
    blk = (BLOCK.replace('__DATA__', json.dumps(data, ensure_ascii=False))
           .replace('__RATIO__', f'{ratio:.2f}').replace('__CMIN__', str(COEF_MIN)).replace('__CMAX__', str(COEF_MAX))
           .replace('__ENTRY__', str(ENTRY)).replace('__HARV__', str(HARVEST)).replace('__MINO__', str(MIN_ORDERS))
           .replace('__START__', a.start_date.replace('-', '/')).replace('__END__', a.end_date.replace('-', '/'))
           .replace('__MINS__', f'{MIN_SPEND:,}'))
    h = open(a.all_html, encoding='utf-8').read()
    if START in h:
        i, j = h.index(START), h.index(END) + len(END) + 1
        h = h[:i] + blk + h[j:]
    else:
        assert ANCHOR in h, 'kol-calc anchor not found'
        h = h.replace(ANCHOR, blk + ANCHOR, 1)
    open(a.out or a.all_html, 'w', encoding='utf-8').write(h)
    from collections import Counter
    print(f'ratio {ratio:.3f}; rows {len(rows)}; {dict(Counter(r["cls"] for r in rows))}; unmapped ad ids with sales: {len(unmapped)}')


if __name__ == '__main__':
    main()
