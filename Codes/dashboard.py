import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime


# ============================================================
# CONFIG
# ============================================================

PROJECT_DIR = Path(
    r"C:\Users\anshu\OneDrive\Desktop\prog\Projects\reconpilot"
)

OUTPUT_DIR = PROJECT_DIR / "Output"
DATA_DIR = PROJECT_DIR / "Data"
TESTS_DIR = PROJECT_DIR / "Tests"

RESULTS_PATH = OUTPUT_DIR / "reconciliation_results.csv"
AI_RESULTS_PATH = TESTS_DIR / "ai_investigation_results.csv"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.csv"
AUDIT_PATH = OUTPUT_DIR / "audit_log.csv"


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="ReconPilot™",
    page_icon="💳",
    layout="wide",
)

# ------------------------------------------------------------
# BRANDING / POLISH
# ------------------------------------------------------------

st.markdown(
    '''
    <style>
    .brand-footer {
        text-align: center;
        padding: 1.2rem 0 0.4rem 0;
        color: #8b8f98;
        font-size: 0.82rem;
    }

    .brand-footer a {
        color: #9aa0aa;
        text-decoration: none;
    }

    .brand-footer a:hover {
        text-decoration: underline;
    }

    .brand-mark {
        font-weight: 600;
    }
    </style>
    ''',
    unsafe_allow_html=True,
)


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data
def load_results():
    return pd.read_csv(RESULTS_PATH)


@st.cache_data
def load_ai_results():
    return pd.read_csv(AI_RESULTS_PATH)


@st.cache_data
def load_ground_truth():
    return pd.read_csv(GROUND_TRUTH_PATH)


def load_audit_log():
    if AUDIT_PATH.exists():
        return pd.read_csv(AUDIT_PATH)

    return pd.DataFrame(
        columns=[
            "timestamp",
            "payment_id",
            "deterministic_finding",
            "ai_classification",
            "recommended_action",
            "confidence",
            "decision",
            "reviewer",
        ]
    )


# ============================================================
# AUDIT TRAIL
# ============================================================

def save_audit_decision(
    payment_id,
    deterministic_finding,
    ai_classification,
    recommended_action,
    confidence,
    decision,
):
    audit = load_audit_log()

    new_record = pd.DataFrame(
        [
            {
                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "payment_id": payment_id,
                "deterministic_finding": deterministic_finding,
                "ai_classification": ai_classification,
                "recommended_action": recommended_action,
                "confidence": confidence,
                "decision": decision,
                "reviewer": "Finance Controller",
            }
        ]
    )

    audit = pd.concat(
        [audit, new_record],
        ignore_index=True,
    )

    audit.to_csv(
        AUDIT_PATH,
        index=False,
    )


# ============================================================
# CASH POSITION CALCULATION
# ============================================================

def calculate_cash_position(results, exceptions):
    """
    Calculate the current cash position and financial exposure.

    Expected Settlement:
        Total expected net settlement across all payments.

    Bank Credits:
        Total amount actually visible in bank records.

    Outstanding:
        Expected settlement value not currently represented
        by bank credits.

    Exception Exposure:
        Financial amount associated with exception cases.
    """

    # --------------------------------------------------------
    # Expected settlement
    # --------------------------------------------------------

    expected_settlement = (
        pd.to_numeric(
            results["expected_net_amount"],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

    # --------------------------------------------------------
    # Actual bank credits
    # --------------------------------------------------------

    bank_credits = (
        pd.to_numeric(
            results["bank_amount"],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

    # --------------------------------------------------------
    # Outstanding amount
    # --------------------------------------------------------

    outstanding = max(
        expected_settlement - bank_credits,
        0,
    )

    # --------------------------------------------------------
    # Exposure by exception type
    # --------------------------------------------------------

    exposure = {}

    for exception_type in exceptions["reason"].dropna().unique():

        cases = exceptions[
            exceptions["reason"] == exception_type
        ]

        # Settlement delays:
        # Full expected settlement is still outstanding.

        if exception_type == "SETTLEMENT_DELAY":

            amount = (
                pd.to_numeric(
                    cases["expected_net_amount"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        # Missing bank records:
        # Full expected settlement has no corresponding
        # bank transaction.

        elif exception_type == "MISSING_BANK_RECORD":

            amount = (
                pd.to_numeric(
                    cases["expected_net_amount"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        # Unexplained mismatch:
        # Only the monetary discrepancy is exposed.

        elif exception_type == "BANK_AMOUNT_MISMATCH":

            expected = pd.to_numeric(
                cases["expected_net_amount"],
                errors="coerce",
            ).fillna(0)

            bank = pd.to_numeric(
                cases["bank_amount"],
                errors="coerce",
            ).fillna(0)

            amount = (
                expected - bank
            ).abs().sum()

        # AI classification calls this
        # PARTIAL_REFUND, while deterministic reconciliation
        # calls it REFUND_REQUIRES_INVESTIGATION.

        elif exception_type == "REFUND_REQUIRES_INVESTIGATION":

            amount = (
                pd.to_numeric(
                    cases["refund_amount"],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        else:
            amount = 0

        exposure[exception_type] = amount

    total_exception_exposure = sum(
        exposure.values()
    )

    return {
        "expected_settlement": expected_settlement,
        "bank_credits": bank_credits,
        "outstanding": outstanding,
        "exception_exposure": total_exception_exposure,
        "exposure_by_type": exposure,
    }



# ============================================================
# EXCEPTION PRIORITIZATION
# ============================================================

def build_priority_queue(exceptions):
    """
    Rank exceptions using deterministic financial exposure
    and exception severity.

    The AI investigates and explains cases. This ranking is
    deterministic, transparent, and auditable.
    """

    queue = exceptions.copy()

    queue["expected_amount"] = pd.to_numeric(
        queue["expected_net_amount"],
        errors="coerce",
    ).fillna(0)

    queue["bank_amount_numeric"] = pd.to_numeric(
        queue["bank_amount"],
        errors="coerce",
    ).fillna(0)

    queue["refund_amount_numeric"] = pd.to_numeric(
        queue["refund_amount"],
        errors="coerce",
    ).fillna(0)

    queue["financial_exposure"] = 0.0

    # Delayed settlement: full expected settlement is outstanding.
    mask = queue["reason"] == "SETTLEMENT_DELAY"
    queue.loc[mask, "financial_exposure"] = (
        queue.loc[mask, "expected_amount"]
    )

    # Missing bank record: no corresponding bank evidence.
    mask = queue["reason"] == "MISSING_BANK_RECORD"
    queue.loc[mask, "financial_exposure"] = (
        queue.loc[mask, "expected_amount"]
    )

    # Bank mismatch: expose only the actual discrepancy.
    mask = queue["reason"] == "BANK_AMOUNT_MISMATCH"
    queue.loc[mask, "financial_exposure"] = (
        queue.loc[mask, "expected_amount"]
        - queue.loc[mask, "bank_amount_numeric"]
    ).abs()

    # Refund investigation: refund amount requires review.
    mask = queue["reason"] == "REFUND_REQUIRES_INVESTIGATION"
    queue.loc[mask, "financial_exposure"] = (
        queue.loc[mask, "refund_amount_numeric"]
    )

    severity_map = {
        "BANK_AMOUNT_MISMATCH": 4,
        "MISSING_BANK_RECORD": 3,
        "REFUND_REQUIRES_INVESTIGATION": 3,
        "SETTLEMENT_DELAY": 2,
    }

    queue["severity"] = (
        queue["reason"]
        .map(severity_map)
        .fillna(1)
    )

    queue["priority_score"] = (
        queue["financial_exposure"]
        * queue["severity"]
    )

    def assign_priority(row):
        if row["reason"] == "BANK_AMOUNT_MISMATCH":
            return "CRITICAL"

        if (
            row["reason"] == "MISSING_BANK_RECORD"
            and row["financial_exposure"] >= 10000
        ):
            return "CRITICAL"

        if (
            row["financial_exposure"] >= 10000
            or row["reason"] in [
                "MISSING_BANK_RECORD",
                "REFUND_REQUIRES_INVESTIGATION",
            ]
        ):
            return "HIGH"

        if row["reason"] == "SETTLEMENT_DELAY":
            return "MEDIUM"

        return "LOW"

    queue["priority"] = queue.apply(
        assign_priority,
        axis=1,
    )

    priority_order = {
        "CRITICAL": 1,
        "HIGH": 2,
        "MEDIUM": 3,
        "LOW": 4,
    }

    queue["priority_order"] = (
        queue["priority"]
        .map(priority_order)
    )

    return queue.sort_values(
        ["priority_order", "priority_score"],
        ascending=[True, False],
    )


# ============================================================
# LOAD DATA
# ============================================================

results = load_results()
ai_results = load_ai_results()
ground_truth = load_ground_truth()
audit = load_audit_log()


# ============================================================
# MERGE AI RESULTS
# ============================================================

investigations = results.merge(
    ai_results,
    on="payment_id",
    how="left",
)

exceptions = investigations[
    investigations["status"] == "EXCEPTION"
].copy()


# ============================================================
# HEADER
# ============================================================

st.title("ReconPilot™")

st.caption(
    "AI Finance Controller · Automated reconciliation and exception investigation"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("ReconPilot")

st.sidebar.subheader("Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Controller Dashboard",
        "Exception Investigation",
        "Evaluation",
        "Audit Trail",
    ],
)

st.sidebar.divider()

st.sidebar.caption(
    "Deterministic reconciliation + AI investigation"
)


# ============================================================
# CONTROLLER DASHBOARD
# ============================================================

if page == "Controller Dashboard":

    st.header("Controller Dashboard")

    # --------------------------------------------------------
    # BASIC KPIs
    # --------------------------------------------------------

    total_records = len(results)

    auto_reconciled = len(
        results[
            results["status"] == "AUTO_RECONCILED"
        ]
    )

    exception_count = len(
        results[
            results["status"] == "EXCEPTION"
        ]
    )

    exception_rate = (
        exception_count / total_records
        if total_records > 0
        else 0
    )

    # --------------------------------------------------------
    # HUMAN REVIEW METRICS
    # --------------------------------------------------------

    approved_count = len(
        audit[
            audit["decision"] == "APPROVED"
        ]
    )

    escalated_count = len(
        audit[
            audit["decision"] == "ESCALATED"
        ]
    )

    resolved_count = (
        approved_count + escalated_count
    )

    pending_count = max(
        exception_count - resolved_count,
        0,
    )

    # --------------------------------------------------------
    # KPI ROW
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Records",
        total_records,
    )

    col2.metric(
        "Auto-Reconciled",
        auto_reconciled,
    )

    col3.metric(
        "Exceptions",
        exception_count,
    )

    col4.metric(
        "Exception Rate",
        f"{exception_rate:.1%}",
    )

    st.divider()

    # --------------------------------------------------------
    # HUMAN REVIEW STATUS
    # --------------------------------------------------------

    st.subheader(
        "Exception Resolution Status"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Pending Review",
        pending_count,
    )

    col2.metric(
        "Approved",
        approved_count,
    )

    col3.metric(
        "Escalated",
        escalated_count,
    )

    st.divider()

    # --------------------------------------------------------
    # CASH POSITION
    # --------------------------------------------------------

    st.subheader("Cash Position")

    cash = calculate_cash_position(
        results,
        exceptions,
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Expected Settlement",
            f"₹{cash['expected_settlement']:,.2f}",
        )

    with col2:

        st.metric(
            "Bank Credits",
            f"₹{cash['bank_credits']:,.2f}",
        )

    with col3:

        st.metric(
            "Outstanding",
            f"₹{cash['outstanding']:,.2f}",
        )

    with col4:

        st.metric(
            "Exception Exposure",
            f"₹{cash['exception_exposure']:,.2f}",
        )

    st.caption(
        "Outstanding represents expected settlement value "
        "not currently reflected in bank credits."
    )

    st.divider()

    # --------------------------------------------------------
    # FINANCIAL EXPOSURE BY EXCEPTION
    # --------------------------------------------------------

    st.subheader(
        "Financial Exposure by Exception"
    )

    exposure_df = pd.DataFrame(
        [
            {
                "Exception Type": exception_type,
                "Exposure": amount,
            }
            for exception_type, amount
            in cash["exposure_by_type"].items()
        ]
    )

    if not exposure_df.empty:

        exposure_df = exposure_df.sort_values(
            "Exposure",
            ascending=False,
        )

        col1, col2 = st.columns([1, 2])

        with col1:

            display_exposure = (
                exposure_df.copy()
            )

            display_exposure["Exposure"] = (
                display_exposure["Exposure"]
                .map(
                    lambda x:
                    f"₹{x:,.2f}"
                )
            )

            st.dataframe(
                display_exposure,
                use_container_width=True,
                hide_index=True,
            )

        with col2:

            chart_data = (
                exposure_df
                .set_index("Exception Type")
            )

            st.bar_chart(
                chart_data
            )

    else:

        st.info(
            "No financial exposure detected."
        )

    st.divider()

    # --------------------------------------------------------
    # EXCEPTION BREAKDOWN
    # --------------------------------------------------------

    st.subheader(
        "Exception Breakdown"
    )

    exception_breakdown = (
        exceptions["reason"]
        .value_counts()
        .rename_axis("Exception Type")
        .reset_index(name="Count")
    )

    col1, col2 = st.columns([1, 2])

    with col1:

        st.dataframe(
            exception_breakdown,
            use_container_width=True,
            hide_index=True,
        )

    with col2:

        st.bar_chart(
            exception_breakdown.set_index(
                "Exception Type"
            )
        )

    st.divider()

    # --------------------------------------------------------
    # PRIORITIZED EXCEPTION QUEUE
    # --------------------------------------------------------

    st.subheader("Prioritized Exception Queue")

    priority_queue = build_priority_queue(exceptions)

    critical_count = len(
        priority_queue[
            priority_queue["priority"] == "CRITICAL"
        ]
    )

    high_count = len(
        priority_queue[
            priority_queue["priority"] == "HIGH"
        ]
    )

    medium_count = len(
        priority_queue[
            priority_queue["priority"] == "MEDIUM"
        ]
    )

    low_count = len(
        priority_queue[
            priority_queue["priority"] == "LOW"
        ]
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Critical", critical_count)
    col2.metric("High", high_count)
    col3.metric("Medium", medium_count)
    col4.metric("Low", low_count)

    st.caption(
        "Priority combines financial exposure with deterministic "
        "exception severity. AI classification remains separate."
    )

    st.divider()

    # --------------------------------------------------------
    # TOP PRIORITY CASES
    # --------------------------------------------------------

    st.markdown("### Top Priority Cases")

    top_cases = priority_queue.head(5)

    for _, case in top_cases.iterrows():

        message = (
            f"**{case['payment_id']}** · "
            f"{case['reason']} · "
            f"₹{case['financial_exposure']:,.2f}"
        )

        if case["priority"] == "CRITICAL":
            st.error(f"🔴 {message}")

        elif case["priority"] == "HIGH":
            st.warning(f"🟠 {message}")

        elif case["priority"] == "MEDIUM":
            st.info(f"🟡 {message}")

        else:
            st.success(f"🟢 {message}")

    st.divider()

    # --------------------------------------------------------
    # FULL PRIORITIZED TABLE
    # --------------------------------------------------------

    display_queue = priority_queue[
        [
            "payment_id",
            "priority",
            "reason",
            "financial_exposure",
            "ai_classification",
            "recommended_action",
            "confidence",
        ]
    ].copy()

    display_queue["financial_exposure"] = (
        display_queue["financial_exposure"]
        .map(lambda x: f"₹{x:,.2f}")
    )

    display_queue["confidence"] = (
        pd.to_numeric(
            display_queue["confidence"],
            errors="coerce",
        )
        .fillna(0)
        .mul(100)
        .round(0)
        .astype(int)
        .astype(str)
        + "%"
    )

    display_queue = display_queue.rename(
        columns={
            "payment_id": "Payment",
            "priority": "Priority",
            "reason": "Deterministic Finding",
            "financial_exposure": "Financial Exposure",
            "ai_classification": "AI Classification",
            "recommended_action": "Recommended Action",
            "confidence": "AI Confidence",
        }
    )

    st.dataframe(
        display_queue,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# EXCEPTION INVESTIGATION
# ============================================================

elif page == "Exception Investigation":

    st.header(
        "AI Exception Investigation"
    )

    exception_ids = (
        exceptions["payment_id"]
        .tolist()
    )

    if not exception_ids:

        st.success(
            "No exceptions found."
        )

        st.stop()

    selected_payment = st.selectbox(
        "Select an exception",
        exception_ids,
    )

    case = exceptions[
        exceptions["payment_id"]
        == selected_payment
    ].iloc[0]

    st.divider()

    # --------------------------------------------------------
    # CASE HEADER
    # --------------------------------------------------------

    st.subheader(
        f"Payment: {selected_payment}"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown(
            "**Deterministic Finding**"
        )

        st.markdown(
            f"### `{case['reason']}`"
        )

    with col2:

        st.markdown(
            "**AI Classification**"
        )

        st.markdown(
            f"### `{case['ai_classification']}`"
        )

    with col3:

        st.markdown(
            "**AI Confidence**"
        )

        confidence = case["confidence"]

        if pd.notna(confidence):

            st.markdown(
                f"### {float(confidence):.0%}"
            )

        else:

            st.markdown(
                "### N/A"
            )

    st.divider()

    # --------------------------------------------------------
    # FINANCIAL EVIDENCE
    # --------------------------------------------------------

    st.subheader(
        "Financial Evidence"
    )

    col1, col2, col3, col4 = st.columns(4)

    # Payment
    with col1:

        st.markdown(
            "### Payment"
        )

        st.metric(
            "Gross Amount",
            f"₹{float(case['gross_amount']):,.2f}",
        )

        st.write(
            f"Payment Date: `{case['payment_date']}`"
        )

    # Settlement
    with col2:

        st.markdown(
            "### Settlement"
        )

        if pd.notna(
            case["settlement_net_amount"]
        ):

            st.metric(
                "Net Amount",
                f"₹{float(case['settlement_net_amount']):,.2f}",
            )

        else:

            st.metric(
                "Net Amount",
                "N/A",
            )

        if pd.notna(
            case["settlement_date"]
        ):

            st.write(
                "Settlement Date: "
                f"`{case['settlement_date']}`"
            )

        if pd.notna(
            case["delay_days"]
        ):

            st.write(
                f"Delay: `{int(case['delay_days'])} days`"
            )

    # Bank
    with col3:

        st.markdown(
            "### Bank"
        )

        if pd.notna(
            case["bank_amount"]
        ):

            st.metric(
                "Bank Amount",
                f"₹{float(case['bank_amount']):,.2f}",
            )

        else:

            st.metric(
                "Bank Amount",
                "Missing",
            )

    # Refund
    with col4:

        st.markdown(
            "### Refund"
        )

        if pd.notna(
            case["refund_amount"]
        ):

            st.metric(
                "Refund Amount",
                f"₹{float(case['refund_amount']):,.2f}",
            )

        else:

            st.metric(
                "Refund Amount",
                "None",
            )

    st.divider()

    # --------------------------------------------------------
    # CALCULATION EVIDENCE
    # --------------------------------------------------------

    st.subheader(
        "Reconciliation Evidence"
    )

    evidence_col1, evidence_col2, evidence_col3 = (
        st.columns(3)
    )

    with evidence_col1:

        if pd.notna(
            case["expected_net_amount"]
        ):

            st.metric(
                "Expected Net",
                f"₹{float(case['expected_net_amount']):,.2f}",
            )

        else:

            st.metric(
                "Expected Net",
                "N/A",
            )

    with evidence_col2:

        if pd.notna(
            case["settlement_net_amount"]
        ):

            st.metric(
                "Settlement Net",
                f"₹{float(case['settlement_net_amount']):,.2f}",
            )

        else:

            st.metric(
                "Settlement Net",
                "N/A",
            )

    with evidence_col3:

        difference = case["difference"]

        if pd.notna(difference):

            st.metric(
                "AI Difference",
                f"₹{float(difference):,.2f}",
            )

        else:

            st.metric(
                "AI Difference",
                "N/A",
            )

    st.divider()

    # --------------------------------------------------------
    # AI INVESTIGATION
    # --------------------------------------------------------

    st.subheader(
        "AI Investigation"
    )

    explanation = case["explanation"]

    if pd.notna(explanation):

        st.info(
            str(explanation)
        )

    else:

        st.warning(
            "No AI explanation available."
        )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            "**Recommended Action**"
        )

        st.success(
            str(
                case["recommended_action"]
            )
        )

    with col2:

        st.markdown(
            "**AI Confidence**"
        )

        if pd.notna(
            case["confidence"]
        ):

            st.progress(
                float(case["confidence"])
            )

        else:

            st.write(
                "Confidence unavailable"
            )

    st.divider()

    # --------------------------------------------------------
    # HUMAN REVIEW
    # --------------------------------------------------------

    st.subheader(
        "Human Review"
    )

    case_audit = audit[
        audit["payment_id"]
        == selected_payment
    ]

    if not case_audit.empty:

        latest_decision = (
            case_audit.iloc[-1]["decision"]
        )

        if latest_decision == "APPROVED":

            st.success(
                "Resolution approved by Finance Controller."
            )

        elif latest_decision == "ESCALATED":

            st.warning(
                "Case escalated for further investigation."
            )

        st.caption(
            f"Latest decision: {latest_decision}"
        )

    else:

        st.info(
            "This exception is awaiting human review."
        )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "✓ Approve Resolution",
            use_container_width=True,
            type="primary",
        ):

            save_audit_decision(
                payment_id=selected_payment,
                deterministic_finding=case["reason"],
                ai_classification=case[
                    "ai_classification"
                ],
                recommended_action=case[
                    "recommended_action"
                ],
                confidence=case["confidence"],
                decision="APPROVED",
            )

            st.success(
                f"{selected_payment} resolution approved."
            )

            st.rerun()

    with col2:

        if st.button(
            "⚠ Escalate",
            use_container_width=True,
        ):

            save_audit_decision(
                payment_id=selected_payment,
                deterministic_finding=case["reason"],
                ai_classification=case[
                    "ai_classification"
                ],
                recommended_action=case[
                    "recommended_action"
                ],
                confidence=case["confidence"],
                decision="ESCALATED",
            )

            st.warning(
                f"{selected_payment} escalated."
            )

            st.rerun()


# ============================================================
# EVALUATION
# ============================================================

elif page == "Evaluation":

    st.header(
        "AI Evaluation"
    )

    evaluation = ai_results.merge(
        ground_truth,
        on="payment_id",
        how="inner",
    )

    evaluation["correct"] = (
        evaluation["ai_classification"]
        == evaluation["true_scenario"]
    )

    total = len(evaluation)

    correct = int(
        evaluation["correct"].sum()
    )

    incorrect = total - correct

    accuracy = (
        correct / total
        if total > 0
        else 0
    )

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "AI Investigations",
        total,
    )

    col2.metric(
        "Correct",
        correct,
    )

    col3.metric(
        "Incorrect",
        incorrect,
    )

    col4.metric(
        "AI Accuracy",
        f"{accuracy:.2%}",
    )

    st.divider()

    # --------------------------------------------------------
    # CLASSIFICATION DISTRIBUTION
    # --------------------------------------------------------

    st.subheader(
        "AI Classification Distribution"
    )

    classification_counts = (
        evaluation["ai_classification"]
        .value_counts()
        .rename_axis("Classification")
        .reset_index(name="Count")
    )

    st.bar_chart(
        classification_counts.set_index(
            "Classification"
        )
    )

    st.divider()

    # --------------------------------------------------------
    # INCORRECT CASES
    # --------------------------------------------------------

    st.subheader(
        "Incorrect Classifications"
    )

    incorrect_cases = evaluation[
        ~evaluation["correct"]
    ][
        [
            "payment_id",
            "true_scenario",
            "ai_classification",
            "confidence",
            "explanation",
        ]
    ].copy()

    if incorrect_cases.empty:

        st.success(
            "No incorrect classifications."
        )

    else:

        incorrect_cases["confidence"] = (
            pd.to_numeric(
                incorrect_cases["confidence"],
                errors="coerce",
            )
            .fillna(0)
            .mul(100)
            .round(0)
            .astype(int)
            .astype(str)
            + "%"
        )

        st.dataframe(
            incorrect_cases,
            use_container_width=True,
            hide_index=True,
        )

        st.warning(
            "These cases should be reviewed before production deployment."
        )


# ============================================================
# AUDIT TRAIL
# ============================================================

elif page == "Audit Trail":

    st.header(
        "Audit Trail"
    )

    audit = load_audit_log()

    if audit.empty:

        st.info(
            "No human review decisions have been recorded yet."
        )

    else:

        # ----------------------------------------------------
        # AUDIT KPIs
        # ----------------------------------------------------

        approved = len(
            audit[
                audit["decision"] == "APPROVED"
            ]
        )

        escalated = len(
            audit[
                audit["decision"] == "ESCALATED"
            ]
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Decisions",
            len(audit),
        )

        col2.metric(
            "Approved",
            approved,
        )

        col3.metric(
            "Escalated",
            escalated,
        )

        st.divider()

        # ----------------------------------------------------
        # AUDIT TABLE
        # ----------------------------------------------------

        display_audit = audit.copy()

        if "confidence" in display_audit.columns:

            display_audit["confidence"] = (
                pd.to_numeric(
                    display_audit["confidence"],
                    errors="coerce",
                )
                .fillna(0)
                .map(
                    lambda x: f"{x:.0%}"
                )
            )

        st.dataframe(
            display_audit.sort_values(
                "timestamp",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.markdown(
    '''
    <div class="brand-footer">
        <span class="brand-mark">ReconPilot™</span>
        · Deterministic reconciliation + AI investigation
        + human approval + audit trail
        <br>
        © 2026 Anshuman Nigam · All rights reserved
        · <a href="https://anshumannigam.github.io/Anshuman-Nigam/" target="_blank">
            anshumannigam.github.io/Anshuman-Nigam/
          </a>
    </div>
    ''',
    unsafe_allow_html=True,
)