/* Release 668: CSV preview from a local file; server validates every row. */
(() => {
  "use strict";
  const file = document.getElementById("workout668-csv-file");
  const input = document.getElementById("workout668-csv-text");
  const status = document.getElementById("workout668-csv-status");
  if (!file || !input || !status) return;
  file.addEventListener("change", async () => {
    const chosen = file.files?.[0];
    if (!chosen) return;
    if (chosen.size > 160000 || chosen.size === 0) {
      status.textContent = "Choose a CSV up to 160 KB.";
      return;
    }
    try {
      const content = await chosen.text();
      if (content.length > 160000) {
        status.textContent = "CSV is too large.";
        return;
      }
      input.value = content;
      status.textContent = "CSV loaded for review. Importing will create new sessions only.";
    } catch (_) {
      status.textContent = "Unable to read this local file.";
    }
  });
})();
