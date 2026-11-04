/*
 * Tracker Releases 105-108.
 *
 * Scenario-first layout, automatic previews and visible state.
 * Existing saved-scenario endpoints remain authoritative.
 * Nothing is saved by simply loading or previewing.
 */
(() => {
  "use strict";

  function initialize() {
    const $ = id => document.getElementById(id);

    const setup = $("pkSetup");
    const scenario = $("scenario");
    const graph = $("pkResults");
    const builder = $("whatIfCard");

    if (!setup || !scenario || !graph || !builder)
      return;

    const card = scenario.closest(".card");
    if (!card) return;

    // Keep saved scenarios immediately adjacent to their graph.
    // The more advanced recurring what-if builder follows both.
    setup.after(card, graph);

    card.classList.add("pk-scenario-primary");

    const title = card.querySelector("h2");
    if (title)
      title.textContent = "Saved PK scenarios";

    const introduction = document.createElement("p");
    introduction.className = "note";
    introduction.textContent =
      "Select a saved scenario to load its assumptions, " +
      "planned administrations and exposure graph. " +
      "Previewing changes never saves them.";

    if (title) title.after(introduction);
    else card.prepend(introduction);

    const status = document.createElement("p");
    status.id = "pkScenarioLoadStatus";
    status.className = "pk-scenario-state";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    introduction.after(status);

    const selectorLabel = scenario.closest("label");
    if (selectorLabel)
      selectorLabel.classList.add("pk-scenario-selector");

    const run = $("refresh");
    const update = $("update");
    const create = $("save");

    const fieldIds = [
      "scenarioName", "half", "abs"
    ];

    let savedValues = null;
    let debounce = null;
    let selecting = false;
    let requestVersion = 0;
    let latestRequestedVersion = 0;

    function setStatus(value, kind = "") {
      status.textContent = value;
      status.dataset.state = kind;
    }

    function values() {
      return {
        id: scenario.value,
        name: $("scenarioName").value,
        half: $("half").value,
        absorption: $("abs").value
      };
    }

    function rememberSaved() {
      savedValues = scenario.value ? values() : null;
    }

    function hasChanges() {
      if (!savedValues || !scenario.value)
        return false;

      const current = values();

      return current.id !== savedValues.id ||
        current.name !== savedValues.name ||
        current.half !== savedValues.half ||
        current.absorption !== savedValues.absorption;
    }

    function showState() {
      if (selecting) return;

      if (!scenario.value) {
        setStatus(
          "No saved scenario selected. " +
          "Configure a new scenario or choose an existing one.",
          "neutral"
        );
      } else if (hasChanges()) {
        setStatus(
          "Unsaved settings · Preview updates do not " +
          "overwrite the saved scenario.",
          "unsaved"
        );
      } else {
        setStatus(
          "Saved scenario selected · Graph is ready.",
          "ready"
        );
      }
    }

    function schedulePreview() {
      clearTimeout(debounce);

      if (
        !Number.isFinite(Number($("half").value)) ||
        !Number.isFinite(Number($("abs").value)) ||
        Number($("half").value) <= 0 ||
        Number($("abs").value) <= 0
      ) {
        setStatus(
          "Enter positive elimination and absorption " +
          "half-lives to preview.",
          "warning"
        );
        return;
      }

      const currentVersion = ++requestVersion;
      latestRequestedVersion = currentVersion;

      setStatus(
        hasChanges()
          ? "Unsaved settings · Updating graph preview…"
          : "Updating graph preview…",
        "loading"
      );

      debounce = setTimeout(() => {
        if (currentVersion !== latestRequestedVersion)
          return;

        run.click();
      }, 350);
    }

    // The original PK script loads scenario details and runs
    // the graph request. Preserve that behavior, adding a
    // clear mode selection and loading state.
    const originalSelect = scenario.onchange;

    if (typeof originalSelect !== "function")
      throw new Error(
        "Tracker PK scenario handler was not initialized"
      );

    scenario.onchange = async function(event) {
      clearTimeout(debounce);
      selecting = true;

      if (scenario.value) {
        const custom = document.querySelector(
          '[data-pk-mode="custom"]'
        );
        custom?.click();
      }

      setStatus(
        scenario.value
          ? "Loading saved scenario and graph…"
          : "Clearing saved scenario…",
        "loading"
      );

      $("pkError").textContent = "";

      try {
        await originalSelect.call(this, event);
        rememberSaved();
        selecting = false;

        if ($("pkError").textContent.trim()) {
          setStatus(
            "Scenario selected, but the graph could " +
            "not be updated. Check the error below.",
            "warning"
          );
        } else {
          showState();
        }
      } catch (error) {
        selecting = false;
        setStatus(
          "Unable to load scenario: " + error.message,
          "warning"
        );
      }
    };

    fieldIds.forEach(id => {
      $(id).addEventListener("input", () => {
        if (id === "scenarioName") showState();
        else schedulePreview();
      });
    });

    // Changes to the visible time window do not change
    // the saved scenario definition.
    ["back", "forward"].forEach(id => {
      $(id).addEventListener(
        "input", schedulePreview
      );
    });

    document.addEventListener(
      "tracker:pk-graph-updated",
      event => {
        if (
          !scenario.value ||
          String(event.detail.scenarioId) === scenario.value
        ) {
          if (!selecting) showState();
        }
      }
    );

    // Preserve existing create/update handlers; they are
    // responsible for persistence and validation.
    function wrapPersistence(button, message) {
      const original = button.onclick;
      if (typeof original !== "function") return;

      button.onclick = async function(event) {
        clearTimeout(debounce);
        $("pkError").textContent = "";

        setStatus(
          "Saving scenario settings…",
          "loading"
        );

        try {
          await original.call(this, event);

          if ($("pkError").textContent.trim()) {
            setStatus(
              "Save failed. Check the error below.",
              "warning"
            );
          } else {
            rememberSaved();
            setStatus(message, "ready");
          }
        } catch (error) {
          setStatus(
            "Save failed: " + error.message,
            "warning"
          );
        }
      };
    }

    wrapPersistence(
      create,
      "New saved scenario created · Graph ready."
    );

    wrapPersistence(
      update,
      "Scenario name and half-lives saved."
    );

    // Make the explicit Run action useful as a fallback.
    run.setAttribute(
      "aria-label",
      "Recalculate the PK exposure graph"
    );

    if (update) {
      update.title =
        "Save the scenario name and half-lives. " +
        "Previewing does not save changes.";
    }

    if (create) {
      create.title =
        "Create a separate saved PK scenario.";
    }

    rememberSaved();
    showState();
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded", initialize, {once:true}
    );
  } else {
    initialize();
  }
})();
