(() => {
  'use strict';
  const toggle = document.getElementById('ux-add-toggle');
  const panel = document.getElementById('ux-add-panel');
  if (toggle && panel) {
    toggle.addEventListener('click', () => { panel.hidden = !panel.hidden; toggle.setAttribute('aria-expanded', String(!panel.hidden)); });
    document.addEventListener('click', e => { if (!e.target.closest('.ux-add-menu')) { panel.hidden = true; toggle.setAttribute('aria-expanded','false'); } });
    document.addEventListener('keydown', e => { if(e.key === 'Escape') { panel.hidden = true; toggle.setAttribute('aria-expanded','false'); } });
  }
  const names = {protocols:'Protocols',vials:'Vials',purchases:'Purchases',labs:'Labs',pages:'Notes',coas:'COAs',blends:'Blends',compounds:'Compounds',supplies:'Supplies',doses:'Dose log'};
  const parts = location.pathname.split('/').filter(Boolean);
  const crumb = document.getElementById('ux-breadcrumbs');
  if(crumb && parts.length > 1 && names[parts[0]]) {
    const home = document.createElement('a'); home.href='/'; home.textContent='Dashboard'; crumb.append(home);
    const sep = document.createElement('span'); sep.textContent=' / '; crumb.append(sep);
    const parent = document.createElement('a'); parent.href='/'+parts[0]; parent.textContent=names[parts[0]]; crumb.append(parent);
    const leaf = document.createElement('span'); leaf.textContent=' / Details'; crumb.append(leaf); crumb.hidden=false;
  }
  // Remember table filter values only when an explicit data-persist-filter attribute is present.
  document.querySelectorAll('input[data-persist-filter]').forEach(input => {
    const key = 'tracker:filter:' + location.pathname + ':' + input.id;
    try { if(!input.value) input.value=localStorage.getItem(key)||''; } catch(_) {}
    input.addEventListener('input', () => { try {localStorage.setItem(key,input.value);}catch(_){} });
  });
})();
