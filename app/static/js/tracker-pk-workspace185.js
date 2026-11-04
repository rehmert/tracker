(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  function init() {
    const bar=$('pkWorkspaceNav');
    if(!bar)return;

    // The accessible panel controller supersedes the older
    // shortcut bar; avoid displaying duplicate navigation.
    if($('pkPanelControls')){
      bar.hidden=true;
      return;
    }
    const targets=[
      ['Setup','pkSetup'],
      ['Exposure','pkResults'],
      ['Sensitivity','pkSensitivityWorkspace'],
      ['Compare','pkDeltaCard'],
      ['Scenarios','pkScenarioLibraryAnchor']
    ];
    for(const [name,id] of targets) {
      const a=document.createElement('a');
      a.href='#'+id;a.textContent=name;
      a.addEventListener('click',()=>{
        if(name==='Compare'||name==='Sensitivity') {
          document.querySelector('[data-pk-mode="compare"]')?.click();
        } else if(name==='Scenarios') {
          document.querySelector('[data-pk-mode="custom"]')?.click();
        }
      });
      bar.append(a);
    }
    const status=$('pkWorkspaceStatus');
    let requests=0;
    document.addEventListener('tracker:pk-graph-updated',event=>{
      requests++;
      status.textContent='Graph refreshed · '+requests+' · '+
        'compound '+(event.detail?.compoundId??'unknown');
    });
    $('scenario')?.addEventListener('change',()=>{
      status.textContent='Scenario selection changed. Updating view…';
    });
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
