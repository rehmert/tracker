/* TRACKER_BULK_CONSOLIDATED — one manager for cross-view vial selection. */
(() => {
  'use strict';
  const KEY = 'tracker.bulkVials.selection.v1';
  const PENDING = 'tracker.bulkVials.pendingUpdate.v1';
  const LIMIT = 1000;
  const form = document.getElementById('bulk-vials');
  const summary = document.getElementById('bulk7-summary');
  if (!form || !summary) return;
  // Vial rows live outside the form and associate through form="bulk-vials".
  const boxes = [...document.querySelectorAll('.bulk-vial-check[form="bulk-vials"]')];
  const visible = new Map(boxes.map(b => [String(b.value), b]));
  const compoundSelect = document.getElementById('bulk7-compound');
  const statusSelect = document.getElementById('bulk7-status');
  const all = document.getElementById('bulk-all');
  let submitting = false;
  let selected = {};
  let previousSelection = null;
  let lastClickIndex = null;
  let showSelected = 8;
  let selectedQuery = "";
  function metadata(box) {
    const cells = box.closest('tr')?.querySelectorAll('td') || [];
    return {id:String(box.value),compound:cells[1]?.textContent.trim()||'',label:cells[2]?.querySelector('a')?.textContent.trim()||'',status:box.closest('tr')?.dataset.attentionStatus||''};
  }
  function load() {
    try {
      const data=JSON.parse(sessionStorage.getItem(KEY)||'{}');
      if (!data || typeof data!=='object' || Array.isArray(data)) return {};
      const clean={};
      for (const [id,entry] of Object.entries(data)) {
        if (!/^[1-9]\d*$/.test(id) || !entry || typeof entry!=='object') continue;
        clean[id]={id,compound:String(entry.compound||''),label:String(entry.label||''),status:String(entry.status||'')};
        if (Object.keys(clean).length>=LIMIT) break;
      }
      return clean;
    } catch (_) {return {};}
  }
  selected=load();
  // Clear only when this tab really submitted a confirmed bulk update.
  // A crafted or stale success URL must never clear unrelated selections.
  const params = new URLSearchParams(location.search);
  const flash = params.get('msg') || '';
  const completed = flash.startsWith('Bulk update completed:');
  let pending = false;
  try {pending=sessionStorage.getItem(PENDING)==='1';} catch (_) {}
  if (completed && pending) {
    selected = {};
    try {sessionStorage.removeItem(KEY);} catch (_) {}
  }
  if (pending && (completed || params.has('err'))) {
    try {sessionStorage.removeItem(PENDING);} catch (_) {}
  }
  function remember() {
    previousSelection = {...selected};
  }
  function restore() {
    if (!previousSelection) return;
    const earlier = previousSelection;
    previousSelection = {...selected};
    selected = earlier;
    sync();
  }
  function save() {try {sessionStorage.setItem(KEY,JSON.stringify(selected));} catch(e) {console.warn('Bulk selection storage unavailable',e);}}
  function hidden() {
    form.querySelectorAll('[data-bulk-persisted="1"], [data-bulk8-hidden="1"]').forEach(e=>e.remove());
    for (const id of Object.keys(selected)) {
      if (visible.has(id)) continue;
      const input=document.createElement('input');
      input.type='hidden'; input.name='vial_ids'; input.value=id; input.dataset.bulkPersisted='1';
      form.appendChild(input);
    }
  }
  function sync() {
    for (const b of boxes) b.checked=Object.hasOwn(selected,String(b.value));
    const count=boxes.filter(b=>b.checked).length;
    summary.textContent=`${Object.keys(selected).length} selected across all views (${count} visible).`;
    if(all) {all.checked=boxes.length>0 && count===boxes.length; all.indeterminate=count>0 && count<boxes.length;}
    const selectedCount=Object.keys(selected).length;
    for(const id of ['bulk-count','bulk-toolbar-count']) {const el=document.getElementById(id);if(el)el.textContent=String(selectedCount);}
    // This manager owns selection changes in the capture phase, so the older
    // editor's checkbox listeners do not run. Keep its controls in sync here.
    for(const id of ['bulk-open-editor','bulk-apply']) {
      const control=document.getElementById(id);
      if(control)control.disabled=selectedCount===0;
    }
    const undo = document.getElementById('bulk-undo-selection');
    if (undo) undo.disabled = !previousSelection;
    const preview=document.getElementById('bulk-selected-preview');
    if(preview) {
      // Preserve the search text and row-limit when selection changes.
      preview.replaceChildren();
      if(selectedCount) {
        const heading=document.createElement('strong');
        heading.textContent='Selected vials ('+selectedCount+'):';
        preview.appendChild(heading);
        const search=document.createElement('input');
        search.type='search';
        search.id='bulk-selected-search';
        search.placeholder='Find within selected vials…';
        search.setAttribute('aria-label','Find within selected vials');
        search.value=selectedQuery;
        preview.appendChild(search);
        const entries=Object.values(selected).filter(entry=>
          [entry.compound,entry.label,entry.id,entry.status]
          .join(' ').toLocaleLowerCase().includes(selectedQuery.toLocaleLowerCase())
        );
        const status=document.createElement('p');
        status.className='bulk-selected-match-count';
        status.textContent=entries.length+' matching selected vial(s).';
        preview.appendChild(status);
        const list=document.createElement('ul');
        for(const entry of entries.slice(0,showSelected)) {
          const row=document.createElement('li');
          row.className='bulk-selected-row';
          const name=document.createElement('span');
          name.textContent=(entry.compound ? entry.compound+' — ' : '')+
            (entry.label||('Vial #'+entry.id))+' (#'+entry.id+')';
          const remove=document.createElement('button');
          remove.type='button';
          remove.dataset.bulkRemoveId=entry.id;
          remove.setAttribute('aria-label','Remove vial #'+entry.id+' from selection');
          remove.textContent='Remove';
          row.append(name,remove);
          list.appendChild(row);
        }
        preview.appendChild(list);
        if(entries.length>showSelected) {
          const more=document.createElement('button');
          more.type='button';
          more.id='bulk-selected-more';
          more.textContent='Show '+Math.min(25,entries.length-showSelected)+' more';
          preview.appendChild(more);
        }
      }
    }
    hidden();save();
    document.dispatchEvent(new Event('tracker:bulk-selection-changed'));
  }
  function commitVisible() {
    const next={...selected};
    for (const b of boxes) {const id=String(b.value);if(b.checked)next[id]=metadata(b);else delete next[id];}
    if(Object.keys(next).length>LIMIT) {alert('Maximum selection is 1,000 vials.');sync();return;}
    if (Object.keys(next).length !== Object.keys(selected).length ||
      Object.keys(next).some(id=>!Object.hasOwn(selected,id))) remember();
    selected=next;sync();
  }
  if(compoundSelect) {
    const names=[...new Set(boxes.map(b=>metadata(b).compound).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    compoundSelect.replaceChildren(new Option('All compounds',''));
    for(const name of names)compoundSelect.appendChild(new Option(name,name));
  }
  const actions={
    // All bulk controls use this one persisted cross-view selection source.
    'bulk-select-all':()=>{for(const b of boxes)b.checked=true;commitVisible();},
    'bulk-select-none':()=>{remember();selected={};sync();},
    'bulk-undo-selection':restore,
    'bulk-open-editor':()=>{
      if(!Object.keys(selected).length)return;
      const panel=document.getElementById('bulk-editor-panel');
      if(!panel)return;
      panel.open=true;
      panel.scrollIntoView({behavior:'auto',block:'start'});
      panel.querySelector('select[name^="mode_"]')?.focus({preventScroll:true});
    },
    'bulk7-select':()=>{for(const b of boxes){const d=metadata(b);if((!compoundSelect?.value||compoundSelect.value===d.compound)&&(!statusSelect?.value||statusSelect.value===d.status.toLowerCase().replaceAll(' ','_')))b.checked=true;}commitVisible();},
    'bulk7-invert':()=>{for(const b of boxes)b.checked=!b.checked;commitVisible();},
    'bulk7-clear':()=>{for(const b of boxes)b.checked=false;commitVisible();},
    'bulk7-deselect':()=>{
      for(const b of boxes){
        const d=metadata(b);
        if((!compoundSelect?.value||compoundSelect.value===d.compound)&&
           (!statusSelect?.value||statusSelect.value===d.status.toLowerCase().replaceAll(' ','_')))b.checked=false;
      }
      commitVisible();
    },
    'bulk8-clear-all':()=>{remember();selected={};sync();},
    'bulk7-export':()=>{
      const records=Object.values(selected);if(!records.length){alert('Select at least one vial.');return;}
      const csv=v=>{
        const raw=String(v??'');
        const safe=/^\s*[=+\-@]/.test(raw)?"'"+raw:raw;
        return '"'+safe.replaceAll('"','""')+'"';
      };
      const rows=[['Vial ID','Compound','Label','Status'],...records.map(r=>[r.id,r.compound,r.label,r.status])];
      const blob=new Blob(['\uFEFF'+rows.map(r=>r.map(csv).join(',')).join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'});
      const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='tracker-selected-vials.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
  };
  const selectedPreview=document.getElementById('bulk-selected-preview');
  if(selectedPreview) {
    selectedPreview.addEventListener('input',event=>{
      if(event.target.id!=='bulk-selected-search')return;
      selectedQuery=event.target.value;
      showSelected=8;
      // Re-render without stealing focus or resetting the cursor.
      const cursor=event.target.selectionStart;
      sync();
      const field=document.getElementById('bulk-selected-search');
      field?.focus({preventScroll:true});
      if(cursor!==null)field?.setSelectionRange(cursor,cursor);
    });
    selectedPreview.addEventListener('click',event=>{
      const more=event.target.closest('#bulk-selected-more');
      if(more){showSelected+=25;sync();return;}
      const remove=event.target.closest('button[data-bulk-remove-id]');
      if(!remove) return;
      const id=remove.dataset.bulkRemoveId;
      if(!Object.hasOwn(selected,id)) return;
      remember();delete selected[id];sync();
    });
  }
  if(!document.getElementById('bulk8-clear-all') &&
     !document.getElementById('bulk-select-none')) {
    const target=document.querySelector('#bulk-selection-tools .inline');
    if(target){const button=document.createElement('button');button.type='button';button.id='bulk8-clear-all';button.textContent='Clear all saved selections';target.append(button);}
  }
  // Document capture runs before older element handlers, avoiding duplicate actions.
  document.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button || !Object.hasOwn(actions,button.id))return;
    event.preventDefault();event.stopImmediatePropagation();actions[button.id]();
  },true);
  // Shift-click selects the intervening displayed rows. A filter never
  // modifies selections on other inventory pages.
  document.addEventListener('click',event=>{
    const idx=boxes.indexOf(event.target);
    if(idx<0)return;
    if(event.shiftKey && lastClickIndex!==null) {
      const checked=event.target.checked;
      const lo=Math.min(idx,lastClickIndex), hi=Math.max(idx,lastClickIndex);
      for(let i=lo;i<=hi;i++)boxes[i].checked=checked;
    }
    lastClickIndex=idx;
  },true);
  document.addEventListener('change',event=>{
    if(boxes.includes(event.target)){event.stopImmediatePropagation();commitVisible();}
    else if(event.target===all){event.stopImmediatePropagation();for(const b of boxes)b.checked=all.checked;commitVisible();}
  },true);
  // Validate before Stage 4 form-level preview handlers receive the submit event.
  document.addEventListener('submit',async event=>{
    if(event.target!==form || submitting)return;
    event.preventDefault();event.stopImmediatePropagation();
    commitVisible();
    const ids=Object.keys(selected);
    if(!ids.length){alert('Select at least one vial.');return;}
    const data=new FormData();for(const id of ids)data.append('vial_ids',id);
    let result;
    try {
      const response=await fetch('/vials/bulk/validate-selection',{method:'POST',body:data,credentials:'same-origin'});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      result=await response.json();
    } catch(e){alert('Could not validate selected vials. No update was submitted.');return;}
    if(!result.ok){alert(result.error||'Selection validation failed.');return;}
    const missing=(result.missing||[]).map(String);
    if(missing.length){
      if(!confirm(`${missing.length} selected vial(s) no longer exist. Remove them and review again?`))return;
      remember();
    for(const id of missing)delete selected[id];sync();alert('Selection updated. Review it before submitting again.');return;
    }
    // Refresh display metadata from the server without blocking the edit.
    // Selection validity is determined by vial IDs; cosmetic metadata changes
    // must not force a second submission or prevent the review dialog.
    for(const current of result.current||[]){
      const id=String(current.id);if(!selected[id])continue;
      selected[id]={id,compound:current.compound,label:current.label,status:current.status};
    }
    sync();
    // Re-dispatch so Stage 4 performs its normal server-side preview and confirmation.
    submitting=true;
    try {form.requestSubmit(event.submitter && event.submitter.form===form ? event.submitter : undefined);}
    finally {queueMicrotask(()=>{submitting=false;});}
  },true);
  sync();
})();
