from django.db import models
from django.conf import settings
from django.utils import timezone
from deployment.models import Deployment
import uuid


# Create your models here.

class Policy(models.Model):
    POLICY_TYPES =(
        ("deployment","DEPLOYMENT"),
        ("monitoring","MONITORING"),
        ("drift","DRIFT")
    )
    
    name = models.CharField(max_length=100, unique=True)
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    rules = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
        )
    created_at = models.DateTimeField(auto_now_add = True)

    def __str__(self):
        return f"{self.name} ({self.policy_type})"
    
class PolicyAssignment(models.Model):
    
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE)

    applied_at = models.DateTimeField(default=timezone.now)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        unique_together = ("policy", "deployment")

    def __str__(self):
        return f"{self.policy} -> {self.deployment}"


class AuditLog(models.Model):
    
    ACTIONS = (
        ("DEPLOY", "Deploy Model"),
        ("STOP", "Stop Deployment"),
        ("POLICY_APPLY", "Apply Policy"),
        ("POLICY_REMOVE", "Remove Policy"),
        ("LOGIN", "User Login"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    action = models.CharField(default=ACTIONS)
    metadata = models.JSONField(default=dict)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"
