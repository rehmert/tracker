-- Reference schema (SQLite). The app creates these tables itself at startup via
-- SQLAlchemy `create_all`; this file documents the result and can bootstrap a DB:
--   sqlite3 data/tracker.db < schema.sql
-- Conventions: money = integer cents; vial amounts are stored as entered
-- (content_value + content_unit) and converted to base units (mcg or IU) in code;
-- dose_logs.amount_base is already in the vial's base unit (mcg or IU).
PRAGMA foreign_keys = ON;

CREATE TABLE compounds (
  id        INTEGER PRIMARY KEY,
  name      VARCHAR(120) NOT NULL UNIQUE,
  category  VARCHAR(30)  NOT NULL DEFAULT 'peptide',   -- peptide | testosterone | other
  notes     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE purchases (
  id              INTEGER PRIMARY KEY,
  vendor          VARCHAR(160) NOT NULL,
  purchased_on    DATE NOT NULL,
  order_ref       VARCHAR(120) NOT NULL DEFAULT '',
  shipping_cents  INTEGER NOT NULL DEFAULT 0,
  tax_cents       INTEGER NOT NULL DEFAULT 0,
  discount_cents  INTEGER NOT NULL DEFAULT 0,
  notes           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE vials (
  id                INTEGER PRIMARY KEY,
  compound_id       INTEGER NOT NULL REFERENCES compounds(id),
  purchase_id       INTEGER REFERENCES purchases(id),
  label             VARCHAR(160) NOT NULL DEFAULT '',
  lot               VARCHAR(80)  NOT NULL DEFAULT '',
  form              VARCHAR(20)  NOT NULL DEFAULT 'lyophilized',   -- lyophilized | solution
  content_value     FLOAT NOT NULL CHECK (content_value > 0),       -- label claim for the whole vial
  content_unit      VARCHAR(8) NOT NULL,                            -- mcg | mg | g | IU
  volume_ml         FLOAT CHECK (volume_ml IS NULL OR volume_ml > 0),
  reconstituted_on  DATE,
  expires_on        DATE,
  status            VARCHAR(12) NOT NULL DEFAULT 'sealed',          -- sealed | in_use | finished | discarded
  coa_id            INTEGER REFERENCES coas(id) ON DELETE SET NULL,
  use_coa_content   BOOLEAN NOT NULL DEFAULT 0,
  unit_price_cents  INTEGER NOT NULL DEFAULT 0,
  notes             TEXT NOT NULL DEFAULT '',
  created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_vials_compound ON vials(compound_id);
CREATE INDEX ix_vials_purchase ON vials(purchase_id);

CREATE TABLE coas (
  id                      INTEGER PRIMARY KEY,
  original_name           VARCHAR(255) NOT NULL,
  stored_name             VARCHAR(80)  UNIQUE,   -- random name under data/uploads/coa/
  content_type            VARCHAR(80)  NOT NULL,
  size_bytes              INTEGER NOT NULL,
  sha256                  VARCHAR(64)  NOT NULL,
  lab_name                VARCHAR(160) NOT NULL DEFAULT '',
  tested_on               DATE,
  purity_pct              FLOAT,
  endotoxin_pct           FLOAT,
  job_id                  VARCHAR(120) NOT NULL DEFAULT '',
  verify_code             VARCHAR(120) NOT NULL DEFAULT '',
  reported_content_value  FLOAT,
  reported_content_unit   VARCHAR(8),
  notes                   TEXT NOT NULL DEFAULT '',
  uploaded_at             DATETIME DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE dose_logs (
  id             INTEGER PRIMARY KEY,
  vial_id        INTEGER NOT NULL REFERENCES vials(id),
  taken_at       DATETIME NOT NULL,
  entered_value  FLOAT NOT NULL,
  entered_unit   VARCHAR(8) NOT NULL,
  amount_base    FLOAT NOT NULL,                          -- mcg or IU
  kind           VARCHAR(8) NOT NULL DEFAULT 'dose',      -- dose | waste
  site           VARCHAR(80) NOT NULL DEFAULT '',
  notes          TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_dose_logs_vial_time ON dose_logs(vial_id, taken_at);

CREATE TABLE protocols (
  id             INTEGER PRIMARY KEY,
  name           VARCHAR(160) NOT NULL,
  notes          TEXT NOT NULL DEFAULT '',
  horizon_weeks  FLOAT NOT NULL DEFAULT 12,
  created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE protocol_items (
  id           INTEGER PRIMARY KEY,
  protocol_id  INTEGER NOT NULL REFERENCES protocols(id) ON DELETE CASCADE,
  compound_id  INTEGER NOT NULL REFERENCES compounds(id),
  position     INTEGER NOT NULL DEFAULT 0,
  amount_value FLOAT NOT NULL,
  amount_unit  VARCHAR(8) NOT NULL,                       -- mcg | mg | g | IU | mL | uL
  freq_count   FLOAT NOT NULL,
  freq_period  VARCHAR(10) NOT NULL                       -- day | week | month | interval (= once every N days)
);

-- ---- vitals ----
CREATE TABLE vital_readings (
  id           INTEGER PRIMARY KEY,
  measured_at  DATETIME NOT NULL,
  weight_kg    FLOAT,                          -- always kg; shown in kg or lb per TRACKER_WEIGHT_UNIT
  systolic     INTEGER,
  diastolic    INTEGER,
  pulse_bpm    INTEGER,
  context      VARCHAR(80) NOT NULL DEFAULT '',
  notes        TEXT NOT NULL DEFAULT '',
  CONSTRAINT ck_reading_has_value CHECK (weight_kg IS NOT NULL OR systolic IS NOT NULL OR pulse_bpm IS NOT NULL)
);
CREATE INDEX ix_vital_readings_time ON vital_readings(measured_at);

-- ---- notes pages ----
CREATE TABLE pages (
  id          INTEGER PRIMARY KEY,
  title       VARCHAR(200) NOT NULL UNIQUE,
  body        TEXT NOT NULL DEFAULT '',        -- markdown-style text; [[Title]] links to other pages
  tags        VARCHAR(400) NOT NULL DEFAULT '',-- comma separated, lower case
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE page_compounds (
  page_id      INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  compound_id  INTEGER NOT NULL REFERENCES compounds(id) ON DELETE CASCADE,
  PRIMARY KEY (page_id, compound_id)
);

CREATE TABLE sources (
  id           INTEGER PRIMARY KEY,
  page_id      INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  kind         VARCHAR(10) NOT NULL DEFAULT 'web',   -- web | book | paper | other
  title        VARCHAR(300) NOT NULL DEFAULT '',
  url          VARCHAR(2000),                         -- http(s) only, validated on input
  author       VARCHAR(200) NOT NULL DEFAULT '',
  publication  VARCHAR(200) NOT NULL DEFAULT '',      -- site, journal or publisher
  location     VARCHAR(120) NOT NULL DEFAULT '',      -- chapter, page or DOI
  accessed_on  DATE,
  note         TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_sources_page ON sources(page_id);

-- ---- lab results ----
CREATE TABLE lab_reports (
  id             INTEGER PRIMARY KEY,
  drawn_on       DATE NOT NULL,
  lab_name       VARCHAR(160) NOT NULL DEFAULT '',
  notes          TEXT NOT NULL DEFAULT '',
  original_name  VARCHAR(255),                 -- optional copy of the report (data/uploads/labs/)
  stored_name    VARCHAR(80) UNIQUE,
  content_type   VARCHAR(80),
  size_bytes     INTEGER,
  sha256         VARCHAR(64),
  created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lab_results (
  id         INTEGER PRIMARY KEY,
  report_id  INTEGER NOT NULL REFERENCES lab_reports(id) ON DELETE CASCADE,
  analyte    VARCHAR(120) NOT NULL,
  value      FLOAT NOT NULL,
  unit       VARCHAR(30)  NOT NULL,            -- as printed on the report
  ref_low    FLOAT,                            -- range PRINTED on the report (both or neither)
  ref_high   FLOAT,
  note       VARCHAR(300) NOT NULL DEFAULT ''
);
CREATE INDEX ix_lab_results_report ON lab_results(report_id);
CREATE INDEX ix_lab_results_analyte ON lab_results(analyte);
