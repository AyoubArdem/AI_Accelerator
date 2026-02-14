from .models import AuditLog

def LogAction(user, action, description, metadata=None, service="governance", deployment=None, severity="medium"):
    if metadata is None:
        metadata = {}
    # AuditLog.deployment is required in the schema; skip invalid writes gracefully.
    if deployment is None:
        return None
    audit = AuditLog.objects.create(
        user=user,
        action=action,
        severity=severity,
        description=description,
        metadata=metadata,
        service=service,
        deployment=deployment
    )
    return audit
