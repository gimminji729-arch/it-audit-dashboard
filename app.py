"""
app.py — ITGC User Access & Change Management Audit Dashboard
------------------------------------------------------------
Streamlit UI. All audit logic (SQL control tests, risk scoring,
CCCER findings, review workflow) lives in logic.py so it can be
tested independently of this UI layer. Run with:

    streamlit run app.py
------------------------------------------------------------
"""
from pathlib import Path

import pandas as pd
import streamlit as st

import logic

st.set_page_config(
    page_title="HMA ITGC Audit Dashboard",
    page_icon="🛡️",
    layout="wide",
)

SEVERITY_COLORS = {"High": "#DC2626", "Medium": "#D97706", "Low": "#16A34A"}
STATUS_COLORS = {
    "Open": "#DC2626",
    "In Remediation": "#D97706",
    "Remediated": "#16A34A",
    "Closed": "#6B7280",
}


def rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:  # pragma: no cover - older Streamlit versions
        st.experimental_rerun()


@st.cache_resource
def get_conn():
    return logic.get_connection()


def badge(text: str, color: str) -> str:
    return (
        f"<span style='background:{color}20;color:{color};border:1px solid {color};"
        f"padding:2px 10px;border-radius:999px;font-size:0.85em;font-weight:600'>{text}</span>"
    )


def style_findings_table(df: pd.DataFrame, severity_col="Severity", status_col="Status"):
    def color_severity(val):
        c = SEVERITY_COLORS.get(val, "#000")
        return f"color:{c}; font-weight:600"

    def color_status(val):
        c = STATUS_COLORS.get(val, "#000")
        return f"color:{c}; font-weight:600"

    styler = df.style
    if severity_col in df.columns:
        styler = styler.map(color_severity, subset=[severity_col])
    if status_col in df.columns:
        styler = styler.map(color_status, subset=[status_col])
    return styler


# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------
conn = get_conn()

st.sidebar.markdown(f"### 🛡️ {logic.COMPANY_NAME}")
st.sidebar.caption("ITGC User Access & Change Management Audit")
st.sidebar.caption(f"Data as of: **{logic.AS_OF_DATE}**")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Findings", "Risk and Control Matrix", "Evidence and Audit Trail", "About / README"],
)

st.sidebar.divider()
if st.sidebar.button("▶ Re-run control tests", use_container_width=True):
    findings_tmp = logic.build_findings(conn)
    logic.log_test_run(conn, len(findings_tmp), "IT Audit Analyst (Preparer)")
    st.sidebar.success(f"Logged a new test run ({len(findings_tmp)} exceptions).")
    rerun()

st.sidebar.info(
    "⚠️ All company, employee, and system data in this project is **synthetic** and was "
    "created for portfolio demonstration purposes only.",
    icon="⚠️",
)

findings = logic.get_findings_with_status(conn)
metrics = logic.dashboard_metrics(conn, findings)

# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
if page == "Dashboard":
    st.title("ITGC User Access & Change Management Audit Dashboard")
    st.caption(
        f"{logic.COMPANY_NAME} — Access Management (SAP, Payroll, Sales Cloud, AWS IAM Console) "
        "and Change Management controls"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Employees", metrics["total_employees"])
    c2.metric("Active Accounts", metrics["active_accounts"])
    c3.metric("Admin-Level Accounts", metrics["admin_account_count"])
    c4.metric("Total Findings", metrics["total_findings"])

    st.markdown("#### Access Management Exceptions")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Terminated User, Active Account", metrics["terminated_active_count"])
    a2.metric("Dormant Accounts (90+ days)", metrics["dormant_count"])
    a3.metric("SoD Conflicts", metrics["sod_conflict_count"])
    a4.metric("Orphan Accounts", metrics["orphan_count"])

    st.markdown("#### Change Management Exceptions")
    st.metric("Change Management Findings", metrics["change_finding_count"])

    st.markdown("#### Findings by Risk Severity")
    s1, s2, s3 = st.columns(3)
    for col, sev in zip((s1, s2, s3), ("High", "Medium", "Low")):
        color = SEVERITY_COLORS[sev]
        count = metrics[sev.lower()]
        col.markdown(
            f"""
            <div style='border:1px solid {color}40;border-left:6px solid {color};
                        border-radius:8px;padding:14px 18px;background:{color}10'>
                <div style='font-size:0.85em;color:{color};font-weight:700'>{sev.upper()} RISK</div>
                <div style='font-size:2em;font-weight:700;color:{color}'>{count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### Findings by Category")
    cat_summary = (
        findings.groupby(["domain", "category_label"])
        .size()
        .reset_index(name="Count")
        .rename(columns={"domain": "Domain", "category_label": "Finding Type"})
        .sort_values("Count", ascending=False)
    )
    st.dataframe(cat_summary, hide_index=True, use_container_width=True)

    st.markdown("#### Remediation Status")
    status_summary = findings["status"].value_counts().reset_index()
    status_summary.columns = ["Status", "Count"]
    st.dataframe(status_summary, hide_index=True, use_container_width=True)

# ------------------------------------------------------------------
# Findings
# ------------------------------------------------------------------
elif page == "Findings":
    st.title("Findings Register")

    f1, f2, f3 = st.columns(3)
    domain_filter = f1.multiselect(
        "Domain", sorted(findings["domain"].unique()), default=list(findings["domain"].unique())
    )
    severity_filter = f2.multiselect(
        "Severity", ["High", "Medium", "Low"], default=["High", "Medium", "Low"]
    )
    status_filter = f3.multiselect(
        "Status", sorted(findings["status"].unique()), default=list(findings["status"].unique())
    )

    filtered = findings[
        findings["domain"].isin(domain_filter)
        & findings["severity"].isin(severity_filter)
        & findings["status"].isin(status_filter)
    ]

    display_cols = {
        "finding_id": "Finding ID",
        "category_label": "Finding",
        "entity": "User / Entity",
        "system": "System",
        "severity": "Severity",
        "status": "Status",
        "remediation_due_date": "Due Date",
    }
    table = filtered[list(display_cols.keys())].rename(columns=display_cols)
    st.dataframe(
        style_findings_table(table),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(f"Showing {len(filtered)} of {len(findings)} findings.")

    st.divider()
    st.subheader("Finding Detail")
    if filtered.empty:
        st.info("No findings match the current filters.")
    else:
        options = filtered["finding_id"] + " — " + filtered["category_label"] + " (" + filtered["entity"] + ")"
        choice = st.selectbox("Select a finding to review", options)
        finding_id = choice.split(" — ")[0]
        row = findings[findings["finding_id"] == finding_id].iloc[0]

        st.markdown(
            f"### {row['finding_id']} — {row['category_label']}  "
            f"{badge(row['severity'], SEVERITY_COLORS[row['severity']])} "
            f"{badge(row['status'], STATUS_COLORS.get(row['status'], '#6B7280'))}",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Domain: {row['domain']} | Entity: {row['entity']} | System: {row['system']} | "
            f"Likelihood: {row['likelihood']}/3 | Impact: {row['impact']}/3 | "
            f"Risk Score: {row['risk_score']}/9"
        )

        st.markdown(f"**Condition**  \n{row['condition']}")
        st.markdown(f"**Criteria**  \n{row['criteria']}")
        st.markdown(f"**Cause**  \n{row['cause']}")
        st.markdown(f"**Effect / Risk**  \n{row['effect']}")
        st.markdown(f"**Recommendation**  \n{row['recommendation']}")

        st.divider()
        st.markdown("#### Management Response & Remediation Tracking")
        with st.form(f"review_form_{finding_id}"):
            status_options = ["Open", "In Remediation", "Remediated", "Closed"]
            new_status = st.selectbox(
                "Finding Status", status_options, index=status_options.index(row["status"])
                if row["status"] in status_options else 0,
            )
            new_response = st.text_area("Management Response", value=row["management_response"] or "")
            new_due = st.text_input(
                "Remediation Due Date (YYYY-MM-DD)", value=row["remediation_due_date"] or ""
            )
            new_reviewer = st.text_input("Reviewer", value=row["reviewer"] or "")
            submitted = st.form_submit_button("💾 Save review")
            if submitted:
                logic.update_finding_review(
                    conn, finding_id, new_status, new_response, new_due, new_reviewer
                )
                st.success("Saved. This change was also logged to the audit trail below.")
                rerun()

# ------------------------------------------------------------------
# Risk and Control Matrix
# ------------------------------------------------------------------
elif page == "Risk and Control Matrix":
    st.title("Risk and Control Matrix (RCM)")
    st.caption(
        "Each row links a risk to its control objective, the control activity in place, "
        "the audit test procedure performed, the SQL script that performs it, and the "
        "control framework it maps to."
    )
    rcm_df = pd.DataFrame(logic.RISK_CONTROL_MATRIX)
    for domain in rcm_df["Domain"].unique():
        st.markdown(f"#### {domain}")
        st.dataframe(
            rcm_df[rcm_df["Domain"] == domain].drop(columns=["Domain"]),
            hide_index=True,
            use_container_width=True,
        )

    xlsx_path = Path(__file__).parent / "docs" / "Risk_and_Control_Matrix.xlsx"
    if xlsx_path.exists():
        st.download_button(
            "⬇ Download Risk and Control Matrix (.xlsx)",
            data=xlsx_path.read_bytes(),
            file_name="Risk_and_Control_Matrix.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ------------------------------------------------------------------
# Evidence and Audit Trail
# ------------------------------------------------------------------
elif page == "Evidence and Audit Trail":
    st.title("Evidence and Audit Trail")

    st.markdown("#### Data Sources Used in This Test Cycle")
    data_files = [
        ("Employees.csv", "HR employee master file"),
        ("User_Accounts.csv", "System account extract (SAP, Payroll, Sales Cloud, AWS IAM Console)"),
        ("User_Roles.csv", "Role/entitlement assignment extract"),
        ("SoD_Rules.csv", "Segregation-of-duties rule library"),
        ("Change_Requests.csv", "Change management log extract"),
    ]
    rows = []
    for fname, desc in data_files:
        df = pd.read_csv(logic.DATA_DIR / fname)
        rows.append({"File": fname, "Description": desc, "Rows": len(df)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown("#### SQL Control Tests Applied")
    test_rows = []
    for key, fname in logic.TEST_FILES:
        sql_text = logic.load_sql(fname)
        first_comment = next(
            (l.strip("- ").strip() for l in sql_text.splitlines() if l.strip().startswith("-- Control Test")),
            logic.CATEGORY_LABELS[key],
        )
        test_rows.append({"SQL File": fname, "Control Test": first_comment, "Domain": logic.CATEGORY_DOMAIN[key]})
    st.dataframe(pd.DataFrame(test_rows), hide_index=True, use_container_width=True)

    st.markdown("#### Test Run History")
    st.dataframe(logic.get_audit_log(conn), hide_index=True, use_container_width=True)

    st.markdown("#### Findings Review Status")
    review_cols = ["finding_id", "status", "reviewer", "remediation_due_date", "last_updated"]
    st.dataframe(findings[review_cols], hide_index=True, use_container_width=True)

    st.markdown("#### Change History (Findings Review Log)")
    history = logic.get_review_history(conn)
    if history.empty:
        st.caption("No manual changes recorded yet.")
    else:
        st.dataframe(history, hide_index=True, use_container_width=True)

# ------------------------------------------------------------------
# About / README
# ------------------------------------------------------------------
else:
    readme_path = Path(__file__).parent / "docs" / "README.md"
    if readme_path.exists():
        st.markdown(readme_path.read_text(encoding="utf-8"))
    else:
        st.write("README not found.")
