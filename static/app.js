// 成就奖履历总览 -- 页面逻辑（搜索、排序、个人履历、对比、图表、手动调整、自动载入）
(function(){
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const C=window.Core;
let ALL=window.EMBED||[], INFO=window.EMBED_INFO||{files:0,when:''};
const CATLIST=[...C.CATS.filter(c=>c.key!=='total'),C.OTHER];
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=n=>n==null?'—':(Math.round(n*10)/10).toLocaleString('zh-CN');
let state={q:'',club:'',cls:'',year:'',issue:false,sort:'hours',dir:-1,cmp:new Set()};

// ----- theme
try{const t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;}catch(e){}
$('#theme').onclick=()=>{const cur=document.documentElement.dataset.theme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');const n=cur==='dark'?'light':'dark';document.documentElement.dataset.theme=n;try{localStorage.setItem('theme',n)}catch(e){}};

// ----- per-view stats (optionally restricted to one year)
let OV=Object.assign({},window.EMBED_OV||{});if(!window.LIVE){try{Object.assign(OV,JSON.parse(localStorage.getItem('ov-v1')||'{}'))}catch(e){}}
let OVV=0;const SC=new Map();
let ovTimer=null;
function saveOV(){OVV++;SC.clear();
  if(window.LIVE){clearTimeout(ovTimer);ovTimer=setTimeout(()=>fetch('api/overrides',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(OV)}).then(r=>r.ok?toast('手动调整已保存到文件夹'):toast('保存失败',1)).catch(()=>toast('工具已关闭，调整没有保存',1)),400);return}
  try{localStorage.setItem('ov-v1',JSON.stringify(OV))}catch(e){}}
function statsFor(s,year){
  const k=(s.sid||s.file)+'|'+(year||'');let r=SC.get(k);
  if(!r){r=C.computeStats(s,OV,year);const lb=[...r.roleByBlock.entries()].find(([b,l])=>l.length);r.roleLatest=lb?lb[1].join('、'):'';SC.set(k,r)}
  return r;
}
const COLS=[
  {k:'cmp',t:'',w:1},
  {k:'code',t:'学会',get:s=>s.code+' '+s.club},
  {k:'sid',t:'学号',get:s=>s.sid},
  {k:'name',t:'姓名',get:s=>s.cn||s.en},
  {k:'cls',t:'班级',get:s=>s.cls},
  {k:'nyears',t:'年数',num:1,get:s=>new Set(s.years).size},
  {k:'roleLatest',t:'职务（最新一年）',get:(s,st)=>st.roleLatest||''},
  {k:'roles',t:'职务数',num:1},
  {k:'mid',t:'中层管理',num:1},
  {k:'comm',t:'筹委',num:1},
  {k:'comp',t:'比赛',num:1,get:(s,st)=>st.extComp+st.intComp},
  {k:'awards',t:'获奖 ★',num:1},
  {k:'act',t:'活动',num:1,get:(s,st)=>st.extAct+st.intAct},
  {k:'team',t:'团内工作',num:1},
  {k:'svc',t:'服务项',num:1,get:(s,st)=>st.extSvc+st.intSvc},
  {k:'hours',t:'服务时数',num:1},
  {k:'unsure',t:'待确认',num:1},
];
const val=(c,s,st)=>c.get?c.get(s,st):st[c.k];

function hay(s){ if(!s._hay) s._hay=[s.cn,s.en,s.sid,s.cls,s.code,s.club,...s.blocks.flatMap(b=>Object.values(b.cats).flat())].join('\n').toLowerCase(); return s._hay; }
function filtered(){
  const q=state.q.trim().toLowerCase();
  return ALL.filter(s=>(!state.club||s.code===state.club)&&(!state.cls||s.cls===state.cls)&&(!state.issue||s.issues.length)&&(!state.uns||statsFor(s,'').unsure)&&(!state.sp||(s.special||[]).length)&&(!state.year||s.years.includes(+state.year))&&(!q||q.split(/\s+/).every(t=>hay(s).includes(t))));
}

function renderKPIs(list){
  const hours=list.map(s=>statsFor(s,state.year).hours).sort((a,b)=>a-b);
  const med=hours.length?hours[Math.floor(hours.length/2)]:0;
  const aw=list.reduce((n,s)=>n+statsFor(s,state.year).awards,0);
  const clubs=new Set(list.map(s=>s.code)).size;
  const tot=hours.reduce((a,b)=>a+b,0);
  $('#kpis').innerHTML=[
    ['学生人数',list.length,`来自 ${clubs} 个学会/团体`],
    ['服务时数中位数',fmt(med)+' h',`合计 ${fmt(tot)} 小时`],
    ['最高服务时数',fmt(hours[hours.length-1]||0)+' h',(()=>{const s=list.find(s=>statsFor(s,state.year).hours===hours[hours.length-1]);return s?esc(s.cn+' · '+s.code):''})()],
    ['获奖条目',aw,'自动识别名次/奖项'],
  ].map(([k,v,n])=>`<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div><div class="n">${n}</div></div>`).join('');
}

function renderTable(){
  const list=filtered();
  renderKPIs(list);
  const rows=list.map(s=>{const st=statsFor(s,state.year);return {s,st}});
  const col=COLS.find(c=>c.k===state.sort);
  rows.sort((a,b)=>{let x=val(col,a.s,a.st),y=val(col,b.s,b.st);if(typeof x==='string'||typeof y==='string')return state.dir*String(x).localeCompare(String(y),'zh');return state.dir*((x||0)-(y||0))||a.s.sid.localeCompare(b.s.sid)});
  const maxH=Math.max(1,...rows.map(r=>r.st.hours||0));
  $('#tbl thead').innerHTML='<tr>'+COLS.map(c=>c.k==='cmp'?'<th title="勾选以对比">⇆</th>':`<th data-k="${c.k}" class="${c.num?'num':''} ${state.sort===c.k?'sorted':''}">${c.t}<span class="arr">${state.sort===c.k?(state.dir<0?'▼':'▲'):'↕'}</span></th>`).join('')+'</tr>';
  $('#tbl tbody').innerHTML=rows.map(({s,st})=>'<tr data-id="'+esc(s.sid||s.file)+'">'+COLS.map(c=>{
    if(c.k==='cmp') return `<td class="cmp"><input type="checkbox" class="cb" ${state.cmp.has(s.sid||s.file)?'checked':''}></td>`;
    if(c.k==='name') return `<td class="name"><b>${esc(s.cn)}</b><span>${esc(s.en)}</span>${spBadge(s)}${s.issues.length?' <span class="flag" title="'+esc(s.issues.join('；'))+'">⚠</span>':''}</td>`;
    if(c.k==='roleLatest'){const r=st.roleLatest;return `<td class="role" title="${esc(r)}">${esc(r)||'<span class="zero">—</span>'}</td>`}
    if(c.k==='code') return `<td><span class="pill">${esc(s.code)}</span> ${esc(s.club)}</td>`;
    if(c.k==='hours'){const h=st.hours||0;return `<td class="num"><div class="hbar"><span>${fmt(h)}</span><span class="track"><i style="width:${(h/maxH*100).toFixed(1)}%"></i></span></div></td>`}
    if(c.k==='unsure'){return `<td class="num">${st.unsure?`<span class="flag">${st.unsure}</span>`:'<span class="zero">0</span>'}</td>`}
    const v=val(c,s,st); return `<td class="${c.num?'num':''} ${c.num&&!v?'zero':''}">${esc(v)}</td>`;
  }).join('')+'</tr>').join('')||`<tr><td colspan="${COLS.length}" class="muted" style="padding:30px;text-align:center">没有符合条件的学生</td></tr>`;
  $('#count').textContent=`显示 ${list.length} / ${ALL.length} 人`;
}

$('#tbl thead').addEventListener('click',e=>{const th=e.target.closest('th[data-k]');if(!th)return;const k=th.dataset.k;if(state.sort===k)state.dir*=-1;else{state.sort=k;state.dir=COLS.find(c=>c.k===k).num?-1:1}renderTable()});
$('#tbl tbody').addEventListener('click',e=>{
  const tr=e.target.closest('tr[data-id]');if(!tr)return;const id=tr.dataset.id;
  if(e.target.classList.contains('cb')){e.target.checked?(state.cmp.size<4?state.cmp.add(id):(e.target.checked=false,alertCmp())):state.cmp.delete(id);renderCmpBar();return}
  if(e.target.closest('td.cmp'))return;
  openDrawer(ALL.find(s=>(s.sid||s.file)===id));
});
function alertCmp(){$('#cmptxt').textContent='最多对比 4 人';}
function renderCmpBar(){const n=state.cmp.size;$('#cmpbar').classList.toggle('on',n>0);$('#cmptxt').textContent=`已选 ${n} 人`;$('#cmpgo').disabled=n<2;}
$('#cmpclr').onclick=()=>{state.cmp.clear();renderCmpBar();renderTable()};
$('#cmpgo').onclick=()=>openCompare();

// ----- drawer
function hi(t){const q=state.q.trim();let h=esc(t);if(!q)return h;for(const w of q.split(/\s+/)){if(!w)continue;h=h.replace(new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'),m=>`<mark class="hl">${m}</mark>`)}return h}
let CUR=null,CUR_ID=null;
let DMODE='simple';try{DMODE=localStorage.getItem('drawerMode')||'simple'}catch(e){}
function yearGroups(s){const g=[];for(const b of s.blocks){let x=g.find(y=>y.year===b.year);if(!x){x={year:b.year,blocks:[]};g.push(x)}x.blocks.push(b)}return g}
const spBadge=s=>(s.special||[]).map(x=>`<span class="sp" title="特别标记">★ ${esc(x)}</span>`).join('');
function simpleView(s){
  const groups=yearGroups(s);const tot=statsFor(s,'');
  let h=`<div class="simple-wrap"><table class="simple"><thead><tr><th>年份</th><th>班级</th><th>学会</th><th>执委</th><th>中层管理</th><th class="num">筹委<br><span>数量</span></th><th class="num">服务<br><span>小时</span></th><th class="num">活动<br><span>数量</span></th><th class="num">工作<br><span>数量</span></th><th class="num">比赛<br><span>数量（获奖）</span></th></tr></thead><tbody>`;
  for(const g of groups){
    const st=C.computeStats(Object.assign({},s,{blocks:g.blocks}),OV,null);
    const multi=g.blocks.length>1;
    const roles=g.blocks.map(b=>{const l=st.roleByBlock.get(b)||[];const sp=[...new Set(Object.values(b.sp||{}).flat().filter(Boolean))].map(x=>`<span class="sp">★ ${esc(x)}</span>`).join('');if(b.exBlock||(!l.length&&!sp))return '';return (multi?`<span class="muted">${esc(b.clubName)}：</span>`:'')+l.map(esc).join('、')+sp}).filter(Boolean).join('<br>')||'<span class="zero">—</span>';
    const mids=g.blocks.map(b=>{const l=st.midByBlock.get(b)||[];if(b.exBlock||!l.length)return '';return (multi?`<span class="muted">${esc(b.clubName)}：</span>`:'')+l.map(esc).join('、')}).filter(Boolean).join('<br>')||'<span class="zero">—</span>';
    const clubs=g.blocks.map(b=>`${esc((b.clubCode?b.clubCode+' ':'')+b.clubName)}${b.exBlock?' <span class="tag ex">B类不计</span>':''}`).join('<br>');
    const cls=[...new Set(g.blocks.map(b=>b.cls).filter(Boolean))].join(' / ');
    const n=v=>v?v:'<span class="zero">0</span>';
    const comp=st.extComp+st.intComp;
    h+=`<tr data-year="${g.year??''}" title="点击查看这一年的详细内容"><td class="y">${g.year||'年份不明'}</td><td>${esc(cls)}</td><td>${clubs}</td><td class="roles">${roles}</td><td class="roles">${mids}</td><td class="num">${n(st.comm)}</td><td class="num">${st.hours?fmt(st.hours):'<span class="zero">0</span>'}</td><td class="num">${n(st.extAct+st.intAct)}</td><td class="num">${n(st.team)}</td><td class="num">${comp?comp+(st.awards?` <span class="aw">（${st.awards}★）</span>`:''):'<span class="zero">0</span>'}</td></tr>`;
  }
  const tc=tot.extComp+tot.intComp;
  h+=`</tbody><tfoot><tr><td>合计</td><td></td><td></td><td>职务 ${tot.roles} 个<span class="muted">（不含会员）</span></td><td>中层管理 ${tot.mid} 个</td><td class="num">${tot.comm}</td><td class="num">${fmt(tot.hours)}</td><td class="num">${tot.extAct+tot.intAct}</td><td class="num">${tot.team}</td><td class="num">${tc}${tot.awards?` <span class="aw">（${tot.awards}★）</span>`:''}</td></tr></tfoot></table></div>`;
  h+=`<p class="muted" style="font-size:12px;margin-top:8px">只计入符合规则的条目（不计入的在「详细」里以灰色划线显示）。活动＝校内外活动，工作＝团内工作/表演，比赛＝校内外比赛。点任一年可跳到「详细」。</p>`;
  return h;
}
function openDrawer(s,jumpYear){
  if(!s)return;
  CUR=s;const st=statsFor(s,'');
  $('#dname').innerHTML=`${esc(s.cn)} <span class="muted" style="font-size:14px;font-weight:400">${esc(s.en)}</span>`;
  $('#dmeta').innerHTML=`学号 ${esc(s.sid||'—')} · ${esc(s.cls)} · <span class="pill">${esc(s.code)}</span> ${esc(s.club)}${s.clubs.length>1?' · 曾参与：'+s.clubs.map(esc).join('、'):''}${spBadge(s)}`;
  $('#dmini').innerHTML=[['服务时数',fmt(st.hours)],['职务数',st.roles],['中层管理',st.mid],['筹委',st.comm],['比赛',st.extComp+st.intComp],['获奖 ★',st.awards],['活动',st.extAct+st.intAct],['团内工作',st.team],['服务项',st.extSvc+st.intSvc]].map(([k,v])=>`<div><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
  let h=`<div class="seg" role="tablist"><button data-m="simple" class="${DMODE==='simple'?'on':''}">简单</button><button data-m="detail" class="${DMODE==='detail'?'on':''}">详细</button></div>`;
  if(DMODE==='simple'){
    h+=simpleView(s);
    if(s.issues.length) h+=`<div class="notice">⚠ ${s.issues.map(esc).join('<br>⚠ ')}</div>`;
  } else {
  h+=`<div class="legend muted">灰色划线＝不计入（右边注明原因）；<span class="tag uns">待确认</span>＝自动判断不了是否代表本学会，暂时计入。每条右边的按钮可手动改为「计入 / 不计」。</div>`;
  if(s.issues.length) h+=`<div class="notice">⚠ ${s.issues.map(esc).join('<br>⚠ ')}</div>`;
  for(const b of s.blocks){
    const bs=C.computeStats(Object.assign({},s,{blocks:[b]}),OV,null).hours;
    const hrs=b.exBlock?'<span class="muted">B类不计</span>':b.declaredTotal!=null?`服务 <b>${fmt(bs)}</b> h（按自填总数${Math.abs(bs-b.declaredTotal)>0.01?`，已扣除不计入项目`:''}）${b.itemizedHours!=null&&Math.abs(b.itemizedHours-b.declaredTotal)>1?` · <span class="muted">逐项相加 ${fmt(b.itemizedHours)} h</span>`:''}`:(b.itemizedHours!=null?`服务 <b>${fmt(bs)}</b> h（没填总数，逐项相加）`:'<span class="muted">未填服务时数</span>');
    h+=`<div class="year" data-year="${b.year??''}"><div class="yh"><span class="y">${b.year||'年份不明'}</span><span class="c">${esc(b.cls||'')}</span><span class="pill">${esc((b.clubCode?b.clubCode+' ':'')+b.clubName)}</span>${b.exBlock?`<span class="tag ex">${esc(b.exBlock)}</span>`:''}<span class="h">${hrs}</span></div><div class="yb ${b.exBlock?'blockex':''}">`;
    const cats=CATLIST.filter(c=>b.cats[c.key]);
    if(!cats.length) h+='<div class="muted" style="padding:8px 0">（该年没有填写事项）</div>';
    for(const c of cats){
      const isComp=c.key==='extComp'||c.key==='intComp';
      const lis=b.cats[c.key].map((it,i)=>{const x=C.itemState(s,b,c.key,i,OV);
        const spl=b.sp&&b.sp[c.key]&&b.sp[c.key][i];
        const tags=(spl?`<span class="tag sp" title="特别标记">★ ${esc(spl)}</span>`:'')+(x.inc?'':`<span class="tag ex">${esc(x.reason||'不计')}</span>`)+(x.unsure?'<span class="tag uns">待确认</span>':'')+(x.manual?'<span class="tag man">已手动调整</span>':'')+((c.key==='extSvc'||c.key==='intSvc')&&x.inc&&b.declaredTotal==null&&!(b.hr[c.key]&&b.hr[c.key][i])?'<span class="tag uns" title="这一项没有写小时数，服务时数按 0 计">未写时数</span>':'')+(b.mv&&b.mv[c.key]&&b.mv[c.key][i]?(c.key==='comm'?'<span class="tag mv" title="为活动而组成的筹委职位（含「监督/督导XX主席」），按规则从执委栏移到筹委">原写在执委栏</span>':'<span class="tag mv" title="监督/督导/顾问/教练/领队类（「监督XX主席」除外）算中层管理">原写在筹委栏</span>'):'');
        const btn=b.exBlock?'':`<button class="tg" data-b="${s.blocks.indexOf(b)}" data-k="${c.key}" data-i="${i}">${x.inc?'不计':'计入'}</button>`;
        return `<li class="${x.inc?'':'ex'} ${spl?'spi':''} ${x.inc&&isComp&&C.isAward(it)?'aw':''}"><span class="it">${hi(it)}</span>${tags}${btn}</li>`}).join('');
      const nInc=b.cats[c.key].filter((it,i)=>C.itemState(s,b,c.key,i,OV).inc).length;
      if(c.key==='role'){const std=st.roleByBlock.get(b)||[],mid=st.midByBlock.get(b)||[];h+=`<div class="cat"><div class="cl">执委/职务 · ${nInc}</div><div><div class="stdrole">${std.map(x=>`<span class="pill">${esc(x)}</span>`).join('')||(mid.length?'':'<span class="muted">—</span>')}${mid.map(x=>`<span class="pill mid" title="中层管理（助理/授课人/队长/监督/督导/顾问类），另计「中层管理」">中层管理·${esc(x)}</span>`).join('')}</div><div class="orig">原文：<ol>${lis}</ol></div></div></div>`;continue}
      h+=`<div class="cat"><div class="cl">${c.label} · ${nInc}${nInc!==b.cats[c.key].length?`<span class="muted">/${b.cats[c.key].length}</span>`:''}</div><ol>${lis}</ol></div>`;
    }
    h+='</div></div>';
  }
  }
  h+=`<p class="muted" style="margin-top:18px;font-size:12px">来源文件：${esc(s.file)}${(s.otherFiles||[]).length?'<br>其他版本（未采用）：'+s.otherFiles.map(esc).join('<br>'):''}</p>`;
  const keep=$('#drawer').classList.contains('on')&&CUR_ID===(s.sid||s.file)?$('#dbody').scrollTop:0;CUR_ID=s.sid||s.file;
  $('#dbody').innerHTML=h;$('#dbody').scrollTop=keep;
  if(jumpYear!=null){const el=$(`#dbody .year[data-year="${jumpYear}"]`);if(el){const sg=$('#dbody .seg');$('#dbody').scrollTop=el.getBoundingClientRect().top-$('#dbody').getBoundingClientRect().top+$('#dbody').scrollTop-(sg?sg.offsetHeight+16:8)}}
  $('#dbody').onclick=e=>{
    const sg=e.target.closest('.seg button');if(sg){DMODE=sg.dataset.m;try{localStorage.setItem('drawerMode',DMODE)}catch(_){ }CUR_ID=null;openDrawer(s);return}
    const yr=e.target.closest('table.simple tbody tr');if(yr){DMODE='detail';try{localStorage.setItem('drawerMode',DMODE)}catch(_){ }CUR_ID=null;openDrawer(s,yr.dataset.year);return}
    const bt=e.target.closest('.tg');if(!bt)return;const b=s.blocks[+bt.dataset.b],k=bt.dataset.k,i=+bt.dataset.i;const key=C.itemKey(s,b,k,b.cats[k][i],i);const x=C.itemState(s,b,k,i,OV);
    const want=x.inc?'out':'in';const autoInc=!x.auto; if((want==='in')===autoInc) delete OV[key]; else OV[key]=want; saveOV();openDrawer(s);renderInfo();renderTable();};
  $('#drawer').classList.add('on');$('#scrim').classList.add('on');$('#drawer').setAttribute('aria-hidden','false');
}
function closeDrawer(){$('#drawer').classList.remove('on');$('#scrim').classList.remove('on');$('#drawer').setAttribute('aria-hidden','true')}
$('#dclose').onclick=closeDrawer;$('#scrim').onclick=closeDrawer;
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer();if(e.key==='/'&&document.activeElement!==$('#q')){e.preventDefault();$('#q').focus()}});

function openCompare(){
  const ss=[...state.cmp].map(id=>ALL.find(s=>(s.sid||s.file)===id)).filter(Boolean);
  const rows=[['服务时数','hours'],['职务数（不含会员）','roles'],['中层管理','mid'],['筹委','comm'],['校外比赛','extComp'],['校内比赛','intComp'],['获奖 ★','awards'],['校外活动','extAct'],['校内活动','intAct'],['校外服务项','extSvc'],['校内服务项','intSvc'],['团内工作/表演','team'],['考章','badge'],['团内荣誉','honor']];
  $('#dname').textContent=`对比 ${ss.length} 位学生`;$('#dmeta').textContent='绿色为该项最高；点姓名查看完整履历';$('#dmini').innerHTML='';
  let h=`<div class="card" style="overflow:auto"><table class="cmptable"><thead><tr><th></th>${ss.map(s=>`<th><a href="#" data-open="${esc(s.sid||s.file)}">${esc(s.cn)}</a><div class="muted" style="font-weight:400">${esc(s.code)} ${esc(s.club)} · ${esc(s.cls)}</div></th>`).join('')}</tr></thead><tbody>`;
  for(const [t,k] of rows){const vs=ss.map(s=>statsFor(s,'')[k]||0);const mx=Math.max(...vs);h+=`<tr><th style="background:none">${t}</th>${vs.map(v=>`<td class="num ${v===mx&&mx>0?'best':''}">${fmt(v)}</td>`).join('')}</tr>`}
  h+=`<tr><th style="background:none">职务（历年）</th>${ss.map(s=>`<td style="font-size:12px">${[...statsFor(s,'').roleByBlock.entries()].filter(([b,l])=>l.length).map(([b,l])=>`<div>${b.year}：${esc(l.join('、'))}</div>`).join('')||'—'}</td>`).join('')}</tr>`;
  h+=`<tr><th style="background:none">中层管理（历年）</th>${ss.map(s=>`<td style="font-size:12px">${[...statsFor(s,'').midByBlock.entries()].filter(([b,l])=>l.length).map(([b,l])=>`<div>${b.year}：${esc(l.join('、'))}</div>`).join('')||'—'}</td>`).join('')}</tr>`;
  h+=`<tr><th style="background:none">获奖</th>${ss.map(s=>`<td style="font-size:12px">${s.blocks.flatMap(b=>['extComp','intComp'].flatMap(k=>(b.cats[k]||[]).filter((r,i)=>C.itemState(s,b,k,i,OV).inc&&C.isAward(r))).map(r=>`<div>${b.year}：${esc(r)}</div>`)).join('')||'—'}</td>`).join('')}</tr>`;
  h+='</tbody></table></div>';
  $('#dbody').innerHTML=h;
  $('#dbody').onclick=e=>{const a=e.target.closest('[data-open]');if(a){e.preventDefault();openDrawer(ALL.find(s=>(s.sid||s.file)===a.dataset.open))}};
  $('#drawer').classList.add('on');$('#scrim').classList.add('on');
}

// ----- filters
function fillFilters(){
  const clubs=[...new Map(ALL.map(s=>[s.code,s.club])).entries()].sort((a,b)=>a[0].localeCompare(b[0]));
  $('#fclub').innerHTML='<option value="">全部学会</option>'+clubs.map(([c,n])=>`<option value="${esc(c)}">${esc(c)} ${esc(n)}（${ALL.filter(s=>s.code===c).length}）</option>`).join('');
  const cls=[...new Set(ALL.map(s=>s.cls).filter(Boolean))].sort();
  $('#fcls').innerHTML='<option value="">全部班级</option>'+cls.map(c=>`<option>${esc(c)}</option>`).join('');
  const yrs=[...new Set(ALL.flatMap(s=>s.years))].sort((a,b)=>b-a);
  $('#fyear').innerHTML='<option value="">全部年份（六年合计）</option>'+yrs.map(y=>`<option value="${y}">只看 ${y} 年</option>`).join('');
}
$('#q').oninput=e=>{state.q=e.target.value;renderTable()};
$('#fclub').onchange=e=>{state.club=e.target.value;renderTable()};
$('#fcls').onchange=e=>{state.cls=e.target.value;renderTable()};
$('#fyear').onchange=e=>{state.year=e.target.value;renderTable()};
$('#fissue').onchange=e=>{state.issue=e.target.checked;renderTable()};
$('#funs').onchange=e=>{state.uns=e.target.checked;renderTable()};
$('#fsp').onchange=e=>{state.sp=e.target.checked;renderTable()};

// ----- tabs
$$('.tab').forEach(t=>t.onclick=()=>{$$('.tab').forEach(x=>x.classList.toggle('on',x===t));['list','stats','issues','help'].forEach(n=>$('#tab-'+n).classList.toggle('hidden',n!==t.dataset.tab));if(t.dataset.tab==='stats')renderStats();});

// ----- charts (single-series horizontal bars, hover tooltip)
const tip=$('#tip');
function bars(el,data,unit){
  const mx=Math.max(1,...data.map(d=>d.v));
  el.innerHTML=data.map((d,i)=>`<div class="brow" data-i="${i}"><div class="lbl" title="${esc(d.l)}">${esc(d.l)}</div><div class="bt"><i style="width:${(d.v/mx*100).toFixed(1)}%"></i></div><div class="val">${fmt(d.v)}${unit||''}</div></div>`).join('');
  el.onmousemove=e=>{const r=e.target.closest('.brow');if(!r){tip.style.display='none';return}const d=data[r.dataset.i];tip.innerHTML=d.tip||`<b>${esc(d.l)}</b><br>${fmt(d.v)}${unit||''}`;tip.style.display='block';tip.style.left=Math.min(e.clientX+14,innerWidth-290)+'px';tip.style.top=(e.clientY+14)+'px'};
  el.onmouseleave=()=>tip.style.display='none';
}
function renderStats(){
  const list=filtered();
  const by={};for(const s of list){(by[s.code]=by[s.code]||{c:s.code,n:s.club,ss:[]}).ss.push(s)}
  const g=Object.values(by);
  bars($('#ch-club'),g.map(x=>{const hs=x.ss.map(s=>statsFor(s,state.year).hours);const avg=hs.reduce((a,b)=>a+b,0)/hs.length;return{l:`${x.c} ${x.n}（${x.ss.length}）`,v:avg,tip:`<b>${esc(x.c+' '+x.n)}</b><br>平均 ${fmt(avg)} h · ${x.ss.length} 人<br>最高 ${fmt(Math.max(...hs))} h · 最低 ${fmt(Math.min(...hs))} h`}}).sort((a,b)=>b.v-a.v),' h');
  bars($('#ch-award'),g.map(x=>{const a=x.ss.map(s=>statsFor(s,state.year).awards);const avg=a.reduce((p,q)=>p+q,0)/a.length;return{l:`${x.c} ${x.n}（${x.ss.length}）`,v:avg,tip:`<b>${esc(x.c+' '+x.n)}</b><br>平均每人 ${fmt(avg)} 项 · 共 ${a.reduce((p,q)=>p+q,0)} 项`}}).sort((a,b)=>b.v-a.v));
  const edges=[0,50,100,200,300,500,800,1200,Infinity];
  const dist=edges.slice(0,-1).map((lo,i)=>{const hiE=edges[i+1];const n=list.filter(s=>{const h=statsFor(s,state.year).hours;return h>=lo&&h<hiE}).length;return{l:hiE===Infinity?`${lo} h 以上`:`${lo}–${hiE} h`,v:n,tip:`<b>${lo}${hiE===Infinity?'+':'–'+hiE} 小时</b><br>${n} 人`}});
  bars($('#ch-dist'),dist,' 人');
  const catTot=CATLIST.map(c=>({l:c.label,v:list.reduce((n,s)=>n+s.blocks.filter(b=>!state.year||b.year==state.year).reduce((m,b)=>m+(b.cats[c.key]||[]).length,0),0)})).filter(d=>d.v).sort((a,b)=>b.v-a.v);
  bars($('#ch-cat'),catTot,' 条');
}

// ----- issues
function renderIssues(){
  const li=ALL.filter(s=>s.issues.length);
  $('#issuecount').textContent=li.length;
  const fl=(INFO.fail||[]).map(([f,e])=>`<tr><td></td><td></td><td class="flag">读取失败</td><td style="white-space:normal">${esc(e)}</td><td class="muted" style="white-space:normal;font-size:12px">${esc(f)}</td></tr>`).join('');
  $('#issuecount').textContent=li.length+(INFO.fail||[]).length;
  $('#itbl tbody').innerHTML=fl+li.map(s=>`<tr data-id="${esc(s.sid||s.file)}"><td><span class="pill">${esc(s.code)}</span></td><td>${esc(s.sid)}</td><td>${esc(s.cn)}</td><td style="white-space:normal">${s.issues.map(esc).join('<br>')}</td><td class="muted" style="white-space:normal;font-size:12px">${esc(s.file)}</td></tr>`).join('');
}
$('#itbl tbody').addEventListener('click',e=>{const tr=e.target.closest('tr[data-id]');if(tr)openDrawer(ALL.find(s=>(s.sid||s.file)===tr.dataset.id))});

$('#ovexp').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(OV,null,1)],{type:'application/json'}));a.download='成就奖_手动调整.json';a.click()};
$('#ovimp').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const o=JSON.parse(await f.text());Object.assign(OV,o);saveOV();renderInfo();renderTable();alert('已导入 '+Object.keys(o).length+' 项调整')}catch(err){alert('文件格式不对')}e.target.value=''};
// ----- CSV
$('#csv').onclick=()=>{
  const list=filtered();
  const head=['学会代号','学会','学号','姓名','英文名','班级','年数','职务（规范写法，历年）','职务数','中层管理（历年）','中层管理数','筹委','校外比赛','校内比赛','获奖','校外活动','校内活动','团内工作','校外服务项','校内服务项','服务时数','待确认条目','特别标记','问题','文件'];
  const lines=[head].concat(list.map(s=>{const st=statsFor(s,state.year);return[s.code,s.club,s.sid,s.cn,s.en,s.cls,new Set(s.years).size,[...st.roleByBlock.entries()].filter(([b,l])=>l.length).map(([b,l])=>b.year+'：'+l.join('、')).join('；'),st.roles,[...st.midByBlock.entries()].filter(([b,l])=>l.length).map(([b,l])=>b.year+'：'+l.join('、')).join('；'),st.mid,st.comm,st.extComp,st.intComp,st.awards,st.extAct,st.intAct,st.team,st.extSvc,st.intSvc,st.hours,st.unsure,(s.special||[]).join('、'),s.issues.join('；'),s.file]}));
  const csv='﻿'+lines.map(r=>r.map(v=>'"'+String(v??'').replace(/"/g,'""')+'"').join(',')).join('\r\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='成就奖统计'+(state.year?'_'+state.year:'')+'.csv';a.click();
};

function renderInfo(){
  const base=`${ALL.length} 位学生 · 读取 ${INFO.files} 个文件 · ${window.LIVE?'载入于':'生成于'} ${INFO.when}${INFO.fail&&INFO.fail.length?' · '+INFO.fail.length+' 个文件读取失败（见资料问题）':''}${Object.keys(OV).length?' · 手动调整 '+Object.keys(OV).length+' 项':''}`;
  $('#srcinfo').innerHTML=window.LIVE?`<span class="dot ${LIVE_OK?'':'off'}"></span>${LIVE_OK?'自动载入中':'工具已关闭，资料不再自动更新'} · ${esc(base)}`:esc(base+'　（按 / 快速搜索）');
}
function init(){C.index(ALL);ALL.forEach(s=>delete s._hay);SC.clear();fillFilters();renderInfo();renderIssues();renderTable();if(!$('#tab-stats').classList.contains('hidden'))renderStats()}
let LIVE_OK=true,VER=INFO.version||null,tt=null;
function toast(msg,err){const el=$('#toast');el.textContent=msg;el.classList.toggle('err',!!err);el.classList.add('on');clearTimeout(tt);tt=setTimeout(()=>el.classList.remove('on'),2500)}
async function poll(){
  try{
    const v=(await (await fetch('api/version',{cache:'no-store'})).json()).version;
    if(!LIVE_OK){LIVE_OK=true;renderInfo()}
    if(v&&v!==VER){
      const d=await (await fetch('api/data',{cache:'no-store'})).json();
      const open=$('#drawer').classList.contains('on')&&CUR_ID;
      ALL=d.students;INFO=d.info;VER=d.version;OV=Object.assign({},d.overrides||{});
      init();toast(`已自动载入最新资料：${INFO.files} 个文件 · ${ALL.length} 位学生`);
      if(open){const s=ALL.find(x=>(x.sid||x.file)===open);if(s)openDrawer(s)}
    }
  }catch(e){if(LIVE_OK){LIVE_OK=false;renderInfo()}}
}
async function boot(){
  if(window.LIVE){
    document.body.classList.add('live');
    $('#srcinfo').textContent='正在读取 Result 文件夹…';
    try{
      const d=await (await fetch('api/data',{cache:'no-store'})).json();
      if(d.error)throw new Error(d.error);
      ALL=d.students;INFO=d.info;VER=d.version;OV=Object.assign({},d.overrides||{});
    }catch(e){$('#srcinfo').textContent='读取失败：'+e.message;return}
    setInterval(poll,3000);
  }
  init();
}
boot();
})();
