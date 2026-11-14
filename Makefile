.PHONY: setup test lint fmt sample tf-init tf-plan dbt-build

TF_DIR := infra/terraform/envs/dev

setup:
	uv sync --group dev --group dbt --all-extras
	uv run pre-commit install

test:
	uv run pytest --cov=drug_safe --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .
	terraform fmt -recursive infra/terraform

# Pull a small sample (one day, 500 reports) to ./data/raw. No GCP needed.
sample:
	uv run python -m drug_safe.ingestion.cli --start 2024-01-02 --end 2024-01-02 --max-records 500

tf-init:
	cd $(TF_DIR) && terraform init -backend-config="bucket=$(TF_STATE_BUCKET)"

tf-plan:
	cd $(TF_DIR) && terraform plan -out=tfplan

dbt-build:
	uv run dbt build --project-dir dbt
