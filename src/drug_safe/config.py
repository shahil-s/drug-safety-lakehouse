"""Runtime configuration, read from environment variables.

Keeping config in the environment (not in code) means the same artifact runs in dev and prod,
which is part of the change-control story: code is promoted, not edited.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    env: str
    gcp_project: str | None
    raw_root: str
    openfda_api_key: str | None
    actor: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            env=os.getenv("DRUG_SAFE_ENV", "dev"),
            gcp_project=os.getenv("GCP_PROJECT"),
            # Local path for development, gs://bucket for cloud runs.
            raw_root=os.getenv("DRUG_SAFE_RAW_ROOT", "./data/raw"),
            openfda_api_key=os.getenv("OPENFDA_API_KEY"),
            # Who/what is running the pipeline (ALCOA+: Attributable).
            actor=os.getenv("DRUG_SAFE_ACTOR", os.getenv("USER", "unknown")),
        )
