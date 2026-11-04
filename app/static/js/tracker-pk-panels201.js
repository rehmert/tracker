(() => {
  'use strict';

  const $=id=>document.getElementById(id);

  function init() {
    const root=$('pkPanelControls');
    if(!root)return;

    const panels=[
      ['Setup','pkSetup'],
      ['Exposure','pkResults'],
      ['Sensitivity','pkSensitivityWorkspace'],
      ['Comparison','pkDeltaCard'],
      ['Scenarios','pkScenarioLibraryAnchor']
    ];

    const status=$('pkPanelStatus');

    function select(id) {
      const element=$(id);
      if(!element)return;

      if(id==='pkScenarioLibraryAnchor') {
        document.querySelector(
          '[data-pk-mode="custom"]'
        )?.click();
      } else if(
        id==='pkDeltaCard'
        ||id==='pkSensitivityWorkspace'
      ) {
        document.querySelector(
          '[data-pk-mode="compare"]'
        )?.click();
      }

      element.scrollIntoView({
        behavior:'auto',
        block:'start'
      });

      for(const button of root.querySelectorAll('button')) {
        button.setAttribute(
          'aria-pressed',
          String(button.dataset.target===id)
        );
      }

      status.textContent=
        'Viewing '+
        element.textContent.trim()
          .split('\n')[0].slice(0,70);
    }

    for(const [label,id] of panels) {
      const button=document.createElement('button');

      button.type='button';
      button.textContent=label;
      button.dataset.target=id;
      button.setAttribute('aria-pressed','false');
      button.onclick=()=>select(id);

      root.append(button);
    }

    window.addEventListener('hashchange',()=>{
      const id=location.hash.slice(1);

      if(panels.some(p=>p[1]===id))
        select(id);
    });
  }

  if(document.readyState==='loading') {
    document.addEventListener(
      'DOMContentLoaded',init,{once:true}
    );
  } else init();
})();
