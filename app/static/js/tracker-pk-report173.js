(() => {
  'use strict';
  const $=id=>document.getElementById(id);

  function init() {
    if(!$('pkReportDownload'))return;

    $('pkReportDownload').onclick=async()=>{
      const sid=Number($('scenario').value);
      if(!sid) {
        $('pkReportStatus').textContent=
          'Select a saved scenario first.';
        return;
      }

      try {
        const r=await fetch(
          '/pk/workspace/'+sid+'/report',
          {cache:'no-store'}
        );

        if(!r.ok)throw Error(
          'Report unavailable: HTTP '+r.status
        );

        const report=await r.json();
        const url=URL.createObjectURL(
          new Blob(
            [JSON.stringify(report,null,2)],
            {type:'application/json'}
          )
        );

        const link=document.createElement('a');
        link.href=url;
        link.download='tracker-scenario-report.json';
        link.click();

        setTimeout(
          ()=>URL.revokeObjectURL(url),1000
        );

        $('pkReportStatus').textContent=
          'Scenario report exported.';
      }catch(e) {
        $('pkReportStatus').textContent=e.message;
      }
    };

    $('pkReportCopyRevision').onclick=async()=>{
      const sid=Number($('scenario').value);
      if(!sid)return;

      try {
        const r=await fetch(
          '/pk/scenarios/'+sid+'/revision',
          {cache:'no-store'}
        );

        if(!r.ok)throw Error('Revision unavailable');
        const data=await r.json();

        await navigator.clipboard.writeText(
          data.version
        );

        $('pkReportStatus').textContent=
          'Scenario revision copied.';
      }catch(e) {
        $('pkReportStatus').textContent=e.message;
      }
    };
  }

  if(document.readyState==='loading')
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  else init();
})();
