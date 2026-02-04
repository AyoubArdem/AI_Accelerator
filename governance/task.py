from governance.engine import check_violation
from .models import Policy,PolicyViolation,AuditLog
from deployment.models import Deployment
from celery import shared_task


@shared_task
def run_policy_engine():
    policies = Policy.objects.filter(is_active=True)
    if policies.exists():
        recent_logs = AuditLog.objects.order_by("-timestamp")[:100]
        for policy in policies:
            for log in recent_logs:
                violated = check_violation(log.metadata, policy.rules)
                if violated:
                    PolicyViolation.objects.create(
                        deployment=log.deployment,
                        policy=policy,
                        violation_type=log.action,
                        severity=log.severity,
                    )

