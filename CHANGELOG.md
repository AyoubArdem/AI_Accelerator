# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Kubernetes orchestration commands in deployment CLI:
  - `deployment k8s-bootstrap`
  - `deployment k8s-preflight`
  - `deployment k8s-doctor`
  - `deployment k8s-deploy`
  - `deployment k8s-status`
  - `deployment k8s-scale`
  - `deployment k8s-hpa`
  - `deployment k8s-rollback`
  - `deployment k8s-delete`
- Governance violation action commands:
  - `governance resolve-violation`
  - `governance reopen-violation`
  - `governance resolve-all-violations`
- Session-aware violation action hints (current account context and visible IDs guidance).
- Monitoring sample ingestion option:
  - `monitoring samples --drop-last-column` for CSV label/target stripping.
- Runtime metrics endpoint (`GET /metrics`) and request/error counters for more accurate monitoring totals.

### Changed
- `governance metrics` command now supports filters/format:
  - `--deployment-id`, `--severity`, `--resolved`, `--format`
- `server stop` output now includes clear next-step guidance to restart server.
- Deployment list/details output now includes Kubernetes image hint (`model_deploy_<deployment_id>`).
- Improved Kubernetes config auto-recovery path:
  - path/env expansion for kubeconfig
  - best-effort `minikube update-context`
  - clearer remediation instructions.

### Fixed
- Traffic shadow friendly handling for feature-count mismatch errors.
- Governance auth/session error messages now avoid raw JWT payload noise.
- File upload retry after token refresh now rewinds stream to prevent empty-file uploads.
- Violation table now includes violation IDs to support resolve/reopen flows.

## [1.0.1] - 2026-02-27

### Changed
- Packaging/documentation alignment and CLI improvements since `1.0.0`.
- PyPI release update to `1.0.1`.

## [1.0.0] - 2026-02-25

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
- Admin service and CLI commands for user management and audit export.
- Password reset API, UI templates, and CLI (`aiac auth password-reset`).
- Model approval workflow (approve/reject/retire/list approvals) with deployment gating.
- Runtime capability endpoint and explainable decision help route in deployed apps.
- Packaging guardrails for required runtime assets (Dockerfiles) in wheels.
- Improved command documentation in `CONSOLE.md` and richer project/application explanations in `README.md`.

### Changed
- Upgraded deployment workflow UX in CLI:
  - prechecks before deployment
  - better progress tracking and status output
  - runtime service URL visibility after successful deploy/redeploy
- Enhanced drift detection UX with threshold profiles, history display, and watch mode.
- Expanded monitoring records/stats commands with better summaries and output formats.
- Standardized command examples to package-style usage (`aiac ...`).
- CLI auth/logout UX now clears token file on logout success.
- `governance apply-policy` output now shows `applied_by` username when available.
- Server stop now cleans up the server log file.
- Redeploy command output is now friendlier and more focused.

### Fixed
- Friendlier error handling across deployment, monitoring, and governance commands.
- Better empty-state messaging for list views (alerts, violations, records, logs).
- Policy application UX improvements (prompting and duplicate-assignment feedback).
- README formatting/encoding cleanup and metadata example rendering.
- Packaging/runtime issues that caused missing Dockerfiles in installed distributions.

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
