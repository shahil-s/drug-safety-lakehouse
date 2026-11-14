# ADR-0001 — GCP as the primary platform

- **Status:** Accepted
- **Date:** 2026-11-14

## Context
The platform needs streaming and batch ingestion, a governed warehouse, orchestration, and ML/AI services.
Many life-sciences companies run Databricks or Snowflake, often on AWS, so the design should avoid lock-in where practical.

## Decision
Use GCP as the primary platform (Pub/Sub, Dataflow, Cloud Composer, BigQuery, Vertex AI).
Keep the portable layers open:
- **Storage format:** Apache Iceberg via BigLake, so tables are readable by Spark, Snowflake, or Databricks.
- **Transformations:** dbt, which runs on BigQuery, Snowflake, and Databricks with minimal changes.
- **Heavy processing:** PySpark on Dataproc Serverless, so the same code runs on Databricks.

## Alternatives considered
| Option | Pros | Cons |
|---|---|---|
| Databricks on AWS | Common in big pharma; Unity Catalog | Less depth from production experience; cost for a personal project |
| Snowflake | Common in pharma; simple ops | Weaker streaming story; trial-limited |
| GCP-native only (BigQuery tables, no Iceberg) | Simplest | Locks data into one engine |

## Consequences
- Iceberg and dbt make a later migration to Databricks or Snowflake a mapping exercise, not a rewrite.
- BigLake Iceberg tables have some feature gaps compared with native BigQuery tables; revisit as they mature.
