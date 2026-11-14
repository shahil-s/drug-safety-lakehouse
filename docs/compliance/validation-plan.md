# Validation plan (lightweight, GAMP 5 style)

A risk-based validation approach adapted for a portfolio project. In a real company this would be
reviewed and signed by Quality Assurance.

## 1. System description
Pharmacovigilance data platform ingesting public adverse event data into a governed GCP lakehouse.
**GAMP category:** mostly Category 1 (infrastructure: GCP services) and Category 5 (custom code: pipelines, dbt models).

## 2. User requirements (URS)
| ID | Requirement | Risk |
|---|---|---|
| URS-01 | The system shall store every received source payload unchanged. | High |
| URS-02 | The system shall record who/what ran each load, when, and how many records were received. | High |
| URS-03 | The system shall detect and reject records missing a report ID. | Medium |
| URS-04 | Curated data shall contain one row per unique safety report (latest version). | High |
| URS-05 | PHI fields shall be masked for users without the PHI reader role. | High |
| URS-06 | Infrastructure changes shall only be applied through version-controlled code. | Medium |

## 3. Qualification approach
- **IQ (Installation):** `terraform plan` shows no drift; resources match the code.
- **OQ (Operational):** automated tests prove each requirement under normal and error conditions.
- **PQ (Performance):** a full quarterly load completes within the SLA with reconciled counts.

## 4. Traceability matrix
| Requirement | Test(s) | Evidence |
|---|---|---|
| URS-01 | `tests/unit/test_raw_writer.py::test_writes_payload_unchanged_with_checksum` | CI run |
| URS-02 | `tests/unit/test_audit.py::test_audit_record_captures_run_metadata` | CI run |
| URS-03 | `tests/unit/test_openfda_client.py::test_records_without_report_id_are_rejected` | CI run |
| URS-04 | dbt test `unique` on `stg_openfda__reports.safety_report_id` | dbt run log |
| URS-05 | *Phase 3* | — |
| URS-06 | CI `terraform validate`; branch protection on `main` | GitHub settings |
