/* Release 763: unit changes convert the visible numeric entries and labels. */
(() => {
  "use strict";
  const factor = {length:{in:2.54,cm:1},mass:{lb:0.45359237,kg:1}};
  function attach(select) {
    const family=factor[select.dataset.progressUnit], form=select.closest("form");
    if (!family || !form) return;
    const inputs=[...form.querySelectorAll(select.dataset.progressInputs || "[data-never]")];
    const labels=[...form.querySelectorAll(select.dataset.progressLabels || "[data-never]")];
    let previous=select.value;
    const label=(unit)=>labels.forEach(el=>{el.textContent="("+unit+")";});
    label(previous);
    select.addEventListener("change",()=>{
      const next=select.value;
      if (!(next in family) || !(previous in family)) return;
      const ratio=family[previous]/family[next];
      if(next!==previous)inputs.forEach(input=>{
        if(input.value.trim()==="")return;
        const amount=Number(input.value);
        if(Number.isFinite(amount))input.value=String(Number((amount*ratio).toFixed(4)));
      });
      previous=next;label(next);
    });
  }
  document.addEventListener("DOMContentLoaded",()=>document.querySelectorAll("select[data-progress-unit]").forEach(attach));
})();
