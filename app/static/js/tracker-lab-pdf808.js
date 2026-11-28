/* Preview and edit local PDF extraction; native form retains attachment. */
(() => {
  "use strict";
  const form = document.querySelector("form[data-lab-manual-entry]");
  if (!form) return;
  const file = form.querySelector('input[name="file"]');
  const extract = form.querySelector("[data-pdf-extract808]");
  const output = form.querySelector("[data-pdf-status808]");
  const warnings = form.querySelector("[data-pdf-warnings808]");
  const source = form.querySelector("[data-pdf-source808]");
  const tbody = form.querySelector("#lab-rows");
  const review = form.querySelector("[data-pdf-review808]");
  const ack = review.querySelector('input[type="checkbox"]');
  let previewed = null, busy = false;
  const fields = ["analyte","value","unit","ref_low","ref_high"];
  function show(text) { output.textContent = text; }
  function resetReview() {
    previewed = null; review.hidden = true; ack.checked = false;
    warnings.replaceChildren(); source.replaceChildren();
  }
  function makeRow(row) {
    const template = form.querySelector("[data-pdf-row808]");
    const tr = template.content.firstElementChild.cloneNode(true);
    fields.forEach(name => { tr.querySelector('input[name="'+name+'"]').value = row[name] || ""; });
    return tr;
  }
  function addLine(parent, text) {
    const li = document.createElement("li"); li.textContent = text; parent.append(li);
  }
  file.addEventListener("change", () => {
    if (previewed) show("Attachment changed. Review existing rows or extract the new PDF again.");
    resetReview();
  });
  extract.addEventListener("click", async () => {
    if (busy) return;
    const selected = file.files[0];
    if (!selected || !/\.pdf$/i.test(selected.name)) { show("Choose a PDF first."); return; }
    if (selected.size > 15*1024*1024) { show("PDF exceeds 15 MB."); return; }
    if ([...tbody.querySelectorAll("input")].some(i => i.value.trim()) &&
        !window.confirm("Replace the current analyte rows with extracted results?")) return;
    busy = true; extract.disabled = true; resetReview();
    show("Extracting PDF locally…");
    try {
      const data = new FormData(); data.append("file", selected);
      const response = await fetch("/labs/pdf-preview", {method:"POST", body:data, cache:"no-store"});
      const result = await response.json();
      if (file.files[0] !== selected) { show("Attachment changed; extract again."); return; }
      if (!response.ok) { show(result.error || "PDF extraction failed."); return; }
      if (result.existing_report_id) {
        show("This exact PDF is already attached to report #"+result.existing_report_id+". Review that report before importing again.");
        const a = document.createElement("a");
        a.href = "/labs/"+encodeURIComponent(result.existing_report_id);
        a.textContent = "Open existing report"; output.append(" ", a);
        return;
      }
      (result.warnings || []).forEach(text => addLine(warnings, text));
      if (!result.rows.length) {
        show("No reliable numeric rows extracted. Enter results manually or review the source PDF.");
        return;
      }
      tbody.replaceChildren(...result.rows.map(makeRow));
      if (window.htmx) window.htmx.process(tbody);
      form.elements.drawn_on.value = result.drawn_on || "";
      form.elements.lab_name.value = result.lab_name || "";
      result.rows.forEach(row => addLine(source, "Page "+row.page+": "+row.source));
      previewed = selected; review.hidden = false; ack.checked = false;
      show(result.rows.length+" numeric results extracted. Verify every row and any exclusions against the PDF before saving.");
      form.dispatchEvent(new Event("input",{bubbles:true}));
      tbody.querySelector("input")?.focus();
    } catch (_) { show("PDF extraction request failed. Try again or enter results manually."); }
    finally { busy = false; extract.disabled = false; }
  });
  form.addEventListener("submit", event => {
    if (busy || (previewed && (!ack.checked || file.files[0] !== previewed))) {
      event.preventDefault();
      show("Complete extraction and confirm review before saving.");
      if (!review.hidden) ack.focus();
    }
  }, true);
})();
