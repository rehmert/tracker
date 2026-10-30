(() => {
  'use strict';
  // Context-sensitive, accessible breadcrumbs. Only user-visible text is used.
  const breadcrumbs = document.getElementById('ux-breadcrumbs');
  if (breadcrumbs && !breadcrumbs.hidden) {
    const current = breadcrumbs.lastElementChild;
    if (current && current.tagName === 'SPAN') {
      const title = document.querySelector('main h1');
      const label = title?.textContent?.trim();
      if (label && label.length < 110 && !/^details$/i.test(label)) {
        current.textContent = ' / ' + label;
        current.setAttribute('aria-current', 'page');
      }
    }
  }
  // Tables opt in explicitly. Never reorder interactive bulk-selection tables.
  document.querySelectorAll('[data-enhanced-table]').forEach(container => {
    const table = container.querySelector('table');
    const body = table?.tBodies?.[0];
    const head = table?.tHead?.rows?.[0];
    if (!body || !head) return;
    const original = Array.from(body.rows);
    if (original.length < 2 || original.some(row => row.querySelector('input[type=checkbox], form'))) return;
    const toolbar = document.createElement('div');
    toolbar.className = 'ux-table-tools';
    const label = document.createElement('label');
    label.textContent = 'Find rows';
    const search = document.createElement('input');
    search.type = 'search'; search.placeholder = 'Filter this table…';
    search.setAttribute('aria-label','Filter table rows');
    label.append(search);
    const count = document.createElement('span'); count.className='ux-table-count';count.setAttribute('role','status');
    const reset = document.createElement('button');reset.type='button';reset.textContent='Clear';
    toolbar.append(label,count,reset);container.before(toolbar);
    const key = 'tracker:table:' + location.pathname + ':' + Array.from(document.querySelectorAll('[data-enhanced-table]')).indexOf(container);
    try {search.value=sessionStorage.getItem(key)||'';}catch(_){}
    let sortColumn=-1, direction=1;
    const update=()=>{
      const q=search.value.trim().toLocaleLowerCase();let visible=0;
      original.forEach(row=>{const matches=!q||row.textContent.toLocaleLowerCase().includes(q);row.classList.toggle('ux-table-hidden',!matches);if(matches)visible++;});
      count.textContent=`${visible} of ${original.length} rows`;
      try {sessionStorage.setItem(key,search.value);}catch(_){}
    };
    search.addEventListener('input',update);
    reset.addEventListener('click',()=>{search.value='';update();search.focus();});
    Array.from(head.cells).forEach((th,index)=>{
      if(th.colSpan>1 || th.querySelector('input,button,a'))return;
      const label=th.textContent.trim();if(!label)return;
      const button=document.createElement('button');button.type='button';button.className='ux-sort-button';
      button.textContent=label;button.title=`Sort by ${label}`;
      th.textContent='';th.append(button);
      button.addEventListener('click',()=>{
        direction=sortColumn===index?-direction:1;sortColumn=index;
        const number=s=>{const v=s.replace(/[$,%\s,]/g,'').trim();return v && /^-?\d+(\.\d+)?$/.test(v)?Number(v):null;};
        original.sort((a,b)=>{
          const x=a.cells[index]?.textContent?.trim()||'';const y=b.cells[index]?.textContent?.trim()||'';
          const nx=number(x),ny=number(y);
          return direction*(nx!==null&&ny!==null?nx-ny:x.localeCompare(y,undefined,{numeric:true,sensitivity:'base'}));
        });
        original.forEach(row=>body.append(row));
        Array.from(head.cells).forEach(c=>c.removeAttribute('aria-sort'));
        th.setAttribute('aria-sort',direction===1?'ascending':'descending');update();
      });
    });
    update();
  });
  // Disable repeat submits on ordinary POST forms, without interfering with HTMX.
  document.querySelectorAll('form[method="post"]:not([hx-post])').forEach(form=>{
    form.addEventListener('submit',event=>{
      if(event.defaultPrevented)return;
      if(!form.checkValidity())return;
      const submitter=event.submitter;
      if(form.dataset.uxSubmitting==='yes'){event.preventDefault();return;}
      form.dataset.uxSubmitting='yes';
      if(submitter){const status=document.createElement('span');status.className='ux-form-status';status.setAttribute('role','status');status.textContent='Saving…';submitter.after(status);}
      // Browser can restore a page from bfcache after a submission.
    });
  });
  window.addEventListener('pageshow',()=>{
    document.querySelectorAll('form[data-ux-submitting]').forEach(form=>{
      delete form.dataset.uxSubmitting;
      form.querySelectorAll('.ux-form-status').forEach(node=>node.remove());
    });
  });
  // Explicit confirmation for supply consumption; does not alter quantity or server validation.
  document.querySelectorAll('form[action*="/supplies/"][action$="/use"]').forEach(form=>{
    form.addEventListener('submit',event=>{
      if(event.defaultPrevented || !form.checkValidity())return;
      const qty=form.querySelector('[name=quantity]')?.value||'the selected quantity';
      if(!window.confirm(`Record consumption of ${qty} units? Inventory will be updated.`)){
        event.preventDefault();delete form.dataset.uxSubmitting;
        form.querySelectorAll('.ux-form-status').forEach(node=>node.remove());
      }
    });
  });
})();
