"""
logic.py
------------------------------------------------------------
All non-UI logic for the ITGC User Access & Change Management
Audit Dashboard: running the SQL control tests, scoring risk,
building CCCER-style findings, and persisting the review
workflow (status / management response / due date) back to
SQLite.

Kept separate from app.py (the Streamlit UI) so the audit logic
itself can be unit-tested with plain Python, independent of the
UI framework.
------------------------------------------------------------
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SQL_DIR = BASE_DIR / "sql"
DB_PATH = BASE_DIR / "audit.db"

# "As of" date for the audit test run. In a real engagement this
# would be the date the data extract was pulled from HR/IT.
AS_OF_DATE = "2026-09-25"
COMPANY_NAME = "Hankuk Motors America, Inc. (HMA)"

# ------------------------------------------------------------------
# Connection helpers
# ------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn = _ensure_core_tables_built(conn)
    _ensure_workflow_tables(conn)
    return conn


def _ensure_core_tables_built(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Safety net: if audit.db doesn't exist yet or is missing the core
    tables (e.g. this is a fresh checkout and init_db.py was never run),
    build it from the CSVs automatically instead of failing."""
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='employees'"
    ).fetchone()
    if exists:
        return conn

    conn.close()
    import init_db  # local import to avoid a hard dependency at module load time

    init_db.build()
    new_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    new_conn.row_factory = sqlite3.Row
    return new_conn


def _ensure_workflow_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS finding_reviews (
            finding_id            TEXT PRIMARY KEY,
            status                TEXT,
            management_response   TEXT,
            remediation_due_date  TEXT,
            reviewer              TEXT,
            last_updated          TEXT
        );

        CREATE TABLE IF NOT EXISTS review_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id    TEXT,
            field_changed TEXT,
            old_value     TEXT,
            new_value     TEXT,
            changed_by    TEXT,
            changed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            run_timestamp     TEXT,
            as_of_date        TEXT,
            total_exceptions  INTEGER,
            run_by            TEXT
        );
        """
    )
    conn.commit()


# ------------------------------------------------------------------
# SQL test execution
# ------------------------------------------------------------------

# Fixed run order -- this also fixes the Finding ID numbering (F-01, F-02, ...)
TEST_FILES = [
    ("terminated_active",  "01_terminated_user_active_account.sql"),
    ("dormant",            "02_dormant_accounts.sql"),
    ("excessive_privilege","03_excessive_privilege.sql"),
    ("sod_conflict",       "04_sod_conflicts.sql"),
    ("orphan_account",     "05_orphan_accounts.sql"),
    ("change_sod",         "06_change_management_sod.sql"),
    ("change_unapproved",  "07_unapproved_or_unreviewed_changes.sql"),
]

CATEGORY_LABELS = {
    "terminated_active":   "Terminated User With Active Account",
    "dormant":             "Dormant Account",
    "excessive_privilege": "Excessive Privilege",
    "sod_conflict":        "Segregation of Duties (SoD) Conflict",
    "orphan_account":      "Orphan Account",
    "change_sod":          "Change Management SoD Conflict (Developer = Approver)",
    "change_unapproved":   "Unapproved / Unreviewed Change",
}

CATEGORY_DOMAIN = {
    "terminated_active":   "Access Management",
    "dormant":             "Access Management",
    "excessive_privilege": "Access Management",
    "sod_conflict":        "Access Management",
    "orphan_account":      "Access Management",
    "change_sod":          "Change Management",
    "change_unapproved":   "Change Management",
}


def load_sql(filename: str) -> str:
    return (SQL_DIR / filename).read_text(encoding="utf-8")


def run_test(conn: sqlite3.Connection, filename: str) -> pd.DataFrame:
    sql = load_sql(filename)
    params = {"as_of_date": AS_OF_DATE} if ":as_of_date" in sql else None
    return pd.read_sql_query(sql, conn, params=params)


def run_all_tests(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    return {key: run_test(conn, fname) for key, fname in TEST_FILES}


# ------------------------------------------------------------------
# Risk scoring (Likelihood x Impact -> Low/Medium/High)
# Documented methodology also appears in docs/AUDIT_PROGRAM.md
# ------------------------------------------------------------------

def _rating(score: int) -> str:
    if score >= 6:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


def score_row(category: str, row: pd.Series) -> tuple[int, int, str]:
    """Return (likelihood 1-3, impact 1-3, rating) for one finding row."""
    system = str(row.get("system", "") or "")
    is_cloud = system == "AWS IAM Console"
    is_financial_system = system in ("SAP", "Payroll")
    unverified_owner = ("employee_name" in row and pd.isna(row.get("employee_name"))) or (
        "employee_id" in row and pd.isna(row.get("employee_id"))
    )

    if category == "terminated_active":
        # Evidence of a login on/after the termination date = confirmed usage, not just exposure
        likelihood = 3
        impact = 3
        return likelihood, impact, _rating(likelihood * impact)

    if category == "dormant":
        likelihood = 2
        impact = 3 if is_cloud else 2
        return likelihood, impact, _rating(likelihood * impact)

    if category == "excessive_privilege":
        likelihood = 3 if unverified_owner else 2
        impact = 3
        return likelihood, impact, _rating(likelihood * impact)

    if category == "sod_conflict":
        likelihood = 3 if unverified_owner else 2
        impact = 3 if is_financial_system else 2
        return likelihood, impact, _rating(likelihood * impact)

    if category == "orphan_account":
        likelihood = 2
        impact = 3 if (is_cloud or is_financial_system) else 2
        return likelihood, impact, _rating(likelihood * impact)

    if category == "change_sod":
        # a second/repeat instance in the population indicates a systemic gap, not a one-off
        likelihood = 2
        impact = 3
        return likelihood, impact, _rating(likelihood * impact)

    if category == "change_unapproved":
        likelihood = 3  # the change has already been deployed -- risk is realized, not potential
        impact = 3 if is_cloud else 3
        return likelihood, impact, _rating(likelihood * impact)

    return 2, 2, _rating(4)


# ------------------------------------------------------------------
# CCCER (Condition / Criteria / Cause / Effect / Recommendation)
# ------------------------------------------------------------------

CRITERIA_BY_CATEGORY = {
    "terminated_active": (
        "Company IT Access Management Policy Sec. 4.2 (timely revocation of access upon "
        "separation); ITGC - Access to Programs and Data under PCAOB AS 2201 / COSO Control "
        "Activities; corresponding IT control requirement under the Korean Internal Accounting "
        "Control System standard (K-ICFR, 내부회계관리제도 모범규준)."
    ),
    "dormant": (
        "Company IT Access Management Policy Sec. 4.5 (inactive account review); ITGC - "
        "Access to Programs and Data (periodic access recertification) under PCAOB AS 2201 / "
        "COSO Control Activities."
    ),
    "excessive_privilege": (
        "Least-privilege / role-based access principle per Company IT Access Management "
        "Policy Sec. 3.1; ITGC - Access to Programs and Data (appropriateness of access) "
        "under PCAOB AS 2201 / COSO Control Activities."
    ),
    "sod_conflict": (
        "Company Segregation of Duties Policy and SoD conflict matrix; ITGC - Access to "
        "Programs and Data under PCAOB AS 2201 / COSO Control Activities."
    ),
    "orphan_account": (
        "Company IT Access Management Policy Sec. 4.1 (all accounts must map to an approved "
        "owner); ITGC - Access to Programs and Data under PCAOB AS 2201 / COSO Control "
        "Activities."
    ),
    "change_sod": (
        "Company Change Management Policy Sec. 5.3 (independent approval required before "
        "deployment); ITGC - Program Change Management under PCAOB AS 2201 / COSO Control "
        "Activities."
    ),
    "change_unapproved": (
        "Company Change Management Policy Sec. 5.1-5.2 (approval required prior to "
        "deployment; emergency changes require post-implementation review); ITGC - Program "
        "Change Management under PCAOB AS 2201 / COSO Control Activities."
    ),
}

CAUSE_BY_CATEGORY = {
    "terminated_active": (
        "HR termination notifications and IT account deactivation are not reconciled on a "
        "recurring schedule; deactivation currently depends on an informal, manual request "
        "from the employee's manager."
    ),
    "dormant": (
        "No automated job disables accounts after a defined period of inactivity; account "
        "review is performed only when prompted by an unrelated event."
    ),
    "excessive_privilege": (
        "Administrative roles were granted for a one-time project or migration need and were "
        "not revoked afterward; no periodic recertification of privileged access is performed."
    ),
    "sod_conflict": (
        "Role assignment is handled ad hoc by system owners without checking new grants "
        "against the SoD conflict matrix before provisioning."
    ),
    "orphan_account": (
        "Contractor/legacy accounts are not consistently removed from the system when the "
        "underlying HR or vendor record is closed, and the account provisioning process does "
        "not validate the Employee ID against the HR master file."
    ),
    "change_sod": (
        "The change management tool does not technically prevent a developer from being "
        "selected as their own approver, and this is not caught by a compensating manual "
        "review."
    ),
    "change_unapproved": (
        "Deployment is not technically gated on a completed and recorded approval step, and "
        "emergency-change procedures do not include a mandatory, tracked post-implementation "
        "review."
    ),
}

EFFECT_BY_CATEGORY = {
    "terminated_active": (
        "A former employee (or anyone using their credentials) can access company systems, "
        "financial data, or customer/employee PII after their employment has ended, creating "
        "risk of data theft, fraud, or unauthorized transactions that would not be attributable "
        "to a current employee."
    ),
    "dormant": (
        "An unused but active account is a higher-value target for credential compromise, "
        "since activity on it is less likely to be noticed by the nominal owner or their "
        "manager."
    ),
    "excessive_privilege": (
        "The user can make unauthorized configuration or data changes, or access sensitive "
        "data outside the scope of their job duties, without another control layer in place."
    ),
    "sod_conflict": (
        "A single individual can both initiate and approve the same transaction end-to-end "
        "(e.g., create a vendor and approve payment to it), allowing error or fraud to occur "
        "and go undetected by a second party."
    ),
    "orphan_account": (
        "Activity performed under the account cannot be attributed to any accountable "
        "individual, defeating the purpose of user-level access logging and monitoring."
    ),
    "change_sod": (
        "Unauthorized, untested, or erroneous code can be approved and deployed to a "
        "production financial system without independent review."
    ),
    "change_unapproved": (
        "Changes reach production without evidence that they were authorized, increasing the "
        "risk of unintended or unauthorized functionality being introduced into financially "
        "relevant systems."
    ),
}

RECOMMENDATION_BY_CATEGORY = {
    "terminated_active": (
        "Disable the account immediately. Implement a recurring (at minimum weekly) "
        "reconciliation between the HR termination report and active accounts across all "
        "in-scope systems, with IT confirming deactivation within 24 hours of separation."
    ),
    "dormant": (
        "Confirm business need with the account owner's manager; disable if no longer "
        "required. Configure automatic disablement for any account inactive for 90+ days, "
        "with a report to the system owner before the account is disabled."
    ),
    "excessive_privilege": (
        "Remove the administrative role if not required for the employee's current job "
        "duties. Implement a quarterly access recertification for all roles containing "
        "administrative or elevated privileges."
    ),
    "sod_conflict": (
        "Remove one of the conflicting roles from the user, or implement a documented "
        "compensating control (e.g., an independent monthly review of all transactions this "
        "user both created and approved) if business constraints prevent full separation."
    ),
    "orphan_account": (
        "Identify the account owner; if none can be confirmed, disable and remove the "
        "account. Add a validation step to the provisioning process that rejects any account "
        "request whose Employee ID does not exist in the HR master file."
    ),
    "change_sod": (
        "Reassign approval of this change to someone other than the developer, and configure "
        "the change management tool to technically block a developer from approving their own "
        "change request."
    ),
    "change_unapproved": (
        "Document retroactive approval and assess whether the deployed change should be "
        "reviewed or reverted. Configure the deployment pipeline to require a recorded "
        "approval before code can be promoted to production, and make post-implementation "
        "review a mandatory, tracked step for all emergency changes."
    ),
}


def condition_text(category: str, row: pd.Series) -> str:
    r = row.to_dict()
    if category == "terminated_active":
        return (
            f"{r.get('employee_name')} ({r.get('employee_id')}, {r.get('job_title')}, "
            f"{r.get('department')}) was terminated effective {r.get('termination_date')}, "
            f"but user account {r.get('user_id')} on {r.get('system')} remained in "
            f"'{r.get('account_status')}' status with a last login of {r.get('last_login')}."
        )
    if category == "dormant":
        return (
            f"Account {r.get('user_id')} ({r.get('employee_name')}, {r.get('department')}) on "
            f"{r.get('system')} is Active but has not been used in "
            f"{r.get('days_since_last_login')} days (last login {r.get('last_login')}), "
            f"exceeding the 90-day inactivity threshold."
        )
    if category == "excessive_privilege":
        owner = r.get("employee_name") or "an account with no matching HR record"
        return (
            f"User {r.get('user_id')} ({owner}, department: {r.get('department') or 'Unknown'}"
            f", title: {r.get('job_title') or 'N/A'}) holds the '{r.get('role')}' "
            f"administrative role on {r.get('system')}, which is outside the scope of their "
            f"job function."
        )
    if category == "sod_conflict":
        owner = r.get("employee_name") or "an account with no matching HR record"
        return (
            f"User {r.get('user_id')} ({owner}) holds both '{r.get('conflicting_role_1')}' and "
            f"'{r.get('conflicting_role_2')}' on {r.get('system')}, a combination defined as a "
            f"segregation-of-duties conflict: {r.get('risk_description')}."
        )
    if category == "orphan_account":
        return (
            f"Account {r.get('user_id')} on {r.get('system')} is linked to Employee ID "
            f"'{r.get('employee_id_on_account')}', which does not exist in the current HR "
            f"employee master file, and the account is {r.get('account_status')}."
        )
    if category == "change_sod":
        return (
            f"Change {r.get('change_id')} on {r.get('system')} ('{r.get('description')}') was "
            f"both developed and approved by the same individual, {r.get('developer')}, before "
            f"deployment on {r.get('deployment_date')}."
        )
    if category == "change_unapproved":
        return (
            f"Change {r.get('change_id')} on {r.get('system')} ('{r.get('description')}') was "
            f"deployed on {r.get('deployment_date')}. {r.get('exception_reason')} "
            f"(approver on record: {r.get('approved_by') or 'None'}; approval date: "
            f"{r.get('approval_date') or 'None'}; reviewer on record: "
            f"{r.get('reviewed_by') or 'None'})."
        )
    return "N/A"


# ------------------------------------------------------------------
# Assemble the unified findings register
# ------------------------------------------------------------------

def _entity_label(category: str, row: pd.Series) -> str:
    if category in ("change_sod", "change_unapproved"):
        return str(row.get("change_id"))
    name = row.get("employee_name") if "employee_name" in row else None
    if pd.isna(name) if name is not None else True:
        eid = row.get("employee_id") or row.get("employee_id_on_account") or "Unknown"
        return f"Unmatched Employee ID {eid} (User {row.get('user_id')})"
    return f"{name} ({row.get('user_id')})"


def build_findings(conn: sqlite3.Connection) -> pd.DataFrame:
    results = run_all_tests(conn)
    records = []
    seq = 0
    for category, _ in TEST_FILES:
        df = results[category]
        for _, row in df.iterrows():
            seq += 1
            finding_id = f"F-{seq:02d}"
            likelihood, impact, rating = score_row(category, row)
            records.append(
                {
                    "finding_id": finding_id,
                    "category": category,
                    "category_label": CATEGORY_LABELS[category],
                    "domain": CATEGORY_DOMAIN[category],
                    "entity": _entity_label(category, row),
                    "system": row.get("system"),
                    "likelihood": likelihood,
                    "impact": impact,
                    "risk_score": likelihood * impact,
                    "severity": rating,
                    "condition": condition_text(category, row),
                    "criteria": CRITERIA_BY_CATEGORY[category],
                    "cause": CAUSE_BY_CATEGORY[category],
                    "effect": EFFECT_BY_CATEGORY[category],
                    "recommendation": RECOMMENDATION_BY_CATEGORY[category],
                }
            )
    return pd.DataFrame.from_records(records)


# ------------------------------------------------------------------
# Review workflow persistence (Status / Management Response / Due Date)
# ------------------------------------------------------------------

# A handful of findings are seeded with a non-default status/response so the
# dashboard demonstrates a real lifecycle rather than "everything is Open".
SEEDED_REVIEWS = {
    "F-02": {
        "status": "Remediated",
        "management_response": (
            "Account disabled 2026-09-20 upon audit notification. HR/IT offboarding checklist "
            "updated to require an IT deactivation ticket within 24 hours of the termination "
            "effective date."
        ),
        "remediation_due_date": "2026-09-20",
        "reviewer": "IT Audit - Access & Change Management",
    },
    "F-01": {
        "status": "In Remediation",
        "management_response": (
            "IT confirmed the account will be disabled by 2026-10-05. Reviewing SAP change "
            "logs to determine whether any activity occurred between the termination date and "
            "deactivation."
        ),
        "remediation_due_date": "2026-10-05",
        "reviewer": "IT Audit - Access & Change Management",
    },
}


def _default_due_date(severity: str) -> str:
    days = {"High": 30, "Medium": 60, "Low": 90}.get(severity, 60)
    due = datetime.strptime(AS_OF_DATE, "%Y-%m-%d") + timedelta(days=days)
    return due.strftime("%Y-%m-%d")


def ensure_review_rows(conn: sqlite3.Connection, findings_df: pd.DataFrame) -> None:
    """Insert a default review row for any finding that doesn't have one yet."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    for _, f in findings_df.iterrows():
        fid = f["finding_id"]
        existing = cur.execute(
            "SELECT 1 FROM finding_reviews WHERE finding_id = ?", (fid,)
        ).fetchone()
        if existing:
            continue
        seed = SEEDED_REVIEWS.get(fid)
        if seed:
            status = seed["status"]
            mgmt = seed["management_response"]
            due = seed["remediation_due_date"]
            reviewer = seed["reviewer"]
        else:
            status = "Open"
            mgmt = ""
            due = _default_due_date(f["severity"])
            reviewer = "IT Audit - Access & Change Management"
        cur.execute(
            "INSERT INTO finding_reviews VALUES (?,?,?,?,?,?)",
            (fid, status, mgmt, due, reviewer, now),
        )
    conn.commit()


def get_findings_with_status(conn: sqlite3.Connection) -> pd.DataFrame:
    findings = build_findings(conn)
    ensure_review_rows(conn, findings)
    reviews = pd.read_sql_query("SELECT * FROM finding_reviews", conn)
    merged = findings.merge(reviews, on="finding_id", how="left")
    return merged


def update_finding_review(
    conn: sqlite3.Connection,
    finding_id: str,
    status: str,
    management_response: str,
    remediation_due_date: str,
    reviewer: str,
    changed_by: str = "IT Audit Analyst (Preparer)",
) -> None:
    cur = conn.cursor()
    old = cur.execute(
        "SELECT status, management_response, remediation_due_date, reviewer "
        "FROM finding_reviews WHERE finding_id = ?",
        (finding_id,),
    ).fetchone()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute(
        """UPDATE finding_reviews
           SET status = ?, management_response = ?, remediation_due_date = ?,
               reviewer = ?, last_updated = ?
           WHERE finding_id = ?""",
        (status, management_response, remediation_due_date, reviewer, now, finding_id),
    )

    if old is not None:
        fields = [
            ("status", old["status"], status),
            ("management_response", old["management_response"], management_response),
            ("remediation_due_date", old["remediation_due_date"], remediation_due_date),
            ("reviewer", old["reviewer"], reviewer),
        ]
        for field, old_val, new_val in fields:
            if (old_val or "") != (new_val or ""):
                cur.execute(
                    """INSERT INTO review_history
                       (finding_id, field_changed, old_value, new_value, changed_by, changed_at)
                       VALUES (?,?,?,?,?,?)""",
                    (finding_id, field, old_val, new_val, changed_by, now),
                )
    conn.commit()


def get_review_history(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT * FROM review_history ORDER BY changed_at DESC", conn
    )


def log_test_run(conn: sqlite3.Connection, total_exceptions: int, run_by: str) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO audit_log (run_timestamp, as_of_date, total_exceptions, run_by) "
        "VALUES (?,?,?,?)",
        (now, AS_OF_DATE, total_exceptions, run_by),
    )
    conn.commit()


def get_audit_log(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM audit_log ORDER BY id DESC", conn)


# ------------------------------------------------------------------
# Dashboard metrics
# ------------------------------------------------------------------

def dashboard_metrics(conn: sqlite3.Connection, findings_df: pd.DataFrame) -> dict:
    employees = pd.read_sql_query("SELECT * FROM employees", conn)
    accounts = pd.read_sql_query("SELECT * FROM user_accounts", conn)
    roles = pd.read_sql_query("SELECT * FROM user_roles", conn)

    admin_users = roles[roles["role"].str.contains("Admin", na=False)]["user_id"].nunique()

    return {
        "total_employees": len(employees),
        "active_accounts": int((accounts["account_status"] == "Active").sum()),
        "terminated_active_count": len(
            findings_df[findings_df["category"] == "terminated_active"]
        ),
        "dormant_count": len(findings_df[findings_df["category"] == "dormant"]),
        "admin_account_count": int(admin_users),
        "sod_conflict_count": len(findings_df[findings_df["category"] == "sod_conflict"]),
        "orphan_count": len(findings_df[findings_df["category"] == "orphan_account"]),
        "change_finding_count": len(
            findings_df[findings_df["domain"] == "Change Management"]
        ),
        "total_findings": len(findings_df),
        "high": int((findings_df["severity"] == "High").sum()),
        "medium": int((findings_df["severity"] == "Medium").sum()),
        "low": int((findings_df["severity"] == "Low").sum()),
    }


# ------------------------------------------------------------------
# Risk and Control Matrix (shared by the Streamlit page and the xlsx export)
# ------------------------------------------------------------------

RISK_CONTROL_MATRIX = [
    {
        "Domain": "Access Management",
        "Risk": "Unauthorized access by a terminated employee",
        "Control Objective": "Access is removed in a timely manner when employment ends",
        "Control Activity": "HR sends termination notice to IT; IT disables all system accounts within 24 hours",
        "Control Type": "Detective / Preventive",
        "Frequency": "Per termination event; reconciled weekly",
        "Test Procedure": "Compare the HR termination report to the active-account list across all in-scope systems for the period",
        "SQL Test": "01_terminated_user_active_account.sql",
        "Framework Mapping": "PCAOB AS 2201 / COSO - Access to Programs and Data; K-ICFR IT control standard",
    },
    {
        "Domain": "Access Management",
        "Risk": "Unused active accounts are a target for compromise",
        "Control Objective": "Inactive accounts are identified and disabled",
        "Control Activity": "System owner reviews and disables accounts inactive for 90+ days",
        "Control Type": "Detective",
        "Frequency": "Quarterly",
        "Test Procedure": "Compute days since last login for all active accounts; flag those exceeding 90 days",
        "SQL Test": "02_dormant_accounts.sql",
        "Framework Mapping": "PCAOB AS 2201 / COSO - Access to Programs and Data",
    },
    {
        "Domain": "Access Management",
        "Risk": "Users hold privileges beyond what their role requires",
        "Control Objective": "Access is provisioned per the principle of least privilege",
        "Control Activity": "Administrative/elevated roles are recertified by system owners quarterly",
        "Control Type": "Detective / Preventive",
        "Frequency": "Quarterly",
        "Test Procedure": "Compare each user's assigned administrative role to their department/job title",
        "SQL Test": "03_excessive_privilege.sql",
        "Framework Mapping": "PCAOB AS 2201 / COSO - Access to Programs and Data",
    },
    {
        "Domain": "Access Management",
        "Risk": "One user can both initiate and approve the same transaction",
        "Control Objective": "Incompatible duties are segregated between different individuals",
        "Control Activity": "New role grants are checked against the SoD conflict matrix before provisioning",
        "Control Type": "Preventive",
        "Frequency": "At time of provisioning; tested quarterly",
        "Test Procedure": "Compare each user's role combination to the SoD rule library",
        "SQL Test": "04_sod_conflicts.sql",
        "Framework Mapping": "PCAOB AS 2201 / COSO - Access to Programs and Data",
    },
    {
        "Domain": "Access Management",
        "Risk": "Accounts exist with no identifiable, accountable owner",
        "Control Objective": "Every system account is traceable to an approved employee or service-account owner",
        "Control Activity": "Provisioning process validates the Employee ID against the HR master file before an account is created",
        "Control Type": "Preventive / Detective",
        "Frequency": "At provisioning; reconciled quarterly",
        "Test Procedure": "Compare the system account list to the HR employee master file for unmatched Employee IDs",
        "SQL Test": "05_orphan_accounts.sql",
        "Framework Mapping": "PCAOB AS 2201 / COSO - Access to Programs and Data",
    },
    {
        "Domain": "Change Management",
        "Risk": "A developer approves their own code change",
        "Control Objective": "Program changes are independently reviewed and approved before deployment",
        "Control Activity": "Change management tool requires an approver different from the developer",
        "Control Type": "Preventive",
        "Frequency": "Per change",
        "Test Procedure": "Compare the Developer and Approved By fields for every change request",
        "SQL Test": "06_change_management_sod.sql",
        "Framework Mapping": "PCAOB AS 2201 / COSO - Program Change Management",
    },
    {
        "Domain": "Change Management",
        "Risk": "Changes are deployed without documented approval or, for emergencies, without post-implementation review",
        "Control Objective": "All production changes are authorized, and emergency changes are independently reviewed after the fact",
        "Control Activity": "Deployment pipeline requires a recorded approval; emergency changes require a logged post-implementation review",
        "Control Type": "Preventive / Detective",
        "Frequency": "Per change",
        "Test Procedure": "Identify changes with no approver on record, deployed before their approval date, or emergency changes with no reviewer on record",
        "SQL Test": "07_unapproved_or_unreviewed_changes.sql",
        "Framework Mapping": "PCAOB AS 2201 / COSO - Program Change Management",
    },
]
