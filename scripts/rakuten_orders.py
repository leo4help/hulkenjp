#!/usr/bin/env python3
"""Rakuten RMS 楽天ペイ受注API: 日別の売上・件数を集計する。
Keys: .secrets/rakuten.env (gitignored). Never print keys.
Usage: python3 scripts/rakuten_orders.py 2026-11-01 2026-11-07 [--json]
"""
import base64, json, sys, os, urllib.request, urllib.error, datetime as dt
from collections import defaultdict
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env={}
for l in open(os.path.join(ROOT,'.secrets/rakuten.env')):
    if '=' in l: k,v=l.strip().split('=',1); env[k]=v
AUTH='ESA '+base64.b64encode(f"{env['RAKUTEN_SERVICE_SECRET']}:{env['RAKUTEN_LICENSE_KEY']}".encode()).decode()
BASE='https://api.rms.rakuten.co.jp/es/2.0/order/'
def call(ep,body):
    req=urllib.request.Request(BASE+ep,data=json.dumps(body).encode(),method='POST',
        headers={'Authorization':AUTH,'Content-Type':'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req,timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        return {'_http':e.code,'_body':e.read().decode('utf-8','replace')[:800]}
def search(d1,d2):
    out=[];page=1
    while True:
        r=call('searchOrder/',{"dateType":1,"startDatetime":f"{d1}T00:00:00+0900","endDatetime":f"{d2}T23:59:59+0900",
            "PaginationRequestModel":{"requestRecordsAmount":1000,"requestPage":page}})
        if '_http' in r: return r
        out+=r.get('orderNumberList') or []
        pg=r.get('PaginationResponseModel') or {}
        if page>=(pg.get('totalPages') or 1): return out
        page+=1
def details(nums):
    res=[]
    for i in range(0,len(nums),100):
        r=call('getOrder/',{"orderNumberList":nums[i:i+100],"version":7})
        if '_http' in r: return r
        res+=r.get('OrderModelList') or []
    return res
if __name__=='__main__':
    d1,d2=sys.argv[1],sys.argv[2]
    nums=search(d1,d2)
    if isinstance(nums,dict): print('searchOrder error',nums); sys.exit(1)
    ods=details(nums) if nums else []
    if isinstance(ods,dict): print('getOrder error',ods); sys.exit(1)
    agg=defaultdict(lambda:{'orders':0,'goods':0,'total':0,'request':0,'cancel':0})
    for o in ods:
        day=(o.get('orderDatetime') or '')[:10]; a=agg[day]
        if o.get('orderProgress')==900: a['cancel']+=1; continue
        a['orders']+=1; a['goods']+=o.get('goodsPrice') or 0; a['total']+=o.get('totalPrice') or 0; a['request']+=o.get('requestPrice') or 0
    rows=[{'date':k,**v} for k,v in sorted(agg.items())]
    if '--json' in sys.argv: print(json.dumps(rows,ensure_ascii=False))
    else:
        print('date        orders  goodsPrice  totalPrice  requestPrice  cancel')
        for r in rows: print(f"{r['date']}  {r['orders']:6}  {r['goods']:10,}  {r['total']:10,}  {r['request']:12,}  {r['cancel']:6}")
