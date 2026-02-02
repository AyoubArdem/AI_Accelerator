
from rest_framework import serializers
from .models import Alert, Policy, PolicyAssignment, AuditLog, PolicyViolation


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = ["id", "name", "description", "rules", "created_by", "created_at"]
        read_only_fields = ["created_by", "created_at"]

class PolicyAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyAssignment
        fields = ["id", "policy", "deployment", "applied_by", "applied_at"]
        read_only_fields = ["applied_at", "applied_by"]

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "deployment", "user", "severity", "action", "description", "service", "metadata", "timestamp"]
        read_only_fields = ["timestamp"]

class ViolationSerializer(serializers.ModelSerializer):
    violation_metrics = serializers.SerializerMethodField(method_name='get_violation_metrics')
    def get_violation_metrics(self, obj):
        return{
            "deployment": obj.deployment.id,
            "policy":obj.policy.name if obj.policy else None,
            "violation_type": obj.violation_type,
            "severity": obj.severity,
            "resolved": obj.resolved,
            "created_at": obj.created_at,
            "Total Violations": PolicyViolation.objects.count(),
            "Unresolved Violations": PolicyViolation.objects.filter(resolved=False).count(),
            "Resolved Violations": PolicyViolation.objects.filter(resolved=True).count(),
            "High Severity Violations": PolicyViolation.objects.filter(severity="high").count(),
            "Medium Severity Violations": PolicyViolation.objects.filter(severity="medium").count(),
            "Low Severity Violations": PolicyViolation.objects.filter(severity="low").count(),
        }
    class Meta:
        model = PolicyViolation
        fields = ["violation_metrics"]

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ["id", "policy_violation", "message", "sent", "timestamp"]
        read_only_fields = ["sent", "timestamp"]