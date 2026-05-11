# Contributing to EvalForge

Thanks for wanting to contribute. EvalForge is built for the community and every contribution matters.

## Ways to contribute

- **Bug reports** — Open an issue with steps to reproduce
- **Feature requests** — Open an issue describing the use case
- **Code** — Pick up a good-first-issue or propose something new
- **Docs** — Fix typos, add examples, improve explanations
- **Examples** — Add a new example in `examples/`

## Development setup

```bash
git clone https://github.com/evalforge/evalforge.git
cd evalforge

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Copy env file
cp .env.example .env
# Fill in your GEMINI_API_KEY
```

## Running tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=evalforge --cov-report=term-missing

# Run a specific test file
pytest tests/test_models.py -v
```

## Code style

We use `ruff` for linting and formatting.

```bash
# Check
ruff check .

# Fix
ruff check . --fix

# Format
ruff format .
```

Pre-commit hooks run these automatically on every commit.

## Pull request process

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes
3. Add tests for new functionality
4. Run `pytest` and `ruff check .` — both must pass
5. Open a PR with a clear description of what you changed and why

## Good first issues

Look for issues tagged `good first issue`. These are scoped, well-defined tasks
that don't require deep knowledge of the codebase.

Current good first issues:
- Add LangSmith trace fetcher
- Add OpenAI as judge model option
- Add Slack notification on eval completion
- Improve cluster label accuracy

## Questions?

Open a discussion on GitHub or join our Discord.
