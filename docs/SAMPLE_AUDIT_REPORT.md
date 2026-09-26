# IT General Controls Audit Report (Sample)

**Company (fictional):** Hankuk Motors America, Inc. (HMA)
**Scope:** User Access Management & Program Change Management
**Systems in scope:** SAP, Payroll, Sales Cloud, AWS IAM Console
**Audit period:** January 1, 2026 – September 25, 2026
**Report date:** September 25, 2026
**Distribution:** CFO, IT Manager, Controller, Audit Committee (illustrative)

> ⚠️ This is a synthetic, illustrative audit report built from the results
> of a portfolio project. No real company, employee, or system is
> represented.

---

## Executive Summary

We performed a full-population test of user access and program change
controls across four in-scope systems using SQL-based control testing
against extracts from the HR system and each system owner. The testing
identified **18 exceptions across 7 control areas**, of which **15 were
rated High risk**. Two exceptions represent confirmed unauthorized access
(system logins recorded after the employee's termination date), and two
represent changes already deployed to a production financial or
infrastructure system without a complete, independently-approved change
record.

## Overall Conclusion

**Needs Improvement.** The design of the access-deprovisioning and
change-approval controls is reasonable, but operating effectiveness broke
down in specific, identifiable instances — most notably, evidence of actual
post-termination system access and two changes to SAP and AWS IAM Console
that reached production without a complete, independently-recorded approval.
No finding in this cycle indicated intentional fraud; all appear attributable
to manual, undocumented process steps rather than a compromised control
design.

## Findings Summary

| Severity | Count |
|---|---|
| High | 15 |
| Medium | 3 |
| Low | 0 |
| **Total** | **18** |

| Finding Type | Count | Domain |
|---|---|---|
| Terminated User With Active Account | 2 | Access Management |
| Dormant Account | 4 | Access Management |
| Excessive Privilege | 3 | Access Management |
| Segregation of Duties Conflict | 3 | Access Management |
| Orphan Account | 2 | Access Management |
| Change Management SoD Conflict | 2 | Change Management |
| Unapproved / Unreviewed Change | 2 | Change Management |

## High-Risk Findings (Selected)

**F-02 — Terminated User With Active Account (Payroll).** A former HR
Manager's Payroll account remained Active for approximately two months after
termination, with a recorded login nine weeks after the termination date.
*Status: Remediated* — account disabled and the HR/IT offboarding checklist
updated to require deactivation within 24 hours of separation.

**F-01 — Terminated User With Active Account (SAP).** A former Financial
Analyst's SAP account remained Active with a login three days after
termination. *Status: In Remediation.*

**F-07 / F-13 — Orphan Account with Cloud Administrator Privileges (AWS IAM
Console).** An active cloud administrator account has no corresponding
record in the HR employee master file, meaning its activity cannot currently
be attributed to any accountable individual. *Status: Open — highest
remediation priority given the combination of unverified ownership and
infrastructure-wide administrative rights.*

**F-15 — Change Management SoD Conflict, recurring pattern (SAP).** The same
developer both wrote and approved two separate SAP changes during the
period, including one that adjusted the three-way match tolerance threshold
— a change with direct financial-control impact. The recurrence across two
unrelated changes indicates a systemic gap rather than an isolated lapse.
*Status: Open.*

**F-17 — Unapproved Change (AWS IAM Console).** A new IAM role was deployed
to production with no approver recorded at all. *Status: Open.*

The full findings register, including Condition/Criteria/Cause/Effect/
Recommendation detail for all 18 findings, is available in the interactive
dashboard's Findings page and is generated directly from `logic.py` so it
always reflects the current state of the underlying data.

## Management Recommendations

1. Implement a recurring (at minimum weekly) automated reconciliation
   between HR termination notices and active accounts across all four
   systems, with a 24-hour SLA for deactivation.
2. Configure automatic disablement of accounts inactive for 90+ days,
   subject to a manager confirmation step.
3. Perform a quarterly recertification of every account holding an
   administrative role, and validate every account against the HR master
   file to eliminate orphan accounts.
4. Enforce, at the tool level, that a change's approver cannot be the same
   individual as its developer, and require a recorded, completed approval
   before a change can be promoted to production.
5. Require a mandatory, logged post-implementation review for every
   emergency change within 5 business days of deployment.

## Remediation Deadlines

| Finding(s) | Owner | Due Date |
|---|---|---|
| F-01 (terminated-active, SAP) | IT Manager | 2026-10-05 |
| F-07, F-13 (orphan cloud admin account) | IT Manager | 2026-10-25 |
| F-08, F-09 (excessive privilege) | IT Manager | 2026-10-25 |
| F-10, F-11, F-12 (SoD conflicts) | IT Manager / Controller | 2026-10-25 |
| F-15, F-16 (change management SoD) | IT Manager | 2026-10-25 |
| F-17, F-18 (unapproved/unreviewed changes) | IT Manager | 2026-10-25 |
| F-03 – F-06 (dormant accounts) | System Owners | 2026-11-24 |

*(Due dates follow the 30-day-High / 60-day-Medium convention documented in
`docs/AUDIT_PROGRAM.md`; F-02 is already Remediated and is excluded from this
table.)*

## Management Response

Management concurs with all findings and has committed to the remediation
dates above. See the "Management Response" field on each finding in the
dashboard's Findings page for finding-specific commentary.
