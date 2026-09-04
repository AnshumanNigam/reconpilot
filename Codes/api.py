from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = PROJECT_DIR / "Output"
TESTS_DIR = PROJECT_DIR / "Tests"

RESULTS_PATH = OUTPUT_DIR / "reconciliation_results.csv"
AI_RESULTS_PATH = TESTS_DIR / "ai_investigation_results.csv"

# --------------------------------------------------
# FastAPI application
# --------------------------------------------------

app = FastAPI(
    title="ReconPilot API",
    description="AI-powered financial reconciliation API",
    version="0.1.0",
)


# --------------------------------------------------
# Data loaders
# --------------------------------------------------

def load_results():

    if not RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Reconciliation results not found: {RESULTS_PATH}"
        )

    return pd.read_csv(RESULTS_PATH)


def load_ai_results():

    if not AI_RESULTS_PATH.exists():
        return pd.DataFrame()

    return pd.read_csv(AI_RESULTS_PATH)


# --------------------------------------------------
# Convert pandas values to JSON-safe values
# --------------------------------------------------

def clean_record(record):

    cleaned = {}

    for key, value in record.items():

        if pd.isna(value):
            cleaned[key] = None

        else:
            cleaned[key] = value

    return cleaned


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "reconpilot",
    }


# --------------------------------------------------
# Reconciliation summary
# --------------------------------------------------

@app.get("/reconciliation/summary")
def reconciliation_summary():

    results = load_results()

    total_records = len(results)

    auto_reconciled = int(
        (results["status"] == "AUTO_RECONCILED").sum()
    )

    exceptions = int(
        (results["status"] == "EXCEPTION").sum()
    )

    exception_rate = (
        exceptions / total_records
        if total_records > 0
        else 0
    )

    return {
        "total_records": total_records,
        "auto_reconciled": auto_reconciled,
        "exceptions": exceptions,
        "exception_rate": round(exception_rate, 4),
    }


# --------------------------------------------------
# Get all reconciliation exceptions
# IMPORTANT:
# This route must come BEFORE /{payment_id}
# --------------------------------------------------

@app.get("/reconciliation/exceptions")
def get_exceptions():

    results = load_results()

    exceptions = results[
        results["status"] == "EXCEPTION"
    ].copy()

    records = exceptions.to_dict(
        orient="records"
    )

    # ----------------------------------------------
    # Add AI investigation results
    # ----------------------------------------------

    ai_results = load_ai_results()

    if not ai_results.empty:

        ai_lookup = (
            ai_results
            .set_index("payment_id")
            .to_dict(orient="index")
        )

        for record in records:

            payment_id = record["payment_id"]

            if payment_id in ai_lookup:

                ai_record = ai_lookup[payment_id]

                record["ai_investigation"] = (
                    clean_record(ai_record)
                )

            else:

                record["ai_investigation"] = None

    else:

        for record in records:
            record["ai_investigation"] = None

    # ----------------------------------------------
    # Clean deterministic reconciliation record
    # ----------------------------------------------

    records = [
        clean_record(record)
        for record in records
    ]

    return {
        "total_exceptions": len(records),
        "exceptions": records,
    }


# --------------------------------------------------
# Get individual reconciliation case
# IMPORTANT:
# This route must come AFTER /reconciliation/exceptions
# --------------------------------------------------

@app.get("/reconciliation/{payment_id}")
def get_reconciliation(payment_id: str):

    results = load_results()

    match = results[
        results["payment_id"] == payment_id
    ]

    if match.empty:

        raise HTTPException(
            status_code=404,
            detail=f"Payment {payment_id} not found",
        )

    record = match.iloc[0].to_dict()

    # ----------------------------------------------
    # Add AI investigation if available
    # ----------------------------------------------

    ai_results = load_ai_results()

    if not ai_results.empty:

        ai_match = ai_results[
            ai_results["payment_id"] == payment_id
        ]

        if not ai_match.empty:

            ai_record = ai_match.iloc[0].to_dict()

            record["ai_investigation"] = (
                clean_record(ai_record)
            )

        else:

            record["ai_investigation"] = None

    else:

        record["ai_investigation"] = None

    # ----------------------------------------------
    # Clean deterministic record
    # ----------------------------------------------

    record = clean_record(record)

    return record
