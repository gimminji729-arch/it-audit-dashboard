# Audit Program — ITGC User Access & Change Management Review

**Company (fictional):** Hankuk Motors America, Inc. (HMA)
**Audit period covered:** January 1, 2026 – September 25, 2026
**Data as-of date:** September 25, 2026
**Prepared by:** IT Audit Analyst (Preparer)
**Status:** Portfolio demonstration — all data synthetic

---

## 1. Audit Objective

To evaluate whether user access provisioning/deprovisioning and program
change management for in-scope financial and cloud-infrastructure systems
are designed and operating effectively to prevent unauthorized access and
unauthorized changes to financially relevant systems and data, in support of
ITGC requirements under PCAOB AS 2201 / COSO and the Korean Internal
Accounting Control System standard (K-ICFR).

## 2. Audit Scope

**In scope:**
- Logical access administration (provisioning, deprovisioning, privilege
  level, segregation of duties) for four systems: SAP, Payroll, Sales Cloud,
  and AWS IAM Console
- Program change management for the same four systems: request, development,
  review, approval, and deployment of changes

**Out of scope:**
- Application-level (business process) controls, such as three-way match
  configuration correctness or payroll calculation accuracy
- Physical/environmental controls, network security configuration, and data
  backup/recovery (Computer Operations ITGC domain)
- Program development / SDLC controls for net-new system builds

## 3. Population

| Population | Count | Source |
|---|---|---|
| Employees (HR master) | 25 | `data/Employees.csv` |
| System user accounts | 31 | `data/User_Accounts.csv` |
| Role/entitlement grants | 20 | `data/User_Roles.csv` |
| SoD conflict rules evaluated | 4 | `data/SoD_Rules.csv` |
| Change requests | 10 | `data/Change_Requests.csv` |

100% of each population was tested (no sampling), since the dataset is small
enough for a full population test — consistent with how SQL-based control
testing is typically used in practice to move from sample-based to
full-population testing.

## 4. Data Sources

Data was represented as extracts pulled directly from system owners /
HR on the as-of date above and loaded, unmodified, into a SQLite database
(`audit.db`) via `init_db.py`. No data was altered after extraction.

## 5. Test Procedures

| Test # | Control Tested | Procedure | Script |
|---|---|---|---|
| 1 | Timely deprovisioning on termination | Join the HR termination list to active system accounts by Employee ID; flag any active account for a terminated employee | `sql/01_terminated_user_active_account.sql` |
| 2 | Inactive-account monitoring | Compute days since last login for every active account; flag those exceeding 90 days | `sql/02_dormant_accounts.sql` |
| 3 | Least privilege | Identify accounts holding a role containing "Admin"; flag where the employee's department does not match the system's administrative function, or where no employee record exists | `sql/03_excessive_privilege.sql` |
| 4 | Segregation of duties | Compare each user's full set of roles per system against the SoD conflict rule library; flag any user holding both roles of a defined conflicting pair | `sql/04_sod_conflicts.sql` |
| 5 | Account/HR reconciliation | Compare all system account Employee IDs to the HR master file; flag accounts with no matching employee | `sql/05_orphan_accounts.sql` |
| 6 | Independent change approval | Compare the Developer and Approved By fields on every change request; flag where they match | `sql/06_change_management_sod.sql` |
| 7 | Change authorization & emergency review | Flag any change with no approver on record, a deployment date preceding its approval date, or an emergency change with no reviewer on record | `sql/07_unapproved_or_unreviewed_changes.sql` |

## 6. Exception Criteria

A record is an exception if it meets the `WHERE` condition of its test
script — see the script itself for the exact logic (each script is commented
with the risk, the control it tests, and the exact rule). There is no manual
judgment applied at the query level; judgment is applied afterward, when
assessing likelihood/impact and drafting the recommendation.

## 7. Risk Rating Methodology

Every finding is rated on two 1–3 scales and multiplied into a single risk
score, consistent with a standard qualitative risk matrix:

| Score | Likelihood | Impact |
|---|---|---|
| 1 | Unlikely — capability exists but no corroborating evidence of use | Low — non-financial system, limited blast radius |
| 2 | Possible — capability exists, plausible under normal conditions | Medium — supports a financial or infrastructure process but not directly transactional |
| 3 | Likely / Confirmed — evidence the exposure was actually used, or the negative event already occurred | High — directly affects financial reporting systems (SAP, Payroll) or infrastructure-wide cloud administration (AWS IAM Console) |

**Risk Score = Likelihood x Impact**, mapped to a rating:

| Risk Score | Rating |
|---|---|
| 1–2 | Low |
| 3–4 | Medium |
| 6–9 | High |

This methodology, and the specific likelihood/impact assignment logic per
finding type, is implemented in `logic.py::score_row()` so that the rating
shown in the dashboard is always reproducible from the same rules documented
here — not assigned ad hoc per finding.

**Why this population skews High:** all four in-scope systems are either
directly financial (SAP, Payroll) or infrastructure-wide (AWS IAM Console),
so Impact is rated High for most findings by design. Severity differentiates
mainly on Likelihood — for example, a terminated user with an actual
post-termination login is rated higher than a dormant account with no
evidence of misuse, even though both are High. A future test cycle that adds
lower-impact, non-financial systems (e.g., a ticketing tool) would be
expected to produce more Medium/Low findings.

## 8. Conclusion Criteria

- **Satisfactory:** No High-rated findings; Medium findings do not exceed
  [threshold set by engagement team, e.g., 5% of population]
- **Needs Improvement:** One or more High-rated findings, but no evidence of
  actual unauthorized activity
- **Unsatisfactory:** One or more High-rated findings with evidence of actual
  unauthorized access or an unauthorized change already in production

Based on this cycle's results (2 terminated-active accounts with login
activity after the termination date, and 2 unapproved/change-management
findings already deployed to production), this cycle's overall conclusion is
**Needs Improvement**, detailed further in `docs/SAMPLE_AUDIT_REPORT.md`.
