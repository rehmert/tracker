/* TRACKER_BULK_CONSOLIDATED — one manager for cross-view vial selection. */
(() => {
  'use strict';
  const KEY = 'tracker.bulkVials.selection.v1';
  const LIMIT = 1000;
  const form = document.getElementById('bulk-vials');
  const summary = document.getElementById('bulk7-summary');
  if (!form || !summary) return;
  const boxes = [...form.querySelectorAll('.bulk-vial-check')];
  const visible = new Map(boxes.map(b => [String(b.value), b]));
  const compoundSelect = document.getElementById('bulk7-compound');
  const statusSelect = document.getElementById('bulk7-status');
  const all = document.getElementById('bulk-all');
  let submitting = false;
  let selected = {};
  function metadata(box) {
    const cells = box.closest('tr')?.querySelectorAll('td') || [];
    return {id:String(box.value),compound:cells[1]?.textContent.trim()||'',label:cells[2]?.querySelector('a')?.textContent.trim()||'',status:cells[8]?.textContent.trim()||''};
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
    for(const id of ['bulk-count','bulk-toolbar-count']) {const el=document.getElementById(id);if(el)el.textContent=String(Object.keys(selected).length);}
    hidden();save();
  }
  function commitVisible() {
    const next={...selected};
    for (const b of boxes) {const id=String(b.value);if(b.checked)next[id]=metadata(b);else delete next[id];}
    if(Object.keys(next).length>LIMIT) {alert('Maximum selection is 1,000 vials.');sync();return;}
    selected=next;sync();
  }
  if(compoundSelect) {
    const names=[...new Set(boxes.map(b=>metadata(b).compound).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    compoundSelect.replaceChildren(new Option('All compounds',''));
    for(const name of names)compoundSelect.appendChild(new Option(name,name));
  }
  const actions={
    'bulk7-select':()=>{for(const b of boxes){const d=metadata(b);if((!compoundSelect?.value||compoundSelect.value===d.compound)&&(!statusSelect?.value||statusSelect.value===d.status.toLowerCase().replaceAll(' ','_')))b.checked=true;}commitVisible();},
    'bulk7-invert':()=>{for(const b of boxes)b.checked=!b.checked;commitVisible();},
    'bulk7-clear':()=>{for(const b of boxes)b.checked=false;commitVisible();},
    'bulk8-clear-all':()=>{selected={};sync();},
    'bulk7-export':()=>{
      const records=Object.values(selected);if(!records.length){alert('Select at least one vial.');return;}
      const csv=v=>'"'+String(v??'').replaceAll('"','""')+'"';
      const rows=[['Vial ID','Compound','Label','Status'],...records.map(r=>[r.id,r.compound,r.label,r.status])];
      const blob=new Blob(['\uFEFF'+rows.map(r=>r.map(csv).join(',')).join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'});
      const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='tracker-selected-vials.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
  };
  if(!document.getElementById('bulk8-clear-all')) {
    const target=document.querySelector('#bulk-selection-tools .inline');
    if(target){const button=document.createElement('button');button.type='button';button.id='bulk8-clear-all';button.textContent='Clear all saved selections';target.append(button);}
  }
  // Document capture runs before older element handlers, avoiding duplicate actions.
  document.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button || !Object.hasOwn(actions,button.id))return;
    event.preventDefault();event.stopImmediatePropagation();actions[button.id]();
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
      for(const id of missing)delete selected[id];sync();alert('Selection updated. Review it before submitting again.');return;
    }
    let changed=0;
    for(const current of result.current||[]){
      const id=String(current.id),old=selected[id];if(!old)continue;
      if(old.compound!==current.compound||old.label!==current.label||old.status!==current.status)changed++;
      selected[id]={id,compound:current.compound,label:current.label,status:current.status};
    }
    sync();
    if(changed){alert(`${changed} vial record(s) changed. Review the selection before submitting again.`);return;}
    // Re-dispatch so Stage 4 performs its normal server-side preview and confirmation.
    submitting=true;
    try {form.requestSubmit(event.submitter && event.submitter.form===form ? event.submitter : undefined);}
    finally {queueMicrotask(()=>{submitting=false;});}
  },true);
  sync();
})();
