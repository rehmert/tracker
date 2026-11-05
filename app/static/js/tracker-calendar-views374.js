document.addEventListener('DOMContentLoaded',()=>{
 const grid=document.getElementById('calendar-grid');if(!grid)return;
 const days=Array.from(grid.querySelectorAll('.calendar-day[data-calendar-date]'));if(!days.length)return;
 const bar=document.createElement('div');bar.className='tracker-calendar-views';bar.setAttribute('aria-label','Calendar display range');
 const modes=[['day','Day',1],['week','Week',7],['two-weeks','2 weeks',14],['month','Month',0]];
 const today=new Date().toISOString().slice(0,10),current=days.some(x=>x.dataset.calendarDate===today)?today:(days.find(x=>!x.classList.contains('outside'))||days[0]).dataset.calendarDate;
 let anchor=current;let mode=localStorage.getItem('tracker.calendar.view')|| (matchMedia('(max-width:760px)').matches?'week':'month');
 if(!modes.some(x=>x[0]===mode))mode='month';
 const label=document.createElement('p');label.setAttribute('role','status');label.setAttribute('aria-live','polite');
 function apply(){
   const pos=days.findIndex(x=>x.dataset.calendarDate===anchor);const count=(modes.find(x=>x[0]===mode)||modes[3])[2];
   const first=count===7||count===14?Math.max(0,pos-((new Date(anchor+'T12:00:00').getDay()+7)%7)):Math.max(0,pos);
   let shown=[];
   days.forEach((d,i)=>{const visible=!count || (i>=first && i<first+count);d.dataset.viewHidden=String(!visible);if(visible)shown.push(d.dataset.calendarDate);});
   if(count)grid.dataset.compactView=mode;else delete grid.dataset.compactView;
   bar.querySelectorAll('[data-calendar-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.calendarMode===mode)));
   label.textContent=(shown[0]||'')+' — '+(shown[shown.length-1]||'');
   try{localStorage.setItem('tracker.calendar.view',mode)}catch(_){}
 }
 modes.forEach(([key,text])=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.dataset.calendarMode=key;b.addEventListener('click',()=>{mode=key;apply()});bar.append(b)});
 const prev=document.createElement('button'),next=document.createElement('button');prev.type=next.type='button';prev.textContent='←';next.textContent='→';prev.setAttribute('aria-label','Earlier dates');next.setAttribute('aria-label','Later dates');
 function move(dir){const index=days.findIndex(d=>d.dataset.calendarDate===anchor);const step=mode==='day'?1:mode==='two-weeks'?14:7;const target=days[Math.min(days.length-1,Math.max(0,index+dir*step))];if(target){anchor=target.dataset.calendarDate;apply()}}
 prev.addEventListener('click',()=>move(-1));next.addEventListener('click',()=>move(1));
 bar.prepend(prev);bar.append(next);grid.before(bar,label);apply();
});