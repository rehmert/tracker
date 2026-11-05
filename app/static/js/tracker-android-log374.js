document.addEventListener('DOMContentLoaded',()=>{
 const form=document.querySelector('form[data-tracker-vitals-entry]');
 if(form){
 const group=document.createElement('div');group.className='tracker-mobile-quick-tabs';group.setAttribute('aria-label','Choose measurement');
 const buttons=[['weight','Weight'],['bp','BP'],['pulse','Pulse'],['all','All']];
 function setMode(mode){form.dataset.mobileMode=mode;buttons.forEach(([k])=>group.querySelector('[data-mode="'+k+'"]').setAttribute('aria-pressed',String(mode===k)));}
 buttons.forEach(([key,label])=>{let b=document.createElement('button');b.type='button';b.dataset.mode=key;b.textContent=label;b.setAttribute('aria-pressed','false');b.addEventListener('click',()=>{setMode(key);form.querySelector(modeFocus(key))?.focus();});group.append(b)});
 function modeFocus(m){return ({weight:'[name="weight"]',bp:'[name="systolic"]',pulse:'[name="pulse"]',all:'[name="weight"]'})[m];}
 form.before(group);setMode(window.matchMedia('(max-width:760px)').matches?'weight':'all');
 }
 const dose=document.querySelector('form[hx-post="/doses"]');
 if(dose){
 const panel=dose.querySelector('#dose-context');if(panel){let b=document.createElement('button');b.type='button';b.textContent='Show recent sites and supplies';b.addEventListener('click',()=>{panel.classList.toggle('tracker-mobile-expanded');b.textContent=panel.classList.contains('tracker-mobile-expanded')?'Hide context':'Show recent sites and supplies';});panel.before(b);}
 }
});