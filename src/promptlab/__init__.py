"""PromptLab -- Prompt experimentation workspace for A/B testing prompt variations."""

__version__ = "0.1.0"

from .core import Experiment, ExperimentResults, PromptLab, Trial

__all__ = [
    "PromptLab",
    "Experiment",
    "Trial",
    "ExperimentResults",
]
