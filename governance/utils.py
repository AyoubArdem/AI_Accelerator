from .models import AuditLog

def LogAction(user, action , metadata=None):
    if metadata is None:
        metadata = {}
    audit = AuditLog.objects.create(
        user=user,
        action=action,
        metadata = metadata
        )

    return audit