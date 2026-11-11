/* ===== Hulken weekly report v2 renderer (W45+) — data in const R ===== */
(function(){const g=document.getElementById('cursorGlow');if(!g)return;let raf=null,mx=0,my=0;
  addEventListener('mousemove',e=>{mx=e.clientX;my=e.clientY;g.style.opacity='1';if(!raf)raf=requestAnimationFrame(()=>{g.style.transform=`translate(${mx}px,${my}px) translate(-50%,-50%)`;raf=null})},{passive:true});
  document.addEventListener('mouseleave',()=>g.style.opacity='0')})();
(function(){const p=document.getElementById('weekPicker'),t=document.getElementById('weekPickerToggle'),m=document.getElementById('weekMenu');if(!p)return;
  fetch('../weeks.json').then(r=>r.json()).then(W=>{m.innerHTML=W.map(w=>w.file===THIS_REPORT_FILE?`<a class="current">${w.label}${w.status==='archived'?'<span class="beta-badge arch">封存</span>':''}<span class="wm-date">目前檢視中</span></a>`:`<a href="../${w.file}">${w.label}${w.isBeta?'<span class="beta-badge">BETA</span>':''}${w.status==='archived'?'<span class="beta-badge arch">封存</span>':''}</a>`).join('')}).catch(()=>m.innerHTML='<a class="current">週次清單載入失敗</a>');
  t.onclick=e=>{e.stopPropagation();p.classList.toggle('open')};document.addEventListener('click',e=>{if(!p.contains(e.target))p.classList.remove('open')})})();

const fInt=n=>n==null||!isFinite(n)?'–':Math.round(n).toLocaleString('en-US');
const fYen=n=>n==null||!isFinite(n)?'–':'¥'+fInt(n);
const f2=n=>n==null||!isFinite(n)?'–':Number(n).toFixed(2);
const fPct=n=>n==null||!isFinite(n)?'–':Number(n).toFixed(2)+'%';
const div=(a,b)=>b?a/b:null;
const N=R.weeks.length, CUR=N-1, PRV=N-2;
const sum=(arr)=>arr.reduce((o,x)=>{for(const k of ['cost','imp','clicks','conv','rev'])o[k]=(o[k]||0)+(x[k]||0);return o},{});
function met(x,plat){const o={cost:x.cost,rev:x.rev,roas:div(x.rev,x.cost),cpm:x.imp?x.cost/x.imp*1000:null,ctr:x.imp?x.clicks/x.imp*100:null,cvr:x.clicks?x.conv/x.clicks*100:null,conv:x.conv,clicks:x.clicks,imp:x.imp};
  if(plat){o.prev=plat.sales;o.proas=div(plat.sales,x.cost);const ord=plat.orders_cvr!=null?plat.orders_cvr:plat.orders;o.pcvr=plat.sessions?ord/plat.sessions*100:null;o.orders=plat.orders;o.sessions=plat.sessions}
  if(!x.cost){o.roas=null;o.proas=null;o.cpm=x.imp?0:null}return o}
/* group series */
const GROUPS={
  A:{name:'(A) 官網',plat:'Shopify',color:'#3d6fb6',src:R.A,ch:[['Meta','#3d6fb6'],['Google 品牌','#5aa469'],['Google 非品牌','#97c98f'],['ChatGPT','#7a5fb0']]},
  B:{name:'(B) 樂天',plat:'樂天',color:'#c9473f',src:R.B,ch:[['樂天 RPP','#c9473f'],['樂天 TDA','#e8928b']]},
  C:{name:'(C) Amazon',plat:'Amazon',color:'#e8a33d',src:R.C,ch:[['Amazon AD','#e8a33d']]}};
const gWeek=(G,i)=>sum(G.ch.map(c=>G.src[i].channels[c[0]]));
const gMet=(G,i)=>met(gWeek(G,i),G.src[i].platform);
const LIC=R.lic.total;

/* ---------- SVG chart ---------- */
function niceMax(v){if(!(v>0))return 1;const p=Math.pow(10,Math.floor(Math.log10(v)));for(const m of [1,1.2,1.5,2,2.5,3,4,5,6,8,10])if(m*p>=v)return m*p;return 10*p}
function chart(el,o){
  const W=o.w||380,H=o.h||210,L=o.padL||44,Rr=o.right?46:12,T=18,B=34,iw=W-L-Rr,ih=H-T-B,n=o.labels.length,bw=iw/n;
  const X=i=>L+bw*(i+.5);
  let lmax=0;(o.bars||[]).length&&o.labels.forEach((_,i)=>{lmax=Math.max(lmax,o.bars.reduce((s,b)=>s+(b.values[i]||0),0))});
  (o.lines||[]).filter(l=>!l.right).forEach(l=>l.values.forEach(v=>{if(v!=null)lmax=Math.max(lmax,v)}));
  let rmax=0;(o.lines||[]).filter(l=>l.right).forEach(l=>l.values.forEach(v=>{if(v!=null)rmax=Math.max(rmax,v)}));
  lmax=niceMax(lmax*1.08);rmax=niceMax(rmax*1.08);
  const YL=v=>T+ih-(v/lmax)*ih,YR=v=>T+ih-(v/rmax)*ih,fl=o.fmtL||(v=>v),fr=o.fmtR||(v=>v);
  let s=`<svg viewBox="0 0 ${W} ${H}">`;
  for(let k=0;k<=4;k++){const v=lmax*k/4,y=YL(v);s+=`<line x1="${L}" x2="${W-Rr}" y1="${y}" y2="${y}" stroke="#ece4d6"/><text x="${L-5}" y="${y+3.5}" text-anchor="end" font-size="9.5" fill="#9a9186">${fl(v)}</text>`;
    if(o.right)s+=`<text x="${W-Rr+5}" y="${YR(rmax*k/4)+3.5}" font-size="9.5" fill="#9a9186">${fr(rmax*k/4)}</text>`}
  o.labels.forEach((lb,i)=>{const [a,b]=lb.split('\n');s+=`<text x="${X(i)}" y="${H-B+14}" text-anchor="middle" font-size="9.5" font-weight="${i===n-1?800:600}" fill="#6b6255">${a}</text><text x="${X(i)}" y="${H-B+26}" text-anchor="middle" font-size="8.5" fill="#9a9186">${b||''}</text>`});
  (o.bars||[]).length&&o.labels.forEach((_,i)=>{let acc=0;o.bars.forEach(b=>{const v=b.values[i]||0;if(v>0){const y0=YL(acc),y1=YL(acc+v);s+=`<rect x="${X(i)-bw*.32}" y="${y1}" width="${bw*.64}" height="${Math.max(0,y0-y1)}" fill="${b.color}"><title>${b.name} ${o.labels[i].replace('\n',' ')}：${(o.tipL||fl)(v)}</title></rect>`}acc+=v});
    if(o.barTotal&&acc>0)s+=`<text x="${X(i)}" y="${YL(acc)-4}" text-anchor="middle" font-size="9.5" font-weight="700" fill="#3d3220" stroke="#fff" stroke-width="3" paint-order="stroke">${o.barTotal(acc)}</text>`});
  (o.lines||[]).forEach(l=>{const Y=l.right?YR:YL;let d='',pen=false;l.values.forEach((v,i)=>{if(v==null){pen=false;return}d+=(pen?'L':'M')+X(i)+','+Y(v);pen=true});
    s+=`<path d="${d}" fill="none" stroke="${l.color}" stroke-width="2.2" ${l.dash?'stroke-dasharray="5 4"':''} stroke-linejoin="round"/>`;
    l.values.forEach((v,i)=>{if(v==null)return;s+=`<circle cx="${X(i)}" cy="${Y(v)}" r="3" fill="${l.color}"><title>${l.name} ${o.labels[i].replace('\n',' ')}：${l.fmt(v)}</title></circle>`;
      if(o.labelLast!==false&&(i===n-1||o.labelAll))s+=`<text x="${X(i)}" y="${Y(v)-7}" text-anchor="middle" font-size="9.5" font-weight="700" fill="${l.color}" stroke="#fff" stroke-width="3" paint-order="stroke">${l.fmt(v)}</text>`})});
  s+='</svg>';
  const lg=[...(o.bars||[]).map(b=>`<span><i style="background:${b.color};height:10px"></i>${b.name}</span>`),...(o.lines||[]).map(l=>`<span><i style="background:${l.color}"></i>${l.name}${l.right?'（右軸）':''}</span>`)].join('');
  el.innerHTML=(o.title?`<h4>${o.title}</h4>`:'')+`<div class="lg">${lg}</div>`+s;
}
const man=v=>(v/1e4).toFixed(v>=1e6?0:1)+'萬',manAxis=v=>Math.round(v/1e4)+'';

/* ---------- Overview chart ---------- */
(function(){
  const el=document.getElementById('ovChart'),plat=k=>GROUPS[k].src.map(w=>w.platform.sales);
  const spend=R.labels.map((_,i)=>['A','B','C'].reduce((s,k)=>s+gWeek(GROUPS[k],i).cost,0));
  chart(el,{w:1100,h:330,padL:50,right:true,labels:R.labels,labelAll:true,
    bars:[{name:'Shopify 官網',color:'#3d6fb6',values:plat('A')},{name:'Amazon',color:'#e8a33d',values:plat('C')},{name:'樂天',color:'#c9473f',values:plat('B')}],
    barTotal:v=>(v/1e4).toFixed(0),fmtL:manAxis,tipL:man,fmtR:manAxis,
    lines:[{name:'廣告花費（三組合計，不含授權金）',color:'#1f2a44',right:true,values:spend,fmt:v=>(v/1e4).toFixed(1)}]});
  el.insertAdjacentHTML('afterbegin','<h4 style="margin:0 0 4px;font-size:14px;color:var(--brand-deep)">平台營收（萬円，堆疊）與廣告花費（萬円，右軸）</h4>');
})();

/* ---------- standard table ---------- */
const COLS=[['cost','廣告花費',fYen,'pct'],['rev','廣告營收',fYen,'pct'],['prev','平台營收',fYen,'pct'],['roas','廣告 ROAS',f2,'pct'],['proas','平台 ROAS',f2,'pct'],['cpm','CPM',fYen,'pct'],['ctr','CTR',fPct,'pp'],['cvr','廣告 CVR',fPct,'pp'],['pcvr','平台 CVR',fPct,'pp']];
function dl(a,b,mode,inverse){if(a==null||b==null||(mode==='pct'&&!b))return '<span class="dl flat">–</span>';
  const d=mode==='pct'?(a/b-1)*100:a-b,cls=Math.abs(d)<0.05?'flat':((d>0)!==!!inverse?'up':'down');
  return `<span class="dl ${cls}">${d>0?'▲':d<0?'▼':''}${Math.abs(d).toFixed(mode==='pct'?1:2)}${mode==='pct'?'%':'pt'}</span>`}
function cells(c,p,opt={}){return COLS.map(([k,_,f,mode])=>{const plat=['prev','proas','pcvr'].includes(k);
  if(plat&&opt.noPlat)return '<td class="na">—</td>';
  let extra='';if(k==='proas'&&opt.licPlat)extra=`<span class="sub">含授權金 ${f2(opt.licPlat)}</span>`;if(k==='roas'&&opt.licAd)extra=`<span class="sub">含授權金 ${f2(opt.licAd)}</span>`;if(k==='pcvr'&&opt.cvrNote)extra=`<span class="sub">${opt.cvrNote}</span>`;
  return `<td>${f(c[k])}${extra}${p?dl(c[k],p[k],mode,k==='cpm'):''}</td>`}).join('')}
const HEAD='<thead><tr><th>通路</th>'+COLS.map(c=>`<th>${c[1]}</th>`).join('')+'</tr></thead>';
function chRow(G,name,cls,id,parent){const c=met(G.src[CUR].channels[name]),p=met(G.src[PRV].channels[name]);
  return `<tr class="${cls}" data-parent="${parent||''}" ${parent?'hidden':''}><td>${id?`<span class="cat-chevron">›</span> `:''}${name}</td>${cells(c,p,{noPlat:true})}</tr>`}
function aOpts(i){const g=gWeek(GROUPS.A,i);return {licPlat:div(R.A[i].platform.sales,g.cost+LIC),licAd:div(g.rev,g.cost+LIC)}}
function groupRows(k,expand){const G=GROUPS[k],c=gMet(G,CUR),p=gMet(G,PRV);
  const opt=k==='A'?aOpts(CUR):k==='C'&&R.amzNote?{cvrNote:'11/5–11/10'}:{};
  let s=`<tr class="grp cat-row" data-g="${k}"><td><span class="cat-chevron">›</span> ${G.name} <span class="sub" style="display:inline">｜${G.plat}</span></td>${cells(c,p,opt)}</tr>`;
  G.ch.forEach(([n])=>{if(k==='A'&&n.startsWith('Google'))return;s+=chRow(G,n,'lvl1','',k)});
  if(k==='A'){const gg=i=>sum([R.A[i].channels['Google 品牌'],R.A[i].channels['Google 非品牌']]);
    s=s.replace(/(<tr class="lvl1" data-parent="A" hidden><td>ChatGPT)/,`<tr class="lvl1 cat-row" data-parent="A" data-g="G" hidden><td><span class="cat-chevron">›</span> Google</td>${cells(met(gg(CUR)),met(gg(PRV)),{noPlat:true})}</tr>`+chRow(G,'Google 品牌','lvl2','',  'G')+chRow(G,'Google 非品牌','lvl2','','G')+'$1')}
  return s}
function bindExpand(t){t.querySelectorAll('tr.cat-row').forEach(r=>r.onclick=()=>{const g=r.dataset.g,open=!r.classList.contains('expanded');r.classList.toggle('expanded',open);
  const hide=id=>t.querySelectorAll(`tr[data-parent="${id}"]`).forEach(x=>{x.hidden=!open;if(!open&&x.dataset.g){x.classList.remove('expanded');hide(x.dataset.g)}});
  if(open)t.querySelectorAll(`tr[data-parent="${g}"]`).forEach(x=>x.hidden=false);else hide(g)})}
(function(){const t=document.getElementById('ovTable');let s=HEAD+'<tbody>';['A','B','C'].forEach(k=>s+=groupRows(k));
  const tot=i=>{const x=sum(['A','B','C'].map(k=>gWeek(GROUPS[k],i)));const m=met(x);m.prev=['A','B','C'].reduce((a,k)=>a+GROUPS[k].src[i].platform.sales,0);m.proas=div(m.prev,x.cost);m.pcvr=null;return m};
  const tc=tot(CUR),tp=tot(PRV),tl=sum(['A','B','C'].map(k=>gWeek(GROUPS[k],CUR)));
  s+=`<tr class="grand"><td>三通路合計</td>${cells(tc,tp,{licPlat:div(tc.prev,tl.cost+LIC),licAd:div(tl.rev,tl.cost+LIC)})}</tr>`;
  t.innerHTML=s+'</tbody>';bindExpand(t);
  document.getElementById('ovNote').textContent=` 本週 KOL 授權金攤提 ¥${fInt(LIC)}。合計列的平台 CVR 不計算（三平台工作階段定義不同）。`+(R.amzNote?` Amazon：${R.amzNote}。`:'')})();

/* ---------- group sections ---------- */
['C','B','A'].forEach(k=>{
  const G=GROUPS[k],M=R.labels.map((_,i)=>gMet(G,i)),el=document.getElementById('charts'+k);
  const box=()=>{const d=document.createElement('div');d.className='mini';el.appendChild(d);return d};
  chart(box(),{title:'Cost 廣告花費',labels:R.labels,bars:G.ch.map(([n,c])=>({name:n,color:c,values:G.src.map(w=>w.channels[n].cost)})),fmtL:manAxis,tipL:fYen,barTotal:v=>(v/1e4).toFixed(1)});
  chart(box(),{title:'廣告營收 ＋ 平台營收（萬円）',labels:R.labels,fmtL:manAxis,lines:[{name:'廣告營收',color:G.color,values:M.map(m=>m.rev),fmt:v=>(v/1e4).toFixed(0)},{name:'平台營收',color:'#3d3220',dash:true,values:M.map(m=>m.prev),fmt:v=>(v/1e4).toFixed(0)}]});
  chart(box(),{title:'廣告 ROAS ＋ 平台 ROAS',labels:R.labels,fmtL:v=>v.toFixed(v<10?1:0),lines:[{name:'廣告 ROAS',color:G.color,values:M.map(m=>m.roas),fmt:f2},{name:'平台 ROAS',color:'#3d3220',dash:true,values:M.map(m=>m.proas),fmt:f2}]});
  chart(box(),{title:'CPM（円）',labels:R.labels,fmtL:v=>fInt(v),lines:[{name:'CPM',color:G.color,values:M.map(m=>m.cpm||null),fmt:fInt}]});
  chart(box(),{title:'CTR（%）',labels:R.labels,fmtL:v=>v.toFixed(1),lines:[{name:'CTR',color:G.color,values:M.map(m=>m.ctr),fmt:v=>v.toFixed(2)}]});
  chart(box(),{title:'廣告 CVR ＋ 平台 CVR（%）',labels:R.labels,fmtL:v=>v.toFixed(1),lines:[{name:'廣告 CVR',color:G.color,values:M.map(m=>m.cvr),fmt:v=>v.toFixed(2)},{name:'平台 CVR',color:'#3d3220',dash:true,values:M.map(m=>m.pcvr),fmt:v=>v.toFixed(2)}]});
  const t=document.getElementById('tbl'+k);t.innerHTML=HEAD+'<tbody>'+groupRows(k)+'</tbody>';bindExpand(t);t.querySelector('tr.cat-row').click();
  t.querySelectorAll('tr.cat-row').forEach(r=>{if(r.dataset.g==='G')r.click()});
  const hints={A:`平台 = Shopify 總銷售額、CVR = 訂單數 ÷ 工作階段。花費不含 KOL 授權金（本週 ¥${fInt(LIC)}），含授權金 ROAS 以小字顯示。ChatGPT 廣告 11/8 開始投放（30 天點擊＋1 天瀏覽歸因，花費約延遲 7–8 小時）。Google 轉換以轉換日計，之後幾天仍會回補。`,
    B:'平台 = R-Karte 売上／アクセス人数，平台 CVR = R-Karte 転換率（訂單數 = アクセス人数 × 転換率）。RPP 採 720 小時歸因；TDA 照報表（曝光為可視曝光）。RPP 曝光由點擊 ÷ CTR 推算。本週 RPP 未投放，TDA 11/6 起投放。',
    C:'平台 = Seller Central 已訂購商品銷售額，CVR = 訂單商品數 ÷ 工作階段。廣告 = SP 搜尋字詞報表（主控台匯出上限 300 列）。'+(R.amzNote?R.amzNote+'；11/11 營收取自銷售儀表板「昨天」全天。':'')};
  document.getElementById('hint'+k).textContent=hints[k];
});

/* ---------- Amazon brand / non-brand + exclusion ---------- */
(function(){const t=document.getElementById('tblAmzSide');let s='<thead><tr><th>類別</th>'+COLS.filter(c=>!['prev','proas','pcvr'].includes(c[0])).map(c=>`<th>${c[1]}</th>`).join('')+'</tr></thead><tbody>';
  ['品牌','非品牌'].forEach(side=>{const c=met(R.amzSide[side][CUR]),p=met(R.amzSide[side][PRV]);
    s+=`<tr><td>${side}</td>`+COLS.filter(x=>!['prev','proas','pcvr'].includes(x[0])).map(([k,_,f,mode])=>`<td>${f(c[k])}${dl(c[k],p[k],mode,k==='cpm')}</td>`).join('')+'</tr>'});
  t.innerHTML=s+'</tbody>';
  const e=document.getElementById('tblAmzEx');
  e.innerHTML='<thead><tr><th>搜尋字詞 / ASIN</th><th>分類</th><th>累計花費</th><th>累計訂單</th><th>出現週數</th><th>本週花費</th><th>建議</th></tr></thead><tbody>'+
    (R.amzEx.length?R.amzEx.map(x=>`<tr><td>${x.term}</td><td>${x.seg}</td><td>${fYen(x.cost)}</td><td>${x.orders}</td><td>${x.weeks}</td><td>${fYen(x.cur)}</td><td>${x.action}${x.cur>0?'（本週仍在花）':''}</td></tr>`).join(''):'<tr><td colspan="7" class="na">無</td></tr>')+'</tbody>'})();

/* ---------- Meta creatives ---------- */
const AD_IMG_DIR='../AD Images/';
function thumb(r){return `<span class="thumb-slot"><img src="${AD_IMG_DIR}${r}.jpg" class="thumb js-zoom" data-row="${r}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="thumb thumb-missing" style="display:none">缺圖<br>#${r}</div></span>`}
document.addEventListener('click',e=>{const im=e.target.closest('.js-zoom');if(!im)return;const lb=document.getElementById('lightbox');document.getElementById('lightboxImg').src=im.src;lb.style.display='flex'});
const tagOf=c=>c.tag||'NULL';const TAGS=[...new Set(R.creatives.map(tagOf))].sort((a,b)=>(a==='NULL')-(b==='NULL')||a.localeCompare(b));const TSEL=new Set(TAGS);
const CRH='<thead><tr><th>Name-Row</th><th>原廠標記</th><th>類型</th><th>花費</th><th>營收</th><th>ROAS</th><th>購買</th><th>CPA</th><th>CTR</th><th>CVR</th><th>CPM</th><th>上週花費</th><th>上週 ROAS</th></tr></thead>';
function crRow(c){const roas=div(c.rev,c.cost),pr=c.prev_cost?div(c.prev_rev,c.prev_cost):null;
  return `<tr><td><div style="display:flex;align-items:center;gap:8px">${thumb(c.row)}<span>${c.nameRow}</span></div></td><td>${c.tag?`<span class="tag-pill">${c.tag}</span>`:'<span class="na">NULL</span>'}</td><td><span class="type-pill">${c.type}</span></td>
  <td>${fYen(c.cost)}${c.prev_cost?dl(c.cost,c.prev_cost,'pct'):'<span class="dl flat">上週無花費</span>'}</td><td>${fYen(c.rev)}</td>
  <td><b>${f2(roas)}</b>${c.lic?`<span class="lic-s">含授權金 ${f2(div(c.rev,c.cost+c.lic))}（¥${fInt(c.lic)}）</span>`:''}${pr!=null?dl(roas,pr,'pct'):''}</td>
  <td>${fInt(c.pur)}</td><td>${c.pur?fYen(c.cost/c.pur):'–'}</td><td>${fPct(div(c.clicks,c.imp)*100)}</td><td>${fPct(div(c.pur,c.clicks)*100)}</td><td>${fYen(div(c.cost,c.imp)*1000)}</td>
  <td>${c.prev_cost?fYen(c.prev_cost):'–'}</td><td>${pr!=null?f2(pr):'–'}</td></tr>`}
function crTotal(rs){const x=rs.reduce((o,c)=>{o.cost+=c.cost;o.rev+=c.rev;o.pur+=c.pur;o.imp+=c.imp;o.clicks+=c.clicks;o.lic+=c.lic||0;return o},{cost:0,rev:0,pur:0,imp:0,clicks:0,lic:0});
  return `<tr class="grand"><td>小計（${rs.length}）</td><td></td><td></td><td>${fYen(x.cost)}</td><td>${fYen(x.rev)}</td><td>${f2(div(x.rev,x.cost))}${x.lic?`<span class="lic-s">含授權金 ${f2(div(x.rev,x.cost+x.lic))}</span>`:''}</td><td>${fInt(x.pur)}</td><td>${x.pur?fYen(x.cost/x.pur):'–'}</td><td>${fPct(div(x.clicks,x.imp)*100)}</td><td>${fPct(div(x.pur,x.clicks)*100)}</td><td>${fYen(div(x.cost,x.imp)*1000)}</td><td></td><td></td></tr>`}
function renderCr(){const rs=R.creatives.filter(c=>TSEL.has(tagOf(c)));
  const sm=rs.filter(c=>c.cost<R.minSpend),big=rs.filter(c=>c.cost>=R.minSpend),hi=big.filter(c=>c.rev/c.cost>=R.avgRoas),lo=big.filter(c=>c.rev/c.cost<R.avgRoas);
  [['tblCrHi',hi,'cntHi'],['tblCrLo',lo,'cntLo'],['tblCrSm',sm,'cntSm']].forEach(([id,arr,cid])=>{arr.sort((a,b)=>b.cost-a.cost);
    document.getElementById(id).innerHTML=CRH+'<tbody>'+(arr.length?arr.map(crRow).join('')+crTotal(arr):'<tr><td colspan="13" class="na">無</td></tr>')+'</tbody>';
    document.getElementById(cid).textContent=`${arr.length} 支`})}
function drawTF(){const box=document.getElementById('crTagFilter'),all=TSEL.size===TAGS.length;
  box.innerHTML='<span class="tf-label">原廠標記</span>'+TAGS.map(t=>`<label class="${TSEL.has(t)?'on':''}"><input type="checkbox" data-t="${t}" ${TSEL.has(t)?'checked':''}>${t}</label>`).join('')+`<button type="button">${all?'全部取消':'全選'}</button>`;
  box.querySelectorAll('input').forEach(cb=>cb.onchange=()=>{cb.checked?TSEL.add(cb.dataset.t):TSEL.delete(cb.dataset.t);drawTF();renderCr()});
  box.querySelector('button').onclick=()=>{if(all)TSEL.clear();else TAGS.forEach(t=>TSEL.add(t));drawTF();renderCr()}}
document.getElementById('crAvgNote').textContent=`平均 ROAS ${f2(R.avgRoas)}（本週 Meta 帳戶，不含授權金）`;
drawTF();renderCr();

/* ---------- 發佈 / 封存（W45+，只有編輯者看得到按鈕；權限由 _worker.js 在伺服器端控管） ---------- */
(function(){const bar=document.getElementById('pubBar');if(!bar||!location.protocol.startsWith('http'))return;
  const folder=THIS_REPORT_FILE.split('/')[0];
  const fmt=t=>{if(!t)return '';const d=new Date(t),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}/${z(d.getMonth()+1)}/${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}`};
  function draw(st,info){const pub=st==='published';
    bar.innerHTML=`<span class="pub-badge ${pub?'on':''}">${pub?'● 已發佈：檢視者可見':'● 封存中：只有編輯者看得到'}</span>`+
      (info&&info.by?`<span class="pub-meta">${pub?'發佈':'封存'}：${info.by} · ${fmt(info.at)}</span>`:'')+
      `<button class="ins-btn ${pub?'danger':'primary'}" id="pubBtn">${pub?'封存（對檢視者隱藏）':'發佈（讓檢視者可見）'}</button>`;
    bar.hidden=false;
    document.getElementById('pubBtn').onclick=async()=>{const next=pub?'archived':'published';
      if(!confirm(pub?`封存 ${folder}？檢視者將看不到這一週的週報。`:`發佈 ${folder}？所有檢視者都能看到這一週的週報。`))return;
      try{const r=await fetch('/api/publish',{method:'PUT',credentials:'same-origin',headers:{'content-type':'application/json'},body:JSON.stringify({folder,status:next})});
        const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||('HTTP '+r.status));draw(j.status,{by:j.by,at:j.at})}catch(e){alert('操作失敗：'+e.message)}}}
  fetch('/api/publish',{cache:'no-store',credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(r.status)).then(j=>{
    if(!j.canEdit)return;const info=(j.detail||{})[folder];draw(info&&info.status==='published'?'published':'archived',info)}).catch(()=>{});
})();
