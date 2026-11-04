(() => {
  'use strict';
  const $=id=>document.getElementById(id);

  function init() {
    if(!$('pkTransformPreview'))return;

    let draft=null;

    async function json(url,method='GET',data) {
      const headers={
        'Content-Type':'application/json'
      };
      if(method!=='GET') {
        const csrf=window.trackerCsrfToken?.();
        if(csrf)headers['X-Tracker-CSRF']=csrf;
      }
      const r=await fetch(url,{
        method,headers,
        credentials:'same-origin',
        cache:'no-store',
        body:data?JSON.stringify(data):undefined
      });
      if(!r.ok)
        throw Error(
          'HTTP '+r.status+': '+
          (await r.text()).slice(0,150)
        );
      return r.json();
    }

    function invalidate() {
      draft=null;
      $('pkTransformApply').disabled=true;
    }

    ['pkTransformHours','pkTransformScale'].forEach(
      id=>$(id).addEventListener('input',invalidate)
    );
    $('scenario').addEventListener('change',invalidate);

    $('pkTransformPreview').onclick=async()=>{
      invalidate();
      const sid=Number($('scenario').value);
      if(!sid)return;

      try {
        const rev=await json(
          '/pk/scenarios/'+sid+'/revision'
        );
        const value={
          shift_hours:Number($('pkTransformHours').value),
          amount_multiplier:Number(
            $('pkTransformScale').value
          ),
          expected_version:rev.version
        };
        const response=await json(
          '/pk/workspace/'+sid+'/transform-preview',
          'POST',value
        );

        if(Number($('scenario').value)!==sid)
          return;

        const items=response.doses;
        draft={sid,value};
        $('pkTransformApply').disabled=!items.length;

        $('pkTransformStatus').textContent=
          items.length+' doses previewed. First: '+
          (items[0]?.planned_at||'none')+
          '. Last: '+(items.at(-1)?.planned_at||'none')+
          '. No changes saved.';
      }catch(e) {
        $('pkTransformStatus').textContent=e.message;
      }
    };

    $('pkTransformApply').onclick=async()=>{
      if(!draft)return;
      if(Number($('scenario').value)!==draft.sid)return;
      if(!confirm(
        'Apply the schedule shift and amount multiplier '+
        'to every hypothetical dose in this scenario?'
      ))return;

      const value=draft;
      invalidate();

      try {
        const result=await json(
          '/pk/workspace/'+value.sid+'/transform-apply',
          'POST',value.value
        );
        await window.trackerPkReloadScenario();
        $('pkTransformStatus').textContent=
          result.updated+' hypothetical doses updated.';
      }catch(e) {
        $('pkTransformStatus').textContent=e.message;
      }
    };
  }

  if(document.readyState==='loading')
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  else init();
})();
