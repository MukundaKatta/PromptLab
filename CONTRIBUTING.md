# Contributing to PromptLab

Thanks for your interest in contributing! Here is how to get started.

## Development Setup

```bash
git clone https://github.com/officethree/PromptLab.git
cd PromptLab
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
make test
# or
python -m pytest tests/ -v
```

## Code Style

- We use **Ruff** for linting and formatting. Run `make lint` and `make format` before submitting.
- Target Python 3.10+.
- Use Pydantic models for data structures.
- Keep the dependency footprint minimal.

## Pull Requests

1. Fork the repo and create a feature branch.
2. Write tests for any new functionality.
3. Ensure all tests pass (`make test`) and linting is clean (`make lint`).
4. Open a PR with a clear description of what changed and why.

## Reporting Issues

Open a GitHub issue with:
- Steps to reproduce
- Expected vs. actual behaviour
- Python version and OS

## License

By contributing you agree that your contributions will be licensed under the MIT License.
