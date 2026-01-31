from .models import AuditLog

def LogAction(user, action , description , metadata=None):
    if metadata is None:
        metadata = {}
    audit = AuditLog.objects.create(
        user=user,
        action=action,
        description=description,
        metadata = metadata
        )

    return audit