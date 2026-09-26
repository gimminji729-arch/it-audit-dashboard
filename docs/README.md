# ITGC User Access & Change Management Audit Dashboard

An IT audit portfolio project that tests a company's logical access and program
change controls using SQL, and tracks the resulting findings through a
Condition–Criteria–Cause–Effect–Recommendation (CCCER) workflow in an
interactive dashboard.

**⚠️ All company, employee, and data used in this project is synthetic.**
Hankuk Motors America, Inc. does not exist; it was created for demonstration
purposes only. No real company, employee, or system is represented.

---

## 1. Purpose

This project simulates an ITGC (IT General Controls) audit of the Access
Management and Change Management control domains — the two areas most
commonly tested in a SOX / internal audit / external audit ITGC walkthrough.
It was built to demonstrate, hands-on, the skills listed below rather than to
describe them abstractly.

| Resume skill | Where it shows up in this project |
|---|---|
| Risk Assessment | `logic.py::score_row()` — a documented Likelihood x Impact model rates every finding; methodology in `docs/AUDIT_PROGRAM.md` |
| Risk and Control Matrices (RCMs) | `docs/Risk_and_Control_Matrix.xlsx` and the in-app "Risk and Control Matrix" page, both generated from the same source (`logic.RISK_CONTROL_MATRIX`) |
| SQL-Based Control Testing | `/sql/*.sql` — seven control tests written as plain SQL against a SQLite database, independent of the UI |
| Segregation of Duties (SoD) | `sql/04_sod_conflicts.sql` and `sql/06_change_management_sod.sql`, tested against a configurable SoD rule library (`SoD_Rules.csv`) |
| Access and Change Management Controls | Five Access Management tests + two Change Management tests covering both ITGC domains |

## 2. Business Scenario

**Hankuk Motors America, Inc. (HMA)** is a fictional wholly-owned U.S.
subsidiary of a Korea-listed automotive manufacturer. HMA operates four
systems in scope for this audit:

| System | Function |
|---|---|
| SAP | ERP — finance, accounting, procurement |
| Payroll | Payroll processing |
| Sales Cloud | CRM / sales |
| AWS IAM Console | Cloud administration |

As the parent company is listed on the Korea Exchange, HMA's internal
controls are relevant to both **US SOX (PCAOB AS 2201 / COSO)** and the
**Korean Internal Accounting Control System standard (K-ICFR,
내부회계관리제도 모범규준)**, which imposes a parallel set of IT control
requirements. This project frames every finding against both, since a
US-based subsidiary of a Korean listed company must satisfy both regimes in
practice.

## 3. Frameworks & Standards Referenced

- **PCAOB Auditing Standard No. 2201 (AS 2201)** and the **COSO Internal
  Control – Integrated Framework** (Control Activities component) — the ITGC
  domains "Access to Programs and Data" and "Program Change Management"
- **내부회계관리제도 모범규준 (K-ICFR)** — the Korean SOX-equivalent standard
  applicable to the Korea-listed parent

## 4. Data Structure

Five CSV extracts simulate what an auditor would receive from HR and the
system owners, loaded into a SQLite database (`audit.db`) by `init_db.py`:

| File | Contents |
|---|---|
| `data/Employees.csv` | HR employee master (25 employees, incl. 3 terminated) |
| `data/User_Accounts.csv` | System accounts per employee across the 4 systems (31 accounts, incl. 2 unmatched/orphan) |
| `data/User_Roles.csv` | Role/entitlement grants per account |
| `data/SoD_Rules.csv` | Segregation-of-duties conflict rule library (4 rules) |
| `data/Change_Requests.csv` | Change management log (10 change requests) |

The dataset intentionally contains realistic exceptions **and** clean
contrast cases (e.g., a terminated employee whose account *was* properly
disabled) so the control tests can be shown to correctly distinguish a real
exception from a properly-controlled case, not just flag everything.

## 5. How to Run

```bash
pip install -r requirements.txt
python init_db.py      # builds audit.db from the CSVs
streamlit run app.py   # opens the dashboard in your browser
```

To inspect the audit logic directly, without the UI:

```bash
python init_db.py
sqlite3 audit.db < sql/01_terminated_user_active_account.sql
```

or open any file under `/sql` — each is a standalone, commented SQL script.

### Deploying a live demo

This app is a single `app.py` with no external services, so it deploys as-is
to [Streamlit Community Cloud](https://streamlit.io/cloud) for free: push
this folder to a public GitHub repo, connect it on share.streamlit.io, and
point it at `app.py`.

## 6. Controls & Risks Tested

| # | Finding Type | Domain | Risk |
|---|---|---|---|
| 1 | Terminated User With Active Account | Access Management | Unauthorized post-termination access |
| 2 | Dormant Account | Access Management | Unused active account is a target for compromise |
| 3 | Excessive Privilege | Access Management | Access beyond job function (least-privilege violation) |
| 4 | Segregation of Duties Conflict | Access Management | One person can both initiate and approve the same transaction |
| 5 | Orphan Account | Access Management | Account with no verifiable, accountable owner |
| 6 | Change Management SoD Conflict | Change Management | Developer approves their own change |
| 7 | Unapproved / Unreviewed Change | Change Management | Change deployed without approval or independent post-implementation review |

Full risk/control/test-procedure detail is in `docs/Risk_and_Control_Matrix.xlsx`
and `docs/AUDIT_PROGRAM.md`.

## 7. Application Structure

```
it-audit-dashboard/
├── data/                 CSV extracts (synthetic)
├── sql/                  7 standalone SQL control tests
├── docs/                 README, Audit Program, Sample Report, RCM.xlsx
├── init_db.py            builds audit.db from the CSVs
├── logic.py              audit logic: SQL execution, risk scoring, CCCER,
│                         review-workflow persistence (no UI code)
├── app.py                Streamlit UI only — imports logic.py
├── build_rcm_excel.py    generates docs/Risk_and_Control_Matrix.xlsx
└── requirements.txt
```

`logic.py` and `app.py` are deliberately separated: the audit logic can be
run, read, and tested with plain Python/SQL, independent of the dashboard
framework used to display it.

## 8. Project Limitations

This is a portfolio project, not a production audit tool. Known
simplifications, stated plainly:

- All data is synthetic and hand-authored to exercise each control test; it
  is not a live feed from a real HR/IT system.
- The SoD rule library and risk-scoring weights are illustrative; a real
  engagement would use the company's actual conflict matrix and a
  risk-ranking methodology approved by the audit committee/PCAOB engagement
  team.
- There is no authentication/role-based access on the dashboard itself — in
  a real deployment, access to audit workpapers and findings would itself be
  access-controlled (a nice illustration of why ITGC matters everywhere,
  including in the tools auditors use).
- "AI-assisted development" disclosure: this application was built with the
  assistance of an AI coding tool. The audit scenario, control logic, risk
  ratings, SQL test design, and documentation were authored and reviewed by
  the project owner; the AI tool was used to accelerate implementation.
