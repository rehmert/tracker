/* Release 511: vial finder, optimized for mobile without changing the dose form.
 * No dose amount, time, site, or supply is copied. Nothing is submitted here.
 */
(() => {
  "use strict";
  function init() {
    const form = document.querySelector('form[hx-post="/doses"]');
    const finder = form?.querySelector("[data-vial-finder511]");
    const select = form?.querySelector('select[name="vial_id"]');
    if (!form || !finder || !select) return;

    const search = finder.querySelector("[data-vial-search511]");
    const matches = finder.querySelector("[data-vial-matches511]");
    const feedback = finder.querySelector("[data-vial-feedback511]");
    const amount = form.querySelector('input[name="amount"]');
    const choices = [...select.options]
      .filter(option => option.value && !option.disabled)
      .map(option => ({
        id: option.value,
        label: option.textContent.trim(),
        text: (option.textContent + " " + option.value).toLocaleLowerCase()
      }));
    const MAX_RESULTS = 8;
    let shown = [];
    function selectedMessage() {
      const option = select.selectedOptions[0];
      return option?.value ? "Selected: " + option.textContent.trim()
        : "Choose a vial before recording.";
    }
    function choose(id) {
      if (!choices.some(item => item.id === id)) return;
      select.value = id;
      // The existing HTMX dose preview and final review listen for changes.
      select.dispatchEvent(new Event("input", { bubbles: true }));
      select.dispatchEvent(new Event("change", { bubbles: true }));
      if (search) search.value = "";
      matches.replaceChildren();
      shown = [];
      feedback.textContent = selectedMessage();
      amount?.focus({ preventScroll: true });
    }
    function renderMatches() {
      const query = (search?.value || "").trim().toLocaleLowerCase();
      shown = query ? choices.filter(item => item.text.includes(query))
        .slice(0, MAX_RESULTS) : [];
      matches.replaceChildren();
      if (!query) {
        feedback.textContent = selectedMessage();
        return;
      }
      if (!shown.length) {
        feedback.textContent = "No vial matches. Try another term or use the complete selector.";
        return;
      }
      for (const item of shown) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "tracker-vial-result511";
        button.textContent = item.label;
        button.addEventListener("click", () => choose(item.id));
        matches.append(button);
      }
      feedback.textContent = shown.length +
        (shown.length === MAX_RESULTS ? " matching vials shown (refine to narrow)." :
          " matching vial" + (shown.length === 1 ? "." : "s."));
    }
    search?.addEventListener("input", renderMatches);
    search?.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        search.value = "";
        renderMatches();
        return;
      }
      if (event.key === "Enter") {
        // Never submit a dose from the search, even when no vials match.
        event.preventDefault();
        if (shown.length) choose(shown[0].id);
      }
    });
    form.querySelectorAll("[data-vial-choice511]").forEach(button => {
      button.addEventListener("click", () => choose(button.dataset.vialChoice511));
    });
    select.addEventListener("change", () => {
      if (!(search?.value || "").trim()) feedback.textContent = selectedMessage();
    });
    feedback.textContent = selectedMessage();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
