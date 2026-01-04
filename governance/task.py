from governance.engine import check_violation
from .models import Policy,PolicyViolation,AuditLog
from deployment.models import Deployment
from celery import shared_task


@shared_task
def run_policy_engine():
    policy_is_exist = Policy.objects.filter(is_active=True)
    if policy_is_exist :
        recent_logs = AuditLog.objects.order_by("-created_at")[:100]
        for policy in policy_is_exist:
            for log in recent_logs:
                violated = check_violation(log.metadata,policy.metadata)
                if violated:
                    PolicyViolation.objects.create(
                            deployment=Deployment,
                            policy=Policy,
                            violation_type=AuditLog.action,
                            severity=AuditLog.severity,

                    )

