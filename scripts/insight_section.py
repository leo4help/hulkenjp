"""
Insight & Suggestion section (added 2026-10-14, W41) — replaces the old
Weekly-Insight-tab callout. Content format borrowed from the innodanc weekly
report (rows of 分類 / 標題 / 核心洞察 / 執行建議 + a 下週 Action Plan list);
look & feel stays Hulken's own (CSS vars, card/table styles).

Data flow:
  * insights.json (project root) holds Claude's written draft per week, key =
    that week's start date (Thursday) "YYYY-MM-DD". build_weekly_report.py
    embeds that week's entry as INSIGHTS_BUILTIN and the key as INSIGHT_WEEK.
  * Online edits are stored in Cloudflare D1 via _worker.js (/api/insights).
    The page fetches /api/insights; an online version for INSIGHT_WEEK wins
    over the built-in draft. Only ALLOWED_EDITORS (ads@wakazocorp.com) can
    edit; everyone else behind Cloudflare Access just reads.
  * Opened from file:// (local preview) the API fetch fails -> read-only.
"""

CSS = r"""
  /* ---------- Insight & Suggestion (W41+) ---------- */
  .ins-table{width:100%;border-collapse:collapse;font-size:13.5px;}
  .ins-table th{background:var(--tan-soft);color:var(--brand-deep);font-weight:800;text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);}
  .ins-table td{vertical-align:top;padding:12px 14px;border-bottom:1px solid var(--line);line-height:1.7;text-align:left;white-space:normal;}
  .ins-table td:first-child{width:58%;}
  .ins-table tr:last-child td{border-bottom:none;}
  .ins-ch{display:inline-block;font-size:11px;font-weight:800;color:var(--brand-deep);background:var(--tan-soft);border:1px solid var(--tan);padding:1px 8px;border-radius:6px;margin-bottom:4px;}
  .ins-empty{color:var(--ink-faint);text-align:center!important;padding:22px!important;}
  .ins-actions{margin:0;padding-left:22px;line-height:1.9;font-size:13.5px;}
  .ins-sub{font-size:14px;font-weight:800;color:var(--brand-deep);margin:22px 0 10px;}
  .ins-bar{display:flex;align-items:center;gap:10px;margin:-4px 0 14px;flex-wrap:wrap;min-height:4px;}
  .ins-btn{border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:8px;padding:6px 12px;font:inherit;font-size:12.5px;font-weight:700;cursor:pointer;}
  .ins-btn:hover{border-color:var(--brand-gold);color:var(--brand-deep);}
  .ins-btn.primary{background:linear-gradient(135deg,var(--brand-gold),#c79b3f);border-color:transparent;color:#fff;}
  .ins-btn.primary.on{background:#fff;color:var(--brand-deep);border-color:var(--brand-gold);}
  .ins-btn.danger{color:var(--bad);}
  .ins-btn.sm{padding:2px 7px;font-size:12px;margin:0 1px 3px;}
  .ins-status{font-size:12px;color:var(--ink-soft);}
  .ins-status .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#e0a100;margin-right:6px;}
  .ins-status .dot.ok{background:var(--good);} .ins-status .dot.err{background:var(--bad);}
  .ins-in,.ins-ta{width:100%;font:inherit;font-size:13.5px;color:var(--ink);border:1px solid var(--tan);border-radius:8px;padding:7px 9px;background:#fffdf8;}
  .ins-in:focus,.ins-ta:focus{outline:2px solid #e8cf8a;border-color:var(--brand-gold);}
  .ins-ta{min-height:78px;resize:vertical;line-height:1.6;margin-top:6px;}
  .ins-line{display:flex;gap:6px;} .ins-line .ins-ch-in{max-width:120px;} .ins-line .ins-title{font-weight:700;}
  .ins-ops{text-align:center!important;white-space:nowrap;width:44px;}
  .ins-act-ed{margin:0;padding-left:22px;} .ins-act-ed li{display:flex;gap:4px;align-items:center;margin:5px 0;}
  body.ins-editing #insight .card{box-shadow:0 0 0 2px #e8cf8a;}
"""

HTML = r"""
  <!-- ================= INSIGHT & SUGGESTION (W41+, editable) ================= -->
  <section id="insight">
    <div class="sec-head"><h2>Insight &amp; Suggestion</h2><span class="sec-tag">核心洞察與執行建議 · 本週重點</span></div>
    <div class="ins-bar">
      <button class="ins-btn primary" id="insEditBtn" style="display:none">✎ 編輯</button>
      <span class="ins-status" id="insStatus"></span>
      <span style="flex:1"></span>
      <button class="ins-btn danger" id="insRevertBtn" style="display:none" title="刪除線上修改，回到建置時的原始版本">還原原始版本</button>
    </div>
    <datalist id="insChOpts"><option>整體</option><option>Meta</option><option>Google</option><option>Amazon</option><option>樂天</option><option>KOL</option><option>素材</option><option>Shopify</option><option>追蹤</option></datalist>
    <div class="card" style="padding:0;overflow:hidden;"><div class="table-scroll" style="border:none;border-radius:0;"><table class="ins-table" id="insTable"></table></div></div>
    <div class="ins-sub">下週 Action Plan</div>
    <div class="card" id="insActions"></div>
  </section>
"""

JS = r"""
/* ---------------- Insight & Suggestion (W41+, editable via Cloudflare D1) ---------------- */
const INSIGHT_WEEK = '';
const INSIGHTS_BUILTIN = {};
(function(){
  const API='/api/insights';
  const $i=id=>document.getElementById(id);
  const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const md=s=>esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\n/g,'<br>');
  const norm=o=>({rows:((o&&o.rows)||[]).map(r=>({channel:r.channel||'',title:r.title||'',insight:r.insight||'',suggestion:r.suggestion||''})),actions:((o&&o.actions)||[]).slice()});
  let remote=null,work=null,apiOK=false,canEdit=false,editing=false,state='',timer=null;
  const cur=()=>work||remote||norm(INSIGHTS_BUILTIN);
  const ed=()=>{if(!work)work=JSON.parse(JSON.stringify(norm(cur())));return work};
  const clean=d=>({rows:d.rows.filter(r=>(r.title+r.insight+r.suggestion).trim()),actions:d.actions.filter(a=>a&&a.trim())});
  function grow(el){el.style.height='auto';el.style.height=(el.scrollHeight+2)+'px'}
  function queue(){state='pending';bar();clearTimeout(timer);timer=setTimeout(save,900)}
  async function save(){
    clearTimeout(timer);if(!work)return;state='saving';bar();
    try{const r=await fetch(API,{method:'PUT',headers:{'content-type':'application/json'},credentials:'same-origin',body:JSON.stringify({week:INSIGHT_WEEK,data:clean(work)})});
      const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||('HTTP '+r.status));remote=j.item;state='saved'}
    catch(e){state='error:'+e.message}
    bar();
  }
  function fmtAt(t){if(!t)return '';const d=new Date(t);if(isNaN(d))return t;const z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}/${z(d.getMonth()+1)}/${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}`}
  function bar(){
    let m='';
    if(state==='pending'||state==='saving')m='<span class="dot"></span>儲存中…';
    else if(state.startsWith('error:'))m=`<span class="dot err"></span>儲存失敗：${esc(state.slice(6))}（內容仍在畫面上，再改一下即可重試）`;
    else if(state==='saved')m='<span class="dot ok"></span>已儲存，其他人重新整理即可看到';
    else if(remote&&remote._by)m=`最後編輯：${esc(remote._by)} · ${fmtAt(remote._at)}`;
    else if(editing)m='修改會自動儲存';
    $i('insStatus').innerHTML=m;
    const b=$i('insEditBtn');b.style.display=(apiOK&&canEdit)?'':'none';b.textContent=editing?'✓ 完成編輯':'✎ 編輯';b.classList.toggle('on',editing);
    $i('insRevertBtn').style.display=(apiOK&&canEdit&&remote)?'':'none';
    document.body.classList.toggle('ins-editing',editing);
  }
  function render(){
    const d=editing?ed():cur();const rows=d.rows||[];const t=$i('insTable');
    let s='<thead><tr><th>核心洞察 (Insight)</th><th>執行建議 (Suggestion)</th>'+(editing?'<th></th>':'')+'</tr></thead><tbody>';
    if(editing){
      rows.forEach((r,i)=>s+=`<tr data-i="${i}"><td><div class="ins-line"><input list="insChOpts" class="ins-in ins-ch-in" data-f="channel" value="${esc(r.channel)}" placeholder="分類"><input class="ins-in ins-title" data-f="title" value="${esc(r.title)}" placeholder="洞察標題（粗體）"></div><textarea class="ins-ta" data-f="insight" placeholder="洞察內容（**文字** = 粗體）">${esc(r.insight)}</textarea></td><td><textarea class="ins-ta" data-f="suggestion" placeholder="執行建議">${esc(r.suggestion)}</textarea></td><td class="ins-ops"><button class="ins-btn sm" data-op="up">↑</button><button class="ins-btn sm" data-op="down">↓</button><button class="ins-btn sm danger" data-op="del">✕</button></td></tr>`);
      s+='<tr><td colspan="3"><button class="ins-btn" id="insAddRow">＋ 新增一列</button></td></tr>';
    }else if(rows.length)rows.forEach(r=>s+=`<tr><td>${r.channel?`<span class="ins-ch">${esc(r.channel)}</span><br>`:''}${r.title?`<b>${esc(r.title)}</b>：`:''}${md(r.insight)}</td><td>${md(r.suggestion)}</td></tr>`);
    else s+='<tr><td colspan="2" class="ins-empty">本週尚未填寫洞察</td></tr>';
    t.innerHTML=s+'</tbody>';
    const acts=d.actions||[];const box=$i('insActions');
    if(editing){
      box.innerHTML=`<ol class="ins-act-ed">${acts.map((a,i)=>`<li data-i="${i}"><input class="ins-in" value="${esc(a)}" placeholder="下週執行重點"><button class="ins-btn sm" data-op="up">↑</button><button class="ins-btn sm" data-op="down">↓</button><button class="ins-btn sm danger" data-op="del">✕</button></li>`).join('')}</ol><button class="ins-btn" id="insAddAct" style="margin-top:8px">＋ 新增一項</button>`;
    }else box.innerHTML=acts.length?`<ol class="ins-actions">${acts.map(a=>`<li>${md(a)}</li>`).join('')}</ol>`:'<div class="ins-empty">本週尚未填寫 Action Plan</div>';
    bar();
    if(!editing)return;
    t.querySelectorAll('textarea').forEach(grow);
    t.querySelectorAll('[data-f]').forEach(el=>el.addEventListener('input',()=>{ed().rows[+el.closest('tr').dataset.i][el.dataset.f]=el.value;if(el.tagName==='TEXTAREA')grow(el);queue()}));
    const move=(X,i,op)=>{if(op==='del'){if((typeof X[i]==='string'?X[i]:(X[i].title+X[i].insight+X[i].suggestion)).trim()&&!confirm('確定刪除這一列？'))return false;X.splice(i,1)}
      if(op==='up'&&i>0)[X[i-1],X[i]]=[X[i],X[i-1]];if(op==='down'&&i<X.length-1)[X[i+1],X[i]]=[X[i],X[i+1]];return true};
    t.querySelectorAll('[data-op]').forEach(b=>b.onclick=()=>{if(move(ed().rows,+b.closest('tr').dataset.i,b.dataset.op)){queue();render()}});
    $i('insAddRow').onclick=()=>{ed().rows.push({channel:'',title:'',insight:'',suggestion:''});queue();render();const l=[...t.querySelectorAll('.ins-title')].pop();l&&l.focus()};
    box.querySelectorAll('li input').forEach(el=>el.addEventListener('input',()=>{ed().actions[+el.closest('li').dataset.i]=el.value;queue()}));
    box.querySelectorAll('[data-op]').forEach(b=>b.onclick=()=>{if(move(ed().actions,+b.closest('li').dataset.i,b.dataset.op)){queue();render()}});
    $i('insAddAct').onclick=()=>{ed().actions.push('');queue();render();const l=[...box.querySelectorAll('li input')].pop();l&&l.focus()};
  }
  $i('insEditBtn').onclick=async()=>{if(editing){if(state==='pending')await save();editing=false;if(!state.startsWith('error:')){work=null;state=''}}else editing=true;render()};
  $i('insRevertBtn').onclick=async()=>{
    if(!confirm('把本週的 Insight & Suggestion 還原成建置時的原始版本？（所有人都會看到還原後的內容）'))return;
    try{const r=await fetch(API+'?week='+encodeURIComponent(INSIGHT_WEEK),{method:'DELETE',credentials:'same-origin'});if(!r.ok)throw new Error('HTTP '+r.status);
      remote=null;work=null;state='';editing=false;render()}catch(e){alert('還原失敗：'+e.message)}};
  addEventListener('beforeunload',e=>{if(state==='pending'||state==='saving'){e.preventDefault();e.returnValue=''}});
  render();
  if(location.protocol.startsWith('http'))fetch(API,{cache:'no-store',credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(r.status)).then(j=>{
    apiOK=true;canEdit=!!j.canEdit;const o=(j.insights||{})[INSIGHT_WEEK];remote=o?Object.assign(norm(o),{_by:o._by,_at:o._at}):null;render()}).catch(()=>{apiOK=false;bar()});
})();
"""


def ensure_block(html):
    """Inject CSS / section / JS once (idempotent). Section goes right after
    the #channels section; nav gets an 'Insight & Suggestion' link after 全渠道成效."""
    if 'id="insight"' in html:
        return html
    i = html.find('</style>')
    if i < 0:
        raise SystemExit('insight_section: no </style> found')
    html = html[:i] + CSS + html[i:]
    start = html.find('<section id="channels">')
    end = html.find('</section>', start)
    if start < 0 or end < 0:
        raise SystemExit('insight_section: #channels section not found')
    end += len('</section>')
    html = html[:end] + '\n' + HTML.rstrip('\n') + html[end:]
    nav_old = '<a href="#channels">全渠道成效</a>'
    if nav_old in html:
        html = html.replace(nav_old, nav_old + '\n    <a href="#insight">Insight &amp; Suggestion</a>', 1)
    j = html.rfind('</script>')
    if j < 0:
        raise SystemExit('insight_section: no </script> found')
    return html[:j] + JS + html[j:]
