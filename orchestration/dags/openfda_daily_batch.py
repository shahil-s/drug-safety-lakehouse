"""Daily openFDA batch load (Cloud Composer / Airflow 2).

Flow: pull reports received on the logical date → raw bucket → BigQuery raw table → dbt build.

openFDA publishes with a lag, so each run loads the window ending LAG_DAYS before the logical date.
Re-running a date is safe: every run gets a new ingest_id, and staging de-duplicates
by report version.

Status: skeleton. Wire up the TODOs in Phase 2.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

LAG_DAYS = 14

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}


@dag(
    dag_id="openfda_daily_batch",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["pharmacovigilance", "openfda", "batch"],
)
def openfda_daily_batch():
    @task
    def extract_to_raw(ds: str | None = None) -> str:
        from drug_safe.config import Settings
        from drug_safe.ingestion.cli import run

        window = date.fromisoformat(ds) - timedelta(days=LAG_DAYS)
        audit = run(window, window, max_records=None, settings=Settings.from_env())
        if not audit.reconciled:
            raise ValueError(f"Run {audit.run_id} did not reconcile record counts")
        return audit.run_id

    # TODO(phase 2): GCSToBigQueryOperator loading
    #   {raw_bucket}/openfda/drug_event/.../ingest_id={run_id}/*.jsonl
    #   into raw.openfda_adverse_events (WRITE_APPEND), then load the audit record.

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="cd /home/airflow/gcs/dags/dbt && dbt build --select staging",
    )

    extract_to_raw() >> dbt_build


openfda_daily_batch()
