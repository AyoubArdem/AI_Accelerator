from django.db import models
from django.conf import settings
from django.utils import timezone
from deployment.models import Deployment
import uuid


# Create your models here.

class Policy(models.Model):
    POLICY_TYPES =([
        ("deployment","DEPLOYMENT"),
        ("drift","DRIFT")
    ]
    )
    
    name = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
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
    
    ACTION_CHOICES = [
        ("DEPLOY", "Deploy Model"),
        ("STOP", "Stop Deployment"),
        ("DRIFT_DETECTED", "Data Drift Detected"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deployment_id = models.ForeignKey(Deployment , on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    severity = models.CharField(max_length=20, choices=[("low","Low"),("medium","Medium"),("high","High")])
    action = models.CharField(default=ACTION_CHOICES)
    description = models.TextField(max_length=300)
    service = models.CharField(max_length=25)
    metadata = models.JSONField(default=dict)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.service}:{self.action} by {self.user} at {self.timestamp}"



class PolicyViolation(models.Model):
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE)
    policy = models.ForeignKey(Policy, on_delete=models.SET_NULL, null=True)
    violation_type = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, choices=[("low","Low"),("medium","Medium"),("high","High")])
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Violation of {self.policy} on {self.deployment} - {self.violation_type}"


class Alert(models.Model):
    policy_violation = models.ForeignKey(PolicyViolation,on_delete=models.SET_NULL)
    message = models.TextField(max_length=300)
    sent = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alert : {self.message} @ {self.timestamp}"