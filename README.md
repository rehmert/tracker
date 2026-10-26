# Tracker

A single-user web app for keeping personal records: peptide and testosterone **inventory, purchases, COAs, logged doses and costs**, a what-if protocol calculator, **weight / blood pressure / pulse** tracking, and **notes pages with sources** for things you read or find.

It is a recordkeeping tool. It does unit arithmetic on numbers you enter and never suggests, checks or optimizes doses. It does not know what a "normal" amount is for anything, and it doesn't label vitals as normal, high or low.

Stack: FastAPI, SQLite (SQLAlchemy 2), Jinja2 + HTMX. No JavaScript build step.

## What it does

| Area | Details |
|---|---|
| Compounds | Name, category, notes. |
| Purchases | Vendor, date, order ref, shipping, tax, discount. Shipping/tax/discount are spread across the purchase's vials by price to give each vial a **landed cost**. |
| Vials | One row per physical vial; add N identical vials at once for a kit. Powder or solution, contents in mcg / mg / g / IU, liquid volume or reconstitution volume, lot, expiry, status (sealed, in use, finished, discarded). |
| COAs | Upload PDF/PNG/JPG/WEBP per vial (15 MB cap, extension allow-list, magic-byte check, random stored name, SHA-256). Record lab, test date, purity %, reported content. Shows label-vs-COA variance; a per-vial switch makes inventory and cost use the COA figure instead of the label. |
| Dose log | Enter in mcg / mg / g / IU or mL / uL. Volumes convert through the vial's concentration. Live preview of the conversion, cost and amount remaining. Waste entries count against stock. |
| Costs | Cost per mg (or per IU), per logged entry, stock value on hand, spend by compound and by month. |
| Vitals | Weight (stored in kg, shown in kg or lb), blood pressure and pulse, any combination per reading, with context and notes. Server-drawn SVG trend charts over 30 days / 90 days / 1 year / all, plus latest, 7- and 30-day averages, range and 30-day change. Typo guards reject impossible values (e.g. top number below bottom); there is no clinical interpretation. |
| Chart events | Vitals charts (and each lab analyte chart) can overlay your own records on one shared time axis: **dose ticks** in one lane per compound under the plot, and **dashed lines with letters** for **P**urchase, **R**econstituted, **S**tart (first logged use of a vial), **F**inish (last logged use of a finished or discarded vial) and **L**ab draw. Toggle them with "Hide / Show dose and vial events". They're context only; nothing implies cause and effect. |
| Lab results | A lab report (date, lab, optional PDF/image copy, notes) holds any number of results: analyte, value, unit and the **range printed on the report** (both ends or neither). An index of per-analyte trend charts, an analyte page with the full history, and the printed range shaded on the chart. Results are compared with the printed range as plain "below / within / above" text, nothing more. Results in different units are converted for charting only for a short list of common analytes (testosterone, estradiol, glucose, cholesterol fractions, triglycerides, creatinine, hemoglobin, IGF-1); anything else stays in its own unit and is counted as "not drawn" rather than guessed. |
| Notes | Free-text pages with markdown-style formatting, tags, optional links to compounds, `[[Page title]]` links between pages with backlinks, and a live preview while editing. Each page holds any number of **sources**: web links, books, papers (title, author, site or publisher, chapter/page/DOI, access date, short note). Search covers titles, text, tags and sources. |
| Protocols | Free-form what-if plans: any amount, unit and frequency (per day / week / month, or once every N days). Results recalculate as you type: usage, cost per entry/week/month, current stock, days of supply and run-out date, need over a look-ahead window, shortfall, vials to buy and their estimated cost, plus the change against the saved version. Saving a protocol never touches stock or the log. |

### Unit rules

- Mass is stored in mcg, volume in mL, and IU as its own dimension. **IU never converts to mass** because that needs a product-specific potency; mixing them is refused rather than guessed.
- A vial is tracked in mass or IU. A volume dose is accepted only if the vial has a known volume (a solution's volume, or a powder's reconstitution volume).
- A compound's vials must all use the same dimension.
- Money is integer cents in the database.
- Syringe marks assume a U-100 syringe (100 marks = 1 mL) and are just `mL x 100`.

### Pricing used by protocols

Price per unit = total landed cost / total contents of the compound's vials that are sealed or in use (if none, the newest vial). Stock = remaining amount in those same vials. "Vials to buy" uses the newest vial's size and landed cost.

## Layout

```
app/
  main.py          app wiring, auth dependency, table creation at startup
  config.py        paths and env settings
  db.py            engine (WAL, foreign keys on), session
  models.py        SQLAlchemy tables
  units.py         unit parsing, conversion, formatting      (pure Python)
  calc.py          landed cost, inventory, protocol maths    (pure Python)
  services.py      ORM -> calc glue, upload handling, parsing helpers
  security.py      optional HTTP Basic auth
  templating.py    Jinja filters (money, amounts, unit cost)
  metrics.py       weight conversion, vitals validation and summaries (pure Python)
  charts.py        server-side SVG line charts with event overlays and bands (pure Python)
  labs.py          analyte naming, unit conversion, series building (pure Python)
  markup.py        safe markdown-style renderer for notes (pure Python)
  routers/         dashboard, compounds, purchases, vials, coas, doses, vitals, labs, protocols, pages
  templates/       Jinja + HTMX partials
  static/app.css
schema.sql         reference DDL
tests/             unit tests (units, calc, metrics, charts, markup, labs) and an end-to-end smoke test
deploy/            systemd unit, Caddyfile example
scripts/           fetch_vendor.sh (htmx), backup.sh
data/              SQLite DB and uploads (created at runtime, git-ignored)
```

## Run it (development)

Python 3.11+ recommended (3.10 works).

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
sh scripts/fetch_vendor.sh          # downloads htmx into app/static/vendor/
uvicorn app.main:app --reload       # http://127.0.0.1:8000
pytest                              # unit + smoke tests
```

The database file and tables are created on first start in `./data`.

## Deploy on a Linux server / Proxmox VM

```sh
sudo useradd --system --home /opt/tracker tracker
sudo mkdir -p /opt/tracker && sudo chown tracker: /opt/tracker
# copy the project into /opt/tracker, then as user tracker:
cd /opt/tracker
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sh scripts/fetch_vendor.sh

sudo cp .env.example /etc/tracker.env     # edit; set TRACKER_DATA_DIR=/opt/tracker/data
sudo chmod 600 /etc/tracker.env
sudo cp deploy/tracker.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tracker
```

The unit binds to `127.0.0.1:8000`. To reach it from other machines, put a reverse proxy in front (`deploy/Caddyfile.example`) or change `--host`.

### Security notes

This is health-adjacent data, so keep it off the open internet.

- Set `TRACKER_USER` and `TRACKER_PASS` to require HTTP Basic auth on every page. Basic auth is sent in clear text over plain HTTP, so use it with TLS (the Caddy example) or only on a trusted LAN/VPN (WireGuard, Tailscale).
- There is no CSRF token. With Basic auth and no cross-site cookies the risk is low for a LAN tool, but add one before exposing it more widely.
- Uploads (COAs and lab reports) are stored under random names, type-checked by extension and magic bytes, and served with `nosniff`. SVG and HTML are not accepted.
- Encrypt the VM disk or the data directory if the host is shared.

### Backups

`sh scripts/backup.sh /mnt/backups` writes a consistent SQLite copy (`.backup`, safe while running; needs the `sqlite3` CLI) and a tarball of the COA files. Back up both; the DB references the files.

## Notes pages: how links and safety work

- Text is HTML-escaped before formatting, so pasted HTML or scripts show as plain text. Only `http://` and `https://` links become clickable, and they open in a new tab with `noopener noreferrer nofollow`.
- The app never fetches a link itself (no title lookup, no page archiving). That avoids server-side requests from your VM and keeps what you read private. Paste the title and author yourself.
- Renaming a page does not rewrite `[[links]]` that point to it; those show in red as missing until you update them.
- Keep quotes short and paraphrase in your own words; the source field is there so you can find the original again.

## Known limits of this milestone

- Times are stored as naive local time of the server; set the VM timezone.
- No migrations yet: the schema is created with `create_all`. Add Alembic before changing columns on a database you care about.
- Edit forms exist for purchases and vials; compounds and log entries are add/delete only.
- Protocol math treats stock as a pool per compound and ignores expiry and beyond-use dates.
- A vial's measurement dimension (mass vs IU) can't be changed after creation.
- Vitals and sources can be added and deleted but not edited; pages can be edited.
- Lab reports can be added and deleted, and results added to or removed from a report, but a report's header (date, lab) can't be edited yet.
- Vial events use dates the app already has: it doesn't store a separate "finished on" date, so F is the last logged use.
- Lab unit conversion covers only the analytes listed above.

## Ideas for the next milestone

Editing lab report headers, full-text search (SQLite FTS5), CSV export, vial beyond-use reminders, edit log entries, per-vial price history, multi-compound blends, Alembic migrations.

## Inventory extension (October 2026)

New navigation pages: **Supplies** for BAC water (mL) and pills/capsules (counts), and
**COAs** for assigning a certificate to multiple existing vials of the same compound.

On a purchase detail page, choose individual vials, 5-vial half kits, or 10-vial full kits.
Kit purchases create individual vial rows with a common kit reference. The entered
price remains **per vial**, not per kit. Cap color is stored per vial.

Create a COA on a vial detail page with or without an attachment. To reuse the COA,
open the COAs page and select the other vial IDs. A COA's original vial cannot be
deleted while the COA is shared. Manual COAs use an internal metadata placeholder;
no fake document is created. Endotoxin is currently recorded as a **percentage**;
check your lab's reporting units before entering a value.

For powder vials, the reconstitution calculator displays mathematical conversions
between vial mg, diluent mL, mg/mL, and mg dose. Recording reconstitution can debit
an existing BAC water supply. This calculator is not a dosing recommendation.

Existing SQLite databases receive additive columns automatically on startup. **Back
up your data directory before upgrading**. Do not deploy over a running older
instance using the same SQLite database. Test in a copy of the database first.

Run the tests using:

```bash
TRACKER_WEIGHT_UNIT=kg PYTHONPATH=. pytest -q
```

Current limitations: pill consumption is tracked as supply usage, not as an entry in
the injectable dose log; COA bulk selection supports individual vial IDs rather than
one-click kit selection; and reconstitution editing does not automatically reverse
previous BAC-water deductions. The vial calculator requires mass in mg, not IU.

## PK Simulator (exploratory)

The `/pk` page plots modeled mg-equivalent exposure from **actual dose logs** for supported
GLP-1 drugs and testosterone esters. It also supports saved, independently editable
hypothetical future dosing scenarios. Scenario entries do **not** change dose logs,
inventory, or protocols. Supported names: tirzepatide, semaglutide, retatrutide,
testosterone cypionate, and testosterone enanthate (case-insensitive exact match).

The model is one-compartment first-order absorption and elimination. Half-lives are
editable *illustrative defaults*, not patient-specific measurements. It does not
estimate serum ng/dL, measured plasma mg/L, hormone response, or clinical effect.
Testosterone ester release is more complex than this approximation; retatrutide is
investigational. Only logged administrations of mass-based vials are modeled.

Existing databases gain `pk_scenarios` and `pk_planned_doses` via SQLAlchemy
`create_all` at startup. No destructive migrations are required. Back up your
SQLite database and `data/` directory before deployment.
