# Peptide & TRT Ledger

A single-user web app for keeping records of peptide and testosterone **inventory, purchases, COAs, logged doses and costs**, plus a what-if protocol calculator.

It is a recordkeeping tool. It does unit arithmetic on numbers you enter and never suggests, checks or optimizes doses. It does not know what a "normal" amount is for anything.

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
  routers/         dashboard, compounds, purchases, vials, coas, doses, protocols
  templates/       Jinja + HTMX partials
  static/app.css
schema.sql         reference DDL
tests/             unit tests (units, calc) and an end-to-end smoke test
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
useradd --system --home /opt/tracker tracker
mkdir -p /opt/tracker && chown -R tracker:tracker /opt/tracker
# copy the project into /opt/tracker, then as user tracker:
cd /opt/tracker
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sh scripts/fetch_vendor.sh

cp .env.example /etc/tracker.env     # edit; set TRACKER_DATA_DIR=/opt/tracker/data
chmod 600 /etc/tracker.env
cp deploy/tracker.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now tracker
```

The unit binds to `0.0.0.0:8000`. To reach it from other machines, put a reverse proxy in front (`deploy/Caddyfile.example`) or change `--host`.

### Security notes

This is health-adjacent data, so keep it off the open internet.

- Set `TRACKER_USER` and `TRACKER_PASS` to require HTTP Basic auth on every page. Basic auth is sent in clear text over plain HTTP, so use it with TLS (the Caddy example) or only on a trusted LAN/VPN (WireGuard, Tailscale).
- There is no CSRF token. With Basic auth and no cross-site cookies the risk is low for a LAN tool, but add one before exposing it more widely.
- Uploads are stored under random names, type-checked by extension and magic bytes, and served with `nosniff`. SVG and HTML are not accepted.
- Encrypt the VM disk or the data directory if the host is shared.

### Backups

`sh scripts/backup.sh /mnt/backups` writes a consistent SQLite copy (`.backup`, safe while running; needs the `sqlite3` CLI) and a tarball of the COA files. Back up both; the DB references the files.

## Known limits of this milestone

- Times are stored as naive local time of the server; set the VM timezone.
- No migrations yet: the schema is created with `create_all`. Add Alembic before changing columns on a database you care about.
- Edit forms exist for purchases and vials; compounds and log entries are add/delete only.
- Protocol math treats stock as a pool per compound and ignores expiry and beyond-use dates.
- A vial's measurement dimension (mass vs IU) can't be changed after creation.

## Ideas for the next milestone

Bloodwork/lab results and charts, CSV export, vial beyond-use reminders, edit log entries, per-vial price history, multi-compound blends, Alembic migrations.
