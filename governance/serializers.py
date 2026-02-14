
from rest_framework import serializers
from .models import Alert, Policy, PolicyAssignment, AuditLog, PolicyViolation


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = [
            "id",
            "name",
            "user",
            "policy_type",
            "description",
            "is_active",
            "rules",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["user", "created_by", "created_at"]

    def validate_rules(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("rules must be a JSON object.")
        if not value:
            raise serializers.ValidationError("rules cannot be empty.")
        return value

class PolicyAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyAssignment
        fields = ["id", "policy", "deployment", "applied_by", "applied_at"]
        read_only_fields = ["applied_at", "applied_by"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication is required.")

        is_admin = getattr(user, "is_superuser", False) or getattr(user, "role", None) == "admin"
        if is_admin:
            return attrs

        policy = attrs.get("policy")
        deployment = attrs.get("deployment")
        if policy and policy.user_id != user.id:
            raise serializers.ValidationError("You can only assign your own policies.")
        if deployment and deployment.user_id != user.id:
            raise serializers.ValidationError("You can only assign policies to your own deployments.")
        return attrs

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "deployment", "user", "severity", "action", "description", "service", "metadata", "timestamp"]
        read_only_fields = ["timestamp"]

class ViolationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyViolation
        fields = [
            "id",
            "deployment",
            "policy",
            "violation_type",
            "severity",
            "resolved",
            "created_at",
        ]

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ["id", "policy_violation", "message", "sent", "timestamp"]
        read_only_fields = ["sent", "timestamp"]
