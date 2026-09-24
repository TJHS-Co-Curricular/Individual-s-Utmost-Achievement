// 网页端的轻量计算：规则判断已由 Python 预先算好（b.ex / b.unsure / b.aw / b.hr / b.rc / b.nk），
// 这里只负责套用「手动调整」后即时重算数字。
(function(root){
  const CATS=[['role','执委/职务'],['comm','筹委'],['extComp','校外比赛'],['intComp','校内比赛'],['extAct','校外活动'],['intAct','校内活动'],['extSvc','校外服务'],['intSvc','校内服务'],['total','总服务时数'],['team','团内工作/表演'],['badge','考章'],['honor','团内荣誉']].map(([key,label])=>({key,label}));
  const OTHER={key:'other',label:'其他（未注明类别）'};
  const AWARD=new Set();
  function index(all){AWARD.clear();for(const s of all)for(const b of s.blocks)for(const k of ['extComp','intComp'])(b.cats[k]||[]).forEach((t,i)=>{if(b.aw&&b.aw[k]&&b.aw[k][i])AWARD.add(t)})}
  const isAward=t=>AWARD.has(t);
  const itemKey=(s,b,k,t,i)=>[s.sid||s.file,b.year||'',b.clubCode||b.clubName||'',k,(b.nk&&b.nk[k]&&i!=null)?b.nk[k][i]:String(t).replace(/[\s 　​-‏⁠-⁯﻿]+/g,'')].join('|');
  function itemState(s,b,k,i,ov){
    const auto=b.exBlock||(b.ex&&b.ex[k]&&b.ex[k][i])||null;
    const m=ov&&ov[itemKey(s,b,k,b.cats[k][i],i)];
    const inc=b.exBlock?false:m?m==='in':!auto;
    return {inc,reason:b.exBlock||(m==='out'?'手动设为不计':m==='in'?null:auto),auto,manual:b.exBlock?null:(m||null),unsure:!!(b.unsure&&b.unsure[k+'#'+i])&&!m};
  }
  function rolesFrom(cl){
    const std=[],other=[];
    for(const r of cl){if(!r)continue;if(r.other!=null){if(!other.includes(r.other))other.push(r.other)}else if(!std.includes(r.std))std.push(r.std)}
    let out=std.filter(x=>x!=='执委'||!other.length);const merged=other.length?`执委(${other.join(',')})`:null;if(merged)out.push(merged);if(out.length>1)out=out.filter(x=>x!=='会员');
    return {list:out,count:out.reduce((n,x)=>n+(x===merged?other.length:x==='会员'?0:1),0)};
  }
  function computeStats(s,ov,year){
    const bl=s.blocks.filter(b=>!year||b.year==year);
    const c={roles:0,comm:0,extComp:0,intComp:0,extAct:0,intAct:0,extSvc:0,intSvc:0,team:0,badge:0,honor:0,unsure:0,extAwards:0,intAwards:0};
    let hours=0;const roleByBlock=new Map();
    for(const b of bl){
      for(const [k,arr] of Object.entries(b.cats))arr.forEach((t,i)=>{const x=itemState(s,b,k,i,ov);if(x.unsure)c.unsure++;if(x.inc){if(k in c)c[k]++;if((k==='extComp'||k==='intComp')&&b.aw[k][i])c[k==='extComp'?'extAwards':'intAwards']++}});
      const r=rolesFrom((b.cats.role||[]).map((t,i)=>itemState(s,b,'role',i,ov).inc?b.rc[i]:null));roleByBlock.set(b,r.list);c.roles+=r.count;
      if(b.exBlock)continue;
      // 服务时数 = 该年采用的时数（自填总数优先），再扣掉不计入的服务项
      let h=b.hours||0;
      for(const k of ['extSvc','intSvc'])(b.cats[k]||[]).forEach((t,i)=>{if(!itemState(s,b,k,i,ov).inc&&b.hr[k][i])h-=b.hr[k][i]});
      hours+=Math.max(0,h);
    }
    return {...c,awards:c.extAwards+c.intAwards,hours:Math.round(hours*100)/100,roleByBlock};
  }
  root.Core={CATS,OTHER,index,isAward,itemKey,itemState,computeStats};
})(window);
