# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Advanced deployment services endpoints and CLI commands:
  - `deployment advisor`
  - `deployment services`
  - `deployment traffic-shadow`
- Runtime URL bundle exposure for deployments (UI page, docs, redoc, health, predict).
- Monitoring advanced service endpoints and CLI commands:
  - `monitoring health-report`
  - `monitoring cost-intelligence`
- Governance advanced operations:
  - `governance run-policy-engine`
  - `governance debug-policy-engine`
  - `governance policy-insights`
- Interactive metadata-based policy rule generation in `governance create-policy` with scope support (`deployment`, `monitoring`, `both`).
- Improved command documentation in `CONSOLE.md` and richer project/application explanations in `README.md`.

### Changed
- Upgraded deployment workflow UX in CLI:
  - prechecks before deployment
  - better progress tracking and status output
  - runtime service URL visibility after successful deploy/redeploy
- Enhanced drift detection UX with threshold profiles, history display, and watch mode.
- Expanded monitoring records/stats commands with better summaries and output formats.
- Standardized command examples to package-style usage (`aiac ...`).

### Fixed
- Friendlier error handling across deployment, monitoring, and governance commands.
- Better empty-state messaging for list views (alerts, violations, records, logs).
- Policy application UX improvements (prompting and duplicate-assignment feedback).
- README formatting/encoding cleanup and metadata example rendering.

## [0.1.0] - 2026-02-02

### Added
- Initial AI Accelerator platform release.
- Django REST API foundation with JWT authentication.
- Core deployment, monitoring, and governance application modules.
- Project/model version management and initial deployment lifecycle support.
- AIAC command-line interface with interactive prompts.
- OpenAPI schema and interactive API docs.
- Docker-based local deployment support.
- Initial documentation set (`README`, `CONSOLE`, contribution/security/community files).

### Technical
- Django 5.2.8 + Django REST Framework.
- PostgreSQL/SQLite support.
- Redis and Celery integration.
- JWT-based authentication and authorization foundations.

---

## Types of Changes

- `Added` for new features
- `Changed` for changes in existing functionality
- `Deprecated` for soon-to-be removed features
- `Removed` for now removed features
- `Fixed` for any bug fixes
- `Security` in case of vulnerabilities
