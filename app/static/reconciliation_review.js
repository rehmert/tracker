(() => {
  'use strict';
  document.querySelectorAll('.reconcile-form').forEach(form => {
    const counted=form.elements.namedItem('counted');
    const reason=form.elements.namedItem('reason');
    const expected=form.elements.namedItem('expected');
    const confirmed=form.elements.namedItem('confirmed');
    const review=form.querySelector('.reconcile-review');
    const submit=form.querySelector('.reconcile-submit');
    const preview=form.querySelector('.reconcile-preview');
    const reset=()=>{confirmed.value='no';submit.hidden=true;review.hidden=false;preview.textContent='';};
    counted.addEventListener('input',reset);reason.addEventListener('input',reset);
    review.addEventListener('click',()=>{
      if(!form.reportValidity())return;
      const delta=Number(counted.value)-Number(expected.value);
      if(!Number.isFinite(delta))return;
      preview.textContent=`${form.dataset.item}: ${Number(expected.value).toLocaleString()} → ${Number(counted.value).toLocaleString()} (${delta>=0?'+':''}${delta.toLocaleString()}). Reason: ${reason.value.trim()}`;
      if(!reason.value.trim())return;
      confirmed.value='yes';submit.hidden=false;review.hidden=true;
    });
    form.addEventListener('submit',e=>{if(confirmed.value!=='yes'){e.preventDefault();review.click();}});
  });
})();
