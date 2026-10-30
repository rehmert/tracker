/* TRACKER_WORKFLOW_HUB_105_112: progressive navigation only; no server writes. */
(function () {
 'use strict';
 var key='tracker-workflow-recent-v1', limit=8;
 function load(){try{var x=JSON.parse(localStorage.getItem(key)||'[]');return Array.isArray(x)?x.filter(function(v){return v&&typeof v.path==='string'&&typeof v.label==='string';}).slice(0,limit):[];}catch(e){return [];}}
 function save(x){try{localStorage.setItem(key,JSON.stringify(x.slice(0,limit)));}catch(e){}}
 function init(){
   var hub=document.querySelector('.workflow-hub');
   var nav=Array.from(document.querySelectorAll('#app-sidebar a[href^="/"]'));
   var pathname=location.pathname;
   var current=nav.find(function(a){return a.getAttribute('href')===pathname;});
   if(current && pathname!=='/workflow-hub'){
     var history=load().filter(function(v){return v.path!==pathname;});
     history.unshift({path:pathname,label:current.textContent.trim()||pathname});save(history);
   }
   if(!hub)return;
   var search=document.getElementById('workflow-hub-search'),clear=document.getElementById('workflow-hub-clear');
   var groups=Array.from(hub.querySelectorAll('[data-workflow-group]'));
   var count=document.getElementById('workflow-hub-count'),empty=document.getElementById('workflow-hub-empty');
   function update(){var q=search.value.trim().toLocaleLowerCase(),visible=0;
     groups.forEach(function(group){var groupMatch=group.dataset.workflowGroup.toLocaleLowerCase().includes(q),n=0;
       group.querySelectorAll('[data-workflow-link]').forEach(function(link){var match=!q||groupMatch||link.textContent.toLocaleLowerCase().includes(q);link.hidden=!match;if(match){visible++;n++;}});
       group.hidden=n===0;
     });count.textContent=visible+' tools';empty.hidden=visible!==0;
   }
   search.addEventListener('input',update);clear.addEventListener('click',function(){search.value='';update();search.focus();});
   var recent=document.getElementById('workflow-hub-recent'),list=document.getElementById('workflow-hub-recent-links');
   function renderRecent(){var history=load(),allowed=new Map(Array.from(hub.querySelectorAll('[data-workflow-link]')).map(function(a){return [a.getAttribute('href'),a.textContent.trim().replace(/\s*→\s*$/,'')];}));list.replaceChildren();
     history.forEach(function(item){if(!allowed.has(item.path))return;var a=document.createElement('a');a.href=item.path;a.textContent=allowed.get(item.path);list.appendChild(a);});recent.hidden=!list.children.length;
   }
   document.getElementById('workflow-hub-clear-recent').addEventListener('click',function(){try{localStorage.removeItem(key);}catch(e){}renderRecent();});
   document.addEventListener('keydown',function(e){if(e.key==='/'&&!e.altKey&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&!/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)&&!document.activeElement.isContentEditable){e.preventDefault();search.focus();}});
   update();renderRecent();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
