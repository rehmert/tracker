/* Release 662: read-only gym UI enhancements; all writes stay in 659 forms. */
(() => {
  "use strict";
  const root = document.getElementById("workout659-root");
  if (!root) return;

  // Changing the native machine selector is enough on mobile.
  // Keep the existing Go button as the no-JavaScript/keyboard fallback.
  const picker = root.querySelector("form.workout659-machine-picker");
  const selector = picker?.querySelector('select[name="machine"]');
  if (picker && selector) {
    selector.addEventListener("change", () => {
      const id = selector.value;
      if (!/^[1-9]\d*$/.test(id)) return;
      if (typeof picker.requestSubmit === "function") picker.requestSubmit();
    });
  }

  // A collapsed machine directory is a usable link list without JavaScript.
  // Search only filters these existing authenticated, server-rendered links.
  const search = document.getElementById("workout662-search");
  const results = document.getElementById("workout662-results");
  const links = Array.from(root.querySelectorAll(
    ".workout662-directory-list a[data-search662]"
  ));
  if (!search || !results || !links.length) return;

  function refresh() {
    const term = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const link of links) {
      const text = (link.dataset.search662 || "").toLocaleLowerCase();
      const match = !term || text.includes(term);
      link.hidden = !match;
      if (match) visible++;
    }
    results.textContent = visible
      ? String(visible) + " of " + String(links.length) + " machines shown."
      : "No matching machines. Clear search to browse all.";
  }
  search.addEventListener("input", refresh);
  refresh();
})();
