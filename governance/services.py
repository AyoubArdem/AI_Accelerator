from datetime import timedelta
from django.utils import timezone
from .models import Policy, PolicyAssignment, PolicyViolation
from .task import _policy_target


def _risk_level(unresolved_total: int, unresolved_high: int) -> str:
    if unresolved_high > 0:
        return "critical"
    if unresolved_total >= 5:
        return "high"
    if unresolved_total >= 1:
        return "medium"
    return "low"


def _recommendations(assignment_count: int, unresolved_total: int, unresolved_high: int) -> list[str]:
    recs = []
    if assignment_count == 0:
        recs.append("Assign this policy to at least one deployment.")
    if unresolved_high > 0:
        recs.append("Prioritize high-severity unresolved violations.")
    if unresolved_total > 0:
        recs.append("Review unresolved violations and update policy thresholds if needed.")
    if assignment_count > 0 and unresolved_total == 0:
        recs.append("No unresolved violations. Keep monitoring and review weekly.")
    return recs


def get_policy_insights_for_user(user, is_admin: bool, policy_id: int | None = None, days: int = 7):
    policies = Policy.objects.all().order_by("-created_at")
    if not is_admin:
        policies = policies.filter(user=user)
    if policy_id is not None:
        policies = policies.filter(id=policy_id)

    since = timezone.now() - timedelta(days=max(1, days))
    insights = []

    for policy in policies:
        assignments_qs = PolicyAssignment.objects.filter(policy=policy)
        if not is_admin:
            assignments_qs = assignments_qs.filter(deployment__user=user)

        assignment_count = assignments_qs.count()
        deployment_ids = list(assignments_qs.values_list("deployment_id", flat=True))

        violations_qs = PolicyViolation.objects.filter(policy=policy, created_at__gte=since)
        if not is_admin:
            violations_qs = violations_qs.filter(deployment__user=user)

        total_recent = violations_qs.count()
        unresolved_total = violations_qs.filter(resolved=False).count()
        unresolved_high = violations_qs.filter(resolved=False, severity="high").count()

        insights.append(
            {
                "policy_id": policy.id,
                "policy_name": policy.name,
                "policy_type": policy.policy_type,
                "target": _policy_target(policy),
                "is_active": policy.is_active,
                "assignment_count": assignment_count,
                "deployment_ids": deployment_ids,
                "recent_violations": total_recent,
                "unresolved_violations": unresolved_total,
                "high_unresolved_violations": unresolved_high,
                "risk_level": _risk_level(unresolved_total, unresolved_high),
                "recommendations": _recommendations(assignment_count, unresolved_total, unresolved_high),
            }
        )

    return {
        "days": max(1, days),
        "policy_count": len(insights),
        "items": insights,
    }
