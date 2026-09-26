"""
init_db.py
------------------------------------------------------------
Builds the audit SQLite database (audit.db) from the raw CSV
extracts under /data. This mirrors how an IT auditor would
receive a data pull from HR and IT/System owners and load it
into a working database before running control tests.

Run:  python init_db.py
------------------------------------------------------------
"""
import csv
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "audit.db"

SCHEMA = """
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS user_accounts;
DROP TABLE IF EXISTS user_roles;
DROP TABLE IF EXISTS sod_rules;
DROP TABLE IF EXISTS change_requests;

CREATE TABLE employees (
    employee_id       TEXT PRIMARY KEY,
    name              TEXT,
    department        TEXT,
    job_title         TEXT,
    status            TEXT,
    hire_date         TEXT,
    termination_date  TEXT
);

CREATE TABLE user_accounts (
    user_id             TEXT PRIMARY KEY,
    employee_id         TEXT,
    system              TEXT,
    account_status      TEXT,
    last_login          TEXT,
    account_created_date TEXT
);

CREATE TABLE user_roles (
    user_id TEXT,
    role    TEXT,
    system  TEXT
);

CREATE TABLE sod_rules (
    role_1           TEXT,
    role_2           TEXT,
    risk_description TEXT,
    system           TEXT
);

CREATE TABLE change_requests (
    change_id        TEXT PRIMARY KEY,
    system           TEXT,
    description      TEXT,
    requested_by     TEXT,
    developer        TEXT,
    reviewed_by      TEXT,
    approved_by      TEXT,
    approval_date    TEXT,
    deployment_date  TEXT,
    emergency_change TEXT
);

-- Review workflow / evidence tables. logic.py fills in any finding that
-- isn't already seeded here the first time the app runs.
DROP TABLE IF EXISTS finding_reviews;
DROP TABLE IF EXISTS review_history;
DROP TABLE IF EXISTS audit_log;

CREATE TABLE finding_reviews (
    finding_id            TEXT PRIMARY KEY,
    status                TEXT,
    management_response   TEXT,
    remediation_due_date  TEXT,
    reviewer              TEXT,
    last_updated          TEXT
);

CREATE TABLE review_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id    TEXT,
    field_changed TEXT,
    old_value     TEXT,
    new_value     TEXT,
    changed_by    TEXT,
    changed_at    TEXT
);

CREATE TABLE audit_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp     TEXT,
    as_of_date        TEXT,
    total_exceptions  INTEGER,
    run_by            TEXT
);
"""

SEED_REVIEWS = [
    ("F-01", "In Remediation",
     "IT confirmed the account will be disabled by 2026-10-05. Reviewing SAP change logs to "
     "determine whether any activity occurred between the termination date and deactivation.",
     "2026-10-05", "IT Audit - Access & Change Management", "2026-09-25 10:00:00"),
    ("F-02", "Remediated",
     "Account disabled 2026-09-20 upon audit notification. HR/IT offboarding checklist updated "
     "to require an IT deactivation ticket within 24 hours of the termination effective date.",
     "2026-09-20", "IT Audit - Access & Change Management", "2026-09-20 09:30:00"),
]

SEED_HISTORY = [
    ("F-01", "status", "Open", "In Remediation",
     "IT Audit - Access & Change Management", "2026-09-25 10:00:00"),
    ("F-02", "status", "Open", "Remediated",
     "IT Audit - Access & Change Management", "2026-09-20 09:30:00"),
]

SEED_AUDIT_LOG = [
    ("2026-09-25 09:00:00", "2026-09-25", 18, "IT Audit Analyst (Preparer)"),
]

def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))[1:]  # skip header

def build():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    for row in load_csv(DATA_DIR / "Employees.csv"):
        cur.execute(
            "INSERT INTO employees VALUES (?,?,?,?,?,?,?)",
            [v if v != "" else None for v in row],
        )

    for row in load_csv(DATA_DIR / "User_Accounts.csv"):
        cur.execute(
            "INSERT INTO user_accounts VALUES (?,?,?,?,?,?)",
            [v if v != "" else None for v in row],
        )

    for row in load_csv(DATA_DIR / "User_Roles.csv"):
        cur.execute("INSERT INTO user_roles VALUES (?,?,?)", row)

    for row in load_csv(DATA_DIR / "SoD_Rules.csv"):
        cur.execute("INSERT INTO sod_rules VALUES (?,?,?,?)", row)

    for row in load_csv(DATA_DIR / "Change_Requests.csv"):
        cur.execute(
            "INSERT INTO change_requests VALUES (?,?,?,?,?,?,?,?,?,?)",
            [v if v != "" else None for v in row],
        )

    for row in SEED_REVIEWS:
        cur.execute("INSERT INTO finding_reviews VALUES (?,?,?,?,?,?)", row)

    for row in SEED_HISTORY:
        cur.execute(
            "INSERT INTO review_history (finding_id, field_changed, old_value, new_value, "
            "changed_by, changed_at) VALUES (?,?,?,?,?,?)",
            row,
        )

    for row in SEED_AUDIT_LOG:
        cur.execute(
            "INSERT INTO audit_log (run_timestamp, as_of_date, total_exceptions, run_by) "
            "VALUES (?,?,?,?)",
            row,
        )

    conn.commit()
    conn.close()
    print(f"audit.db built at {DB_PATH}")

if __name__ == "__main__":
    build()
