(() => {
  const $ = id => document.getElementById(id);
  let scenarios = [], current = null;
  const error = e => { $('pkError').textContent = e.message || String(e); };
  const request = async (url, method='GET', body) => {
    const r = await fetch(url, {method, headers: body ? {'Content-Type':'application/json'} : {}, body: body ? JSON.stringify(body) : undefined});
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  };
  const cid = () => Number($('compound').value);
  const params = () => ({compound_id:cid(), name:$('scenarioName').value, half_life_hours:Number($('half').value), absorption_half_life_hours:Number($('abs').value)});
  function draw(data) {
    const c=$('plot'), ctx=c.getContext('2d'), w=c.width,h=c.height;
    ctx.clearRect(0,0,w,h);
    const rows=data.rows, max=Math.max(0.001,...rows.map(r=>Math.max(r.actual,r.planned)));
    const left=58,right=20,top=20,bottom=45;
    const x=i=>left+(w-left-right)*i/Math.max(1,rows.length-1), y=v=>h-bottom-(h-top-bottom)*v/max;
    ctx.strokeStyle='#888';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,top);ctx.lineTo(left,h-bottom);ctx.lineTo(w-right,h-bottom);ctx.stroke();
    ctx.fillStyle='#222';ctx.font='14px sans-serif';ctx.fillText(max.toFixed(2)+' mg-eq',5,top+8);ctx.fillText('0',35,h-bottom);
    for (const [key,color] of [['actual','#2563eb'],['planned','#e87921']]) {
      ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2.5;
      rows.forEach((r,i)=>i?ctx.lineTo(x(i),y(r[key])):ctx.moveTo(x(i),y(r[key])));ctx.stroke();
    }
    const now=new Date(data.now).getTime(), t0=new Date(rows[0].at).getTime(),t1=new Date(rows[rows.length-1].at).getTime();
    const nx=left+(w-left-right)*(now-t0)/(t1-t0);
    ctx.setLineDash([5,5]);ctx.strokeStyle='#333';ctx.beginPath();ctx.moveTo(nx,top);ctx.lineTo(nx,h-bottom);ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle='#222';ctx.fillText(rows[0].at.slice(0,10),left,h-13);ctx.fillText(rows[rows.length-1].at.slice(0,10),w-115,h-13);
    $('summary').textContent=`${data.actual_doses} historical administrations, ${data.planned_doses} planned administrations. Units: ${data.units}.`;
  }
  async function refresh() {
    if (!cid()) return;
    const q=new URLSearchParams({compound_id:cid(),half_life_hours:$('half').value,absorption_half_life_hours:$('abs').value,days_back:$('back').value,days_forward:$('forward').value});
    if(current) q.set('scenario_id',current.id);
    draw(await request('/pk/data?'+q));
  }
  function renderRows() {
    const tbody=$('plannedRows');tbody.replaceChildren();
    for(const d of (current?.doses||[])) {
      const tr=document.createElement('tr');
      for(const value of [d.planned_at.replace('T',' ').slice(0,16),String(d.amount_mg)]) {const td=document.createElement('td');td.textContent=value;tr.append(td);}
      const td=document.createElement('td');
      const edit=document.createElement('button');edit.textContent='Edit';edit.type='button';edit.onclick=async()=>{
        const when=prompt('Planned date/time (YYYY-MM-DDTHH:MM)',d.planned_at.slice(0,16));if(when===null)return;
        const amount=prompt('Dose (mg)',d.amount_mg);if(amount===null)return;
        try {await request(`/pk/scenarios/${current.id}/doses/${d.id}`,'PUT',{planned_at:when,amount_mg:Number(amount)});await load();}catch(e){error(e);}
      };
      const del=document.createElement('button');del.textContent='Remove';del.type='button';del.onclick=async()=>{try{await request(`/pk/scenarios/${current.id}/doses/${d.id}`,'DELETE');await load();}catch(e){error(e);}};
      td.append(edit,del);tr.append(td);tbody.append(tr);
    }
  }
  async function load() {
    if (!cid())return;
    const selected=current?.id;
    scenarios=await request('/pk/scenarios?compound_id='+cid());
    $('scenario').replaceChildren(new Option('Unsaved / no future doses',''));
    scenarios.forEach(s=>$('scenario').add(new Option(s.name,String(s.id))));
    current=scenarios.find(s=>s.id===selected)||null;
    $('scenario').value=current?.id||'';renderRows();await refresh();
  }
  $('compound').onchange=async()=>{const o=$('compound').selectedOptions[0];$('half').value=o.dataset.half||120;$('abs').value=o.dataset.abs||24;current=null;try{await load();}catch(e){error(e);}};
  $('scenario').onchange=async()=>{current=scenarios.find(s=>s.id===Number($('scenario').value))||null;if(current){$('scenarioName').value=current.name;$('half').value=current.half_life_hours;$('abs').value=current.absorption_half_life_hours;}renderRows();try{await refresh();}catch(e){error(e);}};
  $('refresh').onclick=()=>refresh().catch(error);
  $('save').onclick=async()=>{try{const r=await request('/pk/scenarios','POST',params());current={id:r.id};await load();}catch(e){error(e);}};
  $('update').onclick=async()=>{if(!current)return;try{await request('/pk/scenarios/'+current.id,'PUT',params());await load();}catch(e){error(e);}};
  $('remove').onclick=async()=>{if(!current||!confirm('Delete this hypothetical scenario?'))return;try{await request('/pk/scenarios/'+current.id,'DELETE');current=null;await load();}catch(e){error(e);}};
  $('add').onclick=async()=>{if(!current){error(new Error('Save or select a scenario first.'));return;}try{await request(`/pk/scenarios/${current.id}/doses`,'POST',{planned_at:$('plannedAt').value,amount_mg:Number($('amount').value)});await load();}catch(e){error(e);}};
  if($('compound').options.length>1){$('compound').selectedIndex=1;$('compound').dispatchEvent(new Event('change'));}
})();

// Create a compound for planning before any vial or dose has been logged.
document.getElementById('addPkCompound').addEventListener('click', async () => {
  const name = document.getElementById('newPkCompound').value;
  const err = document.getElementById('pkError');
  try {
    const response = await fetch('/pk/compounds', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name})
    });
    if (!response.ok) throw new Error(await response.text());
    const added = await response.json();
    window.location.reload();
  } catch (e) { err.textContent = 'Could not add compound: ' + e.message; }
});
