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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deployed = models.BooleanField(default=False)

    def __str__(self):
        return f'Version {self.version_number} of {self.projet.name}'


class Deployment(models.Model):
    class StatusChoices(models.TextChoices):  
        PENDING = 'PENDING', 'Pending'
        DEPLOYING = 'DEPLOYING', 'deploying'
        ACTIVE = 'ACTIVE', 'Active'
        STOP = 'STOPPED', 'Stopped'
        FAILED = 'FAILED', 'Failed'
        DELETED = 'DELETED', 'deleted'
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    docker_container_id = models.AutoField(default=None)
    model_version = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name='deployments')
    deployed_at = models.DateTimeField(auto_now_add=True)
    port = models.PositiveIntegerField()
    endpoint_url = models.URLField()
    status = models.CharField(max_length=50, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    logs = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-deployed_at']

    def __str__(self):
        return f'Deployment of {self.model_version} - Status: {self.status}'