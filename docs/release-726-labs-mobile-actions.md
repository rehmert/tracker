# Release 726 — Labs top actions and phone filter affordances

**Installed DEV base:** Release 725, `7cd9cd9ef76032bd6dc66131f4ccdb20fe10cb4c`.

The Labs overview presented up to five equally weighted navigation links
above the saved reports. On mobile, prioritize the two common tasks:
**Add a lab report** and **Saved reports**. Put optional **Analyte trends**,
**Compare two reports**, and **Reuse latest report layout** behind an
accessible native **More lab tools** disclosure. Destinations and
conditionals remain unchanged; no lab data, schema, HTTP endpoints or
JavaScript state changes.

Improve filter control touch heights to 44px; make report sort select
match the corresponding search input width; use 16px inputs to reduce
mobile viewport zoom; give the More disclosure full grid width on phones.

Qualify on the exact SHA using isolated Jinja, TestClient Labs 200 and
lab-result regression tests, plus read-only Chromium filter and
320/390/430/760/1024 navigation interaction across light/dark schemes.
No full suite is required; PROD requires separate explicit instruction.
