/*
 * Release 462: serving-basis-aware nutrition preview.
 *
 * Entirely local calculations. No remote calls, no new
 * POST fields, and no automatic journal submission.
 */
(function () {
  "use strict";

  const form = document.getElementById(
    "manual-food-form460"
  );
  const basisLabel = document.getElementById(
    "nutrition-basis-label462"
  );
  const gramsRow = document.getElementById(
    "nutrition-grams-row462"
  );
  const gramsInput = document.getElementById(
    "nutrition-grams462"
  );
  const totalStatus = document.getElementById(
    "nutrition-status462"
  );

  if (
    !form || !basisLabel || !gramsRow ||
    !gramsInput || !totalStatus
  ) {
    return;
  }

  const servings = form.elements.namedItem("servings");

  if (!servings) {
    return;
  }

  const nutrients = [
    ["energy", "Calories", "kcal"],
    ["proteins", "Protein", "g"],
    ["carbohydrates", "Carbohydrates", "g"],
    ["fat", "Fat", "g"],
    ["fiber", "Fiber", "g"]
  ];

  let basis = "manual";
  let description = "1 serving";

  function validQuantity(raw, max) {
    if (raw === "" || !/^\d+(?:\.\d{1,3})?$/.test(raw)) {
      return null;
    }
    const value = Number(raw);
    return Number.isFinite(value) &&
      value > 0 && value <= max ? value : null;
  }

  function pretty(number) {
    return String(Math.round(number * 100) / 100);
  }

  function updateNutrition() {
    const count = validQuantity(servings.value, 100);

    if (count === null) {
      totalStatus.textContent =
        "Enter a valid number of servings to preview totals.";
      nutrients.forEach(function (item) {
        const output = document.getElementById(
          "nutrition-total-" + item[0] + "462"
        );
        if (output) output.textContent = "—";
      });
      return;
    }

    let known = 0;
    let unknown = 0;

    nutrients.forEach(function (item) {
      const field = form.elements.namedItem(item[0]);
      const output = document.getElementById(
        "nutrition-total-" + item[0] + "462"
      );

      if (!field || !output) {
        return;
      }

      const raw = field.value.trim();

      if (
        raw === "" ||
        !/^\d+(?:\.\d{1,3})?$/.test(raw) ||
        Number(raw) > 100000
      ) {
        output.textContent = "Unknown";
        unknown += 1;
        return;
      }

      const amount = Number(raw) * count;

      if (!Number.isFinite(amount)) {
        output.textContent = "Unknown";
        unknown += 1;
        return;
      }

      output.textContent =
        pretty(amount) + " " + item[2];
      known += 1;
    });

    totalStatus.textContent =
      pretty(count) + " portion(s) · " +
      String(known) + " nutrients known, " +
      String(unknown) + " unknown. " +
      "Verify the package before saving.";
  }

  function updateFromGrams() {
    if (basis !== "per 100 g") return;

    const grams = validQuantity(gramsInput.value, 10000);

    if (grams === null || grams < 0.1) {
      servings.value = "";
      updateNutrition();
      return;
    }

    const calculated = Math.round(grams * 10) / 1000;

    servings.value = String(calculated);
    updateNutrition();
  }

  function updateGramsFromServings() {
    if (basis === "per 100 g") {
      const value = validQuantity(servings.value, 100);
      gramsInput.value = value === null
        ? "" : String(Math.round(value * 1000) / 10);
    }
    updateNutrition();
  }

  function changeBasis(event) {
    const detail = event && event.detail;
    if (!detail || typeof detail.basis !== "string") {
      return;
    }

    basis = detail.basis === "per 100 g"
      ? "per 100 g" : "per serving";

    description =
      typeof detail.serving === "string"
        ? detail.serving.slice(0, 80)
        : "1 serving";

    if (basis === "per 100 g") {
      basisLabel.textContent =
        "Nutrition basis: per 100 g. " +
        "Enter the weight you ate in grams. " +
        "For example, 150 g equals 1.5 portions.";
      gramsRow.hidden = false;

      // Existing servings remain authoritative for the
      // backend. Set a coherent default for 100 g.
      gramsInput.value = "100";
      servings.value = "1";
    } else {
      basisLabel.textContent =
        "Nutrition basis: per serving (" +
        (description || "check the package") +
        "). Enter the number of servings eaten.";
      gramsRow.hidden = true;
      gramsInput.value = "";
      servings.value = "1";
    }

    updateNutrition();
  }

  document.addEventListener(
    "tracker:barcode-loaded462", changeBasis
  );

  gramsInput.addEventListener("input", updateFromGrams);
  servings.addEventListener(
    "input", updateGramsFromServings
  );

  nutrients.forEach(function (item) {
    const field = form.elements.namedItem(item[0]);
    if (field) {
      field.addEventListener("input", updateNutrition);
    }
  });

  basisLabel.textContent =
    "Manual entry: nutrient values are per serving.";
  gramsRow.hidden = true;
  updateNutrition();
})();
