(() => {
  'use strict';

  const $=id=>document.getElementById(id);

  function init() {
    if(!$('pkWeekPreview'))return;

    const extra=$('pkAdditionalStages');

    window.trackerPkExtraStages=()=>
      [...extra.querySelectorAll('.pk-extra-stage')]
      .map(row=>({
        amount_mg:Number(
          row.querySelector('[data-field="amount"]').value
        ),
        count:Number(
          row.querySelector('[data-field="count"]').value
        ),
        interval_days:Number(
          row.querySelector('[data-field="interval"]').value
        )
      }));

    $('pkAddStage').onclick=()=>{
      if(extra.children.length>=6)return;

      const wrap=document.createElement('div');
      wrap.className='pk-extra-stage';

      for(const [field,label,value] of [
        ['amount','Amount (mg)','1'],
        ['count','Count','8'],
        ['interval','Interval (days)','7']
      ]) {
        const el=document.createElement('label');
        el.textContent=label;

        const input=document.createElement('input');
        input.type='number';
        input.dataset.field=field;
        input.step='any';
        input.min=field==='interval'?'0.125':'1';
        input.value=value;

        el.append(input);
        wrap.append(el);
      }

      const remove=document.createElement('button');
      remove.type='button';
      remove.textContent='Remove stage';

      remove.onclick=()=>{
        wrap.remove();
        $('pkStageReplace').disabled=true;
      };

      wrap.append(remove);
      wrap.addEventListener('input',()=>{
        $('pkStageReplace').disabled=true;
      });

      extra.append(wrap);
      $('pkStageReplace').disabled=true;
    };

    let preview=null;

    const changed=()=>{
      preview=null;
      $('pkWeekReplace').disabled=true;
    };

    [
      ...$('pkWeekdays').querySelectorAll('input'),
      ...[
        'pkWeekStart','pkWeekEnd',
        'pkWeekTime','pkWeekAmount',
        'pkWeekTimezone'
      ].map($)
    ].forEach(el=>
      el.addEventListener('input',changed)
    );

    $('scenario').addEventListener(
      'change',changed
    );

    const csrf=()=>window.trackerCsrfToken?.();

    async function post(url,data) {
      const headers={
        'Content-Type':'application/json'
      };

      if(csrf())
        headers['X-Tracker-CSRF']=csrf();

      const r=await fetch(url,{
        method:'POST',
        headers,
        credentials:'same-origin',
        body:JSON.stringify(data)
      });

      if(!r.ok)
        throw Error(
          'HTTP '+r.status+': '+
          (await r.text()).slice(0,200)
        );

      return r.json();
    }

    $('pkWeekPreview').onclick=async()=>{
      changed();

      const sid=Number($('scenario').value);

      if(!sid) {
        $('pkWeekStatus').textContent=
          'Select a saved scenario first';
        return;
      }

      const data={
        start:$('pkWeekStart').value,
        end:$('pkWeekEnd').value,
        local_time:$('pkWeekTime').value,
        amount_mg:Number(
          $('pkWeekAmount').value
        ),
        timezone_name:$('pkWeekTimezone').value,
        weekdays:[
          ...$('pkWeekdays')
          .querySelectorAll('input:checked')
        ].map(el=>Number(el.value))
      };

      try {
        const v=await fetch(
          '/pk/scenarios/'+sid+'/revision',
          {cache:'no-store'}
        );

        if(!v.ok)
          throw Error('Revision unavailable');

        data.expected_version=
          (await v.json()).version;

        const result=await post(
          '/pk/scenarios/'+sid+'/calendar-preview',
          data
        );

        if(Number($('scenario').value)!==sid)return;

        preview={sid,data};

        $('pkWeekStatus').textContent=
          result.doses.length+
          ' hypothetical doses. '+
          (
            result.warnings.length
              ?result.warnings.join(' | ')
              :'No DST warnings; ready to confirm.'
          );

        $('pkWeekReplace').disabled=
          Boolean(result.warnings.length);
      } catch(e) {
        $('pkWeekStatus').textContent=e.message;
      }
    };

    $('pkWeekReplace').onclick=async()=>{
      if(
        !preview||
        preview.sid!==Number($('scenario').value)
      )return;

      if(!confirm(
        'Replace ALL hypothetical planned doses '+
        'in this scenario?'
      ))return;

      const job=preview;
      changed();

      try {
        const r=await post(
          '/pk/scenarios/'+job.sid+
          '/calendar-replace',
          job.data
        );

        await window.trackerPkReloadScenario();

        $('pkWeekStatus').textContent=
          'Saved '+r.replaced+
          ' hypothetical dates.';
      } catch(e) {
        $('pkWeekStatus').textContent=e.message;
      }
    };
  }

  if(document.readyState==='loading') {
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  } else init();
})();
