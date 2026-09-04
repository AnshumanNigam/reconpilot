# ReconPilot™

### AI Finance Controller for Reconciliation, Exception Investigation, and Cash Position Management

Understand the project in more detail here --> [Link](https://drive.google.com/file/d/14s1YqnB92_HTfArCryZ2SbevNSFqQyis/view?usp=sharing)

ReconPilot is an AI-assisted financial reconciliation system designed to automate a finance operations workflow from transaction matching through exception investigation, financial exposure analysis, human approval, and audit logging.

It combines deterministic financial reconciliation with AI-powered exception investigation rather than using an LLM for tasks that can be solved reliably with explicit rules.

---

## 1. Problem

Finance operations teams often need to reconcile multiple sources of financial data:

- Payment records
- Settlement records
- Bank transactions
- Refunds

The basic question is:

> Did the money from each payment move correctly through the settlement process and appear in the bank?

When transaction volumes increase, manually comparing these datasets becomes slow and error-prone.

More importantly, not every mismatch means the same thing.

A transaction may be:

- Normal
- Delayed
- Missing from the bank
- Affected by a refund
- Financially mismatched

ReconPilot automates the first layer of reconciliation and then uses AI to investigate unresolved exceptions.

---

# 2. What ReconPilot Does

ReconPilot follows a layered approach:

```text
Financial Data
      │
      ▼
Data Generator
      │
      ▼
Deterministic Reconciliation Engine
      │
      ├── Match ──────────────► Auto-Reconciled
      │
      └── Exception
              │
              ▼
        AI Investigator
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
    Explain Classify Recommend
              │
              ▼
       Human Approval
              │
       ┌──────┴──────┐
       ▼             ▼
    Approve        Escalate
       │             │
       └──────┬──────┘
              ▼
         Audit Trail
```

The system deliberately separates deterministic financial logic from AI-based investigation.

---

# 3. Why Deterministic Reconciliation + AI?

Financial calculations should be deterministic whenever possible.

For example, if:

```text
Gross Amount = ₹10,000
Fee = ₹200
Tax = ₹36
```

then:

```text
Expected Net Amount
= ₹10,000 - ₹200 - ₹36
= ₹9,764
```

There is no reason to ask an LLM to calculate this.

ReconPilot therefore uses explicit rules to establish financial facts and uses AI where interpretation and investigation are more useful.

### Deterministic layer

Responsible for:

- Settlement existence
- Settlement timing
- Bank record existence
- Refund detection
- Settlement calculation validation
- Bank amount validation

### AI layer

Responsible for:

- Exception classification
- Evidence-based explanation
- Financial difference interpretation
- Recommended action
- Confidence estimation

### Human layer

Responsible for:

- Final approval
- Escalation
- Recorded operational decision

This provides a more controlled architecture for financial operations than using an LLM as the reconciliation engine itself.

---

# 4. Synthetic Dataset

The project uses a synthetic dataset containing **100 payments**.

The data is separated into:

```text
Data/
├── payments.csv
├── settlements.csv
├── bank_records.csv
├── refunds.csv
└── ground_truth.csv
```

The dataset contains five scenarios:

| Scenario | Description |
|---|---|
| `NORMAL` | Payment, settlement, and bank records reconcile normally |
| `PARTIAL_REFUND` | A portion of the original payment has been refunded |
| `SETTLEMENT_DELAY` | Settlement occurs beyond the expected settlement window |
| `MISSING_BANK_RECORD` | Settlement exists but the corresponding bank credit is missing |
| `UNEXPLAINED_MISMATCH` | Bank amount does not match the expected settlement amount |

`ground_truth.csv` provides the known scenario for each payment and is used to evaluate the AI investigation layer.

---

# 5. Reconciliation Engine

The reconciliation engine processes each payment and checks the available financial evidence.

The checks include:

### 1. Missing Settlement

If a payment does not have a settlement record:

```text
MISSING_SETTLEMENT
```

### 2. Settlement Delay

Settlements occurring more than three days after the payment are classified as:

```text
SETTLEMENT_DELAY
```

### 3. Missing Bank Record

If a settlement exists but the corresponding bank credit is missing:

```text
MISSING_BANK_RECORD
```

### 4. Refund

If a refund exists:

```text
REFUND_REQUIRES_INVESTIGATION
```

The AI investigator can then determine whether the evidence supports a partial refund scenario.

### 5. Settlement Calculation

The expected settlement amount is calculated from:

```text
Expected Net Amount
= Gross Amount - Fee - Tax
```

The calculated value is compared with the recorded settlement amount.

### 6. Bank Amount

The bank credit is compared against the expected settlement amount.

A discrepancy produces:

```text
BANK_AMOUNT_MISMATCH
```

Transactions that pass all relevant checks are:

```text
AUTO_RECONCILED
```

---

# 6. AI Exception Investigation

The AI investigator receives structured evidence from the reconciliation engine.

The AI does not receive arbitrary access to the entire dataset.

For each exception, it receives the relevant payment, settlement, bank, and refund evidence.

It produces structured output containing:

```text
classification
explanation
difference
recommended_action
confidence
```

The supported classifications include:

```text
SETTLEMENT_DELAY
MISSING_BANK_RECORD
PARTIAL_REFUND
UNEXPLAINED_MISMATCH
```

The supported recommendations include:

```text
NO_ACTION
WAIT_FOR_SETTLEMENT
INVESTIGATE_REFUND
ESCALATE
```

The investigator is instructed to use only the supplied evidence and not invent missing facts.

---

# 7. AI Evaluation

The AI investigator was evaluated against the synthetic ground truth.

The reconciliation engine identified:

```text
82 exceptions
18 automatically reconciled transactions
```

The AI investigated all 82 exceptions.

### Results

```text
Correct classifications:   80
Incorrect classifications:  2
Total investigations:      82

AI classification accuracy: 97.56%
```

### Classification distribution

| Classification | AI Results | Ground Truth |
|---|---:|---:|
| Settlement Delay | 38 | 36 |
| Partial Refund | 17 | 17 |
| Unexplained Mismatch | 16 | 16 |
| Missing Bank Record | 11 | 13 |

The two incorrect classifications are retained in the evaluation rather than being removed or corrected after the fact.

This provides an explicit and reproducible failure set.

---

# 8. Cash Position

ReconPilot also provides a high-level view of expected versus observed cash.

The dashboard calculates:

### Expected Settlement

Total expected settlement value based on the reconciliation dataset.

### Bank Credits

Total value represented by bank credit records.

### Outstanding

```text
Outstanding
= Expected Settlement - Bank Credits
```

For the current synthetic dataset:

```text
Expected Settlement: ₹699,471.15
Bank Credits:        ₹311,643.35
Outstanding:         ₹387,827.80
```

The outstanding amount represents expected settlement value that is not currently represented by bank credits in the dataset.

It should not be interpreted as confirmed lost or stolen money.

---

# 9. Exception Prioritization

Not every exception has the same financial importance.

ReconPilot calculates a financial exposure for each exception and prioritizes the investigation queue.

Examples include:

```text
Settlement Delay
→ Expected settlement exposure

Missing Bank Record
→ Expected settlement exposure

Bank Amount Mismatch
→ Absolute difference between expected and bank amount

Refund Investigation
→ Refund amount
```

Priority is determined using financial exposure and exception severity.

The priority system is independent of the AI classification so that financial prioritization is not driven by an LLM's subjective output.

The dashboard categorizes cases into:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

This allows a finance operator to focus attention on the exceptions with the highest operational and financial impact.

---

# 10. Human Approval

ReconPilot does not allow the AI to silently make the final financial decision.

After an exception is investigated, a human reviewer can:

```text
APPROVE
```

or:

```text
ESCALATE
```

The decision is recorded in the audit log.

The audit record contains information such as:

- Timestamp
- Payment ID
- Deterministic finding
- AI classification
- AI confidence
- Reviewer decision
- Reviewer

This provides traceability for operational decisions.

---

# 11. Dashboard

The Streamlit dashboard contains four main sections.

## Controller Dashboard

Provides:

- Expected settlement
- Bank credits
- Outstanding amount
- Exception exposure
- Exception counts
- Prioritized investigation queue

## Exception Investigation

Provides case-level investigation including:

- Payment evidence
- Settlement evidence
- Bank evidence
- Refund evidence
- Deterministic finding
- AI classification
- Explanation
- Recommended action
- Confidence

## Evaluation

Provides:

- AI classification results
- Ground-truth comparison
- Accuracy
- Classification distribution
- Incorrect cases

## Audit Trail

Provides the history of human decisions made on investigated exceptions.

---

# 12. API

ReconPilot also exposes a FastAPI service.

Available endpoints:

```text
GET /health
GET /reconciliation/summary
GET /reconciliation/exceptions
GET /reconciliation/{payment_id}
```

### Health Check

```text
GET /health
```

Returns the API health status.

### Summary

```text
GET /reconciliation/summary
```

Returns reconciliation-level metrics.

### Exceptions

```text
GET /reconciliation/exceptions
```

Returns unresolved exceptions together with available AI investigation results.

### Individual Payment

```text
GET /reconciliation/{payment_id}
```

Returns reconciliation information for an individual payment.

---

# 13. Project Structure

```text
reconpilot/
│
├── Codes/
│   ├── __init__.py
│   ├── api.py
│   ├── ai_evaluator.py
│   ├── data_generator.py
│   ├── evaluator.py
│   ├── investigator.py
│   ├── reconciler.py
│   └── dashboard.py
│
├── Data/
│   ├── payments.csv
│   ├── settlements.csv
│   ├── bank_records.csv
│   ├── refunds.csv
│   └── ground_truth.csv
│
├── Output/
│   └── reconciliation_results.csv
│
├── Tests/
│   └── ai_investigation_results.csv
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

# 14. Technology Stack

- **Python**
- **Pandas**
- **NumPy**
- **FastAPI**
- **Uvicorn**
- **Streamlit**
- **Google Gemini API**

The system uses Pandas for financial data processing, explicit Python logic for reconciliation, Gemini for exception investigation, FastAPI for programmatic access, and Streamlit for the operational dashboard.

---

# 15. Running the Project

## Install dependencies

```bash
pip install -r requirements.txt
```

## Configure Gemini

Set the Gemini API key as an environment variable.

### Windows PowerShell

```powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
```

The API key should never be hardcoded into source code or committed to GitHub.

---

# 16. Run the Dashboard

From the project root:

```bash
streamlit run Codes/dashboard.py
```

The Streamlit dashboard will open in the browser.

---

# 17. Run the API

From the project root:

```bash
uvicorn Codes.api:app --reload
```

The API will be available locally through the Uvicorn server.

---

# 18. Design Principles

ReconPilot is built around several principles:

### Deterministic where possible

Financial calculations and reconciliation rules should not depend on probabilistic model output.

### AI where useful

LLMs are used for investigation and interpretation of exceptions rather than basic arithmetic.

### Human in the loop

AI recommendations do not replace operational approval.

### Measured performance

AI output is evaluated against known ground truth.

### Explicit failures

Incorrect classifications are retained and reported rather than hidden.

### Auditability

Human decisions and investigation results are recorded.

### Financial prioritization

Exceptions are prioritized according to financial exposure rather than AI confidence alone.

---

# 19. Limitations

ReconPilot is a prototype built around a synthetic dataset.

Important limitations include:

- The dataset is synthetic rather than production financial data.
- Settlement rules are simplified for the prototype.
- The reconciliation logic is designed around the scenarios represented in the dataset.
- AI classification is not perfect.
- The current evaluation contains 2 incorrect AI classifications out of 82 investigations.
- Cash outstanding represents unmatched expected settlement value in the dataset and does not establish that money has been permanently lost.

A production implementation would require additional controls around authentication, authorization, data privacy, idempotency, transaction-level lineage, model monitoring, exception workflows, and integration with real payment processors, banks, and ERP systems.

---

# 20. Key Result

ReconPilot demonstrates an end-to-end finance operations workflow:

```text
100 synthetic payments
        ↓
Deterministic reconciliation
        ↓
18 auto-reconciled
        ↓
82 exceptions
        ↓
AI investigation
        ↓
80 / 82 correct classifications
        ↓
97.56% AI classification accuracy
        ↓
Human approval / escalation
        ↓
Audit trail
```

The system therefore combines:

**Reconciliation + AI Investigation + Cash Position + Exception Prioritization + Human Approval + Auditability**

into a single finance operations workflow.

---

# 21. Author

**Anshuman Nigam**

AI & Data Engineer

Portfolio:  
https://anshumannigam.github.io/Anshuman-Nigam/

© 2026 Anshuman Nigam. All rights reserved.

**ReconPilot™**
