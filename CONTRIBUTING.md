# Contributing to AI Accelerator

Thanks for contributing to AI Accelerator. This guide explains how to propose changes, set up your environment, and submit high-quality pull requests.

## Code of Conduct

By participating, you agree to follow the project's code of conduct in `CODE_OF_CONDUCT.md` and  `CLA.md`.

## Ways to Contribute

- Fix bugs
- Add features
- Improve documentation
- Add or improve tests
- Improve developer tooling and automation

## Development Setup

### Prerequisites

- Python 3.8+
- Git
- Redis (recommended for async tasks)
- Docker (recommended for deployment/runtime workflows)

### Local Setup

```bash
git clone https://github.com/AyoubArdem/ai-accelerator.git
cd ai-accelerator

python -m venv env1
# Windows:
env1\Scripts\activate
# Linux/macOS:
# source env1/bin/activate

pip install -e .
pip install -e ".[dev]"

python manage.py migrate
python manage.py runserver
```

Optional:

```bash
python manage.py createsuperuser
```

## Branching and Workflow

1. Create a branch from `main`.
2. Keep each PR focused on one logical change.
3. Add tests for behavior changes.
4. Update docs for user-visible changes.

Branch naming examples:

- `feat/deployment-services`
- `fix/governance-duplicate-assignment`
- `docs/readme-cleanup`

## Coding Standards

- Follow PEP 8
- Format with `black`
- Keep imports clean and consistent
- Use clear names and small functions
- Add comments only when needed to explain non-obvious logic

Run formatting/linting before opening a PR:

```bash
black .
flake8 .
```

## Testing

Run tests locally before submitting:

```bash
pytest
python manage.py test
```

If your change touches CLI/API behavior, include tests or clear manual verification steps in the PR description.

## Documentation Requirements

When changing user-facing behavior, update the relevant docs:

- `README.md` for platform-level behavior
- `CONSOLE.md` for CLI command usage
- `CHANGELOG.md` under `Unreleased`

## Pull Request Guidelines

A good PR should include:

- What changed
- Why it changed
- How it was tested
- Any breaking change notes

Checklist before submit:

- [ ] Code builds/runs locally
- [ ] Tests pass locally
- [ ] Formatting/lint checks pass
- [ ] Docs updated (if needed)
- [ ] Changelog updated (if needed)

## Commit Messages

Use clear commit messages. Conventional commits are preferred:

```text
feat(scope): short summary
fix(scope): short summary
docs(scope): short summary
test(scope): short summary
chore(scope): short summary
```

## Reporting Bugs and Requesting Features

- Use GitHub Issues for bugs and feature requests.
- Include reproduction steps, expected behavior, and actual behavior.
- Add environment details when relevant (OS, Python version, command used).

## Security Issues

Do not post sensitive vulnerabilities publicly in Issues.
Follow `SECURITY.md` for responsible reporting.

## Review and Merge Process

1. Automated and manual checks are reviewed.
2. Maintainers may request changes.
3. Once approved, a maintainer merges the PR.

## License

By contributing, you agree that your contributions are licensed under the same license as this repository (`LICENSE`).
