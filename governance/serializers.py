from rest_framework import serializers
from .models import Policy, PolicyAssignment, AuditLog


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")

class PolicyAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyAssignment
        fields = "__all__"
        read_only_fields = ("applied_at","applied_by")

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = ("timestamp")
