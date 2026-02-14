from django.db import models

# Create your models here.
from django.conf import settings

class Projet(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} - {self.owner.username}'


class ModelVersion(models.Model):
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name='model_versions') 
    description = models.TextField(blank=True, null=True)
    field_file = models.FileField(upload_to='model_versions/')
    sample_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deployed = models.BooleanField(default=False)

    def __str__(self):
        return f'Version {self.id} of {self.projet.name}'


class Deployment(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        DEPLOYING = 'DEPLOYING', 'deploying'
        ACTIVE = 'ACTIVE', 'Active'
        STOP = 'STOPPED', 'Stopped'
        FAILED = 'FAILED', 'Failed'
        DELETED = 'DELETED', 'deleted'
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, default=None, on_delete=models.CASCADE)
    docker_container_id = models.CharField(max_length=255, null=True, blank=True)
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name='deployments')
    deployed_at = models.DateTimeField(auto_now_add=True)
    port = models.PositiveIntegerField(default=8000)
    endpoint_url = models.URLField()
    start_worker = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    logs = models.TextField(blank=True, null=True)


    class Meta:
        ordering = ['-deployed_at']

    def __str__(self):
        return f'Deployment of {self.model_version} - Status: {self.status}'