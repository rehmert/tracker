# Release 721 — Recent Workouts dropdown arrow

DEV baseline: Release 720, exact commit `dc4e3b1d72fa3fd96751424e1b91af42bb0409d7`.

On **Overview → Workout Activity**, the **Recent Workouts** native disclosure remains collapsed initially, and shows an explicit down-pointing chevron immediately after its summary label. Opening the section turns the chevron up; closing turns it down. The summary is still a 48px-tall keyboard-accessible native control. The previous ten-workout pagination, sorting, and delete actions are unchanged.

Implementation is scoped to `app/static/css/tracker-workout-dashboard661.css` (pseudo-element, no JS or backend changes), its dashboard cache-version reference, and related QA contracts. The mobile Chromium test verifies actual computed chevron content, closed/open transforms, hidden/visible workout rows, and horizontal fit. The earlier overview density, CSS order, and workout dashboard regression tests also run.

Guarded, isolated exact-SHA qualification on DEV, then a separate guarded DEV install after a passing receipt. No PROD deployment or preflight is authorized.
