(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  function init(){
    if(!$('pkRevisionLoad'))return;
    let preview=null;
    const status=$('pkRevisionStatus');
    const select=$('pkRevisionSelect');
    async function api(url,method='GET',body){
      const headers={};
      if(body)headers['Content-Type']='application/json';
      if(method!=='GET'){
        const token=window.trackerCsrfToken?.();
        if(token)headers['X-Tracker-CSRF']=token;
      }
      const r=await fetch(url,{method,credentials:'same-origin',cache:'no-store',headers,body:body?JSON.stringify(body):undefined});
      if(!r.ok)throw Error('HTTP '+r.status+': '+(await r.text()).slice(0,120));
      return r.json();
    }
    function invalidate(){preview=null;$('pkRevisionRestore').disabled=true;}
    $('scenario').addEventListener('change',()=>{invalidate();select.replaceChildren();});
    select.addEventListener('change',invalidate);
    $('pkRevisionLoad').onclick=async()=>{
      invalidate();select.replaceChildren();
      const sid=Number($('scenario').value);
      if(!sid)return;
      try{
        const list=await api('/pk/workspace/'+sid+'/revisions');
        if(sid!==Number($('scenario').value))return;
        select.add(new Option('Choose revision',''));
        for(const item of list){
          const option=new Option('#'+item.id+' · '+item.action+(item.restorable?'':' (not restorable)'),String(item.id));
          option.disabled=!item.restorable;select.add(option);
        }
        status.textContent=list.length+' audit entries loaded. Only complete snapshots can be restored.';
      }catch(e){status.textContent=e.message;}
    };
    $('pkRevisionPreview').onclick=async()=>{
      invalidate();
      const sid=Number($('scenario').value),aid=Number(select.value);
      if(!sid||!aid)return;
      try{
        const data=await api('/pk/workspace/'+sid+'/revisions/'+aid+'/preview');
        if(sid!==Number($('scenario').value)||aid!==Number(select.value))return;
        preview={sid,aid,data};$('pkRevisionRestore').disabled=false;
        status.textContent='Restore '+data.dose_count+' hypothetical doses from #'+aid+'? Existing dose IDs will change. Nothing saved yet.';
      }catch(e){status.textContent=e.message;}
    };
    $('pkRevisionRestore').onclick=async()=>{
      if(!preview)return;
      const {sid,aid,data}=preview;
      if(!confirm('Restore this historical hypothetical scenario? All current planned doses will be replaced.'))return;
      invalidate();
      try{
        await api('/pk/workspace/'+sid+'/revisions/'+aid+'/restore','POST',{expected_version:data.current_version});
        await window.trackerPkReloadScenario?.();
        status.textContent='Restored historical scenario; a new audit entry was created.';
      }catch(e){status.textContent=e.message;}
    };
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
