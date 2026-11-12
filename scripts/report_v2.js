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
  o.labels.forEach((lb,i)=>{if(o.xEvery&&(n-1-i)%o.xEvery)return;const [a,b]=lb.split('\n');s+=`<text x="${X(i)}" y="${H-B+14}" text-anchor="middle" font-size="9.5" font-weight="${i===n-1?800:600}" fill="#6b6255">${a}</text><text x="${X(i)}" y="${H-B+26}" text-anchor="middle" font-size="8.5" fill="#9a9186">${b||''}</text>`});
  const tops=[];(o.bars||[]).length&&o.labels.forEach((_,i)=>{let acc=0;o.bars.forEach(b=>{const v=b.values[i]||0;if(v>0){const y0=YL(acc),y1=YL(acc+v);s+=`<rect x="${X(i)-bw*.32}" y="${y1}" width="${bw*.64}" height="${Math.max(0,y0-y1)}" fill="${b.color}"></rect>`}acc+=v});
    const ty=YL(acc)-4,hit=(o.lines||[]).some(l=>l.values[i]!=null&&Math.abs((l.right?YR:YL)(l.values[i])-ty+3)<11);tops[i]=hit?null:ty;
    if(o.barTotal&&acc>0)s+=hit?`<text x="${X(i)}" y="${YL(acc)+13}" text-anchor="middle" font-size="9.5" font-weight="800" fill="#fff">${o.barTotal(acc)}</text>`:`<text x="${X(i)}" y="${ty}" text-anchor="middle" font-size="9.5" font-weight="700" fill="#3d3220" stroke="#fff" stroke-width="3" paint-order="stroke">${o.barTotal(acc)}</text>`});
  (o.lines||[]).forEach(l=>{const Y=l.right?YR:YL;let d='',pen=false;l.values.forEach((v,i)=>{if(v==null){pen=false;return}d+=(pen?'L':'M')+X(i)+','+Y(v);pen=true});
    s+=`<path d="${d}" fill="none" stroke="${l.color}" stroke-width="2.2" ${l.dash?'stroke-dasharray="5 4"':''} stroke-linejoin="round"/>`;
    l.values.forEach((v,i)=>{if(v==null)return;s+=`<circle cx="${X(i)}" cy="${Y(v)}" r="3" fill="${l.color}"></circle>`;
      if(o.labelLast!==false&&(i===n-1||o.labelAll)){const ly=(o.barTotal&&tops[i]!=null&&Math.abs(Y(v)-7-tops[i])<12)?(Y(v)-7<tops[i]?Y(v)-14:Y(v)+16):Y(v)-7;s+=`<text x="${X(i)}" y="${ly}" text-anchor="middle" font-size="9.5" font-weight="700" fill="${l.color}" stroke="#fff" stroke-width="3" paint-order="stroke">${l.fmt(v)}</text>`}})});
  for(let i=0;i<n;i++)s+=`<rect class="hv" data-i="${i}" x="${X(i)-bw/2}" y="${T}" width="${bw}" height="${ih}" fill="transparent"/>`;
  s+='</svg>';
  const lg=[...(o.bars||[]).map(b=>`<span><i style="background:${b.color};height:10px"></i>${b.name}</span>`),...(o.lines||[]).map(l=>`<span><i style="background:${l.color}"></i>${l.name}${l.right?'（右軸）':''}</span>`)].join('');
  el.innerHTML=(o.title?`<h4>${o.title}</h4>`:'')+`<div class="lg">${lg}</div>`+s;
  el.querySelectorAll('.hv').forEach(r=>{const i=+r.dataset.i;
    r.onmouseenter=()=>{r.setAttribute('fill','rgba(169,130,46,.10)');
      const bars=(o.bars||[]).map(b=>[b.color,b.name,b.values[i]||0,(o.tipL||o.fmtL||(v=>v))]);
      let h=`<div class="tt-h">${o.labels[i].replace('\n','（')}${o.labels[i].includes('\n')?' 起）':''}</div>`;
      bars.forEach(([c,nm,v,f])=>h+=`<div class="tt-r"><i style="background:${c}"></i>${nm}<b>${f(v)}</b></div>`);
      if(bars.length>1)h+=`<div class="tt-r tt-tot">合計<b>${(o.tipL||o.fmtL)(bars.reduce((a,x)=>a+x[2],0))}</b></div>`;
      (o.lines||[]).forEach(l=>h+=`<div class="tt-r"><i style="background:${l.color};height:3px"></i>${l.name}<b>${l.values[i]==null?'–':(l.tip||l.fmt)(l.values[i])}</b></div>`);
      TIP.innerHTML=h;TIP.style.display='block'};
    r.onmousemove=e=>{const w=TIP.offsetWidth,x=e.clientX+16+w>innerWidth?e.clientX-w-16:e.clientX+16;TIP.style.left=x+'px';TIP.style.top=(e.clientY+14)+'px'};
    r.onmouseleave=()=>{r.setAttribute('fill','transparent');TIP.style.display='none'}});
}
const TIP=(()=>{const d=document.createElement('div');d.className='chart-tip';document.body.appendChild(d);return d})();
const man=v=>(v/1e4).toFixed(v>=1e6?0:1)+'萬',manAxis=v=>Math.round(v/1e4)+'';

/* ---------- 時間條（雙把手＋快速鍵；Part 1 與 Part 2 各組各自獨立） ---------- */
const WK=R.ytd.map(r=>({week:r.week,start:r.start}));
const wkLabel=r=>{const d=new Date(r.start+'T00:00:00');return `${r.week}\n${d.getMonth()+1}/${d.getDate()}`};
/* 篩選鈕：預設全選；全選狀態下點某一個 = 只看那一個；之後點擊為加選／取消；全部取消時自動回到全選；「全選」鈕一鍵回全選 */
function chipFilter(box,keys,sel,onChange){
  const chips=[...box.querySelectorAll('.rg-grp[data-k]')],allBtn=box.querySelector('.rg-all');
  const paint=()=>{const all=sel.size===keys.length;chips.forEach(c=>c.classList.toggle('on',!all&&sel.has(c.dataset.k)));chips.forEach(c=>c.classList.toggle('dim',!all&&!sel.has(c.dataset.k)));if(allBtn)allBtn.classList.toggle('on',all)};
  chips.forEach(c=>c.onclick=()=>{const k=c.dataset.k;
    if(sel.size===keys.length){sel.clear();sel.add(k)}else if(sel.has(k)){sel.delete(k);if(!sel.size)keys.forEach(x=>sel.add(x))}else sel.add(k);
    paint();onChange()});
  if(allBtn)allBtn.onclick=()=>{keys.forEach(x=>sel.add(x));paint();onChange()};
  paint()}
const chipHtml=(label,items)=>`<span class="rg-sep"></span><span class="rg-gl">${label}</span><button type="button" class="rg-all">全選</button>`+items.map(([k,txt,c])=>`<button type="button" class="rg-grp" data-k="${k}"><i style="background:${c}"></i>${txt}</button>`).join('');
function rangeBox(box,onChange,extraHtml){
  const NY=WK.length,id=box.id;let lo=Math.max(0,NY-8),hi=NY-1;
  const ticks=WK.map((r,i)=>{const d=new Date(r.start+'T00:00:00'),p=i?new Date(WK[i-1].start+'T00:00:00'):null;return (!p||p.getMonth()!==d.getMonth())?`<span style="left:${i/(NY-1)*100}%">${d.getMonth()+1}月</span>`:''}).join('');
  box.innerHTML=`<div class="rg-head"><span class="rg-title">📅 圖表顯示區間</span><span class="rg-label"></span></div>
    <div class="rg-track"><div class="rg-rail"></div><div class="rg-fill"></div>
      <input type="range" class="rg-lo" min="0" max="${NY-1}" step="1"><input type="range" class="rg-hi" min="0" max="${NY-1}" step="1"></div>
    <div class="rg-ticks">${ticks}</div>
    <div class="rg-presets">${[['8','近 8 週'],['12','近 12 週'],['26','近 26 週'],['all','全部']].map(([k,t])=>`<button type="button" class="rg-preset" data-n="${k}">${t}</button>`).join('')}${extraHtml||''}</div>`;
  const L=box.querySelector('.rg-lo'),H=box.querySelector('.rg-hi'),fill=box.querySelector('.rg-fill'),lab=box.querySelector('.rg-label');
  function upd(){const n=hi-lo+1,pct=i=>i/(NY-1)*100;
    lab.textContent=`${WK[lo].week}（${WK[lo].start.slice(5).replace('-','/')}）— ${WK[hi].week}（共 ${n} 週）`;
    fill.style.left=pct(lo)+'%';fill.style.width=(pct(hi)-pct(lo))+'%';L.value=lo;H.value=hi;
    box.querySelectorAll('.rg-preset').forEach(b=>b.classList.toggle('on',hi===NY-1&&(+b.dataset.n===n||(b.dataset.n==='all'&&lo===0))));
    onChange(lo,hi)}
  L.oninput=()=>{lo=Math.min(+L.value,hi);upd()};H.oninput=()=>{hi=Math.max(+H.value,lo);upd()};
  box.querySelectorAll('.rg-preset').forEach(b=>b.onclick=()=>{hi=NY-1;lo=b.dataset.n==='all'?0:Math.max(0,NY-(+b.dataset.n));upd()});
  const api={redraw:()=>onChange(lo,hi)};setTimeout(upd);return api}
const denseOpts=n=>({labelAll:n<=16,labelLast:n<=16,xEvery:n>26?4:(n>16?2:0)});

/* ---------- Overview chart（2026 W1 起；組別篩選 A／B／C 可複選） ---------- */
(function(){
  const Y=R.ytd,el=document.getElementById('ovChart'),box=document.getElementById('ovRange');
  const GS=[['A','(A) 官網｜Shopify','#3d6fb6','shopify','spendA'],['B','(B) 樂天','#c9473f','rakuten','spendB'],['C','(C) Amazon','#e8a33d','amazon','spendC']];
  const SEL=new Set(['A','B','C']);let LO=0,HI=0;
  function draw(lo,hi){LO=lo;HI=hi;const ys=Y.slice(lo,hi+1),n=ys.length,gs=GS.filter(g=>SEL.has(g[0])),dense=n>16;
    const order=['A','C','B'];gs.sort((a,b)=>order.indexOf(a[0])-order.indexOf(b[0]));
    chart(el,{w:1100,h:330,padL:50,right:true,labels:ys.map(wkLabel),...denseOpts(n),
      bars:gs.map(g=>({name:g[1],color:g[2],values:ys.map(r=>r[g[3]])})),
      barTotal:dense?null:(v=>(v/1e4).toFixed(0)),fmtL:manAxis,tipL:fYen,fmtR:manAxis,
      lines:gs.length?[{name:`廣告花費（${gs.map(g=>g[0]).join('＋')}，不含授權金）`,color:'#1f2a44',right:true,values:ys.map(r=>gs.reduce((a,g)=>a+r[g[4]],0)),fmt:v=>(v/1e4).toFixed(1),tip:fYen}]:[]});
    el.insertAdjacentHTML('afterbegin','<h4 style="margin:0 0 4px;font-size:14px;color:var(--brand-deep)">平台營收（萬円，堆疊）與廣告花費（萬円，右軸）</h4>')}
  const extra=chipHtml('組別',[['A','A · Shopify','#3d6fb6'],['B','B · 樂天','#c9473f'],['C','C · Amazon','#e8a33d']]);
  rangeBox(box,draw,extra);
  chipFilter(box,['A','B','C'],SEL,()=>draw(LO,HI));
})();

/* ---------- standard table ---------- */
const COLS=[['cost','廣告花費',fYen,'pct'],['rev','廣告營收',fYen,'pct'],['prev','平台營收',fYen,'pct'],['roas','廣告 ROAS',f2,'pct'],['proas','平台 ROAS',f2,'pct'],['cpm','CPM',fYen,'pct'],['ctr','CTR',fPct,'pct'],['cvr','廣告 CVR',fPct,'pct'],['pcvr','平台 CVR',fPct,'pct']];
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
function aOpts(i,G){G=G||GROUPS.A;if(!G.ch.some(c=>c[0]==='Meta'))return {};const g=gWeek(G,i);return {licPlat:div(R.A[i].platform.sales,g.cost+LIC),licAd:div(g.rev,g.cost+LIC)}}
function groupRows(k,Gx){const G=Gx||GROUPS[k],c=gMet(G,CUR),p=gMet(G,PRV);
  const opt=k==='A'?aOpts(CUR,G):k==='C'&&R.amzNote?{cvrNote:'11/5–11/10'}:{};
  let s=`<tr class="grp cat-row" data-g="${k}"><td><span class="cat-chevron">›</span> ${G.name} <span class="sub" style="display:inline">｜${G.plat}</span></td>${cells(c,p,opt)}</tr>`;
  const names=G.ch.map(x=>x[0]);
  if(k==='A'){
    if(names.includes('Meta'))s+=chRow(G,'Meta','lvl1','',k);
    const gs=names.filter(n=>n.startsWith('Google'));
    if(gs.length){const gg=i=>sum(gs.map(n=>R.A[i].channels[n]));
      s+=`<tr class="lvl1 cat-row" data-parent="A" data-g="G" hidden><td><span class="cat-chevron">›</span> Google</td>${cells(met(gg(CUR)),met(gg(PRV)),{noPlat:true})}</tr>`+gs.map(n=>chRow(G,n,'lvl2','','G')).join('')}
    if(names.includes('ChatGPT'))s+=chRow(G,'ChatGPT','lvl1','',k);
  }else names.forEach(n=>{s+=chRow(G,n,'lvl1','',k)});
  if(k==='C'){const rx='<tr class="lvl1" data-parent="C" hidden><td>Amazon AD</td>';if(s.includes(rx)){
    s=s.replace(rx,'<tr class="lvl1 cat-row" data-parent="C" data-g="AMZ" hidden><td><span class="cat-chevron">›</span> Amazon AD</td>');
    s+=['品牌','非品牌'].map(n=>`<tr class="lvl2" data-parent="AMZ" hidden><td>Amazon AD ${n}</td>${cells(met(R.amzSide[n][CUR]),met(R.amzSide[n][PRV]),{noPlat:true})}</tr>`).join('')}}
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
  const G0=GROUPS[k],FG=R.G[k],el=document.getElementById('charts'+k);
  const CSEL=new Set(G0.ch.map(c=>c[0]));let G=G0,MF=null;
  const calcMF=()=>{G={...G0,ch:G0.ch.filter(c=>CSEL.has(c[0]))};MF=FG.map(w=>{const m=met(sum(G.ch.map(c=>w.channels[c[0]])),w.platform);if(!m.cost)m.rev=null;if(!w.platform.sales&&!w.platform.sessions){m.prev=null;m.pcvr=null}return m})};calcMF();
  const boxes=[...Array(k==='A'?7:6)].map(()=>{const d=document.createElement('div');d.className='mini';el.appendChild(d);return d});
  const extra=k==='A'?chipHtml('廣告渠道',G0.ch.map(([n,c])=>[n,n,c])):'';
  const t=document.getElementById('tbl'+k);
  const drawTable=()=>{const open=[...t.querySelectorAll('tr.cat-row.expanded')].map(r=>r.dataset.g);const first=!t.tBodies.length;
    t.innerHTML=HEAD+'<tbody>'+groupRows(k,G)+'</tbody>';bindExpand(t);
    (first?[k,'G','AMZ']:open).forEach(g=>{const r=t.querySelector(`tr.cat-row[data-g="${g}"]`);if(r&&!r.hidden)r.click()});
    if(!first)sortable(t)};
  const RB=rangeBox(document.getElementById('rg'+k),(lo,hi)=>{
    const M=MF.slice(lo,hi+1),W=FG.slice(lo,hi+1),L=WK.slice(lo,hi+1).map(wkLabel),D=denseOpts(M.length),dense=M.length>16;
    chart(boxes[0],{title:'Cost 廣告花費',labels:L,...D,bars:G.ch.map(([n,c])=>({name:n,color:c,values:W.map(w=>w.channels[n].cost)})),fmtL:manAxis,tipL:fYen,barTotal:dense?null:(v=>(v/1e4).toFixed(1))});
    chart(boxes[1],{title:'廣告營收 ＋ 平台營收（萬円）',labels:L,...D,fmtL:manAxis,lines:[{name:'廣告營收',color:G.color,values:M.map(m=>m.rev),fmt:v=>(v/1e4).toFixed(0),tip:fYen},{name:'平台營收',color:'#3d3220',dash:true,values:M.map(m=>m.prev),fmt:v=>(v/1e4).toFixed(0),tip:fYen}]});
    chart(boxes[2],{title:'廣告 ROAS ＋ 平台 ROAS',labels:L,...D,fmtL:v=>v.toFixed(v<10?1:0),lines:[{name:'廣告 ROAS',color:G.color,values:M.map(m=>m.roas),fmt:f2},{name:'平台 ROAS',color:'#3d3220',dash:true,values:M.map(m=>m.proas),fmt:f2}]});
    chart(boxes[3],{title:'CPM（円）',labels:L,...D,fmtL:v=>fInt(v),lines:[{name:'CPM',color:G.color,values:M.map(m=>m.cpm||null),fmt:fInt,tip:fYen}]});
    chart(boxes[4],{title:'CTR（%）',labels:L,...D,fmtL:v=>v.toFixed(1),lines:[{name:'CTR',color:G.color,values:M.map(m=>m.ctr),fmt:v=>v.toFixed(2),tip:fPct}]});
    chart(boxes[5],{title:'廣告 CVR ＋ 平台 CVR（%）',labels:L,...D,fmtL:v=>v.toFixed(1),lines:[{name:'廣告 CVR',color:G.color,values:M.map(m=>m.cvr),fmt:v=>v.toFixed(2),tip:fPct},{name:'平台 CVR',color:'#3d3220',dash:true,values:M.map(m=>m.pcvr),fmt:v=>v.toFixed(2),tip:fPct}]});
    if(k==='A'){const P=W.map(w=>w.platform);
      chart(boxes[6],{title:'官網漏斗：加入購物車率（右軸）＋ 加購→結帳完成率（左軸）（%）',w:1100,h:300,right:true,labels:L,...D,fmtL:v=>v.toFixed(0),fmtR:v=>v.toFixed(1),lines:[
        {name:'加入購物車率（加購工作階段 ÷ 工作階段）',color:'#3d6fb6',right:true,values:P.map(p=>p.sessions&&p.cart!=null?p.cart/p.sessions*100:null),fmt:v=>v.toFixed(2),tip:fPct},
        {name:'加購→結帳完成率（完成結帳 ÷ 加購工作階段）',color:'#c9473f',values:P.map(p=>p.cart?p.comp/p.cart*100:null),fmt:v=>v.toFixed(1),tip:fPct}]});
      boxes[6].classList.add('mini-wide')}
  },extra);
  drawTable();
  if(k==='A')chipFilter(document.getElementById('rgA'),G0.ch.map(c=>c[0]),CSEL,()=>{calcMF();RB.redraw();drawTable()});
  const hints={A:`平台 = Shopify 總銷售額、CVR = 訂單數 ÷ 工作階段。花費不含 KOL 授權金（本週 ¥${fInt(LIC)}），含授權金 ROAS 以小字顯示。ChatGPT 廣告 11/8 開始投放（30 天點擊＋1 天瀏覽歸因，花費約延遲 7–8 小時）。Google 轉換以轉換日計，之後幾天仍會回補。`,
    B:'平台 = R-Karte 売上／アクセス人数，平台 CVR = R-Karte 転換率（訂單數 = アクセス人数 × 転換率）。RPP 採 720 小時歸因；TDA 照報表（曝光為可視曝光）。RPP 曝光由點擊 ÷ CTR 推算。本週 RPP 未投放，TDA 11/6 起投放。',
    C:'平台 = Seller Central 已訂購商品銷售額，CVR = 訂單商品數 ÷ 工作階段。Amazon AD 可展開為品牌（品牌字 hulken／ハルケン…＋自家 ASIN）／非品牌。廣告 = SP 搜尋字詞報表（主控台匯出上限 300 列）。'+(R.amzNote?R.amzNote+'；11/11 營收取自銷售儀表板「昨天」全天。':'')};
  document.getElementById('hint'+k).textContent=hints[k];
});

/* ---------- Amazon brand / non-brand + exclusion ---------- */
(function(){
  const e=document.getElementById('tblAmzEx');
  e.innerHTML='<thead><tr><th>搜尋字詞 / ASIN</th><th>分類</th><th>累計花費</th><th>累計訂單</th><th>出現週數</th><th>本週花費</th><th>建議</th><th>狀態</th></tr></thead><tbody>'+
    (R.amzEx.length?R.amzEx.map(x=>`<tr><td>${x.term}</td><td>${x.seg}</td><td>${fYen(x.cost)}</td><td>${x.orders}</td><td>${x.weeks}</td><td>${fYen(x.cur)}</td><td>${x.action}${x.cur>0?'（本週仍在花）':''}</td><td>${x.done?`<span class="done-pill">✓ 已執行${x.done!=='先前'?'（'+x.done.slice(5).replace('-','/')+'）':''}</span>`:'<span class="na">待執行</span>'}</td></tr>`).join(''):'<tr><td colspan="8" class="na">無</td></tr>')+'</tbody>'})();

/* ---------- 表格點擊排序（預設：廣告 ROAS 大到小；子列在各自上層內排序；合計列固定在最下） ---------- */
const SORT_STATE={};
function cellVal(td,isText){if(!td)return null;const n=td.childNodes[0];const t=(isText||!n?td.textContent:n.textContent).trim();
  if(isText)return t;const v=parseFloat(t.replace(/[¥,%]/g,''));return isNaN(v)?null:v}
function sortable(t){if(!t||!t.tHead)return;const ths=[...t.tHead.rows[0].cells];
  let st=SORT_STATE[t.id];if(!st){let c=ths.findIndex(th=>th.dataset.lab==='廣告 ROAS'||th.textContent.trim()==='廣告 ROAS');if(c<0)c=ths.findIndex(th=>th.textContent.trim()==='ROAS');if(c<0)c=ths.findIndex(th=>/花費/.test(th.textContent));st=SORT_STATE[t.id]={col:c<0?1:c,dir:-1}}
  ths.forEach((th,i)=>{th.classList.add('sortable');if(!th.dataset.lab)th.dataset.lab=th.textContent.trim();th.innerHTML=th.dataset.lab+(i===st.col?(st.dir<0?' ▼':' ▲'):'');
    th.onclick=()=>{st.dir=st.col===i?-st.dir:(i===0?1:-1);st.col=i;sortable(t)}});
  const tb=t.tBodies[0];if(!tb)return;const rows=[...tb.rows];if(rows.length<2)return;
  const grand=rows.filter(r=>r.classList.contains('grand')),rest=rows.filter(r=>!r.classList.contains('grand'));
  const kids={},top=[];rest.forEach(r=>{const p=r.getAttribute('data-parent');if(p)(kids[p]=kids[p]||[]).push(r);else top.push(r)});
  const cmp=(a,b)=>{const isT=st.col===0,va=cellVal(a.cells[st.col],isT),vb=cellVal(b.cells[st.col],isT);
    if(va==null&&vb==null)return 0;if(va==null)return 1;if(vb==null)return -1;return isT?st.dir*String(va).localeCompare(String(vb)):st.dir*(va-vb)};
  const out=[];const walk=list=>{list.sort(cmp).forEach(r=>{out.push(r);const g=r.dataset.g;if(g&&kids[g])walk(kids[g])})};walk(top);
  [...out,...grand].forEach(r=>tb.appendChild(r))}

/* ---------- Meta creatives ---------- */
const AD_IMG_DIR='../AD Images/';
function thumb(r){return `<span class="thumb-slot"><img src="${AD_IMG_DIR}${r}.jpg" class="thumb js-zoom" data-row="${r}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="thumb thumb-missing" style="display:none">缺圖<br>#${r}</div></span>`}
document.addEventListener('click',e=>{const im=e.target.closest('.js-zoom');if(!im)return;const lb=document.getElementById('lightbox');document.getElementById('lightboxImg').src=im.src;lb.style.display='flex'});
const tagOf=c=>c.tag||'NULL';const TAGS=[...new Set(R.creatives.map(tagOf))].sort((a,b)=>(a==='NULL')-(b==='NULL')||a.localeCompare(b));const TSEL=new Set(TAGS);
const CRH='<thead><tr><th>Name-Row</th><th>原廠標記</th><th>花費</th><th>營收</th><th>ROAS</th><th>購買</th><th>CPA</th><th>CTR</th><th>CVR</th><th>CPM</th></tr></thead>';
function crMet(x){return {cost:x.cost,rev:x.rev,roas:div(x.rev,x.cost),pur:x.pur,cpa:x.pur?x.cost/x.pur:null,ctr:x.imp?x.clicks/x.imp*100:null,cvr:x.clicks?x.pur/x.clicks*100:null,cpm:x.imp?x.cost/x.imp*1000:null}}
function crPrev(c){return c.prev_cost?crMet({cost:c.prev_cost,rev:c.prev_rev,pur:c.prev_pur,imp:c.prev_imp,clicks:c.prev_clicks}):null}
function crCells(m,p,opt={}){const D=(k,inv)=>p?dl(m[k],p[k],'pct',inv):(k==='cost'?'<span class="dl flat">上週無花費</span>':'<span class="dl flat">–</span>');
  return `<td>${fYen(m.cost)}${D('cost')}</td><td>${fYen(m.rev)}${D('rev')}</td><td>${opt.bold?'<b>':''}${f2(m.roas)}${opt.bold?'</b>':''}${opt.lic||''}${D('roas')}</td>
  <td>${fInt(m.pur)}${D('pur')}</td><td>${fYen(m.cpa)}${D('cpa',true)}</td><td>${fPct(m.ctr)}${D('ctr')}</td><td>${fPct(m.cvr)}${D('cvr')}</td><td>${fYen(m.cpm)}${D('cpm',true)}</td>`}
function crRow(c){const m=crMet(c);
  return `<tr><td><div style="display:flex;align-items:center;gap:8px">${thumb(c.row)}<span>${c.nameRow}</span></div></td><td>${c.tag?`<span class="tag-pill">${c.tag}</span>`:'<span class="na">NULL</span>'}</td>`+
    crCells(m,crPrev(c),{bold:true,lic:c.lic?`<span class="lic-s">含授權金 ${f2(div(c.rev,c.cost+c.lic))}（¥${fInt(c.lic)}）</span>`:''})+'</tr>'}
function crTotal(rs){const z=()=>({cost:0,rev:0,pur:0,imp:0,clicks:0});const x=z(),y=z();let lic=0;
  rs.forEach(c=>{x.cost+=c.cost;x.rev+=c.rev;x.pur+=c.pur;x.imp+=c.imp;x.clicks+=c.clicks;lic+=c.lic||0;if(c.prev_cost){y.cost+=c.prev_cost;y.rev+=c.prev_rev;y.pur+=c.prev_pur;y.imp+=c.prev_imp;y.clicks+=c.prev_clicks}});
  return `<tr class="grand"><td>小計（${rs.length}）</td><td></td>`+crCells(crMet(x),y.cost?crMet(y):null,{lic:lic?`<span class="lic-s">含授權金 ${f2(div(x.rev,x.cost+lic))}</span>`:''})+'</tr>'}
function renderCr(){const rs=R.creatives.filter(c=>TSEL.has(tagOf(c)));
  const sm=rs.filter(c=>c.cost<R.minSpend),big=rs.filter(c=>c.cost>=R.minSpend),hi=big.filter(c=>c.rev/c.cost>=R.avgRoas),lo=big.filter(c=>c.rev/c.cost<R.avgRoas);
  [['tblCrHi',hi,'cntHi'],['tblCrLo',lo,'cntLo'],['tblCrSm',sm,'cntSm']].forEach(([id,arr,cid])=>{arr.sort((a,b)=>b.cost-a.cost);
    document.getElementById(id).innerHTML=CRH+'<tbody>'+(arr.length?arr.map(crRow).join('')+crTotal(arr):'<tr><td colspan="10" class="na">無</td></tr>')+'</tbody>';
    document.getElementById(cid).textContent=`${arr.length} 支`;sortable(document.getElementById(id))})}
function drawTF(){const box=document.getElementById('crTagFilter');
  box.innerHTML='<span class="rg-gl">原廠標記</span><button type="button" class="rg-all">全選</button>'+TAGS.map(t=>`<button type="button" class="rg-grp" data-k="${t}">${t}</button>`).join('');
  chipFilter(box,TAGS,TSEL,renderCr)}
drawTF();renderCr();
['ovTable','tblC','tblB','tblA','tblAmzEx'].forEach(id=>sortable(document.getElementById(id)));

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
