import uuid
from django.db import models
from deployment.models import Deployement , ModelVersion
from django.utils import timezone

class DeploymentMonitoringRecord(models.Model):
    deployment = models.ForeignKey(Deployement, on_delete=models.CASCADE, related_name="monitoring_records")
    cpu_usage = models.FloatField()           
    ram_usage = models.FloatField()          
    latency_ms = models.FloatField()          
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Monitoring for {self.deployment.name} at {self.created_at}"


class DeploymentStats(models.Model):         
    deployement = models.OneToOneField(Deployement, on_delete=models.CASCADE, related_name="deployement_stats")
    cpu_usage = models.FloatField()           
    ram_usage = models.FloatField()          
    latency_ms = models.FloatField()          
    request_count = models.IntegerField()
    error_count = models.IntegerField()
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"stats for {self.deployement.name} at {self.created_at}"

class  DeploymentAlert(models.Model):
    ALERT_TYPES=[
        ("high_cpu", "High CPU Usage"),
        ("high_ram", "High RAM Usage"),
        ("latency_spike", "Latency Spike"),
        ("model_down", "Model is not responding"),
        ("container_stopped", "Docker container stopped"),
    ]
 
    deployment = models.ForeignKey(Deployement, on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.alert_type} for {self.deployment.name}"


class BaseDrift(models.Model):
    model_version = models.OneToOneField(ModelVersion, on_delete=models.CASCADE, related_name="drifts")
    detected_at = models.DateTimeField(default=timezone.now)
    description = models.TextField(max_length=600,blank=True,null=True)
    features = models.JSONField(default=dict)
    sample_count = models.IntegerField()

    def __str__(self):
        return f"Drift for {self.model_version.name} detected at {self.detected_at}"
    
class DataDrift(BaseDrift):
    id = models.AutoField(primary_key=True, default=uuid.uuid4, editable=False)
    model_version = models.OneToOneField(ModelVersion, on_delete=models.CASCADE, related_name="data_drifts")
    kl_divergence = models.FloatField()
    wasserstein_distance = models.FloatField()
    ks_statistic = models.FloatField()
    chi_square = models.FloatField()
    results = models.JSONField(default=dict)  # Store detailed results
    scanned_at = models.DateTimeField(default=timezone.now)

    class Meta: 
        ordering = ["-detected_at"]

    def __str__(self):
        return f"Data Drift for {self.model_version.name} detected at {self.detected_at}"

class Samples(models.Model):
    model_version =models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name="samples")
    data = models.FileField(upload_to='samples/')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Sample for {self.model_version.name} at {self.created_at}"