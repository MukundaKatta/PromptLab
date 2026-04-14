# PromptLab — Prompt experimentation workspace — A/B testing prompt variants with statistical significance testing

Prompt experimentation workspace — A/B testing prompt variants with statistical significance testing. PromptLab gives you a focused, inspectable implementation of that idea.

## Why PromptLab

PromptLab exists to make this workflow practical. Prompt experimentation workspace — a/b testing prompt variants with statistical significance testing. It favours a small, inspectable surface over sprawling configuration.

## Features

- `Experiment` — exported from `src/promptlab/core.py`
- `Trial` — exported from `src/promptlab/core.py`
- `ExperimentResults` — exported from `src/promptlab/core.py`
- Included test suite
- Dedicated documentation folder

## Tech Stack

- **Runtime:** Python
- **Tooling:** Pydantic

## How It Works

The codebase is organised into `docs/`, `src/`, `tests/`. The primary entry points are `src/promptlab/core.py`, `src/promptlab/__init__.py`. `src/promptlab/core.py` exposes `Experiment`, `Trial`, `ExperimentResults` — the core types that drive the behaviour.

## Getting Started

```bash
pip install -e .
```

## Usage

```python
from promptlab.core import Experiment

instance = Experiment()
# See the source for the full API
```

## Project Structure

```
PromptLab/
├── .env.example
├── CONTRIBUTING.md
├── Makefile
├── README.md
├── docs/
├── pyproject.toml
├── src/
├── tests/
```
