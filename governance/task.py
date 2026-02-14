from governance.engine import check_violation
from .models import Policy, PolicyAssignment, PolicyViolation, AuditLog
from celery import shared_task


def _policy_target(policy: Policy) -> str:
    rules = policy.rules if isinstance(policy.rules, dict) else {}
    target = str(rules.get("target", "")).strip().lower()
    if target in {"deployment", "monitoring", "both"}:
        return target
    # Backward-compatible fallback for policies created before target existed.
    return "monitoring" if policy.policy_type == "drift" else "deployment"


def _log_matches_target(log: AuditLog, target: str) -> bool:
    action = (log.action or "").upper()
    service = (log.service or "").lower()

    if target == "both":
        return True
    if target == "deployment":
        return action in {"DEPLOY", "STOP"}
    # monitoring
    return action == "DRIFT_DETECTED" or "monitor" in service or "drift" in service


@shared_task
def run_policy_engine():
    policies = Policy.objects.filter(is_active=True)
    if not policies.exists():
        return

    for policy in policies:
        assigned_deployment_ids = list(
            PolicyAssignment.objects.filter(policy=policy).values_list("deployment_id", flat=True)
        )
        # Enforce only on deployments where the policy is explicitly applied.
        if not assigned_deployment_ids:
            continue

        target = _policy_target(policy)
        recent_logs = AuditLog.objects.filter(deployment_id__in=assigned_deployment_ids).order_by("-timestamp")[:100]

        for log in recent_logs:
            if not _log_matches_target(log, target):
                continue

            violated = check_violation(log.metadata, policy.rules)
            if violated:
                PolicyViolation.objects.create(
                    deployment=log.deployment,
                    policy=policy,
                    violation_type=log.action,
                    severity=log.severity,
                )

