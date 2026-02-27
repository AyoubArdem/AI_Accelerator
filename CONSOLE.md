# AIAC Console Command Reference

This document lists all currently available CLI commands and their options.

## Run Forms

Use this form:

```bash
aiac <group> <command> [options]
```

## Command Groups

- `auth`
- `server`
- `deployment`
- `monitoring`
- `governance`
- `admin`

## Quick Help

```bash
aiac --help
aiac auth --help
aiac server --help
aiac deployment --help
aiac monitoring --help
aiac governance --help
aiac admin --help
```

## server

### `server --help`

```bash
 aiac server --help
```

```text
Usage: aiac server [OPTIONS] COMMAND [ARGS]...

Local API server commands

Options:
  --help  Show this message and exit.

Commands:
  run   Run the AI Accelerator Django API server.
```

### `server run`
Run the AI Accelerator Django API server.

Options:
- `--host` (default `127.0.0.1`)
- `--port` (default `8000`)
- `--no-reload/--reload` (default `--no-reload`)
- `--background/--foreground` (default `--background`)
- `--migrate/--no-migrate` (default `--migrate`)

Example:
```bash
aiac server run --host 127.0.0.1 --port 8000 --no-reload
```

Notes:
- By default, AIAC runs database migrations automatically before server startup.

### `server status`
Show local background server status.

Example:
```bash
aiac server status
```

### `server stop`
Stop local background server started by `aiac server run`.

Example:
```bash
aiac server stop
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

### `auth password-reset`
Request a secure password reset email.

Example:
```bash
aiac auth password-reset --email user@example.com
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

Options:
- `--status` (filter by status)
- `--project-id` (filter by project)
- `--deployed-only` (only deployed)

Example:
```bash
aiac deployment list-model-versions
aiac deployment list-model-versions --status approved
```

### `deployment approve-model-version`
Approve a model version for deployment.
This marks the version as approved so it can be deployed.

Options:
- `--model-version-id` (prompted)
- `--note` (optional note)

Example:
```bash
aiac deployment approve-model-version --model-version-id 4 --note "QA passed"
```

### `deployment reject-model-version`
Reject a model version.
This blocks the version from deployment until it is approved again.

Options:
- `--model-version-id` (prompted)
- `--note` (optional note)

Example:
```bash
aiac deployment reject-model-version --model-version-id 4 --note "Missing bias checks"
```

### `deployment retire-model-version`
Retire a model version.
This keeps the version in history but marks it as retired so it should not be deployed again.

Options:
- `--model-version-id` (prompted)
- `--note` (optional note)

Example:
```bash
aiac deployment retire-model-version --model-version-id 4 --note "Replaced by v5"
```

### `deployment list-model-approvals`
List approval history for a model version.

Options:
- `--model-version-id` (prompted)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac deployment list-model-approvals --model-version-id 4
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
- `--auto-preflight/--no-auto-preflight` (default `--auto-preflight`)
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

### `deployment preflight`
Run pre-deployment checks before deploying a model.

Checks:
- API server reachability
- Docker CLI and Docker daemon
- Redis reachability
- Celery worker availability
- Optional model version existence
- Optional local port availability

Options:
- `--model-version-id` (optional)
- `--port` (optional)
- `--redis-host` (default `localhost`)
- `--redis-port` (default `6379`)
- `--check-local-port/--no-check-local-port` (default `--check-local-port`)
- `--format, -f` (`table|json`, default `table`)

Examples:
```bash
aiac deployment preflight --model-version-id 4 --port 6000
aiac deployment preflight --format json
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

Runtime capabilities:
- Runtime exposes `GET /capabilities` for NLP/CV support and dependency checks.
- Example:
```bash
curl http://127.0.0.1:8003/capabilities
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

Result interpretation:
- `Deployment`: live deployment being evaluated.
- `Current Model`: model version currently serving traffic.
- `Candidate`: model version tested in shadow mode.
- `Samples`: number of evaluation samples used.
- `Recommendation`:
  - `promote_candidate`: candidate is safe/better to promote.
  - `keep_current`: keep current model.
  - `review_required`: results are mixed; validate manually.

Shadow metrics:
- `Match Rate`: fraction of samples where current and candidate predictions match (`matches / samples`).
- `Matches`: count of matching predictions.
- `Current Latency (ms)`: average inference latency of current model.
- `Candidate Latency (ms)`: average inference latency of candidate model.
- `Latency Ratio`: `candidate_latency / current_latency`.
  - `< 1.0`: candidate is faster.
  - `= 1.0`: similar speed.
  - `> 1.0`: candidate is slower.
- `Avg Abs Diff`: average absolute prediction difference (mainly for numeric/regression outputs). `0.0` means no numeric deviation on tested samples.

### `deployment k8s-deploy`
Deploy AI runtime image to Kubernetes and expose a Service.

Options:
- `--deployment-id` (prompted)
- `--image, -i` (required container image)
- `--namespace, -n` (default `default`)
- `--replicas, -r` (default `1`)
- `--container-port` (default `8000`)
- `--service-port` (default `80`)
- `--service-type` (`ClusterIP|NodePort|LoadBalancer`, default `ClusterIP`)
- `--rollout-strategy` (`RollingUpdate|Recreate`, default `RollingUpdate`)
- `--max-unavailable` (default `25%`, RollingUpdate only)
- `--max-surge` (default `25%`, RollingUpdate only)
- `--kubeconfig` (optional)
- `--context` (optional)

Notes:
- If kubeconfig is missing, AIAC tries automatic Minikube context refresh (`minikube update-context`) before failing.
- On PowerShell, explicit kubeconfig path format:
  - `--kubeconfig $env:USERPROFILE\\.kube\\config`

Example:
```bash
aiac deployment k8s-deploy --deployment-id 20 --image ghcr.io/acme/model-runtime:1.0 --namespace ml --replicas 2 --service-type LoadBalancer
aiac deployment k8s-deploy --deployment-id 20 --image ghcr.io/acme/model-runtime:1.0 --rollout-strategy RollingUpdate --max-unavailable 1 --max-surge 1
```

### `deployment k8s-preflight`
Run Kubernetes readiness checks before running other k8s commands.

Checks include:
- Kubernetes SDK installed
- kubeconfig/context load
- API reachability
- namespace existence
- optional deployment resource existence

Options:
- `--namespace, -n` (default `default`)
- `--deployment-id` (optional)
- `--kubeconfig` (optional)
- `--context` (optional)

Examples:
```bash
aiac deployment k8s-preflight
aiac deployment k8s-preflight --namespace ml --deployment-id 20
```

### `deployment k8s-bootstrap`
Install Minikube (Windows/winget) and start a local Kubernetes cluster.

Options:
- `--install/--no-install` (default `--install`)
- `--driver` (default `docker`)
- `--profile` (optional Minikube profile)

Examples:
```bash
aiac deployment k8s-bootstrap
aiac deployment k8s-bootstrap --no-install --driver docker
aiac deployment k8s-bootstrap --profile aiac-local
```

### `deployment k8s-doctor`
Diagnose Kubernetes environment and print exact recovery commands.

Checks include:
- Docker CLI availability
- `kubectl` and `minikube` availability
- Python Kubernetes SDK installation
- Minikube cluster status
- kubeconfig/API reachability

Options:
- `--kubeconfig` (optional)
- `--context` (optional)

Examples:
```bash
aiac deployment k8s-doctor
aiac deployment k8s-doctor --kubeconfig $env:USERPROFILE\.kube\config
```

Local setup (Minikube + Docker):
- Prerequisite: Docker Desktop/Engine must be running.
- Install Minikube:
```bash
winget install Kubernetes.minikube
```
- Start a local cluster using Docker driver:
```bash
minikube start --driver=docker
```
- Verify cluster:
```bash
kubectl cluster-info
kubectl get nodes
```
- Then run AIAC preflight:
```bash
aiac deployment k8s-preflight
```

### `deployment k8s-status`
Show Kubernetes deployment/service status for an AIAC deployment ID.

Options:
- `--deployment-id` (prompted)
- `--namespace, -n` (default `default`)
- `--kubeconfig` (optional)
- `--context` (optional)

Example:
```bash
aiac deployment k8s-status --deployment-id 20 --namespace ml
```

### `deployment k8s-scale`
Scale Kubernetes replicas for an AIAC deployment ID.

Options:
- `--deployment-id` (prompted)
- `--replicas, -r` (prompted)
- `--namespace, -n` (default `default`)
- `--kubeconfig` (optional)
- `--context` (optional)

Example:
```bash
aiac deployment k8s-scale --deployment-id 20 --replicas 4 --namespace ml
```

### `deployment k8s-hpa`
Create or update Horizontal Pod Autoscaler for an AIAC deployment.

Options:
- `--deployment-id` (prompted)
- `--min` (default `1`)
- `--max` (prompted)
- `--cpu-percent` (default `70`)
- `--namespace, -n` (default `default`)
- `--kubeconfig` (optional)
- `--context` (optional)

Example:
```bash
aiac deployment k8s-hpa --deployment-id 20 --min 2 --max 8 --cpu-percent 65 --namespace ml
```

### `deployment k8s-delete`
Delete Kubernetes Deployment and Service created by `k8s-deploy`.

Options:
- `--deployment-id` (prompted)
- `--namespace, -n` (default `default`)
- `--yes` (skip confirmation)
- `--kubeconfig` (optional)
- `--context` (optional)

Behavior:
- Deletes HPA (`<name>-hpa`) if present.
- Deletes Service and Deployment.

Example:
```bash
aiac deployment k8s-delete --deployment-id 20 --namespace ml --yes
```

### `deployment k8s-rollback`
Rollback Kubernetes deployment image to a previous ReplicaSet revision.

Options:
- `--deployment-id` (prompted)
- `--namespace, -n` (default `default`)
- `--to-revision` (default `0`: auto-select previous revision)
- `--yes` (skip confirmation)
- `--kubeconfig` (optional)
- `--context` (optional)

Examples:
```bash
aiac deployment k8s-rollback --deployment-id 20 --namespace ml
aiac deployment k8s-rollback --deployment-id 20 --namespace ml --to-revision 3 --yes
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
- `--include-resolved` (include resolved alerts)
- `--limit, -l` (max alerts displayed)
- `--only-type` (filter by alert type)
- `--only-severity` (filter by severity: low|medium|high)
- `--since-hours` (only alerts in last N hours)
- `--since` (only alerts after ISO timestamp)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac monitoring alert --deployment-id 18
aiac monitoring alert --deployment-id 18 --only-severity high --since-hours 24
aiac monitoring alert --deployment-id 18 --only-type latency --since 2026-02-25T10:00:00Z
```

### `monitoring resolve-alert`
Resolve alert by id, or choose from deployment alerts.

Options:
- `--alert-id, -a` (alert UUID)
- `--deployment-id, -d` (to select alert interactively)
- `--include-resolved` (include already resolved alerts when selecting)
- `--yes, -y` (skip confirmation)

Notes:
- After resolving interactively, CLI prints the resolved alert summary (type/message/deployment).

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
- `--drop-last-column` (CSV only; removes last column per row, useful for label/target column)
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
aiac monitoring samples --model-version-id 4 --csv-file samples.csv --drop-last-column --preview 20
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

### `governance resolve-violation`
Mark a violation as resolved.

Options:
- `--violation-id` (prompted)

Example:
```bash
aiac governance resolve-violation --violation-id 12
```

### `governance reopen-violation`
Reopen a previously resolved violation.

Options:
- `--violation-id` (prompted)

Example:
```bash
aiac governance reopen-violation --violation-id 12
```

### `governance resolve-all-violations`
Resolve all unresolved violations. You can filter by deployment and/or policy.

Options:
- `--deployment-id` (optional)
- `--policy-id` (optional)

Examples:
```bash
aiac governance resolve-all-violations
aiac governance resolve-all-violations --deployment-id 14
aiac governance resolve-all-violations --policy-id 3
aiac governance resolve-all-violations --deployment-id 14 --policy-id 3
```

### `governance metrics`
Show aggregated violation metrics.

Options:
- `--deployment-id` (optional filter)
- `--severity` (`low|medium|high`, optional)
- `--resolved` (`all|true|false`, default `all`)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac governance metrics
aiac governance metrics --deployment-id 14 --severity high --resolved false
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

## admin

### `admin list-users`
List all users (admin only).

Options:
- `--role` (filter by role)
- `--active` (only active users)
- `--inactive` (only inactive users)
- `--staff` (only staff users)
- `--email` (filter by email substring)
- `--username` (filter by username substring)
- `--limit, -l` (limit results)
- `--offset` (skip first N results)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac admin list-users
aiac admin list-users --role admin --active
aiac admin list-users --email "@gmail.com" --limit 20
aiac admin list-users --username dad --offset 10
```

### `admin user`
Show details for one user.

Options:
- `--user-id` (prompted)

Example:
```bash
aiac admin user --user-id 7
```

### `admin promote-admin`
Promote a user to admin.

Options:
- `--user-id` (prompted)

Example:
```bash
aiac admin promote-admin --user-id 7
```

### `admin demote-admin`
Demote a user to client.

Options:
- `--user-id` (prompted)

Example:
```bash
aiac admin demote-admin --user-id 7
```

### `admin activate-user`
Activate a user account.

Options:
- `--user-id` (prompted)

Example:
```bash
aiac admin activate-user --user-id 7
```

### `admin deactivate-user`
Deactivate a user account.

Options:
- `--user-id` (prompted)

Example:
```bash
aiac admin deactivate-user --user-id 7
```

### `admin soft-delete-user`
Soft delete (deactivate) a user account.

Options:
- `--user-id` (prompted)

Example:
```bash
aiac admin soft-delete-user --user-id 7
```

### `admin reset-password`
Reset a user password.

Options:
- `--user-id` (prompted)
- `--password` (prompted, hidden)

Example:
```bash
aiac admin reset-password --user-id 7
```

### `admin list-audits`
List audit logs (admin only).

Options:
- `--limit, -l` (default `50`)
- `--format, -f` (`table|json`, default `table`)

Example:
```bash
aiac admin list-audits --limit 100
```

### `admin export-audits`
Export audit logs to CSV.

Options:
- `--out` (CSV file path, default `audit_logs.csv`)

Example:
```bash
aiac admin export-audits --out audit_logs.csv
```

### `admin export-audits-json`
Export audit logs to JSON.

Options:
- `--out` (JSON file path, default `audit_logs.json`)

Example:
```bash
aiac admin export-audits-json --out audit_logs.json
```

## Notes

- Most required values are prompted interactively if omitted.
- Booleans can be toggled with `--flag/--no-flag` for Typer bool options.
- For the most accurate local signature at any time:

```bash
aiac <group> <command> --help
```


