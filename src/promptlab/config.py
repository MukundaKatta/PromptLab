"""Configuration for PromptLab -- loaded from environment or constructor args."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Runtime configuration for PromptLab."""

    db_path: str = Field(default="promptlab.db", description="Path to the SQLite database file.")
    significance_level: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description="p-value threshold for statistical significance.",
    )

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from environment variables."""
        return cls(
            db_path=os.getenv("PROMPTLAB_DB_PATH", "promptlab.db"),
            significance_level=float(
                os.getenv("PROMPTLAB_SIGNIFICANCE_LEVEL", "0.05")
            ),
        )
