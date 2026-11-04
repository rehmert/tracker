(() => {
  'use strict';
  function init(){
    const root=document.getElementById('pkGraphLayerControls');
    if(!root)return;
    root.addEventListener('change',()=>{
      if(!window.trackerPkFullGraph)return;
      document.dispatchEvent(new CustomEvent('tracker:pk-graph-updated',{
        detail:{source:'layer-visibility'}
      }));
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
