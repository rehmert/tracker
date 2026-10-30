/* Grouped sidebar: browser-local preferences, no backend or dependencies. */
(() => {
const STORE='tracker-grouped-nav-v1', OLD='tracker-nav-order-v1', OLD_MODE='tracker-nav-mode-v1';
const boot=()=>{
 const root=document.getElementById('nav-sortable'); if(!root)return;
 const sections=()=>[...root.querySelectorAll(':scope > .nav-section')];
 const all=()=>[...document.querySelectorAll('[data-nav-key]')].filter(x=>x.closest('#nav-sortable, .nav-pinned'));
 const originalSections=sections().map(x=>x.dataset.section);
 const defaults=Object.fromEntries(sections().map(x=>[x.dataset.section,[...x.querySelectorAll('[data-nav-key]')].map(y=>y.dataset.navKey)]));
 const fresh=()=>({open:{},favorites:[],hidden:[],categories:[],order:{},mode:'default'});
 let state=fresh();try{state={...state,...JSON.parse(localStorage.getItem(STORE)||'{}')}}catch{}
 const save=()=>localStorage.setItem(STORE,JSON.stringify(state));
 const mode=document.getElementById('nav-sort-mode'), edit=document.getElementById('nav-edit-toggle'), reset=document.getElementById('nav-reset');
 const filter=document.getElementById('nav-filter'), favBox=document.getElementById('nav-favorites'), favList=document.getElementById('nav-favorite-links');
 const catPrefs=document.getElementById('nav-category-preferences'), visibility=document.getElementById('nav-visibility-preferences');
 let editing=false;
 function apply(){
const alphabetical = state.mode === 'default' || state.mode === 'alpha';

  const compareNames = (a, b) =>
    a.localeCompare(b, undefined, {
      sensitivity: 'base',
      numeric: true
    });

  const categoryOrder = state.categories || [];

  sections().sort((a, b) => {
    if (alphabetical) {
      return compareNames(a.dataset.section, b.dataset.section);
    }

    const rank = key => {
      const index = categoryOrder.indexOf(key);
      return index >= 0
        ? index
        : 1000 + originalSections.indexOf(key);
    };

    return rank(a.dataset.section) - rank(b.dataset.section);
  }).forEach(section => root.appendChild(section));

  sections().forEach(sec=>{
   const key=sec.dataset.section, list=sec.querySelector('.nav-group');
   const defaultOrder=defaults[key], custom=state.order?.[key]||[];
   [...list.children].sort((a,b)=>{
    if (alphabetical) {
      return compareNames(
        a.querySelector('a').textContent.trim(),
        b.querySelector('a').textContent.trim()
      );
    }

    const rank = item => {
      const index = custom.indexOf(item.dataset.navKey);
      return index >= 0
        ? index
        : 1000 + defaultOrder.indexOf(item.dataset.navKey);
    };

    return rank(a) - rank(b);
   }).forEach(x=>list.appendChild(x));
   const active=!!sec.querySelector('[aria-current="page"]');
   const opened=state.open?.[key]??active;
   sec.classList.toggle('nav-expanded',opened);sec.querySelector('.nav-section-toggle').setAttribute('aria-expanded',String(opened));
  });
  all().forEach(li=>{const key=li.dataset.navKey,star=li.querySelector('.nav-star');if(star){const yes=state.favorites.includes(key);star.textContent=yes?'★':'☆';star.setAttribute('aria-pressed',String(yes));}li.hidden=state.hidden.includes(key)&&!li.querySelector('[aria-current="page"]');li.querySelector('.nav-move')?.toggleAttribute('hidden',!editing);});
  favList.replaceChildren();state.favorites.forEach(key=>{if(key==='/')return;const li=all().find(x=>x.dataset.navKey===key);if(!li||state.hidden.includes(key))return;const clone=document.createElement('li');const a=li.querySelector('a').cloneNode(true);clone.appendChild(a);favList.appendChild(clone);});favBox.hidden=!favList.children.length;
  if(mode)mode.value=state.mode;if(edit){edit.textContent=editing?'Done':'Reorder';edit.setAttribute('aria-pressed',String(editing));}const help=document.getElementById('nav-sort-help');if(help)help.hidden=!editing;
  drawPreferences();runFilter();
 }
 function drawPreferences(){
  if(catPrefs){catPrefs.replaceChildren();sections().forEach((sec,i)=>{const row=document.createElement('div');row.className='nav-pref-row';const name=document.createElement('span');name.textContent=sec.dataset.section;row.append(name);for(const [label,delta] of [['↑',-1],['↓',1]]){const btn=document.createElement('button');btn.type='button';btn.textContent=label;btn.disabled=i+delta<0||i+delta>=sections().length;btn.addEventListener('click',()=>{const keys=sections().map(x=>x.dataset.section);[keys[i],keys[i+delta]]=[keys[i+delta],keys[i]];state.categories=keys;state.mode='custom';save();apply();});row.append(btn);}const chk=document.createElement('input');chk.type='checkbox';chk.checked=state.open?.[sec.dataset.section]??sec.classList.contains('nav-expanded');chk.title='Start expanded';chk.addEventListener('change',()=>{state.open[sec.dataset.section]=chk.checked;save();apply();});row.append(chk);catPrefs.append(row);});}
  if(visibility){visibility.replaceChildren();all().forEach(li=>{const label=document.createElement('label');label.className='nav-pref-check';const input=document.createElement('input');input.type='checkbox';input.checked=!state.hidden.includes(li.dataset.navKey);input.addEventListener('change',()=>{state.hidden=input.checked?state.hidden.filter(x=>x!==li.dataset.navKey):[...new Set([...state.hidden,li.dataset.navKey])];save();apply();});label.append(input,document.createTextNode(' '+li.querySelector('a').textContent.trim()));visibility.append(label);});}
 }
 function runFilter(){const q=(filter?.value||'').trim().toLowerCase();sections().forEach(sec=>{let any=false;sec.querySelectorAll('[data-nav-key]').forEach(li=>{const match=li.querySelector('a').textContent.toLowerCase().includes(q)&&(!state.hidden.includes(li.dataset.navKey)||!!q);li.classList.toggle('nav-filter-hidden',!match);if(match)any=true;});sec.classList.toggle('nav-filter-hidden',!any);sec.classList.toggle('nav-search-open',!!q&&any);});document.querySelectorAll('.nav-pinned [data-nav-key],#nav-favorite-links li').forEach(li=>li.classList.toggle('nav-filter-hidden',!!q&&!li.textContent.toLowerCase().includes(q)));}
 root.addEventListener('click',e=>{const head=e.target.closest('.nav-section-toggle');if(head){const sec=head.closest('.nav-section');state.open[sec.dataset.section]=head.getAttribute('aria-expanded')!=='true';save();apply();return;}
 const btn=e.target.closest('.nav-up,.nav-down');if(!btn||!editing)return;const li=btn.closest('li'),list=li.parentElement,sibling=btn.classList.contains('nav-up')?li.previousElementSibling:li.nextElementSibling;if(!sibling)return;if(btn.classList.contains('nav-up'))list.insertBefore(li,sibling);else list.insertBefore(sibling,li);state.order[list.dataset.group]=[...list.children].map(x=>x.dataset.navKey);state.mode='custom';save();apply();});
 document.querySelector('.rail')?.addEventListener('click',e=>{const star=e.target.closest('.nav-star');if(!star)return;const key=star.dataset.favorite;state.favorites=state.favorites.includes(key)?state.favorites.filter(x=>x!==key):[...state.favorites,key];save();apply();});
 filter?.addEventListener('input',runFilter);mode?.addEventListener('change',()=>{state.mode=mode.value;save();apply();});edit?.addEventListener('click',()=>{editing=!editing;save();apply();});reset?.addEventListener('click',()=>{state.mode='default';state.order={};editing=false;save();apply();});document.getElementById('nav-reset-all')?.addEventListener('click',()=>{state=fresh();localStorage.removeItem(OLD);save();apply();});
 apply();
};if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
