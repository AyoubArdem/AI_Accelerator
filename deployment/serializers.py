from rest_framework import serializers
from .models import Deployment, ModelVersion, Projet

class ProjetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projet
        fields = ['id', 'owner', 'name', 'description', 'created_at', 'updated_at']


class ModelVersionSerializer(serializers.ModelSerializer):
    projet = ProjetSerializer(read_only=True)
    class Meta:
        model = ModelVersion
        fields = ['id', 'projet', 'description', 'field_file', 'created_at', 'updated_at', 'deployed']

class DeploymentSerializer(serializers.ModelSerializer):
    model_version = ModelVersionSerializer(read_only=True)
    
    class Meta:
        model = Deployment
        fields = ['id', 'model_version', 'deployed_at', 'endpoint_url', 'status', 'logs']