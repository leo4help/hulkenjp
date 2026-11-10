#!/usr/bin/env python3
"""OpenAI (ChatGPT) Ads Advertiser API: 日別の花費・曝光・點擊・轉換・成立訂單銷售額（唯讀）。
Key: .secrets/openai_ads.env (gitignored). Never print the key.
Usage: python3 scripts/openai_ads.py 2026-10-28 2026-11-10 [--json] [--debug]
"""
import json, os, sys, urllib.request, urllib.parse, urllib.error
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY=open(os.path.join(ROOT,'.secrets/openai_ads.env')).read().split('=',1)[1].strip()
BASE='https://api.ads.openai.com/v1'; TZ='Asia/Tokyo'
def req(method,path,params=None,body=None):
    url=BASE+path+('?'+urllib.parse.urlencode(params,doseq=True) if params else '')
    r=urllib.request.Request(url,method=method,data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json','User-Agent':'hulken-weekly-report/1.0','Accept':'application/json'})
    try:
        with urllib.request.urlopen(r,timeout=60) as x: return json.load(x)
    except urllib.error.HTTPError as e: return {'_http':e.code,'_body':e.read().decode('utf-8','replace')[:800]}
def daily(d1,d2):
    tr=json.dumps({"type":"date_range","since":d1,"until":d2,"timezone":TZ})
    p=[('time_granularity','daily'),('aggregation_level','ad_account'),('limit','2000'),('time_ranges[]',tr)]
    for f in ['metadata.readable_time','ad_account.impressions','ad_account.clicks','ad_account.spend','ad_account.conversions']: p.append(('fields[]',f))
    return req('GET','/ad_account/insights',p)
def campaign_ids(d1,d2):
    tr=json.dumps({"type":"date_range","since":d1,"until":d2,"timezone":TZ})
    a=req('GET','/ad_account/insights',[('time_granularity','none'),('aggregation_level','campaign'),('limit','2000'),
        ('fields[]','campaign.id'),('fields[]','campaign.name'),('time_ranges[]',tr)])
    return [x['campaign_id'] for x in a.get('data',[]) if x.get('campaign_id')] if '_http' not in a else a
def sales(d1,d2):
    """POST /conversions/insights（需 entity_ids；aggregation_level 只能 campaign/ad_group/ad）→ {date: sales}"""
    ids=campaign_ids(d1,d2)
    if isinstance(ids,dict): return ids
    if not ids: return {}
    tr=json.dumps({"type":"date_range","since":d1,"until":d2,"timezone":TZ})
    c=req('POST','/conversions/insights',body={"aggregation_level":"campaign","time_granularity":"daily","time_ranges":[tr],
        "entity_ids":ids,"attribution_window_days":30,"view_through_attribution_window_days":1})
    if '_http' in c: return c
    out={}
    for x in c.get('data',[]):
        out[x['date']]=out.get(x['date'],0.0)+float(x.get('order_created_attributed_sales') or 0)
    return out
if __name__=='__main__':
    d1,d2=sys.argv[1],sys.argv[2]; dbg='--debug' in sys.argv
    a=daily(d1,d2); c=sales(d1,d2)
    if dbg: print(json.dumps({'insights':a,'conversions':c},ensure_ascii=False)[:3000]); sys.exit()
    if '_http' in a: print('insights error',a); sys.exit(1)
    rows={}
    for x in a.get('data',[]):
        day=(x.get('readable_time') or x.get('start_time') or '')[:10]
        rows[day]={'date':day,'impressions':x.get('impressions',0),'clicks':x.get('clicks',0),'spend':float(x.get('spend') or 0),'conversions':x.get('conversions',0),'sales':0.0}
    if '_http' in c: print('# conversions endpoint error (sales=0):',c['_http'],c['_body'][:200],file=sys.stderr)
    else:
        for day,v in c.items():
            if day in rows: rows[day]['sales']=v
    out=[rows[k] for k in sorted(rows)]
    if '--json' in sys.argv: print(json.dumps(out,ensure_ascii=False))
    else:
        print('date        imp  clicks     spend  conv     sales')
        for r in out: print(f"{r['date']} {r['impressions']:5} {r['clicks']:6} {r['spend']:9,.0f} {r['conversions']:5} {r['sales']:9,.0f}")
