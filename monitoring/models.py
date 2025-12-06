from django.db import models
from deployement.models import Deployement
from django.utils import timezone

class DeploymentMonitoringRecord(models.Model):
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="monitoring_records")
    cpu_usage = models.FloatField()           
    ram_usage = models.FloatField()          
    latency_ms = models.FloatField()          
    request_count = models.IntegerField()
    error_count = models.IntegerField()

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Monitoring for {self.deployment.name} at {self.created_at}"


class DeploymentStats(models.Model):         
    deployement = models.OneToOneField(Deployment, on_delete=models.CASCADE, related_name="deployement_stats")
    cpu_usage = models.FloatField()           
    ram_usage = models.FloatField()          
    latency_ms = models.FloatField()          
    request_count = models.IntegerField()
    error_count = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"stats for {deployement.name} at {created_at}"

class  DeploymentAlert(models.Model):
    ALERT_TYPES=[
        ("high_cpu", "High CPU Usage"),
        ("high_ram", "High RAM Usage"),
        ("latency_spike", "Latency Spike"),
        ("model_down", "Model is not responding"),
        ("container_stopped", "Docker container stopped"),
    ]
 
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.alert_type} for {self.deployment.name}"

