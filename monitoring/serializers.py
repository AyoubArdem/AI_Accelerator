from rest_framework import serializers
from .models import (
    DataDrift,
    DeploymentMonitoringRecord,
    DeploymentStats,
    DeploymentAlert,
    Samples
)

class DeploymentMonitoringRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentMonitoringRecord
        fields = [
            "id",
            "deployment",
            "cpu_usage",
            "ram_usage",
            "latency_ms",
            "request_count",
            "error_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class DeploymentStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentStats
        fields = [
            "deployment",
            "cpu_usage",
            "ram_usage",
            "latency_ms",
            "request_count",
            "error_count",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class DeploymentAlertSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(
        source="get_alert_type_display",
        read_only=True
    )

    class Meta:
        model = DeploymentAlert
        fields = [
            "id",
            "deployment",
            "alert_type",
            "alert_type_display",
            "message",
            "created_at",
            "resolved",
        ]
        read_only_fields = ["id", "created_at"]

class SamplesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Samples
        fields = [
            "id",
            "model_version",
            "data",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

class DataDriftSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataDrift
        fields = [
            "id",
            "model_version",
            "kl_divergence",
            "wasserstein_distance",
            "ks_statistic",
            "chi_square",
            "results",
            "sample_count",
            "scanned_at",
        ]
        read_only_fields = ["id", "scanned_at"]