(() => {
  "use strict";

  function init() {
    const input = document.getElementById(
      "pkHomeSearch"
    );
    if (!input) return;

    const rows = [
      ...document.querySelectorAll(
        "[data-pk-protocol]"
      )
    ];

    const counter = document.getElementById(
      "pkHomeCount"
    );

    const apply = () => {
      const query = input.value.trim().toLowerCase();
      let visible = 0;

      rows.forEach(row => {
        row.hidden = !row.dataset.pkProtocol.includes(query);
        if (!row.hidden) visible++;
      });

      counter.textContent =
        visible + " of " + rows.length +
        " protocols shown.";
    };

    input.addEventListener("input", apply);
    apply();
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", init, {once: true}
    );
  } else {
    init();
  }
})();
