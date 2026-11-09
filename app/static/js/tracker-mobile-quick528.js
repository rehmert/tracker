/* Release 528: mobile quick-add.
   Uses existing protected write routes.
   No sensitive data stored in browser storage. */

(() => {
  "use strict";

  function init() {
    const trigger = document.getElementById(
      "tracker-mobile-add528"
    );

    const overlay = document.getElementById(
      "tracker-mobile-quick528"
    );

    const sheet = overlay?.querySelector(
      ".tracker-quick528-sheet"
    );

    if (!trigger || !overlay || !sheet) return;

    const mobile = window.matchMedia(
      "(max-width:760px)"
    );

    const choices = overlay.querySelector(
      "[data-quick528-choices]"
    );

    const entry = overlay.querySelector(
      "[data-quick528-entry]"
    );

    const success = overlay.querySelector(
      "[data-quick528-success]"
    );

    const status = overlay.querySelector(
      "[data-quick528-status]"
    );

    const title = overlay.querySelector(
      "[data-quick528-entry-title]"
    );

    const forms = [
      ...overlay.querySelectorAll("[data-quick528-form]")
    ];

    let selected = null;
    let lastFocus = null;
    let busy = false;

    function stamp() {
      const now = new Date();
      const part = n => String(n).padStart(2, "0");

      const day = [
        now.getFullYear(),
        part(now.getMonth() + 1),
        part(now.getDate())
      ].join("-");

      return {
        date: day,
        time: day + "T" +
          part(now.getHours()) + ":" +
          part(now.getMinutes())
      };
    }

    function message(value) {
      status.textContent = value || "";
    }

    function showChoices() {
      selected = null;
      choices.hidden = false;
      entry.hidden = true;
      success.hidden = true;

      forms.forEach(form => {
        form.hidden = true;
      });

      message("");
    }

    function open() {
      if (!mobile.matches) return;

      lastFocus = document.activeElement;
      overlay.hidden = false;

      document.body.classList.add(
        "tracker-quick528-open"
      );

      trigger.setAttribute(
        "aria-expanded", "true"
      );

      showChoices();

      overlay.querySelector(
        "[data-quick528-close]"
      ).focus();
    }

    function close() {
      if (busy) return;

      overlay.hidden = true;

      document.body.classList.remove(
        "tracker-quick528-open"
      );

      trigger.setAttribute(
        "aria-expanded", "false"
      );

      if (lastFocus?.isConnected) {
        lastFocus.focus({preventScroll: true});
      }
    }

    function choose(kind) {
      if (busy) return;

      selected = kind;

      choices.hidden = true;
      entry.hidden = false;
      success.hidden = true;

      title.textContent = {
        weight: "Record Weight",
        bp: "Record Blood Pressure",
        water: "Record Water"
      }[kind];

      const now = stamp();

      forms.forEach(form => {
        form.hidden =
          form.dataset.quick528Form !== kind;

        form.querySelectorAll(
          "[data-quick528-time]"
        ).forEach(input => {
          input.value = now.time;
        });

        form.querySelectorAll(
          "[data-quick528-day]"
        ).forEach(input => {
          input.value = now.date;
        });
      });

      message("");

      const form = forms.find(f => !f.hidden);

      form?.querySelector(
        'input:not([type="hidden"])'
      )?.focus({preventScroll: true});
    }

    trigger.addEventListener("click", event => {
      // Desktop retains the existing /quick-entry link.
      if (!mobile.matches) return;

      event.preventDefault();

      if (overlay.hidden) open();
      else close();
    });

    overlay.querySelector(
      "[data-quick528-close]"
    ).addEventListener("click", close);

    overlay.querySelector(
      "[data-quick528-back]"
    ).addEventListener("click", () => {
      showChoices();
      choices.querySelector("button")?.focus();
    });

    overlay.querySelector(
      "[data-quick528-done]"
    ).addEventListener("click", close);

    overlay.querySelector(
      "[data-quick528-another]"
    ).addEventListener("click", () => {
      const kind = selected;

      const form = forms.find(
        f => f.dataset.quick528Form === kind
      );

      form?.reset();
      choose(kind);
    });

    for (const button of overlay.querySelectorAll(
      "[data-quick528-choice]"
    )) {
      button.addEventListener("click", () => {
        choose(button.dataset.quick528Choice);
      });
    }

    overlay.addEventListener("click", event => {
      if (event.target === overlay) close();
    });

    overlay.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }

      if (event.key !== "Tab") return;

      const focusable = [
        ...sheet.querySelectorAll(
          'a[href], button:not([disabled]), ' +
          'input:not([type="hidden"]), select'
        )
      ].filter(element => !element.closest("[hidden]"));

      if (!focusable.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (
        event.shiftKey &&
        document.activeElement === first
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        document.activeElement === last
      ) {
        event.preventDefault();
        first.focus();
      }
    });

    mobile.addEventListener?.("change", () => {
      if (!mobile.matches) close();
    });

    for (const form of forms) {
      form.addEventListener(
        "submit",
        async event => {
          event.preventDefault();

          if (busy || !form.reportValidity()) {
            return;
          }

          busy = true;

          const save = form.querySelector(
            'button[type="submit"]'
          );

          save.disabled = true;
          message("Saving…");

          try {
            const response = await fetch(
              form.action,
              {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
                headers: {
                  "X-Tracker-Mobile-Quick": "528",
                  "Accept": "application/json"
                },
                redirect: "error"
              }
            );

            const data = await response.json();

            if (!response.ok || !data.ok) {
              throw new Error(
                data.error ||
                "Save rejected. Review your entry."
              );
            }

            entry.hidden = true;
            success.hidden = false;

            overlay.querySelector(
              "[data-quick528-saved-value]"
            ).textContent =
              data.value ||
              data.message ||
              "Saved.";

            const review = overlay.querySelector(
              "[data-quick528-edit]"
            );

            review.href = data.edit_url || (
              selected === "water"
                ? "/food#food-water"
                : "/vitals"
            );

            review.textContent =
              selected === "water"
                ? "Review water log"
                : "Edit saved reading";

            message("");

            overlay.querySelector(
              "[data-quick528-another]"
            ).focus();

          } catch (error) {
            message(
              error.message ||
              "Could not save. Check your connection."
            );

          } finally {
            busy = false;
            save.disabled = false;
          }
        }
      );
    }

    window.addEventListener("pageshow", () => {
      busy = false;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      init,
      {once: true}
    );
  } else {
    init();
  }
})();
