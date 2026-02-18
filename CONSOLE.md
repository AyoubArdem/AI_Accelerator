# AIAC Console Command Reference

This document lists all currently available CLI commands and their options.

## Run Forms

Use this form:

```bash
aiac <group> <command> [options]
```

## Command Groups

- `auth`
- `deployment`
- `monitoring`
- `governance`

## Quick Help

```bash
aiac --help
aiac auth --help
aiac deployment --help
aiac monitoring --help
aiac governance --help
```

## auth

### `auth register`
Register a new user.

Options:
- `--email` (prompted if omitted)
- `--username` (prompted if omitted)
- `--password` (prompted, hidden)
- `--role` (prompted)

Example:
```bash
aiac auth register --email user@example.com --username user1 --password secret --role client
```

### `auth login`
Login and save access/refresh tokens.

Options:
- `--email` (prompted)
- `--password` (prompted, hidden)

Example:
```bash
aiac auth login --email user@example.com --password secret
```

### `auth logout`
Logout using refresh token (or saved token if blank).

Options:
- `--refresh-token` (prompted, hidden)

Example:
```bash
aiac auth logout
```

### `auth me`
Show current authenticated user info.

Example:
```bash
aiac auth me
```

### `auth token-show`
Verify credentials then show masked saved tokens.

Options:
- `--email` (prompted)
- `--password` (prompted, hidden)

Example:
```bash
aiac auth token-show --email user@example.com --password secret
```

## deployment

### `deployment create-project-deployment`
Create a new project.

Options:
- `--owner-id` (prompted)
- `--name` (prompted)
- `--description` (prompted)

Example:
```bash
aiac deployment create-project-deployment
```

### `deployment list-projects`
List all projects.

Example:
```bash
aiac deployment list-projects
```

### `deployment delete-project`
Delete a project.

Options:
- `--project-id` (prompted)
- `--confirm/--no-confirm` (default confirm)

Example:
```bash
aiac deployment delete-project --project-id 2 --no-confirm
```

### `deployment create-model-version`
Create model version from file upload.

Options:
- `--project-id` (prompted)
- `--description` (prompted)
- `--field-file-path` (prompted)

Example:
```bash
aiac deployment create-model-version --project-id 1 --description "v1" --field-file-path model.pkl
```

### `deployment list-model-versions`
List all model versions.

Example:
```bash
aiac deployment list-model-versions
```

### `deployment delete-model-version`
Delete a model version.

Options:
- `--model-version-id` (prompted)
- `--confirm/--no-confirm` (default confirm)

Example:
```bash
aiac deployment delete-model-version --model-version-id 4 --no-confirm
```

### `deployment deploy-model-version`
Deploy a model version and optionally track progress.

Options:
- `--user-id` (prompted)
- `--model-version-id` (prompted)
- `--port` (prompted)
- `--start-worker/--no-start-worker` (default `--start-worker`)
- `--wait/--no-wait` (default `--wait`)
- `--poll-interval-seconds` (default `2`)
- `--timeout-seconds` (default `900`)
- `--precheck/--no-precheck` (default `--precheck`)
- `--check-local-port/--no-check-local-port` (default `--check-local-port`)
- `--format, -f` (`text|json`, default `text`)
- `--redis-host` (default `localhost`)
- `--redis-port` (default `6379`)

Example:
```bash
aiac deployment deploy-model-version --user-id 14 --model-version-id 4 --port 6000 --format text
```

### `deployment redeploy-model`
Redeploy existing deployment.

Options:
- `--deployment-id` (prompted)
- `--start-worker/--no-start-worker` (default `--start-worker`)
- `--wait/--no-wait` (default `--wait`)
- `--timeout-seconds` (default `900`)
- `--redis-host` (default `localhost`)
- `--redis-port` (default `6379`)

Example:
```bash
aiac deployment redeploy-model --deployment-id 20
```

### `deployment stop-deployment`
Stop a deployment.

Options:
- `--deployment-id` (prompted)

Example:
```bash
aiac deployment stop-deployment --deployment-id 20
```

### `deployment delete-deployment`
Delete a deployment.

Options:
- `--deployment-id` (prompted)
- `--confirm/--no-confirm` (default confirm)

Example:
```bash
aiac deployment delete-deployment --deployment-id 20 --no-confirm
```

### `deployment list-deployments`
List all deployments.

Example:
```bash
aiac deployment list-deployments
```

### `deployment get-deployment-details`
Show deployment details + runtime URLs.

Options:
- `--deployment-id` (prompted)

Example:
```bash
aiac deployment get-deployment-details --deployment-id 20
```

### `deployment advisor`
Advanced advisor report (risk/strategy/metrics).

Options:
- `--deployment-id` (prompted)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac deployment advisor --deployment-id 20 --format table
```

### `deployment services`
Show runtime service URLs and optional health probe.

Options:
- `--deployment-id` (prompted)
- `--probe/--no-probe` (default `--no-probe`)
- `--timeout` (probe timeout, default `2`)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac deployment services --deployment-id 20 --probe --format table
```

### `deployment traffic-shadow`
Compare active model vs candidate model on recent samples.

Options:
- `--deployment-id` (prompted)
- `--candidate, -c` (required candidate model version id)
- `--samples, -s` (default `200`, clamped `10..1000`)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac deployment traffic-shadow --deployment-id 20 --candidate 3 --samples 300 --format json
```

### `deployment explain-decision`
Run explainable decision inference with configurable refusal checks.

Options:
- `--deployment-id` (prompted)
- `--features, -x` (JSON numeric feature array)
- `--min-confidence` (optional refusal threshold)
- `--min-margin` (optional refusal threshold)
- `--blocked-labels` (comma-separated labels to refuse)
- `--fallback/--no-fallback` (default `--fallback`; use `/predict` if `/predict-decision` is missing)
- `--timeout` (request timeout seconds, default `10`)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac deployment explain-decision --deployment-id 20 --features "[0.1, 0.2, 0.3]" --min-confidence 0.7 --min-margin 0.15 --blocked-labels "denied,blocked" --format table
```

Result interpretation:
- `decision=approved`: runtime policy checks passed.
- `decision=refused`: runtime policy checks rejected the request.
- `decision=approved_with_fallback`: `/predict-decision` was unavailable, so CLI used `/predict`; refusal checks were **not** enforced.
- `confidence=None` and `margin=None`: model/runtime did not provide probability scores, so confidence-margin checks could not be evaluated.

Output includes:
- Decision summary table
- Interpretation block (plain-language explanation)
- Reasons list
- Top probabilities (if available)
- Linear feature contributions and contribution summary (if available)

Troubleshooting:
- If you see `runtime request failed: 404` or fallback messages, your deployment runtime is likely outdated. Redeploy the model to enable `/predict-decision`.
- If compliance/safety requires strict refusal enforcement, run with `--no-fallback` so the command fails instead of using `/predict`.
- If `confidence`/`margin` remain `None` after redeploy, your model may not expose probabilities; use models/pipelines with `predict_proba` for confidence-based refusal checks.

## monitoring

### `monitoring deploy-stats`
Live or one-shot deployment stats + health warnings.

Options:
- `--deployment-id` (prompted)
- `--format, -f` (`table|json`, default `table`)
- `--watch, -w` (continuous polling)
- `--interval, -i` (seconds, default `5`)
- `--iterations` (`0` = infinite)
- `--cpu-warn` (default `85.0`)
- `--ram-warn` (default `85.0`)
- `--latency-warn` (default `500.0`)
- `--error-rate-warn` (default `5.0`)

Example:
```bash
aiac monitoring deploy-stats --deployment-id 4 --watch --interval 10
```

### `monitoring deploy-records`
Show monitoring records with summary; supports table/json/csv.

Options:
- `--deployment-id` (prompted)
- `--format, -f` (`table|json|csv`, default `table`)
- `--limit, -l` (default `50`)
- `--watch, -w`
- `--interval, -i` (default `5`)
- `--iterations` (`0` = infinite)
- `--cpu-warn` (default `85.0`)
- `--ram-warn` (default `85.0`)
- `--latency-warn` (default `500.0`)

Example:
```bash
aiac monitoring deploy-records --deployment-id 10 --format table
```

### `monitoring alert`
List alerts for deployment.

Options:
- `--deployment-id` (prompted)

Example:
```bash
aiac monitoring alert --deployment-id 18
```

### `monitoring resolve-alert`
Resolve alert by id, or choose from deployment alerts.

Options:
- `--alert-id, -a` (alert UUID)
- `--deployment-id, -d` (to select alert interactively)
- `--include-resolved` (include already resolved alerts when selecting)
- `--yes, -y` (skip confirmation)

Examples:
```bash
aiac monitoring resolve-alert --alert-id <uuid>
aiac monitoring resolve-alert --deployment-id 18
```

### `monitoring health-report`
Advanced health report with trends/recommendations.

Options:
- `--deployment-id` (prompted)
- `--window, -w` (records window, default `50`)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac monitoring health-report --deployment-id 4 --window 100
```

### `monitoring cost-intelligence`
Advanced FinOps report with monthly/annual cost estimation, efficiency scoring, budget variance, risk flags, and scenario projections.

Options:
- `--deployment-id` (prompted)
- `--window, -w` (default `200`)
- `--cpu-hour-rate` (default `0.05`)
- `--gb-ram-hour-rate` (default `0.01`)
- `--request-million-rate` (default `1.0`)
- `--ram-reference-gb` (default `4.0`)
- `--budget` (optional monthly budget for variance analysis)
- `--target-cpu-utilization` (default `65.0`)
- `--target-ram-utilization` (default `70.0`)
- `--scenarios/--no-scenarios` (default `--scenarios`)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac monitoring cost-intelligence --deployment-id 4 --window 300 --budget 250 --target-cpu-utilization 65 --target-ram-utilization 70 --scenarios --format table
```

### `monitoring detect-drift`
Drift detection with profiles, thresholds, history, and watch mode.

Options:
- `--model-version-id` (prompted)
- `--profile, -p` (`sensitive|balanced|conservative`, default `balanced`)
- `--kl-threshold` (override)
- `--wasserstein-threshold` (override)
- `--ks-threshold` (override)
- `--chi-square-threshold` (override)
- `--explain/--no-explain` (default explain)
- `--history` (show previous scans)
- `--history-limit` (default `5`)
- `--watch, -w`
- `--interval, -i` (default `30`)
- `--iterations` (`0` = infinite)

Example:
```bash
aiac monitoring detect-drift --model-version-id 4 --profile balanced --history
```

### `monitoring samples`
Upload/validate sample data for monitoring and drift.

Options:
- `--model-version-id` (prompted)
- `--data-samples` (JSON array string)
- `--samples-file` (JSON or CSV file)
- `--csv-file` (CSV file)
- `--format, -f` (`auto|json|csv`, for `--samples-file`, default `auto`)
- `--chunk-size` (`0` single request)
- `--dry-run` (validate only)
- `--preview` (show first N samples, default `3`)
- `--strict-shape` (require same vector dimension)

Examples:
```bash
aiac monitoring samples --model-version-id 4 --data-samples "[0.1, 0.2, 0.3]"
aiac monitoring samples --model-version-id 4 --samples-file samples.json
aiac monitoring samples --model-version-id 4 --csv-file samples.csv --chunk-size 100
```

## governance

### `governance create-policy`
Create policy. If `--rules` is omitted, CLI prompts interactive metadata template (`deployment|monitoring|both`) and rules.

Arguments:
- `name` (required)
- `policy_type` (required)

Options:
- `--description, -d` (optional text)
- `--rules, -r` (JSON object string)

Examples:
```bash
aiac governance create-policy model deployment
aiac governance create-policy model deployment -d "prod policy" -r '{"max_latency_ms": 500}'
```

### `governance list-policies`
List policies with owner, creator, created_at, description, and rules preview.

Example:
```bash
aiac governance list-policies
```

### `governance delete-policy`
Delete policy by id.

Arguments:
- `policy_id` (required)

Example:
```bash
aiac governance delete-policy 3
```

### `governance apply-policy`
Apply policy to deployment.

Arguments:
- `policy_id` (required)
- `deployment_id` (optional; if omitted, prompt asks)

Examples:
```bash
aiac governance apply-policy 3 14
aiac governance apply-policy 3
```

### `governance view-violations`
View policy violations.

Example:
```bash
aiac governance view-violations
```

### `governance metrics`
Show aggregated violation metrics.

Example:
```bash
aiac governance metrics
```

### `governance run-policy-engine`
Trigger policy engine execution immediately.

Example:
```bash
aiac governance run-policy-engine
```

### `governance debug-policy-engine`
Debug why violations are/aren't generated for a policy.

Options:
- `--policy, -p` (required policy id)
- `--deployment, -d` (optional deployment filter)
- `--limit, -l` (default `50`, clamped `1..200`)

Example:
```bash
aiac governance debug-policy-engine --policy 3 --deployment 14 --limit 100
```

### `governance policy-insights`
Advanced coverage/risk insights with recommendations.

Options:
- `--policy, -p` (optional)
- `--days, -d` (default `7`, clamped `1..90`)
- `--format, -f` (`table|csv`, default `table`)

Examples:
```bash
aiac governance policy-insights
aiac governance policy-insights --policy 3 --days 30 --format csv
```

### `governance alert-logs`
View governance alert logs.

Example:
```bash
aiac governance alert-logs
```

## Notes

- Most required values are prompted interactively if omitted.
- Booleans can be toggled with `--flag/--no-flag` for Typer bool options.
- For the most accurate local signature at any time:

```bash
aiac <group> <command> --help
```


